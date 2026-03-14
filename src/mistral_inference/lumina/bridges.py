"""
lumina.bridges — Language backend layer

Responsible for:
  - LLMBridge — abstract base class for language backends
  - LLMResponse — standard response envelope
  - MistralBridge — primary language backend (local Mistral inference)
  - ClaudeBridge — Claude API backend (via Anthropic SDK)
  - FallbackBridge — no-op / offline fallback
  - GenericRESTBridge — any OpenAI-compatible REST endpoint
  - GutChannel — somatic/gut-feeling signal layer (pre-linguistic input channel)

Architecture note: Mistral is the language *interface*, not the runtime.
Lumina controls the lifecycle; Mistral is called only for language generation
(step 6 of the respond() loop). All reasoning and state updates happen before
the language backend is ever invoked.

Migration status: re-exporting from lumina_core for backward compatibility.
"""

from mistral_inference.lumina_core import (
    LLMResponse,
    LLMBridge,
    ClaudeBridge,
    MistralBridge,
    FallbackBridge,
    GenericRESTBridge,
    GutChannel,
)

__all__ = [
    "LLMResponse",
    "LLMBridge",
    "ClaudeBridge",
    "MistralBridge",
    "FallbackBridge",
    "GenericRESTBridge",
    "GutChannel",
]
