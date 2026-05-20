from __future__ import annotations

import asyncio
import uuid
from typing import AsyncIterator

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input
from textual.containers import Horizontal
from textual import on, work

from infradx.state.session import Session
from infradx.agent.core import AgentCore
from infradx.tui.widgets.chat import ChatPanel
from infradx.tui.widgets.sidebar import SidebarPanel


_WELCOME = """\
[bold green]InfraDx[/bold green] — AI 인프라 트러블슈팅 도구

서버, 네트워크, 디스크 장애를 단계별로 진단합니다.
Ctrl+Q 또는 Ctrl+C 로 종료합니다.
───────────────────────────────────────────────────
"""

_INIT_MESSAGE = "안녕하세요! 어떤 문제가 발생했나요? 서버, 네트워크, 디스크 중 어떤 영역인지 알려주시거나 증상을 자유롭게 설명해 주세요."


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
            self._send_init_message()
        except RuntimeError as e:
            chat.query_one("#chat-log").write(
                f"[bold red]오류:[/bold red] {e}\n"
                "[yellow]ANTHROPIC_API_KEY 환경변수를 설정해 주세요.[/yellow]"
            )

        chat.focus_input()

    @work(exclusive=True)
    async def _send_init_message(self) -> None:
        await self._stream_agent_response(_INIT_MESSAGE, inject=True)

    @on(Input.Submitted, "#chat-input")
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text or self._is_streaming:
            return

        chat = self.query_one("#chat-panel", ChatPanel)
        chat.clear_input()
        chat.append_user(text)

        self._handle_user_message(text)

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
