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

    async def stream(self, system: str, messages: list[dict]) -> AsyncIterator[str]:
        with self._client.messages.stream(
            model=self._model,
            max_tokens=2048,
            system=system,
            messages=messages,
        ) as s:
            for text in s.text_stream:
                yield text


# ── OpenAI / Codex backend ───────────────────────────────────────────────────

class _OpenAIBackend:
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

    async def stream(self, system: str, messages: list[dict]) -> AsyncIterator[str]:
        full_messages = [{"role": "system", "content": system}] + messages
        async with await self._client.chat.completions.create(
            model=self._model,
            messages=full_messages,
            max_tokens=2048,
            stream=True,
        ) as s:
            async for chunk in s:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta


# ── Claude Code CLI backend ──────────────────────────────────────────────────

class _ClaudeCodeBackend:
    """Uses the locally installed `claude` CLI (Claude Code Pro subscription).
    No separate API key needed — streams via subprocess using stream-json format."""

    def __init__(self) -> None:
        if not shutil.which("claude"):
            raise RuntimeError(
                "`claude` CLI를 찾을 수 없습니다.\n"
                "Claude Code가 설치되어 있는지 확인해 주세요."
            )

    async def stream(self, system: str, messages: list[dict]) -> AsyncIterator[str]:
        prompt = self._format_messages(messages)

        # Write system prompt to a temp file to avoid arg length limits
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(system)
            sys_file = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", prompt,
                "--system-prompt-file", sys_file,
                "--output-format", "stream-json",
                "--include-partial-messages",
                "--verbose",
                "--no-session-persistence",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
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
                    elif data.get("type") == "result" and data.get("is_error"):
                        err = data.get("result", "알 수 없는 오류")
                        yield f"\n[오류] {err}"
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


# ── Provider factory ─────────────────────────────────────────────────────────

_PROVIDERS = {
    "anthropic": _AnthropicBackend,
    "claude": _AnthropicBackend,
    "openai": _OpenAIBackend,
    "codex": _OpenAIBackend,
    "claudecode": _ClaudeCodeBackend,
    "local": _ClaudeCodeBackend,
}

_PROVIDER_INSTALL = {
    "anthropic": "anthropic",
    "claude": "anthropic",
    "openai": "openai",
    "codex": "openai",
    "claudecode": None,
    "local": None,
}


def _make_backend() -> _AnthropicBackend | _OpenAIBackend:
    provider = os.environ.get("INFRADX_PROVIDER", "openai").lower()
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
        # Pre-load all skill files into a cache
        self._skill_cache: dict[str, str] = {}
        for path in _SKILLS_DIR.glob("*.md"):
            self._skill_cache[path.stem] = path.read_text(encoding="utf-8")
        self._kb = get_knowledge_base()

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
        phase_signals = {
            Phase.CLASSIFY: ["domain", "server", "network", "disk", "영역"],
            Phase.GATHER_SPEC: ["spec", "uname", "kernel", "사양", "운영체제"],
            Phase.DESCRIBE_SYMPTOM: ["증상", "symptom", "에러", "error", "언제부터"],
            Phase.REQUEST_METRICS: ["명령어", "command", "붙여넣", "paste"],
            Phase.ANALYZE: ["분석", "analysis", "가설", "hypothesis"],
            Phase.HYPOTHESIZE: ["근본 원인", "root cause", "최종 진단"],
            Phase.REPRODUCE: ["재현", "reproduction", "재현 시나리오"],
            Phase.RECOMMEND: ["권고", "recommend", "즉각 조치", "mitigation"],
        }
        for phase, signals in phase_signals.items():
            if any(sig in response_lower for sig in signals):
                if phase.value > session.phase.value:
                    session.phase = phase
                break
