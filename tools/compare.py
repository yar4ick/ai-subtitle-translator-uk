"""Compare our Ukrainian subtitles with a human (reference) translation.

Development tool, not part of the package. Usage:

    python tools/compare.py en.srt ours.uk.srt ref.uk.srt [-o report.md]

The reference may come from another release: a constant offset and the usual
frame-rate differences are detected from cue start times. Cues are matched
by overlap in time; only our cues that are actually translated (have
Cyrillic) are compared. Disagreements in gender, number and ти/ви are found
with simple suffix and pronoun rules, so the report lists candidates, not
verdicts.
"""

from __future__ import annotations

import argparse
import bisect
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aisubs import limits, srt  # noqa: E402

_CYRILLIC_RE = re.compile(r"[а-яіїєґ]", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>|\{\\[^}]*\}")
_WORD_RE = re.compile(r"[а-яіїєґʼ'’-]+", re.IGNORECASE)
_SCALES = {
    "1": 1.0,
    "25→23.976": 25 / 23.976,
    "23.976→25": 23.976 / 25,
    "24→23.976": 24 / 23.976,
    "23.976→24": 23.976 / 24,
    "25→24": 25 / 24,
    "24→25": 24 / 25,
}
# Past tense / short forms: (feminine, masculine) endings
_GENDER_PAIRS = [("лася", "вся"), ("ла", "в")]
_TI = {"ти", "тебе", "тобі", "тобою", "твій", "твоя", "твоє", "твої", "твого", "твоєї", "твоїх", "твоїм", "твоєму"}
_VY = {"ви", "вас", "вам", "вами", "ваш", "ваша", "ваше", "ваші", "вашого", "вашої", "ваших", "вашим", "вашому"}


def read(path: Path, encoding: str | None) -> list[srt.Cue]:
    data = path.read_bytes()
    if encoding is None:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            # Ukrainian subtitles that are not UTF-8 are almost always cp1251
            encoding = "cp1251" if not data.startswith((b"\xff\xfe", b"\xfe\xff")) else None
    return srt.parse(data, encoding).cues


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub("", text)).strip()


def detect_timing(ours: list[srt.Cue], ref: list[srt.Cue]) -> tuple[str, float, int]:
    """Return (scale name, scale, offset ms) mapping ref times onto ours."""
    starts = sorted(c.start for c in ours)
    best = ("1", 1.0, 0, -1)
    for name, scale in _SCALES.items():
        votes: Counter[int] = Counter()
        for r in ref:
            t = r.start * scale
            lo, hi = bisect.bisect_left(starts, t - 120_000), bisect.bisect_right(starts, t + 120_000)
            for s in starts[lo:hi]:
                votes[round((s - t) / 200)] += 1
        if votes:
            bin_, count = votes.most_common(1)[0]
            if count > best[3]:
                best = (name, scale, bin_ * 200, count)
    return best[0], best[1], best[2]


def align(ours: list[srt.Cue], ref: list[srt.Cue], scale: float, offset: int) -> list[tuple[list[int], list[int]]]:
    """Group overlapping cues: [(our indices, ref indices)]. Our cues without a match get []."""
    mapped = [(r.start * scale + offset, r.end * scale + offset) for r in ref]
    parent = list(range(len(ours) + len(ref)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    j0 = 0
    for i, c in enumerate(ours):
        while j0 < len(mapped) and mapped[j0][1] <= c.start:
            j0 += 1
        j = j0
        while j < len(mapped) and mapped[j][0] < c.end:
            a, b = mapped[j]
            overlap = min(b, c.end) - max(a, c.start)
            if overlap > 0.3 * min(b - a, c.end - c.start):
                parent[find(i)] = find(len(ours) + j)
            j += 1
    groups: dict[int, tuple[list[int], list[int]]] = {}
    for i in range(len(ours)):
        groups.setdefault(find(i), ([], []))[0].append(i)
    for j in range(len(ref)):
        root = find(len(ours) + j)
        if root in groups:
            groups[root][1].append(j)
    return sorted(groups.values(), key=lambda g: g[0][0])


def words(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


def gender_marks(text: str) -> dict[str, str]:
    """{stem: 'ж' | 'ч' | 'мн'} for past-tense-looking words."""
    marks = {}
    for w in words(text):
        if len(w) < 4:
            continue
        if w.endswith(("лися", "ли")):
            marks[w[: -4 if w.endswith("лися") else -2]] = "мн"
            continue
        for fem, masc in _GENDER_PAIRS:
            if w.endswith(fem):
                marks[w[: -len(fem)]] = "ж"
                break
            if w.endswith(masc):
                marks[w[: -len(masc)]] = "ч"
                break
    return marks


def formality(text: str) -> str:
    ws = set(words(text))
    ti, vy = bool(ws & _TI), bool(ws & _VY)
    return "ти" if ti and not vy else "ви" if vy and not ti else ""


def cps(text: str, cue: srt.Cue) -> float:
    return limits.cps(_TAG_RE.sub("", text), cue.start, cue.end)


def capitalized(cues: list[srt.Cue]) -> Counter[str]:
    names: Counter[str] = Counter()
    for c in cues:
        for sentence in re.split(r"[.!?…]\s+|\n-|^-", plain(c.text)):
            for w in re.findall(r"(?<=\s)[А-ЯІЇЄҐ][а-яіїєґʼ']+", " " + sentence.strip())[1:]:
                names[w] += 1
    return names


def report(en: list[srt.Cue], ours: list[srt.Cue], ref: list[srt.Cue], title: str, samples: int) -> str:
    timing = detect_timing(ours, ref)
    groups = align(ours, ref, timing[1], timing[2])
    translated = [g for g in groups if any(_CYRILLIC_RE.search(ours[i].text) for i in g[0])]
    matched = [g for g in translated if g[1]]

    def text(cues, idx):
        return " / ".join(plain(cues[i].text) for i in idx)

    # Our cues keep the source timings, so the English text is found by time
    en_at = {(c.start, c.end): k for k, c in enumerate(en)}

    def en_idx(idx):
        return [en_at[(ours[i].start, ours[i].end)] for i in idx if (ours[i].start, ours[i].end) in en_at]

    rows_gender, rows_form = [], []
    for g in matched:
        o, r = text(ours, g[0]), text(ref, g[1])
        mo, mr = gender_marks(o), gender_marks(r)
        diff = sorted(s for s in mo.keys() & mr.keys() if mo[s] != mr[s])
        if diff:
            rows_gender.append((g, ", ".join(f"{s}-: {mo[s]}≠{mr[s]}" for s in diff)))
        fo, fr = formality(o), formality(r)
        if fo and fr and fo != fr:
            rows_form.append((g, f"{fo}≠{fr}"))

    def stats(cues, idx_list):
        all_idx = [i for idx in idx_list for i in idx]
        lines = [plain(l) for i in all_idx for l in cues[i].text.split("\n")]
        rates = [cps(cues[i].text, cues[i]) for i in all_idx]
        n = max(1, len(rates))
        chars = sum(len(plain(cues[i].text)) for i in all_idx)
        return chars, sum(len(l) > 42 for l in lines) / max(1, len(lines)), sum(r > 17 for r in rates) / n, sum(r > 20 for r in rates) / n

    so = stats(ours, [g[0] for g in matched])
    sr = stats(ref, [g[1] for g in matched])
    se = stats(en, [en_idx(g[0]) for g in matched])

    out = [f"# Порівняння: {title}", ""]
    out += [
        f"- Наших перекладених субтитрів: {sum(len(g[0]) for g in translated)}, з них зіставлено з еталоном: {sum(len(g[0]) for g in matched)}",
        f"- Синхронізація еталону: частота кадрів {timing[0]}, зсув {timing[2] / 1000:+.1f} с",
        "",
        "| | Оригінал (EN) | Наш | Еталон |",
        "|---|---|---|---|",
        f"| Символів | {se[0]} | {so[0]} | {sr[0]} |",
        f"| Рядків > 42 символів | {f'{se[1]:.1%}'} | {so[1]:.1%} | {sr[1]:.1%} |",
        f"| Субтитрів > 17 CPS | {f'{se[2]:.1%}'} | {so[2]:.1%} | {sr[2]:.1%} |",
        f"| Субтитрів > 20 CPS | {f'{se[3]:.1%}'} | {so[3]:.1%} | {sr[3]:.1%} |",
        "",
        "Символи й CPS еталону рахуються на тих самих сценах; якщо еталон зливає чи ділить субтитри інакше, порівнюйте лише відношення.",
        "",
    ]

    def table(rows, heading, note):
        nonlocal out
        out += [f"## {heading} ({len(rows)})", "", note, ""]
        if not rows:
            out += ["Немає.", ""]
            return
        out += ["| # | Оригінал | Наш | Еталон | Різниця |", "|---|---|---|---|---|"]
        for g, diff in rows:
            en_text = text(en, en_idx(g[0]))
            cell = lambda s: s.replace("|", "\\|")
            out.append(f"| {g[0][0] + 1} | {cell(en_text)} | {cell(text(ours, g[0]))} | {cell(text(ref, g[1]))} | {diff} |")
        out.append("")

    table(rows_gender, "Розбіжності в роді й числі", "Слова з тією самою основою, але різним закінченням минулого часу (ж — -ла, ч — -в, мн — -ли). Кандидати: частина з них — різні дієслова з однаковою основою або різна побудова фрази.")
    table(rows_form, "Розбіжності ти / ви", "У нашому перекладі і в еталоні різні займенники звертання.")

    names_o, names_r = capitalized(ours), capitalized(ref)
    out += ["## Імена та слова з великої літери (не на початку речення)", "", "| Наш | к-сть | Еталон | к-сть |", "|---|---|---|---|"]
    top_o, top_r = names_o.most_common(20), names_r.most_common(20)
    for k in range(max(len(top_o), len(top_r))):
        a = top_o[k] if k < len(top_o) else ("", "")
        b = top_r[k] if k < len(top_r) else ("", "")
        out.append(f"| {a[0]} | {a[1]} | {b[0]} | {b[1]} |")
    out.append("")

    rng = random.Random(0)
    sample = sorted(rng.sample(matched, min(samples, len(matched))), key=lambda g: g[0][0])
    out += [f"## Випадкова вибірка ({len(sample)})", "", "| # | Оригінал | Наш | Еталон |", "|---|---|---|---|"]
    for g in sample:
        en_text = text(en, en_idx(g[0]))
        cell = lambda s: s.replace("|", "\\|")
        out.append(f"| {g[0][0] + 1} | {cell(en_text)} | {cell(text(ours, g[0]))} | {cell(text(ref, g[1]))} |")
    out.append("")
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("en", type=Path, help="English source SRT")
    p.add_argument("ours", type=Path, help="our .uk.srt (assembled with --partial is fine)")
    p.add_argument("ref", type=Path, help="reference Ukrainian SRT")
    p.add_argument("-o", "--output", type=Path, help="report file (default: stdout)")
    p.add_argument("--ref-encoding", help="reference encoding if detected wrongly")
    p.add_argument("--samples", type=int, default=30, help="random aligned pairs to show (default: 30)")
    p.add_argument("--title", default="", help="film title for the report")
    args = p.parse_args()

    en, ours, ref = read(args.en, None), read(args.ours, None), read(args.ref, args.ref_encoding)
    text = report(en, ours, ref, args.title or args.ours.stem, args.samples)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
