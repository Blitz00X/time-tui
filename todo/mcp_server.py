"""
MCP server for time-tui.

Exposes the same Markdown-backed data store the TUI and CLI use, as MCP
tools. Lets an MCP-capable agent (e.g. an LLM running with tool access) read
and write tasks, calendar events, and sessions without subprocess overhead
or text-format parsing on the agent side.

Run via the installed entry point::

    todo-mcp --root /path/to/project
    todo-mcp --root /path/to/project --transport streamable-http
    # or:
    TIME_TUI_ROOT=/path/to/project todo-mcp

The server uses ``stdio`` transport by default (matches most local MCP
clients). ``streamable-http`` is available for remote clients and tunnels.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .core import calendar_parser, sessions_parser, storage
from .core.models import Task
from .core.parser import build_markdown, parse_tasks


# ── server-wide state ────────────────────────────────────────────────────────

mcp = FastMCP("time-tui")
_PROJECT_ROOT: Path | None = None


def _root() -> Path:
    if _PROJECT_ROOT is None:
        raise RuntimeError("project root not configured; pass --root or set TIME_TUI_ROOT")
    return _PROJECT_ROOT


def _namespace_path(namespace: str) -> Path:
    return storage.namespaces_dir(_root()) / namespace / storage._FILENAME  # noqa: SLF001


def _ensure_namespace(namespace: str) -> Path:
    storage.create_namespace(_root(), namespace)
    return _namespace_path(namespace)


def _load_tasks(namespace: str) -> list[Task]:
    path = _ensure_namespace(namespace)
    return storage.load_tasks(path)


def _save_tasks(namespace: str, tasks: list[Task]) -> None:
    path = _ensure_namespace(namespace)
    storage.locked_write_to(path, lambda _cur: build_markdown(tasks), root=_root())


def _task_to_dict(t: Task) -> dict[str, Any]:
    return {"text": t.text, "indent": t.indent, "done": t.done}


def _find_parent(tasks: list[Task], parent_text: str) -> int:
    matches = [i for i, t in enumerate(tasks) if t.text.strip() == parent_text.strip()]
    if not matches:
        raise KeyError(f"parent task not found: {parent_text!r}")
    if len(matches) > 1:
        matches.sort(key=lambda i: tasks[i].indent)
    return matches[0]


def _find_task(tasks: list[Task], task_text: str) -> int:
    matches = [i for i, t in enumerate(tasks) if t.text.strip() == task_text.strip()]
    if not matches:
        raise KeyError(f"task not found: {task_text!r}")
    if len(matches) > 1:
        matches.sort(key=lambda i: tasks[i].indent)
    return matches[0]


def _load_calendar() -> dict[str, list[calendar_parser.CalendarEvent]]:
    path = storage.calendar_path(_root())
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return calendar_parser.parse_calendar(text)


def _save_calendar(cal: dict[str, list[calendar_parser.CalendarEvent]]) -> None:
    path = storage.calendar_path(_root())
    storage.locked_write_to(
        path, lambda _cur: calendar_parser.build_calendar(cal), root=_root()
    )


def _load_sessions() -> dict[str, list[sessions_parser.SessionEntry]]:
    path = storage.sessions_md_path(_root())
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    return sessions_parser.parse_sessions(text)


def _save_sessions(data: dict[str, list[sessions_parser.SessionEntry]]) -> None:
    path = storage.sessions_md_path(_root())
    storage.locked_write_to(
        path, lambda _cur: sessions_parser.build_sessions(data), root=_root()
    )


def _compute_end(start_hm: str, duration_min: int) -> str:
    sh, sm = (int(x) for x in calendar_parser.normalize_hm(start_hm).split(":"))
    total = sh * 60 + sm + duration_min
    eh, em = divmod(total, 60)
    eh = eh % 24
    return f"{eh:02d}:{em:02d}"


# ── task tools ───────────────────────────────────────────────────────────────

@mcp.tool()
def task_list(namespace: str = "main") -> dict[str, Any]:
    """List all tasks in a namespace. Returns ``{"namespace": ..., "tasks": [...]}``.

    Each task is ``{"text", "indent", "done"}``. Wrapped in a dict so the MCP
    client receives a single structured payload rather than a fragmented
    list of text blocks.
    """
    tasks = _load_tasks(namespace)
    return {"namespace": namespace, "tasks": [_task_to_dict(t) for t in tasks]}


@mcp.tool()
def task_add(namespace: str, text: str) -> dict[str, Any]:
    """Add a top-level task to a namespace. Returns the created task."""
    tasks = _load_tasks(namespace)
    new = Task(text=text.strip(), indent=0, done=False)
    tasks.append(new)
    _save_tasks(namespace, tasks)
    return _task_to_dict(new)


@mcp.tool()
def task_add_child(namespace: str, parent: str, text: str) -> dict[str, Any]:
    """Add a child task under a parent (matched by exact text).

    The child inherits ``parent.indent + 1``. Returns the created child.
    """
    tasks = _load_tasks(namespace)
    idx = _find_parent(tasks, parent)
    new = Task(text=text.strip(), indent=tasks[idx].indent + 1, done=False)
    tasks.insert(idx + 1, new)
    _save_tasks(namespace, tasks)
    return _task_to_dict(new)


@mcp.tool()
def task_done(namespace: str, task: str) -> bool:
    """Mark a task as done. Returns True if state changed, False if already done."""
    tasks = _load_tasks(namespace)
    idx = _find_task(tasks, task)
    if tasks[idx].done:
        return False
    tasks[idx].done = True
    _save_tasks(namespace, tasks)
    return True


@mcp.tool()
def task_rename(namespace: str, task: str, new_text: str) -> str:
    """Rename a task. Returns the new text."""
    tasks = _load_tasks(namespace)
    idx = _find_task(tasks, task)
    tasks[idx].text = new_text.strip()
    _save_tasks(namespace, tasks)
    return tasks[idx].text


@mcp.tool()
def task_delete(namespace: str, task: str, cascade: bool = False) -> int:
    """Delete a task. With ``cascade=True`` also removes descendants.

    Returns the count of removed items.
    """
    tasks = _load_tasks(namespace)
    idx = _find_task(tasks, task)
    base = tasks[idx].indent
    end = idx + 1
    if cascade:
        while end < len(tasks) and tasks[end].indent > base:
            end += 1
    removed = end - idx
    del tasks[idx:end]
    _save_tasks(namespace, tasks)
    return removed


@mcp.tool()
def task_move(namespace: str, task: str, to_namespace: str) -> bool:
    """Move a task (and its descendants, if any) to a different namespace."""
    tasks = _load_tasks(namespace)
    idx = _find_task(tasks, task)
    base = tasks[idx].indent
    end = idx + 1
    while end < len(tasks) and tasks[end].indent > base:
        end += 1
    chunk = tasks[idx:end]
    del tasks[idx:end]
    _save_tasks(namespace, tasks)

    dest = _load_tasks(to_namespace)
    # Renormalize indent so chunk sits at root in destination.
    indent_offset = -chunk[0].indent
    for t in chunk:
        t.indent += indent_offset
    dest.extend(chunk)
    _save_tasks(to_namespace, dest)
    return True


# ── calendar tools ───────────────────────────────────────────────────────────

@mcp.tool()
def calendar_today() -> dict[str, Any]:
    """List events for today. Returns ``{"date": ..., "events": [...]}``."""
    return calendar_list(date.today().isoformat())


@mcp.tool()
def calendar_list(date_str: str) -> dict[str, Any]:
    """List events on a date (YYYY-MM-DD). Returns ``{"date": ..., "events": [...]}``.

    Each event is ``{"date", "start", "end", "title", "color", "duration_min"}``.
    """
    iso = calendar_parser.normalize_iso_day(date_str)
    cal = _load_calendar()
    out: list[dict[str, Any]] = []
    for ev in cal.get(iso, []):
        out.append({
            "date": iso,
            "start": ev.start,
            "end": ev.end,
            "title": ev.title,
            "color": ev.color,
            "duration_min": ev.duration_min(),
        })
    return {"date": iso, "events": out}


@mcp.tool()
def calendar_add(
    date_str: str,
    start: str,
    duration_min: int,
    title: str,
    color: str = "green",
) -> dict[str, Any]:
    """Add a single calendar event. Returns the created event."""
    iso = calendar_parser.normalize_iso_day(date_str)
    event = calendar_parser.make_event(
        start_hm=start,
        end_hm=_compute_end(start, duration_min),
        title=title,
        color=color,
    )
    cal = _load_calendar()
    cal.setdefault(iso, []).append(event)
    cal[iso].sort(key=lambda e: e.start)
    _save_calendar(cal)
    return {
        "date": iso,
        "start": event.start,
        "end": event.end,
        "title": event.title,
        "color": event.color,
        "duration_min": event.duration_min(),
    }


@mcp.tool()
def calendar_add_bulk(
    date_str: str,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Add multiple events on a date at once.

    Each event dict must have ``start`` (HH:MM), ``duration_min`` (int),
    and ``title`` (str). Returns ``{"added": N}``.
    """
    iso = calendar_parser.normalize_iso_day(date_str)
    cal = _load_calendar()
    new_events: list[calendar_parser.CalendarEvent] = []
    for i, raw in enumerate(events):
        try:
            start = raw["start"]
            duration = int(raw["duration_min"])
            title = raw["title"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"event #{i}: missing/invalid fields ({exc})") from exc
        new_events.append(
            calendar_parser.make_event(
                start_hm=start,
                end_hm=_compute_end(start, duration),
                title=title,
            )
        )
    cal.setdefault(iso, []).extend(new_events)
    cal[iso].sort(key=lambda e: e.start)
    _save_calendar(cal)
    return {"date": iso, "added": len(new_events)}


@mcp.tool()
def calendar_delete(date_str: str, event_id: int) -> bool:
    """Delete an event by its index on a given date."""
    iso = calendar_parser.normalize_iso_day(date_str)
    cal = _load_calendar()
    events = cal.get(iso, [])
    if event_id < 0 or event_id >= len(events):
        raise IndexError(f"event {event_id} not found on {iso}")
    events.pop(event_id)
    if not events:
        del cal[iso]
    _save_calendar(cal)
    return True


@mcp.tool()
def calendar_move(date_str: str, event_id: int, to_start: str) -> dict[str, Any]:
    """Move an event to a different start time on the same day."""
    iso = calendar_parser.normalize_iso_day(date_str)
    cal = _load_calendar()
    events = cal.get(iso, [])
    if event_id < 0 or event_id >= len(events):
        raise IndexError(f"event {event_id} not found on {iso}")
    ev = events[event_id]
    new_start = calendar_parser.normalize_hm(to_start)
    duration = ev.duration_min()
    sh, sm = (int(x) for x in new_start.split(":"))
    eh, em = divmod(sm + duration, 60)
    eh = (sh + eh) % 24
    ev.start = new_start
    ev.end = f"{eh:02d}:{em:02d}"
    events.sort(key=lambda e: e.start)
    _save_calendar(cal)
    return {
        "date": iso,
        "start": ev.start,
        "end": ev.end,
        "title": ev.title,
    }


# ── session tools ────────────────────────────────────────────────────────────

@mcp.tool()
def session_today() -> dict[str, Any]:
    """List sessions for today. Returns ``{"date": ..., "sessions": [...]}``."""
    return session_log(date.today().isoformat())


@mcp.tool()
def session_log(date_str: str) -> dict[str, Any]:
    """List session entries on a date (YYYY-MM-DD), newest first.

    Returns ``{"date": ..., "sessions": [...]}``. Each entry is
    ``{"date", "start", "end", "label", "duration_min"}``.
    """
    iso = sessions_parser.normalize_iso_day(date_str)
    data = _load_sessions()
    sessions = [
        {
            "date": iso,
            "start": e.start,
            "end": e.end,
            "label": e.label,
            "duration_min": e.duration_min(),
        }
        for e in data.get(iso, [])
    ]
    return {"date": iso, "sessions": sessions}


@mcp.tool()
def session_add(date_str: str, start: str, end: str, label: str = "session") -> dict[str, Any]:
    """Log a manual session entry."""
    iso = sessions_parser.normalize_iso_day(date_str)
    entry = sessions_parser.make_entry(start_hm=start, end_hm=end, label=label)
    data = _load_sessions()
    data.setdefault(iso, []).append(entry)
    data[iso].sort(key=lambda e: e.start, reverse=True)
    _save_sessions(data)
    return {
        "date": iso,
        "start": entry.start,
        "end": entry.end,
        "label": entry.label,
        "duration_min": entry.duration_min(),
    }


# ── namespace tools ──────────────────────────────────────────────────────────

@mcp.tool()
def namespace_list() -> dict[str, Any]:
    """List all namespaces. Returns ``{"namespaces": [...]}``."""
    return {"namespaces": storage.list_namespaces(_root())}


@mcp.tool()
def namespace_create(name: str) -> bool:
    """Create a new namespace. Idempotent."""
    storage.create_namespace(_root(), name)
    return True


# ── entry point ──────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="time-tui MCP server.")
    parser.add_argument(
        "--root", type=Path, default=None,
        help="Project root (defaults to TIME_TUI_ROOT env or CWD).",
    )
    parser.add_argument(
        "--transport", choices=("stdio", "streamable-http"), default="stdio",
        help="MCP transport (default: stdio).",
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="HTTP bind host (streamable-http only; default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="HTTP bind port (streamable-http only; default: 8000).",
    )
    parser.add_argument(
        "--http-path", default="/mcp",
        help="MCP endpoint path (streamable-http only; default: /mcp).",
    )
    args = parser.parse_args(argv)

    global _PROJECT_ROOT
    env_root = os.environ.get("TIME_TUI_ROOT")
    root: Path
    if args.root:
        root = args.root.resolve()
    elif env_root:
        root = Path(env_root).expanduser().resolve()
    else:
        root = Path.cwd().resolve()

    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    _PROJECT_ROOT = root
    storage.ensure_todo_dir(root)

    if args.transport == "streamable-http":
        if not 1 <= args.port <= 65535:
            parser.error("--port must be between 1 and 65535")
        if not args.http_path.startswith("/"):
            parser.error("--http-path must start with '/'")
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.settings.streamable_http_path = args.http_path

    mcp.run(transport=args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())