# tui-md-todo

> A keyboard-driven, terminal-native to-do manager that stores everything in plain Markdown.

```
 todo / login                                          [pending]
─────────────────────────────────────────────────────────────────
  namespaces ◀  │  tasks [pending]   3 shown
  ▸ root     2  │  [ ] ! Fix auth bug              @doing
    login    3  │  [ ] ~ Write unit tests           @today
    signup   0  │  [ ] · Update API docs
    homepage 1  │
─────────────────────────────────────────────────────────────────
 ↑↓ nav  enter done  a add  e edit  d del  s pomodoro  \ sidebar
```

Built with [Textual](https://github.com/Textualize/textual). Inspired by lazygit, taskwarrior, and the philosophy that the best tools get out of your way.

---

## Features

- **Plain Markdown storage** — tasks live in `tasks.md`, fully human-readable and editable by hand
- **Namespaces** — create isolated task lists per project (`login`, `signup`, `homepage`), each with their own `tasks.md`
- **Pomodoro timer** — built-in 25/5/15 min work-break timer, launched per task with `s`
- **Priority system** — `!` high / `~` medium / `·` low, color-coded
- **Tag support** — `@today`, `@doing`, and any custom `@tag`
- **Interactive filter mode** — press f to open the filter selector for 5 seconds, then choose a filter using dedicated keys
- **Atomic writes** — every save goes through a temp-file rename, no corruption on crash
- **Zero flicker** — DOM updates are surgical (in-place for same-count rows, structural only when needed)
- **Fully keyboard-driven** — no mouse required

---

## Installation

### uv (recommended)



```bash
uv tool install git+https://github.com/Advaithdp02/Todo_tui.git
```

### pipx

```bash
pipx install git+https://github.com/Advaithdp02/Todo_tui.git
```

### From source

```bash
git clone https://github.com/Advaithdp02/Todo_tui.git
cd Todo_tui
pip install -e .
```
### Requirements

- Python 3.10+
- [Textual](https://github.com/Textualize/textual) >= 0.47 (installed automatically)

---

## Usage

```bash
todo                   # launch in the current directory
todo --dir ~/projects  # launch in a specific directory
todo --help
```

On first run, `tasks.md` is created automatically with a starter template. That is the only file you need to commit to version control — everything else is optional.

---

## Keyboard Reference

### Task list

| Key | Action |
|-----|--------|
| `↑` / `k` | Move cursor up |
| `↓` / `j` | Move cursor down |
| `Enter` | Toggle task done / undone |
| `a` | Add new task |
| `e` | Edit selected task |
| `d` | Delete selected task |
| `s` | Open Pomodoro timer for selected task |
| `f` | filter bar (all → pending → today → doing → high) |
| `q` | Quit |

### Sidebar (namespaces)

| Key | Action |
|-----|--------|
| `\` | Toggle sidebar focus on / off |
| `↑` / `↓` | Navigate namespaces (when sidebar is focused) |
| `N` | Create new namespace |
| `X` | Delete current namespace |

### Full-screen calendar

| Key | Action |
|-----|--------|
| `Shift+C` | Open the full-screen calendar from the dashboard |
| `D` / `W` / `M` | Switch between Day, Week, and Month views |
| `←` / `→` | Previous / next day, week, or month |
| `T` | Jump to today |
| `A` | Add an event to the selected date |
| `Esc` | Return to the dashboard |

The dashboard calendar also has an `Expand` button for mouse users.

### Pomodoro screen

| Key | Action |
|-----|--------|
| `Space` | Start / pause timer |
| `r` | Reset timer |
| `b` | Go back to task list |

---

## Namespaces

Namespaces let you keep separate task lists for different areas of a project, all managed from one place.

Press `N` inside the TUI, enter a name (e.g. `login`), and a new task list is created. Switch between namespaces using `\` to focus the sidebar, then `↑` / `↓`.

```
myproject/
└── .todo/
    ├── root/
    |   └── tasks.md             ← root namespace (always present)
    ├── login/
    │   └── tasks.md
    ├── signup/
    │   └── tasks.md
    └── homepage/
        └── tasks.md
```

Each `tasks.md` is a standalone Markdown file you can open in any editor.

---

## Pomodoro Timer

Select any task and press `s` to open a full-screen timer for it.

```
── FOCUS ──

task: Fix auth bug

         24:07

██████████████░░░░░░░░░░░░░░░░  41%

●  ●  ○  ○    2 done

              ⏸ paused

space start/pause   r reset   b back
```

Follows the standard Pomodoro technique:

| Phase | Duration |
|-------|----------|
| Focus | 25 min |
| Short break | 5 min |
| Long break (every 4th) | 15 min |

A desktop notification fires at the end of each phase.

---

## tasks.md Format

```markdown
# 📝 Tasks

## 🔴 High Priority

* [ ] Fix login bug #high @doing
* [ ] Write tests #high @today

## 🟡 Medium Priority

* [ ] Update documentation #medium

## 🟢 Low Priority

* [ ] Refactor utils module #low

## ✅ Completed

* [x] Initial project setup #high
```

**Task anatomy:**

```
* [ ] Task text here #priority @tag1 @tag2
  │    │             │          └── optional tags (@today, @doing, anything)
  │    │             └── #high | #medium | #low
  │    └── task text (free-form)
  └── [ ] undone  |  [x] done
```

The file is plain Markdown — edit it by hand any time. The parser is lenient and will not crash on unknown lines.

---

## Project Structure



```text
tui_md_todo/
├── __init__.py
├── cli.py                 # CLI entry point → `todo`
├── core/
│   ├── keybindings.py     # key mappings and action constants
│   ├── models.py          # Task dataclass and priority models
│   ├── parser.py          # Markdown ↔ task parser
│   └── storage.py         # atomic file handling + namespace storage
├── ui/
│   ├── app.py             # main Textual application
│   ├── pomodoro.py        # Pomodoro timer screen
│   └── modals/
│       ├── modal.py       # add/edit task modal
│       └── ns_modal.py    # namespace creation modal
└── tests/
    ├── test_models.py
    ├── test_parser.py
    └── test_storage.py
```

## Contributing

Issues and PRs are welcome.

```bash
git clone https://github.com/yourname/tui-md-todo
cd tui-md-todo
pip install -e ".[dev]"
```

Please open an issue before submitting a large PR so we can discuss the approach first.

### Dev dependencies

Add this to `pyproject.toml` to install dev tools:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7",
    "ruff>=0.4",
    "mypy>=1.8",
]
```

```bash
pip install -e ".[dev]"

pytest          # run tests
ruff check .    # lint
ruff format .   # format
mypy .          # type check
```

---




THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
