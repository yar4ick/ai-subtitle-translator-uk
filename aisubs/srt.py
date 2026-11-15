"""Reading and writing SRT subtitle files.

The parser is lenient: it accepts broken numbering, missing blank lines,
`.` instead of `,` in timestamps and several encodings. Problems that do not
stop parsing are reported in `SrtFile.warnings`. Text is kept as is; cleaning
tags, SDH and other junk inside cues is the job of later stages.
"""

from __future__ import annotations

import codecs
import re
from dataclasses import dataclass, field
from pathlib import Path

_TIME = r"(\d{1,2}):(\d{1,2}):(\d{1,2})[,.:](\d{1,3})"
_TIMING_RE = re.compile(rf"^\s*{_TIME}\s*-+>\s*{_TIME}(.*)$")


@dataclass
class Cue:
    start: int  # milliseconds
    end: int  # milliseconds
    text: str  # lines joined with "\n"
    extra: str = ""  # anything after the end time, e.g. "  X1:100 X2:200 ..."


@dataclass
class SrtFile:
    cues: list[Cue]
    encoding: str
    bom: bool
    newline: str
    warnings: list[str] = field(default_factory=list)


def decode(data: bytes, encoding: str | None = None) -> tuple[str, str, bool]:
    """Return (text, encoding, has_bom).

    Without an explicit encoding: UTF-8 BOM, UTF-16 BOM, strict UTF-8, cp1252.
    """
    if encoding:
        bom = data.startswith(codecs.BOM_UTF8) and encoding.lower().replace("_", "-") in ("utf-8", "utf8", "utf-8-sig")
        if bom:
            return data[len(codecs.BOM_UTF8):].decode("utf-8"), "utf-8", True
        return data.decode(encoding), encoding, False
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8):].decode("utf-8"), "utf-8", True
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16"), "utf-16", True
    try:
        return data.decode("utf-8"), "utf-8", False
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace"), "cp1252", False


def parse_time(h: str, m: str, s: str, ms: str) -> int:
    # ",5" means half a second, so the fraction is padded on the right
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms.ljust(3, "0"))


def format_time(ms: int) -> str:
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_text(text: str) -> tuple[list[Cue], list[str]]:
    """Parse SRT text with "\\n" line endings. Return (cues, warnings)."""
    lines = text.split("\n")
    timings = [i for i, line in enumerate(lines) if _TIMING_RE.match(line)]
    warnings: list[str] = []
    if not timings:
        return [], ["no timing lines found"]

    def block_start(t: int, prev: int) -> int:
        # A digits-only line right before the timing line is the cue number
        if t - 1 > prev and lines[t - 1].strip().isdigit():
            return t - 1
        return t

    starts = []
    prev = -1
    for t in timings:
        starts.append(block_start(t, prev))
        prev = t

    if any(line.strip() for line in lines[: starts[0]]):
        warnings.append("ignored text before the first cue")

    cues = []
    renumbered = False
    for n, t in enumerate(timings):
        if starts[n] == t:
            warnings.append(f"cue {n + 1}: missing number")
        elif int(lines[starts[n]]) != n + 1:
            renumbered = True
        g = _TIMING_RE.match(lines[t]).groups()
        start, end = parse_time(*g[0:4]), parse_time(*g[4:8])
        body_end = starts[n + 1] if n + 1 < len(timings) else len(lines)
        body = [line.rstrip() for line in lines[t + 1 : body_end]]
        cues.append(Cue(start, end, "\n".join(line for line in body if line), g[8].rstrip()))

    if renumbered:
        warnings.append("cue numbers are not sequential; output is renumbered")
    for n, cue in enumerate(cues):
        if cue.end < cue.start:
            warnings.append(f"cue {n + 1}: ends before it starts")
        if n and cue.start < cues[n - 1].start:
            warnings.append(f"cue {n + 1}: starts before the previous cue")
        elif n and cue.start < cues[n - 1].end:
            warnings.append(f"cue {n + 1}: overlaps the previous cue")
    return cues, warnings


def parse(data: bytes, encoding: str | None = None) -> SrtFile:
    text, encoding, bom = decode(data, encoding)
    newline = "\r\n" if "\r\n" in text else "\n"
    cues, warnings = parse_text(text.replace("\r\n", "\n").replace("\r", "\n"))
    return SrtFile(cues, encoding, bom, newline, warnings)


def read(path: str | Path, encoding: str | None = None) -> SrtFile:
    return parse(Path(path).read_bytes(), encoding)


def dumps(cues: list[Cue], newline: str = "\n") -> str:
    blocks = [
        f"{n}\n{format_time(cue.start)} --> {format_time(cue.end)}{cue.extra}\n{cue.text}\n"
        for n, cue in enumerate(cues, 1)
    ]
    return "\n".join(blocks).replace("\n", newline)


def write(path: str | Path, cues: list[Cue], *, bom: bool = False, newline: str = "\n") -> None:
    """Write cues as UTF-8, numbered from 1."""
    data = dumps(cues, newline).encode("utf-8")
    Path(path).write_bytes(codecs.BOM_UTF8 + data if bom else data)
