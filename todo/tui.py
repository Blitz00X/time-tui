"""time-tui — TUI launcher.

Run with::

    python -m todo.tui

or via the ``todotui`` script in ~/.local/bin which points here.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .ui.dashboard_screen import TimeTuiApp


def main() -> int:
    # Project root: explicit override, else CWD.
    root_arg: Path | None = None
    if "--root" in sys.argv:
        idx = sys.argv.index("--root")
        if idx + 1 < len(sys.argv):
            root_arg = Path(sys.argv[idx + 1])
            sys.argv.pop(idx)
            sys.argv.pop(idx)
    root = (root_arg or Path.cwd()).resolve()
    app = TimeTuiApp(root)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
