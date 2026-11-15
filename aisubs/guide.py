"""Instructions for an AI agent that runs the whole translation with the CLI."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from .project import Project

PROMPTS = Path(__file__).parent / "prompts"


def _quote(path: str) -> str:
    return f'"{path}"' if " " in path else path


def command() -> str:
    """How the agent should call the tool, the way it was called now."""
    python = _quote(sys.executable or "python3")
    if Path(sys.argv[0]).is_dir():  # `python path/to/aisubs`, as the Claude Code plugin runs it
        return f"{python} {_quote(str(Path(sys.argv[0]).resolve()))}"
    name = Path(sys.argv[0]).name.lower()
    if name.startswith("aisubs") and not name.endswith(".py"):  # the installed console script
        return "aisubs"
    return f"{python} -m aisubs"


def text(film: str, cmd: str | None = None) -> str:
    work = str(Project(film).dir) if film else "film.aisubs"
    body = re.sub(r"\{work\}/([\w.-]+)", lambda m: _quote(str(Path(work) / m.group(1))), (PROMPTS / "guide.md").read_text(encoding="utf-8"))
    return (
        body
        .replace("{cmd}", cmd or command())
        .replace("{film}", _quote(film or "film.srt"))
        .replace("{work}", _quote(work))
        .replace("{wiki}", "\n   With internet access, add `--wikipedia`: the cast from Wikipedia improves the glossary.")
    )
