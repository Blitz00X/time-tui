"""Unit tests for the calendar Markdown parser."""
from __future__ import annotations

from datetime import date

import pytest

from todo.core.calendar_parser import (
    CalendarEvent,
    build_calendar,
    make_event,
    normalize_hm,
    normalize_iso_day,
    parse_calendar,
    parse_event_line,
)


SAMPLE = """# 2026-07-25
- 09:00–10:00 jüriler
- 14:00–15:00 prova
- 19:00–20:00 sunum

# 2026-07-26
- 10:00–11:30 mentor toplantısı
"""


def test_parse_basic_sample() -> None:
    cal = parse_calendar(SAMPLE)
    assert set(cal.keys()) == {"2026-07-25", "2026-07-26"}
    assert len(cal["2026-07-25"]) == 3
    assert cal["2026-07-25"][0].title == "jüriler"
    assert cal["2026-07-25"][2].title == "sunum"


def test_parse_sorts_within_day() -> None:
    cal = parse_calendar(SAMPLE)
    times = [(e.start, e.end) for e in cal["2026-07-25"]]
    assert times == sorted(times, key=lambda t: int(t[0].split(":")[0]) * 60 + int(t[0].split(":")[1]))


def test_parse_skips_blank_lines_and_comments() -> None:
    text = "# 2026-07-25\n\n   \n- 09:00–10:00 test\n\n"
    cal = parse_calendar(text)
    assert list(cal.keys()) == ["2026-07-25"]
    assert cal["2026-07-25"][0].title == "test"


def test_parse_ignores_lines_before_first_day() -> None:
    text = "- 09:00–10:00 orphan\n# 2026-07-25\n- 10:00–11:00 ok\n"
    cal = parse_calendar(text)
    assert "orphan" not in str(cal)
    assert cal["2026-07-25"][0].title == "ok"


def test_parse_ignores_invalid_event_lines() -> None:
    text = "# 2026-07-25\n- bu bir event değil\n- 09:00–10:00 valid\n"
    cal = parse_calendar(text)
    assert len(cal["2026-07-25"]) == 1
    assert cal["2026-07-25"][0].title == "valid"


def test_parse_skips_zero_or_negative_duration() -> None:
    text = "# 2026-07-25\n- 09:00–09:00 same-time\n- 10:00–09:00 inverted\n- 11:00–12:00 ok\n"
    cal = parse_calendar(text)
    assert len(cal["2026-07-25"]) == 1
    assert cal["2026-07-25"][0].title == "ok"


def test_build_roundtrip() -> None:
    cal = parse_calendar(SAMPLE)
    out = build_calendar(cal)
    cal2 = parse_calendar(out)
    assert cal == cal2


def test_build_empty() -> None:
    assert build_calendar({}) == "\n"


def test_build_sorts_and_orders_days() -> None:
    cal = {
        "2026-07-26": [CalendarEvent("10:00", "11:00", "x", "green")],
        "2026-07-25": [CalendarEvent("09:00", "10:00", "y", "green")],
    }
    out = build_calendar(cal)
    assert out.index("2026-07-25") < out.index("2026-07-26")


def test_normalize_iso_day_valid() -> None:
    assert normalize_iso_day("2026-07-25") == "2026-07-25"


def test_normalize_iso_day_invalid() -> None:
    with pytest.raises(ValueError):
        normalize_iso_day("2026-7-25")
    with pytest.raises(ValueError):
        normalize_iso_day("2026/07/25")
    with pytest.raises(ValueError):
        normalize_iso_day("not-a-date")


def test_normalize_hm_valid() -> None:
    assert normalize_hm("9:00") == "09:00"
    assert normalize_hm("23:59") == "23:59"


def test_normalize_hm_invalid() -> None:
    with pytest.raises(ValueError):
        normalize_hm("24:00")
    with pytest.raises(ValueError):
        normalize_hm("9:60")
    with pytest.raises(ValueError):
        normalize_hm("abc")


def test_make_event_validates_inputs() -> None:
    ev = make_event(start_hm="09:00", end_hm="10:00", title="x", color="blue")
    assert ev.start == "09:00"
    assert ev.end == "10:00"
    assert ev.duration_min() == 60


def test_make_event_rejects_bad_color() -> None:
    with pytest.raises(ValueError):
        make_event(start_hm="09:00", end_hm="10:00", title="x", color="red")


def test_make_event_rejects_end_before_start() -> None:
    with pytest.raises(ValueError):
        make_event(start_hm="10:00", end_hm="09:00", title="x")


def test_make_event_requires_title() -> None:
    with pytest.raises(ValueError):
        make_event(start_hm="09:00", end_hm="10:00", title="   ")


def test_parse_event_line_returns_none_on_garbage() -> None:
    assert parse_event_line("hello world") is None
    assert parse_event_line("") is None