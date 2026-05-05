"""
Modal dialog for adding / editing tasks.
"""
from __future__ import annotations
from typing import Optional
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static
from ..models import Priority, Task


class TaskModal(ModalScreen[Optional[Task]]):
    """Centered modal for creating or editing a task."""

    DEFAULT_CSS = """
    TaskModal {
        align: center middle;
    }

    #modal-container {
        width: 64;
        height: auto;
        min-height: 24;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #modal-title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 1;
    }

    .field-label {
        margin-top: 1;
        color: $text-muted;
        text-style: italic;
    }

    Input {
        margin-top: 0;
    }

    RadioSet {
        margin-top: 0;
        border: none;
        height: auto;
        padding: 0;
    }

    RadioSet > RadioButton {
        margin: 0 1 0 0;
    }

    #tags-hint {
        color: $text-muted;
        margin-top: 0;
    }

    #button-row {
        margin-top: 2;
        align: right middle;
        height: auto;
    }

    #btn-cancel {
        margin-right: 1;
    }

    Button {
        min-width: 10;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, todo_task: Optional[Task] = None) -> None:
        super().__init__()
        self._todo_task = todo_task  # None → new task, Task → edit existing

    def compose(self) -> ComposeResult:
        editing = self._todo_task is not None
        title = "✏️  Edit Task" if editing else "➕  New Task"

        with Container(id="modal-container"):
            yield Static(title, id="modal-title")

            yield Label("Task text", classes="field-label")
            yield Input(
                value=self._todo_task.text if editing else "",
                placeholder="What needs to be done?",
                id="task-text",
            )

            yield Label("Priority", classes="field-label")
            current_priority = self._todo_task.priority.value if editing else "medium"
            with RadioSet(id="priority-set"):
                yield RadioButton(" High",   value="high",   id="prio-high",   classes="prio-radio")
                yield RadioButton(" Medium", value="medium", id="prio-medium", classes="prio-radio")
                yield RadioButton(" Low",    value="low",    id="prio-low",    classes="prio-radio")

            yield Label("Tags", classes="field-label")
            current_tags = " ".join(self._todo_task.tags) if editing and self._todo_task.tags else ""
            yield Input(
                value=current_tags,
                placeholder="@today @doing (space-separated)",
                id="task-tags",
            )
            yield Static("Space-separated, e.g. @today @doing", id="tags-hint")

            with Horizontal(id="button-row"):
                yield Button("Cancel", variant="default", id="btn-cancel")
                yield Button("Save", variant="primary", id="btn-save")

    def on_mount(self) -> None:
        # Pre-select the current priority
        current = self._todo_task.priority.value if self._todo_task else "medium"
        radio_set = self.query_one(RadioSet)
        for btn in radio_set.query(RadioButton):
            if btn.id == f"prio-{current}":
                btn.value = True
                break
        self.query_one("#task-text", Input).focus()

    # ── button handlers ───────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#btn-save")
    def _on_save(self) -> None:
        self._submit()

    @on(Input.Submitted)
    def _on_input_submitted(self) -> None:
        self._submit()

    def _submit(self) -> None:
        text_input = self.query_one("#task-text", Input).value.strip()
        if not text_input:
            self.query_one("#task-text", Input).focus()
            self.query_one("#task-text", Input).add_class("error")
            return

        # Determine selected priority
        radio_set = self.query_one(RadioSet)
        priority = Priority.MEDIUM
        for btn in radio_set.query(RadioButton):
            if btn.value:
                try:
                    priority = Priority(btn.id.replace("prio-", ""))
                except (ValueError, AttributeError):
                    pass
                break

        # Parse tags
        raw_tags = self.query_one("#task-tags", Input).value.strip()
        tags: list[str] = []
        for token in raw_tags.split():
            token = token.strip()
            if token:
                if not token.startswith("@"):
                    token = f"@{token}"
                tags.append(token)

        if self._todo_task is not None:
            # Edit in place
            task = self._todo_task.clone()
            task.text = text_input
            task.priority = priority
            task.tags = tags
        else:
            from ..models import Task as T
            task = T(text=text_input, priority=priority, tags=tags)

        self.dismiss(task)
