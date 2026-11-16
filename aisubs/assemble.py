"""Build the translated SRT text of each cue: typography, dialogue dashes, line breaks."""

from __future__ import annotations

import re

from .prepare import Item

MAX_LINE = 42

# A line should not end with these: they belong with the next word
_GLUE_WORDS = set(
    "і й та а але або чи що щоб як коли бо якщо хоч хоча ніж "
    "в у на з із зі зо до від за по під над про при без для через між перед біля коло "
    "не ні ж же б би ще вже то це цей ця ці мій моя моє мої твій твоя твоє твої".split()
)
_TAG_RE = re.compile(r"</?i>")


def visible_len(text: str) -> int:
    return len(_TAG_RE.sub("", text))


def typography(text: str) -> str:
    text = text.replace("...", "…")
    # A line cut off with a dash right after a word ("Якщо через учора—") ends with …
    text = re.sub(r"(\w)\s?[—–-](</i>)?$", r"\1…\2", text)
    # Straight double quotes in pairs -> «»
    return re.sub(r'"([^"]*)"', r"«\1»", text)


def wrap(text: str, width: int = MAX_LINE) -> list[str]:
    """Split into at most two lines, balanced, breaking after punctuation where possible."""
    if visible_len(text) <= width:
        return [text]
    best, best_score = [text], None
    for m in re.finditer(" ", text):
        top, bottom = text[: m.start()], text[m.end():]
        lt, lb = visible_len(top), visible_len(bottom)
        score = abs(lt - lb) + 10 * (max(0, lt - width) + max(0, lb - width))
        if _TAG_RE.sub("", top).rstrip()[-1:] in ",.;:!?…»":
            score -= 20  # a break after punctuation beats a balanced one
        last = _TAG_RE.sub("", top).split()[-1].lower().strip("«»\"'(")
        if last in _GLUE_WORDS:
            score += 12
        if len(top.split()) <= 2 < len(bottom.split()):
            score += 10
        if lt > lb:
            score += 2  # prefer a shorter top line
        if best_score is None or score < best_score:
            best, best_score = [top, bottom], score
    return best


def cue_text(item: Item, translations: list[str]) -> str:
    """SRT text for one item, given one translation per part."""
    if item.skip:
        return item.source
    parts = [typography(t) for t in translations]
    if len(parts) > 1:
        lines = [f"<i>-{t}</i>" if p.italic else f"-{t}" for p, t in zip(item.parts, parts)]
    else:
        lines = wrap(parts[0])
        if item.parts[0].italic:
            lines = [f"<i>{lines[0]}", *lines[1:]]
            lines[-1] += "</i>"
    return item.pos + "\n".join(lines)
