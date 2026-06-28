# DEVLOG

## Project Vision

Jarvis Voice is a fully local AI personal assistant designed to reason, plan, and perform tasks on my Mac. The long-term goal is to create an autonomous agent capable of understanding natural language, interacting with desktop applications, browsing the web, remembering user preferences, and assisting with software development.

Unlike traditional voice assistants, Jarvis should make decisions using planning and reasoning rather than relying on hardcoded commands.

---

## Session 1 — Initial Foundation

### Goal

Build a local voice assistant that works completely offline.

### Decisions

- Chose Python as the primary language.
- Chose Ollama for running local LLMs.
- Chose Whisper for offline speech recognition.
- Used macOS `say` for text-to-speech.

### Lessons Learned

- Offline speech recognition is sufficiently accurate.
- Local inference is fast enough for interactive use.

---

## Session 2 — Browser Automation

### Goal

Allow Jarvis to interact with websites.

### Decisions

- Selected Playwright instead of Selenium.
- Implemented Google and YouTube search tools.

### Problems

Browser closed immediately after execution.

### Solution

Added wait conditions and adjusted browser lifecycle management.

### Lessons Learned

Browser automation should be separated from reasoning logic.

---

## Session 3 — Planner

### Goal

Move from command execution to goal-based execution.

### Decisions

Introduced a planner that converts natural language into structured JSON plans.

Example:

```
User Goal: Find me good Python videos
        ↓
    Planner
        ↓
get_youtube_video_details
        ↓
    Reasoner
        ↓
Recommendation
```

### Problems

Planner occasionally generated invalid tools and empty targets.

### Solution

Improved prompts and added plan validation.

### Lessons Learned

LLMs require guardrails and validation before execution.

---

## Session 4 — Vision

### Goal

Allow Jarvis to understand what is visible on screen.

### Decisions

Implemented screenshot capture and vision analysis.

### Problems

Image decoding errors due to binary data handling.

### Solution

Corrected image processing pipeline.

### Lessons Learned

Vision tools should always return structured observations.

---

## Session 5 — Architecture Refactor

### Goal

Reduce complexity in `jarvis_main.py`.

### Decisions

Created `core/executor.py`.

Separated responsibilities:

- Wake loop
- Command parsing
- Planning
- Tool execution
- Reasoning

### Lessons Learned

Large conditional blocks become difficult to maintain. Execution logic should remain independent from the wake loop.

---

## Current Architecture

```
Microphone
        ↓
Wake Word
        ↓
Whisper
        ↓
Command Parser
        ↓
Planner
        ↓
Executor
        ↓
MCP Tools
        ↓
Observation
        ↓
Reasoner
        ↓
Final Response
```

---

## Future Ideas

- Replace OpenWakeWord with Porcupine.
- Tool registry.
- Long-term memory.
- Local RAG.
- Desktop automation.
- Email and Calendar integration.
- GitHub automation.
- Autonomous replanning.
- Self-healing execution.
- Multi-agent architecture.

---

## Personal Notes

### Things that worked well

-

### Things that should be redesigned

-

### Interesting ideas to explore

-

### Performance observations

-

### Models tested

| Model       | Purpose             | Notes                  |
| ----------- | ------------------- | ---------------------- |
| qwen3:4b    | Command parsing     | Fast, lightweight      |
| qwen3:30b   | Planned upgrade     | Better reasoning       |
| qwen3-coder | Future coding tasks | Dedicated coding model |
