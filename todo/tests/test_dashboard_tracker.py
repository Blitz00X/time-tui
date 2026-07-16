import asyncio
import re
from datetime import datetime
from pathlib import Path

from textual.widgets import Static

from todo.core.dashboard_io import insert_session_manual, load_recent_sessions
from todo.ui.dashboard_screen import APP_CSS, TimeTuiApp


def _tracker_css_block() -> str:
    match = re.search(r"#trk-clock\s*\{([^}]*)\}", APP_CSS, re.MULTILINE)
    assert match is not None
    return match.group(1)


def test_header_shows_datetime_above_tags(tmp_path: Path):
    async def run() -> None:
        app = TimeTuiApp(tmp_path)

        async with app.run_test(size=(100, 30)):
            app._sync_everything()
            date_hdr = app.query_one("#hdr-datetime", Static)
            date_plain = date_hdr.render().plain
            tags = app.query_one("#pane-tags")
            now = datetime.now()

            assert str(now.year) in date_plain
            assert now.strftime("%H:%M") in date_plain
            assert date_hdr.region.width == 26
            assert date_hdr.region.x == tags.region.x

    asyncio.run(run())


def test_tracker_title_text_only_contains_heading():
    app = TimeTuiApp(Path.cwd())

    assert app._tracker_title_text() == "[dodgerblue]tracker[/]"


def test_tracker_clock_css_uses_hero_layout():
    css = _tracker_css_block()

    assert "height: 5;" in css
    assert "content-align: center middle;" in css


def test_tracker_clock_renders_as_big_multiline_digits():
    app = TimeTuiApp(Path.cwd())

    clock = app._tr_clock_plain()

    assert clock.count("\n") == 4
    assert "█" in clock


def test_tracker_tabs_render_in_dedicated_row(tmp_path: Path):
    async def run() -> None:
        app = TimeTuiApp(tmp_path)

        async with app.run_test(size=(100, 30)):
            app._sync_everything()
            tabs = app.query_one("#trk-tabs", Static)
            tabs_text = tabs.render().plain

            assert "Timer" in tabs_text
            assert "Stopwatch" in tabs_text
            assert "Pomodoro" in tabs_text

    asyncio.run(run())


def test_tracker_down_focuses_control_and_sessions_rows(tmp_path: Path):
    async def run() -> None:
        app = TimeTuiApp(tmp_path)

        async with app.run_test() as pilot:
            app._pane = "tracker"
            app._sync_everything()

            await pilot.press("enter")
            assert app._inner_focus is True
            assert app._tr_tracker_row == "kind"

            await pilot.press("down")
            assert app._tr_tracker_row == "control"

            await pilot.press("down")
            assert app._tr_tracker_row == "sessions"

            keys = app.query_one("#trk-keys", Static)
            keys_text = keys.render().plain
            assert "start" in keys_text

    asyncio.run(run())


def test_tracker_done_logs_session(tmp_path: Path):
    async def run() -> None:
        app = TimeTuiApp(tmp_path)

        async with app.run_test() as pilot:
            app._pane = "tracker"
            app._tr_kind = "stopwatch"
            app._sw_elapsed_s = 90
            app._sync_everything()

            await pilot.press("enter")
            await pilot.press("down")
            app._tr_control_cursor = 2
            app._sync_tracker()
            await pilot.press("enter")

            rows = load_recent_sessions(tmp_path, limit=5)
            assert len(rows) == 1
            assert rows[0]["duration_secs"] == 90

    asyncio.run(run())


def test_tracker_session_navigation_and_delete(tmp_path: Path):
    async def run() -> None:
        insert_session_manual(tmp_path, start_hm="09:00", end_hm="09:30", label="one")
        insert_session_manual(tmp_path, start_hm="10:00", end_hm="10:15", label="two")
        app = TimeTuiApp(tmp_path)

        async with app.run_test() as pilot:
            app._pane = "tracker"
            app._inner_focus = True
            app._tr_tracker_row = "sessions"
            app._sync_everything()

            assert app._session_cursor == 0
            await pilot.press("down")
            assert app._session_cursor == 1

            app._session_cursor = 0
            app._sync_everything()
            await pilot.press("d")
            rows = load_recent_sessions(tmp_path, limit=10)
            assert len(rows) == 1
            assert rows[0]["label"] == "one"

    asyncio.run(run())
