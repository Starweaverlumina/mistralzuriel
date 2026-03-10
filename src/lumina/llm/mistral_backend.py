"""
lumina/llm/mistral_backend.py — Mistral Backend Adapter.

Wraps the existing MistralBridge from mistral_inference.lumina_core
behind the BaseLLMBackend interface.

This is the encapsulation seam: all Mistral-specific code lives here.
The orchestrator never imports MistralBridge directly.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Iterator, List, Optional

from lumina.llm.backend_base import (
    BackendResponse,
    BaseLLMBackend,
    FallbackBackend,
    GenerationConfig,
    HealthStatus,
    Message,
)


class MistralBackend(BaseLLMBackend):
    """
    Lumina backend adapter for local Mistral inference.

    Delegates all generation to MistralBridge (from lumina_core) while
    exposing only the BaseLLMBackend interface to the rest of Lumina.

    Args:
        model_path: Path to a Mistral checkpoint directory.
        max_tokens: Default max generation tokens.
        temperature: Default sampling temperature.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> None:
        self._model_path = model_path
        self._default_max_tokens = max_tokens
        self._default_temperature = temperature
        self._bridge: Optional[Any] = None
        self._available = False
        self._load_error: str = ""

        self._try_load()

    def _try_load(self) -> None:
        """Attempt to import and initialize MistralBridge."""
        try:
            from mistral_inference.lumina_core import MistralBridge  # type: ignore
            bridge = MistralBridge(model_path=self._model_path)
            self._bridge = bridge
            self._available = True
        except ImportError as exc:
            self._load_error = f"mistral_inference not importable: {exc}"
        except Exception as exc:
            self._load_error = f"Mistral model load failed: {exc}"

    @property
    def name(self) -> str:
        if self._model_path:
            import os
            return f"mistral:{os.path.basename(self._model_path)}"
        return "mistral:auto"

    @property
    def available(self) -> bool:
        return self._available

    # ------------------------------------------------------------------
    # BaseLLMBackend interface
    # ------------------------------------------------------------------

    def generate(
        self,
        messages: List[Message],
        system_prompt: str = "",
        config: Optional[GenerationConfig] = None,
    ) -> BackendResponse:
        if not self._available or self._bridge is None:
            fallback = FallbackBackend()
            return fallback.generate(messages, system_prompt, config)

        cfg = config or GenerationConfig()
        t0 = time.time()

        # Convert Message list to the format MistralBridge expects
        # MistralBridge.respond() takes a single string; for multi-turn
        # we use respond() with the last user message plus injected history.
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )

        try:
            bridge = self._bridge
            # Temporarily override history in bridge if it supports it
            if hasattr(bridge, "_history"):
                bridge._history = self._messages_to_bridge_history(messages, system_prompt)

            chunks = []
            for chunk in bridge.respond(
                last_user,
                stream=True,
                max_tokens=cfg.max_tokens,
                temperature=cfg.temperature,
            ):
                chunks.append(chunk)

            content = "".join(chunks)
            latency = (time.time() - t0) * 1000
            return BackendResponse(
                content=content,
                model=self.name,
                finish_reason="stop",
                metadata={"latency_ms": latency},
            )
        except Exception as exc:
            return BackendResponse(
                content=f"[Mistral generation error: {exc}]",
                model=self.name,
                finish_reason="error",
            )

    def generate_stream(
        self,
        messages: List[Message],
        system_prompt: str = "",
        config: Optional[GenerationConfig] = None,
    ) -> Iterator[str]:
        if not self._available or self._bridge is None:
            fallback = FallbackBackend()
            yield from fallback.generate_stream(messages, system_prompt, config)
            return

        cfg = config or GenerationConfig()
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )

        try:
            bridge = self._bridge
            if hasattr(bridge, "_history"):
                bridge._history = self._messages_to_bridge_history(messages, system_prompt)

            yield from bridge.respond(
                last_user,
                stream=True,
                max_tokens=cfg.max_tokens,
                temperature=cfg.temperature,
            )
        except Exception as exc:
            yield f"[Mistral stream error: {exc}]"

    def tokenize(self, text: str) -> List[int]:
        if self._bridge is not None and hasattr(self._bridge, "_tokenizer"):
            try:
                return self._bridge._tokenizer.encode(text)
            except Exception:
                pass
        # Fallback: 4 chars ≈ 1 token
        return list(range(max(1, len(text) // 4)))

    def healthcheck(self) -> HealthStatus:
        if not self._available:
            return HealthStatus(
                healthy=False,
                backend=self.name,
                message=self._load_error or "Mistral not available.",
            )
        t0 = time.time()
        # Light probe: just check the bridge exists
        ok = self._bridge is not None
        latency = (time.time() - t0) * 1000
        return HealthStatus(
            healthy=ok,
            backend=self.name,
            message="Mistral backend ready." if ok else "Bridge is None.",
            latency_ms=latency,
        )

    def reset_history(self) -> None:
        if self._bridge is not None and hasattr(self._bridge, "reset_history"):
            self._bridge.reset_history()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _messages_to_bridge_history(
        self,
        messages: List[Message],
        system_prompt: str,
    ) -> List[Dict[str, str]]:
        """Convert BaseLLMBackend Message list to MistralBridge history format."""
        history = []
        if system_prompt:
            history.append({"role": "system", "content": system_prompt})
        for m in messages:
            history.append({"role": m.role, "content": m.content})
        return history
