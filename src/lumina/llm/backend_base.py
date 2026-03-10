"""
lumina/llm/backend_base.py — Abstract LLM backend interface.

All language-model backends (Mistral, Claude, REST, fallback) implement
BaseLLMBackend.  Lumina's orchestrator only calls this interface —
it never imports raw Mistral or Anthropic code directly.

This makes the backend fully replaceable: swap Mistral for any other
inference engine without touching the orchestration layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """A single message in a conversation history."""
    role: str           # "user" | "assistant" | "system"
    content: str


@dataclass
class GenerationConfig:
    """Generation hyperparameters passed from the orchestrator to the backend."""
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.95
    stop_sequences: List[str] = field(default_factory=list)
    stream: bool = False


@dataclass
class BackendResponse:
    """Structured response from any backend."""
    content: str                          # Full generated text
    model: str = "unknown"               # Backend identifier
    tokens_used: int = 0
    finish_reason: str = "stop"          # stop | length | error
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthStatus:
    healthy: bool
    backend: str
    message: str = ""
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseLLMBackend(ABC):
    """
    Abstract interface that all Lumina language-model backends must implement.

    Lumina's orchestrator depends only on this class — never on any
    concrete backend.  This enforces the architectural rule:

        Lumina owns orchestration.  Mistral (or Claude, or any other model)
        is a replaceable generation engine behind this interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend identifier (e.g. 'mistral-7b', 'claude-opus')."""

    @abstractmethod
    def generate(
        self,
        messages: List[Message],
        system_prompt: str = "",
        config: Optional[GenerationConfig] = None,
    ) -> BackendResponse:
        """
        Generate a response for a conversation.

        Args:
            messages: Conversation history (including the latest user turn).
            system_prompt: System-level instruction prepended to context.
            config: Generation hyperparameters.

        Returns:
            BackendResponse with the generated text.
        """

    def generate_stream(
        self,
        messages: List[Message],
        system_prompt: str = "",
        config: Optional[GenerationConfig] = None,
    ) -> Iterator[str]:
        """
        Streaming variant.  Default implementation falls back to generate().
        Override for true token-by-token streaming.
        """
        response = self.generate(messages, system_prompt, config)
        yield response.content

    @abstractmethod
    def tokenize(self, text: str) -> List[int]:
        """
        Tokenize *text* and return a list of token IDs.
        Used for token-budget accounting in the planner.
        """

    def embed(self, text: str) -> List[float]:
        """
        Return a dense embedding vector for *text*.
        Default: returns an empty list (embedding not supported).
        Override in backends that provide embeddings.
        """
        return []

    @abstractmethod
    def healthcheck(self) -> HealthStatus:
        """Return the backend's health status."""

    def reset_history(self) -> None:
        """
        Clear any conversation history held by the backend.
        Default: no-op.  Override in backends that track history internally.
        """


# ---------------------------------------------------------------------------
# Fallback backend (no external model required)
# ---------------------------------------------------------------------------

class FallbackBackend(BaseLLMBackend):
    """
    Backend used when no external model is available.

    Returns structured introspective responses based on the system prompt
    and message content rather than actual language model inference.
    Honest about its limitations.
    """

    @property
    def name(self) -> str:
        return "fallback"

    def generate(
        self,
        messages: List[Message],
        system_prompt: str = "",
        config: Optional[GenerationConfig] = None,
    ) -> BackendResponse:
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "(no input)",
        )
        content = (
            f"[Lumina — operating without external language model]\n\n"
            f"I received: \"{last_user[:200]}\"\n\n"
            f"My internal memory and reasoning systems are fully active, "
            f"but I cannot generate natural language responses without a "
            f"language model backend. Please configure a backend in "
            f"~/.lumina_ai/config.yaml or via the LUMINA_BACKEND_TYPE "
            f"environment variable."
        )
        return BackendResponse(content=content, model="fallback", finish_reason="stop")

    def tokenize(self, text: str) -> List[int]:
        # Approximate: 4 chars ≈ 1 token
        return list(range(max(1, len(text) // 4)))

    def healthcheck(self) -> HealthStatus:
        return HealthStatus(healthy=True, backend="fallback",
                            message="Fallback backend (no LLM) is active.")
