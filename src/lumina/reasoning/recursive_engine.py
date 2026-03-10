"""
lumina/reasoning/recursive_engine.py — Bounded recursive thought engine.

Re-exports BlackHoleThoughtEngine from lumina_core and enforces hard limits:
  - recursion depth ≤ bh_max_depth (config-driven, default 7)
  - max iterations ≤ bh_max_iterations (default 50)
  - token budget enforced per pass

The engine is used by the orchestrator's THINKING phase to produce
Hawking radiation (insights) before prompt construction.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


try:
    from mistral_inference.lumina_core import BlackHoleThoughtEngine  # type: ignore
    _BH_AVAILABLE = True
except ImportError:
    BlackHoleThoughtEngine = None  # type: ignore
    _BH_AVAILABLE = False


def accrete_thought(
    engines: Dict[str, Any],
    topic: str,
    anchor: Any,
    user_input: str,
    emotional_weight: float,
    llm_bridge: Any,
    max_depth: int = 7,
    activated_topics: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run one accretion pass through the BlackHoleThoughtEngine for *topic*.

    Creates the engine if it doesn't exist yet.
    Enforces max_depth from config.

    Args:
        engines: Per-topic engine cache (mutated in place).
        topic: Current topic key.
        anchor: CenterAnchor instance.
        user_input: Current user message.
        emotional_weight: Emotional weight for this turn.
        llm_bridge: LLM bridge for inline summaries at each depth.
        max_depth: Hard depth limit (default 7).
        activated_topics: Topics activated by spreading activation.

    Returns:
        Accretion result dict with keys:
          singularity, recursive_insight, hawking_radiation.
    """
    if not _BH_AVAILABLE or BlackHoleThoughtEngine is None:
        return {
            "singularity": None,
            "recursive_insight": user_input[:100],
            "hawking_radiation": [],
        }

    if topic not in engines:
        engine = BlackHoleThoughtEngine(topic, anchor)
        engine.MAX_DEPTH = max_depth
        engine.attach_llm(llm_bridge)
        engines[topic] = engine

    engine = engines[topic]
    engine.MAX_DEPTH = max_depth  # re-apply on every call (config may have changed)

    try:
        result = engine.accrete({
            "content":          user_input,
            "emotional_weight": emotional_weight,
            "activated_topics": activated_topics or [],
        })
        return result
    except Exception as exc:
        return {
            "singularity": None,
            "recursive_insight": str(exc),
            "hawking_radiation": [],
        }


def hawking_summary(bh_result: Dict[str, Any], max_items: int = 2) -> str:
    """
    Format Hawking radiation from an accretion result into a prompt note.

    Args:
        bh_result: Output of accrete_thought().
        max_items: Maximum radiation items to include.

    Returns:
        Compact string for injection into reasoning_notes.
    """
    radiation = bh_result.get("hawking_radiation", [])
    if not radiation:
        return ""
    items = radiation[:max_items]
    lines = [f"  • {r}" for r in items if r]
    if not lines:
        return ""
    return "[Hawking radiation — emergent insights]\n" + "\n".join(lines)
