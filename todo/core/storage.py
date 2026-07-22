"""
File I/O for tui-md-todo.

Supports:
  - Root tasks.md  (the default namespace)
  - Namespace dirs: .todo/<name>/tasks.md
  - Calendar log: .todo/calendar.md (Markdown)
  - Session log:  .todo/sessions.md  (Markdown)

Locking: every read-modify-write that crosses the parser boundary MUST go
through ``locked_write`` so concurrent CLI + TUI writers don't clobber each
other. The lock file lives at ``.todo/lock`` and uses POSIX flock semantics.
"""
from __future__ import annotations
import contextlib
import fcntl
import os
import shutil
import tempfile
import time
from pathlib import Path
from .models import Task
from .parser import parse_tasks, build_markdown, DEFAULT_TEMPLATE

_FILENAME  = "tasks.md"
_TODO_DIR  = ".todo"          # hidden dir that holds all namespaces
_CAL_FILENAME = "calendar.md"
_SES_FILENAME = "sessions.md"
_LOCK_FILENAME = "lock"
_LOCK_TIMEOUT_S = 5.0


# ── namespace helpers ─────────────────────────────────────────────────────────

def namespaces_dir(root: Path) -> Path:
    return root / _TODO_DIR

def list_namespaces(root: Path) -> list[str]:
    nd = namespaces_dir(root)
    if not nd.exists():
        return []
    return sorted(
        d.name for d in nd.iterdir()
        if d.is_dir() and (d / _FILENAME).exists()
    )

def namespace_path(root: Path, name: str) -> Path:
    return namespaces_dir(root) / name / _FILENAME

def create_namespace(root: Path, name: str) -> Path:
    p = namespace_path(root, name)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(DEFAULT_TEMPLATE, encoding="utf-8")
    return p

def delete_namespace(root: Path, name: str) -> None:
    d = namespaces_dir(root) / name
    if d.exists():
        shutil.rmtree(d)


# ── root tasks ────────────────────────────────────────────────────────────────

def root_tasks_path(root: Path) -> Path:
    return root / _FILENAME

def init_if_missing(
    root: Path | None = None,
    namespace: str = "main",
) -> Path:
    base = root or Path.cwd()

    if namespace == "root":
        namespace = "main"

    p = namespace_path(base, namespace)

    p.parent.mkdir(parents=True, exist_ok=True)

    if not p.exists():
        p.write_text(DEFAULT_TEMPLATE, encoding="utf-8")

    return p
# ── generic load / save ───────────────────────────────────────────────────────

def load_tasks(path: Path) -> list[Task]:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_TEMPLATE, encoding="utf-8")
    return parse_tasks(path.read_text(encoding="utf-8"))

def save_tasks(tasks: list[Task], path: Path) -> None:
    _atomic_write(path, build_markdown(tasks))

def _atomic_write(path: Path, content: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tasks_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        shutil.move(tmp, path)
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise

#----Gitignore ----------
def ensure_gitignore(root: Path) -> None:
    gitignore = root / ".gitignore"

    if not gitignore.exists():
        gitignore.write_text(".todo/\n.time-tui/\n", encoding="utf-8")
        return

    content = gitignore.read_text(encoding="utf-8")

    if ".todo/" not in content:
        with gitignore.open("a", encoding="utf-8") as f:
            if not content.endswith("\n"):
                f.write("\n")
            f.write(".todo/\n")
            content = gitignore.read_text(encoding="utf-8")

    if ".time-tui/" not in content:
        with gitignore.open("a", encoding="utf-8") as f:
            content = gitignore.read_text(encoding="utf-8")
            if not content.endswith("\n"):
                f.write("\n")
            f.write(".time-tui/\n")


# ── locking ───────────────────────────────────────────────────────────────────

def todo_dir(root: Path) -> Path:
    """Absolute path to the .todo dir for a project root."""
    return root / _TODO_DIR


def lock_path(root: Path) -> Path:
    return todo_dir(root) / _LOCK_FILENAME


def calendar_path(root: Path) -> Path:
    return todo_dir(root) / _CAL_FILENAME


def sessions_md_path(root: Path) -> Path:
    return todo_dir(root) / _SES_FILENAME


def ensure_todo_dir(root: Path) -> Path:
    """Create .todo/ if missing and return its path."""
    td = todo_dir(root)
    td.mkdir(parents=True, exist_ok=True)
    return td


@contextlib.contextmanager
def file_lock(root: Path, *, timeout: float | None = None, blocking: bool = True):
    """POSIX flock wrapper around ``.todo/lock``.

    ``timeout`` is a wall-clock limit in seconds. ``blocking=False`` raises
    ``BlockingIOError`` immediately if the lock is held. The lock is released
    when the context exits.
    """
    ensure_todo_dir(root)
    path = lock_path(root)
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        if blocking:
            deadline = time.monotonic() + (timeout if timeout is not None else _LOCK_TIMEOUT_S)
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"could not acquire {path} within {timeout}s")
                    time.sleep(0.05)
        else:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield fd
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(fd)


def locked_write_to(path: Path, mutate, *, root: Path | None = None) -> None:
    """Lock the project, mutate a file, write atomically.

    ``path`` must live under ``.todo/`` of some project root. ``root`` defaults
    to ``path.parent.parent`` (i.e. ``.todo/..``). If ``path`` does not exist
    yet, an empty string is passed to ``mutate``.
    """
    if root is None:
        # path like <root>/.todo/<name>/tasks.md or <root>/.todo/calendar.md
        # walk up two levels to find the project root (the dir containing .todo).
        candidate = path.parent
        while candidate != candidate.parent and candidate.name != _TODO_DIR:
            candidate = candidate.parent
        if candidate.name == _TODO_DIR:
            root = candidate.parent
        else:
            raise ValueError(f"could not infer project root from {path}")
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    new_content = mutate(current)
    with file_lock(root):
        _atomic_write(path, new_content)


def tasks_md_for(root: Path) -> Path:
    """Default tasks file location (legacy helper retained for compatibility)."""
    return root / _FILENAME


def file_mtime(path: Path) -> float:
    """Return mtime as float; 0 if the file doesn't exist."""
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0