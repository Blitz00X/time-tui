"""time-tui CLI.

Provides ``python -m todo.cli <command> [...]`` access to the same data files
the TUI manipulates. Used by humans (shell) and agents (subprocess) alike.
"""
from .main import main  # noqa: F401