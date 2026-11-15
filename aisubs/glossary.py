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
import unicodedata
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


def speaker_codes(g: Glossary) -> dict[str, str]:
    """SDH speaker name (lowercase) -> cast code, by full English name or its first word."""
    out = {}
    for code, en, *_ in g.cast:
        name = en.strip(" ?").lower()
        out.setdefault(name, code)
        out.setdefault(name.split()[0] if name else name, code)
    return out


def build_request(title: str, found: list[dict], sample: list[str], extra: str = "") -> str:
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
    if extra:
        out += ["", extra.rstrip()]
    out += ["", "SAMPLE:"] + sample
    return "\n".join(out) + "\n"


# Forms of address, not names: no glossary entry needed
_ADDRESS = set("mom mommy mama mum mother dad daddy papa father sir ma'am madam man dude bro honey sweetie sweetheart "
               "baby babe kid kids guys boy girl buddy pal mister miss lady son darling".split())


def name_words(text: str) -> set[str]:
    """Lowercase words of a name, accents removed: "Léon Lando" -> {"leon", "lando"}."""
    plain = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    words = (re.sub(r"'s$", "", w.lower()).strip("'") for w in re.findall(r"[A-Za-z']+", plain))
    return {w for w in words if len(w) > 2}


_HE_RE = re.compile(r"\b(?:he|him|his|himself)\b", re.I)
_SHE_RE = re.compile(r"\b(?:she|her|hers|herself)\b", re.I)
_TITLE_RE = r"\b(Mr|Mister|Mrs|Ms|Miss)\.?\s+"


def gender_evidence(lines: list[str], name: str) -> tuple[int, int]:
    """(he, she): pronouns after a mention of the name (not when spoken to), and Mr/Mrs before it."""
    he = she = 0
    plain = [re.sub(r"<[^>]+>", "", t).replace("\n", " ") for t in lines]
    word = r"\b" + re.escape(name) + r"\b"
    for n, t in enumerate(plain):
        for m in re.finditer(_TITLE_RE + word, t):
            if m.group(1) in ("Mr", "Mister"):
                he += 2
            else:
                she += 2
        for m in re.finditer(word, t):
            # The rest of the name ("Steve Harrington") and what follows it
            tail = re.match(r"(?:\s+[A-Z][a-z]+)*\s*([^\w\s]|$)?", t[m.end():])
            after, before = tail.group(1), t[:m.start()].rstrip()
            alone = not before or before.endswith((",", ".", "!", "?", "-"))
            if after == "," or (after is not None and after in ".!?…" and alone):
                continue  # spoken to: "David, wait", "Wait, David.", "Steve?" (but not "Where's Gloria?")
            rest = re.split(r"\s-\s", t[m.end():])[0]  # "- Who is David? - Her …": the other speaker
            if n + 1 < len(plain) and not plain[n + 1].lstrip().startswith("-"):
                rest += " " + plain[n + 1]  # the same speaker goes on; "- " is someone else
            he += len(_HE_RE.findall(rest))
            she += len(_SHE_RE.findall(rest))
    return he, she


def gender_warnings(g: Glossary, lines: list[str]) -> list[str]:
    """Characters whose gender in CAST contradicts how the subtitles speak about them."""
    words: dict[str, list[str]] = {}
    for row in g.cast:
        for w in re.findall(r"[A-Z][a-z]{2,}", row[1]):
            words.setdefault(w, []).append(row[0])
    out = []
    for row in g.cast:
        code, en, gender = row[0], row[1], row[3].strip(" ?")
        if gender not in ("ч", "ж"):
            continue
        he = she = 0
        for w in re.findall(r"[A-Z][a-z]{2,}", en):
            if len(words[w]) == 1 and w not in ("Mrs", "Miss", "The"):  # a shared surname says nothing
                a, b = gender_evidence(lines, w)
                he, she = he + a, she + b
        same, other = (he, she) if gender == "ч" else (she, he)
        if (other >= 2 and not same) or (other >= 3 and other >= 3 * same):
            out.append(f"{code} {en}: CAST says {gender}, but the subtitles say "
                       f"{'she/her' if gender == 'ч' else 'he/him'} about them ({other} vs {same}); check the gender")
    return out


def cross_check(g: Glossary, found: list[dict], source_words: set[str], min_count: int = 5,
                lines: list[str] | None = None) -> list[str]:
    """Warnings about the glossary against the subtitles (cheap, by code)."""
    out = gender_warnings(g, lines) if lines else []
    named = set()
    for code, en, uk, *_ in g.cast:
        words = name_words(en) - {"mrs", "the"}
        named |= words
        if words and not words & source_words:
            out.append(f"{code} {en}: the name never occurs in the subtitles (another film? a guess?)")
    for c in found:
        words = name_words(c["name"]) - _ADDRESS
        count = max(c.get("count", 0), c.get("speaker", 0))
        # A short form of a known name counts as known: Stan -> Stansfield
        known = any(n.startswith(w) for w in words for n in named)
        if count >= min_count and words and not known and not any(w in t[0].lower() for t in g.terms for w in words):
            out.append(f"{c['name']} occurs {count} times but is not in CAST or TERMS")
    return out

