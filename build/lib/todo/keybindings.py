"""
Keyboard binding definitions for tui-md-todo.

Centralising keybindings here makes them easy to document and change.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Binding:
    key: str
    description: str
    display: str  # short label shown in footer


BINDINGS: list[Binding] = [
    Binding("up",        "Move up",           "↑"),
    Binding("down",      "Move down",         "↓"),
    Binding("enter",     "Toggle done",       "Enter"),
    Binding("a",         "Add task",          "a"),
    Binding("e",         "Edit task",         "e"),
    Binding("d",         "Delete task",       "d"),
    Binding("s",         "Toggle doing",      "s"),
    Binding("f",         "Filter",            "f"),
    Binding("question_mark", "Help",          "?"),
    Binding("q",         "Quit",              "q"),
]

FOOTER_TEXT = "  ".join(f"[{b.display}] {b.description}" for b in BINDINGS)
