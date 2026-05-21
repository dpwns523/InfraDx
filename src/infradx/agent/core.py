from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncIterator, Protocol

from infradx.state.session import Session, Phase
from infradx.knowledge import get_knowledge_base

_SKILLS_DIR = Path(__file__).parent.parent.parent.parent / "skills"
_AGENT_MD = Path(__file__).parent.parent.parent.parent / "AGENT.md"


def _load_system_prompt() -> str:
    parts: list[str] = []
    if _AGENT_MD.exists():
        parts.append(_AGENT_MD.read_text())
    for skill_file in sorted(_SKILLS_DIR.glob("*.md")):
        parts.append(f"\n\n---\n# Skill: {skill_file.stem}\n")
        parts.append(skill_file.read_text())
    return "\n".join(parts)


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


# ── Provider factory ─────────────────────────────────────────────────────────

_PROVIDERS = {
    "anthropic": _AnthropicBackend,
    "claude": _AnthropicBackend,
    "openai": _OpenAIBackend,
    "codex": _OpenAIBackend,
}

_PROVIDER_INSTALL = {
    "anthropic": "anthropic",
    "claude": "anthropic",
    "openai": "openai",
    "codex": "openai",
}


def _make_backend() -> _AnthropicBackend | _OpenAIBackend:
    provider = os.environ.get("INFRADX_PROVIDER", "anthropic").lower()
    cls = _PROVIDERS.get(provider)
    if cls is None:
        raise RuntimeError(
            f"알 수 없는 프로바이더: '{provider}'\n"
            f"지원 값: {', '.join(_PROVIDERS.keys())}"
        )
    try:
        return cls()
    except ImportError:
        pkg = _PROVIDER_INSTALL[provider]
        raise RuntimeError(
            f"'{pkg}' 패키지가 설치되지 않았습니다.\n"
            f"실행: pip install {pkg}"
        )


# ── AgentCore ────────────────────────────────────────────────────────────────

class AgentCore:
    def __init__(self) -> None:
        self._backend = _make_backend()
        self._system_prompt = _load_system_prompt()
        self._kb = get_knowledge_base()

    async def stream_response(
        self, session: Session, user_message: str
    ) -> AsyncIterator[str]:
        session.add_message("user", user_message)

        context_prefix = self._build_context_prefix(session)
        messages = self._build_messages(session, context_prefix)

        full_response = ""
        async for chunk in self._backend.stream(self._system_prompt, messages):
            full_response += chunk
            yield chunk

        session.add_message("assistant", full_response)
        self._update_session_phase(session, full_response)

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

        # Inject relevant knowledge base entries
        kb_context = self._build_kb_context(session)
        if kb_context:
            lines.append(kb_context)

        return "\n".join(lines)

    def _build_kb_context(self, session: Session) -> str:
        """Search KB for entries relevant to the current session state."""
        query_parts: list[str] = []

        # Build search query from session state
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

        # Enrich query with cloud/k8s spec context
        if session.spec.cloud_provider:
            query_parts.append(session.spec.cloud_provider)
        if session.spec.cloud_service:
            query_parts.append(session.spec.cloud_service)
        if session.spec.k8s_distribution:
            query_parts.append(session.spec.k8s_distribution)
        if session.spec.k8s_problem_scope:
            query_parts.append(session.spec.k8s_problem_scope)

        query = " ".join(query_parts)

        # For kubernetes/cloud domains, search with os_type override
        search_os = session.spec.os_type
        if session.domain in ("kubernetes", "cloud"):
            search_os = None  # don't filter by OS for these domains

        entries = self._kb.search(
            query=query,
            domain="server",  # kubernetes/cloud entries are filed under server domain
            os_type=search_os,
            top_n=2,
        )

        if not entries:
            return ""

        blocks = ["[Knowledge Base — 관련 알려진 이슈:]"]
        for entry in entries:
            blocks.append(entry.to_context_block())

        return "\n".join(blocks)

    def _build_messages(self, session: Session, context_prefix: str) -> list[dict]:
        messages: list[dict] = []
        for i, msg in enumerate(session.messages):
            content = msg["content"]
            if msg["role"] == "user" and i == len(session.messages) - 1:
                content = f"{context_prefix}\n\n{content}"
            messages.append({"role": msg["role"], "content": content})
        return messages

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
