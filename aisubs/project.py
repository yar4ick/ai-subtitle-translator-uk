"""The working folder next to the film: `film.aisubs/`."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import candidates, exchange, glossary, prepare, srt

FORMAT_VERSION = 1


class ProjectError(Exception):
    pass


def _write_json(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Project:
    def __init__(self, film: str | Path):
        self.film = Path(film)
        self.dir = self.film.with_name(self.film.stem + ".aisubs")
        self.meta: dict = {}
        self.items: list[prepare.Item] = []
        self.chunks: list[tuple[int, int]] = []

    @property
    def done_dir(self) -> Path:
        return self.dir / "done"

    @property
    def glossary_path(self) -> Path:
        return self.dir / "glossary.txt"

    def glossary(self) -> glossary.Glossary:
        if not self.glossary_path.exists():
            return glossary.Glossary()
        return glossary.parse(self.glossary_path.read_text(encoding="utf-8"))[0]

    def save_glossary(self, g: glossary.Glossary) -> None:
        tmp = self.glossary_path.with_suffix(".tmp")
        tmp.write_text(glossary.dumps(g), encoding="utf-8")
        tmp.replace(self.glossary_path)

    def glossary_request(self) -> str:
        data = json.loads((self.dir / "candidates.json").read_text(encoding="utf-8"))
        return glossary.build_request(self.meta["title"], data["candidates"], data["sample"])

    def output_path(self) -> Path:
        stem = re.sub(r"[._-](en|eng|english)$", "", self.film.stem, flags=re.IGNORECASE)
        return self.film.with_name(stem + ".uk.srt")

    # --- prepare ---

    def create(self, *, title: str | None, keep_sdh: bool, chunk_size: int, scene_gap: int, encoding: str | None, force: bool) -> srt.SrtFile:
        if self.dir.exists() and any(self.done_dir.glob("*.json")) and not force:
            raise ProjectError(f"{self.dir} already has translations; use --force to start over (they will be deleted)")
        parsed = srt.read(self.film, encoding)
        if not parsed.cues:
            raise ProjectError("no subtitles found in " + str(self.film))
        items, dropped = prepare.make_items(parsed.cues, keep_sdh)
        chunks = prepare.make_chunks(items, chunk_size, scene_gap)
        self.dir.mkdir(exist_ok=True)
        self.done_dir.mkdir(exist_ok=True)
        for old in self.done_dir.glob("*.json"):
            old.unlink()
        if self.glossary_path.exists() and force:
            self.glossary_path.unlink()
        self.meta = {
            "format": FORMAT_VERSION,
            "prompt_version": exchange.PROMPT_VERSION,
            "title": title or prepare.guess_title(self.film.name),
            "source": self.film.name,
            "sha256": _sha256(self.film),
            "encoding": parsed.encoding,
            "newline": parsed.newline,
            "keep_sdh": keep_sdh,
            "chunk_size": chunk_size,
            "scene_gap": scene_gap,
            "cues": len(parsed.cues),
            "dropped": dropped,
            "chunks": chunks,
        }
        self.items, self.chunks = items, chunks
        _write_json(self.dir / "cues.json", [prepare.item_to_dict(i) for i in items])
        _write_json(self.dir / "candidates.json", {
            "candidates": [candidates.to_dict(c) for c in candidates.find(items)],
            "sample": candidates.sample(items, scene_gap),
        })
        _write_json(self.dir / "meta.json", self.meta)
        return parsed

    # --- load ---

    def load(self) -> "Project":
        meta_path = self.dir / "meta.json"
        if not meta_path.exists():
            raise ProjectError(f"not prepared yet; run: aisubs prepare {self.film}")
        self.meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if self.meta.get("format") != FORMAT_VERSION:
            raise ProjectError(f"{self.dir} was made by another version of aisubs; run prepare --force")
        if self.film.exists() and _sha256(self.film) != self.meta["sha256"]:
            raise ProjectError(f"{self.film} changed since prepare; run: aisubs prepare --force {self.film}")
        data = json.loads((self.dir / "cues.json").read_text(encoding="utf-8"))
        self.items = [prepare.item_from_dict(d) for d in data]
        self.chunks = [tuple(c) for c in self.meta["chunks"]]
        return self

    # --- translations ---

    def _done_path(self, k: int) -> Path:
        return self.done_dir / f"{k + 1:03d}.json"

    def done(self) -> dict[int, dict[str, str]]:
        out = {}
        for k in range(len(self.chunks)):
            path = self._done_path(k)
            if path.exists():
                out[k] = json.loads(path.read_text(encoding="utf-8"))["items"]
        return out

    def flags(self) -> dict[int, list[str]]:
        out = {}
        for k in range(len(self.chunks)):
            path = self._done_path(k)
            if path.exists():
                out[k] = json.loads(path.read_text(encoding="utf-8"))["flags"]
        return out

    def speakers(self) -> dict[int, dict[str, str]]:
        out = {}
        for k in range(len(self.chunks)):
            path = self._done_path(k)
            if path.exists():
                out[k] = json.loads(path.read_text(encoding="utf-8")).get("speakers", {})
        return out

    def set_refused(self, k: int, refused: bool) -> None:
        marks = set(self.meta.get("refused", []))
        new = marks | {k} if refused else marks - {k}
        if new != marks:
            self.meta["refused"] = sorted(new)
            _write_json(self.dir / "meta.json", self.meta)

    def retries(self) -> dict[int, dict[str, int]]:
        """Part -> {key: how many times the line was sent back by `fix`}."""
        out = {}
        for k in range(len(self.chunks)):
            path = self._done_path(k)
            if path.exists():
                out[k] = json.loads(path.read_text(encoding="utf-8")).get("retries", {})
        return out

    def keys(self, k: int) -> list[str]:
        return [key for key, _, _ in exchange.chunk_keys(self.items, self.chunks[k])]

    def is_complete(self, k: int, done: dict[int, dict[str, str]] | None = None) -> bool:
        have = (done if done is not None else self.done()).get(k, {})
        return all(key in have for key in self.keys(k))

    def pending_chunk(self) -> int | None:
        done = self.done()
        return next((k for k in range(len(self.chunks)) if not self.is_complete(k, done)), None)

    def save(self, k: int, answer: dict[str, tuple[str, bool, str]], notes: list | None = None, *, retry: bool = False) -> dict:
        """Merge accepted lines into chunk k (counting a retry for each with `retry`). Return a report."""
        expected = self.keys(k)
        path = self._done_path(k)
        record = {"items": {}, "flags": [], "speakers": {}}
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
            record.setdefault("speakers", {})
        accepted, empty = [], []
        for key, (text, flagged, speakers) in answer.items():
            if key not in expected:
                continue
            if not text.strip():
                empty.append(key)
                continue
            record["items"][key] = text.strip()
            if speakers:
                record["speakers"][key] = speakers
            if flagged and key not in record["flags"]:
                record["flags"].append(key)
            elif not flagged and key in record["flags"]:
                record["flags"].remove(key)
            if retry:
                record.setdefault("retries", {})
                record["retries"][key] = record["retries"].get(key, 0) + 1
            accepted.append(key)
        order = {key: n for n, key in enumerate(expected)}
        record["items"] = dict(sorted(record["items"].items(), key=lambda kv: order[kv[0]]))
        record["flags"].sort(key=order.get)
        if notes:
            record.setdefault("notes", [])
            record["notes"] += [list(n) for n in notes if list(n) not in record["notes"]]
        record["prompt_version"] = exchange.PROMPT_VERSION
        record["sha256"] = self.meta["sha256"]
        if accepted:
            _write_json(path, record)
        return {
            "accepted": accepted,
            "unknown": [key for key in answer if key not in order],
            "empty": empty,
            "missing": [key for key in expected if key not in record["items"]],
        }
