import asyncio
from pathlib import Path

from todo.ui.dashboard_screen import TimeTuiApp


def test_down_arrow_moves_focus_through_task_modal_fields():
    async def run() -> None:
        app = TimeTuiApp(Path("/tmp/time-tui-modal-fields"))

        async with app.run_test() as pilot:
            await pilot.press("a")
            await pilot.pause()

            assert getattr(app.focused, "id", None) == "task-text"

            await pilot.press("down")
            assert getattr(app.focused, "id", None) == "priority-set"

            await pilot.press("down")
            assert getattr(app.focused, "id", None) == "task-tags"

            await pilot.press("down")
            assert getattr(app.focused, "id", None) == "btn-cancel"

    asyncio.run(run())


def test_up_arrow_moves_focus_back_to_previous_task_modal_field():
    async def run() -> None:
        app = TimeTuiApp(Path("/tmp/time-tui-modal-fields-up"))

        async with app.run_test() as pilot:
            await pilot.press("a")
            await pilot.pause()
            await pilot.press("down")
            await pilot.press("down")

            assert getattr(app.focused, "id", None) == "task-tags"

            await pilot.press("up")
            assert getattr(app.focused, "id", None) == "priority-set"

            await pilot.press("up")
            assert getattr(app.focused, "id", None) == "task-text"

    asyncio.run(run())
