from __future__ import annotations

from rich.markdown import Markdown

from textual import events
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import RichLog, Button, TextArea, Static
from textual.containers import Vertical, Horizontal


class _ChatInput(TextArea):
    """Multi-line input: Enter submits, Shift+Enter inserts newline."""

    class Submitted(Message):
        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    def on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            text = self.text.strip()
            if text:
                self.post_message(self.Submitted(text))
                self.clear()
            event.prevent_default()
        # shift+enter → TextArea default (inserts newline)


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

    ChatPanel #typing-indicator {
        height: 1;
        padding: 0 1;
        color: $text-muted;
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

    ChatPanel _ChatInput {
        height: 5;
        margin: 0 1 1 1;
        border: tall $primary;
    }

    ChatPanel _ChatInput:focus {
        border: tall $accent;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._full_buffer: str = ""

    def compose(self) -> ComposeResult:
        yield RichLog(id="chat-log", markup=True, wrap=True, highlight=True)
        yield Static("", id="typing-indicator", markup=True)
        with Horizontal(id="action-bar"):
            yield Button("📊 메트릭 분석", id="btn-metrics", variant="default")
            yield Button("🔍 가설 업데이트", id="btn-hypothesize", variant="default")
            yield Button("📋 결론 도출", id="btn-conclude", variant="success")
        yield _ChatInput(
            id="chat-input",
            language=None,
            show_line_numbers=False,
        )

    def on_mount(self) -> None:
        self.query_one("#chat-input", _ChatInput).placeholder = (
            "메시지를 입력하세요 (Enter 전송 / Shift+Enter 줄바꿈)"
        )

    def append_user(self, text: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold cyan]You:[/bold cyan] {text}")

    def append_assistant_start(self) -> None:
        self._full_buffer = ""
        indicator = self.query_one("#typing-indicator", Static)
        indicator.update("[dim]InfraDx: ▍ 작성 중...[/dim]")
        indicator.display = True

    def append_chunk(self, chunk: str) -> None:
        self._full_buffer += chunk

    def append_assistant_end(self) -> None:
        indicator = self.query_one("#typing-indicator", Static)
        indicator.display = False
        indicator.update("")

        log = self.query_one("#chat-log", RichLog)
        if self._full_buffer:
            log.write("[bold green]InfraDx:[/bold green]")
            log.write(Markdown(self._full_buffer))
        log.write("")
        self._full_buffer = ""

    def clear_input(self) -> None:
        self.query_one("#chat-input", _ChatInput).clear()

    def focus_input(self) -> None:
        self.query_one("#chat-input", _ChatInput).focus()

    def set_buttons_disabled(self, disabled: bool) -> None:
        for btn_id in ("btn-metrics", "btn-hypothesize", "btn-conclude"):
            self.query_one(f"#{btn_id}", Button).disabled = disabled
