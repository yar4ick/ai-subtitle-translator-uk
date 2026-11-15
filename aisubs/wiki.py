"""Optional: the cast of the film from Wikipedia, for the glossary request.

`aisubs prepare --wikipedia` (or `aisubs glossary --wikipedia`) finds the
English article of the film through the MediaWiki API, takes its cast or
characters section and, through the interlanguage link, the same section of
the Ukrainian article, which gives established Ukrainian name forms. Only
stdlib `urllib`, no key. Parsing wiki markup is fragile, so everything here
is best effort: on any failure the glossary is built without it.

Characters whose names never occur in the subtitles are marked, and when
almost none occur, the article is probably about another film.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

from .glossary import name_words

USER_AGENT = "aisubs (AI subtitle translator; stdlib urllib)"
TIMEOUT = 15
MAX_ENTRIES = 40
MAX_LEN = 140

_HEADING_RE = re.compile(r"^(=+)\s*(.+?)\s*=+\s*$", re.M)
_CAST_EN = re.compile(r"^(cast|cast and characters|main cast|voice cast|starring|characters|cast and roles)$", re.I)
_CAST_UK = re.compile(r"^(у ролях|в ролях|ролі|акторський склад|персонажі|актори|ролі озвучували)$", re.I)
_REF_RE = re.compile(r"<ref[^>/]*/>|<ref[^>]*>.*?</ref>", re.S)
_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_LINK_RE = re.compile(r"\[\[(?:[^\[\]|]*\|)?([^\[\]|]*)\]\]")
_EXT_LINK_RE = re.compile(r"\[https?://\S+\s*([^\]]*)\]")
_TEMPLATE_RE = re.compile(r"\{\{([^{}]*)\}\}")
# Templates whose arguments are the list itself
_CONTAINERS = {"cast listing", "div col", "columns-list", "col-begin", "gallery", "plainlist", "ubl", "unbulleted list", "flatlist", "div col end"}
# Templates that stand for their first argument
_FIRST_ARG = {"nihongo", "lang", "nowrap", "small", "nobold", "abbr", "nihongo2", "ill", "illm", "anchor"}
_TV_RE = re.compile(r"\bS\d{1,2}\s*E\d{1,3}\b.*$", re.I)
_YEAR_RE = re.compile(r"\((\d{4})\)")


class WikiError(Exception):
    pass


def _api(host: str, **params) -> dict:
    params.update(format="json", formatversion=2)
    url = f"https://{host}/w/api.php?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response)
    except (OSError, ValueError) as e:
        raise WikiError(f"{host}: {e}") from e


def _template(body: str) -> str:
    name, _, rest = body.partition("|")
    name = name.strip().lower()
    args = [a.strip() for a in rest.split("|")] if rest else []
    if name in _CONTAINERS:
        keep = [a for a in args if a and not re.match(r"^[\w\s-]+=", a) and not re.match(r"^(file|image|файл|зображення):", a, re.I)]
        return "\n" + "\n".join(keep) + "\n"
    if name == "sortname" and len(args) >= 2:
        return f"{args[0]} {args[1]}"
    if name in _FIRST_ARG and args:
        return args[0]
    return ""


def clean(wikitext: str) -> str:
    """Plain text of wiki markup, keeping line structure."""
    text = _COMMENT_RE.sub("", _REF_RE.sub("", wikitext))
    for pattern, repl in ((_LINK_RE, r"\1"), (_TEMPLATE_RE, lambda m: _template(m.group(1)))):
        while True:
            new = pattern.sub(repl, text)
            if new == text:
                break
            text = new
    text = _EXT_LINK_RE.sub(r"\1", text)
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.replace("&nbsp;", " ").replace(" ", " ")


def section(wikitext: str, pattern: re.Pattern) -> str:
    """The first section whose heading matches, with its subsections."""
    headings = list(_HEADING_RE.finditer(wikitext))
    for n, h in enumerate(headings):
        if pattern.match(h.group(2).strip()):
            level = len(h.group(1))
            end = next((x.start() for x in headings[n + 1:] if len(x.group(1)) <= level), len(wikitext))
            return wikitext[h.end():end]
    return ""


def _shorten(entry: str) -> str:
    entry = re.sub(r"\s*\((?:seasons?|episodes?|recurring|guest|сезони?|епізоди?)\b[^)]*\)?", "", entry, flags=re.I)
    entry = re.sub(r"\s+", " ", entry).strip(" ,;")
    m = re.search(r"\.(\s|$)", entry[30:])
    if m:
        entry = entry[: 30 + m.start() + 1]
    return entry if len(entry) <= MAX_LEN else entry[: MAX_LEN - 1].rstrip() + "…"


def entries(wikitext: str, pattern: re.Pattern) -> list[str]:
    """Cast lines like "Jean Reno as Léon" / "Жан Рено — Леон" / "David Martinez: a street kid…"."""
    lines = clean(section(wikitext, pattern)).splitlines()
    out: list[str] = []
    term = ""
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith(("=", "{|", "|}", "|-")):
            continue
        if line.startswith(";"):  # definition list: ";Name" then ":description"
            term = line.lstrip("; ").split(":")[0].strip()
            if term:
                out.append(term)
            continue
        body = line.lstrip("*#: ").strip()
        if raw.lstrip().startswith(":") and term and body:
            if len(out[-1]) == len(term) and not body.lower().startswith(("voiced by", "озвучу")):
                out[-1] = f"{term}: {body}"
            continue
        if re.search(r"\s(as|—|–)\s|\s-\s", body):
            out.append(body)
            term = ""
    return [_shorten(e) for e in out if e][:MAX_ENTRIES]


def character(entry: str) -> str:
    """The character's name in a cast entry: "Jean Reno as Léon, a hitman" -> "Léon"."""
    for sep in (" as ", " — ", " – ", " - "):
        if sep in entry:
            entry = entry.split(sep, 1)[1]
            break
    else:
        entry = entry.split(":", 1)[0]
    return re.split(r"[,(;:]", entry, maxsplit=1)[0].strip()


def find_article(title: str) -> str:
    """English article title for "Film (1994)" or "Series S01E01 (2016)"."""
    is_tv = bool(_TV_RE.search(title))
    year = (_YEAR_RE.search(title) or [None, ""])[1]
    name = _YEAR_RE.sub("", _TV_RE.sub("", title)).strip(" -.")
    query = f"{name} {year} {'TV series' if is_tv else 'film'}".strip()
    hits = _api("en.wikipedia.org", action="query", list="search", srsearch=query, srlimit=5)["query"]["search"]
    words = {w for w in re.findall(r"\w+", name.lower()) if len(w) > 2}
    for hit in hits:
        if words and words <= set(re.findall(r"\w+", hit["title"].lower())) | {"the"}:
            return hit["title"]
    raise WikiError(f"no Wikipedia article found for {name!r}")


def fetch(title: str, page: str | None = None) -> tuple[str, list[str], str, list[str]]:
    """(English title, English entries, Ukrainian title, Ukrainian entries)."""
    page = page or find_article(title)
    data = _api("en.wikipedia.org", action="parse", page=page, prop="wikitext|langlinks", redirects=1)
    if "error" in data:
        raise WikiError(data["error"].get("info", "parse error"))
    parsed = data["parse"]
    en = entries(parsed["wikitext"], _CAST_EN)
    uk_title, uk = "", []
    link = next((l for l in parsed.get("langlinks", []) if l.get("lang") == "uk"), None)
    if link:
        uk_title = link["title"]
        try:
            uk_data = _api("uk.wikipedia.org", action="parse", page=uk_title, prop="wikitext", redirects=1)
            uk = entries(uk_data["parse"]["wikitext"], _CAST_UK)
        except (WikiError, KeyError):
            uk = []
    return parsed["title"], en, uk_title, uk


def check(en: list[str], names: set[str]) -> tuple[list[str], float]:
    """Mark entries whose character never occurs in the subtitles; return (entries, share found)."""
    out, found = [], 0
    for entry in en:
        words = name_words(character(entry))
        hit = bool(words & names)
        found += hit
        out.append(entry if hit else entry + " [not in the subtitles]")
    return out, (found / len(en) if en else 0.0)


def render(en_title: str, en: list[str], uk_title: str, uk: list[str]) -> str:
    out = [f"WIKIPEDIA (cast of «{en_title}»; may be incomplete):"] + en
    if uk:
        out += ["", f"UKRAINIAN WIKIPEDIA («{uk_title}»; established Ukrainian names):"] + uk
    return "\n".join(out) + "\n"
