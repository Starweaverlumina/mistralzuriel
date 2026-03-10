"""
lumina/core/session.py — Session tracking for a single Lumina runtime session.

A Session owns the lifecycle of one conversation (start → end).
It tracks turns, topics, emotions, and produces a named summary on close.
"""

from __future__ import annotations

import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Turn:
    """A single user ↔ Lumina exchange within a session."""
    index: int
    user_input: str
    lumina_response: str
    topic: str
    emotional_weight: float
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionStats:
    total_turns: int
    top_topics: List[tuple]
    avg_emotion: float
    duration_seconds: float
    start_time: float
    end_time: float


class Session:
    """
    Tracks runtime state for one Lumina conversation session.

    Created by LuminaApp on startup; closed on exit (saves summary to DB).
    """

    def __init__(self, session_id: Optional[str] = None) -> None:
        self.session_id: str = session_id or str(uuid.uuid4())
        self.start_time: float = time.time()
        self.end_time: Optional[float] = None

        self._turns: List[Turn] = []
        self._topic_counter: Counter = Counter()
        self._emotions: List[float] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_turn(
        self,
        user_input: str,
        lumina_response: str,
        topic: str = "general",
        emotional_weight: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Turn:
        """Append a completed turn to this session's history."""
        turn = Turn(
            index=len(self._turns),
            user_input=user_input,
            lumina_response=lumina_response,
            topic=topic,
            emotional_weight=emotional_weight,
            metadata=metadata or {},
        )
        self._turns.append(turn)
        self._topic_counter[topic] += 1
        self._emotions.append(emotional_weight)
        return turn

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    @property
    def recent_turns(self) -> List[Turn]:
        """Last 10 turns."""
        return self._turns[-10:]

    @property
    def all_turns(self) -> List[Turn]:
        return list(self._turns)

    def top_topics(self, n: int = 5) -> List[tuple]:
        """Return top-N topics by turn count."""
        return self._topic_counter.most_common(n)

    def avg_emotion(self) -> float:
        if not self._emotions:
            return 0.5
        return sum(self._emotions) / len(self._emotions)

    def duration(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time

    def stats(self) -> SessionStats:
        return SessionStats(
            total_turns=self.turn_count,
            top_topics=self.top_topics(),
            avg_emotion=self.avg_emotion(),
            duration_seconds=self.duration(),
            start_time=self.start_time,
            end_time=self.end_time or time.time(),
        )

    def close(self) -> None:
        """Mark the session as ended."""
        self.end_time = time.time()

    def __repr__(self) -> str:
        return (
            f"<Session id={self.session_id[:8]}... "
            f"turns={self.turn_count} "
            f"duration={self.duration():.0f}s>"
        )
