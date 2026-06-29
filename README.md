# Jarvis Voice

A fully local AI personal assistant for macOS. Jarvis listens for a wake word, transcribes speech offline, plans multi-step tasks, executes tools, and reasons over observations to produce a final response — all without sending data to the cloud.

**Current milestone:** v1.0 — Foundation Complete (June 2026)

## Documentation

| Document | Description |
|----------|-------------|
| [ROADMAP.md](./ROADMAP.md) | Phased feature plan (Phase 1–3) |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System pipeline and component flow |
| [CHANGELOG.md](./CHANGELOG.md) | Release history and notable changes |
| [DEVLOG.md](./DEVLOG.md) | Development sessions, decisions, and lessons learned |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start Ollama with your configured models
ollama serve

# Run Jarvis
python jarvis_main.py
```

## Repository Layout

```
Jarvis Voice/
├── README.md
├── ARCHITECTURE.md
├── ROADMAP.md
├── CHANGELOG.md
├── DEVLOG.md
├── config/
├── core/
├── voice/
├── data/
├── mcp_layer/
├── skills/
├── logs/
├── tests/
├── jarvis_main.py
├── requirements.txt
└── .gitignore
```

## Phase Status

- **Phase 1** — Complete (wake word, voice, planner, MCP, browser, projects)
- **Phase 2** — In progress (memory, executor, tool registry, self-healing)
- **Phase 3** — Planned (desktop agent, calendar, email, GitHub, RAG)

See [ROADMAP.md](./ROADMAP.md) for details.
