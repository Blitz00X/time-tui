"""Full-screen Day / Week / Month calendar for time-tui."""
from __future__ import annotations

from calendar import Calendar, month_name, monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Literal, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from ..core.dashboard_io import (
    CalendarEvent,
    event_from_form,
    format_duration,
    hm_total_min,
    insert_event,
    load_event_calendar,
    load_events,
)
from .modals.event_modal import EventFormResult, EventModal

CalendarView = Literal["day", "week", "month"]
CALENDAR_VIEWS: tuple[CalendarView, ...] = ("day", "week", "month")
EVENT_COLORS = {
    "green": "green",
    "blue": "dodgerblue",
    "yellow": "yellow",
    "purple": "magenta",
}


@dataclass(frozen=True)
class FullCalendarResult:
    selected_date: date
    view: CalendarView
    day_start_hour: int


def _shift_month(value: date, delta: int) -> date:
    month_index = value.year * 12 + value.month - 1 + delta
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


class FullCalendarScreen(Screen[FullCalendarResult]):
    """Large calendar workspace backed by the dashboard calendar JSON."""

    DEFAULT_CSS = """
    FullCalendarScreen {
        background: $background;
    }

    #fc-shell {
        height: 1fr;
        padding: 1 2 0 2;
    }

    #fc-toolbar {
        height: 3;
        layout: horizontal;
        align: left middle;
    }

    #fc-back { width: 9; min-width: 9; margin-right: 1; }
    #fc-title {
        width: 1fr;
        height: 3;
        padding: 1 2;
        color: $text;
        text-style: bold;
    }
    #fc-prev, #fc-next { width: 7; min-width: 7; }
    #fc-today { width: 11; min-width: 11; margin: 0 1; }

    #fc-tabs {
        height: 3;
        layout: horizontal;
        padding-left: 13;
        border-bottom: solid $primary-darken-2;
    }
    .fc-tab { width: 12; min-width: 12; }
    .fc-tab.-active {
        background: $primary;
        color: $text;
        text-style: bold;
    }

    #fc-content {
        height: 1fr;
        border: solid $primary-darken-2;
        background: $surface-darken-1;
    }

    #fc-footer {
        height: 1;
        padding: 0 1;
        color: $text-muted;
        background: $surface-darken-2;
    }

    #fc-day-scroll, #fc-week-scroll, #fc-month-scroll {
        height: 1fr;
        scrollbar-size: 1 1;
    }

    #fc-day-view { height: auto; width: 1fr; }
    .fc-day-hour {
        height: 2;
        padding: 0 1;
        border-bottom: solid $surface-lighten-1;
    }
    .fc-day-hour.-selected { background: $primary-darken-3; }

    #fc-week-view { height: auto; min-width: 92; }
    #fc-week-hours { width: 7; height: auto; }
    .fc-week-corner {
        height: 3;
        border-bottom: solid $primary-darken-2;
    }
    .fc-week-hour {
        height: 2;
        padding: 0 1;
        color: $text-muted;
        content-align: right top;
        border-bottom: solid $surface-lighten-1;
    }
    .fc-week-day {
        width: 1fr;
        min-width: 12;
        height: auto;
        border-left: solid $primary-darken-3;
    }
    .fc-week-day.-selected { background: $primary-darken-3 35%; }
    .fc-week-head {
        height: 3;
        padding: 0 1;
        content-align: center middle;
        border-bottom: solid $primary-darken-2;
        color: $text-muted;
    }
    .fc-week-head.-today {
        color: $warning;
        text-style: bold;
    }
    .fc-week-slot {
        height: 2;
        padding: 0 1;
        border-bottom: solid $surface-lighten-1;
        text-overflow: ellipsis;
    }
    .fc-event-block { text-style: bold; }
    .fc-event-green { background: green 15%; }
    .fc-event-blue { background: blue 20%; }
    .fc-event-yellow { background: yellow 12%; }
    .fc-event-purple { background: purple 18%; }

    #fc-month-view { height: 1fr; min-height: 26; }
    #fc-month-weekdays { height: 2; }
    .fc-month-weekday {
        width: 1fr;
        padding: 0 1;
        content-align: center middle;
        color: $text-muted;
        background: $surface-darken-2;
    }
    .fc-month-week { height: 1fr; }
    .fc-month-cell {
        width: 1fr;
        height: 1fr;
        min-height: 4;
        padding: 0 1;
        border-left: solid $primary-darken-3;
        border-bottom: solid $primary-darken-3;
    }
    .fc-month-cell.-outside { color: $text-disabled; }
    .fc-month-cell.-today { color: $warning; }
    .fc-month-cell.-selected {
        background: $primary-darken-3;
        border: heavy $primary;
    }
    """

    BINDINGS = [
        Binding("escape", "close_calendar", show=False, priority=True),
        Binding("left", "previous_period", show=False, priority=True),
        Binding("right", "next_period", show=False, priority=True),
        Binding("d", "day_view", show=False, priority=True),
        Binding("w", "week_view", show=False, priority=True),
        Binding("m", "month_view", show=False, priority=True),
        Binding("t", "today", show=False, priority=True),
        Binding("a", "add_event", show=False, priority=True),
        Binding("up", "ignore", show=False, priority=True),
        Binding("down", "ignore", show=False, priority=True),
        Binding("tab", "ignore", show=False, priority=True),
        Binding("shift+tab", "ignore", show=False, priority=True),
        Binding("enter", "ignore", show=False, priority=True),
        Binding("e", "ignore", show=False, priority=True),
        Binding("s", "ignore", show=False, priority=True),
        Binding("f", "ignore", show=False, priority=True),
        Binding("slash", "ignore", show=False, priority=True),
        Binding("comma", "ignore", show=False, priority=True),
        Binding(".", "ignore", show=False, priority=True),
        Binding("[", "ignore", show=False, priority=True),
        Binding("]", "ignore", show=False, priority=True),
        Binding("c", "ignore", show=False, priority=True),
        Binding("C", "ignore", show=False, priority=True),
        Binding("n", "ignore", show=False, priority=True),
        Binding("N", "ignore", show=False, priority=True),
        Binding("X", "ignore", show=False, priority=True),
        Binding("r", "ignore", show=False, priority=True),
        Binding("1", "ignore", show=False, priority=True),
        Binding("2", "ignore", show=False, priority=True),
        Binding("3", "ignore", show=False, priority=True),
        Binding("q", "close_calendar", show=False, priority=True),
    ]

    def __init__(
        self,
        root: Path,
        *,
        selected_date: date,
        initial_view: CalendarView = "month",
        day_start_hour: int = 8,
    ) -> None:
        super().__init__()
        self._root = root
        self.selected_date = selected_date
        self.view: CalendarView = initial_view if initial_view in CALENDAR_VIEWS else "month"
        self.day_start_hour = max(0, min(23, day_start_hour))

    def compose(self) -> ComposeResult:
        with Vertical(id="fc-shell"):
            with Horizontal(id="fc-toolbar"):
                yield Button("← Back", id="fc-back")
                yield Static("", id="fc-title")
                yield Button("‹", id="fc-prev")
                yield Button("Today", id="fc-today")
                yield Button("›", id="fc-next")
            with Horizontal(id="fc-tabs"):
                yield Button("Day", id="fc-day", classes="fc-tab")
                yield Button("Week", id="fc-week", classes="fc-tab")
                yield Button("Month", id="fc-month", classes="fc-tab")
            yield Container(id="fc-content")
            yield Static(
                "Esc dashboard   ←/→ navigate   D/W/M view   T today   A add event",
                id="fc-footer",
            )

    async def on_mount(self) -> None:
        await self._refresh_view()

    def _title_text(self) -> str:
        if self.size.width < 100:
            if self.view == "day":
                return self.selected_date.strftime("%d %b %Y")
            if self.view == "week":
                iso_year, iso_week, _ = self.selected_date.isocalendar()
                return f"W{iso_week} {iso_year}"
            return self.selected_date.strftime("%b %Y")
        if self.view == "day":
            return self.selected_date.strftime("%A, %B %d, %Y")
        if self.view == "week":
            start = self.selected_date - timedelta(days=self.selected_date.weekday())
            end = start + timedelta(days=6)
            if start.month == end.month:
                return f"{month_name[start.month]} {start.day} - {end.day}, {start.year}"
            if start.year != end.year:
                return (
                    f"{month_name[start.month]} {start.day}, {start.year} - "
                    f"{month_name[end.month]} {end.day}, {end.year}"
                )
            return f"{month_name[start.month]} {start.day} - {month_name[end.month]} {end.day}, {end.year}"
        return f"{month_name[self.selected_date.month]} {self.selected_date.year}"

    def _event_markup(self, event: CalendarEvent, *, include_time: bool = True) -> str:
        color = EVENT_COLORS.get(event.color, "green")
        prefix = f"{event.start} " if include_time else ""
        return f"[{color}]▌ {prefix}{event.title}[/]"

    def _events_overlapping_hour(
        self,
        events: list[CalendarEvent],
        hour: int,
    ) -> list[CalendarEvent]:
        hour_start = hour * 60
        hour_end = hour_start + 60
        return [
            event
            for event in events
            if hm_total_min(event.start) < hour_end and hm_total_min(event.end) > hour_start
        ]

    def _hour_block(
        self,
        events: list[CalendarEvent],
        hour: int,
        *,
        include_time: bool,
    ) -> tuple[str, str]:
        overlapping = self._events_overlapping_hour(events, hour)
        if not overlapping:
            return "", ""
        chunks: list[str] = []
        for event in overlapping:
            starts_here = hm_total_min(event.start) // 60 == hour
            if starts_here:
                chunks.append(
                    f"{self._event_markup(event, include_time=include_time)} "
                    f"[dim]({format_duration(event.start, event.end)})[/]"
                )
            else:
                color = EVENT_COLORS.get(event.color, "green")
                chunks.append(f"[{color}]▌ │[/]")
        return " ".join(chunks), f"fc-event-block fc-event-{overlapping[0].color}"

    def _build_day_view(self) -> ScrollableContainer:
        rows: list[Static] = []
        events = load_events(self._root, self.selected_date.isoformat())
        for hour in range(24):
            event_text, event_classes = self._hour_block(events, hour, include_time=True)
            line = f"[dim]{hour:02d}:00[/]   {event_text}"
            classes = "fc-day-hour"
            if event_classes:
                classes += " " + event_classes
            if hour == self.day_start_hour:
                classes += " -selected"
            rows.append(Static(line, classes=classes))
        return ScrollableContainer(Vertical(*rows, id="fc-day-view"), id="fc-day-scroll")

    def _build_week_view(self) -> ScrollableContainer:
        week_start = self.selected_date - timedelta(days=self.selected_date.weekday())
        hour_column = Vertical(
            Static("", classes="fc-week-corner"),
            *(Static(f"{hour:02d}:00", classes="fc-week-hour") for hour in range(24)),
            id="fc-week-hours",
        )
        day_columns: list[Vertical] = []
        for offset in range(7):
            current = week_start + timedelta(days=offset)
            events = load_events(self._root, current.isoformat())
            head_classes = "fc-week-head"
            if current == date.today():
                head_classes += " -today"
            slots = []
            for hour in range(24):
                text, event_classes = self._hour_block(events, hour, include_time=False)
                classes = "fc-week-slot"
                if event_classes:
                    classes += " " + event_classes
                slots.append(Static(text, classes=classes))
            day_classes = "fc-week-day"
            if current == self.selected_date:
                day_classes += " -selected"
            day_columns.append(
                Vertical(
                    Static(current.strftime("%a\n%d %b"), classes=head_classes),
                    *slots,
                    classes=day_classes,
                )
            )
        grid = Horizontal(hour_column, *day_columns, id="fc-week-view")
        return ScrollableContainer(grid, id="fc-week-scroll")

    def _month_dates(self) -> list[date]:
        weeks = Calendar(firstweekday=0).monthdatescalendar(
            self.selected_date.year,
            self.selected_date.month,
        )
        while len(weeks) < 6:
            start = weeks[-1][-1] + timedelta(days=1)
            weeks.append([start + timedelta(days=i) for i in range(7)])
        return [day for week in weeks[:6] for day in week]

    def _build_month_view(self) -> ScrollableContainer:
        event_calendar = load_event_calendar(self._root)
        weekday_row = Horizontal(
            *(Static(label, classes="fc-month-weekday") for label in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")),
            id="fc-month-weekdays",
        )
        dates = self._month_dates()
        week_rows: list[Horizontal] = []
        for week_index in range(6):
            cells: list[Static] = []
            for current in dates[week_index * 7 : (week_index + 1) * 7]:
                events = event_calendar.get(current.isoformat(), [])
                lines = [f"[bold]{current.day}[/]"]
                for event in events[:2]:
                    lines.append(self._event_markup(event))
                if len(events) > 2:
                    lines.append(f"[dim]+{len(events) - 2} more[/]")
                classes = "fc-month-cell"
                if current.month != self.selected_date.month:
                    classes += " -outside"
                if current == date.today():
                    classes += " -today"
                if current == self.selected_date:
                    classes += " -selected"
                cells.append(Static("\n".join(lines), classes=classes))
            week_rows.append(Horizontal(*cells, classes="fc-month-week"))
        month_view = Vertical(weekday_row, *week_rows, id="fc-month-view")
        return ScrollableContainer(month_view, id="fc-month-scroll")

    async def _refresh_view(self) -> None:
        self.query_one("#fc-title", Static).update(self._title_text())
        for view in CALENDAR_VIEWS:
            self.query_one(f"#fc-{view}", Button).set_class(self.view == view, "-active")
        content = self.query_one("#fc-content", Container)
        await content.remove_children()
        if self.view == "day":
            await content.mount(self._build_day_view())
            self.call_after_refresh(self._scroll_day_to_start)
        elif self.view == "week":
            await content.mount(self._build_week_view())
        else:
            await content.mount(self._build_month_view())

    def _scroll_day_to_start(self) -> None:
        day_scroll = self.query_one("#fc-day-scroll", ScrollableContainer)
        day_scroll.scroll_to(
            y=self.day_start_hour * 2,
            animate=False,
            force=True,
            immediate=True,
        )

    def action_ignore(self) -> None:
        """Consume dashboard-only bindings while this screen is active."""

    async def _set_view(self, view: CalendarView) -> None:
        self.view = view
        await self._refresh_view()

    async def action_day_view(self) -> None:
        await self._set_view("day")

    async def action_week_view(self) -> None:
        await self._set_view("week")

    async def action_month_view(self) -> None:
        await self._set_view("month")

    async def action_previous_period(self) -> None:
        if self.view == "day":
            self.selected_date -= timedelta(days=1)
        elif self.view == "week":
            self.selected_date -= timedelta(days=7)
        else:
            self.selected_date = _shift_month(self.selected_date, -1)
        await self._refresh_view()

    async def action_next_period(self) -> None:
        if self.view == "day":
            self.selected_date += timedelta(days=1)
        elif self.view == "week":
            self.selected_date += timedelta(days=7)
        else:
            self.selected_date = _shift_month(self.selected_date, 1)
        await self._refresh_view()

    async def action_today(self) -> None:
        self.selected_date = date.today()
        await self._refresh_view()

    def action_add_event(self) -> None:
        self.app.push_screen(EventModal(), callback=self._on_event_modal)

    async def _on_event_modal(self, result: Optional[EventFormResult]) -> None:
        if result is None:
            return
        try:
            event = event_from_form(
                start_hm=result.start_hm,
                end_hm=result.end_hm,
                title=result.title,
                color=result.color,
            )
            insert_event(self._root, self.selected_date.isoformat(), event)
        except ValueError as exc:
            self.notify(str(exc))
            return
        await self._refresh_view()

    def action_close_calendar(self) -> None:
        self.dismiss(
            FullCalendarResult(
                selected_date=self.selected_date,
                view=self.view,
                day_start_hour=self.day_start_hour,
            )
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "fc-back":
            self.action_close_calendar()
        elif button_id == "fc-prev":
            await self.action_previous_period()
        elif button_id == "fc-today":
            await self.action_today()
        elif button_id == "fc-next":
            await self.action_next_period()
        elif button_id == "fc-day":
            await self.action_day_view()
        elif button_id == "fc-week":
            await self.action_week_view()
        elif button_id == "fc-month":
            await self.action_month_view()
