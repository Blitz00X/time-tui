# tui-md-todo

> A keyboard-driven terminal UI to-do manager backed by a plain Markdown file.

```
╔══════════════════════════════════════════════════════════╗
║  tui-md-todo               ⌚ 14:32                       ║
╠══════════════════════════════════════════════════════════╣
║ 📋 Total 5   ⏳ Pending 3   🔵 Doing 1   📅 Today 2      ║
╠══════════════════════════════╦═══════════════════════════╣
║  📝 All Tasks  (5 shown)     ║ ── Task Details ──        ║
║                              ║                           ║
║ ⬜ Write unit tests     🔴   ║ Status                    ║
║ ⬜ Update README  @today 🟡  ║ ⏳ Pending                ║
║ ▶ ⬜ Fix login bug @doing 🔴 ║                           ║
║ ⬜ Code review        🟢    ║ Priority                  ║
║ ✅ Deploy to staging  🔴    ║ 🔴 High                   ║
╚══════════════════════════════╩═══════════════════════════╝
```

## Features

- 📄 **Plain Markdown storage** — tasks live in `tasks.md`, editable by hand
- ⌨️ **Fully keyboard-driven** — no mouse needed
- 🎨 **Color-coded priorities** — red / yellow / green at a glance
- 🏷️ **Tag support** — `@today`, `@doing`, and any custom tags
- 🔍 **Filter modes** — cycle through all / pending / today / doing / high
- 💾 **Instant persistence** — every change is saved atomically

## Installation

```bash
pip install -e .
```

## Usage

```bash
todo              # launch in current directory
todo --dir ~/work # launch in a specific directory
```

A `tasks.md` file is created automatically if it does not exist.

## Keyboard Controls

| Key     | Action                        |
|---------|-------------------------------|
| ↑ / k   | Move cursor up                |
| ↓ / j   | Move cursor down              |
| Enter   | Toggle task complete          |
| a       | Add new task (modal)          |
| e       | Edit selected task (modal)    |
| d       | Delete selected task          |
| s       | Toggle @doing tag             |
| f       | Cycle filter mode             |
| q       | Quit                          |

## tasks.md Format

```markdown
# 📝 Tasks

## 🔴 High Priority

* [ ] Fix login bug #high @doing
* [ ] Write tests #high @today

## 🟡 Medium Priority

* [ ] Update docs #medium

## 🟢 Low Priority

* [ ] Refactor utils #low

## ✅ Completed

* [x] Initial setup #high
```

## Architecture

```
tui_md_todo/
├── cli.py          # entry point → `todo`
├── app.py          # Textual App, all widget composition & actions
├── models.py       # Task dataclass, Priority enum
├── parser.py       # Markdown ↔ Task conversion
├── storage.py      # atomic file I/O
├── keybindings.py  # binding constants
└── ui/
    └── modal.py    # Add/Edit modal screen
```


