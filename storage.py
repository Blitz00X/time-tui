from pathlib import Path

TASK_FILE = "tasks.md"

TEMPLATE = """# 📝 Tasks

## 🔴 High Priority

## 🟡 Medium Priority

## 🟢 Low Priority

## ✅ Completed
"""

def ensure_file():
    path = Path(TASK_FILE)
    if not path.exists():
        path.write_text(TEMPLATE)

def read_file():
    return Path(TASK_FILE).read_text()

def write_file(content: str):
    Path(TASK_FILE).write_text(content)
