"""Claude importer.

Three real inputs, detected from the path:

1. **claude.ai data export** (Settings → Privacy → Export data), as the ``.zip`` or the
   unpacked folder. It contains ``conversations.json``, ``users.json`` and ``projects.json``
   and **no memory file**. This importer reads ``projects.json``: each project becomes an
   ``areas/<slug>.md`` with its ``description`` and the lines of its ``prompt_template``
   (project instructions) as ``[stated]`` facts. Conversations are not mined; the spec
   would rather import nothing than guess.

2. **Pasted memory text**: Settings → Memory → "View and edit your memory", or ask Claude
   to "write out your memories of me verbatim". Save it to a ``.txt``/``.md`` file and pass
   that path, or pass it alongside an export with ``--memory-text``. Prose is split into
   sentences; bullets are one fact each. Everything is ``[stated]`` except hedged
   sentences, which are ``[inferred]``.

3. **A Claude Code memory directory** (``~/.claude/projects/<project>/memory/``, the
   folder holding ``MEMORY.md`` and one ``.md`` per memory, each with ``name``,
   ``description`` and ``metadata.type`` frontmatter). ``type`` maps to a kind:
   ``user`` → profile, ``feedback`` → preferences, ``project`` → area,
   ``reference`` → topic. Bullets and sentences in the body become ``[stated]`` facts.
   A ``CLAUDE.md`` next to it, if present, is read as preferences.
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import yaml

from memory_passport.importers.base import Importer, ImportOptions, ImportResult
from memory_passport.importers.builder import VaultBuilder
from memory_passport.importers.router import PREFERENCES, PROFILE, Route
from memory_passport.importers.text import is_hedged, split_prose, tidy
from memory_passport.model import Fact, VaultError, slugify, split_frontmatter

_TYPE_TO_KIND = {
    "user": "profile",
    "feedback": "preferences",
    "project": "area",
    "reference": "topic",
}
_CODE_SPAN = re.compile(r"`[^`]*`")


class ClaudeImporter(Importer):
    name = "claude"
    help = "claude.ai export (.zip/folder), pasted memory text, or a Claude Code memory folder"

    def detect(self, path: Path) -> bool:
        return _classify(path) is not None

    def load(self, path: Path, options: ImportOptions) -> ImportResult:
        kind = _classify(path)
        if kind is None:
            raise VaultError(
                f"{path}: not a claude.ai export, memory text or Claude Code memory dir"
            )
        source = "claude-code" if kind == "code" else "claude"
        b = VaultBuilder(source, allow_health=options.allow_health, do_route=options.route)
        notes: list[str] = []

        if kind == "export":
            n = _import_projects(_read_export(path, "projects.json"), b)
            notes.append(f"imported {n} project(s) from projects.json; conversations not mined")
        elif kind == "text":
            n = _import_text(path.read_text(encoding="utf-8"), b)
            notes.append(f"split {path.name} into {n} sentence(s)")
        else:
            n, files = _import_code_dir(path, b)
            notes.append(f"read {files} memory file(s) from {path}, {n} fact(s)")

        if options.memory_text:
            n = _import_text(options.memory_text.read_text(encoding="utf-8"), b)
            notes.append(f"split {options.memory_text.name} into {n} sentence(s)")

        notes.append(f"dropped {len(b.dropped)} fact(s) by exclusion")
        return ImportResult(vault=b.build(), notes=notes, dropped=b.dropped)


def _classify(path: Path) -> str | None:
    if path.is_file() and path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
        return "export" if any(n.endswith("projects.json") for n in names) else None
    if path.is_dir():
        if (path / "projects.json").is_file():
            return "export"
        if (path / "MEMORY.md").is_file() or any(_is_code_memory(p) for p in path.glob("*.md")):
            return "code"
        return None
    if path.suffix in (".txt", ".md"):
        return "text"
    return None


def _is_code_memory(p: Path) -> bool:
    try:
        fm, _ = split_frontmatter(p.read_text(encoding="utf-8"))
    except (VaultError, OSError):
        return False
    return isinstance(fm.get("metadata"), dict) and "type" in fm["metadata"]


def _read_export(path: Path, name: str) -> list[dict]:
    if path.is_file():
        with zipfile.ZipFile(path) as z:
            member = next((n for n in z.namelist() if n.endswith(name)), None)
            data = json.loads(z.read(member)) if member else []
    else:
        f = path / name
        data = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else []
    return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []


def _import_projects(projects: list[dict], b: VaultBuilder) -> int:
    n = 0
    for p in projects:
        name = (p.get("name") or "").strip()
        if not name:
            continue
        r = Route(
            "area",
            slugify(name),
            name,
            (p.get("description") or f"Claude project: {name}.").strip(),
        )
        desc = (p.get("description") or "").strip()
        if desc:
            b.add(Fact("stated", tidy(f"Project description: {desc}")), to=r)
        for s in split_prose(p.get("prompt_template") or ""):
            b.add(Fact("stated", tidy(s)), to=r, section="Project instructions")
        n += 1
    return n


def _import_text(text: str, b: VaultBuilder) -> int:
    n = 0
    for s in split_prose(text):
        t = tidy(s)
        b.add(Fact("inferred" if is_hedged(t) else "stated", t))
        n += 1
    return n


def _import_code_dir(path: Path, b: VaultBuilder) -> tuple[int, int]:
    facts = files = 0
    for p in sorted(path.glob("*.md")):
        if p.name == "MEMORY.md":
            continue
        try:
            fm, body = split_frontmatter(p.read_text(encoding="utf-8"))
        except VaultError:
            continue
        meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
        kind = _TYPE_TO_KIND.get(str(meta.get("type", "")), "topic")
        name = str(fm.get("name") or p.stem)
        display = _display_name(name, kind)
        description = str(fm.get("description") or display)
        if kind == "profile":
            r = PROFILE
        elif kind == "preferences":
            r = PREFERENCES
        else:
            r = Route(kind, slugify(display), display, description)  # type: ignore[arg-type]
        files += 1
        for s in split_prose(_CODE_SPAN.sub(lambda m: m.group(0), body)):
            if b.add(
                Fact("stated", tidy(s)),
                to=r,
                section=display if kind in ("profile", "preferences") else "",
            ):
                facts += 1
    claude_md = path.parent / "CLAUDE.md"
    if claude_md.is_file():
        _, body = _maybe_frontmatter(claude_md.read_text(encoding="utf-8"))
        for s in split_prose(body):
            if b.add(Fact("stated", tidy(s)), to=PREFERENCES, section="CLAUDE.md"):
                facts += 1
    return facts, files


def _maybe_frontmatter(text: str) -> tuple[dict, str]:
    try:
        return split_frontmatter(text)
    except VaultError:
        return {}, text


def _display_name(name: str, kind: str) -> str:
    s = re.sub(r"^(project|feedback|user|reference)[-_]", "", name)
    s = s.replace("-", " ").replace("_", " ").strip()
    return s[:1].upper() + s[1:] if s else name


def _yaml_dump(d: dict) -> str:  # pragma: no cover - debugging aid
    return yaml.safe_dump(d, sort_keys=False)
