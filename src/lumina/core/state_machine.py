"""
lumina/core/state_machine.py — Lumina Runtime State Machine.

Tracks the explicit lifecycle state of the Lumina runtime.
Every turn through the orchestrator drives state transitions.
No implicit state — every phase is named and auditable.
"""

from __future__ import annotations

import threading
import time
from enum import Enum, auto
from typing import Callable, Dict, List, Optional


class LuminaState(Enum):
    """
    Explicit runtime states for the Lumina orchestrator.

    Transitions form a directed graph; invalid transitions raise StateError.
    """
    IDLE             = auto()   # No active turn; ready for input
    INITIALIZING     = auto()   # Startup: loading config, db, model
    LISTENING        = auto()   # Waiting for user input
    THINKING         = auto()   # Processing input through neural architecture
    PLANNING         = auto()   # Recursive planner building a response plan
    ACTING           = auto()   # Executing tool calls / skills
    RESPONDING       = auto()   # Generating and streaming the LLM response
    SAVING_MEMORY    = auto()   # Writing back episodic/semantic memory
    ERROR_RECOVERY   = auto()   # Recovering from an unexpected error
    SHUTDOWN         = auto()   # Graceful shutdown in progress


class StateError(Exception):
    """Raised when an illegal state transition is attempted."""


# Valid transitions: state → set of states it can move to
_VALID_TRANSITIONS: Dict[LuminaState, List[LuminaState]] = {
    LuminaState.IDLE:           [LuminaState.INITIALIZING, LuminaState.LISTENING,
                                  LuminaState.SHUTDOWN],
    LuminaState.INITIALIZING:   [LuminaState.LISTENING, LuminaState.ERROR_RECOVERY,
                                  LuminaState.SHUTDOWN],
    LuminaState.LISTENING:      [LuminaState.THINKING, LuminaState.SHUTDOWN,
                                  LuminaState.ERROR_RECOVERY],
    LuminaState.THINKING:       [LuminaState.PLANNING, LuminaState.RESPONDING,
                                  LuminaState.ERROR_RECOVERY, LuminaState.SHUTDOWN],
    LuminaState.PLANNING:       [LuminaState.ACTING, LuminaState.RESPONDING,
                                  LuminaState.ERROR_RECOVERY, LuminaState.SHUTDOWN],
    LuminaState.ACTING:         [LuminaState.PLANNING, LuminaState.RESPONDING,
                                  LuminaState.ERROR_RECOVERY, LuminaState.SHUTDOWN],
    LuminaState.RESPONDING:     [LuminaState.SAVING_MEMORY, LuminaState.LISTENING,
                                  LuminaState.ERROR_RECOVERY, LuminaState.SHUTDOWN],
    LuminaState.SAVING_MEMORY:  [LuminaState.LISTENING, LuminaState.ERROR_RECOVERY,
                                  LuminaState.SHUTDOWN],
    LuminaState.ERROR_RECOVERY: [LuminaState.LISTENING, LuminaState.SHUTDOWN],
    LuminaState.SHUTDOWN:       [],  # Terminal — no exits
}


StateListener = Callable[[LuminaState, LuminaState], None]


class StateMachine:
    """
    Lumina runtime state machine.

    Thread-safe; uses a reentrant lock so the same thread can call
    transition() inside a listener without deadlock.

    Usage::

        sm = StateMachine()
        sm.add_listener(lambda old, new: print(f"{old.name} → {new.name}"))
        sm.transition(LuminaState.INITIALIZING)
        # ... boot ...
        sm.transition(LuminaState.LISTENING)
    """

    def __init__(self, initial: LuminaState = LuminaState.IDLE) -> None:
        self._state = initial
        self._lock  = threading.RLock()
        self._listeners: List[StateListener] = []
        self._history: List[tuple] = []   # (timestamp, old, new)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> LuminaState:
        """Current state (thread-safe read)."""
        with self._lock:
            return self._state

    def transition(self, new_state: LuminaState, *, force: bool = False) -> None:
        """
        Move to *new_state*.

        Args:
            new_state: Target state.
            force: If True, skip validation (emergency use only — e.g., ERROR_RECOVERY
                   from any state including SHUTDOWN).

        Raises:
            StateError: If the transition is invalid and *force* is False.
        """
        with self._lock:
            old = self._state
            if not force:
                allowed = _VALID_TRANSITIONS.get(old, [])
                if new_state not in allowed:
                    raise StateError(
                        f"Invalid state transition: {old.name} → {new_state.name}. "
                        f"Allowed: {[s.name for s in allowed]}"
                    )
            self._state = new_state
            self._history.append((time.time(), old, new_state))
            listeners = list(self._listeners)

        # Fire listeners outside the lock to avoid potential deadlock from
        # listeners that call transition() themselves.
        for fn in listeners:
            try:
                fn(old, new_state)
            except Exception:
                pass  # listeners must never crash the state machine

    def add_listener(self, fn: StateListener) -> None:
        """Register a callback invoked on every state transition."""
        with self._lock:
            self._listeners.append(fn)

    def remove_listener(self, fn: StateListener) -> None:
        with self._lock:
            self._listeners = [l for l in self._listeners if l is not fn]

    def is_in(self, *states: LuminaState) -> bool:
        """Return True if current state is one of *states*."""
        return self.state in states

    def history(self, last_n: int = 20) -> List[Dict]:
        """Return last N transitions as a list of dicts."""
        with self._lock:
            subset = self._history[-last_n:]
        return [
            {"timestamp": ts, "from": old.name, "to": new.name}
            for ts, old, new in subset
        ]

    def reset(self, state: LuminaState = LuminaState.IDLE) -> None:
        """Force-reset to *state* (for testing / recovery)."""
        with self._lock:
            old = self._state
            self._state = state
            self._history.append((time.time(), old, state))

    def __repr__(self) -> str:
        return f"<StateMachine state={self._state.name}>"
