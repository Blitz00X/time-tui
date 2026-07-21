"""
Robust Markdown parser for tui-md-todo.

Parses tasks.md into Task objects and rebuilds the file from Task objects.
The parser is lenient — it never crashes on malformed input.
"""
from __future__ import annotations
import re
from typing import Optional
from .models import Task, Priority

# ── regex patterns ────────────────────────────────────────────────────────────

# Matches:  * [ ] text  OR  * [x] text  (leading whitespace allowed)
_TASK_RE = re.compile(
    r"^\s*\*\s+\[(?P<done>[xX ])\]\s+(?P<rest>.+)$"
)

# Matches:  * text  (bare bullet, no checkbox — treat as task without checkbox)
_BARE_BULLET_RE = re.compile(r"^\s*\*\s+(?P<rest>.+)$")

# Priority tag anywhere in the text
_PRIORITY_RE = re.compile(r"#(?P<p>high|medium|low)\b", re.IGNORECASE)

# Tags like @today, @doing, @anything
_TAG_RE = re.compile(r"@\w+")

# Section headers we recognise
_SECTION_RE = re.compile(
    r"^[#\s]*(?P<icon>[🔴🟡🟢✅📝])\s*(?P<name>.+)$"
)

_PRIORITY_FROM_SECTION: dict[str, Priority] = {
    "High Priority": Priority.HIGH,
    "Medium Priority": Priority.MEDIUM,
    "Low Priority": Priority.LOW,
    "Completed": Priority.LOW,  # fallback
}

# ── public API ────────────────────────────────────────────────────────────────

DEFAULT_TEMPLATE = """\
# 📝 Tasks

## 🔴 High Priority

* [ ] Example high-priority task #high @today

## 🟡 Medium Priority

* [ ] Example medium task #medium

## 🟢 Low Priority

* [ ] Example low-priority task #low

## ✅ Completed

"""


def parse_tasks(content: str) -> list[Task]:
    """Parse markdown *content* and return an ordered list of Task objects."""
    tasks: list[Task] = []
    current_priority = Priority.MEDIUM
    in_completed = False

    for raw_line in content.splitlines():
        line = raw_line.rstrip()

        # ── section detection ─────────────────────────────────────────
        if line.startswith("#"):
            stripped = line.lstrip("#").strip()
            if "High" in stripped:
                current_priority = Priority.HIGH
                in_completed = False
            elif "Medium" in stripped:
                current_priority = Priority.MEDIUM
                in_completed = False
            elif "Low" in stripped:
                current_priority = Priority.LOW
                in_completed = False
            elif "Completed" in stripped or "✅" in stripped:
                in_completed = True
            continue

        # ── indent detection ──────────────────────────────────────────
        # Count leading spaces on the raw line BEFORE rstrip, since trailing
        # spaces do not contribute to indent but may exist in user files.
        indent = len(raw_line) - len(raw_line.lstrip(" "))

        # ── task line with checkbox ───────────────────────────────────
        m = _TASK_RE.match(line)
        if m:
            done = m.group("done").lower() == "x"
            rest = m.group("rest")
            task = _parse_rest(rest, current_priority)
            if in_completed:
                task.done = True
            else:
                task.done = done
            task.indent = indent // 2
            tasks.append(task)
            continue

        # ── bare bullet (no checkbox) — treat as undone task ──────────
        m2 = _BARE_BULLET_RE.match(line)
        if m2:
            rest = m2.group("rest")
            task = _parse_rest(rest, current_priority)
            task.done = in_completed
            task.indent = indent // 2
            tasks.append(task)

    return tasks


def build_markdown(tasks: list[Task]) -> str:
    """Rebuild markdown from a list of Task objects."""
    buckets: dict[str, list[Task]] = {
        "high": [],
        "medium": [],
        "low": [],
        "done": [],
    }

    for task in tasks:
        if task.done:
            buckets["done"].append(task)
        else:
            buckets[task.priority.value].append(task)

    lines: list[str] = ["# 📝 Tasks", ""]

    def _section(icon: str, title: str, task_list: list[Task]) -> None:
        lines.append(f"## {icon} {title}")
        lines.append("")
        for t in task_list:
            lines.append(t.to_markdown_line())
        if not task_list:
            pass  # empty section — keep header, no tasks
        lines.append("")

    _section("🔴", "High Priority", buckets["high"])
    _section("🟡", "Medium Priority", buckets["medium"])
    _section("🟢", "Low Priority", buckets["low"])
    _section("✅", "Completed", buckets["done"])

    return "\n".join(lines)


# ── internal helpers ──────────────────────────────────────────────────────────

def _parse_rest(rest: str, default_priority: Priority) -> Task:
    """Parse the text after the checkbox marker."""
    # Extract priority tag
    pm = _PRIORITY_RE.search(rest)
    if pm:
        try:
            priority = Priority(pm.group("p").lower())
        except ValueError:
            priority = default_priority
        rest = _PRIORITY_RE.sub("", rest).strip()
    else:
        priority = default_priority

    # Extract @tags
    tags = _TAG_RE.findall(rest)
    text = _TAG_RE.sub("", rest).strip()

    # Clean up extra spaces
    text = re.sub(r"\s{2,}", " ", text).strip()

    return Task(text=text, priority=priority, done=False, tags=tags)
