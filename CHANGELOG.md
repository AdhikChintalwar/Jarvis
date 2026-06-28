# CHANGELOG

All notable changes to **Jarvis Voice** will be documented in this file.

---

## v1.0.0 — Foundation Complete

**Date:** June 2026

### Added

#### Voice Interaction

- Wake word detection using OpenWakeWord.
- Offline speech recognition using Whisper.
- Text-to-speech responses using macOS `say`.

#### AI Brain

- Local LLM integration with Ollama.
- Command parser using Qwen.
- Structured JSON action parsing.

#### Planning & Reasoning

- Planner capable of generating multi-step execution plans.
- Agent loop for observing tool output.
- Reasoner for selecting the next action or producing a final answer.

#### MCP Integration

- MCP server/client architecture.
- Modular tool invocation through MCP.

#### Browser Automation

- Google search automation.
- YouTube search automation.
- Retrieval of YouTube titles.
- Retrieval of YouTube video details.
- Automatic recommendation of the most relevant video.

#### Desktop Automation

- Open applications.
- Open websites.
- Open folders.
- Open saved projects.
- Run saved workspace profiles.

#### Screen Intelligence

- Screenshot capture.
- Screenshot preview.
- Vision-based screen analysis.
- Screen explanation using the local vision model.

#### System Utilities

- Battery status.
- Current time.
- CPU usage.
- Disk space.
- Lock Mac.

#### Memory

- Last-command memory.
- User profile memory.
- Project/profile configuration.

#### Architecture

- Separated execution logic into `core/executor.py`.
- Simplified `jarvis_main.py`.
- Modularized planning, reasoning, and skills (browser, screen, macOS).

### Improvements

- Reduced repeated wake-word triggering.
- Added busy-state handling.
- Added cooldown between commands.
- Improved planner prompts.
- Improved YouTube recommendation workflow.
- Added project launcher.
- Added profile launcher.
- Cleaner repository structure.

### Known Limitations

- Wake-word detection occasionally produces false positives.
- OpenWakeWord will be replaced by Porcupine.
- Long-term memory has not yet been implemented.
- Tool execution still relies on conditional branching instead of a tool registry.
- Agent cannot yet re-plan after failed execution.

---

## Next Release (v1.1)

Planned features:

- Tool Registry
- Memory Manager
- Porcupine Wake Word
- Local RAG
- Agent Re-planning
- Self-healing execution
- Email and Calendar skills
- GitHub integration
- Desktop automation workflows
