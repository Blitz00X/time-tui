from datetime import datetime, timedelta
from pathlib import Path
import json

from todo.core.dashboard_io import (
    append_session,
    delete_session_at,
    insert_event,
    insert_session_manual,
    load_recent_sessions,
    parse_session_time_range,
    sessions_file,
    update_session_at,
)


def test_load_recent_sessions_returns_only_today(tmp_path: Path):
    sf = sessions_file(tmp_path)
    sf.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    payload = {
        "sessions": [
            {
                "started": today.isoformat(timespec="seconds"),
                "ended": (today + timedelta(minutes=25)).isoformat(timespec="seconds"),
                "duration_secs": 1500,
                "label": "today",
            },
            {
                "started": yesterday.isoformat(timespec="seconds"),
                "ended": (yesterday + timedelta(minutes=25)).isoformat(timespec="seconds"),
                "duration_secs": 1500,
                "label": "yesterday",
            },
        ]
    }
    sf.write_text(json.dumps(payload), encoding="utf-8")

    rows = load_recent_sessions(tmp_path, limit=10)

    assert len(rows) == 1
    assert rows[0]["label"] == "today"


def test_append_session_resets_old_days_and_keeps_today(tmp_path: Path):
    sf = sessions_file(tmp_path)
    sf.parent.mkdir(parents=True, exist_ok=True)
    yesterday = datetime.now() - timedelta(days=1)
    sf.write_text(
        json.dumps(
            {
                "sessions": [
                    {
                        "started": yesterday.isoformat(timespec="seconds"),
                        "ended": (yesterday + timedelta(minutes=25)).isoformat(timespec="seconds"),
                        "duration_secs": 1500,
                        "label": "old",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    append_session(tmp_path, task_label="new", duration_secs=1500)
    rows = load_recent_sessions(tmp_path, limit=10)

    assert len(rows) == 1
    assert rows[0]["label"] == "new"


def test_parse_session_time_range_accepts_hh_mm_dash_hh_mm():
    start, end = parse_session_time_range("09:00 - 10:30")

    assert start == "09:00"
    assert end == "10:30"


def test_insert_update_delete_session_manual(tmp_path: Path):
    insert_session_manual(tmp_path, start_hm="09:00", end_hm="09:45", label="focus")
    rows = load_recent_sessions(tmp_path, limit=10)

    assert len(rows) == 1
    assert rows[0]["label"] == "focus"
    assert rows[0]["duration_secs"] == 45 * 60

    update_session_at(tmp_path, 0, start_hm="10:00", end_hm="11:00", label="edited")
    rows = load_recent_sessions(tmp_path, limit=10)

    assert rows[0]["label"] == "edited"
    assert rows[0]["duration_secs"] == 3600

    delete_session_at(tmp_path, 0)
    rows = load_recent_sessions(tmp_path, limit=10)

    assert rows == []


def test_insert_update_delete_event_manual(tmp_path: Path):
    from todo.core.dashboard_io import CalendarEvent, delete_event_at, load_events, update_event_at

    iso_day = "2026-05-27"
    insert_event(
        tmp_path,
        iso_day,
        CalendarEvent("09:00", "09:45", "standup", "green"),
    )
    events = load_events(tmp_path, iso_day)

    assert len(events) == 1
    assert events[0].title == "standup"

    update_event_at(
        tmp_path,
        iso_day,
        0,
        CalendarEvent("10:00", "11:00", "review", "blue"),
    )
    events = load_events(tmp_path, iso_day)

    assert events[0].title == "review"
    assert events[0].color == "blue"

    delete_event_at(tmp_path, iso_day, 0)
    events = load_events(tmp_path, iso_day)

    assert events == []
