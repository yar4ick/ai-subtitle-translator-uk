"""Find names, forms of address and SDH speakers for the glossary, with sample lines.

The model builds the glossary from this short digest instead of the whole film.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field

from .prepare import Item, make_scenes

EXAMPLES = 2
FIRST_LINES = 60
SCENE_LINES = 2
SCENE_SAMPLE = 90  # at most this many scene-opening lines, spread over the film

_TAG_RE = re.compile(r"</?i>")
# A capitalized word: "Leon", "McAllister", "O'Brien", "MaxTac", "ICE"; names join several: "Night City"
_WORD = r"(?:O'|Mc)?[A-Z](?:[a-z]+(?:[A-Z][a-z]+)?|[A-Z]+s?\b)"
_NAME = rf"(?:(?:Mr|Mrs|Ms|Dr|Miss)\.?\s+)?{_WORD}(?:\s+{_WORD})*"
_NAME_RE = re.compile(rf"\b{_NAME}(?:'s\b)?")  # possessive "David's" is counted as "David"
_SENTENCE_END_RE = re.compile(r"[.!?…]\s*$|^\s*$")
# ", kid." / ", Mathilda?" at the end; "Gloria, " at the start
_VOCATIVE_END_RE = re.compile(rf",\s+({_NAME}|[a-z]+)\s*[.?!…]+$")
_VOCATIVE_START_RE = re.compile(rf"^({_NAME}),\s")

# Capitalized mid-sentence for other reasons
_NOT_NAMES = set(
    "I I'm I'll I've I'd OK Okay TV God Jesus Christ Lord Mom Dad Mama Papa Sir Ma'am Mister Miss Mr Mrs Ms Dr "
    "Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July "
    "August September October November December English".split()
)
# Sentence-initial words that are followed by a comma but are not vocatives
_NOT_VOCATIVES = set(
    "Well Look Okay OK Yes Yeah Yep No Nope Oh Ah Uh Um Hey Hi Hello So Now Listen Come Please Right Sorry "
    "Thanks Wait Fine Sure Alright All Good Great Man God Jesus Anyway Actually Honestly Then But And Or If "
    "When Like Whoa Wow Damn Shit Fuck Okey Hmm Huh Boy Geez Gee See Plus Besides Also Still Maybe".split()
)


# Lowercase words after a comma at the end of a line that are not forms of address
_TAG_WORDS = set(
    "okay ok right huh yeah yes yep no nope then too please eh though anyway again now there here so what all "
    "uh um but or and like well".split()
)


@dataclass
class Candidate:
    name: str
    count: int = 0
    vocative: int = 0  # times used to address someone
    speaker: int = 0  # times seen as an SDH speaker label
    examples: list[str] = field(default_factory=list)


def _plain(text: str) -> str:
    return _TAG_RE.sub("", text)


def _mid_sentence_names(text: str) -> list[str]:
    names = []
    for m in _NAME_RE.finditer(text):
        before = text[: m.start()]
        name = m.group().strip().removesuffix("'s")
        if _SENTENCE_END_RE.search(before) or before.rstrip().endswith(("-", "\"", "«", "♪")):
            # "Ask Leon." starts a sentence: the first word is not part of the name
            name = name.partition(" ")[2]
            if not name:
                continue
        if name.split()[0] not in _NOT_NAMES and len(name) > 1:
            names.append(name)
    return names


def find(items: list[Item]) -> list[Candidate]:
    """Candidates sorted by importance (speaker labels, then frequency)."""
    found: dict[str, Candidate] = {}
    lines = [(i, _plain(p.text), p.speaker) for i, it in enumerate(items) if not it.skip for p in it.parts]

    def add(name: str, line: str, kind: str | None = None) -> None:
        c = found.setdefault(name, Candidate(name))
        if kind == "speaker":
            c.speaker += 1
            return
        c.count += 1
        if kind == "vocative":
            c.vocative += 1
        if len(c.examples) < EXAMPLES and line not in c.examples:
            c.examples.append(line)

    mid_names: Counter[str] = Counter()
    for _, line, _ in lines:
        mid_names.update(_mid_sentence_names(line))
    # A sentence-initial "Word, ..." is a vocative only if the word is also used as a name elsewhere
    starts: set[str] = set()
    end_vocatives = {m.group(1) for _, line, _ in lines if (m := _VOCATIVE_END_RE.search(line))}

    for _, line, speaker in lines:
        if speaker:
            add(speaker, line, "speaker")
        vocatives = set()
        if (m := _VOCATIVE_END_RE.search(line)) and m.group(1) not in _TAG_WORDS:
            vocatives.add(m.group(1))
        if (m := _VOCATIVE_START_RE.match(line)) and m.group(1).split()[0] not in _NOT_VOCATIVES:
            starts.add(m.group(1))
            vocatives.add(m.group(1))
        for v in vocatives:
            add(v, line, "vocative")
        for name in _mid_sentence_names(line):
            if name not in vocatives:
                add(name, line)

    def keep(c: Candidate) -> bool:
        if c.speaker:
            return True
        if c.name[0].islower():  # "kid", "choom": only repeated forms of address
            return c.vocative >= 2
        return c.name in mid_names or c.name in end_vocatives

    return sorted((c for c in found.values() if keep(c)), key=lambda c: (-c.speaker, -c.count, c.name))


def sample(items: list[Item], scene_gap: int = 3000) -> list[str]:
    """The first lines of the film and the first lines of each scene, in film order."""
    translatable = [i for i, it in enumerate(items) if not it.skip]
    picked = translatable[:FIRST_LINES]
    openings = [i for a, b in make_scenes(items, scene_gap) for i in [i for i in range(a, b) if not items[i].skip][:SCENE_LINES]]
    openings = [i for i in openings if i not in set(picked)]
    if len(openings) > SCENE_SAMPLE:
        step = len(openings) / SCENE_SAMPLE
        openings = [openings[int(k * step)] for k in range(SCENE_SAMPLE)]
    picked += openings
    out = []
    for i in sorted(set(picked)):
        out.append(" / ".join(_plain(p.text) for p in items[i].parts))
    return out


def to_dict(c: Candidate) -> dict:
    return asdict(c)
