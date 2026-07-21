"""Tests for child-task insertion logic in the dashboard."""
from todo.core.models import Priority, Task


def _insert_child(parent_list: list[Task], parent: Task, child: Task) -> None:
    """Mirror the dashboard's insert-after-parent-with-indent+1 logic."""
    parent_index = next((i for i, t in enumerate(parent_list) if t.id == parent.id), -1)
    if parent_index < 0:
        child.indent = 0
        parent_list.append(child)
        return
    child.indent = parent.indent + 1
    insert_at = parent_index + 1
    parent_list.insert(insert_at, child)


def test_insert_child_appends_immediately_after_parent():
    parent = Task(text="Parent", indent=0)
    a = Task(text="Child A", indent=1)
    b = Task(text="Child B", indent=1)
    grand = Task(text="Grandchild", indent=2)
    sibling = Task(text="Sibling", indent=0)
    lst = [parent, a, b, grand, sibling]

    new_child = Task(text="New")
    _insert_child(lst, parent, new_child)

    assert [t.text for t in lst] == ["Parent", "New", "Child A", "Child B", "Grandchild", "Sibling"]
    assert new_child.indent == 1


def test_insert_child_under_nested_parent():
    a = Task(text="Child A", indent=1)
    b = Task(text="Child B", indent=1)
    grand = Task(text="Grandchild", indent=2)
    sibling = Task(text="Sibling", indent=0)
    parent = Task(text="Parent", indent=0)
    lst = [parent, a, b, grand, sibling]

    new_grand = Task(text="New")
    _insert_child(lst, grand, new_grand)

    assert new_grand.indent == 3
    assert [t.text for t in lst] == [
        "Parent", "Child A", "Child B", "Grandchild", "New", "Sibling",
    ]


def test_insert_root_when_parent_missing():
    """If the parent id is not found in the list, fall back to root append."""
    lst: list[Task] = []
    parent = Task(text="Ghost")  # never inserted into lst
    new_root = Task(text="New")
    _insert_child(lst, parent, new_root)
    assert lst and lst[0].text == "New"
    assert lst[0].indent == 0