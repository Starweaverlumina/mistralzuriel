"""
lumina/core/app.py — LuminaApp: top-level application façade.

LuminaApp is the object constructed by the CLI and API server.
It wraps LuminaRuntime and provides a stable public API that the
CLI commands interact with.

This is where all the pieces connect:
  config → runtime → orchestrator → backend / memory / tools

Usage::

    from lumina.core.app import LuminaApp
    from lumina.config import load_config

    cfg = load_config()
    app = LuminaApp(cfg)
    response = app.chat("Hello, Lumina!")
    app.shutdown()
"""

from __future__ import annotations

import logging
import signal
import sys
from typing import Any, Dict, Iterator, Optional

from lumina.config.loader import LuminaConfig, load_config
from lumina.core.runtime import LuminaRuntime
from lumina.core.orchestrator import TurnResult

log = logging.getLogger(__name__)


class LuminaApp:
    """
    Lumina application — the public interface for CLI and API consumers.

    Wraps LuminaRuntime and adds:
    - Signal handling (graceful shutdown on SIGINT/SIGTERM)
    - Logging initialization
    - Convenience helpers
    """

    def __init__(
        self,
        config: Optional[LuminaConfig] = None,
        config_path: Optional[str] = None,
        **config_overrides: Any,
    ) -> None:
        self._config = config or load_config(
            user_config_path=config_path,
            overrides=config_overrides or None,
        )
        self._setup_logging()
        self._runtime = LuminaRuntime(self._config)
        self._register_signals()
        log.info("LuminaApp ready. Backend: %s", self._runtime.backend.name)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def chat(
        self,
        user_input: str,
        topic: Optional[str] = None,
        emotional_weight: float = 0.5,
        tone_state: Optional[Dict[str, Any]] = None,
    ) -> TurnResult:
        """
        Send a message to Lumina and get a full turn result.

        Args:
            user_input: The user's message.
            topic: Optional explicit topic.
            emotional_weight: Emotional salience (0.0–1.0).
            tone_state: Paralinguistic signals.

        Returns:
            TurnResult with response text and lifecycle metadata.
        """
        return self._runtime.chat(
            user_input=user_input,
            topic=topic,
            emotional_weight=emotional_weight,
            tone_state=tone_state,
        )

    def chat_stream(
        self,
        user_input: str,
        topic: Optional[str] = None,
        emotional_weight: float = 0.5,
    ) -> Iterator[str]:
        """Stream a Lumina response chunk by chunk."""
        yield from self._runtime.chat_stream(
            user_input=user_input,
            topic=topic,
            emotional_weight=emotional_weight,
        )

    def healthcheck(self) -> Dict[str, Any]:
        """Return health status of all subsystems."""
        return self._runtime.healthcheck()

    def introspect(self) -> Dict[str, Any]:
        """Return full internal state (debug)."""
        return self._runtime.introspect()

    def shutdown(self) -> None:
        """Gracefully shut down Lumina."""
        self._runtime.shutdown()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def config(self) -> LuminaConfig:
        return self._config

    @property
    def runtime(self) -> LuminaRuntime:
        return self._runtime

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _setup_logging(self) -> None:
        level = getattr(logging, self._config.logging.level.upper(), logging.INFO)
        handlers = []
        if self._config.logging.console:
            handlers.append(logging.StreamHandler(sys.stderr))
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            handlers=handlers or None,
        )

    def _register_signals(self) -> None:
        def _handler(signum, frame):
            print("\n[Lumina] Received shutdown signal. Saving state...")
            self.shutdown()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, _handler)
            signal.signal(signal.SIGTERM, _handler)
        except (OSError, ValueError):
            # Signal registration may fail in non-main threads or certain environments
            pass
