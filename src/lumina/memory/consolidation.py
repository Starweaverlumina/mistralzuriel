"""
lumina/memory/consolidation.py — Memory consolidation interface.

Consolidation promotes episodic memories into semantic abstractions
after N experiences (mimicking hippocampus → cortex transfer during sleep).

This module re-exports HumanLearningModel and provides a standalone
consolidation helper for the orchestrator.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


try:
    from mistral_inference.lumina_core import HumanLearningModel  # type: ignore
except ImportError:
    HumanLearningModel = None  # type: ignore


def maybe_consolidate(lumina_instance: Any) -> Optional[Dict]:
    """
    Trigger consolidation on the HumanLearningModel if it is due.

    Called by the orchestrator after the SAVING_MEMORY phase.

    Returns:
        Consolidation result dict, or None if no consolidation was needed.
    """
    learning = getattr(lumina_instance, "learning", None)
    if learning is None:
        return None
    try:
        return learning.consolidate()
    except Exception:
        return None


def consolidation_summary(result: Optional[Dict]) -> str:
    """
    Format a consolidation result dict into a human-readable string.

    Returns empty string if result is None or contains nothing notable.
    """
    if not result:
        return ""
    promoted = result.get("promoted_to_semantic", [])
    if not promoted:
        return ""
    topics = ", ".join(str(p) for p in promoted[:5])
    return f"[Memory] Consolidated {len(promoted)} experience(s) → semantic: {topics}"


__all__ = [
    "HumanLearningModel",
    "maybe_consolidate",
    "consolidation_summary",
]
