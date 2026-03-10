"""
lumina/memory/semantic.py — Semantic memory interface.

Semantic memory stores stable facts, topic knowledge, preferences, and
long-term abstractions.  It is backed by the WeightMemory system (Hebbian
64×64 weight matrices per topic) and the anchor's semantic_web.

This module re-exports relevant classes and provides a clean query API.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


try:
    from mistral_inference.lumina_core import (  # type: ignore
        WeightMatrix,
        WeightMemory,
    )
except ImportError:
    WeightMatrix = None   # type: ignore
    WeightMemory = None   # type: ignore


def get_topic_summary(anchor: Any, topic: str) -> Optional[str]:
    """
    Return a short semantic summary string for *topic* from the anchor's
    semantic_web.

    Returns None if there is no semantic knowledge about this topic yet.
    """
    if anchor is None:
        return None
    semantic_web = getattr(anchor, "semantic_web", {})
    entry = semantic_web.get(topic)
    if entry is None:
        return None

    encounters = entry.get("encounters", 0)
    emotion    = entry.get("avg_emotion", 0.5)
    relations  = entry.get("relations", [])
    rel_str    = ", ".join(relations[:5]) if relations else "none"

    return (
        f"Topic '{topic}': {encounters} encounters, "
        f"avg emotion {emotion:.2f}, "
        f"related topics: {rel_str}"
    )


def list_known_topics(anchor: Any, top_n: int = 20) -> List[str]:
    """Return the top-N most-encountered topics from semantic memory."""
    if anchor is None:
        return []
    semantic_web = getattr(anchor, "semantic_web", {})
    sorted_topics = sorted(
        semantic_web.items(),
        key=lambda kv: kv[1].get("encounters", 0),
        reverse=True,
    )
    return [t for t, _ in sorted_topics[:top_n]]


def format_semantic_context(anchor: Any, topics: List[str], max_chars: int = 800) -> str:
    """
    Format semantic knowledge about *topics* into a prompt-ready block.

    Args:
        anchor: CenterAnchor instance.
        topics: Topics to summarize.
        max_chars: Truncate output at this many characters.

    Returns:
        Human-readable semantic context string.
    """
    if anchor is None or not topics:
        return ""

    lines = ["[Semantic knowledge]"]
    total = 0
    for topic in topics:
        summary = get_topic_summary(anchor, topic)
        if summary:
            line = f"  • {summary}"
            if total + len(line) > max_chars:
                break
            lines.append(line)
            total += len(line)

    if len(lines) == 1:
        return ""
    return "\n".join(lines)


__all__ = [
    "WeightMatrix",
    "WeightMemory",
    "get_topic_summary",
    "list_known_topics",
    "format_semantic_context",
]
