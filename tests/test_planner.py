"""Tests for lumina.reasoning.planner."""

import pytest
from lumina.reasoning.planner import Plan, PlanStep, PlanStepType, Planner
from lumina.memory.retrieval import MemoryContext


class TestPlanner:
    def setup_method(self):
        self.planner = Planner(max_steps=5, max_tool_calls=3, token_budget=2000)

    def test_basic_plan_has_generate_step(self):
        plan = self.planner.plan("Hello!", MemoryContext())
        types = [s.step_type for s in plan.steps]
        assert PlanStepType.GENERATE_RESPONSE in types

    def test_plan_always_has_save_memory(self):
        plan = self.planner.plan("Hello!", MemoryContext())
        types = [s.step_type for s in plan.steps]
        assert PlanStepType.SAVE_MEMORY in types

    def test_plan_step_limit(self):
        plan = self.planner.plan("Hello!", MemoryContext(), available_tools=[
            "web_fetch", "run_shell", "write_file", "read_file", "recall_topic"
        ])
        assert len(plan.steps) <= self.planner.max_steps

    def test_tool_steps_require_tools(self):
        plan = self.planner.plan("Hello!", MemoryContext(), available_tools=[])
        assert len(plan.tool_steps) == 0

    def test_tool_step_selected_for_fetch_keyword(self):
        plan = self.planner.plan(
            "fetch url https://example.com",
            MemoryContext(),
            available_tools=["web_fetch"],
        )
        tool_names = [s.tool_name for s in plan.tool_steps]
        assert "web_fetch" in tool_names

    def test_tool_step_selected_for_shell_keyword(self):
        plan = self.planner.plan(
            "run command ls",
            MemoryContext(),
            available_tools=["run_shell"],
        )
        tool_names = [s.tool_name for s in plan.tool_steps]
        assert "run_shell" in tool_names

    def test_max_tool_calls_respected(self):
        planner = Planner(max_steps=10, max_tool_calls=2)
        # Trigger multiple tool keywords
        plan = planner.plan(
            "fetch url, run command, summarize this, and recall my notes",
            MemoryContext(),
            available_tools=["web_fetch", "run_shell", "web_summarize", "recall_topic"],
        )
        assert len(plan.tool_steps) <= 2

    def test_reasoning_step_for_complex_query(self):
        plan = self.planner.plan(
            "explain the difference between Python and Rust",
            MemoryContext(),
        )
        types = [s.step_type for s in plan.steps]
        assert PlanStepType.REASON in types

    def test_no_reasoning_for_simple_query(self):
        plan = self.planner.plan("hi", MemoryContext())
        types = [s.step_type for s in plan.steps]
        assert PlanStepType.REASON not in types

    def test_is_direct_plan(self):
        plan = self.planner.plan("hi", MemoryContext(), available_tools=[])
        assert plan.is_direct()

    def test_token_budget_positive(self):
        plan = self.planner.plan("Hello!", MemoryContext())
        assert plan.token_budget_remaining >= 0

    def test_plan_reasoning_string(self):
        plan = self.planner.plan("Hello!", MemoryContext())
        assert isinstance(plan.reasoning, str)
        assert len(plan.reasoning) > 0
