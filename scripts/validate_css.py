#!/usr/bin/env python3
"""Validate TimeTuiApp CSS through Textual's runtime compiler."""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from todo.ui.dashboard_screen import TimeTuiApp


async def validate() -> None:
    with tempfile.TemporaryDirectory(prefix="time-tui-css-") as temp_dir:
        app = TimeTuiApp(Path(temp_dir))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            if app.screen is None:
                raise RuntimeError("dashboard did not mount")


try:
    asyncio.run(validate())
except Exception as exc:
    print(f"FAIL runtime CSS validation: {exc}")
    raise

print("OK runtime CSS compiled and dashboard mounted")
