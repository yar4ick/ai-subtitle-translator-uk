"""Measure how well the model tells who speaks (S>A) against hand-made labels.

Development tool, not part of the package.

    python tools/speakers.py template en.srt 26-56 [more ranges] -o labels.txt
        Write a labeling sheet: one line per subtitle, "number  time  English  →".
        Fill in after → the speaker, as a cast code or English name:
            31 … → Gloria
            14 … → David, Gloria        (a two-speaker subtitle "- A / - B")
        Leave → empty for lines you are not sure of; they are not scored.

    python tools/speakers.py names film.srt labels.txt
        Show how the names in the labels map to cast codes of the glossary.

    python tools/speakers.py score film.srt labels.txt
        Compare the labels with the S>A codes stored in film.aisubs/done/
        and print the metrics from docs/speaker-review.md.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aisubs import checks, exchange, glossary, srt  # noqa: E402
from aisubs.project import Project  # noqa: E402

_TAG_RE = re.compile(r"<[^>]+>|\{\\[^}]*\}")
_LABEL_RE = re.compile(r"^\s*(\d+)\b.*→\s*(.*?)\s*$")


def ranges(specs: list[str]) -> list[int]:
    out = []
    for spec in specs:
        a, _, b = spec.partition("-")
        out += range(int(a), int(b or a) + 1)
    return out


def template(en: Path, specs: list[str]) -> str:
    cues = srt.read(en).cues
    lines = ["# Speaker labels. After → write the speaker (cast code or English name);", "# two names, comma-separated, for a \"- A / - B\" subtitle. Empty = not sure.", ""]
    previous = None
    for n in ranges(specs):
        if not 1 <= n <= len(cues):
            continue
        if previous is not None and n != previous + 1:
            lines.append("")
        c = cues[n - 1]
        text = re.sub(r"\s+", " ", _TAG_RE.sub("", c.text)).strip()
        lines.append(f"{n:>5}  {srt.format_time(c.start)[:8]}  {text}  →")
        previous = n
    return "\n".join(lines) + "\n"


def read_labels(path: Path) -> dict[int, list[str]]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#"):
            continue
        m = _LABEL_RE.match(line)
        if m and m.group(2):
            out[int(m.group(1))] = [x.strip() for x in m.group(2).split(",") if x.strip()]
    return out


UNNAMED = "~"  # a person who is not in the cast: the model should answer ч/ж/x, not a cast code
_FEMALE = re.compile(r"\b(woman|girl|lady|mother|mom|wife|daughter|sister|nurse|waitress|female)\b", re.I)
_MALE = re.compile(r"\b(man|boy|guy|father|dad|husband|son|brother|male)\b", re.I)
# Not a person in the scene: the model should answer `-`
_OFFSCREEN = re.compile(r"\b(tv|radio|robot|machine|computer|announcer|narrator|presenter|news|sign|song|caption|voice ?mail)\b", re.I)


def name_matcher(g: glossary.Glossary):
    """Label -> cast code, tolerant to spelling ("Steinfild" -> Stansfield); UNNAMED otherwise."""
    words: dict[str, str] = {}
    for code, en, uk, *_ in g.cast:
        words[code.lower()] = code
        for name in (en, uk):
            name = name.strip(" ?").lower()
            words[name] = code
            for w in re.findall(r"[\w']+", name):
                if len(w) > 2 and w not in ("mrs", "mr", "dr", "detective"):
                    words.setdefault(w, code)

    def match(label: str) -> str:
        if _OFFSCREEN.search(label):
            return "-"
        key = label.strip().lower()
        if key in words:
            return words[key]
        close = difflib.get_close_matches(key, words, n=1, cutoff=0.7)
        return words[close[0]] if close else UNNAMED

    return match


def score(film: Path, labels_path: Path) -> str:
    project = Project(film).load()
    g = project.glossary()
    match = name_matcher(g)
    gender = checks.genders(g)
    labels = read_labels(labels_path)

    # Subtitle number (in the source file) -> [(chunk, key)] for its parts
    cue_no = {(c.start, c.end): n for n, c in enumerate(srt.read(film).cues, 1)}
    where: dict[int, list[tuple[int, str]]] = {}
    for k, chunk in enumerate(project.chunks):
        for key, i, p in exchange.chunk_keys(project.items, chunk):
            n = cue_no.get((project.items[i].start, project.items[i].end))
            if n:
                where.setdefault(n, []).append((k, key))
    speakers = project.speakers()

    rows = []  # (number, key, expected code, model code, unsure)
    unknown = set()
    for n, names in sorted(labels.items()):
        parts = where.get(n, [])
        for (k, key), name in zip(parts, names):
            expected = match(name)
            sa = speakers.get(k, {}).get(key)
            if sa is None:
                continue
            s = sa.partition(">")[0]
            model = checks.base_code(s)
            if expected == UNNAMED:
                unknown.add(name)
                # Right if the model also used a non-cast code of a compatible gender
                want = "ж" if _FEMALE.search(name) else "ч" if _MALE.search(name) else ""
                if model in ("ч", "ж", "x") and (not want or model in (want, "x")):
                    model = UNNAMED
            rows.append((n, key, expected, model, "?" in s))
    if not rows:
        return "No labelled lines matched translated lines.\n"

    total = len(rows)
    right = sum(e == m for _, _, e, m, _ in rows)
    wrong = [r for r in rows if r[2] != r[3]]
    silent = [r for r in wrong if not r[4]]
    unsure = [r for r in rows if r[4]]
    gendered = [(e, m) for _, _, e, m, _ in rows if gender.get(e)]
    same_gender = sum(gender[e] == gender.get(m) for e, m in gendered)
    sure = [r for r in rows if not r[4]]
    out = [
        f"Labelled lines scored: {total}" + (f" (not in the cast, scored as unnamed: {', '.join(sorted(unknown))})" if unknown else ""),
        f"Speaker right: {right}/{total} ({right / total:.0%})",
        f"Silent errors (wrong, no ?): {len(silent)}/{total} ({len(silent) / total:.1%})",
        f"Right among sure: {sum(r[2] == r[3] for r in sure)}/{len(sure)}",
        f"Marked ?: {len(unsure)}, of them wrong: {sum(r[2] != r[3] for r in unsure)}; wrong lines marked: {len(wrong) - len(silent)}/{len(wrong)}",
        f"Speaker gender right: {same_gender}/{len(gendered)} (lines of cast members)",
        "",
        "Wrong lines (number, key, expected, model):",
    ]
    out += [f"  {n:>4} {key:>4}  {e:<4} {m}{'?' if u else ''}" for n, key, e, m, u in wrong]
    return "\n".join(out) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    t = sub.add_parser("template")
    t.add_argument("en", type=Path)
    t.add_argument("ranges", nargs="+", help="subtitle numbers, e.g. 26-56 95-130")
    t.add_argument("-o", "--output", type=Path, required=True)
    nm = sub.add_parser("names", help="show how label names map to cast codes")
    nm.add_argument("film", type=Path)
    nm.add_argument("labels", type=Path)
    s = sub.add_parser("score")
    s.add_argument("film", type=Path, help="the prepared and translated .srt")
    s.add_argument("labels", type=Path)
    args = p.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if args.command == "template":
        if args.output.exists():
            sys.exit(f"{args.output} exists; not overwriting labels")
        args.output.write_text(template(args.en, args.ranges), encoding="utf-8")
        print(f"Wrote {args.output}")
    elif args.command == "names":
        g = Project(args.film).load().glossary()
        match = name_matcher(g)
        cast = {c[0]: c[1] for c in g.cast} | {"-": "(narration, TV, machines)"}
        for name in sorted({n for v in read_labels(args.labels).values() for n in v}):
            code = match(name)
            print(f"{name:<24} -> {code} {cast.get(code, '(not in cast)')}")
    else:
        sys.stdout.write(score(args.film, args.labels))
    return 0


if __name__ == "__main__":
    sys.exit(main())
