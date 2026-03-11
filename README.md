# AgentForge

> A multi-agent CLI that forges code through a **Worker** and an **Evaluator** collaborating in a loop — until the goal is achieved.

Inspired by [OpenCode](https://opencode.ai), AgentForge wraps AI coding CLIs (currently `codex`, with Claude and Gemini support planned) to orchestrate two specialized agents: one that acts, one that judges.

[한국어 README](./README.ko.md)

---

## Demo

```
┌─ ⚙ WORKER AGENT ──────────────────────┬─ ◈ EVALUATOR AGENT ────────────────────┐
│                                        │                                         │
│ > Reading App.tsx...                   │ [Iter 1]                                │
│ > Writing dark_mode.css...             │ IMPROVE:                                │
│ > Modifying index.html...              │ Toggle button is missing.               │
│ ▌                                      │ Save state to localStorage.             │
│                                        │                                         │
│ [Iter 2]                               │ [Iter 2]                                │
│ > Adding ThemeToggle.tsx...            │ ✓ DONE                                  │
│ ✓ Created 2 files                      │ 결과물: ./src/ThemeToggle.tsx            │
│                                        │                                         │
└────────────────────────────────────────┴─────────────────────────────────────────┘
[AgentForge] > /plan Add dark mode to the React app
```

---

## How It Works

```
User input (goal)
       │
       ▼
 ┌─────────────┐     code changes      ┌────────────────┐
 │   Worker    │ ───────────────────►  │   file system  │
 │   Agent     │   (full-auto sandbox) └────────────────┘
 └──────┬──────┘
        │ output
        ▼
 ┌──────────────────┐
 │   Evaluator      │
 │   Agent          │  (read-only sandbox — cannot modify files)
 └────────┬─────────┘
          │
          ├── DONE      →  Print Korean summary, wait for next command
          ├── IMPROVE   →  Send feedback to Worker → repeat
          └── REDIRECT  →  Change strategy entirely → repeat
```

The loop continues until the Evaluator decides `DONE` or the iteration limit is reached.

### DONE Output Example

```
════════════════ ✓ Done — 3 iterations ════════════════

판단 이유
  Dark mode has been fully implemented with a toggle button.
  The theme state persists via localStorage across page reloads.

결과물 위치
  • ./src/ThemeToggle.tsx
  • ./src/App.tsx  (modified)

결과 요약
  React-based dark mode with persistent state. No extra dependencies.
```

---

## Requirements

- Python 3.10+
- [`codex` CLI](https://github.com/openai/codex) — installed and authenticated
- Python packages: `rich`, `prompt_toolkit`

---

## Installation

```bash
git clone https://github.com/<your-username>/AgentForge.git
cd AgentForge
bash install.sh
```

Or manually:

```bash
cp agentforge ~/.local/bin/agentforge
chmod +x ~/.local/bin/agentforge
pip install rich prompt_toolkit
```

---

## Usage

```bash
agentforge                  # Launch interactive CLI
agentforge -d /my/project   # Set working directory
agentforge -n 20            # Set max iterations (default: 5000)
```

### Slash Commands

| Command | Description |
|---------|-------------|
| `<goal text>` | Send goal directly to the Worker agent and start the loop |
| `/plan <goal>` | Plan Agent drafts a plan → Q&A → confirm → execute |
| `/exit` | Exit AgentForge |

> Type `/` to see available commands with autocomplete (like Claude Code).

### /plan Flow

```
[AgentForge] > /plan Build a simple web page that says hello

[Plan Agent]
계획:
- Create index.html
- Add <h1>hello</h1>

accept (y/n) > y

▶ Starting Worker + Evaluator loop...
```

---

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `-d DIR` | `.` | Working directory |
| `-n N` | `5000` | Max iterations |
| `--worker-model M` | config default | Model for Worker agent |
| `--eval-model M` | config default | Model for Evaluator agent |

---

## Roadmap

- [x] `codex` CLI backend
- [ ] Claude CLI backend
- [ ] Gemini CLI backend
- [ ] Configurable agent personas
- [ ] Session history export

---

## Project Structure

```
AgentForge/
├── agentforge      # Main executable script
├── install.sh      # Installation script
├── README.md       # English README (this file)
├── README.ko.md    # Korean README
└── .gitignore
```

---

## Inspiration

- [OpenCode](https://opencode.ai) — terminal-first AI coding agent
- [Codex CLI](https://github.com/openai/codex) — current underlying engine

---

## License

MIT
