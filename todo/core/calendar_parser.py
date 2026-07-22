"""
Calendar events in Markdown format.

Format:
    # 2026-07-25
    - 09:00–10:00 jüriler
    - 14:00–15:00 prova
    - 19:00–20:00 sunum

    # 2026-07-26
    - 10:00–11:30 mentor toplantısı

Each `# YYYY-MM-DD` heading introduces a day. Events are dash-prefixed
``HH:MM–HH:MM title`` lines. Empty days may have no event lines.

This module is pure: parses text to events, builds text from events. The
storage layer (storage.py) handles locking and atomic writes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import date


_DAY_HEADING = re.compile(r"^#\s+(\d{4}-\d{2}-\d{2})\s*$")
_EVENT_LINE = re.compile(r"^-\s+(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})\s+(.+?)\s*$")


@dataclass
class CalendarEvent:
    start: str   # HH:MM
    end: str     # HH:MM
    title: str
    color: str   # green | blue | yellow | purple

    def duration_min(self) -> int:
        sh, sm = (int(x) for x in self.start.split(":"))
        eh, em = (int(x) for x in self.end.split(":"))
        return max(0, (eh * 60 + em) - (sh * 60 + sm))

    def as_dict(self) -> dict:
        return asdict(self)


def normalize_iso_day(s: str) -> str:
    """Validate and normalize YYYY-MM-DD. Raises ValueError on bad input."""
    try:
        d = date.fromisoformat(s.strip())
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Date must be YYYY-MM-DD, got: {s!r}") from exc
    return d.isoformat()


def normalize_hm(hm: str) -> str:
    """Validate HH:MM, return zero-padded form."""
    parts = hm.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Time must be HH:MM, got: {hm!r}")
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise ValueError(f"Time must be HH:MM, got: {hm!r}") from exc
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"Time out of range: {hm!r}")
    return f"{h:02d}:{m:02d}"


def parse_event_line(line: str) -> CalendarEvent | None:
    """Parse a single ``- HH:MM-HH:MM title`` line. Returns None if not an event."""
    m = _EVENT_LINE.match(line)
    if not m:
        return None
    start, end, title = m.group(1), m.group(2), m.group(3).strip()
    # We don't preserve color in the Markdown format; default to green.
    # Color is metadata that only matters for TUI rendering.
    return CalendarEvent(
        start=normalize_hm(start),
        end=normalize_hm(end),
        title=title,
        color="green",
    )


def parse_calendar(text: str) -> dict[str, list[CalendarEvent]]:
    """Parse Markdown calendar text into ``{iso_day: [events]}`` dict.

    Days are sorted ascending. Events within a day are sorted by start time.
    Unrecognized lines are ignored (comments / blanks).
    """
    out: dict[str, list[CalendarEvent]] = {}
    current_day: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        m = _DAY_HEADING.match(stripped)
        if m:
            current_day = normalize_iso_day(m.group(1))
            out.setdefault(current_day, [])
            continue
        if current_day is None:
            # Event before any day heading — skip silently.
            continue
        ev = parse_event_line(stripped)
        if ev is None:
            continue
        # Basic sanity: end must be after start.
        if ev.duration_min() <= 0:
            continue
        out[current_day].append(ev)
    # Sort events within each day by start time.
    for day_events in out.values():
        day_events.sort(key=lambda e: (int(e.start.split(":")[0]), int(e.start.split(":")[1])))
    return out


def build_calendar(calendar: dict[str, list[CalendarEvent]]) -> str:
    """Build Markdown calendar text from ``{iso_day: [events]}`` dict."""
    lines: list[str] = []
    for iso_day in sorted(calendar.keys()):
        events = sorted(calendar[iso_day], key=lambda e: e.start)
        lines.append(f"# {iso_day}")
        for ev in events:
            lines.append(f"- {ev.start}–{ev.end} {ev.title}")
        lines.append("")  # blank line between days
    # Trim trailing blank lines but keep one final newline.
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def make_event(*, start_hm: str, end_hm: str, title: str, color: str = "green") -> CalendarEvent:
    """Validate inputs and return a CalendarEvent."""
    start = normalize_hm(start_hm)
    end = normalize_hm(end_hm)
    title = title.strip()
    if not title:
        raise ValueError("Title is required")
    if (int(end.split(":")[0]) * 60 + int(end.split(":")[1])) <= (
        int(start.split(":")[0]) * 60 + int(start.split(":")[1])
    ):
        raise ValueError("End time must be after start time")
    hue = color.strip().lower() or "green"
    if hue not in {"green", "blue", "yellow", "purple"}:
        raise ValueError("Color must be green, blue, yellow, or purple")
    return CalendarEvent(start, end, title, hue)