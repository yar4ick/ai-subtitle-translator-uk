"""Check an answer to invented scenes against what it must satisfy: a cheap test of prompt changes.

Development tool, not part of the package. The scenes are made up (tests/regress/scenes.txt),
so they can be committed and run on any model:

    python tools/regress.py request [scenes.txt]       print the full request (instructions, glossary, lines)
    python tools/regress.py check answer.txt [scenes.txt]   print the numbers and what failed

Give the request to the model (an agent or a chat) and save its answer; run `check` twice
for every prompt change: the spread between two answers shows at once.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aisubs import checks, exchange, glossary, limits  # noqa: E402

SCENES = Path(__file__).resolve().parent.parent / "tests" / "regress" / "scenes.txt"
_LINE_RE = re.compile(r"^(\d+[a-z]?)\|(?:≤(\d+)\|)?(.*?)\s*(?:##\s*(.*))?$")
_LATIN_RE = re.compile(r"[A-Za-z]")
_RUSSIAN_RE = re.compile(r"[ЫыЭэЪъЁё]")


def load(path: Path):
    """(glossary, [(id, limit, english, expectations)], request lines)."""
    g_lines, lines, request = [], [], []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        if raw.strip() == "=":
            request.append("=")
            continue
        m = _LINE_RE.match(raw)
        if not m:
            g_lines.append(raw)
            continue
        key, limit, text, expect = m.groups()
        want = {}
        for field in (expect or "").split():
            name, _, value = field.partition("=")
            want[name] = value
        lines.append((key, int(limit) if limit else None, text, want))
        request.append("|".join([key] + ([f"≤{limit}"] if limit else []) + [text]))
    g, _ = glossary.parse("\n".join(g_lines))
    return g, lines, request


def build(path: Path) -> str:
    g, _, request = load(path)
    while request and request[0] == "=":
        request.pop(0)
    out = [exchange.instructions("Riverside (invented)"), "", "GLOSSARY", glossary.render(g), "", "TRANSLATE (part 1 of 1):"]
    return "\n".join(out + request) + "\n"


def _has(text: str, stem: str) -> bool:
    whole = stem.endswith("$")
    stem = stem.rstrip("$")
    return bool(re.search(r"(?<![\w])" + re.escape(stem) + (r"(?![\w])" if whole else ""), text, re.IGNORECASE))


def check(answer_text: str, path: Path) -> tuple[dict, list[str]]:
    g, lines, _ = load(path)
    answer, _ = exchange.parse_answer(answer_text)
    cast = checks.genders(g)
    n = {"lines": len(lines), "missing": 0, "speaker": 0, "speaker_checked": 0, "addressee": 0, "addressee_checked": 0,
         "gender": 0, "forbidden": 0, "required": 0, "too_long": 0, "latin": 0, "russian": 0}
    failed = []
    for key, limit, english, want in lines:
        if key not in answer:
            n["missing"] += 1
            failed.append(f"{key}: missing")
            continue
        text, _, sa = answer[key]
        s, _, a = sa.partition(">")
        s, a = checks.base_code(s), checks.base_code(a)
        if "S" in want:
            n["speaker_checked"] += 1
            if s == want["S"]:
                n["speaker"] += 1
            else:
                failed.append(f"{key}: speaker {s or '-'}, expected {want['S']} | {english}")
        if "A" in want:
            n["addressee_checked"] += 1
            if a == want["A"]:
                n["addressee"] += 1
            else:
                failed.append(f"{key}: addressee {a or '-'}, expected {want['A']} | {english}")
        # Gender against the expected speakers, not the ones the model chose
        expected = f"{want.get('S', s)}>{want.get('A', a)}"
        for problem in checks.gender_conflicts(text, expected, cast):
            n["gender"] += 1
            failed.append(f"{key}: gender {problem} | {text}")
        # past=ч / past=ж: every past-tense form of the line must have this gender ("Ключі забула?" to a man)
        if want.get("past") in ("ч", "ж"):
            wrong = [w for w in re.findall(r"[а-яіїєґʼ'’]+", text.lower()) if checks.past_gender(w) not in ("", want["past"])]
            if wrong:
                n["gender"] += 1
                failed.append(f"{key}: past tense {', '.join(wrong)}, expected {want['past']} | {text}")
        for stem in filter(None, want.get("forbid", "").split(",")):
            if _has(text, stem):
                n["forbidden"] += 1
                failed.append(f"{key}: has «{stem}» | {text}")
        for stem in filter(None, want.get("require", "").split(",")):
            if not any(_has(text, alt) for alt in stem.split("/")):
                n["required"] += 1
                failed.append(f"{key}: no «{stem}» | {text}")
        if limit and len(limits.visible(text)) > limit:
            n["too_long"] += 1
            failed.append(f"{key}: {len(limits.visible(text))} characters, limit {limit} | {text}")
        if want.get("latin") != "ok" and _LATIN_RE.search(text):
            n["latin"] += 1
            failed.append(f"{key}: Latin letters | {text}")
        if _RUSSIAN_RE.search(text):
            n["russian"] += 1
            failed.append(f"{key}: Russian letters | {text}")
    return n, failed


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in ("request", "check"):
        print(__doc__)
        return 1
    if sys.argv[1] == "request":
        sys.stdout.write(build(Path(sys.argv[2]) if len(sys.argv) > 2 else SCENES))
        return 0
    if len(sys.argv) < 3:
        print("usage: python tools/regress.py check answer.txt [scenes.txt]")
        return 1
    n, failed = check(Path(sys.argv[2]).read_text(encoding="utf-8"), Path(sys.argv[3]) if len(sys.argv) > 3 else SCENES)
    print(f"lines {n['lines']}, missing {n['missing']}")
    print(f"speaker right {n['speaker']}/{n['speaker_checked']}, addressee right {n['addressee']}/{n['addressee_checked']}")
    print(f"gender errors {n['gender']}, forbidden words {n['forbidden']}, required words missing {n['required']}")
    print(f"too long {n['too_long']}, Latin {n['latin']}, Russian letters {n['russian']}")
    if failed:
        print("\n" + "\n".join(failed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
