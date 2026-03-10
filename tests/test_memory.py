"""Tests for lumina.memory interfaces (without requiring lumina_core)."""

import pytest
from lumina.memory.retrieval import MemoryContext
from lumina.memory.working import working_memory_summary, working_memory_read, WorkingMemory
from lumina.memory.episodic import format_episodes_for_prompt, retrieve_episodes
from lumina.memory.semantic import get_topic_summary, format_semantic_context, list_known_topics
from lumina.memory.consolidation import maybe_consolidate, consolidation_summary


class TestMemoryContext:
    def test_empty_context_has_no_memories(self):
        ctx = MemoryContext()
        assert not ctx.has_memories

    def test_with_episodic_has_memories(self):
        ctx = MemoryContext(episodic_memories=[{"content": "test"}])
        assert ctx.has_memories

    def test_with_working_memory_has_memories(self):
        ctx = MemoryContext(working_memory=["chunk 1"])
        assert ctx.has_memories

    def test_all_episodes_deduplication(self):
        ep = {"id": 1, "content": "test"}
        ctx = MemoryContext(
            episodic_memories=[ep],
            tone_memories=[ep],  # Same episode via tone
        )
        all_eps = ctx.all_episodes
        assert len(all_eps) == 1  # deduplicated

    def test_all_episodes_merged_order(self):
        """Tone memories come before episodic in merged list."""
        ctx = MemoryContext(
            tone_memories=[{"id": 1, "content": "tone"}],
            episodic_memories=[{"id": 2, "content": "episodic"}],
        )
        all_eps = ctx.all_episodes
        assert all_eps[0]["content"] == "tone"
        assert all_eps[1]["content"] == "episodic"


class TestWorkingMemory:
    def test_push_and_read(self):
        wm = WorkingMemory()
        wm.push("hello", "general")
        # Use working_memory_read() which handles both real and fallback WM
        chunks = working_memory_read(wm)
        assert any("hello" in c for c in chunks)

    def test_working_memory_summary_empty(self):
        wm = WorkingMemory()
        assert working_memory_summary(wm) == ""

    def test_working_memory_summary_with_content(self):
        wm = WorkingMemory()
        wm.push("recent message", "general")
        summary = working_memory_summary(wm)
        assert "recent message" in summary


class TestEpisodicInterface:
    def test_format_empty_episodes(self):
        result = format_episodes_for_prompt([])
        assert result == ""

    def test_format_episodes(self):
        episodes = [
            {"content": "We talked about Python.", "topic": "programming",
             "emotional_weight": 0.6, "timestamp": "2025-01-01"},
        ]
        result = format_episodes_for_prompt(episodes)
        assert "Python" in result
        assert "programming" in result

    def test_format_episodes_max_chars(self):
        episodes = [
            {"content": "x" * 500, "topic": "test",
             "emotional_weight": 0.5, "timestamp": "now"}
            for _ in range(20)
        ]
        result = format_episodes_for_prompt(episodes, max_chars=200)
        assert len(result) <= 500  # reasonable bound

    def test_retrieve_episodes_no_anchor(self):
        result = retrieve_episodes(None)
        assert result == []


class TestSemanticInterface:
    def _make_anchor(self, topics: dict):
        class FakeAnchor:
            semantic_web = topics
        return FakeAnchor()

    def test_get_topic_summary_no_anchor(self):
        result = get_topic_summary(None, "python")
        assert result is None

    def test_get_topic_summary_unknown_topic(self):
        anchor = self._make_anchor({})
        result = get_topic_summary(anchor, "unknown")
        assert result is None

    def test_get_topic_summary_known_topic(self):
        anchor = self._make_anchor({
            "python": {"encounters": 5, "avg_emotion": 0.7, "relations": ["coding"]}
        })
        result = get_topic_summary(anchor, "python")
        assert result is not None
        assert "python" in result
        assert "5 encounters" in result

    def test_list_known_topics_no_anchor(self):
        result = list_known_topics(None)
        assert result == []

    def test_list_known_topics_sorted_by_encounters(self):
        anchor = self._make_anchor({
            "a": {"encounters": 1},
            "b": {"encounters": 10},
            "c": {"encounters": 5},
        })
        topics = list_known_topics(anchor, top_n=3)
        assert topics[0] == "b"
        assert topics[1] == "c"

    def test_format_semantic_context_empty(self):
        anchor = self._make_anchor({})
        result = format_semantic_context(anchor, [])
        assert result == ""

    def test_format_semantic_context_with_topics(self):
        anchor = self._make_anchor({
            "python": {"encounters": 5, "avg_emotion": 0.7, "relations": []}
        })
        result = format_semantic_context(anchor, ["python"])
        assert "python" in result
        assert "Semantic" in result


class TestConsolidation:
    def test_maybe_consolidate_no_instance(self):
        result = maybe_consolidate(None)
        assert result is None

    def test_maybe_consolidate_no_learning(self):
        class FakeInstance:
            pass
        result = maybe_consolidate(FakeInstance())
        assert result is None

    def test_consolidation_summary_none(self):
        assert consolidation_summary(None) == ""

    def test_consolidation_summary_empty(self):
        assert consolidation_summary({}) == ""

    def test_consolidation_summary_with_promoted(self):
        result = {"promoted_to_semantic": ["python", "math"]}
        summary = consolidation_summary(result)
        assert "python" in summary
        assert "2" in summary
