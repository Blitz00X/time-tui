from pathlib import Path

from todo.core.storage import (
    create_namespace,
    delete_namespace,
    ensure_gitignore,
    init_if_missing,
    list_namespaces,
    load_tasks,
    namespace_path,
    save_tasks,
)

from todo.core.models import Task


def test_create_namespace(tmp_path: Path):
    path = create_namespace(tmp_path, "work")

    assert path.exists()
    assert path.name == "tasks.md"


def test_list_namespaces(tmp_path: Path):
    create_namespace(tmp_path, "work")
    create_namespace(tmp_path, "personal")

    namespaces = list_namespaces(tmp_path)

    assert "work" in namespaces
    assert "personal" in namespaces


def test_delete_namespace(tmp_path: Path):
    create_namespace(tmp_path, "temp")

    delete_namespace(tmp_path, "temp")

    assert not namespace_path(tmp_path, "temp").exists()


def test_init_if_missing_creates_file(tmp_path: Path):
    path = init_if_missing(tmp_path, "main")

    assert path.exists()
    assert path.read_text(encoding="utf-8") != ""


def test_load_tasks_creates_missing_file(tmp_path: Path):
    path = tmp_path / "tasks.md"

    tasks = load_tasks(path)

    assert path.exists()
    assert isinstance(tasks, list)


def test_save_and_load_tasks(tmp_path: Path):
    path = tmp_path / "tasks.md"

    tasks = [
        Task(text="Test task", done=False)
    ]

    save_tasks(tasks, path)

    loaded = load_tasks(path)

    assert len(loaded) == 1
    assert loaded[0].text == "Test task"


def test_ensure_gitignore_creates_file(tmp_path: Path):
    ensure_gitignore(tmp_path)

    gitignore = tmp_path / ".gitignore"

    assert gitignore.exists()
    assert ".todo/" in gitignore.read_text()


def test_ensure_gitignore_appends_once(tmp_path: Path):
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("node_modules/\n", encoding="utf-8")

    ensure_gitignore(tmp_path)
    ensure_gitignore(tmp_path)

    content = gitignore.read_text(encoding="utf-8")

    assert content.count(".todo/") == 1