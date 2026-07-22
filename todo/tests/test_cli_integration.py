"""End-to-end CLI tests against a temporary project root."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A fresh project root with a .todo/ directory."""
    (tmp_path / ".todo").mkdir()
    return tmp_path


def run_cli(project: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "todo.cli", "--root", str(project), *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(project),
        input=stdin,
        timeout=30,
    )


def test_task_add_and_list(project: Path) -> None:
    r = run_cli(project, "task", "add", "--ns", "main", "--text", "alışveriş yap")
    assert r.returncode == 0, r.stderr
    r = run_cli(project, "task", "list", "--ns", "main")
    assert "alışveriş yap" in r.stdout


def test_task_add_child_under_parent(project: Path) -> None:
    """The headline scenario: add a child under an existing task."""
    run_cli(project, "task", "add", "--ns", "bigg", "--text", "jüri sunumu prova et")
    r = run_cli(
        project,
        "task", "add-child",
        "--ns", "bigg",
        "--parent", "jüri sunumu prova et",
        "--text", "slayt deck hazırla",
    )
    assert r.returncode == 0, r.stderr

    r = run_cli(project, "task", "list", "--ns", "bigg")
    lines = r.stdout.splitlines()
    assert any("jüri sunumu prova et" in line for line in lines)
    # Child should be indented under parent.
    parent_idx = next(i for i, line in enumerate(lines) if "jüri sunumu prova et" in line)
    next_line = lines[parent_idx + 1]
    assert "slayt deck hazırla" in next_line
    # The child line should start with whitespace (indent > 0).
    assert next_line != next_line.lstrip()


def test_task_done_marks_done(project: Path) -> None:
    run_cli(project, "task", "add", "--ns", "main", "--text", "foo")
    r = run_cli(project, "task", "done", "--ns", "main", "--task", "foo")
    assert r.returncode == 0
    r = run_cli(project, "task", "list", "--ns", "main")
    assert "[x] foo" in r.stdout


def test_task_delete_cascade(project: Path) -> None:
    run_cli(project, "task", "add", "--ns", "main", "--text", "parent")
    run_cli(
        project,
        "task", "add-child",
        "--ns", "main", "--parent", "parent", "--text", "child1",
    )
    run_cli(
        project,
        "task", "add-child",
        "--ns", "main", "--parent", "parent", "--text", "child2",
    )
    r = run_cli(
        project,
        "task", "delete",
        "--ns", "main", "--task", "parent", "--cascade",
    )
    assert r.returncode == 0
    r = run_cli(project, "task", "list", "--ns", "main")
    assert "parent" not in r.stdout
    assert "child1" not in r.stdout
    assert "child2" not in r.stdout


def test_task_list_json_format(project: Path) -> None:
    run_cli(project, "task", "add", "--ns", "main", "--text", "alpha")
    r = run_cli(project, "task", "list", "--ns", "main", "--json")
    data = json.loads(r.stdout)
    assert isinstance(data, list)
    texts = [row["text"] for row in data]
    assert "alpha" in texts


def test_namespace_create_and_list(project: Path) -> None:
    r = run_cli(project, "namespace", "create", "--name", "bigg")
    assert r.returncode == 0
    r = run_cli(project, "namespace", "list", "--json")
    assert "bigg" in json.loads(r.stdout)


def test_calendar_add_single(project: Path) -> None:
    r = run_cli(
        project, "calendar", "add",
        "--date", "2026-07-25",
        "--start", "09:00",
        "--duration", "60",
        "--text", "jüriler",
    )
    assert r.returncode == 0, r.stderr
    r = run_cli(project, "calendar", "list", "--date", "2026-07-25")
    assert "09:00–10:00" in r.stdout
    assert "jüriler" in r.stdout


def test_calendar_add_bulk(project: Path) -> None:
    """The headline scenario: 'put these on July 25'."""
    bulk_input = "09:00 60 jüriler\n14:00 60 prova\n19:00 60 sunum\n"
    r = run_cli(
        project, "calendar", "add-bulk",
        "--date", "2026-07-25",
        stdin=bulk_input,
    )
    assert r.returncode == 0, r.stderr

    # Verify all three events landed.
    r = run_cli(project, "calendar", "list", "--date", "2026-07-25")
    assert "jüriler" in r.stdout
    assert "prova" in r.stdout
    assert "sunum" in r.stdout
    # And they're sorted by start time.
    lines = [l for l in r.stdout.splitlines() if "–" in l]
    assert "09:00" in lines[0]
    assert "14:00" in lines[1]
    assert "19:00" in lines[2]


def test_calendar_today_uses_today(project: Path) -> None:
    from datetime import date
    today = date.today().isoformat()
    run_cli(
        project, "calendar", "add",
        "--date", today, "--start", "10:00", "--duration", "30", "--text", "şimdi",
    )
    r = run_cli(project, "calendar", "today")
    assert "şimdi" in r.stdout


def test_calendar_delete_removes_event(project: Path) -> None:
    run_cli(
        project, "calendar", "add",
        "--date", "2026-07-25", "--start", "09:00", "--duration", "30", "--text", "x",
    )
    r = run_cli(project, "calendar", "delete", "--date", "2026-07-25", "--id", "0")
    assert r.returncode == 0
    r = run_cli(project, "calendar", "list", "--date", "2026-07-25")
    assert "x" not in r.stdout


def test_session_log_and_list(project: Path) -> None:
    run_cli(
        project, "session", "add",
        "--date", "2026-07-21",
        "--start", "14:30", "--end", "15:00",
        "--label", "kod yaz",
    )
    r = run_cli(project, "session", "log", "--date", "2026-07-21")
    assert "14:30–15:00" in r.stdout
    assert "kod yaz" in r.stdout


def test_cli_writes_atomically(project: Path) -> None:
    """Files written by CLI should land in the expected Markdown paths."""
    run_cli(project, "calendar", "add",
            "--date", "2026-07-25", "--start", "09:00",
            "--duration", "30", "--text", "x")
    cal_md = project / ".todo" / "calendar.md"
    assert cal_md.exists()
    content = cal_md.read_text(encoding="utf-8")
    assert "# 2026-07-25" in content
    assert "- 09:00–09:30 x" in content


def test_cli_respects_invalid_inputs(project: Path) -> None:
    r = run_cli(project, "calendar", "add",
                "--date", "2026-07-25", "--start", "10:00",
                "--duration", "30", "--text", "")
    assert r.returncode != 0
    assert "Title is required" in r.stderr


def test_cli_error_on_unknown_task(project: Path) -> None:
    r = run_cli(
        project, "task", "add-child",
        "--ns", "main", "--parent", "nonexistent", "--text", "child",
    )
    assert r.returncode != 0
    assert "parent task not found" in r.stderr