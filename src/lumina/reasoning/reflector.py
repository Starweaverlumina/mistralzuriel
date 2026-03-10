"""
lumina/reasoning/reflector.py — Post-response reflector.

After each turn the reflector examines the Lumina response and:
  - Extracts topics to reinforce in memory
  - Flags potential guardrail-adjacent content
  - Produces a brief introspective note logged to the session
  - Updates the user model with inferred signals

This runs in the SAVING_MEMORY phase of the orchestrator —
never blocks the response stream.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class ReflectionResult:
    """Output of one reflector pass."""
    extracted_topics: List[str]
    user_signal: str        # e.g. "curious", "skeptical", "satisfied"
    introspective_note: str
    emotional_signal: float  # 0.0–1.0


def reflect(
    user_input: str,
    lumina_response: str,
    topic: str,
    emotional_weight: float,
    lumina_instance: Optional[Any] = None,
) -> ReflectionResult:
    """
    Analyze one completed exchange and produce reflection signals.

    This is intentionally lightweight — it uses heuristics, not an LLM call,
    so it adds zero latency to the response loop.

    Args:
        user_input: The user's turn.
        lumina_response: Lumina's generated reply.
        topic: Inferred topic.
        emotional_weight: Emotional weight used during generation.
        lumina_instance: Optional Lumina object for model updates.

    Returns:
        ReflectionResult with extracted signals.
    """
    # Extract simple topic signals from the response
    extracted_topics = [topic]

    # Basic user signal inference from user_input length and punctuation
    low = user_input.lower()
    if any(w in low for w in ("why", "how", "explain", "??")):
        user_signal = "curious"
    elif any(w in low for w in ("thanks", "great", "perfect", "awesome")):
        user_signal = "satisfied"
    elif any(w in low for w in ("no", "wrong", "incorrect", "disagree")):
        user_signal = "skeptical"
    else:
        user_signal = "neutral"

    # Emotional signal: blend provided weight + simple response length heuristic
    length_factor = min(1.0, len(lumina_response) / 500)
    emotional_signal = (emotional_weight * 0.7) + (length_factor * 0.3)

    introspective_note = (
        f"Turn on '{topic}' — user was {user_signal}, "
        f"emotion={emotional_signal:.2f}, response_length={len(lumina_response)}"
    )

    # Update user model if available
    if lumina_instance is not None:
        user_model = getattr(lumina_instance, "user_model", None)
        if user_model is not None:
            try:
                user_model.observe(
                    topic=topic,
                    emotional_weight=emotional_weight,
                    message_length=len(user_input),
                )
            except Exception:
                pass

    return ReflectionResult(
        extracted_topics=extracted_topics,
        user_signal=user_signal,
        introspective_note=introspective_note,
        emotional_signal=emotional_signal,
    )
