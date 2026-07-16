"""Modal for adding / editing tracker session log entries."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from ...core.dashboard_io import parse_session_time_range


@dataclass(frozen=True)
class SessionFormResult:
    start_hm: str
    end_hm: str
    label: str


class SessionModal(ModalScreen[Optional[SessionFormResult]]):
    DEFAULT_CSS = """
    SessionModal { align: center middle; }

    #session-box {
        width: 54;
        height: auto;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    #session-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    #session-hint {
        color: $text-muted;
        text-style: dim;
        margin-bottom: 1;
    }

    #session-btn-row {
        margin-top: 1;
        align: right middle;
        height: auto;
    }

    #session-btn-cancel { margin-right: 1; }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("down", "focus_next_field", show=False, priority=True),
        Binding("up", "focus_prev_field", show=False, priority=True),
    ]

    _FOCUS_ORDER = ("session-range", "session-label", "session-btn-cancel", "session-btn-save")

    def __init__(self, session: Optional[dict] = None) -> None:
        super().__init__()
        self._session = session

    def compose(self) -> ComposeResult:
        editing = self._session is not None
        title = "Edit Session" if editing else "Add Session"
        range_value = ""
        label_value = ""
        if editing and self._session:
            try:
                from datetime import datetime

                st = datetime.fromisoformat(self._session["started"])
                et = datetime.fromisoformat(self._session["ended"])
                range_value = f"{st.strftime('%H:%M')} - {et.strftime('%H:%M')}"
                label_value = self._session.get("label", "")
            except Exception:
                pass

        with Vertical(id="session-box"):
            yield Static(title, id="session-title")
            yield Static("Time range: HH:MM - HH:MM (today)", id="session-hint")
            yield Label("Time")
            yield Input(
                value=range_value,
                placeholder="09:00 - 10:30",
                id="session-range",
            )
            yield Label("Label")
            yield Input(
                value=label_value,
                placeholder="focus",
                id="session-label",
            )
            with Horizontal(id="session-btn-row"):
                yield Button("Cancel", variant="default", id="session-btn-cancel")
                yield Button("Save", variant="primary", id="session-btn-save")

    def on_mount(self) -> None:
        self.query_one("#session-range", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_focus_next_field(self) -> None:
        self._move_focus(1)

    def action_focus_prev_field(self) -> None:
        self._move_focus(-1)

    def _move_focus(self, step: int) -> None:
        current_id = self.focused.id if self.focused else self._FOCUS_ORDER[0]
        try:
            index = self._FOCUS_ORDER.index(current_id)
        except ValueError:
            index = 0
        next_index = max(0, min(len(self._FOCUS_ORDER) - 1, index + step))
        self.query_one(f"#{self._FOCUS_ORDER[next_index]}").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "session-btn-cancel":
            self.dismiss(None)
        elif event.button.id == "session-btn-save":
            self._submit()

    def on_input_submitted(self) -> None:
        self._submit()

    def _submit(self) -> None:
        raw_range = self.query_one("#session-range", Input).value.strip()
        if not raw_range:
            self.query_one("#session-range", Input).focus()
            return
        try:
            start_hm, end_hm = parse_session_time_range(raw_range)
        except ValueError as exc:
            self.notify(str(exc))
            self.query_one("#session-range", Input).focus()
            return
        label = self.query_one("#session-label", Input).value.strip()
        self.dismiss(SessionFormResult(start_hm=start_hm, end_hm=end_hm, label=label))
