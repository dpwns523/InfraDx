from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button
from textual.containers import Horizontal
from textual import on, work

from infradx.state.session import Session
from infradx.agent.core import AgentCore
from infradx.tui.widgets.chat import ChatPanel, _ChatInput
from infradx.tui.widgets.sidebar import SidebarPanel, _PHASE_LABELS, _PHASE_REASK


_WELCOME = """\
[bold green]InfraDx[/bold green] — AI 인프라 트러블슈팅 도구

서버, 네트워크, 디스크, Kubernetes, 퍼블릭 클라우드 장애를 단계별로 진단합니다.
Ctrl+S: 보고서 저장  Ctrl+C: 명령어 복사  Ctrl+N: 새 세션  Ctrl+Q: 종료
───────────────────────────────────────────────────
"""

_INIT_MESSAGE = "안녕하세요! 어떤 문제가 발생했나요? 서버, 네트워크, 디스크 중 어떤 영역인지 알려주시거나 증상을 자유롭게 설명해 주세요."

_ACTION_MESSAGES = {
    "btn-metrics": "지금까지의 증상과 가설을 바탕으로 수집해야 할 모든 연관 메트릭을 분석하고 다음 명령어를 요청해주세요.",
    "btn-hypothesize": "지금까지 수집된 데이터를 바탕으로 가설 목록을 업데이트하고 신뢰도를 재평가해주세요.",
    "btn-conclude": "지금까지 수집된 모든 근거를 바탕으로 최종 결론과 권고사항을 도출해주세요.",
}


class InfraDxApp(App):
    """Main InfraDx TUI application."""

    TITLE = "InfraDx"
    SUB_TITLE = "AI Infrastructure Diagnostics"

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-area {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("ctrl+q", "quit", "종료"),
        ("ctrl+n", "new_session", "새 세션"),
        ("ctrl+c", "copy_last_command", "명령어 복사"),
        ("ctrl+s", "export_report", "보고서 저장"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._session = Session(session_id=str(uuid.uuid4()))
        self._agent: AgentCore | None = None
        self._last_command: str | None = None
        self._is_streaming = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-area"):
            yield ChatPanel(id="chat-panel")
            yield SidebarPanel(id="sidebar-panel")
        yield Footer()

    def on_mount(self) -> None:
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.append_user("")
        chat.query_one("#chat-log").write(_WELCOME)

        try:
            self._agent = AgentCore()
            backend = type(self._agent._backend).__name__
            provider_label = {
                "_AnthropicBackend":  "Anthropic API",
                "_OpenAIBackend":     "OpenAI API",
                "_ClaudeCodeBackend": "Claude Code CLI",
                "_CodexCLIBackend":   "OpenAI Codex CLI",
            }.get(backend, backend)
            chat.query_one("#chat-log").write(
                f"[dim]백엔드: {provider_label}[/dim]"
            )
            self._send_init_message()
        except RuntimeError as e:
            chat.query_one("#chat-log").write(
                f"[bold red]오류:[/bold red] {e}"
            )

        chat.focus_input()

    @work(exclusive=True)
    async def _send_init_message(self) -> None:
        await self._stream_agent_response(_INIT_MESSAGE, inject=True)

    @on(_ChatInput.Submitted)
    async def on_input_submitted(self, event: _ChatInput.Submitted) -> None:
        text = event.value.strip()
        if not text or self._is_streaming:
            return

        chat = self.query_one("#chat-panel", ChatPanel)
        chat.append_user(text)

        self._handle_user_message(text)

    @on(SidebarPanel.PhaseClicked)
    async def on_phase_clicked(self, event: SidebarPanel.PhaseClicked) -> None:
        if self._is_streaming:
            return
        message = _PHASE_REASK.get(event.phase)
        if not message:
            return
        chat = self.query_one("#chat-panel", ChatPanel)
        phase_label = _PHASE_LABELS.get(event.phase, event.phase.value)
        chat.append_user(f"[단계 재실행] {phase_label}")
        self._handle_user_message(message)

    @on(Button.Pressed, "#btn-metrics")
    @on(Button.Pressed, "#btn-hypothesize")
    @on(Button.Pressed, "#btn-conclude")
    async def on_action_button(self, event: Button.Pressed) -> None:
        if self._is_streaming:
            return
        btn_id = str(event.button.id)
        message = _ACTION_MESSAGES.get(btn_id)
        if not message:
            return
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.append_user(f"[액션] {event.button.label}")
        self._handle_user_message(message)

    @work(exclusive=False)
    async def _handle_user_message(self, text: str) -> None:
        await self._stream_agent_response(text)

    async def _stream_agent_response(
        self, text: str, inject: bool = False
    ) -> None:
        if self._agent is None:
            return

        self._is_streaming = True
        chat = self.query_one("#chat-panel", ChatPanel)
        sidebar = self.query_one("#sidebar-panel", SidebarPanel)
        chat.set_buttons_disabled(True)
        chat.append_assistant_start()

        try:
            async for chunk in self._agent.stream_response(self._session, text):
                chat.append_chunk(chunk)
                await asyncio.sleep(0)
        except Exception as e:
            chat.append_chunk(f"\n[bold red]오류: {e}[/bold red]")
        finally:
            chat.append_assistant_end()
            sidebar.update_from_session(self._session)
            chat.set_buttons_disabled(False)
            self._is_streaming = False

        # Extract command block for copy shortcut
        last_msg = self._session.messages[-1]["content"] if self._session.messages else ""
        self._last_command = self._extract_command(last_msg)

    def _extract_command(self, text: str) -> str | None:
        import re
        match = re.search(r"```(?:bash|sh|shell)?\n(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def action_new_session(self) -> None:
        self._session = Session(session_id=str(uuid.uuid4()))
        chat = self.query_one("#chat-panel", ChatPanel)
        chat.query_one("#chat-log").clear()
        chat.query_one("#chat-log").write(_WELCOME)
        sidebar = self.query_one("#sidebar-panel", SidebarPanel)
        sidebar.update_from_session(self._session)
        self._send_init_message()

    def action_copy_last_command(self) -> None:
        if self._last_command:
            try:
                import pyperclip
                pyperclip.copy(self._last_command)
                self.notify("명령어가 클립보드에 복사되었습니다.", severity="information")
            except Exception:
                self.notify(f"복사 실패: {self._last_command[:60]}", severity="warning")
        else:
            self.notify("복사할 명령어가 없습니다.", severity="warning")

    def action_export_report(self) -> None:
        session = self._session
        lines: list[str] = [
            "# 장애 보고서 — InfraDx",
            "",
            f"**세션 ID:** `{session.session_id[:8]}`  ",
            f"**생성 시간:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
            f"**도메인:** {session.domain or '미분류'}",
            "",
            "---",
            "",
            "## 시스템 정보",
        ]
        spec = session.spec
        if spec.os_type:
            lines.append(f"- OS: {spec.os_type} {spec.kernel_version or ''}")
        if spec.deployment_type:
            lines.append(f"- 배포 유형: {spec.deployment_type}")
        if spec.cloud_provider:
            lines.append(f"- Cloud: {spec.cloud_provider.upper()} / {spec.cloud_service or ''} / {spec.cloud_region or ''}")
        if spec.k8s_distribution:
            lines.append(f"- Kubernetes: {spec.k8s_distribution} {spec.k8s_version or ''} / 범위: {spec.k8s_problem_scope or ''}")

        lines += ["", "## 증상"]
        symptom = session.symptom
        if symptom.started_when:
            lines.append(f"- **발생 시각:** {symptom.started_when}")
        if symptom.reproducibility:
            lines.append(f"- **재현율:** {symptom.reproducibility}")
        if symptom.error_text:
            lines.append(f"- **에러:** {symptom.error_text}")
        if symptom.recent_changes:
            lines.append(f"- **최근 변경:** {symptom.recent_changes}")

        lines += ["", "## 가설 목록"]
        _status_label = {"validated": "✅ 확정", "invalidated": "❌ 기각", "investigating": "🔄 조사중"}
        for h in session.hypotheses:
            status = _status_label.get(h.status, "🔄 조사중")
            lines.append(f"- **[{h.confidence}]** {h.text}  ({status})")
            if h.evidence:
                lines.append(f"  - 근거: {h.evidence}")

        if session.root_cause:
            lines += ["", "## 근본 원인", "", session.root_cause]

        if session.metrics_collected:
            lines += ["", "## 수집된 메트릭"]
            for m in session.metrics_collected:
                lines.append(f"- {m}")

        content = "\n".join(lines)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_dir = Path(__file__).parent.parent.parent.parent / "result"
        result_dir.mkdir(parents=True, exist_ok=True)
        path = result_dir / f"infradx_report_{timestamp}.md"
        path.write_text(content, encoding="utf-8")
        self.notify(f"보고서 저장됨: result/{path.name}", severity="information")
