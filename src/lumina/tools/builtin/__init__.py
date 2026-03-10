"""
lumina/tools/builtin — Standalone built-in tool implementations.

These are minimal implementations that work without lumina_core.
When lumina_core's SkillsEngine is available, the registry
prefers those implementations (richer, with web + LLM support).
These serve as a lightweight fallback.
"""

from __future__ import annotations

import os
import platform
import sys


def read_file(path: str = "") -> str:
    """Read a text file and return its contents."""
    if not path:
        return "Error: path required."
    try:
        with open(os.path.expanduser(path), "r", encoding="utf-8") as fh:
            return fh.read()
    except Exception as exc:
        return f"Error reading '{path}': {exc}"


def system_info() -> str:
    """Return basic system information."""
    return (
        f"OS: {platform.system()} {platform.release()}\n"
        f"Python: {sys.version}\n"
        f"CWD: {os.getcwd()}\n"
        f"Home: {os.path.expanduser('~')}"
    )


__all__ = ["read_file", "system_info"]
