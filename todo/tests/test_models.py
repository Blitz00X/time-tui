from todo.core.models import Priority, Task


def test_task_defaults():
    task = Task(text="Learn pytest")

    assert task.priority == Priority.MEDIUM
    assert task.done is False
    assert task.tags == []


def test_add_tag():
    task = Task(text="Test")

    task.add_tag("today")

    assert "@today" in task.tags


def test_add_duplicate_tag():
    task = Task(text="Test")

    task.add_tag("@today")
    task.add_tag("@today")

    assert task.tags.count("@today") == 1


def test_remove_tag():
    task = Task(text="Test", tags=["@today"])

    task.remove_tag("today")

    assert "@today" not in task.tags


def test_toggle_done():
    task = Task(text="Finish app")

    task.toggle_done()

    assert task.done is True

    task.toggle_done()

    assert task.done is False


def test_is_today():
    task = Task(text="Task", tags=["@today"])

    assert task.is_today is True


def test_is_doing():
    task = Task(text="Task", tags=["@doing"])

    assert task.is_doing is True


def test_display_tags():
    task = Task(text="Task", tags=["@today", "@work"])

    assert task.display_tags == "@today @work"


def test_to_markdown_line():
    task = Task(
        text="Build UI",
        priority=Priority.HIGH,
        done=True,
        tags=["@today"],
    )

    line = task.to_markdown_line()

    assert "* [x]" in line
    assert "#high" in line
    assert "@today" in line


def test_clone():
    task = Task(
        text="Original",
        priority=Priority.LOW,
        tags=["@test"],
    )

    cloned = task.clone()

    assert cloned.text == task.text
    assert cloned.priority == task.priority
    assert cloned.tags == task.tags
    assert cloned.id == task.id

    assert cloned is not task