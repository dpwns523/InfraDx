from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import RichLog, Input
from textual.containers import Vertical
from textual import on


class ChatPanel(Widget):
    """Left panel: conversation history + input."""

    DEFAULT_CSS = """
    ChatPanel {
        width: 2fr;
        height: 100%;
        border: solid $primary;
    }

    ChatPanel RichLog {
        height: 1fr;
        padding: 0 1;
        scrollbar-gutter: stable;
    }

    ChatPanel Input {
        dock: bottom;
        margin: 0 1 1 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield RichLog(id="chat-log", markup=True, wrap=True, highlight=True)
            yield Input(placeholder="메시지를 입력하세요 (Enter로 전송)...", id="chat-input")

    def append_user(self, text: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold cyan]You:[/bold cyan] {text}")

    def append_assistant_start(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write("[bold green]InfraDx:[/bold green] ", end="")

    def append_chunk(self, chunk: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(chunk, end="", animate=False)

    def append_assistant_end(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write("")

    def clear_input(self) -> None:
        self.query_one("#chat-input", Input).value = ""

    def focus_input(self) -> None:
        self.query_one("#chat-input", Input).focus()
