"""
tui-md-todo  —  main Textual application  (v3)

Layout
──────
 breadcrumb (1 line)
 ┌─ sidebar ─┬─ task list ─────────────────────────────┐
 │ namespaces│ tasks                                    │
 └───────────┴──────────────────────────────────────────┘
 statusline  (1 line)

Keys
────
  ↑ k   cursor up          (context-aware: tasks or sidebar)
  ↓ j   cursor down
  backslash  toggle sidebar focus (never intercepted by Textual)
  enter toggle done
  a     add task
  e     edit task
  d     delete task
  s     start pomodoro timer for selected task
  f     cycle filter
  N     create namespace
  X     delete current namespace
  q     quit
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.color import Color
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.renderables.blank import Blank
from textual.widgets import Static

from ..core.models import Priority, Task
from ..core.storage import (
    init_if_missing, load_tasks, save_tasks,
    list_namespaces, create_namespace, namespace_path,
    root_tasks_path, delete_namespace,
)
from .modals.modal import TaskModal
from .modals.ns_modal import NewNamespaceModal
from .pomodoro import PomodoroScreen


# ── CSS ───────────────────────────────────────────────────────────────────────

APP_CSS = """\
Screen { background: $background; }

/* breadcrumb */
#breadcrumb {
    height: 1;
    background: $surface-darken-2;
    color: $text-muted;
    padding: 0 1;
    content-align: left middle;
}

/* body */
#body { layout: horizontal; height: 1fr; }

/* sidebar */
#sidebar {
    width: 22;
    height: 1fr;
    background: $surface-darken-1;
    border-right: solid $primary-darken-3;
}
#sidebar-title {
    height: 1;
    background: $surface-darken-2;
    color: $text-muted;
    padding: 0 1;
    content-align: left middle;
}
#sidebar-title.-focused { color: $primary; background: $primary-darken-3; }

NsRow { height: 1; padding: 0 1; layout: horizontal; width: 1fr; }
NsRow:hover { background: $surface-lighten-1; }
NsRow.-active { background: $primary-darken-2 30%; }
NsRow.-active .ns-icon { color: $primary; }
NsRow.-cursor { background: $primary-darken-3 60%; }

.ns-icon  { width: 3; content-align: left middle; }
.ns-label { width: 1fr; content-align: left middle; overflow: hidden; }
.ns-count { width: 4; content-align: right middle; color: $text-muted; }

/* task pane */
#task-pane { width: 1fr; height: 1fr; layout: vertical; }
#pane-title {
    height: 1;
    background: $surface-darken-2;
    color: $text-muted;
    padding: 0 1;
    content-align: left middle;
}
#task-list {
    height: 1fr;
    padding: 0;
    scrollbar-size: 1 1;
}

/* task rows */
TaskRow { layout: horizontal; height: 1; padding: 0 1; width: 1fr; }
TaskRow:hover { background: $surface-lighten-1; }
TaskRow.-selected { background: $primary-darken-2 30%; }
TaskRow.-selected .task-text { color: $text; }

.task-cb   { width: 3; content-align: left middle; color: $text-muted; }
.task-pri  { width: 2; content-align: left middle; }
.task-text { width: 1fr; content-align: left middle; overflow: hidden; }
.task-tags { width: 18; content-align: right middle; color: $text-muted; }

/* priority */
.pri-high   { color: $error; }
.pri-medium { color: $warning; }
.pri-low    { color: $success; }
.pri-doing  { color: $accent; }
.pri-done   { color: $text-muted; text-style: dim; }

/* statusline */
#statusline {
    height: 1;
    background: $surface-darken-2;
    color: $text-muted;
    padding: 0 1;
    content-align: left middle;
}

/* empty */
#empty-state {
    height: 3;
    content-align: center middle;
    color: $text-muted;
    text-style: dim;
}
"""

_STATUS = (
    "[yellow]↑↓[/] nav  "
    "[yellow]enter[/] done  "
    "[yellow]a[/] add  "
    "[yellow]e[/] edit  "
    "[yellow]d[/] del  "
    "[yellow]s[/] pomodoro  "
    "[yellow]f[/] filter  "
    "[yellow]⧵[/] sidebar  "
    "[yellow]N[/] namespace  "
    "[yellow]q[/] quit "
    "[yellow]X[/] delete namespace"
)

_PRI_SYM = {"high": "!", "medium": "~", "low": "·"}


# ── Widgets ───────────────────────────────────────────────────────────────────

class NsRow(Static):
    def __init__(self, name: str, count: int, active: bool, cursor: bool) -> None:
        super().__init__()
        self._ns_name = name
        if active:  self.add_class("-active")
        if cursor:  self.add_class("-cursor")

    def compose(self) -> ComposeResult:
        icon = "▸" if "-active" in self.classes else " "
        yield Static(icon,          classes="ns-icon")
        yield Static(self._ns_name, classes="ns-label")
        yield Static("",            classes="ns-count")

    def refresh_ns(self, name: str, count: int, active: bool, cursor: bool) -> None:
        self._ns_name = name
        self.set_class(active, "-active")
        self.set_class(cursor, "-cursor")
        kids = list(self.query(Static))
        if len(kids) < 3: return
        kids[0].update("▸" if active else " ")
        kids[1].update(name)
        kids[2].update(str(count) if count else "")


class TaskRow(Static):
    def __init__(self, todo_task: Task, selected: bool = False) -> None:
        super().__init__()
        self.todo_task = todo_task
        if selected: self.add_class("-selected")

    def _tcls(self, t: Task) -> str:
        if t.done:     return "pri-done"
        if t.is_doing: return "pri-doing"
        return f"pri-{t.priority.value}"

    def compose(self) -> ComposeResult:
        t = self.todo_task
        yield Static("[x]" if t.done else "[ ]",      classes="task-cb")
        yield Static(_PRI_SYM[t.priority.value],       classes=f"task-pri {self._tcls(t)}")
        yield Static(t.text,                           classes=f"task-text {self._tcls(t)}")
        yield Static(t.display_tags if t.tags else "", classes="task-tags")

    def refresh_from(self, todo_task: Task, selected: bool) -> None:
        self.todo_task = todo_task
        self.set_class(selected, "-selected")
        kids = list(self.query(Static))
        if len(kids) < 4: return
        t = todo_task
        kids[0].update("[x]" if t.done else "[ ]")
        kids[1].update(_PRI_SYM[t.priority.value])
        kids[1].set_classes(f"task-pri {self._tcls(t)}")
        kids[2].update(t.text)
        kids[2].set_classes(f"task-text {self._tcls(t)}")
        kids[3].update(t.display_tags if t.tags else "")


# ── App ───────────────────────────────────────────────────────────────────────

class TodoApp(App):
    CSS   = APP_CSS
    TITLE = "todo"

    # Use backslash key for sidebar toggle — never intercepted by Textual
    BINDINGS = [
        Binding("up",           "cursor_up",     show=False),
        Binding("k",            "cursor_up",     show=False),
        Binding("down",         "cursor_down",   show=False),
        Binding("j",            "cursor_down",   show=False),
        Binding("backslash",    "toggle_sidebar","Sidebar", show=False),
        Binding("enter",        "toggle_done",   show=False),
        Binding("a",            "add_task",      show=False),
        Binding("e",            "edit_task",     show=False),
        Binding("d",            "delete_task",   show=False),
        Binding("s",            "start_pomo",    show=False),
        Binding("f",            "cycle_filter",  show=False),
        Binding("N",            "new_namespace", show=False),
        Binding("X",            "del_namespace", show=False),
        Binding("q",            "quit",          show=False),
    ]

    # Fix: return proper Blank so Textual can render this screen as background
    # when PomodoroScreen / modals are on top.
    def render(self) -> Blank:
        return Blank(self.styles.background)

    def __init__(self, root: Path) -> None:
        super().__init__()
        self._root       = root
        self._tasks:     list[Task] = []
        self._cursor     = 0
        self._filter     = "all"
        self._sidebar    = False          # False = task focus, True = sidebar focus
        self._ns_list:   list[str] = []
        self._ns_cursor  = 0
        self._active_ns  = "root"

    # ── lifecycle ─────────────────────────────────────────────────────

    def on_mount(self) -> None:
        # Remove Textual's built-in Tab focus cycling so it doesn't fight us
        self.app.set_focus(None)
        self._reload_ns()
        self._load_ns()
        self._sync_all()

    def compose(self) -> ComposeResult:
        yield Static("", id="breadcrumb")
        with Horizontal(id="body"):
            with Vertical(id="sidebar"):
                yield Static("  namespaces", id="sidebar-title")
                yield ScrollableContainer(id="ns-list")
            with Vertical(id="task-pane"):
                yield Static("", id="pane-title")
                yield ScrollableContainer(id="task-list")
        yield Static("", id="statusline")

    # ── namespace helpers ─────────────────────────────────────────────

    def _reload_ns(self) -> None:
        names = list_namespaces(self._root)
        self._ns_list = ["root"] + names
        self._ns_cursor = min(self._ns_cursor, len(self._ns_list) - 1)
        if self._active_ns not in self._ns_list:
            self._active_ns = "root"
            self._ns_cursor = 0

    def _tasks_path_for(self, ns: str) -> Path:
        return namespace_path(self._root, ns)

    def _load_ns(self) -> None:
        self._tasks  = load_tasks(self._tasks_path_for(self._active_ns))
        self._cursor = 0
        self._filter = "all"

    def _persist(self) -> None:
        save_tasks(self._tasks, self._tasks_path_for(self._active_ns))

    def _ns_count(self, ns: str) -> int:
        p = self._tasks_path_for(ns)
        if not p.exists(): return 0
        try:   return sum(1 for t in load_tasks(p) if not t.done)
        except: return 0

    # ── filtered tasks ────────────────────────────────────────────────

    def _filtered(self) -> list[Task]:
        f, a = self._filter, self._tasks
        if f == "all":     return list(a)
        if f == "pending": return [t for t in a if not t.done]
        if f == "today":   return [t for t in a if t.is_today  and not t.done]
        if f == "doing":   return [t for t in a if t.is_doing  and not t.done]
        if f == "high":    return [t for t in a if t.priority == Priority.HIGH and not t.done]
        return list(a)

    def _selected(self) -> Optional[Task]:
        vis = self._filtered()
        if not vis: return None
        return vis[max(0, min(self._cursor, len(vis) - 1))]

    # ── sync ─────────────────────────────────────────────────────────

    def _sync_breadcrumb(self) -> None:
        ns = f"[bold]{self._active_ns}[/]" if self._active_ns != "root" else "root"
        fi = f" [{self._filter}]" if self._filter != "all" else ""
        self.query_one("#breadcrumb", Static).update(f" todo / {ns}{fi}")

    def _sync_sidebar(self) -> None:
        container = self.query_one("#ns-list", ScrollableContainer)
        existing  = list(container.query(NsRow))
        entries   = self._ns_list

        if len(existing) == len(entries):
            for i, (row, ns) in enumerate(zip(existing, entries)):
                row.refresh_ns(ns, self._ns_count(ns),
                               active=(ns == self._active_ns),
                               cursor=(self._sidebar and i == self._ns_cursor))
        else:
            container.remove_children()
            for i, ns in enumerate(entries):
                container.mount(NsRow(ns, self._ns_count(ns),
                                      active=(ns == self._active_ns),
                                      cursor=(self._sidebar and i == self._ns_cursor)))

        title = self.query_one("#sidebar-title", Static)
        title.set_class(self._sidebar, "-focused")
        title.update("  namespaces [bold]◀[/]" if self._sidebar else "  namespaces")

    def _sync_list(self) -> None:
        visible   = self._filtered()
        container = self.query_one("#task-list", ScrollableContainer)
        existing  = list(container.query(TaskRow))

        if len(existing) == len(visible):
            for i, (row, t) in enumerate(zip(existing, visible)):
                row.refresh_from(t, selected=(i == self._cursor))
        else:
            container.remove_children()
            if not visible:
                container.mount(Static(
                    "  (empty)  press [bold]a[/] to add a task",
                    id="empty-state",
                ))
            else:
                for i, t in enumerate(visible):
                    container.mount(TaskRow(t, selected=(i == self._cursor)))

        fl = {"all":"all","pending":"pending","today":"today","doing":"doing","high":"high"}
        self.query_one("#pane-title", Static).update(
            f"  tasks [{fl.get(self._filter,'all')}]  [dim]{len(visible)} shown[/]"
        )

    def _sync_status(self) -> None:
        t = self._selected()
        sel = ""
        if t:
            mark = (
    "[dim]✓[/]" if t.done else
    (
       
        "[red]○[/]" if t.priority == Priority.HIGH else
        "[yellow]○[/]" if t.priority == Priority.MEDIUM else
        "[green]○[/]"
    )
)
           
            sel  = f"   {mark} {t.text[:50]}"
        self.query_one("#statusline", Static).update(_STATUS + sel)

    def _sync_all(self) -> None:
        vis = self._filtered()
        self._cursor = max(0, min(self._cursor, len(vis) - 1)) if vis else 0
        self._sync_breadcrumb()
        self._sync_sidebar()
        self._sync_list()
        self._sync_status()

    # ── actions ───────────────────────────────────────────────────────

    def action_toggle_sidebar(self) -> None:
        self._sidebar = not self._sidebar
        # sync ns_cursor to active ns when entering sidebar
        if self._sidebar:
            try: self._ns_cursor = self._ns_list.index(self._active_ns)
            except ValueError: self._ns_cursor = 0
        self._sync_sidebar()
        self._sync_status()

    def action_cursor_up(self) -> None:
        if self._sidebar:
            if self._ns_cursor > 0:
                self._ns_cursor -= 1
                self._active_ns = self._ns_list[self._ns_cursor]
                self._load_ns()
                self._sync_all()
        else:
            if self._cursor > 0:
                self._cursor -= 1
                self._sync_list()
                self._sync_status()

    def action_cursor_down(self) -> None:
        if self._sidebar:
            if self._ns_cursor < len(self._ns_list) - 1:
                self._ns_cursor += 1
                self._active_ns = self._ns_list[self._ns_cursor]
                self._load_ns()
                self._sync_all()
        else:
            if self._cursor < len(self._filtered()) - 1:
                self._cursor += 1
                self._sync_list()
                self._sync_status()

    def action_toggle_done(self) -> None:
        t = self._selected()
        if not t: return
        t.toggle_done()
        self._persist()
        self._sync_all()

    def action_delete_task(self) -> None:
        t = self._selected()
        if not t: return
        self._tasks = [x for x in self._tasks if x.id != t.id]
        self._cursor = max(0, self._cursor - 1)
        self._persist()
        self._sync_all()

    def action_start_pomo(self) -> None:
        t = self._selected()
        self.push_screen(PomodoroScreen(task_name=t.text if t else ""))

    def action_cycle_filter(self) -> None:
        filters = ["all","pending","today","doing","high"]
        self._filter = filters[(filters.index(self._filter) + 1) % len(filters)]
        self._cursor = 0
        self._sync_all()
        self.notify(f"filter: {self._filter}", timeout=1)

    def action_add_task(self) -> None:
        self.push_screen(TaskModal(), callback=self._on_modal)

    def action_edit_task(self) -> None:
        t = self._selected()
        if not t: return
        self.push_screen(TaskModal(todo_task=t), callback=self._on_modal)

    def _on_modal(self, result: Optional[Task]) -> None:
        if not result: return
        for i, t in enumerate(self._tasks):
            if t.id == result.id:
                self._tasks[i] = result
                self._persist(); self._sync_all(); return
        self._tasks.append(result)
        self._persist()
        vis = self._filtered()
        for i, t in enumerate(vis):
            if t.id == result.id:
                self._cursor = i; break
        self._sync_all()

    def action_new_namespace(self) -> None:
        self.push_screen(NewNamespaceModal(), callback=self._on_new_ns)

    def _on_new_ns(self, name: Optional[str]) -> None:
        if not name: return
        create_namespace(self._root, name)
        self._reload_ns()
        self._active_ns = name
        self._ns_cursor = self._ns_list.index(name)
        self._load_ns()
        self._sync_all()
        self.notify(f"namespace '{name}' created", timeout=2)

    def action_del_namespace(self) -> None:
        if self._active_ns == "root":
            self.notify("cannot delete root", timeout=2); return
        delete_namespace(self._root, self._active_ns)
        self._active_ns = "root"
        self._ns_cursor = 0
        self._reload_ns(); self._load_ns(); self._sync_all()
        self.notify("namespace deleted", timeout=2)

    def action_quit(self) -> None:
        self.exit()
