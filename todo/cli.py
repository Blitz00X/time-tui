"""CLI entry point — `todo`"""
from __future__ import annotations
import sys
from pathlib import Path


def main() -> None:
    args = sys.argv[1:]
    directory: Path | None = None

    if "--dir" in args:
        idx = args.index("--dir")
        try:
            directory = Path(args[idx + 1]).expanduser().resolve()
            if not directory.is_dir():
                print(f"error: '{directory}' is not a directory.", file=sys.stderr)
                sys.exit(1)
        except IndexError:
            print("error: --dir requires a path argument.", file=sys.stderr)
            sys.exit(1)
    elif "--help" in args or "-h" in args:
        print(
            "tui-md-todo\n\n"
            "usage:\n"
            "  todo              launch in current directory\n"
            "  todo --dir PATH   launch in the specified directory\n"
        )
        sys.exit(0)

    root = directory or Path.cwd()

    from todo.ui.app import TodoApp
    from todo.core.storage import ensure_gitignore

    ensure_gitignore(root)
    app = TodoApp(root=root)
    app.run()


if __name__ == "__main__":
    main()