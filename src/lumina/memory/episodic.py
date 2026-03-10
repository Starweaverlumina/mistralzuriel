"""
lumina/memory/episodic.py — Episodic memory interface.

Episodic memory stores timestamped events, conversations, and outcomes.
It implements a forgetting curve so old memories fade unless revisited.

This module re-exports the relevant classes from lumina_core and provides
a clean retrieval API for the orchestrator.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


try:
    from mistral_inference.lumina_core import (  # type: ignore
        CenterAnchor,
        ForgettingCurve,
    )
except ImportError:
    CenterAnchor = None   # type: ignore
    ForgettingCurve = None  # type: ignore


def retrieve_episodes(
    anchor: Any,
    n: int = 7,
    topic: Optional[str] = None,
    query_signal: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve the most relevant episodic memories from the CenterAnchor.

    Args:
        anchor: CenterAnchor instance.
        n: Maximum number of episodes to return.
        topic: Optional topic filter for retrieval.
        query_signal: Optional signal vector for similarity-based retrieval.

    Returns:
        List of episode dicts, most relevant first.
    """
    if anchor is None:
        return []
    try:
        return anchor.read_episodic(n=n, topic=topic, query_signal=query_signal)
    except Exception:
        return []


def format_episodes_for_prompt(episodes: List[Dict[str, Any]], max_chars: int = 1500) -> str:
    """
    Format a list of episode dicts into a concise memory block for prompt injection.

    Args:
        episodes: Output of retrieve_episodes().
        max_chars: Truncate output at this many characters.

    Returns:
        Human-readable memory block string.
    """
    if not episodes:
        return ""

    lines = ["[Relevant memories from past interactions]"]
    total = 0
    for ep in episodes:
        content = ep.get("content", "")
        topic   = ep.get("topic", "")
        ew      = ep.get("emotional_weight", 0.5)
        ts      = ep.get("timestamp", "")

        line = f"  • [{topic}] (emotion: {ew:.2f}) {content[:200]}"
        if len(line) + total > max_chars:
            break
        lines.append(line)
        total += len(line)

    return "\n".join(lines)


__all__ = [
    "CenterAnchor",
    "ForgettingCurve",
    "retrieve_episodes",
    "format_episodes_for_prompt",
]
