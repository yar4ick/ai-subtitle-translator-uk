"""`python -m aisubs`, or `python path/to/aisubs` without installing (as the Claude Code plugin runs it)."""

if __package__:
    from .cli import main
else:  # run as a directory: make the package importable
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from aisubs.cli import main

raise SystemExit(main())
