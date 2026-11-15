"""Command line: aisubs prepare | glossary | status | next | import | assemble."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, assemble, checks, exchange, glossary, prepare, srt
from .project import Project, ProjectError


def cmd_prepare(args) -> int:
    project = Project(args.film)
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
    print(f"Next: aisubs next {args.film}")
    return 0


def _request(project: Project, k: int, brief: bool) -> str:
    g = project.glossary()
    scenes = prepare.make_scenes(project.items, project.meta["scene_gap"])
    return exchange.build_request(
        project.items, project.chunks, k, project.done(), project.meta["title"],
        brief=brief, glossary_block="" if g.is_empty() else glossary.render(g),
        scene_starts=frozenset(a for a, _ in scenes[1:]), speaker_codes=glossary.speaker_codes(g),
    )


def cmd_glossary(args) -> int:
    project = Project(args.film).load()
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
    print(f"Check or edit {project.glossary_path}, then: aisubs next {args.film}")
    return 0


def cmd_status(args) -> int:
    project = Project(args.film).load()
    done, flags = project.done(), project.flags()
    total = len(project.chunks)
    for k in range(total):
        keys = project.keys(k)
        have = len([key for key in keys if key in done.get(k, {})])
        mark = "done" if have == len(keys) else ("partial" if have else "todo")
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


def cmd_import(args) -> int:
    project = Project(args.film).load()
    k = _chunk_arg(project, args.part)
    if k is None:
        print("All parts are already translated.")
        return 0
    if args.answer == "-":
        text = sys.stdin.read()
    else:
        text = Path(args.answer).read_text(encoding="utf-8-sig")
    answer, ignored = exchange.parse_answer(text)
    report = project.save(k, answer, exchange.parse_notes(text))
    print(f"part {k + 1}/{len(project.chunks)}: accepted {len(report['accepted'])} lines")
    cast = checks.genders(project.glossary())
    conflicts = [
        (key, problem)
        for key in report["accepted"]
        if answer[key][2]
        for problem in checks.gender_conflicts(answer[key][0], answer[key][2], cast)
    ]
    for key, problem in conflicts:
        print(f"gender check: {key}|{answer[key][2]}|{answer[key][0]} — {problem}")
    if additions := glossary.parse_additions(text):
        g = project.glossary()
        if added := glossary.add_terms(g, additions):
            project.save_glossary(g)
            print("glossary: added " + "; ".join(f"{en}={uk}" for en, uk in added))
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
        print(f"All parts translated. Next: aisubs assemble {args.film}")
    elif args.next:
        print()
        sys.stdout.write(_request(project, pending, True))
    else:
        print(f"Next: aisubs next {args.film}")
    return 0


def cmd_assemble(args) -> int:
    project = Project(args.film).load()
    done = project.done()
    texts: dict[int, list[str | None]] = {i: [None] * len(item.parts) for i, item in enumerate(project.items)}
    for k, chunk in enumerate(project.chunks):
        for key, i, p in exchange.chunk_keys(project.items, chunk):
            texts[i][p] = done.get(k, {}).get(key)
    missing = sum(1 for i, item in enumerate(project.items) if not item.skip and None in texts[i])
    if missing and not args.partial:
        raise ProjectError(f"{missing} subtitles are not translated yet; see: aisubs status {args.film} (or use --partial)")
    cues = []
    for i, item in enumerate(project.items):
        if not item.skip and None in texts[i]:
            cues.append(srt.Cue(item.start, item.end, item.source))  # --partial: keep the original
        else:
            cues.append(srt.Cue(item.start, item.end, assemble.cue_text(item, texts[i])))
    out = Path(args.output) if args.output else project.output_path()
    srt.write(out, cues, bom=args.bom, newline=project.meta["newline"])
    print(f"Wrote {out}" + (f" ({missing} subtitles left in the original)" if missing else ""))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aisubs", description="AI translation of SRT subtitles into Ukrainian.")
    parser.add_argument("--version", action="version", version=f"aisubs {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prepare", help="read the SRT and split it into parts for translation")
    p.add_argument("film", help="subtitle file, e.g. film.srt")
    p.add_argument("--title", help='film title, e.g. "The One I Love (2014)"; guessed from the file name by default')
    p.add_argument("--keep-sdh", action="store_true", help="keep and translate SDH (sound descriptions, speaker labels)")
    p.add_argument("--chunk-size", type=int, default=200, help="max lines per part (default: 200)")
    p.add_argument("--scene-gap", type=int, default=3000, help="pause in ms that ends a scene (default: 3000)")
    p.add_argument("--encoding", help="source encoding if it is detected wrongly")
    p.add_argument("--force", action="store_true", help="start over, deleting existing translations")
    p.set_defaults(func=cmd_prepare)

    p = sub.add_parser("glossary", help="print the glossary request, or save the AI answer to it")
    p.add_argument("film")
    p.add_argument("answer", nargs="?", help="file with the AI answer, or - for stdin; without it the request is printed")
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
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("assemble", help="write the translated .uk.srt")
    p.add_argument("film")
    p.add_argument("-o", "--output", help="output file (default: film.uk.srt)")
    p.add_argument("--partial", action="store_true", help="keep untranslated subtitles in the original")
    p.add_argument("--bom", action="store_true", help="write a UTF-8 BOM (for old players)")
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
