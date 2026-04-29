"""
CLI entry point for tui-md-todo.

Installed as `todo` via pyproject.toml.
"""
from __future__ import annotations
import sys
from pathlib import Path


def main() -> None:
    """Launch the tui-md-todo application."""
    # Resolve the working directory (support --dir flag for future use)
    directory: Path | None = None

    args = sys.argv[1:]
    if "--dir" in args:
        idx = args.index("--dir")
        try:
            directory = Path(args[idx + 1]).expanduser().resolve()
            if not directory.is_dir():
                print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
                sys.exit(1)
        except IndexError:
            print("Error: --dir requires a path argument.", file=sys.stderr)
            sys.exit(1)
    elif "--help" in args or "-h" in args:
        print(
            "tui-md-todo — keyboard-driven Markdown task manager\n\n"
            "Usage:\n"
            "  todo              Launch in current directory\n"
            "  todo --dir PATH   Launch in the specified directory\n"
            "  todo --help       Show this help message\n",
        )
        sys.exit(0)

    # Import here to keep startup fast
    from .storage import init_if_missing
    from .app import TodoApp

    path = init_if_missing(directory)
    app = TodoApp(tasks_path=path)
    app.run()


if __name__ == "__main__":
    main()
