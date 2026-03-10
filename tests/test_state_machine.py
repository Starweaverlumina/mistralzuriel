"""Tests for lumina.core.state_machine."""

import pytest
from lumina.core.state_machine import LuminaState, StateMachine, StateError


class TestStateMachine:
    def test_initial_state(self):
        sm = StateMachine()
        assert sm.state == LuminaState.IDLE

    def test_custom_initial_state(self):
        sm = StateMachine(initial=LuminaState.LISTENING)
        assert sm.state == LuminaState.LISTENING

    def test_valid_transition(self):
        sm = StateMachine()
        sm.transition(LuminaState.INITIALIZING)
        assert sm.state == LuminaState.INITIALIZING

    def test_invalid_transition_raises(self):
        sm = StateMachine()
        with pytest.raises(StateError):
            sm.transition(LuminaState.RESPONDING)  # IDLE → RESPONDING not valid

    def test_force_transition_bypasses_validation(self):
        sm = StateMachine()
        sm.transition(LuminaState.ERROR_RECOVERY, force=True)
        assert sm.state == LuminaState.ERROR_RECOVERY

    def test_full_turn_lifecycle(self):
        """Test a complete turn transition sequence."""
        sm = StateMachine(initial=LuminaState.LISTENING)
        sm.transition(LuminaState.THINKING)
        sm.transition(LuminaState.PLANNING)
        sm.transition(LuminaState.ACTING)
        sm.transition(LuminaState.RESPONDING)
        sm.transition(LuminaState.SAVING_MEMORY)
        sm.transition(LuminaState.LISTENING)
        assert sm.state == LuminaState.LISTENING

    def test_shutdown_is_terminal(self):
        sm = StateMachine(initial=LuminaState.LISTENING)
        sm.transition(LuminaState.SHUTDOWN)
        with pytest.raises(StateError):
            sm.transition(LuminaState.LISTENING)

    def test_listener_called_on_transition(self):
        transitions = []
        sm = StateMachine()
        sm.add_listener(lambda old, new: transitions.append((old, new)))
        sm.transition(LuminaState.INITIALIZING)
        assert len(transitions) == 1
        assert transitions[0] == (LuminaState.IDLE, LuminaState.INITIALIZING)

    def test_listener_exception_does_not_crash(self):
        sm = StateMachine()
        sm.add_listener(lambda old, new: (_ for _ in ()).throw(RuntimeError("boom")))
        sm.transition(LuminaState.INITIALIZING)  # should not raise
        assert sm.state == LuminaState.INITIALIZING

    def test_history_records_transitions(self):
        sm = StateMachine()
        sm.transition(LuminaState.INITIALIZING)
        sm.transition(LuminaState.LISTENING)
        history = sm.history()
        assert len(history) == 2
        assert history[-1]["to"] == "LISTENING"

    def test_is_in(self):
        sm = StateMachine()
        assert sm.is_in(LuminaState.IDLE)
        assert sm.is_in(LuminaState.IDLE, LuminaState.LISTENING)
        assert not sm.is_in(LuminaState.LISTENING)

    def test_reset(self):
        sm = StateMachine()
        sm.transition(LuminaState.INITIALIZING)
        sm.reset(LuminaState.IDLE)
        assert sm.state == LuminaState.IDLE

    def test_remove_listener(self):
        calls = []
        sm = StateMachine()
        fn = lambda old, new: calls.append(1)
        sm.add_listener(fn)
        sm.remove_listener(fn)
        sm.transition(LuminaState.INITIALIZING)
        assert len(calls) == 0

    def test_repr(self):
        sm = StateMachine()
        assert "IDLE" in repr(sm)
