"""
lumina/config/loader.py — Configuration loader for Lumina.

Priority (highest wins):
  1. Environment variables  (LUMINA_*)
  2. User config file       (~/.lumina_ai/config.yaml)
  3. Defaults               (src/lumina/config/defaults.yaml)
"""

from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_yaml_simple(path: str) -> Dict[str, Any]:
    """
    Minimal YAML-ish loader (no external dependency).

    Handles: string scalars, null, bool, int, float, nested dicts (indented
    keys), and inline block scalars (|).  Sufficient for the defaults file.
    Falls back to an empty dict if the file doesn't exist.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return _parse_yaml_lines(fh.readlines())
    except FileNotFoundError:
        return {}


def _parse_yaml_lines(lines: List[str]) -> Dict[str, Any]:
    """Very small YAML subset parser — enough for Lumina's config format."""
    result: Dict[str, Any] = {}
    stack: List[tuple] = []  # (indent, dict_ref)
    block_key: Optional[str] = None
    block_lines: List[str] = []
    block_indent: int = 0

    for raw in lines:
        line = raw.rstrip("\n")

        # Block scalar continuation
        if block_key is not None:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if indent > block_indent or stripped == "":
                block_lines.append(line[block_indent + 2:] if len(line) > block_indent + 2 else "")
                continue
            else:
                # End of block — commit
                _current(stack, result)[block_key] = "\n".join(block_lines).strip()
                block_key = None
                block_lines = []

        # Skip comments and empty lines
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(stripped)

        # Pop stack: remove entries whose indent level is >= current indent.
        # We keep entries whose indent is strictly less than the current line's
        # indent — those are the ancestor containers.
        while stack and stack[-1][0] >= indent:
            stack.pop()

        # key: value  or  key:
        if ":" in stripped:
            idx = stripped.index(":")
            key = stripped[:idx].strip()
            val_raw = stripped[idx + 1:].strip()

            # Parent container is whatever is at the top of the stack now
            # (after popping over-indented entries).
            current = _current(stack, result)

            if val_raw == "|":
                # Block scalar starts
                block_key = key
                block_indent = indent
                block_lines = []
                current[key] = ""
                continue
            elif val_raw in ("", "~", "null"):
                # This key introduces a nested mapping.
                # Record it as an empty dict for now; child keys will fill it.
                sub: Dict[str, Any] = {}
                current[key] = sub
                # Push a stack entry at this key's indent so that child lines
                # (at indent + N) find `sub` as their parent container.
                stack.append((indent, sub))
            else:
                current[key] = _coerce(val_raw)

    # Flush any trailing block scalar
    if block_key is not None:
        _current(stack, result)[block_key] = "\n".join(block_lines).strip()

    return result


def _current(stack: List[tuple], root: Dict) -> Dict:
    return stack[-1][1] if stack else root


def _coerce(val: str) -> Any:
    if val.lower() in ("true", "yes"):
        return True
    if val.lower() in ("false", "no"):
        return False
    if val.lower() in ("null", "~", "none"):
        return None
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    # Strip surrounding quotes
    if (val.startswith('"') and val.endswith('"')) or \
       (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    return val


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """Recursively merge override into base (override wins)."""
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        elif v is not None:
            result[k] = v
    return result


def _expand(path: Optional[str]) -> Optional[str]:
    if path is None:
        return None
    return str(pathlib.Path(path).expanduser())


# ---------------------------------------------------------------------------
# Config dataclass
# ---------------------------------------------------------------------------

@dataclass
class BackendConfig:
    type: str = "auto"
    model_path: Optional[str] = None
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    model_name: Optional[str] = None


@dataclass
class MemoryConfig:
    db_path: str = "~/.lumina_ai/lumina.db"
    state_path: str = "~/.lumina_ai/lumina.json"
    max_bytes: int = 8 * 1024 * 1024 * 1024
    episodic_ring_size: int = 200
    working_memory_chunks: int = 4
    working_memory_ttl: int = 30


@dataclass
class ReasoningConfig:
    fractal_shells: int = 7
    bh_max_depth: int = 7
    bh_max_iterations: int = 50
    bh_token_budget: int = 2000
    consolidation_interval: int = 7
    planner_max_steps: int = 5


@dataclass
class ToolsConfig:
    enabled: bool = True
    allow_shell: bool = True
    allow_file_write: bool = False
    allow_web_fetch: bool = True
    dry_run: bool = False
    audit_log: bool = True
    file_scope: str = "~"


@dataclass
class LoggingConfig:
    level: str = "INFO"
    log_file: str = "~/.lumina_ai/lumina.log"
    console: bool = True


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    cors_origins: List[str] = field(default_factory=list)


@dataclass
class SessionConfig:
    auto_name: bool = True
    save_on_exit: bool = True
    heartbeat_interval: int = 300


@dataclass
class SafetyConfig:
    guardrails: bool = True
    self_modification: bool = False
    confirm_actions: bool = False


@dataclass
class LuminaConfig:
    """Top-level Lumina configuration object."""

    version: str = "4.0.0"
    persona: str = "Lumina"
    system_prompt: str = "You are Lumina."

    backend: BackendConfig = field(default_factory=BackendConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    reasoning: ReasoningConfig = field(default_factory=ReasoningConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)

    def resolved_db_path(self) -> str:
        return _expand(self.memory.db_path) or "~/.lumina_ai/lumina.db"

    def resolved_state_path(self) -> str:
        return _expand(self.memory.state_path) or "~/.lumina_ai/lumina.json"

    def resolved_log_file(self) -> str:
        return _expand(self.logging.log_file) or "~/.lumina_ai/lumina.log"

    def resolved_file_scope(self) -> str:
        return _expand(self.tools.file_scope) or str(pathlib.Path.home())


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_DEFAULTS_PATH = str(pathlib.Path(__file__).parent / "defaults.yaml")
_USER_CONFIG_PATH = str(pathlib.Path("~/.lumina_ai/config.yaml").expanduser())


def _apply_env_overrides(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Apply LUMINA_* environment variable overrides."""
    env_map = {
        "LUMINA_BACKEND_TYPE": ("backend", "type"),
        "LUMINA_MODEL_PATH":   ("backend", "model_path"),
        "LUMINA_API_KEY":      ("backend", "api_key"),
        "LUMINA_ENDPOINT":     ("backend", "endpoint"),
        "LUMINA_MODEL_NAME":   ("backend", "model_name"),
        "LUMINA_DB_PATH":      ("memory", "db_path"),
        "LUMINA_STATE_PATH":   ("memory", "state_path"),
        "LUMINA_LOG_LEVEL":    ("logging", "level"),
        "LUMINA_HOST":         ("server", "host"),
        "LUMINA_PORT":         ("server", "port"),
        "LUMINA_PERSONA":      ("lumina", "persona"),
        "LUMINA_ALLOW_SHELL":  ("tools", "allow_shell"),
        "LUMINA_ALLOW_FILE_WRITE": ("tools", "allow_file_write"),
        "LUMINA_DRY_RUN":      ("tools", "dry_run"),
    }
    result = dict(raw)
    for env_key, (section, field_name) in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            if section not in result:
                result[section] = {}
            result[section][field_name] = _coerce(val)
    return result


def _dict_to_config(raw: Dict[str, Any]) -> LuminaConfig:
    """Convert a raw merged dict into a LuminaConfig dataclass."""
    lumina_sect = raw.get("lumina", {})
    backend_sect = raw.get("backend", {})
    memory_sect = raw.get("memory", {})
    reasoning_sect = raw.get("reasoning", {})
    tools_sect = raw.get("tools", {})
    logging_sect = raw.get("logging", {})
    server_sect = raw.get("server", {})
    session_sect = raw.get("session", {})
    safety_sect = raw.get("safety", {})

    def _s(d: Dict, k: str, default: Any) -> Any:
        v = d.get(k, default)
        return default if v is None else v

    cfg = LuminaConfig(
        version=_s(lumina_sect, "version", "4.0.0"),
        persona=_s(lumina_sect, "persona", "Lumina"),
        system_prompt=_s(lumina_sect, "system_prompt", "You are Lumina."),
        backend=BackendConfig(
            type=_s(backend_sect, "type", "auto"),
            model_path=backend_sect.get("model_path"),
            api_key=backend_sect.get("api_key"),
            endpoint=backend_sect.get("endpoint"),
            model_name=backend_sect.get("model_name"),
        ),
        memory=MemoryConfig(
            db_path=_s(memory_sect, "db_path", "~/.lumina_ai/lumina.db"),
            state_path=_s(memory_sect, "state_path", "~/.lumina_ai/lumina.json"),
            max_bytes=_s(memory_sect, "max_bytes", 8 * 1024 * 1024 * 1024),
            episodic_ring_size=_s(memory_sect, "episodic_ring_size", 200),
            working_memory_chunks=_s(memory_sect, "working_memory_chunks", 4),
            working_memory_ttl=_s(memory_sect, "working_memory_ttl", 30),
        ),
        reasoning=ReasoningConfig(
            fractal_shells=_s(reasoning_sect, "fractal_shells", 7),
            bh_max_depth=_s(reasoning_sect, "bh_max_depth", 7),
            bh_max_iterations=_s(reasoning_sect, "bh_max_iterations", 50),
            bh_token_budget=_s(reasoning_sect, "bh_token_budget", 2000),
            consolidation_interval=_s(reasoning_sect, "consolidation_interval", 7),
            planner_max_steps=_s(reasoning_sect, "planner_max_steps", 5),
        ),
        tools=ToolsConfig(
            enabled=_s(tools_sect, "enabled", True),
            allow_shell=_s(tools_sect, "allow_shell", True),
            allow_file_write=_s(tools_sect, "allow_file_write", False),
            allow_web_fetch=_s(tools_sect, "allow_web_fetch", True),
            dry_run=_s(tools_sect, "dry_run", False),
            audit_log=_s(tools_sect, "audit_log", True),
            file_scope=_s(tools_sect, "file_scope", "~"),
        ),
        logging=LoggingConfig(
            level=_s(logging_sect, "level", "INFO"),
            log_file=_s(logging_sect, "log_file", "~/.lumina_ai/lumina.log"),
            console=_s(logging_sect, "console", True),
        ),
        server=ServerConfig(
            host=_s(server_sect, "host", "127.0.0.1"),
            port=_s(server_sect, "port", 8765),
            cors_origins=_s(server_sect, "cors_origins", []),
        ),
        session=SessionConfig(
            auto_name=_s(session_sect, "auto_name", True),
            save_on_exit=_s(session_sect, "save_on_exit", True),
            heartbeat_interval=_s(session_sect, "heartbeat_interval", 300),
        ),
        safety=SafetyConfig(
            guardrails=_s(safety_sect, "guardrails", True),
            self_modification=_s(safety_sect, "self_modification", False),
            confirm_actions=_s(safety_sect, "confirm_actions", False),
        ),
    )
    return cfg


def load_config(
    user_config_path: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> LuminaConfig:
    """
    Load Lumina configuration from defaults + user file + env vars + overrides.

    Args:
        user_config_path: Path to user's config.yaml (defaults to ~/.lumina_ai/config.yaml).
        overrides: Dict of inline overrides (same structure as yaml; highest priority).

    Returns:
        LuminaConfig with all values resolved.
    """
    defaults = _load_yaml_simple(_DEFAULTS_PATH)
    user_path = user_config_path or _USER_CONFIG_PATH
    user = _load_yaml_simple(user_path)
    merged = _deep_merge(defaults, user)
    merged = _apply_env_overrides(merged)
    if overrides:
        merged = _deep_merge(merged, overrides)
    return _dict_to_config(merged)
