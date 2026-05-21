# InfraDx — Claude Code Project Context

## Project Overview
InfraDx is an AI-powered infrastructure troubleshooting tool (TUI).
An AI agent guides users through diagnosing server, network, disk, Kubernetes, and public cloud issues
via structured, 8-phase step-by-step reasoning with automated hypothesis generation.

**Primary backend: OpenAI GPT-4o / Codex** (`INFRADX_PROVIDER=openai`)
Secondary backend: Anthropic Claude (`INFRADX_PROVIDER=anthropic`)

## Architecture
```
infradx/
├── AGENT.md                  # Agent system prompt & 8-phase state machine
├── codex/
│   └── agent_instructions.md # OpenAI Codex-compatible instructions (Function Calling)
├── skills/                   # Individual skill definitions (auto-loaded into system prompt)
├── docs/
│   └── architecture.md       # Mermaid diagrams: system, phase state machine, hypothesis lifecycle
├── src/
│   ├── agent/core.py         # AgentCore: streaming, KB injection, hypothesis parsing
│   ├── tui/                  # Textual TUI (app + chat + sidebar widgets)
│   ├── state/session.py      # Session, Phase, Hypothesis, SystemSpec dataclasses
│   └── knowledge/            # YAML knowledge base (51 known issues across 7 domains)
└── pyproject.toml
```

## Tech Stack
- **Language**: Python 3.11+
- **TUI**: [Textual](https://textual.textualize.io/) 8.x
- **AI (primary)**: OpenAI API — `gpt-4o` via `openai.AsyncOpenAI`
- **AI (secondary)**: Anthropic API — `claude-sonnet-4-6` via `anthropic.Anthropic`
- **Package manager**: `uv`

## Key Files
- `AGENT.md` — Full agent system prompt, 8-phase state machine, command reference for all 5 domains
- `codex/agent_instructions.md` — OpenAI Codex version: Function Calling JSON schemas + inlined skills
- `skills/*.md` — Modular skill definitions, auto-merged into system prompt alphabetically
- `src/agent/core.py` — `AgentCore`: `stream_response()`, `_parse_hypotheses()`, `_parse_root_cause()`, `_build_kb_context()`
- `src/state/session.py` — `Session`, `Phase` (8 values), `Hypothesis` (with `status` field), `SystemSpec`, `Symptom`
- `src/tui/app.py` — Textual app: action button handlers, `Ctrl+C/N/S/Q` bindings, `action_export_report()`
- `src/tui/widgets/chat.py` — `ChatPanel`: line-buffered streaming, 3 action buttons, `set_buttons_disabled()`
- `src/tui/widgets/sidebar.py` — `SidebarPanel`: phase progress, spec summary, hypothesis list with status badges

## Development Setup
```bash
uv venv --python 3.11 && source .venv/bin/activate
uv pip install -e ".[dev,openai]"
cp .env.example .env   # add OPENAI_API_KEY
python -m infradx
```

## Environment Variables
```
INFRADX_PROVIDER=openai              # openai (default) | anthropic
OPENAI_API_KEY=<your key>            # primary
ANTHROPIC_API_KEY=<your key>         # secondary
INFRADX_MODEL=gpt-4o                 # optional model override
INFRADX_DB_PATH=~/.local/share/infradx/sessions.db
```

## Agent Behavior Rules
- Always read `AGENT.md` before modifying agent logic
- Phase transitions in `src/state/session.py` — do not hardcode in TUI
- `skills/*.md` are loaded dynamically — adding a file auto-registers it
- Hypothesis format that `_parse_hypotheses()` expects: `N. [HIGH|MED|LOW] text — 근거: evidence` (em dash)
- `Hypothesis.status`: `investigating` → `validated` or `invalidated` at HYPOTHESIZE phase
- TUI is view-only — all reasoning in `src/agent/`

## Hypothesis Auto-Generation
After DESCRIBE_SYMPTOM, the AI must output hypotheses in this exact format:
```
1. [MED] <hypothesis> — 근거: <evidence>
2. [LOW] <hypothesis> — 근거: <evidence>
```
`AgentCore._parse_hypotheses()` extracts these via regex and populates `session.hypotheses`.

## Knowledge Base
- 51 known issues across 7 YAML files in `src/infradx/knowledge/data/`
- Search uses TF-IDF-style scoring: title ×3.0, keywords ×2.5, symptoms ×2.0, dmesg ×2.0
- `kubernetes`, `monitoring`, `cloud` entries bypass OS-type filtering (`_cross_os` set)
- Top 2 matching entries are injected into each prompt via `_build_kb_context()`

## Coding Conventions
- Async throughout (`asyncio`, `aiofiles`, `aiosqlite`)
- Type hints on all public functions
- No business logic in TUI layer — route everything through `AgentCore`
- Textual widgets in `src/tui/widgets/`
- RichLog.write() has no `end` param — use line-buffering pattern in `ChatPanel.append_chunk()`
