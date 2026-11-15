"""Turn parsed SRT cues into translation items and chunks.

Everything here is deterministic. The model only ever sees `Part.text`:
no timings, no line breaks, no cue-level tags, no SDH.
"""

from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass, field

from . import srt

# Lines like these are ads or credits of the subtitle file, not of the film
_AD_RE = re.compile(
    r"opensubtitles|subscene|addic7ed|podnapisi|yts\.|yify|www\.|https?://|\.(com|org|net)\b"
    r"|subtitles? (by|ripped|downloaded|synced|corrected)|\b(sync|synced|corrected|ripped|encoded)\s+(and\s+\w+\s+)?by\b",
    re.IGNORECASE,
)
# Release tags of the subtitle file: "Film (1994) ….HI1", "720p.BluRay.x264"
_RELEASE_RE = re.compile(
    r"(?:^|[\s._-])(?:HI\d|SDH|CC|\d{3,4}p|Blu-?Ray|BRRip|BDRip|WEB-?DL|WEBRip|HDTV|DVDRip|x26[45]|HEVC)(?:$|[\s._-])"
)
_YEAR_RE = re.compile(r"\((?:19|20)\d\d\)")
EDGE = 3  # a title card of the subtitle file sits among the first or last cues
_POS_RE = re.compile(r"^\{\\an\d\}")
_OVERRIDE_RE = re.compile(r"\{\\[^}]*\}")
_TAG_RE = re.compile(r"</?(?:font|b|u|s)\b[^>]*>", re.IGNORECASE)
_ITALIC_RE = re.compile(r"(</?i>)", re.IGNORECASE)
_DASH_RE = re.compile(r"^[-–—]\s*")
# SDH: "SOPHIE:" / "MAN #2:" / "(ETHAN):" at the start of a line
_SPEAKER_RE = re.compile(r"^[(\[]?([A-Z][A-Z0-9 .'#&-]*[A-Z0-9])[)\]]?:\s*")
_SOUND_RE = re.compile(r"\[[^\]]*\]|\([^)]*\)")
_LETTER_RE = re.compile(r"[^\W\d_]")


@dataclass
class Part:
    text: str  # one line of plain text; <i>…</i> only around some of the words
    italic: bool = False  # the whole part is italic
    speaker: str = ""  # from an SDH label


@dataclass
class Item:
    """A cue after cleaning. `parts` has 2+ entries for "- A / - B" dialogue."""

    start: int
    end: int
    parts: list[Part]
    pos: str = ""  # e.g. "{\\an8}", restored on assembly
    skip: bool = False  # nothing to translate (no letters): copied as is
    source: str = field(default="", repr=False)  # original cue text


def _italic_segments(text: str) -> list[list[tuple[str, bool]]]:
    """Split cue text into lines of (text, italic) segments; tags may span lines."""
    lines: list[list[tuple[str, bool]]] = [[]]
    italic = False
    for token in _ITALIC_RE.split(text):
        if _ITALIC_RE.fullmatch(token):
            italic = not token.startswith("</")
            continue
        for k, chunk in enumerate(token.split("\n")):
            if k:
                lines.append([])
            if chunk:
                lines[-1].append((chunk, italic))
    return lines


def _render(segments: list[tuple[str, bool]]) -> tuple[str, bool]:
    """Join segments into (text, whole_italic), keeping <i> only for partial italics."""
    words = [(s, i) for s, i in segments if s.strip()]
    if words and all(i for _, i in words):
        return "".join(s for s, _ in segments), True
    out = []
    for s, i in segments:
        out.append(f"<i>{s}</i>" if i and s.strip() else s)
    return "".join(out).replace("</i><i>", ""), False


def _norm_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clean_cue(cue: srt.Cue, keep_sdh: bool = False) -> Item | None:
    """Return the cue as an Item, or None if it should be dropped entirely."""
    text = html.unescape(cue.text)
    pos = ""
    if m := _POS_RE.match(text):
        pos, text = m.group(), text[m.end():]
    text = _TAG_RE.sub("", _OVERRIDE_RE.sub("", text))
    if not text.strip():
        return None
    if _AD_RE.search(text):
        return None

    # A dash at a line start begins a new speaker; other lines continue the current one.
    # So "- Yeah." alone is one part (dash dropped), "Hi\n- Hey" is two.
    groups: list[list[tuple[str, bool]]] = []
    for line in _italic_segments(text):
        plain = "".join(s for s, _ in line).lstrip()
        if not plain:
            continue
        if _DASH_RE.match(plain):
            groups.append(_strip_prefix(line, _DASH_RE))
        elif groups:
            groups[-1] = groups[-1] + [(" ", False)] + line
        else:
            groups.append(line)

    parts = []
    for segments in groups:
        speaker = ""
        plain = "".join(s for s, _ in segments).lstrip()
        if m := _SPEAKER_RE.match(plain):
            speaker = m.group(1).title()
            if not keep_sdh:
                segments = _strip_prefix(segments, _SPEAKER_RE)
        if not keep_sdh:
            segments = [(_SOUND_RE.sub("", s), i) for s, i in segments]
        rendered, italic = _render(segments)
        rendered = _norm_space(rendered).replace("<i> ", " <i>").replace(" </i>", "</i> ")
        rendered = _norm_space(rendered)
        if rendered and rendered != "<i></i>":
            parts.append(Part(rendered, italic, speaker))
    if not parts:
        return None
    skip = not any(_LETTER_RE.search(p.text) for p in parts)
    return Item(cue.start, cue.end, parts, pos, skip, cue.text)


def _strip_prefix(segments: list[tuple[str, bool]], pattern: re.Pattern) -> list[tuple[str, bool]]:
    """Remove a regex match from the start of the joined segment text."""
    out = list(segments)
    while out and not out[0][0].strip():
        out.pop(0)
    if not out:
        return out
    first, italic = out[0]
    first = first.lstrip()
    if m := pattern.match(first):
        first = first[m.end():]
    out[0] = (first, italic)
    return out


def _is_banner(text: str) -> bool:
    """A credit of the subtitle file itself, like "Léon- The Professional (1994) Luc Besson….HI1"."""
    text = _TAG_RE.sub("", text)
    return bool(_RELEASE_RE.search(text) or (_YEAR_RE.search(text) and "\n" not in text.strip() and not text.rstrip().endswith(("?", "!"))))


def make_items(cues: list[srt.Cue], keep_sdh: bool = False) -> tuple[list[Item], int]:
    """Return (items, number of dropped cues)."""
    items = [
        None if (n < EDGE or n >= len(cues) - EDGE) and _is_banner(c.text) else clean_cue(c, keep_sdh)
        for n, c in enumerate(cues)
    ]
    kept = [i for i in items if i is not None]
    return kept, len(items) - len(kept)


def make_scenes(items: list[Item], scene_gap: int = 3000) -> list[tuple[int, int]]:
    """Split items where the pause between them is longer than `scene_gap` ms."""
    if not items:
        return []
    scenes = []
    begin = 0
    for k in range(1, len(items)):
        if items[k].start - items[k - 1].end > scene_gap:
            scenes.append((begin, k))
            begin = k
    scenes.append((begin, len(items)))
    return scenes


def make_chunks(items: list[Item], max_size: int = 200, scene_gap: int = 3000) -> list[tuple[int, int]]:
    """Group items into chunks of whole scenes. Return [(first, last_exclusive)].

    A scene longer than `max_size` is split at its longest pause.
    """
    if not items:
        return []
    scenes = make_scenes(items, scene_gap)

    def split(a: int, b: int) -> list[tuple[int, int]]:
        if b - a <= max_size:
            return [(a, b)]
        k = max(range(a + 1, b), key=lambda k: items[k].start - items[k - 1].end)
        if k - a > max_size or b - k > max_size or min(k - a, b - k) < max_size // 4:
            k = a + max_size  # no usable pause: hard cut
        return split(a, k) + split(k, b)

    scenes = [s for a, b in scenes for s in split(a, b)]

    def size(a: int, b: int) -> int:
        return sum(len(i.parts) for i in items[a:b] if not i.skip)

    chunks = []
    a, b = scenes[0]
    for sa, sb in scenes[1:]:
        if size(a, sb) > max_size:
            chunks.append((a, b))
            a = sa
        b = sb
    chunks.append((a, b))
    return chunks


def guess_title(filename: str) -> str:
    """'The.One.I.Love.2014.LIMITED.720p...' -> 'The One I Love (2014)'."""
    stem = re.sub(r"\.srt$", "", filename, flags=re.IGNORECASE)
    words = re.split(r"[._ ]+", stem)
    # A language tag at the end: "Film.S01E01.en.srt"
    while len(words) > 1 and words[-1].lower() in ("en", "eng", "english"):
        words.pop()
    # The last year-like word, so "Blade.Runner.2049.2017" gives 2017
    for k in range(len(words) - 1, 0, -1):
        if re.fullmatch(r"(19|20)\d\d", words[k]):
            return f"{' '.join(words[:k])} ({words[k]})"
    return " ".join(w for w in words if w)


def item_to_dict(item: Item) -> dict:
    return asdict(item)


def item_from_dict(data: dict) -> Item:
    return Item(**{**data, "parts": [Part(**p) for p in data["parts"]]})
