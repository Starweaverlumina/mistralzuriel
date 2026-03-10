"""
lumina/tools/executor.py — Policy-aware tool executor.

Every tool call in Lumina passes through this executor.
The executor:
  1. Looks up the tool in the registry
  2. Runs it through the policy gate
  3. Executes (or dry-runs) the implementation
  4. Returns a structured ToolResult

No tool code anywhere else in Lumina calls implementations directly.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from lumina.tools.policies import PolicyConfig, ToolPolicyEnforcer
from lumina.tools.registry import ToolRegistry

log = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result of one policy-gated tool execution."""
    tool_name: str
    success: bool
    output: str
    blocked: bool = False
    block_reason: str = ""
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def __str__(self) -> str:
        if self.blocked:
            return f"[{self.tool_name} BLOCKED] {self.block_reason}"
        if not self.success:
            return f"[{self.tool_name} ERROR] {self.output}"
        return self.output


class ToolExecutor:
    """
    Runs tool calls through the policy gate and produces ToolResult objects.

    Usage::

        executor = ToolExecutor(registry=registry, policy_config=cfg.tools)
        result = executor.run("web_fetch", url="https://example.com")
        print(result)
    """

    def __init__(
        self,
        registry: ToolRegistry,
        policy_config: Optional[PolicyConfig] = None,
        guardrails: Optional[Any] = None,
    ) -> None:
        self._registry = registry
        self._enforcer = ToolPolicyEnforcer(
            config=policy_config or PolicyConfig(),
            guardrails=guardrails,
        )

    @property
    def audit(self):
        return self._enforcer.audit

    def run(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """
        Execute *tool_name* with *kwargs* after policy check.

        Args:
            tool_name: Registered tool name.
            **kwargs: Arguments forwarded to the tool implementation.

        Returns:
            ToolResult — always returns (never raises).
        """
        # 1. Look up tool
        descriptor = self._registry.get(tool_name)
        if descriptor is None:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output=f"Tool '{tool_name}' not found in registry.",
                blocked=False,
            )

        # 2. Policy check
        policy_result = self._enforcer.check(tool_name, kwargs=kwargs)
        if not policy_result:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output="",
                blocked=True,
                block_reason=policy_result.reason,
            )

        # 3. Execute
        t0 = time.time()
        try:
            output = descriptor.fn(**kwargs)
            duration = (time.time() - t0) * 1000
            log.info("Tool executed: %s (%.1f ms)", tool_name, duration)
            return ToolResult(
                tool_name=tool_name,
                success=True,
                output=str(output),
                duration_ms=duration,
            )
        except Exception as exc:
            duration = (time.time() - t0) * 1000
            log.warning("Tool error: %s — %s", tool_name, exc)
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output=f"Tool execution error: {exc}",
                duration_ms=duration,
            )
