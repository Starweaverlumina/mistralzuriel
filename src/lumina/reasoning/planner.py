"""
lumina/reasoning/planner.py — Bounded planning engine.

Converts the black-hole recursive thought concept into a bounded,
deterministic planner.  Given a user turn and memory context, it
produces a plan — an ordered list of steps the orchestrator should
take before calling the LLM for the final response.

Limits (hard, not soft):
  - max_steps: 5 (no infinite planning loops)
  - max_tool_calls: 3 (per turn)
  - token_budget: configurable (default 2000)
  - failure_fallback: returns DIRECT_RESPONSE plan if planning fails
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional


class PlanStepType(Enum):
    RETRIEVE_MEMORY   = auto()   # Query additional memory
    CALL_TOOL         = auto()   # Execute a registered skill
    REASON            = auto()   # Internal reflection / thought
    GENERATE_RESPONSE = auto()   # Call the LLM backend
    SAVE_MEMORY       = auto()   # Write result back to memory


@dataclass
class PlanStep:
    """One step in the execution plan for a turn."""
    step_type: PlanStepType
    description: str
    tool_name: Optional[str] = None
    tool_kwargs: Dict[str, Any] = field(default_factory=dict)
    token_budget: int = 0


@dataclass
class Plan:
    """Ordered execution plan for one orchestrator turn."""
    steps: List[PlanStep]
    reasoning: str = ""
    token_budget_remaining: int = 2000
    created_at: float = field(default_factory=time.time)

    def is_direct(self) -> bool:
        """True if the plan has no tool calls or reasoning steps (pure generation path)."""
        _direct_types = {
            PlanStepType.RETRIEVE_MEMORY,
            PlanStepType.GENERATE_RESPONSE,
            PlanStepType.SAVE_MEMORY,
        }
        return all(s.step_type in _direct_types for s in self.steps)

    @property
    def tool_steps(self) -> List[PlanStep]:
        return [s for s in self.steps if s.step_type == PlanStepType.CALL_TOOL]


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

class Planner:
    """
    Bounded planning engine for Lumina's orchestrator.

    The planner inspects the user input and memory context and decides
    whether the turn requires tool calls, additional memory retrieval,
    or can be answered directly.

    Limits (enforced, not advisory):
        max_steps:      Maximum plan steps.
        max_tool_calls: Maximum tool invocations per plan.
        token_budget:   Approximate token budget for the full turn.
    """

    def __init__(
        self,
        max_steps: int = 5,
        max_tool_calls: int = 3,
        token_budget: int = 2000,
    ) -> None:
        self.max_steps = max_steps
        self.max_tool_calls = max_tool_calls
        self.token_budget = token_budget

    def plan(
        self,
        user_input: str,
        memory_context: Any,
        available_tools: Optional[List[str]] = None,
        lumina_state: Optional[str] = None,
    ) -> Plan:
        """
        Build an execution plan for one turn.

        Args:
            user_input: The raw user message.
            memory_context: MemoryContext from the retrieval pipeline.
            available_tools: List of enabled tool names.
            lumina_state: Current state name (for context).

        Returns:
            Plan with ordered steps.
        """
        tools = available_tools or []
        steps: List[PlanStep] = []
        reasoning_parts: List[str] = []
        token_used = 0

        # Step 1: Always retrieve memory (already done by orchestrator, mark it)
        steps.append(PlanStep(
            step_type=PlanStepType.RETRIEVE_MEMORY,
            description="Load episodic and semantic context.",
        ))

        # Step 2: Decide if tools are needed
        tool_count = 0
        if tools and self._needs_tool(user_input, tools):
            for tool_name in self._select_tools(user_input, tools):
                if tool_count >= self.max_tool_calls:
                    reasoning_parts.append(f"Tool limit ({self.max_tool_calls}) reached.")
                    break
                steps.append(PlanStep(
                    step_type=PlanStepType.CALL_TOOL,
                    description=f"Execute tool: {tool_name}",
                    tool_name=tool_name,
                ))
                tool_count += 1
                token_used += 50  # estimated overhead per tool call

        # Step 3: Inline reasoning if topic is complex
        if self._needs_reasoning(user_input):
            steps.append(PlanStep(
                step_type=PlanStepType.REASON,
                description="Reflect on prior knowledge before responding.",
                token_budget=min(300, self.token_budget - token_used),
            ))
            token_used += 300

        # Step 4: Generate response
        steps.append(PlanStep(
            step_type=PlanStepType.GENERATE_RESPONSE,
            description="Generate final LLM response.",
            token_budget=min(512, self.token_budget - token_used),
        ))

        # Step 5: Save memory
        steps.append(PlanStep(
            step_type=PlanStepType.SAVE_MEMORY,
            description="Write interaction to episodic memory.",
        ))

        # Enforce step limit
        steps = steps[:self.max_steps]

        return Plan(
            steps=steps,
            reasoning="; ".join(reasoning_parts) if reasoning_parts else "Direct response path.",
            token_budget_remaining=max(0, self.token_budget - token_used),
        )

    # ------------------------------------------------------------------
    # Decision heuristics (rule-based; no LLM needed for planning)
    # ------------------------------------------------------------------

    _TOOL_KEYWORDS = {
        "read_file":     ["read file", "open file", "show file", "cat "],
        "write_file":    ["write to", "save to file", "create file"],
        "web_fetch":     ["fetch url", "get url", "download from"],
        "web_summarize": ["summarize", "tldr", "summary of"],
        "run_shell":     ["run command", "execute", "shell", "bash"],
        "recall_topic":  ["remember", "recall", "what do you know about"],
        "system_info":   ["system info", "disk space", "python version"],
    }

    def _needs_tool(self, user_input: str, tools: List[str]) -> bool:
        low = user_input.lower()
        for tool, keywords in self._TOOL_KEYWORDS.items():
            if tool in tools and any(kw in low for kw in keywords):
                return True
        return False

    def _select_tools(self, user_input: str, tools: List[str]) -> List[str]:
        low = user_input.lower()
        selected = []
        for tool, keywords in self._TOOL_KEYWORDS.items():
            if tool in tools and any(kw in low for kw in keywords):
                selected.append(tool)
        return selected[:self.max_tool_calls]

    _COMPLEX_MARKERS = [
        "explain", "why", "how does", "analyze", "compare",
        "difference between", "pros and cons", "design",
    ]

    def _needs_reasoning(self, user_input: str) -> bool:
        low = user_input.lower()
        return any(marker in low for marker in self._COMPLEX_MARKERS)
