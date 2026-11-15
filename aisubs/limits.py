"""Reading-speed and length limits (Netflix Ukrainian style guide as a soft norm)."""

from __future__ import annotations

import re

from .prepare import Item

CPS = 17  # target reading speed
MAX_CPS = 20  # above this a line is worth re-translating
LINE = 42  # characters per line
LINES = 2  # lines per subtitle
MIN_DURATION = 500  # ms; shorter cues are rated as if they lasted this long

_TAG_RE = re.compile(r"</?i>")


def visible(text: str) -> str:
    return _TAG_RE.sub("", text)


def cps(text: str, start: int, end: int) -> float:
    """Characters per second, spaces included, tags and line breaks excluded."""
    chars = len(visible(text).replace("\n", ""))
    return chars / (max(end - start, MIN_DURATION) / 1000)


def budgets(item: Item, rate: float = CPS) -> list[int]:
    """Max characters for each part of the item.

    The cue's reading-time budget is shared between dialogue parts in
    proportion to their source length; each part is also capped by the space
    on screen (two lines for a single speaker, one line per speaker otherwise).
    """
    total = rate * max(item.end - item.start, MIN_DURATION) / 1000
    lengths = [max(1, len(visible(p.text))) for p in item.parts]
    cap = LINE * LINES if len(item.parts) == 1 else LINE
    return [int(min(cap, total * n / sum(lengths))) for n in lengths]


def is_tight(source: str, budget: int, ratio: float = 0.8) -> bool:
    """A part is tight when its English text already uses most of its budget.

    Ukrainian runs about as long as English, so such lines need condensing.
    """
    return len(visible(source)) > ratio * budget
