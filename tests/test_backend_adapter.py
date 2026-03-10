"""Tests for lumina.llm.backend_base and FallbackBackend."""

import pytest
from lumina.llm.backend_base import (
    BackendResponse,
    BaseLLMBackend,
    FallbackBackend,
    GenerationConfig,
    HealthStatus,
    Message,
)


class TestMessage:
    def test_create(self):
        m = Message(role="user", content="hello")
        assert m.role == "user"
        assert m.content == "hello"


class TestGenerationConfig:
    def test_defaults(self):
        cfg = GenerationConfig()
        assert cfg.max_tokens == 512
        assert cfg.temperature == 0.7
        assert cfg.stream is False


class TestBackendResponse:
    def test_defaults(self):
        r = BackendResponse(content="hello")
        assert r.content == "hello"
        assert r.model == "unknown"
        assert r.finish_reason == "stop"


class TestFallbackBackend:
    def setup_method(self):
        self.backend = FallbackBackend()

    def test_name(self):
        assert self.backend.name == "fallback"

    def test_generate_returns_response(self):
        messages = [Message(role="user", content="test input")]
        response = self.backend.generate(messages)
        assert isinstance(response, BackendResponse)
        assert "test input" in response.content or "Lumina" in response.content

    def test_generate_with_empty_messages(self):
        response = self.backend.generate([])
        assert isinstance(response, BackendResponse)

    def test_generate_stream(self):
        messages = [Message(role="user", content="stream test")]
        chunks = list(self.backend.generate_stream(messages))
        assert len(chunks) >= 1
        full = "".join(chunks)
        assert len(full) > 0

    def test_tokenize(self):
        tokens = self.backend.tokenize("hello world")
        assert isinstance(tokens, list)
        assert len(tokens) > 0

    def test_embed_returns_empty(self):
        result = self.backend.embed("test")
        assert result == []

    def test_healthcheck(self):
        health = self.backend.healthcheck()
        assert isinstance(health, HealthStatus)
        assert health.healthy is True
        assert health.backend == "fallback"

    def test_reset_history_no_op(self):
        # Should not raise
        self.backend.reset_history()

    def test_is_abstract_base(self):
        """BaseLLMBackend cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseLLMBackend()  # type: ignore


class TestBaseLLMBackendContract:
    """Verify that a minimal concrete implementation satisfies the contract."""

    def test_minimal_implementation(self):
        class MinimalBackend(BaseLLMBackend):
            @property
            def name(self) -> str:
                return "minimal"

            def generate(self, messages, system_prompt="", config=None):
                return BackendResponse(content="ok", model="minimal")

            def tokenize(self, text):
                return [1, 2, 3]

            def healthcheck(self):
                return HealthStatus(healthy=True, backend="minimal")

        backend = MinimalBackend()
        assert backend.name == "minimal"

        msgs = [Message(role="user", content="hi")]
        resp = backend.generate(msgs)
        assert resp.content == "ok"

        # Default stream delegates to generate()
        chunks = list(backend.generate_stream(msgs))
        assert "ok" in "".join(chunks)

        assert backend.tokenize("test") == [1, 2, 3]
        assert backend.embed("x") == []

        health = backend.healthcheck()
        assert health.healthy is True
