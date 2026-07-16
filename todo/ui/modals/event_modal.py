"""Modal for adding / editing calendar events."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from ...core.dashboard_io import CalendarEvent, parse_session_time_range


@dataclass(frozen=True)
class EventFormResult:
    start_hm: str
    end_hm: str
    title: str
    color: str


class EventModal(ModalScreen[Optional[EventFormResult]]):
    DEFAULT_CSS = """
    EventModal { align: center middle; }

    #event-box {
        width: 54;
        height: auto;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    #event-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    #event-hint {
        color: $text-muted;
        text-style: dim;
        margin-bottom: 1;
    }

    #event-btn-row {
        margin-top: 1;
        align: right middle;
        height: auto;
    }

    #event-btn-cancel { margin-right: 1; }
    """

    BINDINGS = [
        Binding("escape", "cancel", show=False),
        Binding("down", "focus_next_field", show=False, priority=True),
        Binding("up", "focus_prev_field", show=False, priority=True),
    ]

    _FOCUS_ORDER = (
        "event-range",
        "event-title",
        "event-color",
        "event-btn-cancel",
        "event-btn-save",
    )

    def __init__(self, event: Optional[CalendarEvent] = None) -> None:
        super().__init__()
        self._event = event

    def compose(self) -> ComposeResult:
        editing = self._event is not None
        title = "Edit Event" if editing else "Add Event"
        range_value = ""
        title_value = ""
        color_value = "green"
        if editing and self._event:
            range_value = f"{self._event.start} - {self._event.end}"
            title_value = self._event.title
            color_value = self._event.color

        with Vertical(id="event-box"):
            yield Static(title, id="event-title")
            yield Static("Time: HH:MM - HH:MM", id="event-hint")
            yield Label("Time")
            yield Input(value=range_value, placeholder="09:00 - 10:30", id="event-range")
            yield Label("Title")
            yield Input(value=title_value, placeholder="Team standup", id="event-title-input")
            yield Label("Color (green, blue, yellow, purple)")
            yield Input(value=color_value, placeholder="green", id="event-color")
            with Horizontal(id="event-btn-row"):
                yield Button("Cancel", variant="default", id="event-btn-cancel")
                yield Button("Save", variant="primary", id="event-btn-save")

    def on_mount(self) -> None:
        self.query_one("#event-range", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_focus_next_field(self) -> None:
        self._move_focus(1)

    def action_focus_prev_field(self) -> None:
        self._move_focus(-1)

    def _move_focus(self, step: int) -> None:
        current_id = self.focused.id if self.focused else self._FOCUS_ORDER[0]
        if current_id == "event-title-input":
            current_id = "event-title"
        try:
            index = self._FOCUS_ORDER.index(current_id)
        except ValueError:
            index = 0
        next_index = max(0, min(len(self._FOCUS_ORDER) - 1, index + step))
        field_id = self._FOCUS_ORDER[next_index]
        if field_id == "event-title":
            field_id = "event-title-input"
        self.query_one(f"#{field_id}").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "event-btn-cancel":
            self.dismiss(None)
        elif event.button.id == "event-btn-save":
            self._submit()

    def on_input_submitted(self) -> None:
        self._submit()

    def _submit(self) -> None:
        raw_range = self.query_one("#event-range", Input).value.strip()
        if not raw_range:
            self.query_one("#event-range", Input).focus()
            return
        try:
            start_hm, end_hm = parse_session_time_range(raw_range)
        except ValueError as exc:
            self.notify(str(exc))
            self.query_one("#event-range", Input).focus()
            return
        title = self.query_one("#event-title-input", Input).value.strip()
        if not title:
            self.notify("Title is required")
            self.query_one("#event-title-input", Input).focus()
            return
        color = self.query_one("#event-color", Input).value.strip().lower() or "green"
        if color not in {"green", "blue", "yellow", "purple"}:
            self.notify("Color must be green, blue, yellow, or purple")
            self.query_one("#event-color", Input).focus()
            return
        self.dismiss(
            EventFormResult(start_hm=start_hm, end_hm=end_hm, title=title, color=color),
        )
