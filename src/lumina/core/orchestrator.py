"""
lumina/core/orchestrator.py — Lumina Turn Orchestrator.

The orchestrator is the control center for every user interaction.
It owns the full turn lifecycle and drives state machine transitions.

Turn lifecycle (11 steps):

  1.  LISTENING   → Accept user input, validate basics
  2.  THINKING    → Push to working memory, infer topic + emotion
  3.  THINKING    → Retrieve all memory layers (episodic, semantic, trigger)
  4.  THINKING    → Run fractal matrix forward pass + black hole accretion
  5.  PLANNING    → Build execution plan (tool calls, reasoning notes)
  6.  ACTING      → Execute tool calls through policy gate
  7.  RESPONDING  → Build prompt (system + memories + notes + user turn)
  8.  RESPONDING  → Call backend.generate() / generate_stream()
  9.  SAVING_MEMORY → Run post-response reflector
  10. SAVING_MEMORY → Write back to episodic memory + consolidate
  11. LISTENING   → Update session, return TurnResult

Mistral (or any backend) is called in step 8 only.
Every other step is pure Lumina orchestration.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

from lumina.core.session import Session, Turn
from lumina.core.state_machine import LuminaState, StateMachine
from lumina.llm.backend_base import BaseLLMBackend, GenerationConfig, Message
from lumina.memory.retrieval import MemoryContext, retrieve_memory_context
from lumina.reasoning.planner import Plan, Planner
from lumina.reasoning.prompt_builder import PromptContext, build_messages, build_system_prompt
from lumina.reasoning.recursive_engine import accrete_thought, hawking_summary
from lumina.reasoning.reflector import reflect
from lumina.tools.executor import ToolExecutor, ToolResult
from lumina.tools.registry import ToolRegistry

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Turn result
# ---------------------------------------------------------------------------

@dataclass
class TurnResult:
    """Structured result of one orchestrated turn."""
    user_input: str
    response: str
    topic: str
    emotional_weight: float
    plan: Optional[Plan] = None
    memory_context: Optional[MemoryContext] = None
    tool_results: List[ToolResult] = field(default_factory=list)
    hawking_notes: str = ""
    lumina_state: str = ""
    session_turn: Optional[Turn] = None
    duration_ms: float = 0.0
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class Orchestrator:
    """
    Lumina's turn lifecycle orchestrator.

    Owns every phase of one user↔Lumina exchange:
      - memory retrieval
      - planning
      - tool execution
      - prompt construction
      - backend generation
      - memory writeback

    The Lumina core object (from lumina_core) is injected as *lumina_core*
    so the orchestrator can drive it without importing it directly.

    Args:
        backend: Language model backend (MistralBackend, AnthropicBackend, etc.).
        state_machine: Runtime state machine.
        session: Current session tracker.
        lumina_core: Core Lumina object (from mistral_inference.lumina_core.Lumina).
        planner: Bounded planning engine.
        tool_registry: Registered tools.
        tool_executor: Policy-gated tool runner.
        system_identity: System prompt identity string.
        gen_config: Default generation configuration.
    """

    def __init__(
        self,
        backend: BaseLLMBackend,
        state_machine: StateMachine,
        session: Session,
        lumina_core: Optional[Any] = None,
        planner: Optional[Planner] = None,
        tool_registry: Optional[ToolRegistry] = None,
        tool_executor: Optional[ToolExecutor] = None,
        system_identity: str = "You are Lumina.",
        gen_config: Optional[GenerationConfig] = None,
    ) -> None:
        self._backend = backend
        self._sm = state_machine
        self._session = session
        self._lumina = lumina_core
        self._planner = planner or Planner()
        self._registry = tool_registry or ToolRegistry()
        self._executor = tool_executor
        self._system_identity = system_identity
        self._gen_config = gen_config or GenerationConfig()
        self._history: List[Message] = []  # Conversation history sent to backend

    # ------------------------------------------------------------------
    # Primary public interface
    # ------------------------------------------------------------------

    def turn(
        self,
        user_input: str,
        topic: Optional[str] = None,
        emotional_weight: float = 0.5,
        tone_state: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> TurnResult:
        """
        Execute one complete turn through the 11-step lifecycle.

        Args:
            user_input: Raw input from the user.
            topic: Optional explicit topic (auto-inferred if None).
            emotional_weight: Emotional salience (0.0–1.0).
            tone_state: Paralinguistic tone signals.
            stream: If True, generation is streamed (response field in TurnResult
                    will be the complete joined text; use turn_stream() for live chunks).

        Returns:
            TurnResult with response and all lifecycle metadata.
        """
        t0 = time.time()
        result = TurnResult(
            user_input=user_input,
            response="",
            topic=topic or "general",
            emotional_weight=emotional_weight,
        )

        try:
            result = self._run_turn(
                user_input, topic, emotional_weight, tone_state, stream=False
            )
        except Exception as exc:
            log.exception("Orchestrator turn failed: %s", exc)
            self._sm.transition(LuminaState.ERROR_RECOVERY, force=True)
            result.error = str(exc)
            result.response = (
                "[Lumina] I encountered an error in my reasoning. "
                f"Error details: {exc}"
            )
            self._sm.transition(LuminaState.LISTENING, force=True)

        result.duration_ms = (time.time() - t0) * 1000
        return result

    def turn_stream(
        self,
        user_input: str,
        topic: Optional[str] = None,
        emotional_weight: float = 0.5,
        tone_state: Optional[Dict[str, Any]] = None,
    ) -> Iterator[str]:
        """
        Execute one turn and yield response tokens as they arrive.

        Runs all pre-generation phases synchronously, then streams generation,
        then runs all post-generation phases after the stream is exhausted.

        Yields:
            Response text chunks from the backend.
        """
        # Phase 1–6: pre-generation (synchronous)
        preresult = self._pre_generation(user_input, topic, emotional_weight, tone_state)
        if preresult.error:
            yield preresult.response
            return

        # Phase 7: Build prompt
        prompt_ctx = self._build_prompt_context(preresult, user_input, tone_state)
        system_prompt = build_system_prompt(prompt_ctx)
        messages = build_messages(prompt_ctx, system_prompt)

        # Phase 8: Stream
        chunks: List[str] = []
        self._sm.transition(LuminaState.RESPONDING)
        try:
            for chunk in self._backend.generate_stream(
                messages, system_prompt=system_prompt, config=self._gen_config
            ):
                chunks.append(chunk)
                yield chunk
        except Exception as exc:
            err = f"[Stream error: {exc}]"
            chunks.append(err)
            yield err

        full_response = "".join(chunks)

        # Phase 9–11: post-generation
        self._post_generation(preresult, user_input, full_response, messages)

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _run_turn(
        self,
        user_input: str,
        topic: Optional[str],
        emotional_weight: float,
        tone_state: Optional[Dict[str, Any]],
        stream: bool,
    ) -> TurnResult:
        # Phase 1–6: pre-generation
        preresult = self._pre_generation(user_input, topic, emotional_weight, tone_state)
        if preresult.error:
            return preresult

        # Phase 7: Build prompt
        prompt_ctx = self._build_prompt_context(preresult, user_input, tone_state)
        system_prompt = build_system_prompt(prompt_ctx)
        messages = build_messages(prompt_ctx, system_prompt)

        # Phase 8: Generate
        self._sm.transition(LuminaState.RESPONDING)
        backend_response = self._backend.generate(
            messages, system_prompt=system_prompt, config=self._gen_config
        )
        full_response = backend_response.content
        preresult.response = full_response

        # Phase 9–11: post-generation
        self._post_generation(preresult, user_input, full_response, messages)

        return preresult

    def _pre_generation(
        self,
        user_input: str,
        topic: Optional[str],
        emotional_weight: float,
        tone_state: Optional[Dict[str, Any]],
    ) -> TurnResult:
        """
        Run phases 1–6 (everything before calling the LLM backend).
        Returns a partial TurnResult.
        """
        result = TurnResult(
            user_input=user_input,
            response="",
            topic=topic or "general",
            emotional_weight=emotional_weight,
        )

        # Phase 1: LISTENING → THINKING
        self._sm.transition(LuminaState.THINKING)

        # Phase 2: Infer topic and emotion if not provided
        if topic is None and self._lumina is not None:
            try:
                inferred_topic, inferred_ew, _tone = self._lumina._infer_topic_and_emotion(user_input)
                result.topic = inferred_topic
                result.emotional_weight = inferred_ew
            except Exception:
                pass

        # Push to working memory
        if self._lumina is not None:
            wm = getattr(self._lumina, "working_mem", None)
            if wm is not None:
                try:
                    wm.push(user_input[:200], result.topic)
                except Exception:
                    pass

        # Phase 3: Retrieve memory
        mem_ctx = retrieve_memory_context(
            self._lumina,
            user_input=user_input,
            topic=result.topic,
            emotional_weight=result.emotional_weight,
            tone_state=tone_state,
        )
        result.memory_context = mem_ctx

        # Phase 4: Lumina core processing (fractal matrix + black hole)
        bh_result: Dict[str, Any] = {}
        if self._lumina is not None:
            try:
                # Drive Lumina's internal processing (all shells touch Anchor)
                self._lumina.process(
                    user_input=user_input,
                    topic=result.topic,
                    emotional_weight=result.emotional_weight,
                    tone_state=tone_state,
                )
                # Extract Hawking radiation for reasoning notes
                engines = getattr(self._lumina, "thought_engines", {})
                anchor = getattr(self._lumina, "anchor", None)
                llm_bridge = getattr(self._lumina, "llm", None)
                bh_result = accrete_thought(
                    engines=engines,
                    topic=result.topic,
                    anchor=anchor,
                    user_input=user_input,
                    emotional_weight=result.emotional_weight,
                    llm_bridge=llm_bridge,
                )
            except Exception as exc:
                log.debug("Lumina core processing error (non-fatal): %s", exc)

        result.hawking_notes = hawking_summary(bh_result)

        # Phase 5: Planning
        self._sm.transition(LuminaState.PLANNING)
        plan = self._planner.plan(
            user_input=user_input,
            memory_context=mem_ctx,
            available_tools=self._registry.tool_names(),
        )
        result.plan = plan

        # Phase 6: Execute tool steps
        tool_results: List[ToolResult] = []
        if self._executor is not None:
            for step in plan.tool_steps:
                self._sm.transition(LuminaState.ACTING)
                tr = self._executor.run(step.tool_name or "", **step.tool_kwargs)
                tool_results.append(tr)
                if plan.tool_steps:
                    self._sm.transition(LuminaState.PLANNING)
        result.tool_results = tool_results

        result.lumina_state = self._sm.state.name
        return result

    def _build_prompt_context(
        self,
        preresult: TurnResult,
        user_input: str,
        tone_state: Optional[Dict[str, Any]],
    ) -> PromptContext:
        """Assemble a PromptContext from the pre-generation result."""
        anchor = getattr(self._lumina, "anchor", None) if self._lumina else None
        working_mem = getattr(self._lumina, "working_mem", None) if self._lumina else None
        consciousness = ""
        if self._lumina is not None:
            cs = getattr(self._lumina, "consciousness", None)
            if cs is not None:
                consciousness = cs.name

        # User model summary
        user_model_summary = ""
        if self._lumina is not None:
            um = getattr(self._lumina, "user_model", None)
            if um is not None:
                try:
                    user_model_summary = um.summary() or ""
                except Exception:
                    pass

        # Tool context
        tool_context = self._registry.tool_context_string()

        # Reasoning notes (hawking + tool results)
        reasoning_parts: List[str] = []
        if preresult.hawking_notes:
            reasoning_parts.append(preresult.hawking_notes)
        for tr in preresult.tool_results:
            if tr.success:
                reasoning_parts.append(f"[Tool: {tr.tool_name}]\n{tr.output[:500]}")
            else:
                reasoning_parts.append(f"[Tool: {tr.tool_name} failed] {tr.block_reason or tr.output}")
        reasoning_notes = "\n\n".join(reasoning_parts)

        return PromptContext(
            user_input=user_input,
            system_identity=self._system_identity,
            memory_context=preresult.memory_context,
            anchor=anchor,
            working_memory=working_mem,
            user_model_summary=user_model_summary,
            tool_context=tool_context,
            reasoning_notes=reasoning_notes,
            conversation_history=list(self._history),
            lumina_state_name=preresult.lumina_state,
            consciousness_state=consciousness,
        )

    def _post_generation(
        self,
        preresult: TurnResult,
        user_input: str,
        full_response: str,
        messages: List[Message],
    ) -> None:
        """Run phases 9–11 (post-generation: reflect, memory writeback, session update)."""
        self._sm.transition(LuminaState.SAVING_MEMORY)

        # Phase 9: Reflect
        reflection = reflect(
            user_input=user_input,
            lumina_response=full_response,
            topic=preresult.topic,
            emotional_weight=preresult.emotional_weight,
            lumina_instance=self._lumina,
        )

        # Phase 10: Memory writeback
        if self._lumina is not None:
            try:
                self._lumina._save()
            except Exception as exc:
                log.debug("Memory save error (non-fatal): %s", exc)

        # Update conversation history for next turn
        self._history.append(Message(role="user", content=user_input))
        self._history.append(Message(role="assistant", content=full_response))

        # Phase 11: Session update
        turn = self._session.record_turn(
            user_input=user_input,
            lumina_response=full_response,
            topic=preresult.topic,
            emotional_weight=preresult.emotional_weight,
            metadata={
                "reflection": reflection.introspective_note,
                "lumina_state": preresult.lumina_state,
            },
        )
        preresult.session_turn = turn
        preresult.response = full_response

        self._sm.transition(LuminaState.LISTENING)

    # ------------------------------------------------------------------
    # History management
    # ------------------------------------------------------------------

    def reset_history(self) -> None:
        """Clear conversation history sent to the backend."""
        self._history.clear()
        if hasattr(self._backend, "reset_history"):
            self._backend.reset_history()
