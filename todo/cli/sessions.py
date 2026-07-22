"""Session log CLI commands.

Reads/writes ``.todo/sessions.md`` through the storage lock. Provides a thin
start/stop helper that delegates duration calculation to the user (the TUI's
pomodoro widget already does this; the CLI is for manual/agent entry).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from ..core import sessions_parser, storage


def _load_sessions(root: Path) -> dict[str, list[sessions_parser.SessionEntry]]:
    path = storage.sessions_md_path(root)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return sessions_parser.parse_sessions(text)


def _save_sessions(root: Path, data: dict[str, list[sessions_parser.SessionEntry]]) -> None:
    path = storage.sessions_md_path(root)
    storage.locked_write_to(
        path,
        lambda _cur: sessions_parser.build_sessions(data),
        root=root,
    )


def _print_day(iso_day: str, entries: list[sessions_parser.SessionEntry], *, as_json: bool) -> None:
    if as_json:
        rows = [{"date": iso_day, "start": e.start, "end": e.end, "label": e.label,
                 "duration_min": e.duration_min()} for e in entries]
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"# {iso_day}")
        for e in entries:
            print(f"  {e.start}–{e.end}  {e.label}  ({e.duration_min()} dk)")


# ── subcommand handlers ───────────────────────────────────────────────────────

def cmd_session_log(root: Path, args: argparse.Namespace) -> int:
    iso_day = sessions_parser.normalize_iso_day(args.date)
    data = _load_sessions(root)
    entries = data.get(iso_day, [])
    _print_day(iso_day, entries, as_json=args.json)
    return 0


def cmd_session_add(root: Path, args: argparse.Namespace) -> int:
    iso_day = sessions_parser.normalize_iso_day(args.date)
    entry = sessions_parser.make_entry(
        start_hm=args.start,
        end_hm=args.end,
        label=args.label or "session",
    )
    data = _load_sessions(root)
    data.setdefault(iso_day, []).append(entry)
    data[iso_day].sort(key=lambda e: e.start, reverse=True)
    _save_sessions(root, data)
    print(f"logged {iso_day} {entry.start}–{entry.end} {entry.label}")
    return 0


def cmd_session_today(root: Path, args: argparse.Namespace) -> int:
    today = datetime.now().date().isoformat()
    data = _load_sessions(root)
    entries = data.get(today, [])
    _print_day(today, entries, as_json=args.json)
    return 0


# ── parser registration ───────────────────────────────────────────────────────

def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("session", help="Manage time-tracker sessions in sessions.md.")
    sub_p = p.add_subparsers(dest="sess_cmd", required=True)

    p_today = sub_p.add_parser("today", help="List today's sessions.")
    p_today.add_argument("--json", action="store_true")
    p_today.set_defaults(handler=cmd_session_today)

    p_log = sub_p.add_parser("log", help="List sessions on a given date.")
    p_log.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_log.add_argument("--json", action="store_true")
    p_log.set_defaults(handler=cmd_session_log)

    p_add = sub_p.add_parser("add", help="Log a session entry manually.")
    p_add.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_add.add_argument("--start", required=True, help="HH:MM")
    p_add.add_argument("--end", required=True, help="HH:MM")
    p_add.add_argument("--label", default="session")
    p_add.set_defaults(handler=cmd_session_add)