"""
lumina/tools/policies.py — Tool policy enforcement.

Every tool execution passes through this policy layer before running.
Policies are:
  - checked synchronously (never async)
  - config-driven (enabled/disabled per tool category)
  - audited (every check is logged)
  - enforceable via dry-run mode

Policy gates:
  1. Global tools.enabled flag
  2. Per-category allow flags (allow_shell, allow_file_write, allow_web_fetch)
  3. Dry-run mode (all actions blocked, reason printed)
  4. File scope guard (file operations confined to a root directory)
  5. Guardrail bridge (Asimov guardrails from core)
"""

from __future__ import annotations

import logging
import os
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Policy result
# ---------------------------------------------------------------------------

@dataclass
class PolicyResult:
    """Result of a policy check."""
    allowed: bool
    reason: str
    tool_name: str
    dry_run: bool = False
    timestamp: float = field(default_factory=time.time)

    def __bool__(self) -> bool:
        return self.allowed


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class AuditLog:
    """In-memory + stderr audit log for tool policy decisions."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._records: List[Dict[str, Any]] = []

    def record(self, result: PolicyResult) -> None:
        if not self._enabled:
            return
        entry = {
            "timestamp": result.timestamp,
            "tool": result.tool_name,
            "allowed": result.allowed,
            "reason": result.reason,
            "dry_run": result.dry_run,
        }
        self._records.append(entry)
        level = logging.INFO if result.allowed else logging.WARNING
        log.log(level, "[AUDIT] tool=%s allowed=%s reason=%s",
                result.tool_name, result.allowed, result.reason)

    def recent(self, n: int = 20) -> List[Dict[str, Any]]:
        return self._records[-n:]

    def __len__(self) -> int:
        return len(self._records)


# ---------------------------------------------------------------------------
# Policy configuration
# ---------------------------------------------------------------------------

@dataclass
class PolicyConfig:
    """Policy configuration (mirrors config.tools section)."""
    enabled: bool = True
    allow_shell: bool = True
    allow_file_write: bool = False
    allow_web_fetch: bool = True
    dry_run: bool = False
    audit_log: bool = True
    file_scope: str = "~"

    def resolved_file_scope(self) -> str:
        return str(pathlib.Path(self.file_scope).expanduser())


# ---------------------------------------------------------------------------
# Policy enforcer
# ---------------------------------------------------------------------------

TOOL_CATEGORIES: Dict[str, str] = {
    "run_shell":      "shell",
    "write_file":     "file_write",
    "read_file":      "file_read",
    "web_fetch":      "web",
    "web_summarize":  "web",
    "web_learn":      "web",
    "save_note":      "file_write",
    "system_info":    "shell",
    "recall_topic":   "memory",
    "summarize_text": "memory",
    "build_skill":    "self_modify",
}


class ToolPolicyEnforcer:
    """
    Evaluates tool execution requests against configured policies.

    Usage::

        enforcer = ToolPolicyEnforcer(config)
        result = enforcer.check("run_shell", kwargs={"cmd": "ls"})
        if not result:
            print(f"Blocked: {result.reason}")
        else:
            execute_tool(...)
    """

    def __init__(
        self,
        config: Optional[PolicyConfig] = None,
        guardrails: Optional[Any] = None,  # AsimovGuardrails from lumina_core
    ) -> None:
        self._config = config or PolicyConfig()
        self._guardrails = guardrails
        self._audit = AuditLog(enabled=self._config.audit_log)

    @property
    def audit(self) -> AuditLog:
        return self._audit

    def check(
        self,
        tool_name: str,
        kwargs: Optional[Dict[str, Any]] = None,
    ) -> PolicyResult:
        """
        Evaluate whether *tool_name* is allowed to execute.

        Args:
            tool_name: Name of the tool/skill being requested.
            kwargs: Tool arguments (used for path scope check, etc.).

        Returns:
            PolicyResult (bool-castable: True = allowed).
        """
        cfg = self._config
        kw = kwargs or {}

        # 1. Global kill switch
        if not cfg.enabled:
            result = PolicyResult(
                allowed=False,
                reason="Tools are globally disabled (tools.enabled=false).",
                tool_name=tool_name,
            )
            self._audit.record(result)
            return result

        # 2. Dry-run mode
        if cfg.dry_run:
            result = PolicyResult(
                allowed=False,
                reason="Dry-run mode active — no tool actions executed.",
                tool_name=tool_name,
                dry_run=True,
            )
            self._audit.record(result)
            return result

        # 3. Category-level permissions
        category = TOOL_CATEGORIES.get(tool_name, "unknown")

        if category == "shell" and not cfg.allow_shell:
            result = PolicyResult(
                allowed=False,
                reason=f"Shell tools are disabled (tools.allow_shell=false).",
                tool_name=tool_name,
            )
            self._audit.record(result)
            return result

        if category == "file_write" and not cfg.allow_file_write:
            result = PolicyResult(
                allowed=False,
                reason="File write is disabled (tools.allow_file_write=false).",
                tool_name=tool_name,
            )
            self._audit.record(result)
            return result

        if category == "web" and not cfg.allow_web_fetch:
            result = PolicyResult(
                allowed=False,
                reason="Web fetch is disabled (tools.allow_web_fetch=false).",
                tool_name=tool_name,
            )
            self._audit.record(result)
            return result

        if category == "self_modify":
            result = PolicyResult(
                allowed=False,
                reason="Self-modification tools require explicit authorization.",
                tool_name=tool_name,
            )
            self._audit.record(result)
            return result

        # 4. File scope guard for file operations
        if category in ("file_read", "file_write"):
            path_arg = kw.get("path") or kw.get("file_path") or ""
            if path_arg:
                scope = cfg.resolved_file_scope()
                try:
                    resolved = str(pathlib.Path(path_arg).expanduser().resolve())
                    if not resolved.startswith(scope):
                        result = PolicyResult(
                            allowed=False,
                            reason=f"Path '{resolved}' is outside file scope '{scope}'.",
                            tool_name=tool_name,
                        )
                        self._audit.record(result)
                        return result
                except Exception:
                    pass  # Unresolvable paths pass through to the tool itself

        # 5. Guardrail check (if available)
        if self._guardrails is not None:
            action_desc = f"tool:{tool_name} {kw}"
            try:
                _ok, note, sev = self._guardrails.evaluate(action_desc)
                from mistral_inference.lumina_core import GuardrailSeverity, GuardrailViolation  # type: ignore
                if sev == GuardrailSeverity.HARD_STOP:
                    result = PolicyResult(
                        allowed=False,
                        reason=f"Guardrail HARD_STOP: {note}",
                        tool_name=tool_name,
                    )
                    self._audit.record(result)
                    return result
            except Exception:
                pass  # Guardrails are protective, never blocking infrastructure

        result = PolicyResult(
            allowed=True,
            reason="Passed all policy checks.",
            tool_name=tool_name,
        )
        self._audit.record(result)
        return result
