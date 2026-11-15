"""Cheap checks of the translated lines, done by code.

Each problem is either `fix` (worth one more try by the model: too long,
left in English, Russian letters, broken tags, a gender that contradicts
the speaker, a misspelled name) or `review` (for a person to look at: the
model was unsure, or a line is still wrong after its retry).
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from . import checks, exchange, limits
from .glossary import Glossary

_LATIN_RE = re.compile(r"[A-Za-z]")
_CYRILLIC_RE = re.compile(r"[А-Яа-яІіЇїЄєҐґ]")
_RUSSIAN_RE = re.compile(r"[ЫыЭэЪъЁё]")
_TAG_RE = re.compile(r"</?i>")
_ANY_TAG_RE = re.compile(r"<[^>]*>|[<>]")
# Pieces of the exchange format left inside a translation
_JUNK_RE = re.compile(r"^\s*(?:≤\d+|S=[^|]*|[^\s|]{1,4}>[^\s|]{1,4})\s*\||\|")
_WORD_RE = re.compile(r"[А-ЯІЇЄҐ][а-яіїєґʼ'’-]+")
_LATIN_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]+")


@dataclass
class Problem:
    k: int  # part, 0-based
    key: str
    fix: bool  # True: ask the model again; False: for review
    message: str
    source: str = ""
    text: str = ""


def _stem(name: str) -> str:
    """The part of a Ukrainian name that stays in every case: Матильда -> Матильд, Стенсфілд -> Стенсфілд."""
    return name[:-1] if len(name) > 4 and name[-1] in "аяоеєиіїйьу" else name


class Checker:
    def __init__(self, g: Glossary):
        self.cast = checks.genders(g)
        # Ukrainian name word -> English words of the same entry: «Стенсфілд» -> {norman, stansfield}
        self.origin: dict[str, set[str]] = {}
        for en, uk in [(row[1], row[2]) for row in g.cast] + [(row[0], row[1]) for row in g.terms]:
            for w in _WORD_RE.findall(uk.strip(" ?")):
                if len(w) >= 4:
                    self.origin.setdefault(w, set()).update(x.lower() for x in _LATIN_WORD_RE.findall(en))
        self.names = sorted(self.origin)
        self.stems = {_stem(w) for w in self.names}
        self.english = {}  # English cast name word -> Ukrainian name
        for row in g.cast:
            for w in _LATIN_WORD_RE.findall(row[1]):
                if len(w) >= 3 and w.lower() not in ("mrs", "mr", "dr", "the"):
                    self.english[w.lower()] = row[2].strip(" ?")

    def line(self, source: str, text: str, speakers: str = "", limit: int | None = None) -> list[tuple[bool, str]]:
        """Problems of one translated part as (fix, message)."""
        out: list[tuple[bool, str]] = []
        plain = _TAG_RE.sub("", text)
        if _JUNK_RE.search(text):
            out.append((True, "pieces of the answer format (|, ≤N, S>A) left in the text"))
        if _LATIN_RE.search(plain) and not _CYRILLIC_RE.search(plain) and _LATIN_RE.search(source):
            out.append((True, "not translated"))
        else:
            left = sorted({w for w in _LATIN_WORD_RE.findall(plain) if w.lower() in self.english})
            if left:
                out.append((True, "name left in English: " + ", ".join(f"{w} (glossary: {self.english[w.lower()]})" for w in left)))
        if _RUSSIAN_RE.search(plain):
            out.append((True, "Russian letters: " + "".join(sorted(set(_RUSSIAN_RE.findall(plain))))))
        if _ANY_TAG_RE.sub("", _TAG_RE.sub("", text)) != _TAG_RE.sub("", text) or text.count("<i>") != text.count("</i>"):
            out.append((True, "broken tags (only <i>…</i> may stay)"))
        if limit is not None and len(limits.visible(text)) > limit:
            out.append((True, f"too long: {len(limits.visible(text))} characters"))
        for problem in checks.gender_conflicts(text, speakers, self.cast) if speakers else []:
            out.append((True, "gender: " + problem))
        for word in _WORD_RE.findall(plain):
            if len(word) < 4 or any(word.startswith(s) for s in self.stems):
                continue
            close = difflib.get_close_matches(word, self.names, n=1, cutoff=0.8)
            # Only when the English line has that name: «Бонні» for Bonnie is not a misspelled «Бенні»
            if close and self.origin[close[0]] & set(w.lower() for w in _LATIN_WORD_RE.findall(source)):
                out.append((True, f"name spelled «{word}», glossary: «{close[0]}»"))
        return out


def run(project) -> tuple[list[Problem], dict]:
    """Check every translated line of the project. Return (problems, stats)."""
    checker = Checker(project.glossary())
    done, flags, speakers, retries = project.done(), project.flags(), project.speakers(), project.retries()
    problems: list[Problem] = []
    stats = {"subtitles": 0, "over_cps": 0, "over_max_cps": 0}
    for k, chunk in enumerate(project.chunks):
        have = done.get(k, {})
        by_item: dict[int, list[tuple[str, int]]] = {}
        for key, i, p in exchange.chunk_keys(project.items, chunk):
            if key in have:
                by_item.setdefault(i, []).append((key, p))
        for i, parts in by_item.items():
            item = project.items[i]
            if len(parts) != len(item.parts):
                continue
            texts = [have[key] for key, _ in parts]
            stats["subtitles"] += 1
            rate = limits.cps(" ".join(texts), item.start, item.end)
            stats["over_cps"] += rate > limits.CPS
            stats["over_max_cps"] += rate > limits.MAX_CPS
            soft = limits.budgets(item)
            # Too long when the whole subtitle reads faster than MAX_CPS or does not fit the screen;
            # then each part over its share of the budget goes back (a dialogue part may borrow from the other)
            cap = limits.LINE * limits.LINES if len(parts) == 1 else limits.LINE
            lengths = [len(limits.visible(t)) for t in texts]
            too_long = rate > limits.MAX_CPS or max(lengths) > cap
            for (key, p), length in zip(parts, lengths):
                part = item.parts[p]
                limit = soft[p] if too_long and (length > soft[p] or length == max(lengths)) else None
                tried = retries.get(k, {}).get(key, 0)
                for fix, message in checker.line(part.text, have[key], speakers.get(k, {}).get(key, ""), limit):
                    if message.startswith("too long"):
                        message += f", the limit is {soft[p]}"
                    if fix and tried:
                        fix, message = False, message + " (after a retry)"
                    problems.append(Problem(k, key, fix, message, part.text, have[key]))
                if key in flags.get(k, []):
                    problems.append(Problem(k, key, False, "the model was unsure who speaks (?)", part.text, have[key]))
    return problems, stats


def fix_request(project, k: int, problems: list[Problem], *, brief: bool, instructions: str = "") -> str:
    """Ask the model again for the lines of part k that have `fix` problems."""
    speakers = project.speakers().get(k, {})
    keyed = {key: (i, p) for key, i, p in exchange.chunk_keys(project.items, project.chunks[k])}
    wanted: dict[str, list[str]] = {}
    for pr in problems:
        if pr.k == k and pr.fix:
            wanted.setdefault(pr.key, []).append(pr.message)
    out = [] if brief else [instructions, ""]
    out.append(
        f"FIX (part {k + 1} of {len(project.chunks)}): translate these lines again. "
        "Under each line are your earlier answer and what is wrong with it. "
        "Answer as usual, `ID|S>A|translation`, only for these IDs. Keep the earlier S>A unless "
        "the problem is the gender. `before:` and `after:` are neighbouring lines, for the sense only."
    )
    done = project.done().get(k, {})
    order = list(keyed)

    def neighbour(n: int, label: str) -> None:
        if 0 <= n < len(order) and order[n] not in wanted:
            j, q = keyed[order[n]]
            out.append(f"  {label}: {project.items[j].parts[q].text} => {done.get(order[n], '')}")

    for key in sorted(wanted, key=order.index):
        n = order.index(key)
        i, p = keyed[key]
        neighbour(n - 1, "before")
        item = project.items[i]
        fields = [key]
        if item.parts[p].speaker:
            fields.append("S=" + item.parts[p].speaker)
        if any(m.startswith("too long") for m in wanted[key]):
            fields.append(f"≤{limits.budgets(item)[p]}")
        out.append("|".join(fields + [item.parts[p].text]))
        sa = speakers.get(key, "")
        out.append(f"  was: {sa + '|' if sa else ''}{done.get(key, '')}")
        out.append("  wrong: " + "; ".join(wanted[key]))
        neighbour(n + 1, "after")
    return "\n".join(out) + "\n"
