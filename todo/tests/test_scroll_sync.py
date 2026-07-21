"""Tests for the cursor-into-view scroll sync in the tasks pane."""
import asyncio
from pathlib import Path

from todo.core.models import Priority, Task
from todo.ui.dashboard_screen import TimeTuiApp


def _build_flat(n: int) -> list[Task]:
    return [
        Task(text=f"task {i}", indent=0, priority=Priority.MEDIUM)
        for i in range(n)
    ]


async def _scroll_test(n: int, target: int):
    root = Path("/tmp/time-tui-scroll-test")
    app = TimeTuiApp(root)
    async with app.run_test(size=(120, 20)) as pilot:
        app._tasks = _build_flat(n)
        app._cursor = target
        # Force a full sync.
        app._sync_everything()
        await pilot.pause()
        pane = app.screen.query_one("#task-list")
        return pane.scroll_y, app._cursor


def test_scroll_into_view_when_cursor_below_visible():
    """Cursor far below the viewport should scroll the list down."""
    scroll_y, cursor = asyncio.run(_scroll_test(50, target=40))
    # Pane height = ~16 (after header/footer); cursor=40 means we need scroll_y >= 25.
    assert scroll_y >= cursor - 15


def test_scroll_into_view_when_cursor_above_visible():
    """Cursor above the visible window should scroll back up."""
    scroll_y, cursor = asyncio.run(_scroll_test(50, target=0))
    assert scroll_y == 0


def test_scroll_into_view_keeps_position_when_inside_window():
    """If the cursor already sits inside the visible window, no scroll change."""
    scroll_y, cursor = asyncio.run(_scroll_test(50, target=3))
    assert scroll_y == 0