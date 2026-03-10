"""
lumina/bridges/anthropic_bridge.py — Anthropic Claude backend adapter.

Wraps ClaudeBridge from lumina_core behind the BaseLLMBackend interface.
Supports streaming with adaptive thinking (Claude decides depth).
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


class AnthropicBackend(BaseLLMBackend):
    """
    Lumina backend adapter for Anthropic Claude.

    Delegates to ClaudeBridge (from lumina_core), which handles streaming,
    history compression, and adaptive thinking budget.

    Args:
        api_key: Anthropic API key (falls back to ANTHROPIC_API_KEY env var).
        model: Claude model ID (default: claude-opus-4-6).
        max_tokens: Default maximum tokens per response.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-opus-4-6",
        max_tokens: int = 8096,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._bridge: Optional[Any] = None
        self._available = False
        self._load_error: str = ""
        self._try_load()

    def _try_load(self) -> None:
        try:
            from mistral_inference.lumina_core import ClaudeBridge  # type: ignore
            bridge = ClaudeBridge(api_key=self._api_key)
            self._bridge = bridge
            self._available = True
        except ImportError as exc:
            self._load_error = f"ClaudeBridge not importable: {exc}"
        except Exception as exc:
            self._load_error = f"Claude bridge init failed: {exc}"

    @property
    def name(self) -> str:
        return f"anthropic:{self._model}"

    @property
    def available(self) -> bool:
        return self._available

    def generate(
        self,
        messages: List[Message],
        system_prompt: str = "",
        config: Optional[GenerationConfig] = None,
    ) -> BackendResponse:
        if not self._available or self._bridge is None:
            return FallbackBackend().generate(messages, system_prompt, config)

        cfg = config or GenerationConfig()
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )

        try:
            bridge = self._bridge
            # Sync history in bridge
            bridge._history = self._to_bridge_history(messages)
            if system_prompt and hasattr(bridge, "_system_prompt"):
                bridge._system_prompt = system_prompt

            chunks = list(bridge.respond(last_user, stream=True))
            content = "".join(chunks)
            return BackendResponse(
                content=content,
                model=self.name,
                finish_reason="stop",
            )
        except Exception as exc:
            return BackendResponse(
                content=f"[Claude error: {exc}]",
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
            yield from FallbackBackend().generate_stream(messages, system_prompt, config)
            return

        cfg = config or GenerationConfig()
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )

        try:
            bridge = self._bridge
            bridge._history = self._to_bridge_history(messages)
            if system_prompt and hasattr(bridge, "_system_prompt"):
                bridge._system_prompt = system_prompt
            yield from bridge.respond(last_user, stream=True)
        except Exception as exc:
            yield f"[Claude stream error: {exc}]"

    def tokenize(self, text: str) -> List[int]:
        # Claude uses approximately 4 chars per token
        return list(range(max(1, len(text) // 4)))

    def healthcheck(self) -> HealthStatus:
        if not self._available:
            return HealthStatus(
                healthy=False,
                backend=self.name,
                message=self._load_error,
            )
        return HealthStatus(
            healthy=True,
            backend=self.name,
            message="Anthropic bridge ready.",
        )

    def reset_history(self) -> None:
        if self._bridge is not None and hasattr(self._bridge, "reset_history"):
            self._bridge.reset_history()

    def _to_bridge_history(self, messages: List[Message]) -> List[Dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]
