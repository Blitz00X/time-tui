"""Migration test: legacy JSON -> Markdown format."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from todo.core import storage


def _write_json(p: Path, payload: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_migrate_creates_markdown_files(tmp_path: Path) -> None:
    legacy = tmp_path / ".time-tui"
    legacy.mkdir()
    cal_data = {
        "2026-07-25": [
            {"start": "09:00", "end": "10:00", "title": "jüriler", "color": "blue"},
            {"start": "14:00", "end": "15:00", "title": "prova", "color": "green"},
        ]
    }
    _write_json(legacy / "calendar.json", cal_data)
    sessions_data = {
        "sessions": [
            {
                "started": "2026-07-21T14:30:00",
                "ended": "2026-07-21T15:00:00",
                "label": "kod yaz",
                "duration_secs": 1800,
            }
        ]
    }
    _write_json(legacy / "sessions.json", sessions_data)

    r = subprocess.run(
        [sys.executable, "-m", "todo.cli.migrate", "--root", str(tmp_path)],
        capture_output=True, text=True, timeout=15,
    )
    assert r.returncode == 0, r.stderr

    cal_md = storage.calendar_path(tmp_path)
    assert cal_md.exists()
    text = cal_md.read_text(encoding="utf-8")
    assert "# 2026-07-25" in text
    assert "09:00–10:00 jüriler" in text
    assert "14:00–15:00 prova" in text

    ses_md = storage.sessions_md_path(tmp_path)
    assert ses_md.exists()
    text = ses_md.read_text(encoding="utf-8")
    assert "# 2026-07-21" in text
    assert "14:30–15:00 kod yaz" in text

    # Originals are renamed to .bak
    assert (legacy / "calendar.json.bak").exists()
    assert (legacy / "sessions.json.bak").exists()


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    legacy = tmp_path / ".time-tui"
    legacy.mkdir()
    _write_json(legacy / "calendar.json", {"2026-07-25": [{"start": "09:00", "end": "10:00", "title": "x"}]})

    # First migration writes .md and renames json to .bak
    subprocess.run([sys.executable, "-m", "todo.cli.migrate", "--root", str(tmp_path)],
                   check=True, capture_output=True, timeout=15)
    cal_md = storage.calendar_path(tmp_path)
    original = cal_md.read_text(encoding="utf-8")

    # Second migration without --force: should skip because .md exists
    r = subprocess.run([sys.executable, "-m", "todo.cli.migrate", "--root", str(tmp_path)],
                       capture_output=True, text=True, timeout=15)
    assert "skipped" in r.stdout
    # Markdown content should be unchanged
    assert cal_md.read_text(encoding="utf-8") == original


def test_migrate_force_overwrites(tmp_path: Path) -> None:
    legacy = tmp_path / ".time-tui"
    legacy.mkdir()
    _write_json(legacy / "calendar.json", {"2026-07-25": [{"start": "09:00", "end": "10:00", "title": "x"}]})

    # Pre-create a manual calendar.md so migration would skip without --force
    storage.ensure_todo_dir(tmp_path)
    storage.calendar_path(tmp_path).write_text("manual\n", encoding="utf-8")

    r = subprocess.run([sys.executable, "-m", "todo.cli.migrate", "--root", str(tmp_path), "--force"],
                       capture_output=True, text=True, timeout=15)
    assert r.returncode == 0, r.stderr
    text = storage.calendar_path(tmp_path).read_text(encoding="utf-8")
    assert "# 2026-07-25" in text


def test_migrate_handles_missing_legacy_files(tmp_path: Path) -> None:
    """If neither json file exists, migration is a no-op (no errors)."""
    r = subprocess.run([sys.executable, "-m", "todo.cli.migrate", "--root", str(tmp_path)],
                       capture_output=True, text=True, timeout=15)
    assert r.returncode == 0
    assert "missing, skipped" in r.stdout