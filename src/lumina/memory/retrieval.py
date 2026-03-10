"""
lumina/memory/retrieval.py — Unified memory retrieval pipeline.

This module assembles memory context for the prompt builder by querying
all memory layers in priority order:

    1. Working memory  (current session buffer — highest priority)
    2. Tone-matched episodic memory (mood-congruent fast recall)
    3. Semantically similar episodic memory (spreading activation)
    4. Trigger-matched episodic memory (phrase → memory cue links)
    5. Semantic knowledge (topic abstractions)

The MemoryContext dataclass is the single structured object handed to
the prompt builder — one clean seam between retrieval and generation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MemoryContext:
    """
    All memory layers assembled for one turn.

    Passed from the retrieval pipeline → prompt builder → LLM backend.
    """
    working_memory: List[str] = field(default_factory=list)
    episodic_memories: List[Dict[str, Any]] = field(default_factory=list)
    tone_memories: List[Dict[str, Any]] = field(default_factory=list)
    trigger_memories: List[Dict[str, Any]] = field(default_factory=list)
    semantic_topics: List[str] = field(default_factory=list)
    topic: str = "general"
    emotional_weight: float = 0.5

    @property
    def has_memories(self) -> bool:
        return bool(
            self.working_memory
            or self.episodic_memories
            or self.tone_memories
            or self.trigger_memories
        )

    @property
    def all_episodes(self) -> List[Dict[str, Any]]:
        """Deduplicated list of all episodic episodes."""
        seen_ids = set()
        result = []
        for ep in (self.tone_memories + self.episodic_memories + self.trigger_memories):
            ep_id = ep.get("id") or id(ep)
            if ep_id not in seen_ids:
                seen_ids.add(ep_id)
                result.append(ep)
        return result


def retrieve_memory_context(
    lumina_instance: Any,
    user_input: str,
    topic: str,
    emotional_weight: float = 0.5,
    tone_state: Optional[Dict[str, Any]] = None,
    n_episodic: int = 7,
    n_tone: int = 3,
) -> MemoryContext:
    """
    Run the full memory retrieval pipeline for one turn.

    Args:
        lumina_instance: The core Lumina object (from lumina_core.Lumina).
        user_input: Raw user text for this turn.
        topic: Inferred or provided topic string.
        emotional_weight: Inferred emotional weight (0.0–1.0).
        tone_state: Optional paralinguistic tone signals.
        n_episodic: Max episodic memories to retrieve.
        n_tone: Max tone-matched memories to retrieve.

    Returns:
        MemoryContext with all layers populated.
    """
    ctx = MemoryContext(topic=topic, emotional_weight=emotional_weight)

    # 1. Working memory
    wm = getattr(lumina_instance, "working_mem", None)
    if wm is not None:
        try:
            ctx.working_memory = wm.read()
        except Exception:
            pass

    anchor = getattr(lumina_instance, "anchor", None)
    if anchor is None:
        return ctx

    # 2. Tone-matched episodic recall (fast O(1) lookup)
    if tone_state:
        tone_label = tone_state.get("label")
        if tone_label and tone_label != "neutral":
            try:
                ctx.tone_memories = anchor.read_episodic_by_tone(tone_label, n=n_tone)
            except Exception:
                pass

    # 3. Semantic similarity episodic recall
    try:
        raw_signal: Optional[Dict[str, float]] = None
        if hasattr(lumina_instance, "_text_to_signal"):
            raw_signal = lumina_instance._text_to_signal(user_input)
        ctx.episodic_memories = anchor.read_episodic(
            n=n_episodic, topic=topic, query_signal=raw_signal
        )
    except Exception:
        pass

    # 4. Trigger-matched episodic recall
    db = getattr(getattr(lumina_instance, "nexus", None), "db", None)
    if db is not None:
        try:
            trigger_matches = db.match_triggers(user_input)
            for _phrase, ep_ids, _tw in trigger_matches:
                for ep_id in ep_ids:
                    triggered = db.recall_episodes_by_id(ep_id)
                    if triggered:
                        ctx.trigger_memories.append(triggered)
        except Exception:
            pass

    # 5. Semantic topics from anchor
    semantic_web = getattr(anchor, "semantic_web", {})
    ctx.semantic_topics = list(semantic_web.keys())[:20]

    return ctx
