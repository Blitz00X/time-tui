"""
Main Textual application for tui-md-todo.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widgets import (
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
    Static,
)

from .models import Priority, Task
from .storage import load_tasks, save_tasks
from .ui.modal import TaskModal

# ── CSS ───────────────────────────────────────────────────────────────────────

APP_CSS = """\
/* ── Root & Layout ─────────────────────────────── */

Screen {
    background: $background;
}

#app-grid {
    layout: vertical;
    height: 1fr;
}

#summary-bar {
    height: 3;
    background: $surface;
    border-bottom: solid $primary-darken-2;
    layout: horizontal;
    align: left middle;
    padding: 0 2;
}

.stat-chip {
    margin-right: 3;
    text-style: bold;
}

.stat-count {
    color: $accent;
}

#main-split {
    layout: horizontal;
    height: 1fr;
}

#task-pane {
    width: 1fr;
    height: 1fr;
    border-right: solid $primary-darken-2;
}

#pane-title {
    background: $primary-darken-3;
    color: $text;
    text-style: bold;
    padding: 0 2;
    height: 2;
    content-align: left middle;
}

#task-list {
    height: 1fr;
    padding: 0 1;
    border: none;
    scrollbar-size: 1 1;
}

/* ── Task items ─────────────────────────────────── */

.task-item {
    height: 3;
    padding: 0 1;
    border-bottom: solid $surface-lighten-1;
}

.task-item:hover {
    background: $surface-lighten-1;
}

.task-item.--highlight {
    background: $primary-darken-2;
}

.task-checkbox {
    width: 4;
    content-align: left middle;
}

.task-text {
    width: 1fr;
    content-align: left middle;
    overflow: hidden;
}

.task-meta {
    width: 28;
    content-align: right middle;
    text-style: italic;
    color: $text-muted;
}

/* ── Priority colours ───────────────────────────── */

.priority-high   { color: $error; }
.priority-medium { color: $warning; }
.priority-low    { color: $success; }
.priority-doing  { color: $accent; }
.priority-done   {
    color: $text-muted;
    text-style: dim;
}

/* ── Detail pane ────────────────────────────────── */

#detail-pane {
    width: 36;
    height: 1fr;
    padding: 1 2;
    background: $surface-darken-1;
}

#detail-title {
    text-style: bold;
    color: $primary;
    margin-bottom: 1;
}

.detail-row {
    margin-bottom: 1;
}

.detail-label {
    color: $text-muted;
    text-style: italic;
}

.detail-value {
    text-style: bold;
}

/* ── Footer ─────────────────────────────────────── */

Footer {
    background: $surface-darken-2;
}

/* ── Empty state ────────────────────────────────── */

#empty-state {
    width: 1fr;
    height: 1fr;
    content-align: center middle;
    color: $text-muted;
    text-style: italic;
}

/* ── Filter bar ─────────────────────────────────── */

#filter-bar {
    height: 2;
    background: $surface;
    border-bottom: solid $primary-darken-2;
    layout: horizontal;
    align: left middle;
    padding: 0 2;
    display: none;
}

#filter-bar.visible {
    display: block;
}

.filter-chip {
    margin-right: 1;
    padding: 0 1;
    border: solid $primary-darken-2;
}

.filter-chip.active {
    background: $primary-darken-2;
    color: $text;
}
"""

# ── Task Row Widget ───────────────────────────────────────────────────────────

class TaskRow(Static):
    """A single row in the task list."""

    DEFAULT_CSS = """
    TaskRow {
        layout: horizontal;
        height: 3;
        padding: 0 1;
        border-bottom: solid $surface-lighten-1;
        width: 1fr;
    }
    TaskRow:hover {
        background: $surface-lighten-1;
    }
    TaskRow.-selected {
        background: $primary-darken-2 20%;
        border-left: thick $primary;
    }
    """

    def __init__(self, todo_task: Task, selected: bool = False) -> None:
        super().__init__()
        self.todo_task = todo_task  # avoid collision with Widget.task
        self._selected = selected
        if selected:
            self.add_class("-selected")

    def compose(self) -> ComposeResult:
        t = self.todo_task

        # checkbox
        checkbox = "✅" if t.done else "⬜"
        yield Static(checkbox, classes="task-checkbox")

        # text + tags
        text_class = "priority-done" if t.done else (
            "priority-doing" if t.is_doing else f"priority-{t.priority.value}"
        )
        label = t.text
        yield Static(label, classes=f"task-text {text_class}")

        # right meta: priority icon + tags
        meta_parts: list[str] = []
        if not t.done:
            meta_parts.append(t.priority.label)
        if t.tags:
            meta_parts.append(t.display_tags)
        yield Static("  ".join(meta_parts), classes="task-meta")


# ── Summary Bar ───────────────────────────────────────────────────────────────

class SummaryBar(Static):
    """Top bar showing task counts."""

    DEFAULT_CSS = """
    SummaryBar {
        height: 3;
        background: $surface;
        border-bottom: solid $primary-darken-2;
        layout: horizontal;
        align: left middle;
        padding: 0 2;
    }
    .chip {
        margin-right: 3;
    }
    """

    def __init__(self, tasks: list[Task]) -> None:
        super().__init__()
        self._tasks = tasks

    def compose(self) -> ComposeResult:
        tasks = self._tasks
        total   = len(tasks)
        done    = sum(1 for t in tasks if t.done)
        doing   = sum(1 for t in tasks if t.is_doing and not t.done)
        today   = sum(1 for t in tasks if t.is_today and not t.done)
        pending = total - done

        yield Static(f"📋 Total [bold]{total}[/]",   classes="chip")
        yield Static(f"⏳ Pending [bold cyan]{pending}[/]", classes="chip")
        yield Static(f"🔵 Doing [bold blue]{doing}[/]",     classes="chip")
        yield Static(f"📅 Today [bold yellow]{today}[/]",   classes="chip")
        yield Static(f"✅ Done [bold green]{done}[/]",      classes="chip")


# ── Detail Pane ───────────────────────────────────────────────────────────────

class DetailPane(Static):
    DEFAULT_CSS = """
    DetailPane {
        width: 36;
        height: 1fr;
        padding: 1 2;
        background: $surface-darken-1;
        border-left: solid $primary-darken-2;
    }
    """

    def __init__(self, task: "Optional[Task]") -> None:
        super().__init__()
        self._todo_task = task  # renamed to avoid shadowing asyncio.Task

    def compose(self) -> ComposeResult:
        if self._todo_task is None:
            yield Static("No task selected", id="detail-empty")
            return

        t = self._todo_task
        yield Static("── Task Details ──", id="detail-title")

        status = "✅ Done" if t.done else ("🔵 Doing" if t.is_doing else "⏳ Pending")
        yield Static(f"[italic dim]Status[/]\n{status}", classes="detail-row")

        priority_colors = {"high": "red", "medium": "yellow", "low": "green"}
        c = priority_colors.get(t.priority.value, "white")
        yield Static(
            f"[italic dim]Priority[/]\n[bold {c}]{t.priority.label} {t.priority.value.capitalize()}[/]",
            classes="detail-row",
        )

        tags_str = "  ".join(t.tags) if t.tags else "[dim]none[/]"
        yield Static(f"[italic dim]Tags[/]\n{tags_str}", classes="detail-row")

        yield Static(f"[italic dim]ID[/]\n[dim]{t.id}[/]", classes="detail-row")

        yield Static("")
        yield Static("[dim]↑↓ navigate  Enter toggle\na add  e edit  d delete\ns toggle doing  q quit[/]")


# ── Main App ──────────────────────────────────────────────────────────────────

class TodoApp(App):
    """tui-md-todo — keyboard-driven Markdown task manager."""

    CSS = APP_CSS
    TITLE = "tui-md-todo"
    SUB_TITLE = "Markdown-powered task manager"

    BINDINGS = [
        Binding("up",    "cursor_up",   "Up",          show=False),
        Binding("k",     "cursor_up",   "Up",          show=False),
        Binding("down",  "cursor_down", "Down",        show=False),
        Binding("j",     "cursor_down", "Down",        show=False),
        Binding("enter", "toggle_done", "Toggle done", show=True),
        Binding("a",     "add_task",    "Add",         show=True),
        Binding("e",     "edit_task",   "Edit",        show=True),
        Binding("d",     "delete_task", "Delete",      show=True),
        Binding("s",     "toggle_doing","Doing",       show=True),
        Binding("f",     "cycle_filter","Filter",      show=True),
        Binding("q",     "quit",        "Quit",        show=True),
    ]

    # ── reactive state ────────────────────────────────────────────────

    _cursor: reactive[int] = reactive(0, layout=True)
    _filter: reactive[str] = reactive("all", layout=True)  # all | today | doing | high

    def __init__(self, tasks_path: Path) -> None:
        super().__init__()
        self._path = tasks_path
        self._tasks: list[Task] = []

    # ── lifecycle ─────────────────────────────────────────────────────

    def on_mount(self) -> None:
        from .storage import load_tasks
        self._tasks, _ = load_tasks(self._path.parent)
        self._refresh_ui()

    # ── compose ───────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="app-grid"):
            yield SummaryBar([])  # will be refreshed on mount
            with Horizontal(id="main-split"):
                with Vertical(id="task-pane"):
                    yield Static("  📝 Tasks", id="pane-title")
                    yield ScrollableContainer(id="task-list")
                yield DetailPane(None)
        yield Footer()

    # ── refresh helpers ───────────────────────────────────────────────

    def _filtered_tasks(self) -> list[Task]:
        f = self._filter
        if f == "all":
            return list(self._tasks)
        elif f == "today":
            return [t for t in self._tasks if t.is_today and not t.done]
        elif f == "doing":
            return [t for t in self._tasks if t.is_doing and not t.done]
        elif f == "high":
            return [t for t in self._tasks if t.priority == Priority.HIGH and not t.done]
        elif f == "pending":
            return [t for t in self._tasks if not t.done]
        return list(self._tasks)

    def _selected_task(self) -> Optional[Task]:
        visible = self._filtered_tasks()
        if not visible:
            return None
        idx = max(0, min(self._cursor, len(visible) - 1))
        return visible[idx]

    def _refresh_ui(self) -> None:
        """Rebuild the task list and detail pane from current state."""
        visible = self._filtered_tasks()

        # Clamp cursor
        if visible:
            self._cursor = max(0, min(self._cursor, len(visible) - 1))

        # Rebuild summary bar
        try:
            old_bar = self.query_one(SummaryBar)
            new_bar = SummaryBar(self._tasks)
            old_bar.remove()
            app_grid = self.query_one("#app-grid")
            app_grid.mount(new_bar, before=app_grid.query_one("#main-split"))
        except NoMatches:
            pass

        # Rebuild task rows
        task_list = self.query_one("#task-list")
        task_list.remove_children()

        if not visible:
            task_list.mount(Static("No tasks here. Press [bold]a[/] to add one.", id="empty-state"))
        else:
            for i, task in enumerate(visible):
                row = TaskRow(task, selected=(i == self._cursor))
                task_list.mount(row)

        # Update pane title with filter info
        filter_labels = {
            "all": "All Tasks",
            "today": "Today's Tasks",
            "doing": "Currently Doing",
            "high": "High Priority",
            "pending": "Pending Tasks",
        }
        try:
            title = self.query_one("#pane-title", Static)
            fl = filter_labels.get(self._filter, self._filter)
            title.update(f"  📝 {fl}  [dim]({len(visible)} shown)[/]")
        except NoMatches:
            pass

        # Rebuild detail pane
        try:
            old_detail = self.query_one(DetailPane)
            new_detail = DetailPane(self._selected_task())
            old_detail.remove()
            main_split = self.query_one("#main-split")
            main_split.mount(new_detail)
        except NoMatches:
            pass

    def _persist(self) -> None:
        save_tasks(self._tasks, self._path)

    # ── actions ───────────────────────────────────────────────────────

    def action_cursor_up(self) -> None:
        visible = self._filtered_tasks()
        if visible and self._cursor > 0:
            self._cursor -= 1
            self._refresh_ui()

    def action_cursor_down(self) -> None:
        visible = self._filtered_tasks()
        if visible and self._cursor < len(visible) - 1:
            self._cursor += 1
            self._refresh_ui()

    def action_toggle_done(self) -> None:
        task = self._selected_task()
        if task is None:
            return
        task.toggle_done()
        self._persist()
        self._refresh_ui()

    def action_delete_task(self) -> None:
        task = self._selected_task()
        if task is None:
            return
        self._tasks = [t for t in self._tasks if t.id != task.id]
        self._cursor = max(0, self._cursor - 1)
        self._persist()
        self._refresh_ui()

    def action_toggle_doing(self) -> None:
        task = self._selected_task()
        if task is None:
            return
        if task.is_doing:
            task.remove_tag("@doing")
        else:
            task.add_tag("@doing")
        self._persist()
        self._refresh_ui()

    def action_cycle_filter(self) -> None:
        filters = ["all", "pending", "today", "doing", "high"]
        idx = filters.index(self._filter)
        self._filter = filters[(idx + 1) % len(filters)]
        self._cursor = 0
        self._refresh_ui()
        self.notify(f"Filter: {self._filter}", timeout=1.5)

    def action_add_task(self) -> None:
        self.push_screen(TaskModal(), callback=self._on_modal_result)

    def action_edit_task(self) -> None:
        task = self._selected_task()
        if task is None:
            return
        self.push_screen(TaskModal(todo_task=task), callback=self._on_modal_result)

    def _on_modal_result(self, result: Optional[Task]) -> None:
        if result is None:
            return  # cancelled

        # Edit in place if task with same id exists
        for i, t in enumerate(self._tasks):
            if t.id == result.id:
                self._tasks[i] = result
                self._persist()
                self._refresh_ui()
                return

        # New task — insert at beginning of its priority bucket (before done)
        self._tasks.append(result)
        self._persist()
        self._refresh_ui()
        # Move cursor to the newly added task
        visible = self._filtered_tasks()
        for i, t in enumerate(visible):
            if t.id == result.id:
                self._cursor = i
                break
        self._refresh_ui()

    def action_quit(self) -> None:
        self.exit()
