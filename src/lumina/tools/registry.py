"""
lumina/tools/registry.py — Tool/skill registry.

The registry is the authoritative source of all tools available to Lumina.
Tools are registered with metadata and callable implementations.
The orchestrator queries the registry; the executor runs tools through
the policy gate before calling the implementation.

Re-exports SkillsEngine from lumina_core for access to the 10 built-in
skills + the self-building skill.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


try:
    from mistral_inference.lumina_core import SkillsEngine  # type: ignore
    _SKILLS_ENGINE_AVAILABLE = True
except ImportError:
    SkillsEngine = None  # type: ignore
    _SKILLS_ENGINE_AVAILABLE = False


# ---------------------------------------------------------------------------
# Tool descriptor
# ---------------------------------------------------------------------------

@dataclass
class ToolDescriptor:
    """Metadata for one registered tool."""
    name: str
    description: str
    category: str               # shell | file | web | memory | self_modify | custom
    fn: Callable[..., str]     # implementation: (**kwargs) -> str
    parameters: Dict[str, str] = field(default_factory=dict)  # name → description
    enabled: bool = True


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ToolRegistry:
    """
    Central registry of all Lumina tools/skills.

    Tools are registered explicitly by the application layer.
    The orchestrator uses list_tools() to present context to the planner.
    The executor fetches tools via get() before calling them.

    Usage::

        registry = ToolRegistry()
        registry.register(ToolDescriptor(
            name="echo",
            description="Echo the input back.",
            category="custom",
            fn=lambda text="": text,
        ))
        tool = registry.get("echo")
        result = tool.fn(text="hello")
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDescriptor] = {}

    def register(self, descriptor: ToolDescriptor) -> None:
        """Register a tool. Replaces existing registration for the same name."""
        self._tools[descriptor.name] = descriptor
        log.debug("Registered tool: %s (%s)", descriptor.name, descriptor.category)

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[ToolDescriptor]:
        return self._tools.get(name)

    def list_tools(self, enabled_only: bool = True) -> List[ToolDescriptor]:
        tools = list(self._tools.values())
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        return tools

    def tool_names(self, enabled_only: bool = True) -> List[str]:
        return [t.name for t in self.list_tools(enabled_only)]

    def tool_context_string(self) -> str:
        """Return a compact description of all enabled tools for prompt injection."""
        tools = self.list_tools()
        if not tools:
            return "No tools available."
        lines = [f"  • {t.name}: {t.description}" for t in tools]
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


def build_default_registry(skills_engine: Optional[Any] = None) -> ToolRegistry:
    """
    Build a ToolRegistry pre-populated with Lumina's built-in skills.

    If skills_engine is a SkillsEngine instance from lumina_core, the
    existing 10 built-in skills are wrapped and registered.

    Args:
        skills_engine: Optional SkillsEngine from lumina_core.

    Returns:
        Populated ToolRegistry.
    """
    registry = ToolRegistry()

    if skills_engine is not None and hasattr(skills_engine, "run"):
        # Wrap each built-in skill from SkillsEngine
        report = skills_engine.report() if hasattr(skills_engine, "report") else {}
        all_names = []
        for names in (report.get("by_category") or {}).values():
            all_names.extend(names)

        for skill_name in all_names:
            _name = skill_name  # capture for closure

            def _make_fn(n: str) -> Callable[..., str]:
                def _fn(**kwargs: Any) -> str:
                    try:
                        return skills_engine.run(n, **kwargs)
                    except Exception as exc:
                        return f"[{n} error: {exc}]"
                return _fn

            # Determine category from TOOL_CATEGORIES mapping (reuse from policies)
            from lumina.tools.policies import TOOL_CATEGORIES
            cat = TOOL_CATEGORIES.get(skill_name, "custom")

            registry.register(ToolDescriptor(
                name=skill_name,
                description=f"Built-in Lumina skill: {skill_name}",
                category=cat,
                fn=_make_fn(skill_name),
            ))

    return registry
