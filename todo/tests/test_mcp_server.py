"""MCP tool tests via in-process FastMCP server."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

import todo.mcp_server as srv


def _run(coro):
    """Run an async coroutine synchronously for test ergonomics."""
    return asyncio.run(coro)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Fresh project root with .todo/ dir, MCP server pointed at it."""
    (tmp_path / ".todo").mkdir()
    srv._PROJECT_ROOT = tmp_path  # type: ignore[assignment]
    yield tmp_path
    srv._PROJECT_ROOT = None  # type: ignore[assignment]


def _content(payload: Any) -> Any:
    """Extract content from an MCP tool result.

    FastMCP returns ``(content_list, structured_dict)``. Tests parse the
    structured payload when present (dict/list) and fall back to the JSON
    text in the content list otherwise.

    When FastMCP wraps a primitive (bool/int/str) into ``{"result": v}``,
    unwrap that single-key wrapper to keep test assertions clean.
    """
    if isinstance(payload, tuple) and len(payload) == 2:
        content_list, structured = payload
        if isinstance(structured, dict):
            if set(structured.keys()) == {"result"}:
                return structured["result"]
            return structured
        if isinstance(structured, list):
            return structured
        if content_list:
            text = getattr(content_list[0], "text", None)
            if text is not None:
                try:
                    return json.loads(text)
                except (json.JSONDecodeError, TypeError):
                    return text
        return structured
    if isinstance(payload, list) and payload and hasattr(payload[0], "text"):
        try:
            return json.loads(payload[0].text)
        except (json.JSONDecodeError, TypeError):
            return payload[0].text
    return payload


# ── list_tools smoke ──────────────────────────────────────────────────────────

def test_lists_all_expected_tools() -> None:
    tools = _run(srv.mcp.list_tools())
    names = {t.name for t in tools}
    expected = {
        "task_list", "task_add", "task_add_child", "task_done",
        "task_rename", "task_delete", "task_move",
        "calendar_list", "calendar_today", "calendar_add",
        "calendar_add_bulk", "calendar_delete", "calendar_move",
        "session_log", "session_today", "session_add",
        "namespace_list", "namespace_create",
    }
    missing = expected - names
    assert not missing, f"missing tools: {missing}"


# ── task tools ───────────────────────────────────────────────────────────────

def test_namespace_create_and_list(project: Path) -> None:
    out = _content(_run(srv.mcp.call_tool("namespace_create", {"name": "bigg"})))
    assert out is True
    out = _content(_run(srv.mcp.call_tool("namespace_list", {})))
    assert "bigg" in out["namespaces"]


def test_task_add_then_list(project: Path) -> None:
    _run(srv.mcp.call_tool("task_add", {"namespace": "main", "text": "foo"}))
    out = _content(_run(srv.mcp.call_tool("task_list", {"namespace": "main"})))
    assert out["namespace"] == "main"
    texts = [r["text"] for r in out["tasks"]]
    assert "foo" in texts


def test_task_add_child_under_parent(project: Path) -> None:
    """Headline scenario: 'add a child under an existing task'."""
    _run(srv.mcp.call_tool("task_add", {"namespace": "bigg", "text": "jüri sunumu prova et"}))
    out = _content(_run(
        srv.mcp.call_tool("task_add_child", {
            "namespace": "bigg",
            "parent": "jüri sunumu prova et",
            "text": "slayt deck hazırla",
        })
    ))
    assert out["text"] == "slayt deck hazırla"
    assert out["indent"] == 1

    out = _content(_run(srv.mcp.call_tool("task_list", {"namespace": "bigg"})))
    children = [r for r in out["tasks"] if r["text"] == "slayt deck hazırla"]
    assert children
    assert children[0]["indent"] == 1


def test_task_done_toggles_flag(project: Path) -> None:
    _run(srv.mcp.call_tool("task_add", {"namespace": "main", "text": "x"}))
    changed = _content(_run(srv.mcp.call_tool("task_done", {"namespace": "main", "task": "x"})))
    assert changed is True
    again = _content(_run(srv.mcp.call_tool("task_done", {"namespace": "main", "task": "x"})))
    assert again is False


def test_task_rename(project: Path) -> None:
    _run(srv.mcp.call_tool("task_add", {"namespace": "main", "text": "old"}))
    new_text = _content(_run(
        srv.mcp.call_tool("task_rename", {"namespace": "main", "task": "old", "new_text": "new"})
    ))
    assert new_text == "new"


def test_task_delete_cascade(project: Path) -> None:
    _run(srv.mcp.call_tool("task_add", {"namespace": "main", "text": "parent"}))
    _run(srv.mcp.call_tool("task_add_child", {"namespace": "main", "parent": "parent", "text": "c1"}))
    _run(srv.mcp.call_tool("task_add_child", {"namespace": "main", "parent": "parent", "text": "c2"}))
    removed = _content(_run(
        srv.mcp.call_tool("task_delete", {"namespace": "main", "task": "parent", "cascade": True})
    ))
    assert removed == 3
    out = _content(_run(srv.mcp.call_tool("task_list", {"namespace": "main"})))
    texts = [r["text"] for r in out["tasks"]]
    assert "parent" not in texts
    assert "c1" not in texts
    assert "c2" not in texts


def test_task_move_to_another_namespace(project: Path) -> None:
    _run(srv.mcp.call_tool("namespace_create", {"name": "dest"}))
    _run(srv.mcp.call_tool("task_add", {"namespace": "main", "text": "migrate-me"}))
    _run(srv.mcp.call_tool("task_move", {"namespace": "main", "task": "migrate-me", "to_namespace": "dest"}))
    src = _content(_run(srv.mcp.call_tool("task_list", {"namespace": "main"})))
    dst = _content(_run(srv.mcp.call_tool("task_list", {"namespace": "dest"})))
    assert "migrate-me" not in [r["text"] for r in src["tasks"]]
    assert "migrate-me" in [r["text"] for r in dst["tasks"]]


def test_task_add_child_missing_parent_raises(project: Path) -> None:
    """Tool should propagate KeyError when parent is not found."""
    with pytest.raises(Exception) as excinfo:
        _run(srv.mcp.call_tool("task_add_child", {
            "namespace": "main", "parent": "nope", "text": "child",
        }))
    assert "not found" in str(excinfo.value)


# ── calendar tools ───────────────────────────────────────────────────────────

def test_calendar_add_single(project: Path) -> None:
    out = _content(_run(
        srv.mcp.call_tool("calendar_add", {
            "date_str": "2026-07-25",
            "start": "09:00",
            "duration_min": 60,
            "title": "jüriler",
        })
    ))
    assert out["start"] == "09:00"
    assert out["end"] == "10:00"
    assert out["title"] == "jüriler"
    assert out["duration_min"] == 60


def test_calendar_add_bulk_headline_scenario(project: Path) -> None:
    """Headline scenario: 'put these on July 25'."""
    events = [
        {"start": "09:00", "duration_min": 60, "title": "jüriler"},
        {"start": "14:00", "duration_min": 60, "title": "prova"},
        {"start": "19:00", "duration_min": 60, "title": "sunum"},
    ]
    out = _content(_run(
        srv.mcp.call_tool("calendar_add_bulk", {"date_str": "2026-07-25", "events": events})
    ))
    assert out["added"] == 3

    listed = _content(_run(srv.mcp.call_tool("calendar_list", {"date_str": "2026-07-25"})))
    assert [e["title"] for e in listed["events"]] == ["jüriler", "prova", "sunum"]
    assert [e["start"] for e in listed["events"]] == ["09:00", "14:00", "19:00"]


def test_calendar_today_uses_today(project: Path) -> None:
    from datetime import date
    today = date.today().isoformat()
    _run(srv.mcp.call_tool("calendar_add", {
        "date_str": today, "start": "10:00", "duration_min": 30, "title": "now",
    }))
    out = _content(_run(srv.mcp.call_tool("calendar_today", {})))
    titles = [e["title"] for e in out["events"]]
    assert "now" in titles


def test_calendar_delete_removes_event(project: Path) -> None:
    _run(srv.mcp.call_tool("calendar_add", {
        "date_str": "2026-07-25", "start": "09:00", "duration_min": 30, "title": "x",
    }))
    deleted = _content(_run(
        srv.mcp.call_tool("calendar_delete", {"date_str": "2026-07-25", "event_id": 0})
    ))
    assert deleted is True
    listed = _content(_run(srv.mcp.call_tool("calendar_list", {"date_str": "2026-07-25"})))
    assert listed["events"] == []


def test_calendar_move_updates_start(project: Path) -> None:
    _run(srv.mcp.call_tool("calendar_add", {
        "date_str": "2026-07-25", "start": "09:00", "duration_min": 60, "title": "x",
    }))
    out = _content(_run(
        srv.mcp.call_tool("calendar_move", {"date_str": "2026-07-25", "event_id": 0, "to_start": "14:00"})
    ))
    assert out["start"] == "14:00"
    assert out["end"] == "15:00"


def test_calendar_add_rejects_bad_inputs(project: Path) -> None:
    """Empty title and inverted durations should be rejected by the parser."""
    with pytest.raises(Exception):
        _run(srv.mcp.call_tool("calendar_add", {
            "date_str": "2026-07-25", "start": "09:00", "duration_min": 0, "title": "x",
        }))


# ── session tools ────────────────────────────────────────────────────────────

def test_session_add_and_log(project: Path) -> None:
    out = _content(_run(
        srv.mcp.call_tool("session_add", {
            "date_str": "2026-07-21",
            "start": "14:30", "end": "15:00",
            "label": "kod yaz",
        })
    ))
    assert out["label"] == "kod yaz"
    assert out["duration_min"] == 30
    listed = _content(_run(srv.mcp.call_tool("session_log", {"date_str": "2026-07-21"})))
    assert listed["sessions"][0]["label"] == "kod yaz"


def test_session_today_returns_today(project: Path) -> None:
    from datetime import date
    today = date.today().isoformat()
    _run(srv.mcp.call_tool("session_add", {
        "date_str": today, "start": "10:00", "end": "10:30", "label": "focus",
    }))
    out = _content(_run(srv.mcp.call_tool("session_today", {})))
    assert any(e["label"] == "focus" for e in out["sessions"])


# ── end-to-end: scenario combined ────────────────────────────────────────────

def test_combined_scenario(project: Path) -> None:
    """Both headline scenarios in one session:
    - add events on July 25 (calendar)
    - add child under bigg task (task hierarchy)
    """
    _run(srv.mcp.call_tool("namespace_create", {"name": "bigg"}))
    _run(srv.mcp.call_tool("task_add", {"namespace": "bigg", "text": "jüri sunumu prova et"}))
    _run(srv.mcp.call_tool("task_add_child", {
        "namespace": "bigg",
        "parent": "jüri sunumu prova et",
        "text": "slayt deck hazırla",
    }))
    _run(srv.mcp.call_tool("calendar_add_bulk", {
        "date_str": "2026-07-25",
        "events": [
            {"start": "09:00", "duration_min": 60, "title": "jüriler"},
            {"start": "14:00", "duration_min": 60, "title": "prova"},
            {"start": "19:00", "duration_min": 60, "title": "sunum"},
        ],
    }))

    # Verify everything on disk.
    tasks_md = project / ".todo" / "bigg" / "tasks.md"
    assert tasks_md.exists()
    text = tasks_md.read_text(encoding="utf-8")
    assert "jüri sunumu prova et" in text
    assert "slayt deck hazırla" in text

    cal_md = project / ".todo" / "calendar.md"
    assert cal_md.exists()
    text = cal_md.read_text(encoding="utf-8")
    assert "09:00–10:00 jüriler" in text
    assert "14:00–15:00 prova" in text
    assert "19:00–20:00 sunum" in text