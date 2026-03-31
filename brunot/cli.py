from __future__ import annotations

import sys

from .ui.main_window import run_app


def main(argv: list[str] | None = None) -> int:
    """Entry point for the brunot desktop client."""
    if argv is None:
        argv = sys.argv[1:]
    run_app(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

