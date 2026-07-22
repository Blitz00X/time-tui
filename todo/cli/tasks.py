"""Task / namespace CLI commands.

Drives the same ``.todo/<name>/tasks.md`` files the TUI edits, going through
``storage.locked_write_to`` so concurrent CLI and TUI writers serialize.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..core import storage
from ..core.models import Task
from ..core.parser import build_markdown, parse_tasks, DEFAULT_TEMPLATE


def _namespace_path(root: Path, namespace: str) -> Path:
    return storage.namespaces_dir(root) / namespace / storage._FILENAME  # noqa: SLF001


def _ensure_namespace(root: Path, namespace: str) -> Path:
    storage.create_namespace(root, namespace)
    return _namespace_path(root, namespace)


def _load_tasks(root: Path, namespace: str) -> list[Task]:
    path = _ensure_namespace(root, namespace)
    return storage.load_tasks(path)


def _save_tasks(root: Path, namespace: str, tasks: list[Task]) -> None:
    path = _ensure_namespace(root, namespace)
    storage.locked_write_to(path, lambda _cur: build_markdown(tasks), root=root)


def _print_tasks_plain(tasks: list[Task]) -> None:
    for t in tasks:
        prefix = "  " * t.indent
        marker = "[x]" if t.done else "[ ]"
        print(f"{prefix}{marker} {t.text}")


def _print_tasks_json(tasks: list[Task]) -> None:
    out = [
        {"text": t.text, "indent": t.indent, "done": t.done}
        for t in tasks
    ]
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _find_parent(tasks: list[Task], parent_text: str) -> int:
    """Return the index of the parent task. -1 if not found."""
    matches: list[int] = []
    for i, t in enumerate(tasks):
        if t.text.strip() == parent_text.strip():
            matches.append(i)
    if not matches:
        raise KeyError(f"parent task not found: {parent_text!r}")
    if len(matches) > 1:
        # Prefer the first one at the lowest indent.
        matches.sort(key=lambda i: tasks[i].indent)
    return matches[0]


def _insert_child(tasks: list[Task], parent_idx: int, child_text: str) -> Task:
    parent = tasks[parent_idx]
    new = Task(text=child_text.strip(), indent=parent.indent + 1, done=False)
    tasks.insert(parent_idx + 1, new)
    return new


# ── subcommand handlers ───────────────────────────────────────────────────────

def cmd_task_list(root: Path, args: argparse.Namespace) -> int:
    ns = args.namespace or "main"
    tasks = _load_tasks(root, ns)
    if args.json:
        _print_tasks_json(tasks)
    else:
        if ns != "main":
            print(f"# {ns}")
        _print_tasks_plain(tasks)
    return 0


def cmd_task_add(root: Path, args: argparse.Namespace) -> int:
    ns = args.namespace or "main"
    tasks = _load_tasks(root, ns)
    new = Task(text=args.text.strip(), indent=0, done=False)
    tasks.append(new)
    _save_tasks(root, ns, tasks)
    print(f"added: {new.text}")
    return 0


def cmd_task_add_child(root: Path, args: argparse.Namespace) -> int:
    ns = args.namespace or "main"
    tasks = _load_tasks(root, ns)
    parent_idx = _find_parent(tasks, args.parent)
    new = _insert_child(tasks, parent_idx, args.text)
    _save_tasks(root, ns, tasks)
    print(f"added child under '{args.parent}': {new.text}")
    return 0


def cmd_task_done(root: Path, args: argparse.Namespace) -> int:
    ns = args.namespace or "main"
    tasks = _load_tasks(root, ns)
    idx = _find_parent(tasks, args.task)
    if tasks[idx].done:
        print(f"already done: {tasks[idx].text}")
        return 0
    tasks[idx].done = True
    _save_tasks(root, ns, tasks)
    print(f"done: {tasks[idx].text}")
    return 0


def cmd_task_rename(root: Path, args: argparse.Namespace) -> int:
    ns = args.namespace or "main"
    tasks = _load_tasks(root, ns)
    idx = _find_parent(tasks, args.task)
    old = tasks[idx].text
    tasks[idx].text = args.new.strip()
    _save_tasks(root, ns, tasks)
    print(f"renamed: {old!r} -> {tasks[idx].text!r}")
    return 0


def cmd_task_delete(root: Path, args: argparse.Namespace) -> int:
    ns = args.namespace or "main"
    tasks = _load_tasks(root, ns)
    idx = _find_parent(tasks, args.task)
    base_indent = tasks[idx].indent
    # Cascade: drop the task and any descendants.
    end = idx + 1
    if args.cascade:
        while end < len(tasks) and tasks[end].indent > base_indent:
            end += 1
    removed = tasks[idx:end]
    del tasks[idx:end]
    _save_tasks(root, ns, tasks)
    if args.cascade and len(removed) > 1:
        print(f"deleted {len(removed)} items (cascade)")
    else:
        print(f"deleted: {removed[0].text}")
    return 0


def cmd_namespace_list(root: Path, args: argparse.Namespace) -> int:
    namespaces = storage.list_namespaces(root)
    if args.json:
        json.dump(namespaces, sys.stdout, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        for ns in namespaces:
            print(ns)
    return 0


def cmd_namespace_create(root: Path, args: argparse.Namespace) -> int:
    storage.create_namespace(root, args.name)
    print(f"created namespace: {args.name}")
    return 0


# ── parser registration ───────────────────────────────────────────────────────

def register(sub: argparse._SubParsersAction) -> None:
    p_task = sub.add_parser("task", help="Operate on tasks within a namespace.")
    p_task_sub = p_task.add_subparsers(dest="task_cmd", required=True)

    p_list = p_task_sub.add_parser("list", help="List tasks in a namespace.")
    p_list.add_argument("--namespace", "--ns", dest="namespace", default="main")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(handler=cmd_task_list)

    p_add = p_task_sub.add_parser("add", help="Add a top-level task.")
    p_add.add_argument("--namespace", "--ns", dest="namespace", default="main")
    p_add.add_argument("--text", required=True)
    p_add.set_defaults(handler=cmd_task_add)

    p_child = p_task_sub.add_parser("add-child", help="Add a child task under a parent.")
    p_child.add_argument("--namespace", "--ns", dest="namespace", default="main")
    p_child.add_argument("--parent", required=True, help="Parent task text (exact match).")
    p_child.add_argument("--text", required=True)
    p_child.set_defaults(handler=cmd_task_add_child)

    p_done = p_task_sub.add_parser("done", help="Mark a task as done.")
    p_done.add_argument("--namespace", "--ns", dest="namespace", default="main")
    p_done.add_argument("--task", required=True)
    p_done.set_defaults(handler=cmd_task_done)

    p_rename = p_task_sub.add_parser("rename", help="Rename a task.")
    p_rename.add_argument("--namespace", "--ns", dest="namespace", default="main")
    p_rename.add_argument("--task", required=True)
    p_rename.add_argument("--new", required=True)
    p_rename.set_defaults(handler=cmd_task_rename)

    p_del = p_task_sub.add_parser("delete", help="Delete a task (and descendants with --cascade).")
    p_del.add_argument("--namespace", "--ns", dest="namespace", default="main")
    p_del.add_argument("--task", required=True)
    p_del.add_argument("--cascade", action="store_true", help="Also delete descendants.")
    p_del.set_defaults(handler=cmd_task_delete)

    p_ns = sub.add_parser("namespace", help="Operate on namespaces.")
    p_ns_sub = p_ns.add_subparsers(dest="ns_cmd", required=True)

    p_ns_l = p_ns_sub.add_parser("list", help="List namespaces.")
    p_ns_l.add_argument("--json", action="store_true")
    p_ns_l.set_defaults(handler=cmd_namespace_list)

    p_ns_c = p_ns_sub.add_parser("create", help="Create a namespace.")
    p_ns_c.add_argument("--name", required=True)
    p_ns_c.set_defaults(handler=cmd_namespace_create)