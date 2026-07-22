"""
Session log in Markdown format — daily pomodoro / time tracker entries.

Format:
    # 2026-07-21
    - 14:30–15:00 kod yaz
    - 15:05–15:15 mola

    # 2026-07-22
    - 09:00–12:00 BİGG çalışması

Each `# YYYY-MM-DD` heading introduces a day. Entries are dash-prefixed
``HH:MM–HH:MM label`` lines. Multiple entries per day are allowed.

The legacy ``sessions.json`` schema used ISO timestamps + duration_secs; the
markdown form only stores the visible wall-clock range and the label. Duration
is derived on demand. This is sufficient for the dashboard's display needs
and stays trivially diffable / hand-editable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


_DAY_HEADING = re.compile(r"^#\s+(\d{4}-\d{2}-\d{2})\s*$")
_SESSION_LINE = re.compile(r"^-\s+(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})\s+(.+?)\s*$")


@dataclass
class SessionEntry:
    start: str   # HH:MM
    end: str     # HH:MM
    label: str

    def duration_min(self) -> int:
        sh, sm = (int(x) for x in self.start.split(":"))
        eh, em = (int(x) for x in self.end.split(":"))
        return max(0, (eh * 60 + em) - (sh * 60 + sm))


def normalize_iso_day(s: str) -> str:
    try:
        d = date.fromisoformat(s.strip())
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Date must be YYYY-MM-DD, got: {s!r}") from exc
    return d.isoformat()


def normalize_hm(hm: str) -> str:
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


def parse_session_line(line: str) -> SessionEntry | None:
    m = _SESSION_LINE.match(line)
    if not m:
        return None
    start = normalize_hm(m.group(1))
    end = normalize_hm(m.group(2))
    label = m.group(3).strip()
    return SessionEntry(start, end, label)


def parse_sessions(text: str) -> dict[str, list[SessionEntry]]:
    """Parse Markdown session log into ``{iso_day: [sessions]}`` dict."""
    out: dict[str, list[SessionEntry]] = {}
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
            continue
        entry = parse_session_line(stripped)
        if entry is None:
            continue
        if entry.duration_min() <= 0:
            continue
        out[current_day].append(entry)
    # Sort within day by start time, then reverse so newest entries come first
    # (matches the legacy JSON behavior where the dashboard shows recent-first).
    for day_sessions in out.values():
        day_sessions.sort(key=lambda e: e.start, reverse=True)
    return out


def build_sessions(sessions: dict[str, list[SessionEntry]]) -> str:
    """Build Markdown session log from ``{iso_day: [sessions]}`` dict.

    Entries are emitted newest-first within each day (matches dashboard order).
    """
    lines: list[str] = []
    for iso_day in sorted(sessions.keys()):
        entries = sorted(sessions[iso_day], key=lambda e: e.start, reverse=True)
        lines.append(f"# {iso_day}")
        for entry in entries:
            lines.append(f"- {entry.start}–{entry.end} {entry.label}")
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def make_entry(*, start_hm: str, end_hm: str, label: str = "session") -> SessionEntry:
    start = normalize_hm(start_hm)
    end = normalize_hm(end_hm)
    label = label.strip() or "session"
    if (int(end.split(":")[0]) * 60 + int(end.split(":")[1])) <= (
        int(start.split(":")[0]) * 60 + int(start.split(":")[1])
    ):
        raise ValueError("End time must be after start time")
    return SessionEntry(start, end, label)