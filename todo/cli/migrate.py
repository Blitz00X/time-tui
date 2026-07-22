"""
One-shot migration: legacy ``.time-tui/calendar.json`` and ``sessions.json``
into the new Markdown format at ``.todo/calendar.md`` and ``.todo/sessions.md``.

Run:
    python -m todo.cli.migrate [--root DIR] [--force]

Behavior:
- If ``.todo/calendar.md`` already exists and ``--force`` is not given, skip.
- Otherwise read the JSON, convert, write the Markdown.
- Rename the original JSON files to ``.bak`` so a rollback is possible.

The script is idempotent and safe to run multiple times.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

from ..core import calendar_parser, sessions_parser, storage


def dashboard_dir(root: Path) -> Path:
    return root / ".time-tui"


def calendar_json_path(root: Path) -> Path:
    return dashboard_dir(root) / "calendar.json"


def sessions_json_path(root: Path) -> Path:
    return dashboard_dir(root) / "sessions.json"


def migrate_calendar(root: Path, *, force: bool) -> str:
    src = calendar_json_path(root)
    dst = storage.calendar_path(root)
    if not src.exists():
        return "calendar.json: missing, skipped"
    if dst.exists() and not force:
        return f"calendar.md: already exists, skipped (use --force to overwrite)"
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"calendar.json: failed to parse: {exc}"
    cal: dict[str, list[calendar_parser.CalendarEvent]] = {}
    if isinstance(data, dict):
        for iso_day, rows in data.items():
            events: list[calendar_parser.CalendarEvent] = []
            for row in rows or []:
                try:
                    events.append(
                        calendar_parser.CalendarEvent(
                            start=calendar_parser.normalize_hm(row["start"]),
                            end=calendar_parser.normalize_hm(row["end"]),
                            title=str(row.get("title", "")).strip() or "untitled",
                            color=str(row.get("color", "green")),
                        )
                    )
                except (KeyError, TypeError, ValueError):
                    continue
            cal[iso_day] = events
    md = calendar_parser.build_calendar(cal)
    storage.ensure_todo_dir(root)
    storage._atomic_write(dst, md)  # noqa: SLF001
    shutil.move(str(src), str(src) + ".bak")
    n = sum(len(v) for v in cal.values())
    return f"calendar: {n} events across {len(cal)} days -> {dst}"


def migrate_sessions(root: Path, *, force: bool) -> str:
    src = sessions_json_path(root)
    dst = storage.sessions_md_path(root)
    if not src.exists():
        return "sessions.json: missing, skipped"
    if dst.exists() and not force:
        return f"sessions.md: already exists, skipped (use --force to overwrite)"
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"sessions.json: failed to parse: {exc}"
    rows = data.get("sessions", []) if isinstance(data, dict) else []
    sessions: dict[str, list[sessions_parser.SessionEntry]] = {}
    for row in rows:
        try:
            start_iso = row["started"]
            end_iso = row["ended"]
            label = str(row.get("label", "session"))
            start_dt = __import__("datetime").datetime.fromisoformat(start_iso)
            end_dt = __import__("datetime").datetime.fromisoformat(end_iso)
            iso_day = start_dt.date().isoformat()
            entry = sessions_parser.make_entry(
                start_hm=f"{start_dt.hour:02d}:{start_dt.minute:02d}",
                end_hm=f"{end_dt.hour:02d}:{end_dt.minute:02d}",
                label=label,
            )
            sessions.setdefault(iso_day, []).append(entry)
        except (KeyError, TypeError, ValueError):
            continue
    md = sessions_parser.build_sessions(sessions)
    storage.ensure_todo_dir(root)
    storage._atomic_write(dst, md)  # noqa: SLF001
    shutil.move(str(src), str(src) + ".bak")
    n = sum(len(v) for v in sessions.values())
    return f"sessions: {n} entries across {len(sessions)} days -> {dst}"


def register(sub) -> None:
    p = sub.add_parser("migrate", help="One-shot migration from legacy JSON to Markdown.")
    p.add_argument("--root", type=Path, default=Path.cwd(),
                   help="Project root (defaults to current dir).")
    p.add_argument("--force", action="store_true",
                   help="Overwrite existing Markdown files.")
    p.set_defaults(handler=_handler)


def _handler(root_from_main, args):
    argv = ["--root", str(args.root)]
    if args.force:
        argv.append("--force")
    return main(argv)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Migrate legacy JSON data to Markdown.")
    p.add_argument("--root", type=Path, default=Path.cwd(),
                   help="Project root (defaults to current dir).")
    p.add_argument("--force", action="store_true",
                   help="Overwrite existing Markdown files.")
    args = p.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    results = [migrate_calendar(root, force=args.force),
               migrate_sessions(root, force=args.force)]
    for r in results:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())