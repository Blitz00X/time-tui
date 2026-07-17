import asyncio
from datetime import date
from pathlib import Path

from todo.core.dashboard_io import CalendarEvent, insert_event, load_events
from todo.core.models import Task
from todo.core.storage import create_namespace, namespace_path, save_tasks
from todo.ui.dashboard_screen import TimeTuiApp


def test_enter_locks_tasks_pane_until_tab():
    async def run() -> None:
        app = TimeTuiApp(Path("/tmp/time-tui-nav-tasks"))

        async with app.run_test() as pilot:
            assert app._pane == "tasks"
            assert app._inner_focus is False

            await pilot.press("enter")

            assert app._pane == "tasks"
            assert app._inner_focus is True

            await pilot.press("right")

            assert app._pane == "tasks"
            assert app._inner_focus is True

    asyncio.run(run())


def test_enter_does_not_toggle_tracker_focus_off():
    async def run() -> None:
        app = TimeTuiApp(Path("/tmp/time-tui-nav-tracker"))

        async with app.run_test() as pilot:
            app._pane = "tracker"
            app._sync_everything()

            await pilot.press("enter")
            assert app._pane == "tracker"
            assert app._inner_focus is True

            await pilot.press("enter")

            assert app._pane == "tracker"
            assert app._inner_focus is True

    asyncio.run(run())


def test_tab_exits_inner_focus_and_moves_to_next_pane():
    async def run() -> None:
        app = TimeTuiApp(Path("/tmp/time-tui-nav-tab"))

        async with app.run_test() as pilot:
            app._pane = "tracker"
            app._sync_everything()

            await pilot.press("enter")
            assert app._inner_focus is True

            await pilot.press("tab")

            assert app._inner_focus is False
            assert app._pane == "tasks"

    asyncio.run(run())


def test_right_moves_from_namespaces_into_tasks_while_staying_locked():
    async def run() -> None:
        app = TimeTuiApp(Path("/tmp/time-tui-nav-ns-to-tasks"))

        async with app.run_test() as pilot:
            app._pane = "namespaces"
            app._sync_everything()

            await pilot.press("enter")
            assert app._pane == "namespaces"
            assert app._inner_focus is True

            await pilot.press("right")

            assert app._pane == "tasks"
            assert app._inner_focus is True

    asyncio.run(run())


def test_left_moves_from_tasks_into_namespaces_while_staying_locked():
    async def run() -> None:
        app = TimeTuiApp(Path("/tmp/time-tui-nav-tasks-to-ns"))

        async with app.run_test() as pilot:
            app._pane = "tasks"
            app._sync_everything()

            await pilot.press("enter")
            assert app._pane == "tasks"
            assert app._inner_focus is True

            await pilot.press("left")

            assert app._pane == "namespaces"
            assert app._inner_focus is True

    asyncio.run(run())


def test_d_deletes_selected_empty_namespace(tmp_path: Path):
    async def run() -> None:
        create_namespace(tmp_path, "empty")
        save_tasks([], namespace_path(tmp_path, "empty"))
        app = TimeTuiApp(tmp_path)

        async with app.run_test() as pilot:
            app._pane = "namespaces"
            app._reload_ns()
            app._load_ns_keep_filter()
            app._ns_cursor = app._ns_list.index("empty")
            app._sync_everything()

            await pilot.press("d")

            assert "empty" not in app._ns_list

    asyncio.run(run())


def test_d_does_not_delete_selected_non_empty_namespace(tmp_path: Path):
    async def run() -> None:
        create_namespace(tmp_path, "full")
        save_tasks([Task(text="kept")], namespace_path(tmp_path, "full"))

        app = TimeTuiApp(tmp_path)

        async with app.run_test() as pilot:
            app._pane = "namespaces"
            app._reload_ns()
            app._load_ns_keep_filter()
            app._ns_cursor = app._ns_list.index("full")
            app._sync_everything()

            await pilot.press("d")

            assert "full" in app._ns_list

    asyncio.run(run())


def test_calendar_event_navigation_and_delete(tmp_path: Path):
    async def run() -> None:
        iso_day = date.today().isoformat()
        insert_event(tmp_path, iso_day, CalendarEvent("09:00", "09:30", "A", "green"))
        insert_event(tmp_path, iso_day, CalendarEvent("10:00", "10:30", "B", "blue"))
        app = TimeTuiApp(tmp_path)

        async with app.run_test(size=(100, 30)) as pilot:
            app._pane = "calendar"
            app._sync_everything()

            await pilot.press("enter")
            await pilot.press("down")
            assert app._cal_inner_row == "events"
            assert app._cal_event_cursor == 0

            await pilot.press("down")
            assert app._cal_event_cursor == 1

            app._cal_event_cursor = 0
            app._sync_everything()
            await pilot.press("d")

            events = load_events(tmp_path, iso_day)
            assert len(events) == 1
            assert events[0].title == "B"

    asyncio.run(run())


def test_calendar_day_defaults_to_08_through_18(tmp_path: Path):
    app = TimeTuiApp(tmp_path)
    body = app._calendar_body_text()

    assert "08:00" in body
    assert "18:00" in body
    assert "07:00" not in body
    assert "19:00" not in body


def test_calendar_day_arrow_keys_scroll_to_full_day_bounds(tmp_path: Path):
    async def run() -> None:
        app = TimeTuiApp(tmp_path)

        async with app.run_test(size=(100, 30)) as pilot:
            app._pane = "calendar"
            app._sync_everything()

            await pilot.press("enter")
            await pilot.press("down")
            assert app._cal_inner_row == "events"
            assert app._cal_day_start_hour == 8

            for _ in range(20):
                await pilot.press("down")

            assert app._cal_day_start_hour == 13
            body = app._calendar_body_text()
            assert "13:00" in body
            assert "23:00" in body
            assert "08:00" not in body

            for _ in range(20):
                await pilot.press("up")

            assert app._cal_day_start_hour == 0
            body = app._calendar_body_text()
            assert "00:00" in body
            assert "10:00" in body
            assert "18:00" not in body

            await pilot.press("up")
            assert app._cal_inner_row == "tabs"

    asyncio.run(run())


def test_calendar_week_view_lists_days(tmp_path: Path):
    iso = date(2026, 5, 27).isoformat()
    insert_event(tmp_path, iso, CalendarEvent("09:00", "09:30", "standup", "green"))
    app = TimeTuiApp(tmp_path)
    app._cal_tab = "week"
    app._cal_date = date(2026, 5, 27)
    app._reload_cal_events()
    body = app._calendar_body_text()

    assert "Mon" in body
    assert "Tue" in body
    assert "standup" in body


def test_calendar_month_view_shows_grid(tmp_path: Path):
    app = TimeTuiApp(tmp_path)
    app._cal_tab = "month"
    app._cal_date = date(2026, 5, 27)
    app._reload_cal_events()
    body = app._calendar_body_text()

    assert "Mo Tu We Th Fr Sa Su" in body
    assert "May" in body
    assert "2026" in body
