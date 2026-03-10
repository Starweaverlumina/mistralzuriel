"""Tests for lumina.reasoning.prompt_builder."""

import pytest
from lumina.reasoning.prompt_builder import (
    PromptContext,
    build_system_prompt,
    build_messages,
    token_count_estimate,
)
from lumina.llm.backend_base import Message
from lumina.memory.retrieval import MemoryContext


class TestTokenCountEstimate:
    def test_empty_string(self):
        assert token_count_estimate("") >= 1

    def test_short_text(self):
        count = token_count_estimate("hello")
        assert count >= 1

    def test_longer_text(self):
        text = "x" * 400
        count = token_count_estimate(text)
        assert count == 100  # 400 / 4


class TestBuildSystemPrompt:
    def test_identity_always_present(self):
        ctx = PromptContext(user_input="hi", system_identity="You are TestBot.")
        prompt = build_system_prompt(ctx)
        assert "You are TestBot." in prompt

    def test_no_memory_no_memory_block(self):
        ctx = PromptContext(user_input="hi")
        prompt = build_system_prompt(ctx)
        # Should not have memory header if no memories
        assert "[Relevant memories" not in prompt

    def test_working_memory_injected(self):
        class FakeWM:
            def summary(self):
                return "chunk 1; chunk 2"

            def active(self):
                return [{"content": "chunk 1"}, {"content": "chunk 2"}]

        ctx = PromptContext(user_input="hi", working_memory=FakeWM())
        prompt = build_system_prompt(ctx)
        assert "chunk 1" in prompt

    def test_user_model_injected(self):
        ctx = PromptContext(
            user_input="hi",
            user_model_summary="Prefers concise responses. Interested in Python.",
        )
        prompt = build_system_prompt(ctx)
        assert "Prefers concise" in prompt

    def test_tool_context_injected(self):
        ctx = PromptContext(
            user_input="hi",
            tool_context="  • web_fetch: Fetch a URL.",
        )
        prompt = build_system_prompt(ctx)
        assert "web_fetch" in prompt

    def test_reasoning_notes_injected(self):
        ctx = PromptContext(
            user_input="hi",
            reasoning_notes="Key insight: user wants a summary.",
        )
        prompt = build_system_prompt(ctx)
        assert "Key insight" in prompt

    def test_state_signals(self):
        ctx = PromptContext(
            user_input="hi",
            lumina_state_name="THINKING",
            consciousness_state="ABSORBING",
        )
        prompt = build_system_prompt(ctx)
        assert "THINKING" in prompt
        assert "ABSORBING" in prompt

    def test_episodic_memory_from_context(self):
        mem_ctx = MemoryContext(
            episodic_memories=[{
                "content": "We discussed Python last time.",
                "topic": "programming",
                "emotional_weight": 0.7,
                "timestamp": "2025-01-01",
            }],
        )
        ctx = PromptContext(user_input="hi", memory_context=mem_ctx)
        prompt = build_system_prompt(ctx)
        assert "Python" in prompt

    def test_empty_context_returns_identity(self):
        ctx = PromptContext(user_input="hi", system_identity="Base identity.")
        prompt = build_system_prompt(ctx)
        assert prompt.strip() != ""
        assert "Base identity" in prompt


class TestBuildMessages:
    def test_user_turn_appended(self):
        ctx = PromptContext(user_input="My question")
        messages = build_messages(ctx)
        # Last message should be the user turn
        assert messages[-1].role == "user"
        assert messages[-1].content == "My question"

    def test_history_preserved(self):
        history = [
            Message(role="user", content="previous question"),
            Message(role="assistant", content="previous answer"),
        ]
        ctx = PromptContext(user_input="new question", conversation_history=history)
        messages = build_messages(ctx)
        # History + new user turn
        assert len(messages) == 3
        assert messages[0].content == "previous question"
        assert messages[-1].content == "new question"

    def test_system_messages_in_history_skipped(self):
        history = [
            Message(role="system", content="old system"),
            Message(role="user", content="user msg"),
        ]
        ctx = PromptContext(user_input="new", conversation_history=history)
        messages = build_messages(ctx)
        # system message should be filtered
        roles = [m.role for m in messages]
        assert "system" not in roles

    def test_custom_system_prompt(self):
        ctx = PromptContext(user_input="hi")
        messages = build_messages(ctx, system_prompt="Custom system")
        # Messages should not include system (it's passed separately)
        roles = [m.role for m in messages]
        assert "system" not in roles
        assert messages[-1].content == "hi"
