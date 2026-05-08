"""
Modal for creating a new namespace (project directory).
"""
from __future__ import annotations
from typing import Optional
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class NewNamespaceModal(ModalScreen[Optional[str]]):
    """Ask for a namespace name; returns the name or None on cancel."""

    DEFAULT_CSS = """
    NewNamespaceModal { align: center middle; }

    #ns-box {
        width: 50;
        height: auto;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    #ns-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    #ns-hint {
        color: $text-muted;
        text-style: dim;
        margin-bottom: 1;
    }

    #ns-btn-row {
        margin-top: 1;
        align: right middle;
        height: auto;
    }

    #ns-btn-cancel { margin-right: 1; }
    """

    BINDINGS = [Binding("escape", "cancel", show=False)]

    def compose(self) -> ComposeResult:
        with Vertical(id="ns-box"):
            yield Static("  New Namespace", id="ns-title")
            yield Static(
                "A namespace is a named project folder.\n"
                "Each namespace has its own tasks.md.\n"
                "e.g.  login  signup  homepage",
                id="ns-hint",
            )
            yield Label("Name")
            yield Input(placeholder="my-project", id="ns-name")
            with Horizontal(id="ns-btn-row"):
                yield Button("Cancel", variant="default",  id="ns-btn-cancel")
                yield Button("Create", variant="primary",  id="ns-btn-create")

    def on_mount(self) -> None:
        self.query_one("#ns-name", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ns-btn-cancel":
            self.dismiss(None)
        elif event.button.id == "ns-btn-create":
            self._submit()

    def on_input_submitted(self) -> None:
        self._submit()

    def _submit(self) -> None:
        raw = self.query_one("#ns-name", Input).value.strip()
        # sanitise: allow letters, digits, dash, underscore
        import re
        name = re.sub(r"[^\w\-]", "-", raw).strip("-")
        if not name:
            return
        self.dismiss(name)
