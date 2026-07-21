"""Tests for hierarchical task support."""
from todo.core.models import Priority, Task
from todo.core.parser import build_markdown, parse_tasks


def test_parse_indent_assigns_level():
    md = (
        "* [ ] Parent\n"
        "  * [ ] Child A\n"
        "  * [ ] Child B\n"
        "    * [ ] Grandchild\n"
    )
    tasks = parse_tasks(md)
    levels = [t.indent for t in tasks]
    assert levels == [0, 1, 1, 2]
    assert tasks[0].text == "Parent"
    assert tasks[1].text == "Child A"
    assert tasks[2].text == "Child B"
    assert tasks[3].text == "Grandchild"


def test_parse_indent_mixed_with_bare_bullet():
    md = (
        "* Parent bare\n"
        "  * [ ] Child with box\n"
    )
    tasks = parse_tasks(md)
    assert tasks[0].indent == 0
    assert tasks[1].indent == 1


def test_build_markdown_preserves_indent():
    tasks = [
        Task(text="Parent", indent=0),
        Task(text="Child", indent=1),
        Task(text="Grandchild", indent=2),
    ]
    md = build_markdown(tasks)
    # Lines should appear with leading spaces matching indent.
    lines = md.splitlines()
    parent_line = next(ln for ln in lines if "Parent" in ln)
    child_line = next(ln for ln in lines if "Child" in ln)
    grand_line = next(ln for ln in lines if "Grandchild" in ln)
    assert not parent_line.startswith(" ")
    assert child_line.startswith("  ")
    assert grand_line.startswith("    ")


def test_round_trip_preserves_hierarchy():
    md = (
        "* [ ] Top #high\n"
        "  * [ ] Sub one @today\n"
        "  * [ ] Sub two\n"
        "    * [ ] Deep\n"
    )
    first = parse_tasks(md)
    rebuilt = build_markdown(first)
    second = parse_tasks(rebuilt)
    assert [t.text for t in second] == [t.text for t in first]
    assert [t.indent for t in second] == [t.indent for t in first]


def test_default_template_remains_zero_indent():
    tasks = parse_tasks(
        "# 📝 Tasks\n\n"
        "## 🔴 High Priority\n\n"
        "* [ ] Example high-priority task #high @today\n"
    )
    assert all(t.indent == 0 for t in tasks)


def test_expanded_defaults_true():
    t = Task(text="x")
    assert t.expanded is True