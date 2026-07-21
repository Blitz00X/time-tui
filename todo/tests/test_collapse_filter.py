"""Tests for the visible-filter collapse behaviour."""
from todo.core.models import Priority, Task


def _make_hierarchy():
    return [
        Task(text="Parent", indent=0, expanded=False),
        Task(text="Child A", indent=1),
        Task(text="Child B", indent=1),
        Task(text="Grandchild", indent=2),
        Task(text="Sibling", indent=0),
    ]


def _filter_collapsed(tasks):
    """Mirror the dashboard's collapse filter."""
    result = []
    skip_until_under = -1
    for t in tasks:
        if skip_until_under >= 0:
            if t.indent > skip_until_under:
                continue
            skip_until_under = -1
        result.append(t)
        if not t.expanded:
            skip_until_under = t.indent
    return result


def test_collapsed_parent_hides_descendants():
    out = _filter_collapsed(_make_hierarchy())
    assert [t.text for t in out] == ["Parent", "Sibling"]


def test_expanded_parent_shows_descendants():
    tasks = _make_hierarchy()
    tasks[0].expanded = True
    out = _filter_collapsed(tasks)
    assert [t.text for t in out] == ["Parent", "Child A", "Child B", "Grandchild", "Sibling"]


def test_collapsed_root_keeps_next_root():
    out = _filter_collapsed(_make_hierarchy())
    assert out[-1].text == "Sibling"