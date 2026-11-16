"""Cheap checks of a translated line against the speaker and addressee the model named.

Ukrainian past tense shows gender: «я забув» (he) / «я забула» (she). When a
line says «я» or «ти» together with such a verb, its gender must match the
speaker or the addressee from the `S>A` field.
"""

from __future__ import annotations

import re

from .glossary import Glossary

_WORD_RE = re.compile(r"[а-яіїєґʼ'’]+", re.IGNORECASE)
_SENTENCE_RE = re.compile(r"[^.!?…]+[.!?…]*")
# Subjects only: in «я не бачила тебе» the verb near «тебе» is not the addressee's
_FIRST = {"я"}
_SECOND = {"ти"}
_GENDERS = {"ч": "ч", "ж": "ж"}
WINDOW = 3  # past-tense words this close to «я» / «ти» are taken as its verbs
# Look like masculine past tense but are not verbs
_NOT_VERBS = set("знов любов кров морков років друзів хлопців батьків грошей слів часів разів днів тижнів доларів братів".split())
# «-ів» is as often a plural noun (копів, псів) as a verb (хотів, сидів): such a word counts
# only right next to «я» / «ти», with nothing but these words between them
_PARTICLES = set("не ж же вже би б теж також ще аж навіть просто так дуже завжди ніколи справді тоді тут там й і".split())


def past_gender(word: str) -> str:
    """'ч' / 'ж' for a word that looks like a singular past-tense verb, else ''."""
    w = word.lower()
    if len(w) < 4:
        return ""
    if w.endswith(("лася", "лась", "ла")):
        return "ж"
    if w.endswith(("вся", "в")) and w not in _NOT_VERBS:
        return "ч"
    return ""


def genders(g: Glossary) -> dict[str, str]:
    """Cast code -> 'ч' / 'ж' (the bare letters ч, ж work as codes too)."""
    out = dict(_GENDERS)
    for code, _, _, gender, *_ in g.cast:
        gender = gender.strip().lower()
        if gender in ("ч", "ж"):  # a guess ("ж?") is not checked: the line may be right and the guess wrong
            out[code] = gender
    return out


def base_code(code: str) -> str:
    """'Гл?' -> 'Гл', 'ч1' -> 'ч', 'Д!' -> 'Д'."""
    return code.strip().rstrip("?!").rstrip("0123456789")


def gender_conflicts(text: str, speakers: str, cast: dict[str, str]) -> list[str]:
    """Problems like "я забув: S is ж" for one line; `speakers` is "S>A"."""
    s, _, a = speakers.partition(">")
    want = {"я": cast.get(base_code(s), ""), "ти": cast.get(base_code(a), "")}
    problems = []
    for sentence in _SENTENCE_RE.findall(text):
        words = [w.lower() for w in _WORD_RE.findall(sentence)]
        for k, word in enumerate(words):
            person = "я" if word in _FIRST else "ти" if word in _SECOND else ""
            if not person or not want[person]:
                continue
            forms = []
            for j in range(max(0, k - WINDOW), min(len(words), k + 1 + WINDOW)):
                w = words[j]
                if j == k or not past_gender(w):
                    continue
                between = words[min(j, k) + 1: max(j, k)]
                if w.endswith(("ів", "їв")) and any(b not in _PARTICLES for b in between):
                    continue
                forms.append((w, past_gender(w)))
            # Only when no nearby form has the right gender ("я не бачила тебе багато років" is fine)
            if forms and all(g != want[person] for _, g in forms):
                role = "S" if person == "я" else "A"
                problem = f"«{person} {forms[0][0]}», but {role} is {want[person]}"
                if problem not in problems:
                    problems.append(problem)
    return problems
