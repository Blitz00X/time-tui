"""
File I/O for tui-md-todo.
Supports:
  - Root tasks.md  (the default namespace)
  - Namespace dirs: .todo/<name>/tasks.md
"""
from __future__ import annotations
import os, shutil, tempfile
from pathlib import Path
from .models import Task
from .parser import parse_tasks, build_markdown, DEFAULT_TEMPLATE

_FILENAME  = "tasks.md"
_TODO_DIR  = ".todo"          # hidden dir that holds all namespaces


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

def init_if_missing(root: Path | None = None) -> Path:
    base = root or Path.cwd()
    p = root_tasks_path(base)
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
