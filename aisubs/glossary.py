"""The film glossary: style, characters, forms of address, terms.

Stored as `glossary.txt` in the same line format the model answers with, so
it is easy to read and fix by hand:

    STYLE|…
    PLOT|…
    C|code|English name|Ukrainian name|ч/ж/мн|role|voice
    P|code|code|ти/ви|note
    T|english|українською

A trailing `?` marks a line the model was not sure of. Every translation
request carries a compact rendering of the glossary.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

PROMPTS = Path(__file__).parent / "prompts"
_FIELDS = {"STYLE": 1, "PLOT": 1, "C": 6, "P": 4, "T": 2}
# A term coined while translating: "+|choom=чумба"
_ADDITION_RE = re.compile(r"^\s*\+\|\s*([^=|]+?)\s*=\s*(.+?)\s*$")


@dataclass
class Glossary:
    style: str = ""
    plot: str = ""
    cast: list[list[str]] = field(default_factory=list)  # code, en, uk, gender, role, voice
    pairs: list[list[str]] = field(default_factory=list)  # code, code, ти/ви, note
    terms: list[list[str]] = field(default_factory=list)  # en, uk

    def is_empty(self) -> bool:
        return not (self.style or self.plot or self.cast or self.pairs or self.terms)


def parse(text: str) -> tuple[Glossary, list[str]]:
    """Read glossary lines, tolerating code fences and chatter. Return (glossary, ignored lines)."""
    g = Glossary()
    ignored = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("```", "#")):
            continue
        kind, _, rest = line.partition("|")
        kind = kind.strip().upper()
        if kind not in _FIELDS or not rest.strip():
            ignored.append(line)
            continue
        n = _FIELDS[kind]
        values = [v.strip() for v in rest.split("|", n - 1)]
        values += [""] * (n - len(values))
        if kind == "STYLE":
            g.style = values[0]
        elif kind == "PLOT":
            g.plot = values[0]
        elif kind == "C":
            g.cast.append(values)
        elif kind == "P":
            g.pairs.append(values)
        else:
            g.terms.append(values)
    return g, ignored


def dumps(g: Glossary) -> str:
    out = []
    if g.style:
        out.append(f"STYLE|{g.style}")
    if g.plot:
        out.append(f"PLOT|{g.plot}")
    out += ["C|" + "|".join(c).rstrip("|") for c in g.cast]
    out += ["P|" + "|".join(p).rstrip("|") for p in g.pairs]
    out += ["T|" + "|".join(t) for t in g.terms]
    return "\n".join(out) + "\n"


def add_terms(g: Glossary, additions: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Add terms coined during translation unless already known. Return the added ones."""
    known = {t[0].lower() for t in g.terms} | {c[1].lower() for c in g.cast}
    added = []
    for en, uk in additions:
        if en.lower() not in known:
            g.terms.append([en, uk])
            known.add(en.lower())
            added.append((en, uk))
    return added


def parse_additions(text: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for line in text.splitlines() if (m := _ADDITION_RE.match(line))]


def render(g: Glossary) -> str:
    """The compact block that goes into every translation request."""
    out = []
    if g.style:
        out.append(f"STYLE: {g.style}")
    if g.plot:
        out.append(f"PLOT: {g.plot}")
    if g.cast:
        out.append("CAST (code name — gender; role; voice):")
        for code, en, uk, gender, role, voice in g.cast:
            details = "; ".join(x for x in (gender, role, voice) if x)
            out.append(f"{code} {uk} ({en}) — {details}")
    if g.pairs:
        items = []
        for a, b, form, note in g.pairs:
            items.append(f"{a}→{b} {form}" + (f" ({note})" if note else ""))
        out.append("PAIRS: " + "; ".join(items))
    if g.terms:
        out.append("TERMS: " + "; ".join(f"{en}={uk}" for en, uk in g.terms))
    return "\n".join(out)


def build_request(title: str, found: list[dict], sample: list[str]) -> str:
    out = [(PROMPTS / "glossary.md").read_text(encoding="utf-8").replace("{title}", title).strip(), "", "CANDIDATES (name ×count, how often used to address someone; examples):"]
    for c in found:
        notes = []
        if c["vocative"]:
            notes.append(f"address ×{c['vocative']}")
        if c["speaker"]:
            notes.append(f"SDH speaker ×{c['speaker']}")
        line = f"{c['name']} ×{c['count'] or c['speaker']}" + (f" ({', '.join(notes)})" if notes else "")
        if c["examples"]:
            line += ": " + " / ".join(c["examples"])
        out.append(line)
    out += ["", "SAMPLE:"] + sample
    return "\n".join(out) + "\n"

