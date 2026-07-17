"""Verify dashboard CSS through Textual's real runtime compiler."""
from __future__ import annotations

import asyncio
from pathlib import Path

from todo.ui.dashboard_screen import TimeTuiApp


def test_app_css_compiles_when_dashboard_mounts(tmp_path: Path):
    async def run() -> None:
        app = TimeTuiApp(tmp_path)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.screen is not None

    asyncio.run(run())
