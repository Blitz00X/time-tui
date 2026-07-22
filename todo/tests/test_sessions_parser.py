"""Unit tests for the session log Markdown parser."""
from __future__ import annotations

import pytest

from todo.core.sessions_parser import (
    SessionEntry,
    build_sessions,
    make_entry,
    normalize_hm,
    normalize_iso_day,
    parse_sessions,
    parse_session_line,
)


SAMPLE = """# 2026-07-21
- 14:30–15:00 kod yaz
- 15:05–15:15 mola

# 2026-07-22
- 09:00–12:00 BİGG çalışması
"""


def test_parse_basic_sample() -> None:
    out = parse_sessions(SAMPLE)
    assert set(out.keys()) == {"2026-07-21", "2026-07-22"}
    assert len(out["2026-07-21"]) == 2
    # Newest-first within a day: 15:05 entry comes before 14:30.
    assert out["2026-07-21"][0].label == "mola"
    assert out["2026-07-21"][1].label == "kod yaz"


def test_parse_sorts_within_day_newest_first() -> None:
    """Sessions within a day come out newest-first (matches dashboard order)."""
    out = parse_sessions(SAMPLE)
    starts = [e.start for e in out["2026-07-21"]]
    assert starts == ["15:05", "14:30"]


def test_parse_skips_invalid_lines() -> None:
    text = "# 2026-07-21\n- foo bar baz\n- 09:00–10:00 valid\n"
    out = parse_sessions(text)
    assert len(out["2026-07-21"]) == 1


def test_parse_skips_zero_duration() -> None:
    text = "# 2026-07-21\n- 09:00–09:00 zero\n- 10:00–11:00 valid\n"
    out = parse_sessions(text)
    assert len(out["2026-07-21"]) == 1


def test_build_roundtrip() -> None:
    out = parse_sessions(SAMPLE)
    rebuilt = build_sessions(out)
    out2 = parse_sessions(rebuilt)
    assert out == out2


def test_make_entry_validates_inputs() -> None:
    e = make_entry(start_hm="09:00", end_hm="10:00", label="x")
    assert e.duration_min() == 60


def test_make_entry_defaults_label() -> None:
    e = make_entry(start_hm="09:00", end_hm="10:00")
    assert e.label == "session"


def test_make_entry_rejects_inverted_range() -> None:
    with pytest.raises(ValueError):
        make_entry(start_hm="10:00", end_hm="09:00")


def test_normalize_hm_invalid() -> None:
    with pytest.raises(ValueError):
        normalize_hm("25:00")
    with pytest.raises(ValueError):
        normalize_hm("9:99")


def test_normalize_iso_day_invalid() -> None:
    with pytest.raises(ValueError):
        normalize_iso_day("2026-13-01")


def test_parse_session_line_returns_none_for_non_event() -> None:
    assert parse_session_line("hello") is None
    assert parse_session_line("") is None