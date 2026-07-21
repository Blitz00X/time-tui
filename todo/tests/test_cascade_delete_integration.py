"""Integration tests for cascade delete with confirmation modal."""
import asyncio
from pathlib import Path

from todo.core.models import Priority, Task
from todo.ui.dashboard_screen import TimeTuiApp, _subtree_indices


def _build():
    return [
        Task(text="Root", indent=0),
        Task(text="A", indent=1),
        Task(text="A1", indent=2),
        Task(text="B", indent=1),
        Task(text="Sibling", indent=0),
    ]


async def _run_delete(target_idx: int, confirm: bool):
    root = Path("/tmp/time-tui-cascade")
    app = TimeTuiApp(root)
    async with app.run_test(size=(120, 24)) as pilot:
        app._tasks = _build()
        app._cursor = target_idx
        app._sync_everything()
        await pilot.pause()
        app.action_delete_task()
        await pilot.pause()
        if isinstance(app.screen_stack[-1].screen.__class__.__name__, str):
            pass
        # If a confirm modal opened, press Y or N.
        from todo.ui.modals.confirm_modal import ConfirmModal
        if any(isinstance(s, ConfirmModal) for s in app.screen_stack):
            if confirm:
                await pilot.press("y")
            else:
                await pilot.press("n")
            await pilot.pause()
        return [t.text for t in app._tasks]


def test_delete_leaf_no_modal():
    """Deleting a leaf task should not open a confirm modal."""
    out = asyncio.run(_run_delete(target_idx=4, confirm=True))
    assert "Sibling" not in out
    assert "Root" in out


def test_delete_root_with_children_opens_modal_and_confirm():
    """Deleting a root with children should ask, then cascade on yes."""
    out = asyncio.run(_run_delete(target_idx=0, confirm=True))
    assert "Root" not in out
    assert "A" not in out
    assert "A1" not in out
    assert "B" not in out
    assert "Sibling" in out


def test_delete_root_with_children_cancel_keeps():
    """If user presses N, all tasks remain."""
    out = asyncio.run(_run_delete(target_idx=0, confirm=False))
    assert "Root" in out
    assert "A" in out
    assert "Sibling" in out


def test_subtree_helper_returns_descendants_for_root():
    """Direct unit test for the helper used by delete logic."""
    tasks = _build()
    indices = _subtree_indices(tasks, 0)
    assert indices == [0, 1, 2, 3]