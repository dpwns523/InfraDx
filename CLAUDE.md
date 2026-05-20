# InfraDx — Claude Code Project Context

## Project Overview
InfraDx is an AI-powered infrastructure troubleshooting tool (TUI/GUI).
An AI agent guides users through diagnosing server, network, and disk issues
via structured, step-by-step reasoning and targeted metric collection.

## Architecture
```
infradx/
├── AGENT.md                  # Agent system prompt & state machine
├── skills/                   # Individual skill definitions
├── src/
│   ├── agent/                # AI agent core (Claude API integration)
│   ├── tui/                  # Textual-based TUI
│   ├── state/                # Session state machine
│   └── knowledge/            # Domain knowledge base (Linux/AIX/Network/Disk)
├── codex/                    # OpenAI Codex-compatible instructions
└── pyproject.toml
```

## Tech Stack
- **Language**: Python 3.11+
- **TUI**: [Textual](https://textual.textualize.io/)
- **AI**: Anthropic Claude API (`claude-sonnet-4-6`)
- **State**: SQLite via `aiosqlite`
- **Package manager**: `uv`

## Key Files
- `AGENT.md` — Full agent system prompt, state machine, command reference
- `skills/*.md` — Modular skill definitions, each with trigger/input/output spec
- `src/agent/core.py` — Agent loop, phase transitions, Claude API calls
- `src/state/session.py` — Session persistence (SQLite)
- `src/tui/app.py` — Textual app entry point

## Development Setup
```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
python -m infradx
```

## Environment Variables
```
ANTHROPIC_API_KEY=<your key>
INFRADX_MODEL=claude-sonnet-4-6        # optional override
INFRADX_DB_PATH=~/.local/share/infradx/sessions.db  # optional
```

## Agent Behavior Rules
- Always read `AGENT.md` for the full state machine before modifying agent logic
- Skills in `skills/` are loaded dynamically — adding a `.md` file registers it
- Phase transitions live in `src/state/session.py` — do not hardcode phases in TUI
- The TUI is a view only — all reasoning lives in `src/agent/`

## Coding Conventions
- Async throughout (`asyncio`, `aiofiles`, `aiosqlite`)
- Type hints on all public functions
- Textual widgets go in `src/tui/widgets/`
- No business logic in TUI layer
