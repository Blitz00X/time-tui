from todo.core.parser import (
    DEFAULT_TEMPLATE,
    build_markdown,
    parse_tasks,
)

from todo.core.models import Priority, Task


def test_parse_default_template():
    tasks = parse_tasks(DEFAULT_TEMPLATE)

    assert len(tasks) >= 3


def test_parse_checkbox_done():
    md = "* [x] Finish project #high"

    tasks = parse_tasks(md)

    assert tasks[0].done is True
    assert tasks[0].priority == Priority.HIGH


def test_parse_checkbox_not_done():
    md = "* [ ] Buy milk #low"

    tasks = parse_tasks(md)

    assert tasks[0].done is False
    assert tasks[0].priority == Priority.LOW


def test_parse_tags():
    md = "* [ ] Study Python @today @coding"

    tasks = parse_tasks(md)

    assert "@today" in tasks[0].tags
    assert "@coding" in tasks[0].tags


def test_parse_bare_bullet():
    md = "* Learn Textual"

    tasks = parse_tasks(md)

    assert len(tasks) == 1
    assert tasks[0].text == "Learn Textual"


def test_section_priority_detection():
    md = """
## 🔴 High Priority

* [ ] Critical task
"""

    tasks = parse_tasks(md)

    assert tasks[0].priority == Priority.HIGH


def test_completed_section_marks_done():
    md = """
## ✅ Completed

* [ ] Already finished
"""

    tasks = parse_tasks(md)

    assert tasks[0].done is True


def test_build_markdown():
    tasks = [
        Task(
            text="Write tests",
            priority=Priority.HIGH,
            done=False,
            tags=["@dev"],
        )
    ]

    md = build_markdown(tasks)

    assert "Write tests" in md
    assert "🔴 High Priority" in md


def test_build_markdown_completed():
    tasks = [
        Task(
            text="Done task",
            priority=Priority.MEDIUM,
            done=True,
            tags=[],
        )
    ]

    md = build_markdown(tasks)

    assert "✅ Completed" in md
    assert "Done task" in md


def test_round_trip():
    original = """
## 🔴 High Priority

* [ ] Build app #high @today
"""

    tasks = parse_tasks(original)

    rebuilt = build_markdown(tasks)

    reparsed = parse_tasks(rebuilt)

    assert reparsed[0].text == "Build app"
    assert reparsed[0].priority == Priority.HIGH