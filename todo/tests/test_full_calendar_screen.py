import asyncio
from datetime import date
from pathlib import Path
from typing import cast

from textual.widgets import Static

from todo.core.dashboard_io import CalendarEvent, insert_event
from todo.ui.dashboard_screen import TimeTuiApp
from todo.ui.full_calendar_screen import FullCalendarScreen


def test_dashboard_button_opens_full_calendar_and_restores_state(tmp_path: Path):
    async def run() -> None:
        app = TimeTuiApp(tmp_path)
        app._cal_date = date(2026, 7, 17)
        app._cal_tab = "week"

        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.click("#cal-expand")

            assert isinstance(app.screen, FullCalendarScreen)
            screen = app.screen
            assert screen.selected_date == date(2026, 7, 17)
            assert screen.view == "week"

            await pilot.press("right")
            assert screen.selected_date == date(2026, 7, 24)

            await pilot.press("escape")
            assert not isinstance(app.screen, FullCalendarScreen)
            assert app._cal_date == date(2026, 7, 24)
            assert app._cal_tab == "week"

    asyncio.run(run())


def test_full_calendar_renders_real_week_and_month_grids(tmp_path: Path):
    async def run() -> None:
        app = TimeTuiApp(tmp_path)

        async with app.run_test(size=(140, 44)) as pilot:
            screen = FullCalendarScreen(
                tmp_path,
                selected_date=date(2026, 7, 17),
                initial_view="week",
            )
            app.push_screen(screen)
            await pilot.pause()

            assert len(screen.query(".fc-week-day")) == 7
            assert len(screen.query(".fc-week-hour")) == 24

            await pilot.press("m")
            assert screen.view == "month"
            assert len(screen.query(".fc-month-weekday")) == 7
            assert len(screen.query(".fc-month-cell")) == 42

            await pilot.press("d")
            assert screen.view == "day"
            assert len(screen.query(".fc-day-hour")) == 24

    asyncio.run(run())


def test_full_calendar_displays_events_in_week_and_month(tmp_path: Path):
    event_day = date(2026, 7, 17)
    insert_event(
        tmp_path,
        event_day.isoformat(),
        CalendarEvent("09:00", "10:00", "Design review", "blue"),
    )

    async def run() -> None:
        app = TimeTuiApp(tmp_path)

        async with app.run_test(size=(140, 44)) as pilot:
            screen = FullCalendarScreen(
                tmp_path,
                selected_date=event_day,
                initial_view="week",
            )
            app.push_screen(screen)
            await pilot.pause()

            week_text = "\n".join(
                str(cast(Static, widget).content) for widget in screen.query(".fc-week-slot")
            )
            assert "Design review" in week_text

            await pilot.press("m")
            month_text = "\n".join(
                str(cast(Static, widget).content) for widget in screen.query(".fc-month-cell")
            )
            assert "Design review" in month_text

    asyncio.run(run())


def test_full_calendar_blocks_dashboard_bindings(tmp_path: Path):
    async def run() -> None:
        app = TimeTuiApp(tmp_path)

        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.click("#cal-expand")
            screen = app.screen
            assert isinstance(screen, FullCalendarScreen)
            initial_state = (app._pane, app._filter, app._tr_running, app._cursor)

            for key in ("e", "s", "f", "n", "c", "C", "down", "tab"):
                await pilot.press(key)
                assert app.screen is screen
                assert (app._pane, app._filter, app._tr_running, app._cursor) == initial_state

    asyncio.run(run())


def test_month_view_scrolls_on_standard_80x24_terminal(tmp_path: Path):
    async def run() -> None:
        app = TimeTuiApp(tmp_path)

        async with app.run_test(size=(80, 24)) as pilot:
            screen = FullCalendarScreen(
                tmp_path,
                selected_date=date(2026, 7, 17),
                initial_view="month",
            )
            app.push_screen(screen)
            await pilot.pause()

            month_scroll = screen.query_one("#fc-month-scroll")
            assert month_scroll.max_scroll_y > 0
            assert len(screen.query(".fc-month-cell")) == 42
            assert cast(Static, screen.query_one("#fc-title")).content == "Jul 2026"

    asyncio.run(run())


def test_day_view_opens_at_transferred_start_hour(tmp_path: Path):
    async def run() -> None:
        app = TimeTuiApp(tmp_path)

        async with app.run_test(size=(100, 30)) as pilot:
            screen = FullCalendarScreen(
                tmp_path,
                selected_date=date(2026, 7, 17),
                initial_view="day",
                day_start_hour=8,
            )
            app.push_screen(screen)
            await pilot.pause()

            day_scroll = screen.query_one("#fc-day-scroll")
            assert day_scroll.scroll_y >= 15

    asyncio.run(run())


def test_day_and_week_events_span_their_duration(tmp_path: Path):
    event_day = date(2026, 7, 17)
    insert_event(
        tmp_path,
        event_day.isoformat(),
        CalendarEvent("09:00", "11:00", "Architecture", "purple"),
    )

    async def run() -> None:
        app = TimeTuiApp(tmp_path)

        async with app.run_test(size=(140, 44)) as pilot:
            screen = FullCalendarScreen(
                tmp_path,
                selected_date=event_day,
                initial_view="week",
            )
            app.push_screen(screen)
            await pilot.pause()
            assert len(screen.query(".fc-event-block")) == 2

            await pilot.press("d")
            assert len(screen.query(".fc-event-block")) == 2

    asyncio.run(run())
