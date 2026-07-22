"""CLI entry point for time-tui.

Exposes task / calendar / session commands that operate on the same Markdown
files the TUI uses, behind the same flock-based storage layer. Designed so an
agent (or a shell user) can drive the data store without opening the TUI.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import calendar as calendar_cmd
from . import sessions as sessions_cmd
from . import tasks as tasks_cmd
from . import migrate as migrate_cmd


def project_root() -> Path:
    """Project root for the CLI. Resolves in this order:

    1. ``TIME_TUI_ROOT`` env var (explicit override).
    2. The directory of the symlink/script that invoked us, walking up until
       we find a ``.todo/`` or a ``pyproject.toml`` (the project repo root).
    3. ``Path.cwd()``.
    """
    env = os.environ.get("TIME_TUI_ROOT")
    if env:
        return Path(env).expanduser().resolve()

    # Look at the invoking script's directory and walk up.
    script = Path(sys.argv[0]).resolve() if sys.argv and sys.argv[0] else None
    candidates: list[Path] = []
    if script is not None and script.is_file():
        candidates.append(script.parent)
    candidates.append(Path.cwd())
    for start in candidates:
        cur = start
        for _ in range(8):
            if (cur / ".todo").is_dir() or (cur / "pyproject.toml").is_file():
                return cur.resolve()
            if cur.parent == cur:
                break
            cur = cur.parent
    return Path.cwd().resolve()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m todo.cli",
        description="time-tui CLI: read and write tasks/calendar/sessions without the TUI.",
    )
    p.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project root (defaults to auto-detect). Overrides TIME_TUI_ROOT.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    tasks_cmd.register(sub)
    calendar_cmd.register(sub)
    sessions_cmd.register(sub)
    migrate_cmd.register(sub)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = (args.root or project_root()).resolve()
    if not root.is_dir():
        print(f"error: project root not a directory: {root}", file=sys.stderr)
        return 2
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1
    try:
        return int(handler(root, args) or 0)
    except KeyboardInterrupt:
        return 130
    except (ValueError, KeyError, IndexError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())