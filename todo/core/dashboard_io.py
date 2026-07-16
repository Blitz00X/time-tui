"""Calendar events + tracker session persistence for time-tui dashboard."""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path


def dashboard_dir(root: Path) -> Path:
    return root / ".time-tui"


def calendar_file(root: Path) -> Path:
    return dashboard_dir(root) / "calendar.json"


def sessions_file(root: Path) -> Path:
    return dashboard_dir(root) / "sessions.json"


def ensure_dashboard(root: Path) -> None:
    dashboard_dir(root).mkdir(parents=True, exist_ok=True)
    cf, sf = calendar_file(root), sessions_file(root)
    if not cf.exists():
        cf.write_text("{}", encoding="utf-8")
    if not sf.exists():
        sf.write_text('{"sessions": []}', encoding="utf-8")


@dataclass
class CalendarEvent:
    start: str   # HH:MM
    end: str     # HH:MM
    title: str
    color: str   # green, blue, yellow, purple


def parse_hm(hm: str) -> tuple[int, int]:
    h, m = hm.strip().split(":", 1)
    return int(h), int(m)


def normalize_hm(hm: str) -> str:
    h, m = parse_hm(hm)
    if h < 0 or h > 23 or m < 0 or m > 59:
        raise ValueError("Time must be HH:MM between 00:00 and 23:59")
    return f"{h:02d}:{m:02d}"


def parse_session_time_range(text: str) -> tuple[str, str]:
    """Parse ``HH:MM - HH:MM`` into normalized start/end times."""
    match = re.match(r"^\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})\s*$", text.strip())
    if not match:
        raise ValueError("Use HH:MM - HH:MM")
    return normalize_hm(match.group(1)), normalize_hm(match.group(2))


def session_entry_from_range(start_hm: str, end_hm: str, label: str) -> dict:
    today = datetime.now().date()
    sh, sm = parse_hm(start_hm)
    eh, em = parse_hm(end_hm)
    started = datetime(today.year, today.month, today.day, sh, sm)
    ended = datetime(today.year, today.month, today.day, eh, em)
    if ended <= started:
        raise ValueError("End time must be after start time")
    duration_secs = int((ended - started).total_seconds())
    return {
        "started": started.isoformat(timespec="seconds"),
        "ended": ended.isoformat(timespec="seconds"),
        "duration_secs": duration_secs,
        "label": label.strip() or "session",
    }


def load_today_sessions(root: Path, limit: int = 40) -> list[dict]:
    return load_recent_sessions(root, limit=limit)


def save_today_sessions(root: Path, sessions: list[dict]) -> None:
    ensure_dashboard(root)
    sf = sessions_file(root)
    data = {"sessions": sessions[:40]}
    sf.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def insert_session_manual(
    root: Path,
    *,
    start_hm: str,
    end_hm: str,
    label: str = "session",
) -> None:
    sessions = load_today_sessions(root, 40)
    sessions.insert(0, session_entry_from_range(start_hm, end_hm, label))
    save_today_sessions(root, sessions)


def update_session_at(
    root: Path,
    index: int,
    *,
    start_hm: str,
    end_hm: str,
    label: str,
) -> None:
    sessions = load_today_sessions(root, 40)
    if index < 0 or index >= len(sessions):
        raise IndexError("session not found")
    sessions[index] = session_entry_from_range(start_hm, end_hm, label)
    save_today_sessions(root, sessions)


def delete_session_at(root: Path, index: int) -> None:
    sessions = load_today_sessions(root, 40)
    if index < 0 or index >= len(sessions):
        raise IndexError("session not found")
    sessions.pop(index)
    save_today_sessions(root, sessions)


def hm_total_min(hm: str) -> int:
    h, m = parse_hm(hm)
    return h * 60 + m


def format_duration(start: str, end: str) -> str:
    a, b = hm_total_min(start), hm_total_min(end)
    mins = max(1, b - a)
    if mins >= 60 and mins % 60 == 0:
        return f"{mins // 60}h"
    if mins >= 60:
        return f"{mins // 60}h {mins % 60}m"
    return f"{mins}m"


def load_events(root: Path, iso_day: str) -> list[CalendarEvent]:
    ensure_dashboard(root)
    try:
        data = json.loads(calendar_file(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    rows = data.get(iso_day) or []
    out: list[CalendarEvent] = []
    for r in rows:
        try:
            out.append(CalendarEvent(r["start"], r["end"], r["title"], r.get("color", "green")))
        except KeyError:
            continue
    return sorted(out, key=lambda e: hm_total_min(e.start))


def save_events(root: Path, iso_day: str, events: list[CalendarEvent]) -> None:
    ensure_dashboard(root)
    cf = calendar_file(root)
    try:
        data = json.loads(cf.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    data[iso_day] = [asdict(e) for e in events]
    cf.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def event_from_form(*, start_hm: str, end_hm: str, title: str, color: str) -> CalendarEvent:
    start = normalize_hm(start_hm)
    end = normalize_hm(end_hm)
    label = title.strip()
    if not label:
        raise ValueError("Title is required")
    if hm_total_min(end) <= hm_total_min(start):
        raise ValueError("End time must be after start time")
    hue = color.strip().lower() or "green"
    if hue not in {"green", "blue", "yellow", "purple"}:
        raise ValueError("Color must be green, blue, yellow, or purple")
    return CalendarEvent(start, end, label, hue)


def insert_event(root: Path, iso_day: str, event: CalendarEvent) -> None:
    events = load_events(root, iso_day)
    events.append(event)
    events.sort(key=lambda e: hm_total_min(e.start))
    save_events(root, iso_day, events)


def update_event_at(root: Path, iso_day: str, index: int, event: CalendarEvent) -> None:
    events = load_events(root, iso_day)
    if index < 0 or index >= len(events):
        raise IndexError("event not found")
    events[index] = event
    events.sort(key=lambda e: hm_total_min(e.start))
    save_events(root, iso_day, events)


def delete_event_at(root: Path, iso_day: str, index: int) -> None:
    events = load_events(root, iso_day)
    if index < 0 or index >= len(events):
        raise IndexError("event not found")
    events.pop(index)
    save_events(root, iso_day, events)


def append_session(root: Path, *, task_label: str, duration_secs: int) -> None:
    ensure_dashboard(root)
    sf = sessions_file(root)
    try:
        data = json.loads(sf.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {"sessions": []}
    now = datetime.now()
    ended = now
    started = ended - timedelta(seconds=duration_secs)
    today = now.date()
    sessions = []
    for item in data.get("sessions", []):
        try:
            started_dt = datetime.fromisoformat(item.get("started", ""))
        except Exception:
            continue
        if started_dt.date() == today:
            sessions.append(item)

    entry = {
        "started": started.isoformat(timespec="seconds"),
        "ended": ended.isoformat(timespec="seconds"),
        "duration_secs": duration_secs,
        "label": task_label,
    }
    sessions.insert(0, entry)
    data["sessions"] = sessions[:40]
    sf.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_recent_sessions(root: Path, limit: int = 6) -> list[dict]:
    ensure_dashboard(root)
    try:
        data = json.loads(sessions_file(root).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    today = datetime.now().date()
    out: list[dict] = []
    for item in data.get("sessions") or []:
        try:
            started_dt = datetime.fromisoformat(item.get("started", ""))
        except Exception:
            continue
        if started_dt.date() == today:
            out.append(item)
    return out[:limit]


def aggregate_tag_counts(root: Path) -> list[tuple[str, int]]:
    from .storage import list_namespaces, namespace_path, load_tasks

    counts: Counter[str] = Counter()
    for name in sorted(list_namespaces(root)):
        try:
            for t in load_tasks(namespace_path(root, name)):
                for tg in t.tags:
                    counts[tg] += 1
        except OSError:
            continue
    return sorted(counts.items(), key=lambda x: (-x[1], x[0]))


def seed_dashboard_demo_if_empty(root: Path) -> None:
    """Populate empty calendar/session files with prototip-equivalent demo rows (today-only)."""
    ensure_dashboard(root)
    cf = calendar_file(root)
    try:
        cdata = json.loads(cf.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cdata = {}
    if not cdata:
        today = datetime.now().date().isoformat()
        cdata[today] = [
            {"start": "09:00", "end": "09:30", "title": "Team Standup", "color": "green"},
            {"start": "11:00", "end": "12:00", "title": "Project Review", "color": "blue"},
            {"start": "13:00", "end": "14:00", "title": "Lunch with Alex", "color": "yellow"},
            {"start": "14:30", "end": "16:00", "title": "Focus: Documentation", "color": "purple"},
            {"start": "16:15", "end": "17:00", "title": "Workout", "color": "green"},
        ]
        cf.write_text(json.dumps(cdata, indent=2, ensure_ascii=False), encoding="utf-8")

    sf = sessions_file(root)
    try:
        sdata = json.loads(sf.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        sdata = {"sessions": []}
    if "sessions" not in sdata:
        sdata["sessions"] = []
        sf.write_text(json.dumps(sdata, indent=2, ensure_ascii=False), encoding="utf-8")
