"""
lumina/bridges/rest_bridge.py — Generic OpenAI-compatible REST backend adapter.

Wraps GenericRESTBridge from lumina_core behind the BaseLLMBackend interface.
Compatible with: OpenAI, Ollama, LM Studio, Groq, Together AI, Mistral API.
"""

from __future__ import annotations

import time
from typing import Any, Iterator, List, Optional

from lumina.llm.backend_base import (
    BackendResponse,
    BaseLLMBackend,
    FallbackBackend,
    GenerationConfig,
    HealthStatus,
    Message,
)


class RESTBackend(BaseLLMBackend):
    """
    Lumina backend adapter for any OpenAI-compatible REST API.

    Args:
        endpoint: Base URL (e.g. "https://api.openai.com/v1").
        api_key: Bearer token.
        model: Model name to pass in requests.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._model = model
        self._bridge: Optional[Any] = None
        self._available = False
        self._load_error: str = ""
        self._try_load()

    def _try_load(self) -> None:
        try:
            from mistral_inference.lumina_core import GenericRESTBridge  # type: ignore
            self._bridge = GenericRESTBridge(
                name="_lumina_rest",
                endpoint=self._endpoint,
                api_key=self._api_key or "",
                model=self._model,
            )
            self._available = True
        except Exception as exc:
            self._load_error = str(exc)

    @property
    def name(self) -> str:
        return f"rest:{self._model}@{self._endpoint}"

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

        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        try:
            chunks = list(self._bridge.respond(last_user, stream=False))
            content = "".join(chunks)
            return BackendResponse(content=content, model=self.name, finish_reason="stop")
        except Exception as exc:
            return BackendResponse(
                content=f"[REST error: {exc}]",
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
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        try:
            yield from self._bridge.respond(last_user, stream=True)
        except Exception as exc:
            yield f"[REST stream error: {exc}]"

    def tokenize(self, text: str) -> List[int]:
        return list(range(max(1, len(text) // 4)))

    def healthcheck(self) -> HealthStatus:
        if not self._available:
            return HealthStatus(healthy=False, backend=self.name, message=self._load_error)
        return HealthStatus(healthy=True, backend=self.name, message="REST backend ready.")
