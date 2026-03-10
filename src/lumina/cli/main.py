"""
lumina/cli/main.py — Lumina CLI entrypoint.

Commands:
  lumina shell   — interactive conversation shell (default)
  lumina run     — run a single prompt (non-interactive)
  lumina serve   — start the HTTP API server
  lumina status  — print health status and exit
  lumina doctor  — diagnose backend availability

Usage examples::

    lumina shell
    lumina shell --model /path/to/mistral-7b
    lumina shell --backend claude --api-key sk-...
    lumina shell --config ~/.lumina_ai/config.yaml

    lumina run "What is the capital of France?"
    lumina run --backend fallback "Hello"

    lumina serve --host 0.0.0.0 --port 8765
    lumina status
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lumina",
        description="Lumina — a learning AI that grows with you.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  lumina shell                          # interactive shell (auto-detects backend)
  lumina shell --model /path/to/model  # local Mistral inference
  lumina shell --backend claude        # Anthropic Claude (needs ANTHROPIC_API_KEY)
  lumina run "Hello, Lumina!"          # single prompt, print response, exit
  lumina serve                         # start REST API server
  lumina status                        # print health and exit
""",
    )

    parser.add_argument(
        "--config", metavar="PATH",
        default=None,
        help="Path to config.yaml (default: ~/.lumina_ai/config.yaml)",
    )
    parser.add_argument(
        "--model", metavar="PATH",
        default=None,
        help="Path to Mistral model checkpoint.",
    )
    parser.add_argument(
        "--backend", metavar="TYPE",
        choices=["auto", "mistral", "claude", "rest", "fallback"],
        default=None,
        help="LLM backend type.",
    )
    parser.add_argument(
        "--api-key", metavar="KEY",
        default=None,
        help="API key for Claude or REST backends.",
    )
    parser.add_argument(
        "--endpoint", metavar="URL",
        default=None,
        help="REST endpoint URL (for --backend rest).",
    )
    parser.add_argument(
        "--db", metavar="PATH",
        default=None,
        help="Path to Lumina SQLite database.",
    )
    parser.add_argument(
        "--log-level", metavar="LEVEL",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Logging level.",
    )
    parser.add_argument(
        "--no-stream", action="store_true",
        help="Disable streaming output.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # shell
    shell_p = subparsers.add_parser("shell", help="Interactive conversation shell.")
    shell_p.add_argument("--no-banner", action="store_true", help="Suppress startup banner.")

    # run
    run_p = subparsers.add_parser("run", help="Run a single prompt and exit.")
    run_p.add_argument("prompt", nargs="?", default=None, help="Prompt text.")
    run_p.add_argument("--json", action="store_true", help="Output full TurnResult as JSON.")

    # serve
    serve_p = subparsers.add_parser("serve", help="Start Lumina HTTP API server.")
    serve_p.add_argument("--host", default=None, help="Bind host (default: 127.0.0.1).")
    serve_p.add_argument("--port", type=int, default=None, help="Bind port (default: 8765).")

    # status
    subparsers.add_parser("status", help="Print health status and exit.")

    # doctor
    subparsers.add_parser("doctor", help="Diagnose backend availability.")

    return parser


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def _make_overrides(args: argparse.Namespace) -> dict:
    overrides: dict = {}
    if args.model:
        overrides.setdefault("backend", {})["model_path"] = args.model
        overrides.setdefault("backend", {})["type"] = "mistral"
    if args.backend:
        overrides.setdefault("backend", {})["type"] = args.backend
    if args.api_key:
        overrides.setdefault("backend", {})["api_key"] = args.api_key
    if args.endpoint:
        overrides.setdefault("backend", {})["endpoint"] = args.endpoint
    if args.db:
        overrides.setdefault("memory", {})["db_path"] = args.db
    if args.log_level:
        overrides.setdefault("logging", {})["level"] = args.log_level
    return overrides


def _print_banner(app) -> None:
    cfg = app.config
    runtime = app.runtime
    print(f"\n{'═' * 62}")
    print(f"  LUMINA  v{cfg.version}")
    print(f"  Backend  : {runtime.backend.name}")
    print(f"  State    : {runtime.state.name}")
    print(f"  Session  : {runtime.session.session_id[:8]}...")
    print(f"  Tools    : {len(runtime.registry)} registered")
    print(f"{'═' * 62}")
    print("  Commands:")
    print("    introspect            — full internal state")
    print("    health                — health check")
    print("    history               — session turn history")
    print("    tools                 — list available tools")
    print("    clear                 — clear conversation history")
    print("    quit / exit           — end session")
    print("    (anything else)       — chat with Lumina")
    print(f"{'═' * 62}\n")


def cmd_shell(app, args: argparse.Namespace) -> int:
    """Interactive shell."""
    no_banner = getattr(args, "no_banner", False)
    no_stream = getattr(args, "no_stream", False)

    if not no_banner:
        _print_banner(app)

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Lumina] Ending session. Saving...")
            break

        if not user_input:
            continue

        low = user_input.lower()

        if low in ("quit", "exit"):
            print("[Lumina] Until next time.")
            break

        if low == "introspect":
            print(json.dumps(app.introspect(), indent=2, default=str))
            continue

        if low == "health":
            print(json.dumps(app.healthcheck(), indent=2, default=str))
            continue

        if low == "history":
            for turn in app.runtime.session.all_turns:
                print(f"  [{turn.index}] You: {turn.user_input[:80]}")
                print(f"       Lumina: {turn.lumina_response[:80]}")
            continue

        if low == "tools":
            print(app.runtime.registry.tool_context_string())
            continue

        if low == "clear":
            app.runtime._orchestrator.reset_history()
            print("[Lumina] Conversation history cleared.")
            continue

        # Normal chat
        print("Lumina: ", end="", flush=True)
        if no_stream:
            result = app.chat(user_input)
            print(result.response)
        else:
            try:
                for chunk in app.chat_stream(user_input):
                    print(chunk, end="", flush=True)
                print()
            except Exception as exc:
                print(f"\n[Error: {exc}]")

    return 0


def cmd_run(app, args: argparse.Namespace) -> int:
    """Single prompt, then exit."""
    prompt = getattr(args, "prompt", None)
    as_json = getattr(args, "json", False)

    if not prompt:
        # Read from stdin
        try:
            prompt = sys.stdin.read().strip()
        except Exception:
            print("[lumina] Error: no prompt provided.", file=sys.stderr)
            return 1

    if not prompt:
        print("[lumina] Error: prompt is empty.", file=sys.stderr)
        return 1

    result = app.chat(prompt)

    if as_json:
        import dataclasses
        print(json.dumps(dataclasses.asdict(result) if hasattr(result, "__dataclass_fields__") else {
            "response": result.response,
            "topic": result.topic,
            "error": result.error,
        }, indent=2, default=str))
    else:
        print(result.response)

    return 0 if result.success else 1


def cmd_serve(app, args: argparse.Namespace) -> int:
    """Start HTTP API server."""
    host = getattr(args, "host", None) or app.config.server.host
    port = getattr(args, "port", None) or app.config.server.port

    try:
        from lumina.api.server import start_server
        print(f"[Lumina] Starting API server on {host}:{port}")
        start_server(app, host=host, port=port)
    except ImportError:
        print("[Lumina] API server module not available.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n[Lumina] Server stopped.")
    return 0


def cmd_status(app, args: argparse.Namespace) -> int:
    """Print health status."""
    health = app.healthcheck()
    print(json.dumps(health, indent=2, default=str))
    return 0 if health.get("backend", {}).get("healthy", False) else 1


def cmd_doctor(app, args: argparse.Namespace) -> int:
    """Diagnose backend availability."""
    print("[Lumina Doctor]")
    print()

    # Mistral
    try:
        from lumina.llm.mistral_backend import MistralBackend
        b = MistralBackend()
        h = b.healthcheck()
        status = "✓" if h.healthy else "✗"
        print(f"  {status} Mistral backend: {h.message}")
    except Exception as exc:
        print(f"  ✗ Mistral backend: {exc}")

    # Claude
    try:
        from lumina.bridges.anthropic_bridge import AnthropicBackend
        b = AnthropicBackend()
        h = b.healthcheck()
        status = "✓" if h.healthy else "✗"
        print(f"  {status} Anthropic (Claude) backend: {h.message}")
    except Exception as exc:
        print(f"  ✗ Anthropic backend: {exc}")

    # Fallback
    from lumina.llm.backend_base import FallbackBackend
    h = FallbackBackend().healthcheck()
    print(f"  ✓ Fallback backend: {h.message}")

    # lumina_core
    try:
        from mistral_inference.lumina_core import Lumina  # type: ignore
        print("  ✓ lumina_core (mistral_inference.lumina_core): importable")
    except Exception as exc:
        print(f"  ✗ lumina_core: {exc}")

    print()
    return 0


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------

def main(argv: Optional[list] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Default command is shell
    if args.command is None:
        args.command = "shell"

    # Build config overrides from CLI flags
    overrides = _make_overrides(args)

    # Initialize app
    try:
        from lumina.core.app import LuminaApp
        app = LuminaApp(
            config_path=getattr(args, "config", None),
            **({"overrides": overrides} if overrides else {}),
        )
    except Exception as exc:
        print(f"[lumina] Failed to initialize: {exc}", file=sys.stderr)
        if os.environ.get("LUMINA_DEBUG"):
            raise
        return 1

    try:
        cmd_map = {
            "shell":  cmd_shell,
            "run":    cmd_run,
            "serve":  cmd_serve,
            "status": cmd_status,
            "doctor": cmd_doctor,
        }
        fn = cmd_map.get(args.command)
        if fn is None:
            parser.print_help()
            return 1
        return fn(app, args)
    finally:
        app.shutdown()


if __name__ == "__main__":
    sys.exit(main())
