"""A file for a person to review doubtful places, and reading their edits back.

`aisubs review film.srt` writes `film.aisubs/review.txt`: the scenes around
lines that need a look, each translation as `part:ID|S>A|translation` under
its English line. The person edits translations or speaker codes in place
and runs `aisubs review film.srt --apply`.
"""

from __future__ import annotations

import re

from . import exchange, prepare
from .validate import Problem

AROUND = 4  # lines of the scene shown before and after a doubtful line
_LINE_RE = re.compile(r"^(\d+):(\d+[a-z]?)\|(.*)$")


def render(project, problems: list[Problem], film: str) -> tuple[str, int]:
    """Text of the review file and the number of lines to look at."""
    marks: dict[tuple[int, str], list[str]] = {}
    for p in problems:
        if not p.fix:
            marks.setdefault((p.k, p.key), []).append(p.message)
    g = project.glossary()
    codes = ", ".join(f"{c[0]} {c[2]}" for c in g.cast)
    out = [
        "# Look at the lines marked with !. Fix a translation after the second |, or the speakers",
        "# (S>A) between the | marks. `?` after a code means the AI was unsure who speaks: delete it",
        "# when the code is right. Lines you do not touch stay as they are. Then run:",
        f"#   aisubs review {film} --apply",
    ]
    if codes:
        out.append(f"# Codes: {codes}; ч/ж someone not in the cast, x unknown, * a group, - narration")
    done, speakers = project.done(), project.speakers()
    notes = project.notes()
    scenes = prepare.make_scenes(project.items, project.meta["scene_gap"])
    scene_of = {i: n for n, (a, b) in enumerate(scenes) for i in range(a, b)}

    for k, chunk in enumerate(project.chunks):
        keys = project.chunk_keys(k)
        wanted = [n for n, (key, _, _) in enumerate(keys) if (k, key) in marks]
        if not wanted:
            continue
        # Windows around the marked lines, within their scenes, merged when they touch
        shown: list[list[int]] = []
        for n in wanted:
            scene = scene_of[keys[n][1]]
            lo, hi = n, n
            while lo > 0 and n - lo < AROUND and scene_of[keys[lo - 1][1]] == scene:
                lo -= 1
            while hi + 1 < len(keys) and hi - n < AROUND and scene_of[keys[hi + 1][1]] == scene:
                hi += 1
            if shown and lo <= shown[-1][1] + 1:
                shown[-1][1] = max(shown[-1][1], hi)
            else:
                shown.append([lo, hi])
        for lo, hi in shown:
            first, last = keys[lo][0], keys[hi][0]
            out += ["", f"== part {k + 1}, lines {first}–{last}"]
            index = {key: n for n, (key, _, _) in enumerate(keys)}
            for a, b, note in notes.get(k, []):
                if a in index and b in index and index[a] <= hi and index[b] >= lo:
                    out.append(f"   AI note {a}–{b}: {note}")
            for key, i, p in keys[lo: hi + 1]:
                out.append(f"   {project.items[i].parts[p].text}")
                for message in marks.get((k, key), []):
                    out.append(f"!  {message}")
                sa = speakers.get(k, {}).get(key, "")
                out.append(f"{k + 1}:{key}|{sa + '|' if sa else ''}{done.get(k, {}).get(key, '')}")
    return "\n".join(out) + "\n", len(marks)


def apply(project, text: str, *, dry_run: bool = False) -> tuple[list[tuple[int, str]], list[str]]:
    """Save the edited lines. Return ([(part, key)] changed, problems with the file)."""
    done, speakers = project.done(), project.speakers()
    edits: dict[int, dict] = {}
    errors = []
    for line in text.splitlines():
        m = _LINE_RE.match(line.strip())
        if not m:
            continue
        k, key = int(m.group(1)) - 1, m.group(2)
        if not 0 <= k < len(project.chunks) or key not in project.keys(k):
            errors.append(f"no such line: {m.group(1)}:{key}")
            continue
        answer, _ = exchange.parse_answer(f"{key}|{m.group(3)}")
        if key not in answer or not answer[key][0].strip():
            errors.append(f"empty translation: {m.group(1)}:{key}")
            continue
        new_text, flagged, sa = answer[key]
        if new_text.strip() != done.get(k, {}).get(key) or sa != speakers.get(k, {}).get(key, ""):
            edits.setdefault(k, {})[key] = (new_text, flagged, sa)
    if dry_run:
        return [(k, key) for k, answer in edits.items() for key in answer], errors
    changed = []
    for k, answer in edits.items():
        changed += [(k, key) for key in project.save(k, answer, reviewed=True)["accepted"]]
    return changed, errors
