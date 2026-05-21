from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import RichLog, Input, Button
from textual.containers import Vertical, Horizontal
from textual import on


class ChatPanel(Widget):
    """Left panel: conversation history + action buttons + input."""

    DEFAULT_CSS = """
    ChatPanel {
        width: 2fr;
        height: 100%;
        border: solid $primary;
        layout: vertical;
    }

    ChatPanel RichLog {
        height: 1fr;
        padding: 0 1;
        scrollbar-gutter: stable;
    }

    ChatPanel #action-bar {
        height: 3;
        padding: 0 1;
    }

    ChatPanel #action-bar Button {
        width: 1fr;
        height: 3;
        margin: 0 0 0 1;
    }

    ChatPanel #action-bar Button:first-of-type {
        margin-left: 0;
    }

    ChatPanel Input {
        margin: 0 1 1 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._stream_buffer: str = ""
        self._streaming_started: bool = False

    def compose(self) -> ComposeResult:
        yield RichLog(id="chat-log", markup=True, wrap=True, highlight=True)
        with Horizontal(id="action-bar"):
            yield Button("📊 메트릭 분석", id="btn-metrics", variant="default")
            yield Button("🔍 가설 업데이트", id="btn-hypothesize", variant="default")
            yield Button("📋 결론 도출", id="btn-conclude", variant="success")
        yield Input(placeholder="메시지를 입력하세요 (Enter로 전송)...", id="chat-input")

    def append_user(self, text: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold cyan]You:[/bold cyan] {text}")

    def append_assistant_start(self) -> None:
        self._stream_buffer = ""
        self._streaming_started = False

    def append_chunk(self, chunk: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        self._stream_buffer += chunk
        lines = self._stream_buffer.split("\n")
        # Flush all complete lines immediately
        for line in lines[:-1]:
            prefix = "[bold green]InfraDx:[/bold green] " if not self._streaming_started else ""
            self._streaming_started = True
            log.write(prefix + line)
        self._stream_buffer = lines[-1]

    def append_assistant_end(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        # Flush remaining buffer
        if self._stream_buffer:
            prefix = "[bold green]InfraDx:[/bold green] " if not self._streaming_started else ""
            log.write(prefix + self._stream_buffer)
            self._stream_buffer = ""
            self._streaming_started = False
        log.write("")  # blank separator

    def clear_input(self) -> None:
        self.query_one("#chat-input", Input).value = ""

    def focus_input(self) -> None:
        self.query_one("#chat-input", Input).focus()

    def set_buttons_disabled(self, disabled: bool) -> None:
        for btn_id in ("btn-metrics", "btn-hypothesize", "btn-conclude"):
            self.query_one(f"#{btn_id}", Button).disabled = disabled
