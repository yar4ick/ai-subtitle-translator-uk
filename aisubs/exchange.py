"""The text exchanged with the model: requests built by `next`, answers read by `import`."""

from __future__ import annotations

import re
from pathlib import Path

from . import limits
from .prepare import Item

PROMPT_VERSION = 4
PROMPTS = Path(__file__).parent / "prompts"
CONTEXT_BEFORE = 5
CONTEXT_AFTER = 3
TIGHT_RATIO = 0.85  # mark a line with its budget when the English uses more than this share of it

# "12|text", "12a|text", "12?|text", "| 12 | text |", "**12**|text"
_ANSWER_RE = re.compile(r"^\s*(\|)?\s*\**(\d+[a-z]?)\**\s*(\?)?\s*\|\s?(.*?)\s*$")
_TABLE_RULE_RE = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")
_ECHOED_BUDGET_RE = re.compile(r"^≤\d+\|\s?")
# Who speaks to whom: "Д>Гл|text", "?>М|text"; models also write a bare "-|text" for narration
_SPEAKERS_RE = re.compile(r"^(?:([^\s|>]{1,4})\s*>\s*([^\s|>]{1,4})|([-*?]))\s*\|\s?")


def chunk_keys(items: list[Item], chunk: tuple[int, int]) -> list[tuple[str, int, int]]:
    """Return [(key, item index, part index)] for the translatable parts of a chunk.

    Keys are numbered from 1 within the chunk without gaps; dialogue parts get a, b, c….
    """
    keys = []
    n = 0
    for i in range(*chunk):
        if items[i].skip:
            continue
        n += 1
        parts = items[i].parts
        for p in range(len(parts)):
            keys.append((f"{n}{chr(ord('a') + p)}" if len(parts) > 1 else str(n), i, p))
    return keys


def instructions(title: str) -> str:
    return (PROMPTS / "translate.md").read_text(encoding="utf-8").replace("{title}", title).strip()


def build_request(
    items: list[Item],
    chunks: list[tuple[int, int]],
    k: int,
    done: dict[int, dict[str, str]],
    title: str,
    *,
    brief: bool = False,
    glossary_block: str = "",
) -> str:
    """Request text for chunk `k` (0-based), asking only for keys not in done[k].

    `brief` is for an agent that keeps the conversation: no instructions and
    no previous lines, which it has already seen. The glossary block goes
    with the instructions.
    """
    out = [] if brief else [instructions(title), ""]
    if glossary_block and not brief:
        out += ["GLOSSARY", glossary_block, ""]

    prev = done.get(k - 1, {})
    if k > 0 and prev and not brief:
        pairs = [(items[i].parts[p].text, prev[key]) for key, i, p in chunk_keys(items, chunks[k - 1]) if key in prev]
        if pairs:
            out.append("CONTEXT (previous lines, already translated):")
            out += [f"{src} => {uk}" for src, uk in pairs[-CONTEXT_BEFORE:]]
            out.append("")

    have = done.get(k, {})
    out.append(f"TRANSLATE (part {k + 1} of {len(chunks)}):")
    for key, i, p in chunk_keys(items, chunks[k]):
        if key in have:
            continue
        text = items[i].parts[p].text
        budget = limits.budgets(items[i])[p]
        out.append(f"{key}|≤{budget}|{text}" if limits.is_tight(text, budget, TIGHT_RATIO) else f"{key}|{text}")

    if k + 1 < len(chunks):
        following = [items[i].parts[p].text for _, i, p in chunk_keys(items, chunks[k + 1])][:CONTEXT_AFTER]
        if following:
            out += ["", "CONTEXT (following lines, do not translate):"]
            out += following
    return "\n".join(out) + "\n"


def parse_answer(text: str) -> tuple[dict[str, tuple[str, bool, str]], list[str]]:
    """Read `key|S>A|translation` lines (S>A optional), tolerating code fences, tables and chatter.

    Return ({key: (text, flagged, "S>A" or "")}, ignored non-empty lines).
    A line is flagged when S or A is `?` (or, as in prompt v1, `key?|`).
    """
    result: dict[str, tuple[str, bool, str]] = {}
    ignored = []
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("```") or _TABLE_RULE_RE.match(line):
            continue
        m = _ANSWER_RE.match(line)
        if not m:
            if not line.strip().startswith("+|"):  # glossary additions are read separately
                ignored.append(line.strip())
            continue
        table, key, flag, body = m.groups()
        if table and body.endswith("|"):
            body = body[:-1].rstrip()
        body = _ECHOED_BUDGET_RE.sub("", body)
        speakers = ""
        if m := _SPEAKERS_RE.match(body):
            speakers = m.group(3) or f"{m.group(1)}>{m.group(2)}"
            body = body[m.end():]
            flag = flag or "?" in speakers
        result[key] = (body, bool(flag), speakers)
    return result, ignored
