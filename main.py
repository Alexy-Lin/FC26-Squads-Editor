"""Compatibility entry point for the FC26 CLI."""

import sys

from backend_cli import main


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
