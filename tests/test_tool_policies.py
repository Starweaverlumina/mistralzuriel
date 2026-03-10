"""Tests for lumina.tools.policies and lumina.tools.executor."""

import pytest
from lumina.tools.policies import (
    AuditLog,
    PolicyConfig,
    PolicyResult,
    ToolPolicyEnforcer,
)
from lumina.tools.registry import ToolDescriptor, ToolRegistry, build_default_registry
from lumina.tools.executor import ToolExecutor, ToolResult


# ---------------------------------------------------------------------------
# PolicyResult
# ---------------------------------------------------------------------------

class TestPolicyResult:
    def test_allowed_is_truthy(self):
        r = PolicyResult(allowed=True, reason="ok", tool_name="test")
        assert bool(r) is True

    def test_denied_is_falsy(self):
        r = PolicyResult(allowed=False, reason="blocked", tool_name="test")
        assert bool(r) is False


# ---------------------------------------------------------------------------
# ToolPolicyEnforcer
# ---------------------------------------------------------------------------

class TestToolPolicyEnforcer:
    def test_globally_disabled(self):
        enforcer = ToolPolicyEnforcer(config=PolicyConfig(enabled=False))
        result = enforcer.check("web_fetch")
        assert not result
        assert "disabled" in result.reason.lower()

    def test_dry_run(self):
        enforcer = ToolPolicyEnforcer(config=PolicyConfig(dry_run=True))
        result = enforcer.check("read_file")
        assert not result
        assert result.dry_run is True

    def test_shell_blocked_when_disallowed(self):
        enforcer = ToolPolicyEnforcer(config=PolicyConfig(allow_shell=False))
        result = enforcer.check("run_shell")
        assert not result
        assert "shell" in result.reason.lower()

    def test_file_write_blocked(self):
        enforcer = ToolPolicyEnforcer(config=PolicyConfig(allow_file_write=False))
        result = enforcer.check("write_file")
        assert not result

    def test_web_blocked(self):
        enforcer = ToolPolicyEnforcer(config=PolicyConfig(allow_web_fetch=False))
        result = enforcer.check("web_fetch")
        assert not result

    def test_self_modify_always_blocked(self):
        enforcer = ToolPolicyEnforcer(config=PolicyConfig())
        result = enforcer.check("build_skill")
        assert not result

    def test_allowed_tool_passes(self):
        enforcer = ToolPolicyEnforcer(config=PolicyConfig(
            allow_shell=True, allow_file_write=True, allow_web_fetch=True,
        ))
        result = enforcer.check("read_file")
        assert bool(result) is True

    def test_file_scope_check(self):
        import os
        enforcer = ToolPolicyEnforcer(config=PolicyConfig(
            allow_file_write=True,
            file_scope="/tmp",
        ))
        # Path inside scope
        result = enforcer.check("write_file", kwargs={"path": "/tmp/test.txt"})
        assert bool(result) is True

        # Path outside scope
        result = enforcer.check("write_file", kwargs={"path": "/etc/passwd"})
        assert not result

    def test_audit_records_decisions(self):
        enforcer = ToolPolicyEnforcer(config=PolicyConfig(enabled=False, audit_log=True))
        enforcer.check("run_shell")
        assert len(enforcer.audit) == 1
        assert enforcer.audit.recent(1)[0]["allowed"] is False


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        registry.register(ToolDescriptor(
            name="echo",
            description="Echo input",
            category="custom",
            fn=lambda text="": text,
        ))
        tool = registry.get("echo")
        assert tool is not None
        assert tool.name == "echo"

    def test_unregister(self):
        registry = ToolRegistry()
        registry.register(ToolDescriptor(
            name="temp", description="x", category="custom", fn=lambda: "",
        ))
        registry.unregister("temp")
        assert registry.get("temp") is None

    def test_list_tools_enabled_only(self):
        registry = ToolRegistry()
        registry.register(ToolDescriptor("a", "desc", "custom", lambda: "", enabled=True))
        registry.register(ToolDescriptor("b", "desc", "custom", lambda: "", enabled=False))
        enabled = registry.list_tools(enabled_only=True)
        names = [t.name for t in enabled]
        assert "a" in names
        assert "b" not in names

    def test_contains(self):
        registry = ToolRegistry()
        registry.register(ToolDescriptor("x", "d", "custom", lambda: ""))
        assert "x" in registry
        assert "y" not in registry

    def test_tool_context_string(self):
        registry = ToolRegistry()
        registry.register(ToolDescriptor("greet", "Greets the user", "custom", lambda: ""))
        ctx = registry.tool_context_string()
        assert "greet" in ctx
        assert "Greets" in ctx

    def test_empty_registry(self):
        registry = ToolRegistry()
        assert len(registry) == 0
        assert "No tools available" in registry.tool_context_string()


# ---------------------------------------------------------------------------
# ToolExecutor
# ---------------------------------------------------------------------------

class TestToolExecutor:
    def _make_executor(self, allow_all=True):
        registry = ToolRegistry()
        registry.register(ToolDescriptor(
            name="echo",
            description="Echo",
            category="memory",  # not blocked by any category
            fn=lambda text="hello": text,
        ))
        cfg = PolicyConfig(
            enabled=True,
            allow_shell=allow_all,
            allow_file_write=allow_all,
            allow_web_fetch=allow_all,
        )
        return ToolExecutor(registry=registry, policy_config=cfg), registry

    def test_successful_execution(self):
        executor, _ = self._make_executor()
        result = executor.run("echo", text="world")
        assert result.success is True
        assert result.output == "world"
        assert result.blocked is False

    def test_unknown_tool(self):
        executor, _ = self._make_executor()
        result = executor.run("nonexistent")
        assert result.success is False
        assert "not found" in result.output.lower()

    def test_blocked_tool_returns_blocked_result(self):
        registry = ToolRegistry()
        registry.register(ToolDescriptor(
            name="run_shell",
            description="Shell",
            category="shell",
            fn=lambda cmd="": "output",
        ))
        cfg = PolicyConfig(allow_shell=False)
        executor = ToolExecutor(registry=registry, policy_config=cfg)
        result = executor.run("run_shell", cmd="ls")
        assert result.blocked is True
        assert result.success is False

    def test_tool_error_returns_failed_result(self):
        registry = ToolRegistry()
        registry.register(ToolDescriptor(
            name="broken",
            description="Always fails",
            category="memory",
            fn=lambda: (_ for _ in ()).throw(RuntimeError("tool broke")),
        ))
        cfg = PolicyConfig()
        executor = ToolExecutor(registry=registry, policy_config=cfg)
        result = executor.run("broken")
        assert result.success is False
        assert "tool broke" in result.output.lower() or "error" in result.output.lower()

    def test_str_representation(self):
        executor, _ = self._make_executor()
        result = executor.run("echo", text="test")
        assert str(result) == "test"

        registry = ToolRegistry()
        registry.register(ToolDescriptor(
            name="run_shell", description="x", category="shell", fn=lambda: ""
        ))
        blocked_executor = ToolExecutor(registry=registry, policy_config=PolicyConfig(allow_shell=False))
        blocked = blocked_executor.run("run_shell")
        assert "BLOCKED" in str(blocked)
