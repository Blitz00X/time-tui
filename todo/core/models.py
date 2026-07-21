"""
Task data model for tui-md-todo.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def label(self) -> str:
        return {"high": "🔴", "medium": "🟡", "low": "🟢"}[self.value]

    @property
    def css_class(self) -> str:
        return f"priority-{self.value}"


@dataclass
class Task:
    text: str
    priority: Priority = Priority.MEDIUM
    done: bool = False
    tags: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    indent: int = 0
    expanded: bool = True

    # ── derived helpers ───────────────────────────────────────────────

    @property
    def is_today(self) -> bool:
        return "@today" in self.tags

    @property
    def is_doing(self) -> bool:
        return "@doing" in self.tags

    @property
    def display_tags(self) -> str:
        return " ".join(self.tags)

    def add_tag(self, tag: str) -> None:
        if not tag.startswith("@"):
            tag = f"@{tag}"
        if tag not in self.tags:
            self.tags.append(tag)

    def remove_tag(self, tag: str) -> None:
        if not tag.startswith("@"):
            tag = f"@{tag}"
        self.tags = [t for t in self.tags if t != tag]

    def toggle_done(self) -> None:
        self.done = not self.done

    def to_markdown_line(self) -> str:
        """Serialise back to a markdown list item."""
        checkbox = "[x]" if self.done else "[ ]"
        priority_tag = f"#{self.priority.value}"
        tags_str = (" " + " ".join(self.tags)) if self.tags else ""
        prefix = "  " * self.indent
        return f"{prefix}* {checkbox} {self.text} {priority_tag}{tags_str}"

    def clone(self) -> Task:
        return Task(
            text=self.text,
            priority=self.priority,
            done=self.done,
            tags=list(self.tags),
            id=self.id,
            indent=self.indent,
            expanded=self.expanded,
        )
