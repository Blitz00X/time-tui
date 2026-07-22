"""Calendar CLI commands.

Reads/writes ``.todo/calendar.md`` through the storage lock. Supports
single-event addition and bulk insertion via stdin for ``add-bulk``.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from ..core import calendar_parser, storage


def _load_calendar(root: Path) -> dict[str, list[calendar_parser.CalendarEvent]]:
    path = storage.calendar_path(root)
    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        text = ""
    return calendar_parser.parse_calendar(text)


def _save_calendar(root: Path, cal: dict[str, list[calendar_parser.CalendarEvent]]) -> None:
    path = storage.calendar_path(root)
    storage.locked_write_to(
        path,
        lambda _cur: calendar_parser.build_calendar(cal),
        root=root,
    )


def _print_events(iso_day: str, events: list[calendar_parser.CalendarEvent], *, as_json: bool) -> None:
    if as_json:
        rows = [{"date": iso_day, **ev.as_dict()} for ev in events]
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"# {iso_day}")
        for ev in events:
            print(f"  {ev.start}–{ev.end}  {ev.title}")


# ── subcommand handlers ───────────────────────────────────────────────────────

def cmd_calendar_today(root: Path, args: argparse.Namespace) -> int:
    today = date.today().isoformat()
    cal = _load_calendar(root)
    events = cal.get(today, [])
    _print_events(today, events, as_json=args.json)
    return 0


def cmd_calendar_list(root: Path, args: argparse.Namespace) -> int:
    iso_day = calendar_parser.normalize_iso_day(args.date)
    cal = _load_calendar(root)
    events = cal.get(iso_day, [])
    _print_events(iso_day, events, as_json=args.json)
    return 0


def cmd_calendar_add(root: Path, args: argparse.Namespace) -> int:
    iso_day = calendar_parser.normalize_iso_day(args.date)
    event = calendar_parser.make_event(
        start_hm=args.start,
        end_hm=_compute_end(args.start, args.duration),
        title=args.text,
        color=args.color or "green",
    )
    cal = _load_calendar(root)
    cal.setdefault(iso_day, []).append(event)
    cal[iso_day].sort(key=lambda e: e.start)
    _save_calendar(root, cal)
    print(f"added {iso_day} {event.start}–{event.end} {event.title}")
    return 0


def cmd_calendar_add_bulk(root: Path, args: argparse.Namespace) -> int:
    iso_day = calendar_parser.normalize_iso_day(args.date)
    cal = _load_calendar(root)
    new_events: list[calendar_parser.CalendarEvent] = []
    for lineno, raw in enumerate(sys.stdin.read().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=2)
        if len(parts) < 3:
            raise ValueError(f"line {lineno}: expected 'HH:MM DURATION TITLE', got {raw!r}")
        start_hm, duration_str, title = parts[0], parts[1], parts[2]
        try:
            duration = int(duration_str)
        except ValueError as exc:
            raise ValueError(f"line {lineno}: duration must be integer minutes, got {duration_str!r}") from exc
        event = calendar_parser.make_event(
            start_hm=start_hm,
            end_hm=_compute_end(start_hm, duration),
            title=title,
            color="green",
        )
        new_events.append(event)
    if not new_events:
        print("no events to add", file=sys.stderr)
        return 1
    cal.setdefault(iso_day, []).extend(new_events)
    cal[iso_day].sort(key=lambda e: e.start)
    _save_calendar(root, cal)
    print(f"added {len(new_events)} events to {iso_day}")
    return 0


def cmd_calendar_move(root: Path, args: argparse.Namespace) -> int:
    cal = _load_calendar(root)
    iso_day = calendar_parser.normalize_iso_day(args.date)
    events = cal.get(iso_day, [])
    if args.id < 0 or args.id >= len(events):
        raise IndexError(f"event {args.id} not found on {iso_day}")
    event = events[args.id]
    new_start = calendar_parser.normalize_hm(args.to_start)
    duration = event.duration_min()
    sh, sm = (int(x) for x in new_start.split(":"))
    eh, em = divmod(sm + duration, 60)
    eh = (sh + eh) % 24
    new_end = f"{eh:02d}:{em:02d}"
    event.start = new_start
    event.end = new_end
    cal[iso_day].sort(key=lambda e: e.start)
    _save_calendar(root, cal)
    print(f"moved event to {iso_day} {new_start}–{new_end}")
    return 0


def cmd_calendar_delete(root: Path, args: argparse.Namespace) -> int:
    cal = _load_calendar(root)
    iso_day = calendar_parser.normalize_iso_day(args.date)
    events = cal.get(iso_day, [])
    if args.id < 0 or args.id >= len(events):
        raise IndexError(f"event {args.id} not found on {iso_day}")
    removed = events.pop(args.id)
    if not events:
        del cal[iso_day]
    _save_calendar(root, cal)
    print(f"deleted {iso_day} {removed.start}–{removed.end} {removed.title}")
    return 0


def _compute_end(start_hm: str, duration_min: int) -> str:
    sh, sm = (int(x) for x in calendar_parser.normalize_hm(start_hm).split(":"))
    total = sh * 60 + sm + duration_min
    eh, em = divmod(total, 60)
    eh = eh % 24
    return f"{eh:02d}:{em:02d}"


# ── parser registration ───────────────────────────────────────────────────────

def register(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("calendar", help="Manage calendar events in calendar.md.")
    sub_p = p.add_subparsers(dest="cal_cmd", required=True)

    p_today = sub_p.add_parser("today", help="List today's events.")
    p_today.add_argument("--json", action="store_true")
    p_today.set_defaults(handler=cmd_calendar_today)

    p_list = sub_p.add_parser("list", help="List events on a given date.")
    p_list.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(handler=cmd_calendar_list)

    p_add = sub_p.add_parser("add", help="Add a single event.")
    p_add.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_add.add_argument("--start", required=True, help="HH:MM")
    p_add.add_argument("--duration", required=True, type=int, help="duration in minutes")
    p_add.add_argument("--text", required=True)
    p_add.add_argument("--color", default="green")
    p_add.set_defaults(handler=cmd_calendar_add)

    p_bulk = sub_p.add_parser("add-bulk", help="Add multiple events from stdin.")
    p_bulk.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_bulk.set_defaults(handler=cmd_calendar_add_bulk)

    p_move = sub_p.add_parser("move", help="Move an event.")
    p_move.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_move.add_argument("--id", required=True, type=int)
    p_move.add_argument("--to-start", required=True, help="HH:MM")
    p_move.set_defaults(handler=cmd_calendar_move)

    p_del = sub_p.add_parser("delete", help="Delete an event.")
    p_del.add_argument("--date", required=True, help="YYYY-MM-DD")
    p_del.add_argument("--id", required=True, type=int)
    p_del.set_defaults(handler=cmd_calendar_delete)