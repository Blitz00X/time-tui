"""
time-tui — prototype dashboard: namespaces | tasks | tags / calendar | tracker.
"""
from __future__ import annotations

from calendar import month_name, monthcalendar, monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from ..core.dashboard_io import (
    CalendarEvent,
    append_session,
    delete_event_at,
    delete_session_at,
    event_from_form,
    format_duration,
    hm_total_min,
    insert_event,
    insert_session_manual,
    load_events,
    load_recent_sessions,
    seed_dashboard_demo_if_empty,
    update_event_at,
    update_session_at,
)
from ..core.models import Priority, Task
from ..core.storage import (
    create_namespace,
    delete_namespace,
    list_namespaces,
    load_tasks,
    namespace_path,
    save_tasks,
)
from .modals.event_modal import EventFormResult, EventModal
from .modals.modal import TaskModal
from .modals.ns_modal import NewNamespaceModal
from .modals.session_modal import SessionFormResult, SessionModal

Pane = Literal["namespaces", "tasks", "tags", "calendar", "tracker"]
TrKind = Literal["timer", "stopwatch", "pomodoro"]
TrTrackerRow = Literal["kind", "control", "sessions"]
CalInnerRow = Literal["tabs", "events"]

FILTER_CYCLE = ("all", "pending", "today", "doing", "high")
PANES_CYCLE: tuple[Pane, ...] = ("tasks", "namespaces", "tags", "calendar", "tracker")
POMO_LEN = 25 * 60
WEEKDAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
COLOR_MAP = {"green": "green", "blue": "blue", "yellow": "yellow", "purple": "purple"}
CAL_TABS = ("day", "week", "month")
CAL_DAY_DEFAULT_START_HOUR = 8
CAL_DAY_VISIBLE_HOURS = 11
CAL_DAY_MIN_START_HOUR = 0
CAL_DAY_MAX_START_HOUR = 24 - CAL_DAY_VISIBLE_HOURS
TR_KIND_ORDER = ("timer", "stopwatch", "pomodoro")
TR_CONTROL_ORDER = ("start", "reset", "done")


def weekday_full(idx: int) -> str:
    return [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ][idx]


_PRI_SYM = {"high": "!", "medium": "~", "low": "·"}
_BIG_CLOCK_GLYPHS = {
    "0": [" ███ ", "█   █", "█   █", "█   █", " ███ "],
    "1": ["  █  ", " ██  ", "  █  ", "  █  ", " ███ "],
    "2": ["████ ", "    █", " ███ ", "█    ", "█████"],
    "3": ["████ ", "    █", " ███ ", "    █", "████ "],
    "4": ["█  █ ", "█  █ ", "█████", "   █ ", "   █ "],
    "5": ["█████", "█    ", "████ ", "    █", "████ "],
    "6": [" ████", "█    ", "████ ", "█   █", " ███ "],
    "7": ["█████", "   █ ", "  █  ", " █   ", "█    "],
    "8": [" ███ ", "█   █", " ███ ", "█   █", " ███ "],
    "9": [" ███ ", "█   █", " ████", "    █", " ███ "],
    ":": ["     ", "  █  ", "     ", "  █  ", "     "],
}

APP_CSS = """\
Screen { background: $background; }

#main-stack {
    height: 1fr;
    layout: vertical;
}
#top-banner {
    layout: horizontal;
    height: 1;
    min-height: 1;
}
#hdr-align-ns {
    width: 22;
}
#hdr-align-tasks {
    width: 1fr;
}
#hdr-datetime {
    width: 26;
    padding: 0 1;
    content-align: right middle;
}
#top-row {
    layout: horizontal;
    height: 1fr;
    border-bottom: solid $primary-darken-3;
}
#bottom-row {
    layout: horizontal;
    height: 1fr;
}

#pane-ns {
    width: 22;
    height: 1fr;
    layout: vertical;
    background: $surface-darken-1;
    border: solid $primary-darken-3;
}
#pane-tasks {
    width: 1fr;
    height: 1fr;
    layout: vertical;
    background: $surface-darken-1;
    border: solid $primary-darken-3;
}
#pane-tags {
    width: 26;
    height: 1fr;
    layout: vertical;
    background: $surface-darken-1;
    border: solid $primary-darken-3;
}
#pane-cal {
    width: 1fr;
    height: 1fr;
    layout: vertical;
    background: $surface-darken-1;
    border: solid $primary-darken-3;
}
#pane-trk {
    width: 1fr;
    height: 1fr;
    layout: vertical;
    background: $surface-darken-1;
    border: solid $primary-darken-3;
}

.pane-title {
    height: 1;
    background: $surface-darken-2;
    color: $text-muted;
    padding: 0 1;
    content-align: left middle;
}

#body {
    height: 1fr;
    layout: vertical;
}
.pane-title.-focus {
    color: $primary;
    background: $primary-darken-3;
}
#pane-ns.-focus,
#pane-tasks.-focus,
#pane-tags.-focus,
#pane-cal.-focus,
#pane-trk.-focus {
    border: heavy $primary;
}
.pane-foot {
    height: 1;
    color: $primary;
    padding: 0 1;
    content-align: left middle;
}
.pane-scroll {
    height: 1fr;
    scrollbar-size: 1 1;
}

NsRow { height: 1; padding: 0 1; layout: horizontal; width: 1fr; }
NsRow:hover { background: $surface-lighten-1; }
NsRow.-cursor { background: $primary-darken-3; }
NsRow.-active { background: $primary-darken-2; }
NsRow.-active .ns-glyph { color: $primary; }
.ns-glyph { width: 2; }
.ns-name { width: 1fr; }
.ns-count { width: 4; color: $warning; content-align: right middle; }

TagRow { height: 1; padding: 0 1; layout: horizontal; width: 1fr; }
TagRow:hover { background: $surface-lighten-1; }
TagRow.-cursor { background: $primary-darken-3; }
.tag-n.-active { color: $primary; text-style: bold; }
.tag-n { width: 1fr; color: $accent; }
.tag-c { width: 4; color: $warning; content-align: right middle; }

TaskRow { layout: horizontal; height: 1; padding: 0 1; width: 1fr; }
TaskRow:hover { background: $surface-lighten-1; }
TaskRow.-selected { background: $primary-darken-2; }
.task-cb { width: 4; content-align: left middle; }
.task-pri { width: 3; content-align: left middle; }
.task-text { width: 1fr; content-align: left middle; }
.task-tags { width: 20; color: $text-muted; content-align: right middle; }

.pri-high { color: $error; }
.pri-medium { color: $warning; }
.pri-low { color: $success; }
.pri-doing { color: $accent; }
.pri-done { color: $text-muted; text-style: dim; }

#cal-inner { height: 1fr; scrollbar-size: 1 1; padding: 0 1; }
#trk-tabs { height: 1; padding: 0 2; content-align: left middle; }
#trk-sub { height: 1; padding: 0 2; color: $success; content-align: center middle; }
#trk-clock { height: 5; content-align: center middle; color: $success; text-style: bold; }
#trk-keys { height: 1; padding: 0 2; color: $text-muted; text-style: dim; content-align: center middle; }
#trk-session-h { height: 1; padding: 0 1; }
#tracker-sessions { height: 1fr; scrollbar-size: 1 1; }

#footer-keys {
    height: 1;
    background: $surface-darken-2;
    color: $text-muted;
    padding: 0 1;
    content-align: left middle;
}

SearchModal {
    align: center middle;
}

#search-modal {
    width: 54;
    height: auto;
    background: $surface;
    border: thick $primary;
    padding: 1 2;
}

#search-title {
    color: $primary;
    text-style: bold;
    margin-bottom: 1;
}
"""


def _fmt_clock(total_s: int) -> str:
    return f"{total_s // 60:02d}:{total_s % 60:02d}"


def _big_clock_text(clock_text: str) -> str:
    rows = [""] * 5
    for char in clock_text:
        glyph = _BIG_CLOCK_GLYPHS.get(char, _BIG_CLOCK_GLYPHS["0"])
        for idx, line in enumerate(glyph):
            rows[idx] += line + "  "
    return "\n".join(row.rstrip() for row in rows)


def _session_line_text(i: int, s: dict, *, selected: bool = False) -> str:
    try:
        st = datetime.fromisoformat(s["started"])
        et = datetime.fromisoformat(s["ended"])
        t0 = st.strftime("%H:%M")
        t1 = et.strftime("%H:%M")
        dur = _fmt_clock(int(s.get("duration_secs", 0)))
    except Exception:
        t0 = t1 = "??:??"
        dur = "00:00"
    label = s.get("label", "")
    line = f"{i + 1}. {t0} - {t1} ({dur}) {label}"
    if selected:
        return f"[reverse]{line}[/]"
    return line


class NsRow(Static):
    def __init__(self, name: str, count: int, active: bool, cursor: bool) -> None:
        super().__init__()
        self._nm = name
        self._count = count
        if active:
            self.add_class("-active")
        if cursor:
            self.add_class("-cursor")

    def compose(self) -> ComposeResult:
        yield Static(">", classes="ns-glyph")
        yield Static(self._nm, classes="ns-name")
        yield Static(str(self._count), classes="ns-count")

    def update_row(self, name: str, count: int, active: bool, cursor: bool) -> None:
        self._nm = name
        self._count = count
        self.set_class(active, "-active")
        self.set_class(cursor, "-cursor")
        sts = list(self.query(Static))
        if len(sts) >= 3:
            sts[0].update(">" if active else " ")
            sts[1].update(name)
            sts[2].update(str(count))


class TagRow(Static):
    def __init__(self, tag: str, count: int, cursor: bool, active: bool) -> None:
        super().__init__()
        self._tag = tag
        self._cnt = count
        if cursor:
            self.add_class("-cursor")
        self._active = active

    def compose(self) -> ComposeResult:
        classes = "tag-n -active" if self._active else "tag-n"
        yield Static(self._tag, classes=classes)
        yield Static(str(self._cnt), classes="tag-c")

    def update_row(self, tag: str, count: int, cursor: bool, active: bool) -> None:
        self._tag, self._cnt = tag, count
        self._active = active
        self.set_class(cursor, "-cursor")
        k = list(self.query(Static))
        if len(k) >= 2:
            k[0].update(tag)
            k[0].set_classes("tag-n -active" if active else "tag-n")
            k[1].update(str(count))


class TaskRow(Static):
    def __init__(self, todo_task: Task, selected: bool) -> None:
        super().__init__()
        self._todo_task = todo_task
        if selected:
            self.add_class("-selected")

    def _tcls(self, t: Task) -> str:
        if t.done:
            return "pri-done"
        if t.is_doing:
            return "pri-doing"
        return f"pri-{t.priority.value}"

    def compose(self) -> ComposeResult:
        t = self._todo_task
        c = self._tcls(t)
        yield Static("[x]" if t.done else "[ ]", classes="task-cb")
        yield Static(_PRI_SYM[t.priority.value], classes=f"task-pri {c}")
        yield Static(t.text, classes=f"task-text {c}")
        yield Static(t.display_tags if t.tags else "", classes="task-tags")

    def refresh_from(self, todo_task: Task, selected: bool) -> None:
        self._todo_task = todo_task
        self.set_class(selected, "-selected")
        kids = list(self.query(Static))
        if len(kids) < 4:
            return
        t = todo_task
        c = self._tcls(t)
        kids[0].update("[x]" if t.done else "[ ]")
        kids[1].update(_PRI_SYM[t.priority.value])
        kids[1].set_classes(f"task-pri {c}")
        kids[2].update(t.text)
        kids[2].set_classes(f"task-text {c}")
        kids[3].update(t.display_tags if t.tags else "")


class SearchModal(ModalScreen[Optional[str]]):
    BINDINGS = [Binding("escape", "cancel", show=False)]

    def __init__(self, initial_value: str = "") -> None:
        super().__init__()
        self._initial = initial_value

    def compose(self) -> ComposeResult:
        with Vertical(id="search-modal"):
            yield Static("Search Tasks", id="search-title")
            yield Input(value=self._initial, placeholder="type text and press enter", id="search-input")
            yield Static("[dim]Leave empty to clear search[/]")
            with Horizontal():
                yield Button("Clear", id="search-clear")
                yield Button("Apply", variant="primary", id="search-apply")

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_input_submitted(self) -> None:
        self.dismiss(self.query_one("#search-input", Input).value.strip())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "search-clear":
            self.dismiss("")
        elif event.button.id == "search-apply":
            self.dismiss(self.query_one("#search-input", Input).value.strip())


class TimeTuiApp(App):
    CSS = APP_CSS
    TITLE = "time-tui"

    BINDINGS = [
        Binding("up", "cursor_up", show=False),
        Binding("down", "cursor_down", show=False),
        Binding("tab", "tab_next_pane", show=False, priority=True),
        Binding("shift+tab", "tab_prev_pane", show=False, priority=True),
        Binding("right", "cursor_right", show=False, priority=True),
        Binding("left", "cursor_left", show=False, priority=True),
        Binding("enter", "enter_pressed", show=False),
        Binding("a", "add_task", show=False),
        Binding("e", "edit_task", show=False),
        Binding("d", "delete_task", show=False),
        Binding("s", "toggle_tracker_run", show=False),
        Binding("r", "reset_tracker", show=False),
        Binding("f", "cycle_filter", show=False),
        Binding("slash", "stub_search", show=False),
        Binding("comma", "prev_day", show=False),
        Binding(".", "next_day", show=False),
        Binding("[", "cal_tab_prev", show=False),
        Binding("]", "cal_tab_next", show=False),
        Binding("t", "focus_tracker", show=False),
        Binding("c", "focus_calendar", show=False),
        Binding("n", "focus_namespaces", show=False),
        Binding("N", "new_namespace", show=False),
        Binding("X", "del_namespace", show=False),
        Binding("q", "quit_app", show=False),
        Binding("1", "tr_kind_timer", show=False),
        Binding("2", "tr_kind_stopwatch", show=False),
        Binding("3", "tr_kind_pomodoro", show=False),
        Binding("escape", "exit_inner_focus", show=False),
    ]

    def __init__(self, root: Path) -> None:
        super().__init__()
        self._root = root
        self._tasks: list[Task] = []
        self._cursor = 0
        self._filter: str = "all"
        self._ns_list: list[str] = []
        self._ns_cursor = 0
        self._active_ns = "root"
        self._pane: Pane = "tasks"
        self._tag_rows: list[tuple[str, int]] = []
        self._tag_cursor = 0
        self._cal_tab = "day"
        self._cal_date = date.today()
        self._cal_day_start_hour = CAL_DAY_DEFAULT_START_HOUR
        self._tr_kind: TrKind = "pomodoro"
        self._tr_running = False
        self._tr_remain_s = POMO_LEN
        self._timer_target_s = POMO_LEN
        self._sw_elapsed_s = 0
        self._tag_filter: Optional[str] = None
        self._search_query = ""
        self._inner_focus = False
        self._cal_tab_cursor = 0
        self._cal_inner_row: CalInnerRow = "tabs"
        self._cal_events: list[CalendarEvent] = []
        self._cal_event_refs: list[tuple[str, int]] = []
        self._cal_event_cursor = 0
        self._tr_kind_cursor = 2
        self._tr_tracker_row: TrTrackerRow = "kind"
        self._tr_control_cursor = 0
        self._session_rows: list[dict] = []
        self._session_cursor = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="body"):
            with Vertical(id="main-stack"):
                with Horizontal(id="top-banner"):
                    yield Static("", id="hdr-align-ns")
                    yield Static("", id="hdr-align-tasks")
                    yield Static("", id="hdr-datetime")
                with Horizontal(id="top-row"):
                    with Vertical(id="pane-ns"):
                        yield Static("  namespaces", classes="pane-title", id="title-ns")
                        yield ScrollableContainer(id="box-ns", classes="pane-scroll")
                        yield Static("  + add namespace", classes="pane-foot")
                    with Vertical(id="pane-tasks"):
                        yield Static("", classes="pane-title", id="title-task")
                        yield ScrollableContainer(id="task-list", classes="pane-scroll")
                    with Vertical(id="pane-tags"):
                        yield Static("  tags", classes="pane-title", id="title-tag")
                        yield ScrollableContainer(id="tag-list", classes="pane-scroll")
                        yield Static("  + add tag", classes="pane-foot")
                with Horizontal(id="bottom-row"):
                    with Vertical(id="pane-cal"):
                        yield Static("  calendar", classes="pane-title", id="title-cal")
                        yield ScrollableContainer(Static("", id="cal-inner"), classes="pane-scroll")
                        yield Static("  + add event", classes="pane-foot")
                    with Vertical(id="pane-trk"):
                        yield Static("  tracker", classes="pane-title", id="title-trk")
                        yield Static("", id="trk-tabs")
                        yield Static("", id="trk-sub")
                        yield Static("", id="trk-clock")
                        yield Static("", id="trk-keys")
                        yield Static("", id="trk-session-h")
                        yield ScrollableContainer(id="tracker-sessions", classes="pane-scroll")
            yield Static("", id="footer-keys")

    def on_mount(self) -> None:
        self.app.set_focus(None)
        seed_dashboard_demo_if_empty(self._root)
        self._reload_ns()
        self._load_ns_keep_filter()
        self.set_interval(1.0, self._every_tick)
        self.call_after_refresh(self._sync_everything)

    def on_resize(self) -> None:
        self._paint_header()

    def _reload_ns(self) -> None:
        raw = sorted(list_namespaces(self._root))
        self._ns_list = ["root"] + [n for n in raw if n != "root"]
        self._ns_cursor = min(self._ns_cursor, max(0, len(self._ns_list) - 1))
        if self._active_ns not in self._ns_list:
            self._active_ns = "root"

    def _tasks_path(self, ns: str) -> Path:
        return namespace_path(self._root, ns)

    def _load_ns_keep_filter(self) -> None:
        self._tasks = load_tasks(self._tasks_path(self._active_ns))
        vis = self._filtered_list()
        if vis:
            self._cursor = min(self._cursor, len(vis) - 1)
        else:
            self._cursor = 0

    def _persist(self) -> None:
        save_tasks(self._tasks, self._tasks_path(self._active_ns))

    def _pending_count_ns(self, ns: str) -> int:
        try:
            return sum(1 for t in load_tasks(self._tasks_path(ns)) if not t.done)
        except OSError:
            return 0

    def _filtered_list(self) -> list[Task]:
        a = self._tasks
        f = self._filter
        if f == "pending":
            a = [t for t in a if not t.done]
        if f == "today":
            a = [t for t in a if not t.done and t.is_today]
        if f == "doing":
            a = [t for t in a if not t.done and t.is_doing]
        if f == "high":
            a = [t for t in a if not t.done and t.priority == Priority.HIGH]
        if self._tag_filter:
            a = [t for t in a if self._tag_filter in t.tags]
        if self._search_query:
            q = self._search_query.casefold()
            a = [t for t in a if q in t.text.casefold() or any(q in tg.casefold() for tg in t.tags)]
        return list(a)

    def _chosen_task(self) -> Optional[Task]:
        rows = self._filtered_list()
        if not rows:
            return None
        return rows[max(0, min(self._cursor, len(rows) - 1))]

    def _sync_everything(self) -> None:
        rows = self._filtered_list()
        if rows:
            self._cursor = max(0, min(self._cursor, len(rows) - 1))
        else:
            self._cursor = 0
        self._paint_header()
        self._sync_footer()
        self._pane_title_styles()
        self._sync_namespace_box()
        self._sync_tasks_box(rows)
        self._sync_tags_box()
        self._sync_calendar_inner()
        self._sync_tracker()
        self._sync_sessions_scroll()

    def _pane_has_inner_focus(self) -> bool:
        return self._inner_focus

    def _exit_inner_focus(self) -> None:
        self._inner_focus = False

    def _cycle_pane(self, step: int) -> None:
        ix = PANES_CYCLE.index(self._pane) if self._pane in PANES_CYCLE else 0
        self._pane = PANES_CYCLE[(ix + step) % len(PANES_CYCLE)]

    def _enter_inner_focus(self) -> None:
        self._inner_focus = True
        if self._pane == "calendar":
            self._cal_tab_cursor = CAL_TABS.index(self._cal_tab)
            self._cal_inner_row = "tabs"
            self._cal_event_cursor = 0
        elif self._pane == "tracker":
            self._tr_kind_cursor = TR_KIND_ORDER.index(self._tr_kind)
            self._tr_tracker_row = "kind"
            self._tr_control_cursor = 0
            self._session_cursor = 0

    def _calendar_in_events(self) -> bool:
        return (
            self._pane == "calendar"
            and self._pane_has_inner_focus()
            and self._cal_inner_row == "events"
        )

    def _chosen_event(self) -> Optional[CalendarEvent]:
        if not self._cal_events:
            return None
        idx = max(0, min(self._cal_event_cursor, len(self._cal_events) - 1))
        return self._cal_events[idx]

    def _cal_row_down(self) -> None:
        if self._cal_inner_row == "tabs":
            self._cal_inner_row = "events"
            self._cal_event_cursor = 0

    def _cal_row_up(self) -> None:
        if self._cal_inner_row == "events":
            if self._cal_events and self._cal_event_cursor > 0:
                self._cal_event_cursor -= 1
            elif self._cal_tab == "day" and self._cal_day_start_hour > CAL_DAY_MIN_START_HOUR:
                self._cal_day_start_hour -= 1
            else:
                self._cal_inner_row = "tabs"

    def _cal_event_down(self) -> None:
        if self._cal_events and self._cal_event_cursor < len(self._cal_events) - 1:
            self._cal_event_cursor += 1
        elif self._cal_tab == "day" and self._cal_day_start_hour < CAL_DAY_MAX_START_HOUR:
            self._cal_day_start_hour += 1

    def _tracker_in_sessions(self) -> bool:
        return (
            self._pane == "tracker"
            and self._pane_has_inner_focus()
            and self._tr_tracker_row == "sessions"
        )

    def _chosen_session(self) -> Optional[dict]:
        if not self._session_rows:
            return None
        idx = max(0, min(self._session_cursor, len(self._session_rows) - 1))
        return self._session_rows[idx]

    def _tracker_cursor_kind(self) -> TrKind:
        return TR_KIND_ORDER[self._tr_kind_cursor]

    def _sync_footer(self) -> None:
        width = self.size.width or 0
        if width >= 132:
            text = (
                "[yellow]↑↓[/] [dim]nav[/]  "
                "[yellow]enter[/] [dim]select[/]  "
                "[yellow]a[/] [dim]add[/]  "
                "[yellow]e[/] [dim]edit[/]  "
                "[yellow]d[/] [dim]del[/]  "
                "[yellow]s[/] [dim]start[/]  "
                "[yellow]r[/] [dim]reset[/]  "
                "[yellow]f[/] [dim]filter[/]  "
                "[yellow]/[/] [dim]search[/]  "
                "[yellow]t[/] [dim]tracker[/]  "
                "[yellow]c[/] [dim]calendar[/]  "
                "[yellow]n[/] [dim]namespace[/]  "
                "[yellow]q[/] [dim]quit[/]"
            )
        elif width >= 110:
            text = (
                "[yellow]↑↓[/] [dim]nav[/]  "
                "[yellow]enter[/] [dim]select[/]  "
                "[yellow]a[/] [dim]add[/]  "
                "[yellow]e[/] [dim]edit[/]  "
                "[yellow]d[/] [dim]del[/]  "
                "[yellow]s[/] [dim]start[/]  "
                "[yellow]r[/] [dim]reset[/]  "
                "[yellow]f[/] [dim]filter[/]  "
                "[yellow]/[/] [dim]search[/]  "
                "[yellow]t[/] [dim]tracker[/]  "
                "[yellow]c[/] [dim]cal[/]  "
                "[yellow]n[/] [dim]ns[/]  "
                "[yellow]q[/] [dim]quit[/]"
            )
        else:
            text = (
                "[yellow]↑↓[/] [dim]nav[/]  "
                "[yellow]enter[/] [dim]ok[/]  "
                "[yellow]a[/] [dim]add[/]  "
                "[yellow]e[/] [dim]edit[/]  "
                "[yellow]d[/] [dim]del[/]  "
                "[yellow]s[/] [dim]go[/]  "
                "[yellow]r[/] [dim]reset[/]  "
                "[yellow]f[/] [dim]filter[/]  "
                "[yellow]/[/] [dim]find[/]  "
                "[yellow]q[/] [dim]quit[/]"
            )
        self.query_one("#footer-keys", Static).update(text)

    def _pane_title_styles(self) -> None:
        for title_id, pane_id, key in (
            ("title-ns", "pane-ns", "namespaces"),
            ("title-task", "pane-tasks", "tasks"),
            ("title-tag", "pane-tags", "tags"),
            ("title-cal", "pane-cal", "calendar"),
            ("title-trk", "pane-trk", "tracker"),
        ):
            title = self.query_one(f"#{title_id}", Static)
            pane = self.query_one(f"#{pane_id}")
            if key == self._pane:
                title.add_class("-focus")
                pane.add_class("-focus")
            else:
                title.remove_class("-focus")
                pane.remove_class("-focus")

    def _header_datetime_plain(self, dt: datetime) -> str:
        # Fits the tags column (width 26) above the tags pane title.
        return dt.strftime("%a, %b %d, %Y  %H:%M")

    def _paint_header(self) -> None:
        dt = datetime.now()
        right_plain = self._header_datetime_plain(dt)
        self.query_one("#hdr-datetime", Static).update(
            f"[bold bright_yellow]{right_plain}[/]"
        )

    def _sync_namespace_box(self) -> None:
        outer = self.query_one("#box-ns", ScrollableContainer)
        xs = list(outer.query(NsRow))
        if len(xs) == len(self._ns_list):
            for i, (row, nm) in enumerate(zip(xs, self._ns_list)):
                count = self._pending_count_ns(nm)
                row.update_row(
                    nm,
                    count,
                    nm == self._active_ns,
                    self._pane == "namespaces" and i == self._ns_cursor,
                )
        else:
            outer.remove_children()
            for i, nm in enumerate(self._ns_list):
                count = self._pending_count_ns(nm)
                outer.mount(
                    NsRow(
                        nm,
                        count,
                        nm == self._active_ns,
                        self._pane == "namespaces" and i == self._ns_cursor,
                    )
                )

    def _sync_tasks_box(self, visible: list[Task]) -> None:
        suffix = ""
        if self._tag_filter:
            suffix += f"  [cyan]{self._tag_filter}[/]"
        if self._search_query:
            suffix += f"  [yellow]/ {self._search_query}[/]"
        ttl = "[dodgerblue]tasks[/]    " f"[dim]{len(visible)} shown, {len(self._tasks)} total[/]{suffix}"
        self.query_one("#title-task", Static).update("  " + ttl)
        pane = self.query_one("#task-list", ScrollableContainer)
        existed = list(pane.query(TaskRow))
        if len(existed) == len(visible):
            for i, (rw, tk) in enumerate(zip(existed, visible)):
                rw.refresh_from(tk, i == self._cursor)
        else:
            pane.remove_children()
            if not visible:
                pane.mount(
                    Static(
                        "  (empty)  [dim]press a to add[/]",
                        id="empty-state",
                    )
                )
            else:
                for i, tk in enumerate(visible):
                    pane.mount(TaskRow(tk, i == self._cursor))

    def _sync_tags_box(self) -> None:
        counts: dict[str, int] = {}
        for task in self._tasks:
            if task.done:
                continue
            for tag in task.tags:
                counts[tag] = counts.get(tag, 0) + 1
        self._tag_rows = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        pane = self.query_one("#tag-list", ScrollableContainer)
        existing = list(pane.query(TagRow))
        if len(existing) == len(self._tag_rows):
            for i, ((tg, ct), row) in enumerate(zip(self._tag_rows, existing)):
                row.update_row(
                    tg,
                    ct,
                    self._pane == "tags" and i == self._tag_cursor,
                    tg == self._tag_filter,
                )
        else:
            pane.remove_children()
            if not self._tag_rows:
                pane.mount(Static("  —", classes="pane-foot"))
            else:
                for i, (tg, ct) in enumerate(self._tag_rows):
                    pane.mount(
                        TagRow(
                            tg,
                            ct,
                            self._pane == "tags" and i == self._tag_cursor,
                            tg == self._tag_filter,
                        )
                    )

    def _cal_week_days(self) -> list[date]:
        start = self._cal_date - timedelta(days=self._cal_date.weekday())
        return [start + timedelta(days=i) for i in range(7)]

    def _shift_month(self, delta: int) -> None:
        y, m, d = self._cal_date.year, self._cal_date.month, self._cal_date.day
        m += delta
        while m < 1:
            m += 12
            y -= 1
        while m > 12:
            m -= 12
            y += 1
        last = monthrange(y, m)[1]
        self._cal_date = date(y, m, min(d, last))

    def _cal_nav_line(self) -> str:
        d = self._cal_date
        if self._cal_tab == "week":
            days = self._cal_week_days()
            a, b = days[0], days[-1]
            if a.month == b.month and a.year == b.year:
                label = f"{month_name[a.month]} {a.day} – {b.day}, {a.year}"
            else:
                label = (
                    f"{month_name[a.month]} {a.day}, {a.year} – "
                    f"{month_name[b.month]} {b.day}, {b.year}"
                )
        elif self._cal_tab == "month":
            label = f"{month_name[d.month]} {d.year}"
        else:
            label = f"{WEEKDAY[d.weekday()]}, {month_name[d.month]} {d.day}, {d.year}"
        return f"[yellow]<[/]    [yellow]{label}[/]    [yellow]>[/]"

    def _format_cal_event_line(
        self,
        ev: CalendarEvent,
        *,
        selected: bool,
        prefix: str = "  ",
    ) -> str:
        col = COLOR_MAP.get(ev.color, "green")
        dur_l = format_duration(ev.start, ev.end)
        title = f"{ev.start}  {ev.title[:28]}"
        pad = max(1, 32 - len(title))
        if selected:
            return f"[reverse]{prefix}████ {title}{' ' * pad}{dur_l}[/]"
        return f"{prefix}[{col}]████ {title}{' ' * pad}{dur_l}[/]"

    def _reload_cal_events(self) -> None:
        self._cal_events = []
        self._cal_event_refs = []
        if self._cal_tab == "week":
            days = self._cal_week_days()
        else:
            days = [self._cal_date]
        for day in days:
            iso = day.isoformat()
            for idx, ev in enumerate(load_events(self._root, iso)):
                self._cal_events.append(ev)
                self._cal_event_refs.append((iso, idx))
        if self._cal_events:
            self._cal_event_cursor = max(
                0, min(self._cal_event_cursor, len(self._cal_events) - 1),
            )
        else:
            self._cal_event_cursor = 0

    def _calendar_day_text(self, nav_line: str) -> str:
        d = self._cal_date
        lines = [nav_line, ""]
        if d == date.today():
            ts = datetime.now().strftime("%H:%M")
            lines.append(f"[red]{ts}[/] [dim]······································[/]")
            lines.append("")

        selected = self._calendar_in_events()
        stop_hour = self._cal_day_start_hour + CAL_DAY_VISIBLE_HOURS
        for hh in range(self._cal_day_start_hour, stop_hour):
            lbl = f"{hh:02d}:00"
            hour_events = [
                (event_idx, ev)
                for event_idx, ev in enumerate(self._cal_events)
                if hm_total_min(ev.start) // 60 == hh
            ]
            if not hour_events:
                lines.append(f"[dim]{lbl}[/]")
                continue
            for row_idx, (event_idx, ev) in enumerate(hour_events):
                prefix = f"[dim]{lbl}[/]  " if row_idx == 0 else "      "
                lines.append(
                    self._format_cal_event_line(
                        ev,
                        selected=selected and event_idx == self._cal_event_cursor,
                        prefix=prefix,
                    )
                )
        return "\n".join(lines)

    def _calendar_week_text(self, nav_line: str) -> str:
        lines = [nav_line, ""]
        today = date.today()
        selected = self._calendar_in_events()
        for day in self._cal_week_days():
            iso = day.isoformat()
            wd = WEEKDAY[day.weekday()]
            if day == today:
                head = f"[bold yellow]{wd} {day.day}[/] [dim]today[/]"
            elif day == self._cal_date:
                head = f"[bold cyan]{wd} {day.day}[/]"
            else:
                head = f"[cyan]{wd} {day.day}[/]"
            lines.append(head)
            day_events = [
                (i, ev)
                for i, ev in enumerate(load_events(self._root, iso))
            ]
            if not day_events:
                lines.append("  [dim]—[/]")
            else:
                for local_idx, ev in day_events:
                    is_sel = (
                        selected
                        and self._cal_event_cursor < len(self._cal_event_refs)
                        and self._cal_event_refs[self._cal_event_cursor] == (iso, local_idx)
                    )
                    lines.append(
                        self._format_cal_event_line(ev, selected=is_sel, prefix="  ")
                    )
            lines.append("")
        return "\n".join(lines).rstrip()

    def _calendar_month_text(self, nav_line: str) -> str:
        lines = [nav_line, ""]
        y, m = self._cal_date.year, self._cal_date.month
        lines.append(f"[cyan]     {month_name[m]} {y}[/]")
        lines.append("[dim]Mo Tu We Th Fr Sa Su[/]")
        today = date.today()
        sel = self._cal_date
        for week in monthcalendar(y, m):
            cells: list[str] = []
            for day in week:
                if day == 0:
                    cells.append("   ")
                    continue
                d = date(y, m, day)
                iso = d.isoformat()
                dot = "•" if load_events(self._root, iso) else " "
                if d == sel:
                    cells.append(f"[reverse]{day:2d}[/]{dot}")
                elif d == today:
                    cells.append(f"[yellow]{day:2d}[/]{dot}")
                else:
                    cells.append(f"{day:2d}{dot} ")
            lines.append(" ".join(cells))
        lines.append("")
        wd = WEEKDAY[sel.weekday()]
        lines.append(f"[cyan]{wd}, {month_name[sel.month]} {sel.day}[/]")
        selected = self._calendar_in_events()
        if not self._cal_events:
            lines.append("  [dim]—[/]")
        else:
            iso = sel.isoformat()
            for local_idx, ev in enumerate(load_events(self._root, iso)):
                is_sel = (
                    selected
                    and self._cal_event_cursor < len(self._cal_event_refs)
                    and self._cal_event_refs[self._cal_event_cursor] == (iso, local_idx)
                )
                lines.append(
                    self._format_cal_event_line(ev, selected=is_sel, prefix="  ")
                )
        return "\n".join(lines)

    def _calendar_body_text(self) -> str:
        nav_line = self._cal_nav_line()
        if self._cal_tab == "week":
            return self._calendar_week_text(nav_line)
        if self._cal_tab == "month":
            return self._calendar_month_text(nav_line)
        return self._calendar_day_text(nav_line)

    def _sync_calendar_inner(self) -> None:
        self._reload_cal_events()
        self.query_one("#title-cal", Static).update("  " + self._calendar_title_text())
        self.query_one("#cal-inner", Static).update(self._calendar_body_text())

    def _calendar_title_text(self) -> str:
        tabs = []
        for idx, lab in enumerate(("Day", "Week", "Month")):
            tab_key = lab.lower()
            if (
                self._pane_has_inner_focus()
                and self._pane == "calendar"
                and self._cal_inner_row == "tabs"
                and idx == self._cal_tab_cursor
            ):
                tabs.append(f"[reverse]{lab}[/]")
            elif tab_key == self._cal_tab:
                tabs.append(f"[black on white]{lab}[/]")
            else:
                tabs.append(f"[dodgerblue]{lab}[/]")
        return "[dodgerblue]calendar[/]    " + "  ".join(tabs)

    def _tr_tab_line(self) -> str:
        out = []
        for idx, lab in enumerate(("Timer", "Stopwatch", "Pomodoro")):
            kind = TR_KIND_ORDER[idx]
            sel = (
                (lab == "Timer" and self._tr_kind == "timer")
                or (lab == "Stopwatch" and self._tr_kind == "stopwatch")
                or (lab == "Pomodoro" and self._tr_kind == "pomodoro")
            )
            if (
                self._pane_has_inner_focus()
                and self._pane == "tracker"
                and self._tr_tracker_row == "kind"
                and idx == self._tr_kind_cursor
            ):
                chunk = f"[reverse]{lab}[/]  "
            elif sel:
                chunk = f"[reverse bold]{lab}[/]  "
            else:
                chunk = f"[cyan]{lab}[/]  "
            out.append(chunk)
        return "".join(out).strip()

    def _tr_control_line(self) -> str:
        out = []
        for idx, lab in enumerate(TR_CONTROL_ORDER):
            if (
                self._pane_has_inner_focus()
                and self._pane == "tracker"
                and self._tr_tracker_row == "control"
                and idx == self._tr_control_cursor
            ):
                chunk = f"[reverse]{lab}[/]  "
            else:
                chunk = f"[yellow]{lab}[/]  "
            out.append(chunk)
        return "".join(out).strip()

    def _tracker_title_text(self) -> str:
        return "[dodgerblue]tracker[/]"

    def _tr_sub_label(self) -> str:
        if self._tr_kind == "pomodoro":
            return "[green]Focus Time[/]"
        if self._tr_kind == "stopwatch":
            return "[green]Elapsed[/]"
        return "[green]Timer[/]"

    def _tr_clock_plain(self) -> str:
        if self._tr_kind == "stopwatch":
            sec = self._sw_elapsed_s
        elif self._tr_kind == "timer":
            sec = max(0, self._tr_remain_s)
        else:
            sec = max(0, self._tr_remain_s)
        mm, ss = divmod(sec, 60)
        return f"[bright_green bold]{_big_clock_text(f'{mm:02d}:{ss:02d}')}[/bright_green bold]"

    def _sync_tracker(self) -> None:
        self.query_one("#title-trk", Static).update("  " + self._tracker_title_text())
        self.query_one("#trk-tabs", Static).update(self._tr_tab_line())
        self.query_one("#trk-sub", Static).update(self._tr_sub_label())
        self.query_one("#trk-clock", Static).update(self._tr_clock_plain())
        self.query_one("#trk-keys", Static).update(self._tr_control_line())

    def _sync_sessions_scroll(self) -> None:
        log = load_recent_sessions(self._root, 40)
        self._session_rows = log
        if log:
            self._session_cursor = max(0, min(self._session_cursor, len(log) - 1))
        else:
            self._session_cursor = 0
        self.query_one("#trk-session-h", Static).update(
            f"[cyan]Session Log ({len(log)})[/cyan]" if log else "[dim]Session Log (0)[/dim]",
        )
        box = self.query_one("#tracker-sessions", ScrollableContainer)
        selected = (
            self._pane == "tracker"
            and self._pane_has_inner_focus()
            and self._tr_tracker_row == "sessions"
        )
        existing = list(box.children)
        if len(existing) == len(log):
            for i, (widget, s) in enumerate(zip(existing, log)):
                if isinstance(widget, Static):
                    widget.update(_session_line_text(i, s, selected=selected and i == self._session_cursor))
        else:
            box.remove_children()
            for i, s in enumerate(log):
                box.mount(Static(_session_line_text(i, s, selected=selected and i == self._session_cursor)))
        if selected and log:
            children = list(box.children)
            if 0 <= self._session_cursor < len(children):
                box.scroll_to_widget(children[self._session_cursor])

    def _every_tick(self) -> None:
        self._paint_header()
        if self._cal_tab == "day" and self._cal_date == date.today():
            self._sync_calendar_inner()
        if not self._tr_running:
            self._sync_tracker()
            return
        if self._tr_kind == "stopwatch":
            self._sw_elapsed_s += 1
        else:
            if self._tr_remain_s > 0:
                self._tr_remain_s -= 1
            if self._tr_remain_s <= 0 and self._tr_kind == "pomodoro":
                self._finish_pomo_work()
                return
            if self._tr_remain_s <= 0 and self._tr_kind == "timer":
                self.notify("Timer finished")
                self._tr_running = False
                self._tr_remain_s = self._timer_target_s
        self._sync_tracker()

    def _tracker_elapsed_secs(self) -> int:
        if self._tr_kind == "stopwatch":
            return max(0, self._sw_elapsed_s)
        if self._tr_kind == "timer":
            return max(0, self._timer_target_s - self._tr_remain_s)
        return max(0, POMO_LEN - self._tr_remain_s)

    def _append_tracker_session(self, duration_secs: int) -> None:
        if duration_secs <= 0:
            return
        t = self._chosen_task()
        append_session(
            self._root,
            task_label=t.text[:80] if t else "focus",
            duration_secs=duration_secs,
        )

    def _finish_pomo_work(self) -> None:
        self._tr_running = False
        self._append_tracker_session(POMO_LEN)
        self._tr_remain_s = POMO_LEN
        self.notify("Pomodoro block complete", timeout=4)
        self._sync_sessions_scroll()
        self._sync_tracker()

    def action_done_tracker(self) -> None:
        if self._pane != "tracker":
            self._pane = "tracker"
        secs = self._tracker_elapsed_secs()
        if secs <= 0:
            self.notify("No time to log yet")
            return
        self._tr_running = False
        self._append_tracker_session(secs)
        self._sync_sessions_scroll()
        if self._tr_kind == "stopwatch":
            self._sw_elapsed_s = 0
        elif self._tr_kind == "pomodoro":
            self._tr_remain_s = POMO_LEN
        else:
            self._tr_remain_s = self._timer_target_s
        self.notify(f"Session saved ({secs // 60:02d}:{secs % 60:02d})", timeout=3)
        self._sync_tracker()

    def _activate_tracker_control(self, control: str) -> None:
        if control == "start":
            self.action_toggle_tracker_run()
        elif control == "reset":
            self.action_reset_tracker()
        else:
            self.action_done_tracker()

    def action_cycle_filter(self) -> None:
        i = FILTER_CYCLE.index(self._filter) if self._filter in FILTER_CYCLE else 0
        self._filter = FILTER_CYCLE[(i + 1) % len(FILTER_CYCLE)]
        self._cursor = 0
        self._sync_everything()

    def action_focus_tags(self) -> None:
        self._pane = "tags"
        if self._tag_rows:
            self._tag_cursor = min(self._tag_cursor, len(self._tag_rows) - 1)
        self._sync_everything()

    def action_focus_namespaces(self) -> None:
        self._pane = "namespaces"
        self._ns_cursor = self._ns_list.index(self._active_ns)
        self._sync_everything()

    def action_focus_calendar(self) -> None:
        self._pane = "calendar"
        self._sync_everything()

    def action_focus_tracker(self) -> None:
        self._pane = "tracker"
        self._sync_everything()

    def action_stub_search(self) -> None:
        self.push_screen(SearchModal(self._search_query), callback=self._on_search)

    def action_tab_next_pane(self) -> None:
        if self._pane_has_inner_focus():
            self._exit_inner_focus()
        self._cycle_pane(1)
        self._sync_everything()

    def action_tab_prev_pane(self) -> None:
        if self._pane_has_inner_focus():
            self._exit_inner_focus()
        self._cycle_pane(-1)
        self._sync_everything()

    def action_cursor_right(self) -> None:
        if self._pane_has_inner_focus():
            if self._pane == "namespaces":
                self._active_ns = self._ns_list[self._ns_cursor]
                self._load_ns_keep_filter()
                self._pane = "tasks"
            elif self._pane == "tracker":
                if self._tr_tracker_row == "kind":
                    self._tr_kind_cursor = (self._tr_kind_cursor + 1) % len(TR_KIND_ORDER)
                elif self._tr_tracker_row == "control":
                    self._tr_control_cursor = (self._tr_control_cursor + 1) % len(TR_CONTROL_ORDER)
            elif self._pane == "calendar" and self._cal_inner_row == "tabs":
                self._cal_tab_cursor = (self._cal_tab_cursor + 1) % len(CAL_TABS)
            else:
                self._inner_next()
        elif self._pane == "calendar" and self._cal_tab == "month":
            self._cal_date += timedelta(days=1)
        else:
            self._cycle_pane(1)
        self._sync_everything()

    def action_cursor_left(self) -> None:
        if self._pane_has_inner_focus():
            if self._pane == "tasks":
                self._pane = "namespaces"
                if self._active_ns in self._ns_list:
                    self._ns_cursor = self._ns_list.index(self._active_ns)
            elif self._pane == "tracker":
                if self._tr_tracker_row == "kind":
                    self._tr_kind_cursor = (self._tr_kind_cursor - 1) % len(TR_KIND_ORDER)
                elif self._tr_tracker_row == "control":
                    self._tr_control_cursor = (self._tr_control_cursor - 1) % len(TR_CONTROL_ORDER)
            elif self._pane == "calendar" and self._cal_inner_row == "tabs":
                self._cal_tab_cursor = (self._cal_tab_cursor - 1) % len(CAL_TABS)
            else:
                self._inner_prev()
        elif self._pane == "calendar" and self._cal_tab == "month":
            self._cal_date -= timedelta(days=1)
        else:
            self._cycle_pane(-1)
        self._sync_everything()

    def action_enter_pressed(self) -> None:
        if not self._pane_has_inner_focus():
            self._enter_inner_focus()
            self._sync_everything()
            return

        if self._pane == "tasks":
            self.action_toggle_done()
        elif self._pane == "namespaces":
            self._active_ns = self._ns_list[self._ns_cursor]
            self._load_ns_keep_filter()
            self._sync_everything()
        elif self._pane == "tags":
            if self._tag_rows:
                tag = self._tag_rows[self._tag_cursor][0]
                self._tag_filter = None if self._tag_filter == tag else tag
                self._cursor = 0
                self._sync_everything()
        elif self._pane == "calendar":
            if self._cal_inner_row == "events":
                if self._chosen_event() is not None:
                    self.action_open_event_modal(self._cal_event_cursor)
            else:
                self._cal_tab = CAL_TABS[self._cal_tab_cursor]
            self._sync_everything()
        elif self._pane == "tracker":
            if self._tr_tracker_row == "control":
                control = TR_CONTROL_ORDER[self._tr_control_cursor]
                self._activate_tracker_control(control)
            elif self._tr_tracker_row == "sessions":
                if self._chosen_session() is not None:
                    self.action_open_session_modal(self._session_cursor)
            else:
                chosen = self._tracker_cursor_kind()
                if chosen == "timer":
                    self.action_tr_kind_timer()
                elif chosen == "stopwatch":
                    self.action_tr_kind_stopwatch()
                else:
                    self.action_tr_kind_pomodoro()
            self._sync_everything()

    def action_toggle_done(self) -> None:
        t = self._chosen_task()
        if not t:
            return
        t.toggle_done()
        self._persist()
        self._sync_everything()

    def action_cursor_up(self) -> None:
        if self._pane_has_inner_focus():
            if self._pane == "tracker":
                self._tracker_row_up()
            elif self._pane == "calendar":
                self._cal_row_up()
            else:
                self._inner_prev()
            self._sync_everything()
            return
        if self._pane == "tasks":
            if self._cursor > 0:
                self._cursor -= 1
        elif self._pane == "namespaces":
            if self._ns_cursor > 0:
                self._ns_cursor -= 1
        elif self._pane == "tags" and self._tag_rows:
            if self._tag_cursor > 0:
                self._tag_cursor -= 1
        elif self._pane == "calendar":
            self.action_prev_day()
            return
        self._sync_everything()

    def action_cursor_down(self) -> None:
        if self._pane_has_inner_focus():
            if self._pane == "tracker":
                if self._tr_tracker_row == "sessions":
                    self._tracker_session_down()
                else:
                    self._tracker_row_down()
            elif self._pane == "calendar":
                if self._cal_inner_row == "events":
                    self._cal_event_down()
                else:
                    self._cal_row_down()
            else:
                self._inner_next()
            self._sync_everything()
            return
        if self._pane == "tasks":
            vis = self._filtered_list()
            if self._cursor < len(vis) - 1:
                self._cursor += 1
        elif self._pane == "namespaces":
            if self._ns_cursor < len(self._ns_list) - 1:
                self._ns_cursor += 1
        elif self._pane == "tags" and self._tag_rows:
            if self._tag_cursor < len(self._tag_rows) - 1:
                self._tag_cursor += 1
        elif self._pane == "calendar":
            self.action_next_day()
            return
        self._sync_everything()

    def action_prev_day(self) -> None:
        if self._pane != "calendar" or self._inner_focus:
            return
        if self._cal_tab == "week":
            self._cal_date -= timedelta(days=7)
        elif self._cal_tab == "month":
            self._shift_month(-1)
        else:
            self._cal_date -= timedelta(days=1)
        self._sync_everything()

    def action_next_day(self) -> None:
        if self._pane != "calendar" or self._inner_focus:
            return
        if self._cal_tab == "week":
            self._cal_date += timedelta(days=7)
        elif self._cal_tab == "month":
            self._shift_month(1)
        else:
            self._cal_date += timedelta(days=1)
        self._sync_everything()

    def action_cal_tab_prev(self) -> None:
        if self._pane != "calendar":
            return
        if self._inner_focus:
            if self._cal_inner_row == "tabs":
                self._cal_tab_cursor = (self._cal_tab_cursor - 1) % len(CAL_TABS)
        else:
            i = CAL_TABS.index(self._cal_tab)
            self._cal_tab = CAL_TABS[(i - 1) % 3]
        self._sync_everything()

    def action_cal_tab_next(self) -> None:
        if self._pane != "calendar":
            return
        if self._inner_focus:
            if self._cal_inner_row == "tabs":
                self._cal_tab_cursor = (self._cal_tab_cursor + 1) % len(CAL_TABS)
        else:
            i = CAL_TABS.index(self._cal_tab)
            self._cal_tab = CAL_TABS[(i + 1) % 3]
        self._sync_everything()

    def action_tr_kind_timer(self) -> None:
        self._stop_tr(False)
        self._tr_kind = "timer"
        self._tr_remain_s = self._timer_target_s
        self._sync_everything()

    def action_tr_kind_stopwatch(self) -> None:
        self._stop_tr(False)
        self._tr_kind = "stopwatch"
        self._sw_elapsed_s = 0
        self._sync_everything()

    def action_tr_kind_pomodoro(self) -> None:
        self._stop_tr(False)
        self._tr_kind = "pomodoro"
        self._tr_remain_s = POMO_LEN
        self._sync_everything()

    def _stop_tr(self, reset_remain: bool) -> None:
        self._tr_running = False
        if reset_remain:
            if self._tr_kind == "stopwatch":
                self._sw_elapsed_s = 0
            elif self._tr_kind == "pomodoro":
                self._tr_remain_s = POMO_LEN
            else:
                self._tr_remain_s = self._timer_target_s

    def _tracker_row_down(self) -> None:
        if self._tr_tracker_row == "kind":
            self._tr_tracker_row = "control"
        elif self._tr_tracker_row == "control":
            self._tr_tracker_row = "sessions"
            self._session_cursor = 0

    def _tracker_row_up(self) -> None:
        if self._tr_tracker_row == "sessions":
            if self._session_rows and self._session_cursor > 0:
                self._session_cursor -= 1
            else:
                self._tr_tracker_row = "control"
        elif self._tr_tracker_row == "control":
            self._tr_tracker_row = "kind"

    def _tracker_session_down(self) -> None:
        if not self._session_rows:
            return
        if self._session_cursor < len(self._session_rows) - 1:
            self._session_cursor += 1

    def action_open_session_modal(self, edit_index: Optional[int] = None) -> None:
        if self._pane != "tracker":
            self._pane = "tracker"
        session = self._session_rows[edit_index] if edit_index is not None else None
        self.push_screen(SessionModal(session=session), callback=lambda r: self._on_session_modal(edit_index, r))

    def _on_session_modal(self, edit_index: Optional[int], result: Optional[SessionFormResult]) -> None:
        if result is None:
            return
        try:
            if edit_index is None:
                insert_session_manual(
                    self._root,
                    start_hm=result.start_hm,
                    end_hm=result.end_hm,
                    label=result.label,
                )
                self._session_cursor = 0
            else:
                update_session_at(
                    self._root,
                    edit_index,
                    start_hm=result.start_hm,
                    end_hm=result.end_hm,
                    label=result.label,
                )
        except (ValueError, IndexError) as exc:
            self.notify(str(exc))
            return
        self._sync_everything()
        self.notify("Session saved", timeout=2)

    def action_delete_session(self) -> None:
        if not self._session_rows:
            self.notify("No session to delete")
            return
        try:
            delete_session_at(self._root, self._session_cursor)
        except IndexError:
            self.notify("No session to delete")
            return
        self._session_cursor = max(0, self._session_cursor - 1)
        self._sync_everything()
        self.notify("Session deleted", timeout=2)

    def action_toggle_tracker_run(self) -> None:
        if self._pane == "tasks":
            self._pane = "tracker"
        if self._tr_kind != "stopwatch":
            if self._tr_remain_s <= 0:
                if self._tr_kind == "pomodoro":
                    self._tr_remain_s = POMO_LEN
                else:
                    self._tr_remain_s = self._timer_target_s
        self._tr_running = not self._tr_running
        self._sync_everything()

    def _inner_next(self) -> None:
        if self._pane == "tasks":
            vis = self._filtered_list()
            if vis and self._cursor < len(vis) - 1:
                self._cursor += 1
        elif self._pane == "namespaces":
            if self._ns_cursor < len(self._ns_list) - 1:
                self._ns_cursor += 1
        elif self._pane == "tags":
            if self._tag_rows and self._tag_cursor < len(self._tag_rows) - 1:
                self._tag_cursor += 1

    def _inner_prev(self) -> None:
        if self._pane == "tasks":
            if self._cursor > 0:
                self._cursor -= 1
        elif self._pane == "namespaces":
            if self._ns_cursor > 0:
                self._ns_cursor -= 1
        elif self._pane == "tags":
            if self._tag_rows and self._tag_cursor > 0:
                self._tag_cursor -= 1

    def action_open_event_modal(self, edit_index: Optional[int] = None) -> None:
        if self._pane != "calendar":
            self._pane = "calendar"
        edit_ref = None if edit_index is None else self._cal_event_refs[edit_index]
        event = None if edit_index is None else self._cal_events[edit_index]
        self.push_screen(
            EventModal(event=event),
            callback=lambda r: self._on_event_modal(edit_ref, r),
        )

    def _on_event_modal(
        self,
        edit_ref: Optional[tuple[str, int]],
        result: Optional[EventFormResult],
    ) -> None:
        if result is None:
            return
        iso_day = self._cal_date.isoformat() if edit_ref is None else edit_ref[0]
        try:
            event = event_from_form(
                start_hm=result.start_hm,
                end_hm=result.end_hm,
                title=result.title,
                color=result.color,
            )
            if edit_ref is None:
                insert_event(self._root, iso_day, event)
            else:
                update_event_at(self._root, edit_ref[0], edit_ref[1], event)
        except (ValueError, IndexError) as exc:
            self.notify(str(exc))
            return
        self._sync_everything()
        self.notify("Event saved", timeout=2)

    def action_delete_event(self) -> None:
        if not self._cal_events:
            self.notify("No event to delete")
            return
        try:
            iso, idx = self._cal_event_refs[self._cal_event_cursor]
            delete_event_at(self._root, iso, idx)
        except IndexError:
            self.notify("No event to delete")
            return
        self._cal_event_cursor = max(0, self._cal_event_cursor - 1)
        self._sync_everything()
        self.notify("Event deleted", timeout=2)

    def action_exit_inner_focus(self) -> None:
        if self._pane_has_inner_focus():
            self._exit_inner_focus()
            self._sync_everything()

    def action_reset_tracker(self) -> None:
        self._stop_tr(True)
        self._sync_everything()

    def action_add_task(self) -> None:
        if self._pane == "calendar":
            self.action_open_event_modal(None)
            return
        if self._tracker_in_sessions():
            self.action_open_session_modal(None)
            return
        self.push_screen(TaskModal(), callback=self._on_modal)

    def action_edit_task(self) -> None:
        if self._calendar_in_events():
            if self._chosen_event() is None:
                return
            self.action_open_event_modal(self._cal_event_cursor)
            return
        if self._tracker_in_sessions():
            if self._chosen_session() is None:
                return
            self.action_open_session_modal(self._session_cursor)
            return
        t = self._chosen_task()
        if not t:
            return
        self.push_screen(TaskModal(todo_task=t), callback=self._on_modal)

    def action_delete_task(self) -> None:
        if self._calendar_in_events():
            self.action_delete_event()
            return
        if self._tracker_in_sessions():
            self.action_delete_session()
            return
        if self._pane == "namespaces":
            self.action_del_namespace()
            return
        t = self._chosen_task()
        if not t:
            return
        self._tasks = [x for x in self._tasks if x.id != t.id]
        self._cursor = max(0, self._cursor - 1)
        self._persist()
        self._sync_everything()

    def _on_modal(self, result: Optional[Task]) -> None:
        if not result:
            return
        replaced = False
        for i, t in enumerate(self._tasks):
            if t.id == result.id:
                self._tasks[i] = result
                replaced = True
                break
        if not replaced:
            self._tasks.append(result)
        self._persist()
        visible = self._filtered_list()
        for i, t in enumerate(visible):
            if t.id == result.id:
                self._cursor = i
                break
        self._sync_everything()

    def _on_search(self, result: Optional[str]) -> None:
        if result is None:
            return
        self._search_query = result
        self._cursor = 0
        self._sync_everything()

    def action_new_namespace(self) -> None:
        self.push_screen(NewNamespaceModal(), callback=self._on_new_ns)

    def _on_new_ns(self, name: Optional[str]) -> None:
        if not name:
            return
        create_namespace(self._root, name)
        self._reload_ns()
        self._active_ns = name
        self._ns_cursor = self._ns_list.index(name)
        self._load_ns_keep_filter()
        self._sync_everything()
        self.notify(f"namespace '{name}' created")

    def action_del_namespace(self) -> None:
        target_ns = self._active_ns
        if self._pane == "namespaces" and self._ns_list:
            target_ns = self._ns_list[self._ns_cursor]

        if target_ns == "root":
            self.notify("cannot delete root")
            return

        if load_tasks(self._tasks_path(target_ns)):
            self.notify("namespace is not empty")
            return

        delete_namespace(self._root, target_ns)
        if self._active_ns == target_ns:
            self._active_ns = "root"
        self._reload_ns()
        if self._active_ns in self._ns_list:
            self._ns_cursor = min(self._ns_cursor, len(self._ns_list) - 1)
        else:
            self._active_ns = "root"
            self._ns_cursor = 0
        self._load_ns_keep_filter()
        self._sync_everything()

    def action_quit_app(self) -> None:
        self.exit()
