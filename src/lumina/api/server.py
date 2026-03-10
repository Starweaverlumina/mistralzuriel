"""
lumina/api/server.py — Lumina REST API server.

Lightweight HTTP server (stdlib only — no FastAPI/Flask required).
Exposes Lumina's orchestration pipeline as a JSON API.

Endpoints:
  POST /chat          — Send a message, get a full response
  GET  /health        — Health check
  GET  /introspect    — Full internal state
  GET  /session       — Current session stats
  POST /reset         — Reset conversation history

Request format (POST /chat):
  {"message": "Hello, Lumina!", "topic": null, "emotional_weight": 0.5}

Response format:
  {"response": "...", "topic": "...", "error": null, "duration_ms": 42.0}
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from lumina.core.app import LuminaApp

log = logging.getLogger(__name__)


class _LuminaHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler — one instance per request."""

    app: "LuminaApp"  # Set as class attribute by start_server()

    def log_message(self, fmt: str, *args: Any) -> None:
        log.debug("HTTP " + fmt, *args)

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Any:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        body = self.rfile.read(length)
        return json.loads(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        if path == "/health":
            self._send_json(self.app.healthcheck())
        elif path == "/introspect":
            self._send_json(self.app.introspect())
        elif path == "/session":
            stats = self.app.runtime.session.stats()
            self._send_json({
                "session_id": self.app.runtime.session.session_id,
                "total_turns": stats.total_turns,
                "top_topics": stats.top_topics,
                "avg_emotion": stats.avg_emotion,
                "duration_seconds": stats.duration_seconds,
            })
        else:
            self._send_json({"error": f"Unknown endpoint: {path}"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]

        if path == "/chat":
            try:
                body = self._read_json()
                message = body.get("message", "")
                if not message:
                    self._send_json({"error": "message is required"}, status=400)
                    return
                result = self.app.chat(
                    user_input=message,
                    topic=body.get("topic"),
                    emotional_weight=float(body.get("emotional_weight", 0.5)),
                )
                self._send_json({
                    "response": result.response,
                    "topic": result.topic,
                    "emotional_weight": result.emotional_weight,
                    "lumina_state": result.lumina_state,
                    "error": result.error,
                    "duration_ms": result.duration_ms,
                })
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)

        elif path == "/reset":
            try:
                self.app.runtime._orchestrator.reset_history()
                self._send_json({"status": "history cleared"})
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=500)

        else:
            self._send_json({"error": f"Unknown endpoint: {path}"}, status=404)


def start_server(
    app: "LuminaApp",
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    """
    Start the Lumina HTTP API server (blocking).

    Args:
        app: Initialized LuminaApp instance.
        host: Bind host.
        port: Bind port.
    """
    _LuminaHTTPHandler.app = app  # type: ignore[attr-defined]
    server = HTTPServer((host, port), _LuminaHTTPHandler)
    log.info("Lumina API server listening on %s:%d", host, port)
    print(f"[Lumina] API server: http://{host}:{port}")
    print(f"[Lumina]   POST /chat         — chat endpoint")
    print(f"[Lumina]   GET  /health       — health check")
    print(f"[Lumina]   GET  /introspect   — internal state")
    print(f"[Lumina]   GET  /session      — session stats")
    print(f"[Lumina]   POST /reset        — clear history")
    try:
        server.serve_forever()
    finally:
        server.server_close()
