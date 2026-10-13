"""Thin wrapper: the implementation lives in signoff_cli.py at the project root
(tools/ is excluded from the production image, but the sign-off gate must still run there)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from signoff_cli import main  # noqa: E402,F401

if __name__ == "__main__":
    sys.exit(main())
