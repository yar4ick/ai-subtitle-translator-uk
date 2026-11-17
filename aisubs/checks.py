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
_NOT_VERBS = set("агов знов любов кров морков років друзів хлопців батьків грошей слів часів разів днів тижнів доларів братів".split())
# «-ів» is as often a plural noun (копів, псів) as a verb (хотів, сидів): such a word counts
# only right next to «я» / «ти», with nothing but these words between them
_PARTICLES = set("не ж же вже би б теж також ще аж навіть просто так дуже завжди ніколи справді тоді тут там й і".split())


# Masculine past tense that is short or does not end in -в
_SHORT_MASC = set("був мав дав жив їв пив бив вив шив мив рив крив міг зміг допоміг зник звик замовк "
                  "приніс заніс відніс ніс віз привіз біг втік утік ліг сів ріс виріс помер вмер умер спік".split())


def past_gender(word: str) -> str:
    """'ч' / 'ж' for a word that looks like a singular past-tense verb, else ''."""
    w = word.lower()
    if w in _SHORT_MASC:
        return "ч"
    if len(w) < 4:
        return ""
    if w.endswith(("лася", "лась", "ла")):
        return "ж"
    if w.endswith(("вся", "в")) and w not in _NOT_VERBS:
        return "ч"
    return ""


# Words that show the speaker's or addressee's gender without a past-tense verb
_GENDERED = set("радий рада певен певна певний згоден згодна сам сама винен винна готовий готова живий жива "
                "самотній самотня втомився втомилася голодний голодна потрібен потрібна вагітна".split())
# Forms of address with gender: «Привіт, кохана» says that A is a woman
ADDRESS = {"кохана": "ж", "коханий": "ч", "люба": "ж", "любий": "ч", "мила": "ж", "милий": "ч",
           "рідна": "ж", "рідний": "ч", "серденько": "", "сонечко": ""}
# A sentence about someone else: its past tense says nothing about the speaker or the addressee
_THIRD = set("він вона воно вони це то той та те хтось ніхто все усе всі усі щось ніщо".split())
_PERSONAL = set("я ти мене тебе мені тобі мною тобою".split())


def shows_gender(text: str) -> bool:
    """True if the Ukrainian line has a form that depends on the gender of the speaker or the
    addressee: «забув», «Ти був там?», «Я впевнений», «Привіт, кохана». A doubt about who
    speaks matters for the translation only in such lines; «Це була найкраща ніч» is not one."""
    for sentence in _SENTENCE_RE.findall(text):
        words = [w.lower() for w in _WORD_RE.findall(sentence)]
        personal = any(w in _PERSONAL for w in words)
        if any(w in ADDRESS and ADDRESS[w] for w in words):
            return True
        for k, w in enumerate(words):
            if w in _GENDERED or (past_gender(w) and (personal or not set(words[:k]) & _THIRD)):
                return True
            # «я впевнений», «ти справжня»: an adjective right after я / ти
            if w in ("я", "ти") and k + 1 < len(words):
                nxt = words[k + 1]
                if len(nxt) > 4 and nxt.endswith(("ий", "ій", "а", "я")):
                    return True
    return False


def address_conflicts(text: str, speakers: str, cast: dict[str, str]) -> list[str]:
    """«Привіт, кохана» to a man: a form of address whose gender is not A's."""
    _, _, a = speakers.partition(">")
    want = cast.get(base_code(a), "")
    if not want:
        return []
    out = []
    for m in re.finditer(r"(?:^|[,—–-]\s*)([а-яіїєґʼ'’]+)\s*(?=[,.!?…]|$)", text.lower()):
        g = ADDRESS.get(m.group(1), "")
        if g and g != want:
            out.append(f"«{m.group(1)}», but A is {want}")
    return out


_TI = set("ти тебе тобі тобою твій твоя твоє твої твого твоєї твоїх твоїм твоєму".split())
_VY = set("ви вас вам вами ваш ваша ваше ваші вашого вашої ваших вашим вашому".split())


def formality(text: str) -> str:
    """'ти' / 'ви' if the line uses only one of them, else ''."""
    words = {w.lower() for w in _WORD_RE.findall(text)}
    ti, vy = bool(words & _TI), bool(words & _VY)
    return "ти" if ti and not vy else "ви" if vy and not ti else ""


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
