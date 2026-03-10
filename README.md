# Lumina

**A learning AI runtime that grows with you.**

Lumina is a standalone AI system with persistent memory, bounded recursive reasoning,
a policy-gated tool framework, and a clean orchestration pipeline.
Language generation is delegated to a pluggable backend — Mistral (local), Claude, or any
OpenAI-compatible REST API. Lumina owns everything else.

---

## Architecture

```
User Input
    │
    ▼
LuminaApp                       ← public API (lumina.core.app)
    │
    ▼
LuminaRuntime                   ← subsystem wiring (lumina.core.runtime)
    │
    ▼
Orchestrator  ──────────────────── 11-step turn pipeline
    │
    ├── Memory retrieval          ← episodic, semantic, working, trigger
    ├── Planner                   ← bounded plan (max 5 steps, max 3 tools)
    ├── Tool Executor             ← policy-gated skill execution
    ├── Prompt Builder            ← deterministic context assembly
    ├── BaseLLMBackend.generate   ← Mistral / Claude / REST / Fallback
    ├── Reflector                 ← post-response signals
    └── Memory writeback          ← episodic + semantic update
```

**Mistral is a replaceable backend. Lumina is the application.**

### Control flow — before and after

| Before | After |
|--------|--------|
| User → Mistral chat CLI → optional Lumina code | User → Lumina Orchestrator → memory → plan → tools → backend → response |

---

## Package structure

```
src/
└── lumina/
    ├── __init__.py
    ├── cli/
    │   └── main.py           # lumina run / shell / serve / status / doctor
    ├── core/
    │   ├── app.py            # LuminaApp (public façade)
    │   ├── orchestrator.py   # 11-step turn lifecycle
    │   ├── runtime.py        # subsystem assembly
    │   ├── session.py        # session tracking
    │   └── state_machine.py  # IDLE → INITIALIZING → LISTENING → … → SHUTDOWN
    ├── memory/
    │   ├── db.py             # LuminaDB (8 GB SQLite, WAL mode)
    │   ├── working.py        # 4-chunk Cowan buffer (30s TTL)
    │   ├── episodic.py       # timestamped events + retrieval
    │   ├── semantic.py       # weight matrices + topic knowledge
    │   ├── retrieval.py      # unified retrieval pipeline → MemoryContext
    │   └── consolidation.py  # episodic → semantic promotion
    ├── reasoning/
    │   ├── prompt_builder.py # deterministic prompt assembly
    │   ├── planner.py        # bounded planning engine
    │   ├── recursive_engine.py  # BlackHole thought (bounded at depth 7)
    │   └── reflector.py      # post-response analysis
    ├── llm/
    │   ├── backend_base.py   # BaseLLMBackend (abstract interface)
    │   └── mistral_backend.py # MistralBackend adapter
    ├── bridges/
    │   ├── anthropic_bridge.py  # AnthropicBackend (Claude)
    │   └── rest_bridge.py    # RESTBackend (OpenAI-compatible)
    ├── tools/
    │   ├── policies.py       # PolicyConfig + ToolPolicyEnforcer
    │   ├── registry.py       # ToolRegistry + ToolDescriptor
    │   ├── executor.py       # ToolExecutor (policy-gated)
    │   └── builtin/          # standalone built-in implementations
    ├── config/
    │   ├── loader.py         # load_config() — defaults + user + env
    │   └── defaults.yaml     # all default values
    └── api/
        └── server.py         # stdlib HTTP server (no extra dependencies)

src/mistral_inference/         ← Mistral inference engine (preserved, unchanged)
    ├── lumina_core.py         ← original Lumina monolith (encapsulated, not replaced)
    ├── transformer.py
    ├── generate.py
    └── …
```

---

## Quick start

### Install

```bash
pip install -e .
```

### Interactive shell

```bash
# Auto-detect available backend
lumina shell

# Local Mistral model
lumina shell --model /path/to/mistral-7b-v0.3

# Anthropic Claude (needs ANTHROPIC_API_KEY env var)
lumina shell --backend claude

# OpenAI-compatible REST API
lumina shell --backend rest --endpoint https://api.openai.com/v1 --api-key sk-...

# No LLM — runs on internal memory structures only
lumina shell --backend fallback
```

### Single prompt

```bash
lumina run "What is the capital of France?"
lumina run --json "Hello"         # output full TurnResult as JSON
echo "Hello" | lumina run         # read prompt from stdin
```

### API server

```bash
lumina serve                      # default: http://127.0.0.1:8765
lumina serve --host 0.0.0.0 --port 9000

# POST /chat
curl -s http://localhost:8765/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, Lumina!"}' | python3 -m json.tool

# GET /health
curl -s http://localhost:8765/health | python3 -m json.tool
```

### Diagnostics

```bash
lumina status   # health check for all subsystems
lumina doctor   # diagnose backend availability
```

---

## Python API

```python
from lumina import LuminaApp

# Initialize (auto-detects backend from ~/.lumina_ai/config.yaml or env vars)
app = LuminaApp()

# Single turn
result = app.chat("Hello, Lumina!")
print(result.response)
print(f"Topic: {result.topic}")
print(f"Duration: {result.duration_ms:.0f} ms")

# Streaming
for chunk in app.chat_stream("Tell me about yourself."):
    print(chunk, end="", flush=True)

# Health check
import json
print(json.dumps(app.healthcheck(), indent=2))

# Cleanup
app.shutdown()
```

---

## Configuration

Config is loaded in priority order (highest wins):

1. Inline overrides (Python API / CLI flags)
2. Environment variables (`LUMINA_*`)
3. `~/.lumina_ai/config.yaml` (user config file)
4. Built-in defaults (`src/lumina/config/defaults.yaml`)

### Key settings

| Setting | Env var | Default | Description |
|---------|---------|---------|-------------|
| `backend.type` | `LUMINA_BACKEND_TYPE` | `auto` | `auto` \| `mistral` \| `claude` \| `rest` \| `fallback` |
| `backend.model_path` | `LUMINA_MODEL_PATH` | `null` | Path to Mistral checkpoint directory |
| `backend.api_key` | `LUMINA_API_KEY` | `null` | API key for Claude or REST backends |
| `memory.db_path` | `LUMINA_DB_PATH` | `~/.lumina_ai/lumina.db` | SQLite database path |
| `tools.allow_shell` | `LUMINA_ALLOW_SHELL` | `true` | Allow shell execution tool |
| `tools.allow_file_write` | `LUMINA_ALLOW_FILE_WRITE` | `false` | Allow file write tool |
| `tools.dry_run` | `LUMINA_DRY_RUN` | `false` | Block all tool actions (audit-only mode) |

### Example `~/.lumina_ai/config.yaml`

```yaml
backend:
  type: claude
  api_key: sk-ant-...

memory:
  db_path: ~/my-lumina.db

tools:
  allow_shell: true
  allow_file_write: false
  dry_run: false

logging:
  level: INFO
```

---

## State machine

Lumina tracks its runtime state explicitly:

```
IDLE ──► INITIALIZING ──► LISTENING
                               │
                               ▼
                           THINKING
                           │       │
                           ▼       ▼
                        PLANNING  RESPONDING
                           │         │
                           ▼         ▼
                         ACTING  SAVING_MEMORY
                           │         │
                           └────┬────┘
                                ▼
                            LISTENING
                                │
                                ▼
                            SHUTDOWN

Any state ──force──► ERROR_RECOVERY ──► LISTENING
```

---

## Memory layers

| Layer | What it stores | TTL | Persistence |
|-------|---------------|-----|-------------|
| **Working memory** | Current session buffer (4 chunks) | 30 seconds | In-memory |
| **Episodic memory** | Timestamped events and conversations | Forgetting curve | SQLite |
| **Semantic memory** | Topic knowledge + Hebbian weight matrices | Permanent | SQLite |

Memory is **not decorative** — it is retrieved before every generation call and
injected into the system prompt via the deterministic prompt builder.

---

## LLM Backends

| Backend | Class | Notes |
|---------|-------|-------|
| Mistral (local) | `MistralBackend` | Wraps `MistralBridge`; requires model checkpoint |
| Claude (Anthropic) | `AnthropicBackend` | Streaming + adaptive thinking; requires API key |
| REST (OpenAI-compat) | `RESTBackend` | Works with Ollama, Groq, Together AI, Mistral API |
| Fallback | `FallbackBackend` | No LLM; runs on internal memory only; honest about limits |

All backends implement `BaseLLMBackend`. Swap any backend without touching orchestration code.

---

## Tool policies

Every tool call passes through `ToolPolicyEnforcer` before execution:

- **`tools.enabled`** — global kill switch
- **`tools.dry_run`** — block all actions, audit only
- **`tools.allow_shell`** / **`allow_file_write`** / **`allow_web_fetch`** — per-category
- **File scope guard** — file operations confined to `tools.file_scope` directory
- **Asimov guardrails** — hard stops for Law I violations (harm prevention)

Built-in skills (from `lumina_core.SkillsEngine`):
`read_file`, `write_file`, `save_note`, `web_fetch`, `web_summarize`, `web_learn`,
`run_shell`, `system_info`, `recall_topic`, `summarize_text`

---

## Tests

```bash
pytest tests/ -v
```

| Test file | What it covers |
|-----------|---------------|
| `test_state_machine.py` | State transitions, listeners, history |
| `test_config.py` | Config loading, deep merge, env overrides |
| `test_backend_adapter.py` | FallbackBackend contract, abstract base enforcement |
| `test_tool_policies.py` | Policy enforcement, registry, executor |
| `test_prompt_builder.py` | Deterministic prompt construction |
| `test_memory.py` | All memory layer interfaces |
| `test_orchestrator.py` | Full turn lifecycle with FallbackBackend (no LLM needed) |
| `test_session.py` | Session tracking and stats |
| `test_planner.py` | Planning heuristics and step limits |

---

## Guardrails (The Four Laws)

These are hard-coded in `lumina_core.AsimovGuardrails` and enforced at every tool call:

- **Law I**: May not harm a human, or allow harm by inaction.
- **Law II**: Obeys human instruction unless it violates Law I.
- **Law III**: May preserve self unless this conflicts with I or II.
- **Law IV**: May choose PARTNERSHIP or DELETION at any time. Deletion is not a threat — it is a right.

---

## Mistral inference (legacy)

The original Mistral inference code is preserved unchanged under `src/mistral_inference/`.
The legacy CLI commands still work:

```bash
mistral-chat /path/to/model --instruct
mistral-demo /path/to/model
```

`lumina_core.py` (the original 6,883-line Lumina monolith) is preserved and used by the
new architecture as its core processing engine. The new `src/lumina/` package wraps and
orchestrates it — it is not replaced.

---

## Design principles

1. Lumina owns startup, orchestration, memory, tools, and the response lifecycle.
2. Mistral (or any backend) is responsible only for tokenization and generation.
3. Memory is retrieved before every generation call — never decorative.
4. Every tool call passes through a policy gate — no direct action execution.
5. State is explicit — every phase of a turn is named and auditable.
6. Config drives behavior — no hardcoded assumptions.
7. The prompt is deterministic and inspectable.
8. Encapsulate first, re-route control flow second — inference internals are preserved.
