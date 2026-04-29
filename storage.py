"""
File I/O layer for tui-md-todo.

Handles: initialization, reading, atomic writing.
"""
from __future__ import annotations
import os
import shutil
import tempfile
from pathlib import Path
from .models import Task
from .parser import parse_tasks, build_markdown, DEFAULT_TEMPLATE

_FILENAME = "tasks.md"


def _tasks_path(directory: Path | None = None) -> Path:
    base = directory or Path.cwd()
    return base / _FILENAME


def init_if_missing(directory: Path | None = None) -> Path:
    """Create tasks.md with default template if it does not exist."""
    path = _tasks_path(directory)
    if not path.exists():
        path.write_text(DEFAULT_TEMPLATE, encoding="utf-8")
    return path


def load_tasks(directory: Path | None = None) -> tuple[list[Task], Path]:
    """Read and parse tasks.md; return (tasks, path)."""
    path = init_if_missing(directory)
    content = path.read_text(encoding="utf-8")
    tasks = parse_tasks(content)
    return tasks, path


def save_tasks(tasks: list[Task], path: Path) -> None:
    """Atomically write task list back to *path*."""
    markdown = build_markdown(tasks)
    _atomic_write(path, markdown)


def _atomic_write(path: Path, content: str) -> None:
    """Write to a temp file then rename — prevents corruption on crash."""
    dir_ = path.parent
    fd, tmp_path = tempfile.mkstemp(dir=dir_, prefix=".tasks_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        shutil.move(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
