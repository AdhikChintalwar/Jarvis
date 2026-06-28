# ARCHITECTURE

Jarvis processes voice commands through a linear pipeline. Each stage has a single responsibility; execution and reasoning are separated so the wake loop stays thin.

## Pipeline

```
Microphone
        │
        ▼
Wake Word
        │
        ▼
Whisper
        │
        ▼
Command Parser
        │
        ▼
Planner
        │
        ▼
Executor
        │
        ▼
MCP
        │
        ▼
Browser / Mac / Vision
        │
        ▼
Observation
        │
        ▼
Reasoner
        │
        ▼
Final Response
```

## Components

| Stage | Module | Role |
|-------|--------|------|
| Wake Word | `jarvis_main.py` | OpenWakeWord detection, cooldown, busy state |
| Whisper | `core/offline_listener.py` | Offline speech-to-text |
| Command Parser | `core/ollama_brain.py` | Natural language → structured intent |
| Planner | `core/planner.py` | Goal → multi-step JSON plan |
| Executor | `core/executor.py` | Plan step dispatch and tool routing |
| MCP | `mcp_layer/` | Modular tool server/client |
| Skills | `skills/` | Browser, macOS, screen, and system actions |
| Agent Loop | `core/agent_loop.py` | Observe tool output between steps |
| Reasoner | `core/reasoner.py` | Next action or final answer |
| Memory | `core/memory_profiles.py`, `core/memory_store.py` | User and session context |

## Design Principles

1. **Local-first** — LLM inference via Ollama; Whisper for STT; macOS `say` for TTS.
2. **Plan then execute** — The planner produces structured steps; the executor runs them without embedding business logic in the wake loop.
3. **Observe and reason** — Tool results feed the reasoner so Jarvis can adapt within a plan before responding.
4. **Tools over branches** — Phase 2 moves from conditional routing toward a unified tool registry.
