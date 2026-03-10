"""Tests for lumina.core.orchestrator — using FallbackBackend (no LLM required)."""

import pytest
from lumina.core.orchestrator import Orchestrator, TurnResult
from lumina.core.session import Session
from lumina.core.state_machine import LuminaState, StateMachine
from lumina.llm.backend_base import FallbackBackend, Message
from lumina.reasoning.planner import Planner
from lumina.tools.registry import ToolRegistry, ToolDescriptor
from lumina.tools.executor import ToolExecutor
from lumina.tools.policies import PolicyConfig


def _make_orchestrator(lumina_core=None, tools=None):
    """Factory for a test orchestrator with FallbackBackend."""
    sm = StateMachine(initial=LuminaState.LISTENING)
    session = Session()
    registry = ToolRegistry()
    if tools:
        for name, fn in tools.items():
            registry.register(ToolDescriptor(
                name=name, description=f"Test tool: {name}",
                category="memory", fn=fn,
            ))
    executor = ToolExecutor(registry=registry, policy_config=PolicyConfig())
    return Orchestrator(
        backend=FallbackBackend(),
        state_machine=sm,
        session=session,
        lumina_core=lumina_core,
        planner=Planner(max_steps=5, token_budget=1000),
        tool_registry=registry,
        tool_executor=executor,
        system_identity="You are Lumina (test).",
    )


class TestOrchestratorTurn:
    def test_basic_turn_returns_result(self):
        orch = _make_orchestrator()
        result = orch.turn("Hello!")
        assert isinstance(result, TurnResult)
        assert result.user_input == "Hello!"
        assert result.response != ""
        assert result.success

    def test_state_returns_to_listening(self):
        sm = StateMachine(initial=LuminaState.LISTENING)
        session = Session()
        orch = Orchestrator(
            backend=FallbackBackend(),
            state_machine=sm,
            session=session,
            tool_registry=ToolRegistry(),
        )
        orch.turn("test")
        assert sm.state == LuminaState.LISTENING

    def test_session_records_turn(self):
        orch = _make_orchestrator()
        orch.turn("Hello!")
        assert orch._session.turn_count == 1

    def test_conversation_history_updated(self):
        orch = _make_orchestrator()
        orch.turn("First message")
        assert len(orch._history) == 2  # user + assistant
        assert orch._history[0].role == "user"
        assert orch._history[1].role == "assistant"

    def test_multi_turn_history_grows(self):
        orch = _make_orchestrator()
        orch.turn("Message 1")
        orch.turn("Message 2")
        assert len(orch._history) == 4

    def test_reset_history(self):
        orch = _make_orchestrator()
        orch.turn("Hello")
        orch.reset_history()
        assert len(orch._history) == 0

    def test_turn_result_has_memory_context(self):
        orch = _make_orchestrator()
        result = orch.turn("Remember this?")
        assert result.memory_context is not None

    def test_turn_result_has_plan(self):
        orch = _make_orchestrator()
        result = orch.turn("test")
        assert result.plan is not None

    def test_turn_result_topic_default(self):
        orch = _make_orchestrator()
        result = orch.turn("Hello", topic="test_topic")
        assert result.topic == "test_topic"

    def test_turn_stream_yields_chunks(self):
        orch = _make_orchestrator()
        chunks = list(orch.turn_stream("Hello!"))
        assert len(chunks) >= 1
        full = "".join(chunks)
        assert len(full) > 0

    def test_session_reflects_all_turns(self):
        orch = _make_orchestrator()
        orch.turn("Turn 1")
        orch.turn("Turn 2")
        orch.turn("Turn 3")
        assert orch._session.turn_count == 3

    def test_error_recovery_on_bad_input(self):
        """Orchestrator should handle errors without crashing."""
        orch = _make_orchestrator()
        # Even empty input should return a result
        result = orch.turn("")
        assert isinstance(result, TurnResult)


class TestOrchestratorWithTools:
    def test_tool_results_in_turn(self):
        orch = _make_orchestrator(tools={
            "recall_topic": lambda topic="general": f"Memory about {topic}",
        })
        # The planner only calls tools when heuristics trigger them
        result = orch.turn("recall my notes about general")
        assert isinstance(result, TurnResult)

    def test_blocked_tool_still_completes_turn(self):
        """A blocked tool should not crash the turn."""
        from lumina.tools.policies import PolicyConfig
        sm = StateMachine(initial=LuminaState.LISTENING)
        session = Session()
        registry = ToolRegistry()
        registry.register(ToolDescriptor(
            name="run_shell", description="Shell", category="shell",
            fn=lambda cmd="": "output",
        ))
        executor = ToolExecutor(
            registry=registry,
            policy_config=PolicyConfig(allow_shell=False),
        )
        orch = Orchestrator(
            backend=FallbackBackend(),
            state_machine=sm,
            session=session,
            tool_registry=registry,
            tool_executor=executor,
        )
        result = orch.turn("run command ls")
        assert result.success  # turn completes despite tool being blocked
