"""Allow ``python -m todo.cli`` to work."""
from .main import main
import sys

if __name__ == "__main__":
    sys.exit(main())