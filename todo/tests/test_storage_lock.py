"""Tests for the storage layer's lock + atomic write helpers."""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pytest

from todo.core import storage


def test_ensure_todo_dir_creates_dir(tmp_path: Path) -> None:
    td = storage.ensure_todo_dir(tmp_path)
    assert td.is_dir()
    assert td.name == ".todo"


def test_lock_path_inside_todo_dir(tmp_path: Path) -> None:
    storage.ensure_todo_dir(tmp_path)
    p = storage.lock_path(tmp_path)
    assert p.parent.name == ".todo"
    assert p.name == "lock"


def test_calendar_and_sessions_paths(tmp_path: Path) -> None:
    storage.ensure_todo_dir(tmp_path)
    assert storage.calendar_path(tmp_path).name == "calendar.md"
    assert storage.sessions_md_path(tmp_path).name == "sessions.md"


def test_file_lock_acquires_and_releases(tmp_path: Path) -> None:
    with storage.file_lock(tmp_path):
        # Lock file should exist.
        assert storage.lock_path(tmp_path).exists()
    # After context exit, lock should be released (other process can take it).
    with storage.file_lock(tmp_path):
        pass


def test_lock_blocks_second_acquirer(tmp_path: Path) -> None:
    """A second acquirer in another thread should wait, then succeed after the first releases."""
    second_started = threading.Event()
    second_finished = threading.Event()
    second_acquired = threading.Event()

    def second_lock():
        second_started.set()
        with storage.file_lock(tmp_path, timeout=5.0):
            second_acquired.set()
        second_finished.set()

    t = threading.Thread(target=second_lock)
    t.start()
    # Give the second thread a moment to start, then we hold the lock.
    second_started.wait(timeout=1.0)
    with storage.file_lock(tmp_path):
        # Second thread should be blocked. We expect the timeout flag to fire
        # *after* we release, not before. So second_acquired must not be set yet.
        time.sleep(0.2)
        assert not second_acquired.is_set()
    # After our release, the second thread should acquire and finish.
    second_acquired.wait(timeout=2.0)
    second_finished.wait(timeout=2.0)
    t.join(timeout=2.0)


def test_lock_timeout_raises(tmp_path: Path) -> None:
    def holder():
        with storage.file_lock(tmp_path):
            time.sleep(0.5)

    t = threading.Thread(target=holder)
    t.start()
    time.sleep(0.05)  # ensure holder is in
    try:
        with pytest.raises(TimeoutError):
            with storage.file_lock(tmp_path, timeout=0.1):
                pass
    finally:
        t.join(timeout=2.0)


def test_locked_write_to_creates_and_writes(tmp_path: Path) -> None:
    storage.ensure_todo_dir(tmp_path)
    target = storage.calendar_path(tmp_path)
    assert not target.exists()

    storage.locked_write_to(target, lambda _cur: "hello world\n", root=tmp_path)
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "hello world\n"


def test_locked_write_to_passes_current_content(tmp_path: Path) -> None:
    storage.ensure_todo_dir(tmp_path)
    target = storage.calendar_path(tmp_path)
    target.write_text("old", encoding="utf-8")

    storage.locked_write_to(
        target,
        lambda cur: cur + " appended",
        root=tmp_path,
    )
    assert target.read_text(encoding="utf-8") == "old appended"


def test_locked_write_to_handles_missing_target(tmp_path: Path) -> None:
    """When target doesn't exist, mutate is called with empty string."""
    storage.ensure_todo_dir(tmp_path)
    target = storage.sessions_md_path(tmp_path)
    seen = []

    def mutate(cur: str) -> str:
        seen.append(cur)
        return "from-empty\n"

    storage.locked_write_to(target, mutate, root=tmp_path)
    assert seen == [""]
    assert target.read_text(encoding="utf-8") == "from-empty\n"


def test_locked_write_to_infers_root_from_path(tmp_path: Path) -> None:
    """If root is omitted, walk up to find the project root."""
    storage.ensure_todo_dir(tmp_path)
    target = storage.calendar_path(tmp_path)
    # Don't pass root; rely on inference.
    storage.locked_write_to(target, lambda _cur: "inferred\n")
    assert target.read_text(encoding="utf-8") == "inferred\n"


def test_file_mtime_returns_zero_for_missing(tmp_path: Path) -> None:
    p = tmp_path / "does-not-exist.md"
    assert storage.file_mtime(p) == 0.0


def test_file_mtime_returns_positive_for_existing(tmp_path: Path) -> None:
    p = tmp_path / "x.md"
    p.write_text("hi")
    assert storage.file_mtime(p) > 0.0