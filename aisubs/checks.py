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
        gender = gender.strip(" ?").lower()
        if gender in ("ч", "ж"):
            out[code] = gender
    return out


def gender_conflicts(text: str, speakers: str, cast: dict[str, str]) -> list[str]:
    """Problems like "я забув: S is ж" for one line; `speakers` is "S>A"."""
    s, _, a = speakers.partition(">")
    want = {"я": cast.get(s.strip(), ""), "ти": cast.get(a.strip(), "")}
    problems = []
    for sentence in _SENTENCE_RE.findall(text):
        words = [w.lower() for w in _WORD_RE.findall(sentence)]
        for k, word in enumerate(words):
            person = "я" if word in _FIRST else "ти" if word in _SECOND else ""
            if not person or not want[person]:
                continue
            near = words[max(0, k - WINDOW): k] + words[k + 1: k + 1 + WINDOW]
            forms = [(w, past_gender(w)) for w in near if past_gender(w)]
            # Only when no nearby form has the right gender ("я не бачила тебе багато років" is fine)
            if forms and all(g != want[person] for _, g in forms):
                role = "S" if person == "я" else "A"
                problem = f"«{person} {forms[0][0]}», but {role} is {want[person]}"
                if problem not in problems:
                    problems.append(problem)
    return problems
