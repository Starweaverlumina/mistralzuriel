"""
lumina/memory/working.py — Working Memory interface.

Re-exports WorkingMemory from lumina_core and provides a typed
accessor so the orchestrator can read the current session buffer.

Working memory is the 4-chunk Baddeley/Cowan buffer:
- Capacity: 4 chunks
- TTL: 30 seconds per chunk (rehearsal resets TTL)
- Injected into every LLM system prompt

Note: The real WorkingMemory (from lumina_core) uses active() which
returns List[Dict], not read() which returns List[str].
This module provides working_memory_read() as a compatibility shim.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


try:
    from mistral_inference.lumina_core import WorkingMemory  # type: ignore
except ImportError:
    class WorkingMemory:  # type: ignore
        """Minimal fallback if lumina_core is not importable."""
        def __init__(self, max_chunks: int = 4, ttl: float = 30.0) -> None:
            self._chunks: List[Dict[str, Any]] = []

        def push(self, text: str, topic: str = "general") -> None:
            if len(self._chunks) >= 4:
                self._chunks.pop(0)
            self._chunks.append({"content": text, "topic": topic})

        def active(self) -> List[Dict[str, Any]]:
            return list(self._chunks)

        def summary(self) -> str:
            if not self._chunks:
                return ""
            return "Currently holding in mind: " + "; ".join(
                f"[{c['topic']}] {c['content'][:60]}" for c in self._chunks
            )

        def clear(self) -> None:
            self._chunks.clear()


def working_memory_read(wm: WorkingMemory) -> List[str]:
    """
    Return plain text strings from a WorkingMemory instance.

    Compatible with both the real lumina_core WorkingMemory (which uses active()
    returning List[Dict]) and the fallback class above.
    """
    if hasattr(wm, "active"):
        chunks = wm.active()
        result = []
        for c in chunks:
            if isinstance(c, dict):
                result.append(c.get("content", ""))
            else:
                result.append(str(c))
        return result
    if hasattr(wm, "_chunks"):
        chunks = getattr(wm, "_chunks", [])
        result = []
        for c in chunks:
            if isinstance(c, dict):
                result.append(c.get("content", ""))
            else:
                result.append(str(c))
        return result
    return []


def working_memory_summary(wm: WorkingMemory) -> str:
    """
    Return a compact string representation of the working memory buffer
    suitable for injection into a system prompt.
    """
    # Prefer the built-in summary() method (real lumina_core WorkingMemory)
    if hasattr(wm, "summary"):
        s = wm.summary()
        if s:
            return f"[Working memory — current session context]\n  {s}"

    chunks = working_memory_read(wm)
    if not chunks:
        return ""
    numbered = "\n".join(f"  [{i+1}] {c}" for i, c in enumerate(chunks))
    return f"[Working memory — current session context]\n{numbered}"


__all__ = ["WorkingMemory", "working_memory_read", "working_memory_summary"]
