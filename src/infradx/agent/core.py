from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import AsyncIterator, Protocol

from infradx.state.session import Session, Phase, Hypothesis
from infradx.knowledge import get_knowledge_base

# Matches: "1. [HIGH] text — 근거: evidence" (em-dash or hyphen variants)
_HYPO_RE = re.compile(
    r"^\d+\.\s*\[(HIGH|MED|LOW)\]\s*(.+?)\s*[—\-–]\s*근거:\s*(.+?)$",
    re.MULTILINE,
)
# Matches: "**근본 원인:** text"
_ROOT_CAUSE_RE = re.compile(r"\*\*근본 원인:\*\*\s*(.+?)$", re.MULTILINE)

_SKILLS_DIR = Path(__file__).parent.parent.parent.parent / "skills"
_AGENT_MD = Path(__file__).parent.parent.parent.parent / "AGENT.md"

# ── ① Phase-based skill loading ──────────────────────────────────────────────
# Only load skills relevant to the current phase (+ one ahead for context).
# Reduces system prompt from ~7K to ~2–4K tokens depending on phase.

_PHASE_SKILLS: dict[Phase, list[str]] = {
    Phase.CLASSIFY:         ["classify"],
    Phase.GATHER_SPEC:      ["classify", "gather-context"],
    Phase.DESCRIBE_SYMPTOM: ["gather-context"],
    Phase.REQUEST_METRICS:  ["request-metrics"],
    Phase.ANALYZE:          ["analyze", "request-metrics"],
    Phase.HYPOTHESIZE:      ["hypothesize", "analyze"],
    Phase.REPRODUCE:        ["reproduce", "hypothesize"],
    Phase.RECOMMEND:        ["recommend", "reproduce"],
}

# ── ② KB injection gating ────────────────────────────────────────────────────
# Only inject KB context in phases where it actually helps diagnosis.
# Score threshold avoids injecting loosely matched entries.

_KB_ACTIVE_PHASES = {
    Phase.REQUEST_METRICS,
    Phase.ANALYZE,
    Phase.HYPOTHESIZE,
}
_KB_MIN_SCORE = 3.0

# ── ③ History sliding window ─────────────────────────────────────────────────
# Send at most this many messages. context_prefix carries session state,
# so old turns are redundant once hypotheses and spec are collected.

_MAX_HISTORY = 12  # 6 user+assistant turn pairs


def _load_agent_md() -> str:
    return _AGENT_MD.read_text(encoding="utf-8") if _AGENT_MD.exists() else ""


def _load_skills(names: list[str]) -> str:
    parts: list[str] = []
    for name in names:
        path = _SKILLS_DIR / f"{name}.md"
        if path.exists():
            parts.append(f"\n\n---\n# Skill: {name}\n")
            parts.append(path.read_text(encoding="utf-8"))
    return "".join(parts)


class _Backend(Protocol):
    async def stream(
        self,
        system: str,
        messages: list[dict],
    ) -> AsyncIterator[str]: ...


# ── Anthropic backend ────────────────────────────────────────────────────────

class _AnthropicBackend:
    context_limit = 200_000

    def __init__(self) -> None:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY가 설정되지 않았습니다.\n"
                "console.anthropic.com 에서 API 키를 발급받아 .env에 추가해 주세요."
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = os.environ.get("INFRADX_MODEL", "claude-sonnet-4-6")
        self.last_usage: tuple[int, int] | None = None

    async def stream(self, system: str, messages: list[dict]) -> AsyncIterator[str]:
        with self._client.messages.stream(
            model=self._model,
            max_tokens=2048,
            system=system,
            messages=messages,
        ) as s:
            for text in s.text_stream:
                yield text
            try:
                final = s.get_final_message()
                u = final.usage
                self.last_usage = (u.input_tokens, u.output_tokens)
            except Exception:
                pass


# ── OpenAI / Codex backend ───────────────────────────────────────────────────

class _OpenAIBackend:
    context_limit = 128_000

    def __init__(self) -> None:
        import openai
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY가 설정되지 않았습니다.\n"
                "platform.openai.com 에서 API 키를 발급받아 .env에 추가해 주세요."
            )
        self._client = openai.AsyncOpenAI(api_key=api_key)
        self._model = os.environ.get("INFRADX_MODEL", "gpt-4o")
        self.last_usage: tuple[int, int] | None = None

    async def stream(self, system: str, messages: list[dict]) -> AsyncIterator[str]:
        full_messages = [{"role": "system", "content": system}] + messages
        async with await self._client.chat.completions.create(
            model=self._model,
            messages=full_messages,
            max_tokens=2048,
            stream=True,
            stream_options={"include_usage": True},
        ) as s:
            async for chunk in s:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                if chunk.usage:
                    self.last_usage = (
                        chunk.usage.prompt_tokens,
                        chunk.usage.completion_tokens,
                    )


# ── Claude Code CLI backend ──────────────────────────────────────────────────

class _ClaudeCodeBackend:
    """Uses the locally installed `claude` CLI (Claude Code Pro subscription).
    No separate API key needed — streams via subprocess using stream-json format."""

    context_limit = 200_000

    def __init__(self) -> None:
        if not shutil.which("claude"):
            raise RuntimeError(
                "`claude` CLI를 찾을 수 없습니다.\n"
                "Claude Code가 설치되어 있는지 확인해 주세요."
            )
        self.last_usage: tuple[int, int] | None = None

    async def stream(self, system: str, messages: list[dict]) -> AsyncIterator[str]:
        prompt = self._format_messages(messages)

        # Write system prompt to a temp file to avoid arg length limits
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(system)
            sys_file = f.name

        try:
            # Strip Anthropic/OpenAI API keys from subprocess env so the claude CLI
            # uses its own OAuth credentials (Pro subscription) instead of the key.
            env = {k: v for k, v in os.environ.items()
                   if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")}

            args = [
                "claude", "-p", prompt,
                "--system-prompt-file", sys_file,
                "--output-format", "stream-json",
                "--include-partial-messages",
                "--verbose",
                "--no-session-persistence",
            ]
            # On Windows, `claude` is a .cmd script that requires cmd.exe
            if os.name == "nt":
                proc = await asyncio.create_subprocess_exec(
                    "cmd", "/c", *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    env=env,
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    *args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    env=env,
                )

            async for raw in proc.stdout:  # type: ignore[union-attr]
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("type") == "stream_event":
                        evt = data.get("event", {})
                        if (
                            evt.get("type") == "content_block_delta"
                            and evt.get("delta", {}).get("type") == "text_delta"
                        ):
                            text = evt["delta"]["text"]
                            if text:
                                yield text
                    elif data.get("type") == "result":
                        if data.get("is_error"):
                            err = data.get("result", "알 수 없는 오류")
                            yield f"\n[오류] {err}"
                        usage = data.get("usage", {})
                        if usage:
                            self.last_usage = (
                                usage.get("input_tokens", 0),
                                usage.get("output_tokens", 0),
                            )
                except json.JSONDecodeError:
                    pass

            await proc.wait()
        finally:
            Path(sys_file).unlink(missing_ok=True)

    @staticmethod
    def _format_messages(messages: list[dict]) -> str:
        """Embed conversation history in the prompt text (claude -p is stateless)."""
        if len(messages) == 1:
            return messages[0]["content"]

        lines: list[str] = ["[이전 대화 기록]"]
        for msg in messages[:-1]:
            role = "사용자" if msg["role"] == "user" else "InfraDx"
            # Truncate very long assistant messages to save context
            content = msg["content"]
            if msg["role"] == "assistant" and len(content) > 800:
                content = content[:800] + "...(요약됨)"
            lines.append(f"{role}: {content}")

        lines.append("\n[현재 질문]")
        lines.append(messages[-1]["content"])
        return "\n".join(lines)


# ── Codex CLI backend ────────────────────────────────────────────────────────

class _CodexCLIBackend:
    """Uses the locally installed `codex` CLI (OpenAI Codex, no API key needed).
    Streams via `codex exec - --json` with prompt written to stdin."""

    context_limit = 128_000

    # item.type values that are NOT plain text responses
    _TOOL_ITEM_TYPES = frozenset({
        "tool_call", "tool_result", "command_execution", "file_change",
        "web_search", "mcp_tool_call", "plan_update",
    })

    def __init__(self) -> None:
        if not shutil.which("codex"):
            raise RuntimeError(
                "`codex` CLI를 찾을 수 없습니다.\n"
                "npm install -g @openai/codex 로 설치 후 로그인해 주세요:\n"
                "  codex login"
            )
        self.last_usage: tuple[int, int] | None = None

    async def stream(self, system: str, messages: list[dict]) -> AsyncIterator[str]:
        prompt = self._format_prompt(system, messages)

        # Strip API keys — codex uses its own OAuth credentials
        env = {k: v for k, v in os.environ.items()
               if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")}

        args = [
            "codex", "exec", "-",       # Read prompt from stdin
            "--json",                    # JSONL output to stdout
            "--sandbox", "read-only",    # Block file writes
            "--ignore-rules",            # Skip project .codex rules
            "--ephemeral",               # No session persistence
        ]
        if os.name == "nt":
            args = ["cmd", "/c"] + args

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
        )

        try:
            if proc.stdin:
                proc.stdin.write(prompt.encode("utf-8"))
                await proc.stdin.drain()
                proc.stdin.close()

            async for raw in proc.stdout:  # type: ignore[union-attr]
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    event_type = data.get("type", "")

                    if event_type == "item.completed":
                        item = data.get("item", {})
                        if item.get("type") not in self._TOOL_ITEM_TYPES:
                            text = item.get("text") or item.get("content") or ""
                            if isinstance(text, list):
                                # content may be [{type:text, text:...}] format
                                text = "".join(
                                    p.get("text", "") for p in text
                                    if isinstance(p, dict) and p.get("type") == "text"
                                )
                            if text:
                                yield str(text)

                    elif event_type == "turn.completed":
                        usage = data.get("usage", {})
                        if usage:
                            self.last_usage = (
                                usage.get("input_tokens", 0),
                                usage.get("output_tokens", 0),
                            )

                    elif event_type == "turn.failed":
                        err = data.get("error", {})
                        msg = err.get("message", "알 수 없는 오류") if isinstance(err, dict) else str(err)
                        yield f"\n[오류] {msg}"

                except json.JSONDecodeError:
                    pass

            await proc.wait()
        finally:
            if proc.returncode is None:
                proc.kill()

    @staticmethod
    def _format_prompt(system: str, messages: list[dict]) -> str:
        """Embed system prompt + history in stdin prompt (codex exec is stateless)."""
        lines = [
            "[시스템 지침]",
            system,
            "",
            "※ 중요: 파일 수정이나 명령어 실행 없이 텍스트 답변만 작성하세요.",
            "",
        ]

        if len(messages) > 1:
            lines.append("[이전 대화 기록]")
            for msg in messages[:-1]:
                role = "사용자" if msg["role"] == "user" else "InfraDx"
                content = msg["content"]
                if msg["role"] == "assistant" and len(content) > 800:
                    content = content[:800] + "...(요약됨)"
                lines.append(f"{role}: {content}")
            lines.append("")

        lines.append("[현재 질문]")
        lines.append(messages[-1]["content"])
        return "\n".join(lines)


# ── Provider factory ─────────────────────────────────────────────────────────

_PROVIDERS = {
    "anthropic": _AnthropicBackend,
    "claude": _AnthropicBackend,
    "openai": _OpenAIBackend,
    "codex": _OpenAIBackend,       # OpenAI API (API key required)
    "claudecode": _ClaudeCodeBackend,
    "local": _ClaudeCodeBackend,
    "codexcli": _CodexCLIBackend,  # Codex CLI (no API key)
}

_PROVIDER_INSTALL = {
    "anthropic": "anthropic",
    "claude": "anthropic",
    "openai": "openai",
    "codex": "openai",
    "claudecode": None,
    "local": None,
    "codexcli": None,
}


def _auto_detect_provider() -> str:
    """Try each free CLI backend first, then API key backends, in priority order."""
    if shutil.which("claude"):
        return "claudecode"
    if shutil.which("codex"):
        return "codexcli"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    raise RuntimeError(
        "사용 가능한 AI 프로바이더를 찾을 수 없습니다.\n"
        "\n"
        "다음 중 하나를 설정해 주세요:\n"
        "  [무료] Claude Code CLI  → claude CLI 설치 후 로그인\n"
        "  [무료] OpenAI Codex CLI → npm install -g @openai/codex 후 codex login\n"
        "  [유료] OpenAI API       → .env에 OPENAI_API_KEY 설정\n"
        "  [유료] Anthropic API    → .env에 ANTHROPIC_API_KEY 설정\n"
        "\n"
        "또는 .env에 INFRADX_PROVIDER=<값>으로 직접 지정하세요."
    )


def _make_backend() -> _AnthropicBackend | _OpenAIBackend:
    provider = os.environ.get("INFRADX_PROVIDER", "").strip().lower()
    if not provider:
        provider = _auto_detect_provider()

    cls = _PROVIDERS.get(provider)
    if cls is None:
        raise RuntimeError(
            f"알 수 없는 프로바이더: '{provider}'\n"
            f"지원 값: {', '.join(_PROVIDERS.keys())}"
        )
    try:
        return cls()
    except ImportError:
        pkg = _PROVIDER_INSTALL.get(provider)
        if pkg:
            raise RuntimeError(
                f"'{pkg}' 패키지가 설치되지 않았습니다.\n"
                f"실행: pip install {pkg}"
            )
        raise


# ── AgentCore ────────────────────────────────────────────────────────────────

class AgentCore:
    def __init__(self) -> None:
        self._backend = _make_backend()
        self._agent_md = _load_agent_md()
        self._skill_cache: dict[str, str] = {}
        for path in _SKILLS_DIR.glob("*.md"):
            self._skill_cache[path.stem] = path.read_text(encoding="utf-8")
        self._kb = get_knowledge_base()
        self._context_limit: int = getattr(self._backend, "context_limit", 200_000)

    def _build_system_prompt(self, phase: Phase) -> str:
        """Build a phase-appropriate system prompt (AGENT.md + relevant skills only)."""
        skill_names = _PHASE_SKILLS.get(phase, [])
        skill_parts: list[str] = []
        for name in skill_names:
            if name in self._skill_cache:
                skill_parts.append(f"\n\n---\n# Skill: {name}\n")
                skill_parts.append(self._skill_cache[name])
        return self._agent_md + "".join(skill_parts)

    async def stream_response(
        self, session: Session, user_message: str
    ) -> AsyncIterator[str]:
        session.add_message("user", user_message)
        session.context_limit = self._context_limit

        system = self._build_system_prompt(session.phase)
        context_prefix = self._build_context_prefix(session)
        messages = self._build_messages(session, context_prefix)

        full_response = ""
        async for chunk in self._backend.stream(system, messages):
            full_response += chunk
            yield chunk

        session.add_message("assistant", full_response)
        self._update_session_phase(session, full_response)
        self._parse_hypotheses(session, full_response)
        self._parse_root_cause(session, full_response)

        usage = getattr(self._backend, "last_usage", None)
        if usage:
            session.last_prompt_tokens, session.last_output_tokens = usage
            session.total_output_tokens += usage[1]

    def _build_context_prefix(self, session: Session) -> str:
        lines = [
            f"[Current Phase: {session.phase.value}]",
            f"[Domain: {session.domain or 'not set'}]",
        ]
        if session.spec.os_type:
            lines.append(f"[OS: {session.spec.os_type} {session.spec.kernel_version or ''}]")
        if session.metrics_collected:
            lines.append(f"[Metrics collected: {', '.join(session.metrics_collected)}]")
        if session.hypotheses:
            top = session.top_hypothesis()
            if top:
                lines.append(f"[Top hypothesis ({top.confidence}): {top.text}]")

        kb_context = self._build_kb_context(session)
        if kb_context:
            lines.append(kb_context)

        return "\n".join(lines)

    def _build_kb_context(self, session: Session) -> str:
        """Inject KB only in diagnostic phases and only when score is high enough."""
        if session.phase not in _KB_ACTIVE_PHASES:
            return ""

        query_parts: list[str] = []
        if session.symptom.error_text:
            query_parts.append(session.symptom.error_text[:200])
        if session.hypotheses:
            top = session.top_hypothesis()
            if top:
                query_parts.append(top.text)
        if session.symptom.started_when:
            query_parts.append(session.symptom.started_when)

        if not query_parts:
            return ""

        if session.spec.cloud_provider:
            query_parts.append(session.spec.cloud_provider)
        if session.spec.cloud_service:
            query_parts.append(session.spec.cloud_service)
        if session.spec.k8s_distribution:
            query_parts.append(session.spec.k8s_distribution)
        if session.spec.k8s_problem_scope:
            query_parts.append(session.spec.k8s_problem_scope)

        query = " ".join(query_parts)
        search_os = None if session.domain in ("kubernetes", "cloud") else session.spec.os_type

        entries = self._kb.search(
            query=query,
            domain="server",
            os_type=search_os,
            top_n=2,
            min_score=_KB_MIN_SCORE,
        )

        if not entries:
            return ""

        blocks = ["[Knowledge Base — 관련 알려진 이슈:]"]
        for entry in entries:
            blocks.append(entry.to_context_block())
        return "\n".join(blocks)

    def _build_messages(self, session: Session, context_prefix: str) -> list[dict]:
        """Send only the last _MAX_HISTORY messages; context_prefix carries session state."""
        all_messages = session.messages
        window = all_messages[-_MAX_HISTORY:] if len(all_messages) > _MAX_HISTORY else all_messages
        last_idx = len(window) - 1

        result: list[dict] = []
        for i, msg in enumerate(window):
            content = msg["content"]
            if msg["role"] == "user" and i == last_idx:
                content = f"{context_prefix}\n\n{content}"
            result.append({"role": msg["role"], "content": content})
        return result

    def _parse_hypotheses(self, session: Session, response: str) -> None:
        matches = _HYPO_RE.findall(response)
        if not matches:
            return
        new_hypos: list[Hypothesis] = []
        for conf, text, evidence in matches:
            text = text.strip()
            evidence = evidence.strip()
            existing = next(
                (h for h in session.hypotheses if h.text[:25] in text or text[:25] in h.text),
                None,
            )
            status = existing.status if existing else "investigating"
            new_hypos.append(Hypothesis(text=text, confidence=conf, evidence=evidence, status=status))
        if new_hypos:
            session.hypotheses = new_hypos

    def _parse_root_cause(self, session: Session, response: str) -> None:
        match = _ROOT_CAUSE_RE.search(response)
        if not match:
            return
        session.root_cause = match.group(1).strip()
        root_words = set(session.root_cause.lower().split())
        for h in session.hypotheses:
            overlap = root_words & set(h.text.lower().split())
            if len(overlap) >= 2:
                h.status = "validated"
            elif h.status == "investigating":
                h.status = "invalidated"

    def _update_session_phase(self, session: Session, response: str) -> None:
        response_lower = response.lower()
        phase_order = list(Phase)
        current_idx = phase_order.index(session.phase)

        phase_signals = {
            Phase.CLASSIFY:         ["영역", "domain", "서버인가요", "네트워크인가요", "디스크인가요"],
            Phase.GATHER_SPEC:      ["uname", "kernel", "운영체제", "배포 유형", "버전을 알려", "어떤 os"],
            Phase.DESCRIBE_SYMPTOM: ["증상", "symptom", "언제부터", "언제 시작", "에러 메시지"],
            Phase.REQUEST_METRICS:  ["명령어", "실행해주세요", "붙여넣", "paste", "수집해주세요",
                                     "iostat", "vmstat", "df -h", "free -m", "netstat",
                                     "journalctl", "kubectl get", "kubectl describe", "top -"],
            Phase.ANALYZE:          ["분석", "analysis", "패턴", "의심", "가능성"],
            Phase.HYPOTHESIZE:      ["근본 원인", "root cause", "최종 진단", "가설 확정"],
            Phase.REPRODUCE:        ["재현", "reproduction", "재현 시나리오", "재현 방법"],
            Phase.RECOMMEND:        ["권고", "recommend", "즉각 조치", "mitigation", "해결 방법"],
        }

        # Find the highest phase whose signals appear in the response
        best_idx = current_idx
        for phase, signals in phase_signals.items():
            candidate_idx = phase_order.index(phase)
            if candidate_idx > current_idx and any(sig in response_lower for sig in signals):
                best_idx = max(best_idx, candidate_idx)

        if best_idx > current_idx:
            session.phase = phase_order[best_idx]
