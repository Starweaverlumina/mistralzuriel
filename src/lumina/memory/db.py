"""
lumina/memory/db.py — Memory database interface.

Re-exports LuminaDB from mistral_inference.lumina_core and provides
a factory function so the rest of Lumina can obtain a DB handle without
importing from the legacy namespace directly.
"""

from __future__ import annotations

import os
import pathlib
from typing import Optional


# ---------------------------------------------------------------------------
# Re-export the canonical LuminaDB from the legacy core
# ---------------------------------------------------------------------------

try:
    from mistral_inference.lumina_core import LuminaDB  # type: ignore
except ImportError:
    LuminaDB = None  # type: ignore  # handled gracefully by callers


def open_db(path: Optional[str] = None, max_bytes: Optional[int] = None) -> "LuminaDB":
    """
    Open (or create) a LuminaDB at *path*.

    Args:
        path: Filesystem path for the SQLite file.
              Defaults to ~/.lumina_ai/lumina.db.
        max_bytes: Storage budget (default 8 GB).

    Returns:
        An initialized LuminaDB instance.

    Raises:
        RuntimeError: If LuminaDB is not importable.
    """
    if LuminaDB is None:
        raise RuntimeError(
            "LuminaDB is not available — ensure mistral_inference is installed."
        )

    resolved = str(
        pathlib.Path(path or "~/.lumina_ai/lumina.db").expanduser()
    )
    parent = os.path.dirname(resolved)
    os.makedirs(parent, exist_ok=True)

    kwargs: dict = {"path": resolved}
    if max_bytes is not None:
        kwargs["max_bytes"] = max_bytes
    return LuminaDB(**kwargs)


__all__ = ["LuminaDB", "open_db"]
