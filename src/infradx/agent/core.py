from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncIterator

import anthropic

from infradx.state.session import Session, Phase

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


class AgentCore:
    def __init__(self) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = os.environ.get("INFRADX_MODEL", "claude-sonnet-4-6")
        self._system_prompt = _load_system_prompt()

    async def stream_response(
        self, session: Session, user_message: str
    ) -> AsyncIterator[str]:
        session.add_message("user", user_message)

        context_prefix = self._build_context_prefix(session)
        messages = self._build_messages(session, context_prefix)

        with self._client.messages.stream(
            model=self._model,
            max_tokens=2048,
            system=self._system_prompt,
            messages=messages,
        ) as stream:
            full_response = ""
            for text in stream.text_stream:
                full_response += text
                yield text

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

        return "\n".join(lines)

    def _build_messages(
        self, session: Session, context_prefix: str
    ) -> list[dict]:
        messages: list[dict] = []

        for i, msg in enumerate(session.messages):
            content = msg["content"]
            # Prepend context to the last user message
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
