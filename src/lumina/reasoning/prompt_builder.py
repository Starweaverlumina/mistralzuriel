"""
lumina/reasoning/prompt_builder.py — Deterministic prompt construction.

Assembles the full system prompt and message list that is sent to the
LLM backend on every turn.  This is the single place where all context
layers are merged — no context is injected anywhere else.

Prompt structure (in order):
  1. System identity / persona
  2. Retrieved episodic memories
  3. Semantic knowledge summary
  4. Working memory (current session buffer)
  5. User model summary (who Lumina is talking to)
  6. Active tool/skill context
  7. Reasoning notes (planner output, reflector notes)
  8. The user's current turn

The result is deterministic and inspectable — log the built prompt to
debug context issues without touching inference code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from lumina.llm.backend_base import Message
from lumina.memory.episodic import format_episodes_for_prompt
from lumina.memory.retrieval import MemoryContext
from lumina.memory.semantic import format_semantic_context
from lumina.memory.working import working_memory_summary


# ---------------------------------------------------------------------------
# Prompt context packet
# ---------------------------------------------------------------------------

@dataclass
class PromptContext:
    """
    All inputs needed to build one complete prompt.

    Created by the orchestrator and passed to build_prompt().
    """
    user_input: str
    system_identity: str = "You are Lumina."
    memory_context: Optional[MemoryContext] = None
    anchor: Optional[Any] = None          # CenterAnchor (for semantic context)
    working_memory: Optional[Any] = None  # WorkingMemory instance
    user_model_summary: str = ""
    tool_context: str = ""                # Active tools description
    reasoning_notes: str = ""            # Planner / reflector output
    conversation_history: List[Message] = field(default_factory=list)

    # Lumina internal state signals (informational — do not affect policy)
    lumina_state_name: str = ""
    consciousness_state: str = ""


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_system_prompt(ctx: PromptContext) -> str:
    """
    Assemble the full system prompt from all context layers.

    This function is pure and deterministic — same inputs always produce
    the same output.  Suitable for unit testing without an LLM.

    Args:
        ctx: PromptContext with all layers populated.

    Returns:
        Complete system prompt string.
    """
    sections: List[str] = []

    # 1. Identity
    sections.append(ctx.system_identity.strip())

    # 2. Episodic memories
    if ctx.memory_context and ctx.memory_context.has_memories:
        all_eps = ctx.memory_context.all_episodes
        if all_eps:
            ep_block = format_episodes_for_prompt(all_eps, max_chars=1500)
            if ep_block:
                sections.append(ep_block)

    # 3. Semantic knowledge
    if ctx.anchor and ctx.memory_context:
        topics = (
            ctx.memory_context.semantic_topics[:10]
            if ctx.memory_context.semantic_topics
            else []
        )
        sem_block = format_semantic_context(ctx.anchor, topics, max_chars=800)
        if sem_block:
            sections.append(sem_block)

    # 4. Working memory
    if ctx.working_memory is not None:
        wm_block = working_memory_summary(ctx.working_memory)
        if wm_block:
            sections.append(wm_block)
    elif ctx.memory_context and ctx.memory_context.working_memory:
        chunks = ctx.memory_context.working_memory
        numbered = "\n".join(f"  [{i+1}] {c}" for i, c in enumerate(chunks))
        sections.append(f"[Working memory — current session]\n{numbered}")

    # 5. User model
    if ctx.user_model_summary:
        sections.append(f"[User profile]\n{ctx.user_model_summary}")

    # 6. Tools
    if ctx.tool_context:
        sections.append(f"[Available tools]\n{ctx.tool_context}")

    # 7. Reasoning notes
    if ctx.reasoning_notes:
        sections.append(f"[Internal reasoning]\n{ctx.reasoning_notes}")

    # 8. State signals (lightweight footer)
    state_parts = []
    if ctx.lumina_state_name:
        state_parts.append(f"runtime: {ctx.lumina_state_name}")
    if ctx.consciousness_state:
        state_parts.append(f"consciousness: {ctx.consciousness_state}")
    if state_parts:
        sections.append(f"[State: {', '.join(state_parts)}]")

    return "\n\n".join(s for s in sections if s)


def build_messages(
    ctx: PromptContext,
    system_prompt: Optional[str] = None,
) -> List[Message]:
    """
    Build the complete message list for the LLM backend.

    Args:
        ctx: PromptContext with conversation history and current input.
        system_prompt: Pre-built system prompt (if None, build_system_prompt() is called).

    Returns:
        List of Message objects ready for BaseLLMBackend.generate().
    """
    sp = system_prompt if system_prompt is not None else build_system_prompt(ctx)

    messages: List[Message] = []

    # Include conversation history (already contains prior turns)
    # Skip any system messages in history — we build our own system prompt
    for msg in ctx.conversation_history:
        if msg.role != "system":
            messages.append(msg)

    # Append the current user turn
    messages.append(Message(role="user", content=ctx.user_input))

    return messages


def token_count_estimate(text: str) -> int:
    """Rough token count estimate: 4 chars ≈ 1 token."""
    return max(1, len(text) // 4)


def system_prompt_token_estimate(ctx: PromptContext) -> int:
    """Return approximate token count for the system prompt."""
    return token_count_estimate(build_system_prompt(ctx))
