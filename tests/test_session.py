"""Tests for lumina.core.session."""

import time
import pytest
from lumina.core.session import Session, Turn


class TestSession:
    def test_create_session(self):
        s = Session()
        assert s.session_id
        assert s.turn_count == 0
        assert s.end_time is None

    def test_custom_session_id(self):
        s = Session(session_id="test-id")
        assert s.session_id == "test-id"

    def test_record_turn(self):
        s = Session()
        turn = s.record_turn("Hello!", "Hi there!", topic="general")
        assert isinstance(turn, Turn)
        assert turn.user_input == "Hello!"
        assert turn.lumina_response == "Hi there!"
        assert turn.index == 0

    def test_turn_count_increments(self):
        s = Session()
        s.record_turn("a", "b")
        s.record_turn("c", "d")
        assert s.turn_count == 2

    def test_top_topics(self):
        s = Session()
        s.record_turn("a", "b", topic="python")
        s.record_turn("c", "d", topic="python")
        s.record_turn("e", "f", topic="math")
        top = s.top_topics(2)
        assert top[0][0] == "python"
        assert top[0][1] == 2

    def test_avg_emotion(self):
        s = Session()
        s.record_turn("a", "b", emotional_weight=0.4)
        s.record_turn("c", "d", emotional_weight=0.6)
        assert s.avg_emotion() == pytest.approx(0.5)

    def test_avg_emotion_empty(self):
        s = Session()
        assert s.avg_emotion() == 0.5

    def test_duration(self):
        s = Session()
        time.sleep(0.01)
        assert s.duration() >= 0.01

    def test_close_sets_end_time(self):
        s = Session()
        s.close()
        assert s.end_time is not None

    def test_recent_turns(self):
        s = Session()
        for i in range(15):
            s.record_turn(f"msg {i}", f"resp {i}")
        recent = s.recent_turns
        assert len(recent) == 10  # last 10

    def test_all_turns(self):
        s = Session()
        for i in range(5):
            s.record_turn(f"msg {i}", f"resp {i}")
        assert len(s.all_turns) == 5

    def test_stats(self):
        s = Session()
        s.record_turn("a", "b", topic="coding", emotional_weight=0.8)
        stats = s.stats()
        assert stats.total_turns == 1
        assert stats.avg_emotion == pytest.approx(0.8)

    def test_repr(self):
        s = Session()
        r = repr(s)
        assert "Session" in r
        assert "turns=0" in r
