"""Tests for cascade-delete behaviour on hierarchical tasks."""
from todo.core.models import Priority, Task


def _subtree_indices(tasks: list[Task], target_index: int) -> list[int]:
    """Return indices of *target* plus every descendant in *tasks*."""
    if target_index < 0 or target_index >= len(tasks):
        return []
    target_indent = tasks[target_index].indent
    out = [target_index]
    for i in range(target_index + 1, len(tasks)):
        if tasks[i].indent > target_indent:
            out.append(i)
        else:
            break
    return out


def test_subtree_includes_immediate_children():
    tasks = [
        Task(text="Root", indent=0),
        Task(text="A", indent=1),
        Task(text="B", indent=1),
        Task(text="A1", indent=2),
        Task(text="Sibling", indent=0),
    ]
    indices = _subtree_indices(tasks, 0)
    assert indices == [0, 1, 2, 3]


def test_subtree_stops_at_next_root():
    tasks = [
        Task(text="Root", indent=0),
        Task(text="A", indent=1),
        Task(text="Other root", indent=0),
    ]
    assert _subtree_indices(tasks, 0) == [0, 1]


def test_subtree_leaf_only():
    tasks = [Task(text="Leaf", indent=0)]
    assert _subtree_indices(tasks, 0) == [0]


def test_subtree_missing_target():
    tasks = [Task(text="Other", indent=0)]
    assert _subtree_indices(tasks, 5) == []


def test_subtree_nested_three_levels():
    tasks = [
        Task(text="R", indent=0),
        Task(text="A", indent=1),
        Task(text="A1", indent=2),
        Task(text="A1x", indent=3),
        Task(text="B", indent=1),
    ]
    assert _subtree_indices(tasks, 0) == [0, 1, 2, 3, 4]