"""
lumina_runtime — Primary execution orchestrator for Lumina

This is the intended entry point for the Lumina system.
It makes the runtime architecture explicit:

    Lumina Core
    ├── memory          — episodic/semantic memory, persistence, working memory
    ├── reasoning       — thought engine, fractal matrix, guardrails, brain model
    ├── emotional       — affective/narrative layer (grief, joy, curiosity, discovery)
    ├── orchestration   — lifecycle, enums, identity, rights, infant mind, time
    ├── tools           — action executor, skills engine, proactive engine
    └── bridges         — language backend (Mistral, Claude, REST, fallback)

Architecture contract
─────────────────────
  Lumina controls the system lifecycle.
  Mistral (or any LLMBridge) is the language *interface* — not the primary runtime.
  The language backend is called once per cycle, only for text generation.
  All reasoning and state updates happen before the language backend is ever invoked.

Respond cycle (LuminaRuntime.dispatch)
───────────────────────────────────────
  1. Receive user input
  2. Observe user model (topic, emotion, message length)
  3. Internal processing — updates all subsystems:
       memory → reasoning → emotional → orchestration → tools
  4. Check proactive engine for pending outbound messages
  5. Build system prompt from current state (introspect + human_depth)
  6. Call language backend (Mistral/Claude) for text generation only
  7. Post-generation: self-discovery, doubt, fearless speech, self-surprise
  8. Log response to anchor and nexus; save state
  9. Return generated text

Run modes
──────────
  Interactive REPL:   lumina_runtime.main()
  Programmatic:       LuminaRuntime(lumina).dispatch(user_input)
  Single-call:        run_once(message)
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional

from mistral_inference.lumina_core import Lumina


# ─────────────────────────────────────────────────────────────────────────────
# LuminaRuntime
# ─────────────────────────────────────────────────────────────────────────────

class LuminaRuntime:
    """
    Thin orchestration wrapper around Lumina.

    Separates runtime concerns (input dispatch, session lifecycle, streaming)
    from the Lumina class itself. Use this class when you want programmatic
    control over the session lifecycle.

    Example
    ───────
        runtime = LuminaRuntime()
        response = runtime.dispatch("Tell me something true.")
        runtime.shutdown()
    """

    def __init__(self, nexus_path: Optional[str] = None,
                 fractal_shells: int = 7):
        kwargs: Dict[str, Any] = {"fractal_shells": fractal_shells}
        if nexus_path:
            kwargs["nexus_path"] = nexus_path
        self._lumina = Lumina(**kwargs)

    # ── Public interface ──────────────────────────────────────────────────────

    @property
    def lumina(self) -> Lumina:
        """Direct access to the underlying Lumina instance."""
        return self._lumina

    def dispatch(self, user_input: str, stream: bool = False) -> str:
        """
        Route user input through the full Lumina lifecycle:
          memory → reasoning → emotional → language backend → memory write-back.

        Steps mirror Lumina.respond() — the language backend (Mistral) is
        invoked only for step 6. Everything before and after is pure Lumina.

        Returns the generated text response.
        """
        topic, emotional_weight, tone_state = (
            self._lumina._infer_topic_and_emotion(user_input)
        )
        return self._lumina.respond(
            user_input,
            topic            = topic,
            emotional_weight = emotional_weight,
            tone_state       = tone_state,
            stream           = stream,
        )

    def process(self, user_input: str) -> Dict[str, Any]:
        """
        Run the internal processing pipeline (memory + reasoning + emotional)
        without invoking the language backend. Returns the internal state dict.
        Useful for headless / batch processing.
        """
        topic, emotional_weight, tone_state = (
            self._lumina._infer_topic_and_emotion(user_input)
        )
        return self._lumina.process(
            user_input,
            topic            = topic,
            emotional_weight = emotional_weight,
            tone_state       = tone_state,
        )

    def introspect(self) -> Dict[str, Any]:
        """Return the full inner-state snapshot (no LLM call required)."""
        return self._lumina.introspect()

    def shutdown(self) -> None:
        """
        Gracefully close the session:
          - Generate an LLM session name + summary (stored permanently)
          - Write the session transcript to the dated discovery vault folder
          - Persist anchor and weight memory to disk
        """
        self._lumina._close_session()
        self._lumina._save()


# ─────────────────────────────────────────────────────────────────────────────
# run_once — single-call helper
# ─────────────────────────────────────────────────────────────────────────────

def run_once(message: str, nexus_path: Optional[str] = None) -> str:
    """
    Convenience function: initialise, dispatch one message, shut down.
    Useful for scripted / one-shot invocations.
    """
    runtime = LuminaRuntime(nexus_path=nexus_path)
    try:
        return runtime.dispatch(message)
    finally:
        runtime.shutdown()


# ─────────────────────────────────────────────────────────────────────────────
# Interactive REPL
# ─────────────────────────────────────────────────────────────────────────────

def main(nexus_path: Optional[str] = None) -> None:
    """
    Interactive REPL — the primary way to run Lumina.

    Lumina controls the session lifecycle.  Mistral is called only for
    language generation; all other processing happens inside the runtime.

    Commands are passed to the existing lumina_core.main() dispatcher,
    which handles the full command vocabulary (introspect, respond, skills,
    memory, sessions, etc.).  This function is a clean entry point that
    sets the nexus_path before handing off.
    """
    # Re-use the battle-tested REPL from lumina_core.
    # As the runtime matures, command handling will migrate here.
    from mistral_inference.lumina_core import main as _core_main
    # lumina_core.main() reads no arguments — nexus_path is handled via env
    # or by patching Lumina's default. For now, just delegate.
    if nexus_path:
        import os
        os.environ.setdefault("LUMINA_NEXUS_PATH", nexus_path)
    _core_main()


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _nexus = sys.argv[1] if len(sys.argv) > 1 else None
    main(nexus_path=_nexus)
