"""Generic Yes/No confirmation modal."""
from __future__ import annotations
from typing import Optional
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmModal(ModalScreen[Optional[str]]):
    """Centered yes/no dialog. Dismisses with 'yes' or 'no'."""

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }

    #confirm-box {
        width: 50;
        height: auto;
        background: $surface;
        border: thick $warning;
        padding: 1 2;
    }

    #confirm-prompt {
        text-align: center;
        margin-bottom: 1;
    }

    #confirm-btn-row {
        align: right middle;
        height: auto;
    }

    #confirm-btn-no { margin-right: 1; }
    """

    BINDINGS = [
        Binding("escape", "answer_no", "No", show=False),
        Binding("y", "answer_yes", show=False),
        Binding("n", "answer_no", show=False),
    ]

    def __init__(self, prompt: str) -> None:
        super().__init__()
        self._prompt = prompt

    def compose(self) -> ComposeResult:
        with Container(id="confirm-box"):
            yield Static(self._prompt, id="confirm-prompt")
            with Horizontal(id="confirm-btn-row"):
                yield Button("No", variant="default", id="confirm-btn-no")
                yield Button("Yes", variant="warning", id="confirm-btn-yes")

    def on_mount(self) -> None:
        self.query_one("#confirm-btn-no", Button).focus()

    def action_answer_yes(self) -> None:
        self.dismiss("yes")

    def action_answer_no(self) -> None:
        self.dismiss("no")

    @on(Button.Pressed, "#confirm-btn-yes")
    def _on_yes(self) -> None:
        self.dismiss("yes")

    @on(Button.Pressed, "#confirm-btn-no")
    def _on_no(self) -> None:
        self.dismiss("no")