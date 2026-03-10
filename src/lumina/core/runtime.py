"""
lumina/core/runtime.py — Lumina Runtime.

The Runtime assembles all subsystems and provides the high-level
interface used by the CLI and API server.

                     ┌──────────────────────────────────┐
                     │           LuminaRuntime           │
                     │                                   │
                     │  ┌─────────┐   ┌──────────────┐ │
    User Input  ───► │  │ Orchestr│──►│  Backend     │ │ ──► Response
                     │  │ ator    │   │ (Mistral/    │ │
                     │  └────┬────┘   │  Claude/REST)│ │
                     │       │        └──────────────┘ │
                     │  ┌────▼────┐   ┌──────────────┐ │
                     │  │ Memory  │   │ Tools/Skills │ │
                     │  │ Layers  │   │ (policy gate)│ │
                     │  └─────────┘   └──────────────┘ │
                     │                                   │
                     │  ┌─────────────────────────────┐ │
                     │  │   State Machine (IDLE → ... │ │
                     │  └─────────────────────────────┘ │
                     └──────────────────────────────────┘

Lumina owns control flow.
Mistral (or any backend) is called by the orchestrator for generation only.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterator, Optional

from lumina.config.loader import LuminaConfig
from lumina.core.orchestrator import Orchestrator, TurnResult
from lumina.core.session import Session
from lumina.core.state_machine import LuminaState, StateMachine
from lumina.llm.backend_base import BaseLLMBackend, FallbackBackend, GenerationConfig
from lumina.reasoning.planner import Planner
from lumina.tools.executor import ToolExecutor
from lumina.tools.policies import PolicyConfig
from lumina.tools.registry import ToolRegistry, build_default_registry

log = logging.getLogger(__name__)


class LuminaRuntime:
    """
    Top-level Lumina runtime.

    This is the single object the CLI and API server interact with.
    It initializes all subsystems and delegates work to the Orchestrator.

    Args:
        config: Loaded LuminaConfig.
        backend: Pre-built LLM backend (if None, auto-detected from config).
    """

    def __init__(
        self,
        config: LuminaConfig,
        backend: Optional[BaseLLMBackend] = None,
    ) -> None:
        self._config = config
        self._sm = StateMachine()
        self._session = Session()

        self._sm.transition(LuminaState.INITIALIZING)

        # Backend
        self._backend: BaseLLMBackend = backend or self._auto_backend(config)
        log.info("Backend: %s", self._backend.name)

        # Core Lumina object (from legacy lumina_core)
        self._lumina_core: Optional[Any] = self._init_lumina_core(config)

        # Tools
        skills_engine = getattr(self._lumina_core, "skills", None)
        self._registry: ToolRegistry = build_default_registry(skills_engine)
        policy_cfg = PolicyConfig(
            enabled=config.tools.enabled,
            allow_shell=config.tools.allow_shell,
            allow_file_write=config.tools.allow_file_write,
            allow_web_fetch=config.tools.allow_web_fetch,
            dry_run=config.tools.dry_run,
            audit_log=config.tools.audit_log,
            file_scope=config.tools.file_scope,
        )
        guardrails = getattr(self._lumina_core, "guardrails", None)
        self._executor = ToolExecutor(
            registry=self._registry,
            policy_config=policy_cfg,
            guardrails=guardrails,
        )

        # Orchestrator
        gen_config = GenerationConfig(
            max_tokens=512,
            temperature=0.7,
            stream=False,
        )
        self._orchestrator = Orchestrator(
            backend=self._backend,
            state_machine=self._sm,
            session=self._session,
            lumina_core=self._lumina_core,
            planner=Planner(
                max_steps=config.reasoning.planner_max_steps,
                token_budget=config.reasoning.bh_token_budget,
            ),
            tool_registry=self._registry,
            tool_executor=self._executor,
            system_identity=config.system_prompt,
            gen_config=gen_config,
        )

        self._sm.transition(LuminaState.LISTENING)
        log.info("Lumina runtime initialized. State: LISTENING.")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def state(self) -> LuminaState:
        return self._sm.state

    @property
    def session(self) -> Session:
        return self._session

    @property
    def backend(self) -> BaseLLMBackend:
        return self._backend

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def chat(
        self,
        user_input: str,
        topic: Optional[str] = None,
        emotional_weight: float = 0.5,
        tone_state: Optional[Dict[str, Any]] = None,
    ) -> TurnResult:
        """
        Process one user message through the full Lumina pipeline.

        Returns:
            TurnResult with the response and all lifecycle metadata.
        """
        return self._orchestrator.turn(
            user_input=user_input,
            topic=topic,
            emotional_weight=emotional_weight,
            tone_state=tone_state,
            stream=False,
        )

    def chat_stream(
        self,
        user_input: str,
        topic: Optional[str] = None,
        emotional_weight: float = 0.5,
        tone_state: Optional[Dict[str, Any]] = None,
    ) -> Iterator[str]:
        """
        Process one user message and stream the response token by token.

        Yields:
            Response text chunks.
        """
        yield from self._orchestrator.turn_stream(
            user_input=user_input,
            topic=topic,
            emotional_weight=emotional_weight,
            tone_state=tone_state,
        )

    def healthcheck(self) -> Dict[str, Any]:
        """Return the health status of all subsystems."""
        backend_health = self._backend.healthcheck()
        return {
            "lumina_state": self._sm.state.name,
            "backend": {
                "name": backend_health.backend,
                "healthy": backend_health.healthy,
                "message": backend_health.message,
            },
            "session": {
                "id": self._session.session_id,
                "turns": self._session.turn_count,
                "duration_s": self._session.duration(),
            },
            "tools": {
                "count": len(self._registry),
                "names": self._registry.tool_names(),
            },
            "core_loaded": self._lumina_core is not None,
        }

    def introspect(self) -> Dict[str, Any]:
        """Return full introspection state (for debug / 'introspect' CLI command)."""
        base = self.healthcheck()
        if self._lumina_core is not None:
            try:
                base["lumina_core"] = self._lumina_core.introspect()
            except Exception:
                pass
        base["state_history"] = self._sm.history()
        base["audit_log"] = self._executor.audit.recent(10)
        return base

    def shutdown(self) -> None:
        """Gracefully shut down the runtime (save session, close DB)."""
        self._sm.transition(LuminaState.SHUTDOWN)

        if self._lumina_core is not None:
            try:
                self._lumina_core._save()
                proactive = getattr(self._lumina_core, "proactive", None)
                if proactive is not None:
                    proactive.stop()
            except Exception as exc:
                log.warning("Lumina core shutdown error: %s", exc)

        self._session.close()
        log.info("Lumina runtime shut down.")

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _auto_backend(config: LuminaConfig) -> BaseLLMBackend:
        """Select and initialize backend from config."""
        btype = (config.backend.type or "auto").lower()

        if btype == "mistral" or (btype == "auto" and config.backend.model_path):
            try:
                from lumina.llm.mistral_backend import MistralBackend
                b = MistralBackend(model_path=config.backend.model_path)
                if b.available:
                    return b
            except Exception as exc:
                log.warning("Mistral backend unavailable: %s", exc)

        if btype == "claude" or btype == "anthropic" or (
            btype == "auto" and config.backend.api_key
        ):
            try:
                from lumina.bridges.anthropic_bridge import AnthropicBackend
                b = AnthropicBackend(api_key=config.backend.api_key)
                if b.available:
                    return b
            except Exception as exc:
                log.warning("Anthropic backend unavailable: %s", exc)

        if btype == "rest" or (btype == "auto" and config.backend.endpoint):
            try:
                from lumina.bridges.rest_bridge import RESTBackend
                b = RESTBackend(
                    endpoint=config.backend.endpoint or "",
                    api_key=config.backend.api_key,
                    model=config.backend.model_name or "gpt-4o",
                )
                if b.available:
                    return b
            except Exception as exc:
                log.warning("REST backend unavailable: %s", exc)

        if btype == "auto":
            # Try auto-detect from lumina_core's LLMBridge.auto_detect()
            try:
                from mistral_inference.lumina_core import LLMBridge  # type: ignore
                bridge = LLMBridge.auto_detect()
                # Wrap the legacy bridge in a thin adapter
                return _LegacyBridgeAdapter(bridge)
            except Exception:
                pass

        log.warning("No LLM backend available — using FallbackBackend.")
        return FallbackBackend()

    @staticmethod
    def _init_lumina_core(config: LuminaConfig) -> Optional[Any]:
        """Initialize the core Lumina object from lumina_core."""
        try:
            from mistral_inference.lumina_core import Lumina  # type: ignore
            nexus_path = config.resolved_state_path()
            lumina = Lumina(
                nexus_path=nexus_path,
                fractal_shells=config.reasoning.fractal_shells,
            )
            return lumina
        except ImportError:
            log.warning("mistral_inference not available — running without Lumina core.")
            return None
        except Exception as exc:
            log.warning("Lumina core initialization failed: %s — continuing without it.", exc)
            return None


# ---------------------------------------------------------------------------
# Thin adapter for legacy LLMBridge
# ---------------------------------------------------------------------------

class _LegacyBridgeAdapter(BaseLLMBackend):
    """Wraps a legacy LLMBridge (from lumina_core) as a BaseLLMBackend."""

    def __init__(self, bridge: Any) -> None:
        self._bridge = bridge

    @property
    def name(self) -> str:
        return self._bridge.__class__.__name__

    def generate(self, messages, system_prompt="", config=None):
        from lumina.llm.backend_base import BackendResponse
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        try:
            chunks = list(self._bridge.respond(last_user, stream=False))
            return BackendResponse(content="".join(chunks), model=self.name)
        except Exception as exc:
            return BackendResponse(content=f"[Error: {exc}]", model=self.name, finish_reason="error")

    def generate_stream(self, messages, system_prompt="", config=None):
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        try:
            yield from self._bridge.respond(last_user, stream=True)
        except Exception as exc:
            yield f"[Error: {exc}]"

    def tokenize(self, text):
        return list(range(max(1, len(text) // 4)))

    def healthcheck(self):
        from lumina.llm.backend_base import HealthStatus
        return HealthStatus(healthy=True, backend=self.name, message="Legacy bridge active.")
