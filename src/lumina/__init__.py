"""
Lumina — A Learning AI Runtime.

Lumina is a standalone AI system that grows and learns with the user.
It owns startup, memory, planning, tools, and response orchestration.
Language generation is delegated to a pluggable backend (Mistral, Claude, REST).

Quick start::

    from lumina import LuminaApp

    app = LuminaApp()                      # auto-detects backend
    result = app.chat("Hello, Lumina!")
    print(result.response)
    app.shutdown()

Architecture overview:

    User Input
        │
        ▼
    LuminaApp                      ← public API
        │
        ▼
    LuminaRuntime                  ← subsystem wiring
        │
        ▼
    Orchestrator (11-step pipeline)
        │
        ├── Memory retrieval        ← episodic, semantic, working
        ├── Planner                 ← bounded plan, tool decisions
        ├── Tool executor           ← policy-gated skill execution
        ├── Prompt builder          ← deterministic context assembly
        ├── BaseLLMBackend.generate ← Mistral / Claude / REST / Fallback
        ├── Reflector               ← post-response signals
        └── Memory writeback        ← episodic + semantic update

Mistral is a replaceable backend behind BaseLLMBackend.
Lumina is the application.
"""

__version__ = "4.0.0"

from lumina.core.app import LuminaApp
from lumina.core.runtime import LuminaRuntime
from lumina.core.orchestrator import Orchestrator, TurnResult
from lumina.core.session import Session
from lumina.core.state_machine import LuminaState, StateMachine
from lumina.config.loader import LuminaConfig, load_config
from lumina.llm.backend_base import BaseLLMBackend, FallbackBackend, Message, BackendResponse

__all__ = [
    "__version__",
    "LuminaApp",
    "LuminaRuntime",
    "Orchestrator",
    "TurnResult",
    "Session",
    "LuminaState",
    "StateMachine",
    "LuminaConfig",
    "load_config",
    "BaseLLMBackend",
    "FallbackBackend",
    "Message",
    "BackendResponse",
]
