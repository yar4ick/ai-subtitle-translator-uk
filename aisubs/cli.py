"""Command line: aisubs guide | prepare | glossary | status | next | import | validate | fix | review | assemble."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from . import __version__, assemble, exchange, glossary, guide, prepare, review, srt, validate
from .project import Project, ProjectError


def cmd_guide(args) -> int:
    sys.stdout.write(guide.text(args.film or "", args.command))
    return 0


def cmd_prepare(args) -> int:
    project = Project(args.film)
    if not args.force and project.has_translations():
        # A restarted agent begins with step 1 again: never offer to delete the work done
        project.load()
        pending = project.pending_chunk()
        print(f"Already prepared: {project.dir} has translations. Continue where it stopped:")
        if pending is None:
            print(f"all parts are translated; next: aisubs validate {args.film}, then aisubs assemble {args.film}")
        else:
            print(f"aisubs next {args.film}  (part {pending + 1} of {len(project.chunks)})")
        print("To start over and delete the translations (only if the user asks): add --force")
        return 0
    parsed = project.create(
        title=args.title,
        keep_sdh=args.keep_sdh,
        chunk_size=args.chunk_size,
        scene_gap=args.scene_gap,
        encoding=args.encoding,
        force=args.force,
    )
    for warning in parsed.warnings[:20]:
        print(f"warning: {warning}")
    if len(parsed.warnings) > 20:
        print(f"warning: … and {len(parsed.warnings) - 20} more")
    m = project.meta
    lines = sum(len(project.keys(k)) for k in range(len(project.chunks)))
    print(f"Title: {m['title']}  (wrong? rerun with --title \"Name (year)\")")
    print(f"Subtitles: {m['cues']}, dropped (ads, SDH-only, empty): {m['dropped']}, lines to translate: {lines}")
    print(f"Parts: {len(project.chunks)}")
    if args.wikipedia is not None:
        print(project.fetch_wikipedia(args.wikipedia))
    if args.glossary:
        print()
        sys.stdout.write(project.glossary_request())
        return 0
    print(f"Next: aisubs glossary {args.film}  (or skip it: aisubs next {args.film})")
    return 0


def _header(project: Project) -> str:
    """Instructions and glossary, as at the top of a full request."""
    g = project.glossary()
    text = exchange.instructions(project.meta["title"])
    return text if g.is_empty() else f"{text}\n\nGLOSSARY\n{glossary.render(g)}"


def _request(project: Project, k: int, brief: bool) -> str:
    g = project.glossary()
    scenes = prepare.make_scenes(project.items, project.meta["scene_gap"])
    return exchange.build_request(
        project.items, project.chunks, k, project.done(), project.meta["title"],
        brief=brief, glossary_block="" if g.is_empty() else glossary.render(g),
        scene_starts=frozenset(a for a, _ in scenes[1:]), speaker_codes=glossary.speaker_codes(g),
        starts=project.starts(),
    )


def cmd_glossary(args) -> int:
    project = Project(args.film).load()
    if args.wikipedia is not None:
        print(project.fetch_wikipedia(args.wikipedia), file=sys.stderr)
    if args.answer is None:
        sys.stdout.write(project.glossary_request())
        return 0
    text = sys.stdin.read() if args.answer == "-" else Path(args.answer).read_text(encoding="utf-8-sig")
    g, ignored = glossary.parse(text)
    if g.is_empty():
        raise ProjectError("no glossary lines found (expected STYLE|, PLOT|, C|, P|, T|)")
    project.save_glossary(g)
    unsure = sum(1 for row in g.cast + g.pairs + g.terms if row[-1].endswith("?") or any(v.endswith("?") for v in row))
    print(f"Glossary saved: {len(g.cast)} characters, {len(g.pairs)} pairs, {len(g.terms)} terms" + (f", {unsure} unsure (marked ?)" if unsure else ""))
    if ignored:
        print(f"ignored {len(ignored)} lines that are not glossary lines")
    if g.cast:
        # Spoiler-free: names and gender only, no plot or roles
        print("Names: " + ", ".join(f"{row[2]} ({row[3]})" for row in g.cast))
    if unsure_terms := [f"{en}={uk}" for en, uk in g.terms if uk.endswith("?")]:
        print("Unsure terms: " + ", ".join(unsure_terms))
    data = project.candidates()
    lines = [part.text for item in project.items for part in item.parts]
    warnings = glossary.cross_check(g, data["candidates"], project.source_names(), lines=lines)
    for warning in warnings:
        print(f"warning: {warning}")
    if args.next and not warnings and (k := project.pending_chunk()) is not None:
        print()
        sys.stdout.write(_request(project, k, False))
        return 0
    if args.next and warnings:
        print("Check the warnings: save a corrected glossary the same way, or go on with: aisubs next " + str(args.film))
        return 0
    print(f"Next: aisubs next {args.film}")
    return 0


def cmd_status(args) -> int:
    project = Project(args.film).load()
    done, flags = project.done(), project.flags()
    total = len(project.chunks)
    for k in range(total):
        keys = project.keys(k)
        have = len([key for key in keys if key in done.get(k, {})])
        mark = "done" if have == len(keys) else ("partial" if have else "todo")
        if k in project.meta.get("refused", []) and have < len(keys):
            mark = "refused"
        flagged = len(flags.get(k, []))
        print(f"part {k + 1:>3}/{total}: {mark:<7} {have}/{len(keys)} lines" + (f", {flagged} flagged" if flagged else ""))
    g = project.glossary()
    print("Glossary: " + ("none (aisubs glossary " + str(args.film) + ")" if g.is_empty() else f"{len(g.cast)} characters, {len(g.pairs)} pairs, {len(g.terms)} terms"))
    pending = project.pending_chunk()
    print(f"Next: aisubs next {args.film}" if pending is not None else f"All parts translated. Next: aisubs assemble {args.film}")
    return 0


def _chunk_arg(project: Project, value: int | None) -> int | None:
    if value is None:
        return project.pending_chunk()
    if not 1 <= value <= len(project.chunks):
        raise ProjectError(f"--part must be between 1 and {len(project.chunks)}")
    return value - 1


def cmd_next(args) -> int:
    project = Project(args.film).load()
    k = _chunk_arg(project, args.part)
    if k is None:
        print(f"All parts translated. Next: aisubs assemble {args.film}")
        return 0
    if project.is_complete(k):
        print(f"Part {k + 1} is already translated.")
        return 0
    sys.stdout.write(_request(project, k, args.brief))
    return 0


_REFUSAL_RE = re.compile(r"\b(I can(?:not|'t)|I'm sorry|I am sorry|I'm unable|I am unable|I won't)\b|не можу|вибачте", re.I)


def _fix_parts(project: Project, problems: list[validate.Problem]) -> list[int]:
    """Parts with lines to fix: all of them in one request when IDs run through the film,
    else (old projects, IDs from 1 in every part) the first one."""
    ks = sorted({p.k for p in problems if p.fix})
    return ks if project.meta.get("format", 1) > 1 else ks[:1]


def _gender_report(project: Project, answer: dict) -> None:
    checker = validate.Checker(project.glossary())
    for key, (text, _, sa) in answer.items():
        for problem in validate.checks.gender_conflicts(text, sa, checker.cast) if sa else []:
            print(f"gender check: {key}|{sa}|{text} — {problem}")


def _report(project: Project, problems: list[validate.Problem], stats: dict, limit: int = 30) -> list[str]:
    out = []
    n = stats["subtitles"] or 1
    out.append(f"Checked {stats['subtitles']} subtitles: reading speed over {validate.limits.CPS} CPS in "
               f"{stats['over_cps'] / n:.1%}, over {validate.limits.MAX_CPS} in {stats['over_max_cps'] / n:.1%}")
    for fix, title in ((True, "To fix (the AI gets these lines again)"), (False, "To review")):
        group = [p for p in problems if p.fix == fix]
        if not group:
            continue
        out.append(f"{title}: {len(group)}")
        for p in group[:limit]:
            out.append(f"  part {p.k + 1}, {p.key}: {p.message}\n      {p.source}\n      {p.text}")
        if len(group) > limit:
            out.append(f"  … and {len(group) - limit} more (all in {project.dir / 'report.txt'})")
    return out


def _validate(project: Project) -> tuple[list[validate.Problem], list[str]]:
    problems, stats = validate.run(project)
    lines = _report(project, problems, stats)
    (project.dir / "report.txt").write_text("\n".join(_report(project, problems, stats, limit=10**6)) + "\n", encoding="utf-8")
    return problems, lines


def _after_all_done(project: Project, args, brief_next: bool) -> int:
    """Validate; with --next also print the fix request, if any."""
    problems, lines = _validate(project)
    print("\n".join(lines))
    ks = _fix_parts(project, problems)
    if not ks:
        if brief_next:
            print("Nothing to fix.")
            return _finish(project, problems, args.film)
        nxt = "review" if problems else "assemble"
        print(f"Nothing to fix. Next: aisubs {nxt} {args.film}")
        return 0
    if brief_next:
        print()
        sys.stdout.write(validate.fix_request(project, ks, problems, brief=True))
    else:
        print(f"Next: aisubs fix {args.film}")
    return 0


def _finish(project: Project, problems: list, film) -> int:
    """The last steps without asking: the review file and the translated .srt."""
    path = project.dir / "review.txt"
    text, count = review.render(project, problems, str(film))
    if count:
        if path.exists() and review.apply(project, path.read_text(encoding="utf-8-sig"), dry_run=True)[0]:
            print(f"{path} has edits that are not saved yet; it was left as it is (aisubs review {film} --apply)")
        else:
            path.write_text(text, encoding="utf-8")
            print(f"Wrote {path}: {count} lines to look at (the user can fix them, then: aisubs review {film} --apply)")
    out = project.output_path()
    if not project.owns_output(out):
        print(f"{out} already exists and was not written by aisubs: not overwritten. Write it with: aisubs assemble {film} -o OTHER.srt")
        return 0
    _write_output(project, out, partial=False, bom=False)
    print(f"Wrote {out}. Done.")
    return 0


FULL_EVERY = 4  # parts 5, 9, 13… come with the instructions and the glossary again


def cmd_import(args) -> int:
    project = Project(args.film).load()
    if args.fix:
        problems, _ = validate.run(project)
        ks = _fix_parts(project, problems) if args.part is None else [_chunk_arg(project, args.part)]
        if not ks or ks[0] is None:
            print(f"Nothing to fix. Next: aisubs assemble {args.film}")
            return 0
        k = ks[0]
    else:
        k = _chunk_arg(project, args.part)
        if k is None:
            print("All parts are already translated.")
            return 0
    if args.answer == "-":
        text = sys.stdin.read()
    else:
        text = Path(args.answer).read_text(encoding="utf-8-sig")
    answer, ignored = exchange.parse_answer(text)
    if not args.fix and args.part is None and answer:
        # Line IDs run through the film, so the answer itself says which part it is
        own = project.part_of(answer)
        # Only when the answer has no line of the part it was asked for
        if own is not None and own != k and not set(answer) & set(project.keys(k)):
            if project.is_complete(own):
                print(f"These lines are from part {own + 1}, which is already translated: nothing saved "
                      f"(an answer sent twice?). To replace that part: aisubs import {args.film} FILE --part {own + 1}")
                if args.next:
                    print()
                    sys.stdout.write(_request(project, k, True))
                else:
                    print(f"Next: aisubs next {args.film}")
                return 0
            k = own
    if args.fix:
        # Lines of several parts in one answer: each goes to the part that asked for it
        accepted, wanted_all = [], set()
        for kk in ks:
            wanted = {p.key for p in problems if p.k == kk and p.fix}
            wanted_all |= wanted
            part_answer = {key: v for key, v in answer.items() if key in wanted}
            if part_answer:
                saved = project.save(kk, part_answer, retry=True)["accepted"]
                accepted += saved
                print(f"part {kk + 1}/{len(project.chunks)}: accepted {len(saved)} lines")
        _gender_report(project, {key: answer[key] for key in accepted})
        left = sorted(wanted_all - set(accepted), key=lambda key: (len(key), key))
        if left:
            print(f"not answered: {', '.join(left)}")
        return _after_all_done(project, args, args.next)
    report = project.save(k, answer, exchange.parse_notes(text))
    if not report["accepted"] and _REFUSAL_RE.search(text):
        project.set_refused(k, True)
        print(f"part {k + 1}: the AI seems to have refused to translate it. Try again in a new chat, "
              "with another model, or prepare again with a smaller --chunk-size.")
        return 3
    project.set_refused(k, False)
    print(f"part {k + 1}/{len(project.chunks)}: accepted {len(report['accepted'])} lines")
    _gender_report(project, {key: answer[key] for key in report["accepted"]})
    additions, characters = glossary.parse_additions(text), glossary.parse_cast_additions(text)
    if additions or characters:
        g = project.glossary()
        added = glossary.add_terms(g, additions)
        cast = glossary.add_cast(g, characters)
        if added or cast:
            project.save_glossary(g)
        if added:
            print("glossary: added " + "; ".join(f"{en}={uk}" for en, uk in added))
        if cast:
            print("glossary: new characters " + "; ".join(f"{r[0]} {r[2]} ({r[3]})" for r in cast))
    if ignored:
        print(f"ignored {len(ignored)} lines that are not `ID|text`")
    if report["unknown"]:
        print("unknown IDs (ignored): " + ", ".join(report["unknown"]))
    if report["empty"]:
        print("empty translations (not accepted): " + ", ".join(report["empty"]))
    if report["missing"]:
        print(f"missing {len(report['missing'])} lines: " + ", ".join(report["missing"][:30]))
        if args.next:
            print()
            sys.stdout.write(_request(project, k, True))
        else:
            print(f"Get them with: aisubs next {args.film}")
        return 2
    pending = project.pending_chunk()
    if pending is None:
        print("All parts translated.")
        return _after_all_done(project, args, args.next)
    elif args.next:
        print()
        # Every few parts the full request again: a long conversation may have been compacted
        sys.stdout.write(_request(project, pending, pending % FULL_EVERY != 0))
    else:
        print(f"Next: aisubs next {args.film}")
    return 0


def cmd_validate(args) -> int:
    project = Project(args.film).load()
    if project.pending_chunk() is not None:
        print(f"Not all parts are translated yet; checking what is done (aisubs status {args.film}).")
    problems, lines = _validate(project)
    print("\n".join(lines))
    if _fix_parts(project, problems):
        print(f"Next: aisubs fix {args.film}")
        return 2
    nxt = "review" if any(not p.fix for p in problems) else "assemble"
    print(f"Nothing to fix. Next: aisubs {nxt} {args.film}")
    return 0


def cmd_fix(args) -> int:
    project = Project(args.film).load()
    problems, _ = validate.run(project)
    ks = _fix_parts(project, problems) if args.part is None else [_chunk_arg(project, args.part)]
    ks = [k for k in ks if k is not None and any(p.k == k and p.fix for p in problems)]
    if not ks:
        print(f"Nothing to fix. Next: aisubs assemble {args.film}")
        return 0
    sys.stdout.write(validate.fix_request(project, ks, problems, brief=args.brief, instructions=_header(project)))
    return 0


def cmd_review(args) -> int:
    project = Project(args.film).load()
    path = Path(args.file) if args.file else project.dir / "review.txt"
    if args.apply:
        if not path.exists():
            raise ProjectError(f"{path} not found; first run: aisubs review {args.film}")
        changed, errors = review.apply(project, path.read_text(encoding="utf-8-sig"))
        for error in errors:
            print(f"warning: {error}")
        print(f"Saved {len(changed)} changed lines" + (": " + ", ".join(f"{k + 1}:{key}" for k, key in changed[:30]) if changed else ""))
        checker = validate.Checker(project.glossary())
        done, speakers = project.done(), project.speakers()
        for k, key in changed:
            sa = speakers.get(k, {}).get(key, "")
            for problem in validate.checks.gender_conflicts(done[k][key], sa, checker.cast) if sa else []:
                print(f"gender check: {k + 1}:{key}|{sa}|{done[k][key]} — {problem}")
        print(f"Next: aisubs assemble {args.film}")
        return 0
    if path.exists() and not args.force and review.apply(project, path.read_text(encoding="utf-8-sig"), dry_run=True)[0]:
        raise ProjectError(f"{path} has edits that are not saved yet: run aisubs review {args.film} --apply (or --force to discard them)")
    problems, _ = validate.run(project)
    text, count = review.render(project, problems, args.film)
    if not count:
        print(f"Nothing to review. Next: aisubs assemble {args.film}")
        return 0
    path.write_text(text, encoding="utf-8")
    print(f"Wrote {path}: {count} lines to look at. Edit it, then: aisubs review {args.film} --apply")
    return 0


def cmd_assemble(args) -> int:
    project = Project(args.film).load()
    done = project.done()
    texts: dict[int, list[str | None]] = {i: [None] * len(item.parts) for i, item in enumerate(project.items)}
    for k, chunk in enumerate(project.chunks):
        for key, i, p in project.chunk_keys(k):
            texts[i][p] = done.get(k, {}).get(key)
    missing = sum(1 for i, item in enumerate(project.items) if not item.skip and None in texts[i])
    if missing and not args.partial:
        raise ProjectError(f"{missing} subtitles are not translated yet; see: aisubs status {args.film} (or use --partial)")
    out = Path(args.output) if args.output else project.output_path()
    if not args.output and not args.force and not project.owns_output(out):
        raise ProjectError(f"{out} already exists and was not written by aisubs; use -o OTHER.srt, or --force to overwrite it")
    _write_output(project, out, partial=args.partial, bom=args.bom)
    print(f"Wrote {out}" + (f" ({missing} subtitles left in the original)" if missing else ""))
    return 0


def _write_output(project: Project, out: Path, *, partial: bool, bom: bool) -> None:
    done = project.done()
    texts: dict[int, list[str | None]] = {i: [None] * len(item.parts) for i, item in enumerate(project.items)}
    for k in range(len(project.chunks)):
        for key, i, p in project.chunk_keys(k):
            texts[i][p] = done.get(k, {}).get(key)
    cues = []
    for i, item in enumerate(project.items):
        if not item.skip and None in texts[i]:
            cues.append(srt.Cue(item.start, item.end, item.source))  # --partial: keep the original
        else:
            cues.append(srt.Cue(item.start, item.end, assemble.cue_text(item, texts[i])))
    srt.write(out, cues, bom=bom, newline=project.meta["newline"])
    if out == project.output_path():
        project.mark_output(out)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aisubs", description="AI translation of SRT subtitles into Ukrainian.")
    parser.add_argument("--version", action="version", version=f"aisubs {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("guide", help="print instructions for an AI agent that runs the whole translation")
    p.add_argument("film", nargs="?", help="subtitle file, e.g. film.srt")
    p.add_argument("--command", help="how the agent should run aisubs (default: as it was run now)")
    p.set_defaults(func=cmd_guide)

    p = sub.add_parser("prepare", help="read the SRT and split it into parts for translation")
    p.add_argument("film", help="subtitle file, e.g. film.srt")
    p.add_argument("--title", help='film title, e.g. "The One I Love (2014)"; guessed from the file name by default')
    p.add_argument("--keep-sdh", action="store_true", help="keep and translate SDH (sound descriptions, speaker labels)")
    p.add_argument("--chunk-size", type=int, default=200, help="max lines per part (default: 200)")
    p.add_argument("--scene-gap", type=int, default=3000, help="pause in ms that ends a scene (default: 3000)")
    p.add_argument("--encoding", help="source encoding if it is detected wrongly")
    p.add_argument("--force", action="store_true", help="start over, deleting existing translations")
    p.add_argument("--wikipedia", nargs="?", const="", metavar="PAGE", help="add the cast from Wikipedia to the glossary request (optionally the exact English article title)")
    p.add_argument("--glossary", action="store_true", help="then print the glossary request, saving the agent a step")
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("glossary", help="print the glossary request, or save the AI answer to it")
    p.add_argument("film")
    p.add_argument("answer", nargs="?", help="file with the AI answer, or - for stdin; without it the request is printed")
    p.add_argument("--wikipedia", nargs="?", const="", metavar="PAGE", help="first fetch the cast from Wikipedia (optionally the exact English article title)")
    p.add_argument("--next", action="store_true", help="after saving, print the first translation request (if there are no warnings)")
    p.set_defaults(func=cmd_glossary)

    p = sub.add_parser("status", help="show translation progress")
    p.add_argument("film")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("next", help="print the request for the next part to give to the AI")
    p.add_argument("film")
    p.add_argument("--part", type=int, help="part number (default: the first unfinished)")
    p.add_argument("--brief", action="store_true", help="omit the instructions (the AI already has them)")
    p.set_defaults(func=cmd_next)

    p = sub.add_parser("import", help="accept the AI answer for the current part")
    p.add_argument("film")
    p.add_argument("answer", nargs="?", default="-", help="file with the answer, or - for stdin (default)")
    p.add_argument("--part", type=int, help="part number (default: the first unfinished)")
    p.add_argument("--next", action="store_true", help="then print the next request (brief), saving the agent a step")
    p.add_argument("--fix", action="store_true", help="the answer is to a request from aisubs fix")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("validate", help="check the translation; writes film.aisubs/report.txt")
    p.add_argument("film")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("fix", help="print a request to translate again the lines that failed the checks")
    p.add_argument("film")
    p.add_argument("--part", type=int, help="part number (default: the first with problems)")
    p.add_argument("--brief", action="store_true", help="omit the instructions (the AI already has them)")
    p.set_defaults(func=cmd_fix)

    p = sub.add_parser("review", help="write the doubtful scenes to a file for a person to check; --apply saves the edits")
    p.add_argument("film")
    p.add_argument("--apply", action="store_true", help="save the edits made in the review file")
    p.add_argument("--file", help="review file (default: film.aisubs/review.txt)")
    p.add_argument("--force", action="store_true", help="write a new review file even if the old one has unsaved edits")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("assemble", help="write the translated .uk.srt")
    p.add_argument("film")
    p.add_argument("-o", "--output", help="output file (default: film.uk.srt)")
    p.add_argument("--partial", action="store_true", help="keep untranslated subtitles in the original")
    p.add_argument("--bom", action="store_true", help="write a UTF-8 BOM (for old players)")
    p.add_argument("--force", action="store_true", help="overwrite film.uk.srt even if aisubs did not write it")
    p.set_defaults(func=cmd_assemble)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ProjectError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
