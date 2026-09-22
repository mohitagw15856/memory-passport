"""Markdown importer: a folder of ``.md`` files, with or without frontmatter.

- A file already at a passport path (``profile.md``, ``people/x.md`` ...) keeps that path.
- Any other file lands in ``topics/<slug>.md`` unless its frontmatter has a valid ``kind``.
- Tagged bullets are kept as they are. Untagged bullets become ``[inferred]`` and the
  count is reported, because the file gave no provenance and the spec forbids guessing up.
- Prose is not split into facts; a markdown folder is assumed to be bullets already.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from memory_passport.importers.base import Importer, ImportOptions, ImportResult
from memory_passport.importers.builder import VaultBuilder
from memory_passport.importers.router import PREFERENCES, PROFILE, Route
from memory_passport.model import (
    BULLET_RE,
    FACT_RE,
    KINDS,
    Fact,
    VaultError,
    expected_kind,
    parse_facts,
    slugify,
    split_frontmatter,
)


class MarkdownImporter(Importer):
    name = "markdown"
    help = "a folder of markdown files, tagged or not (untagged bullets become [inferred])"

    def detect(self, path: Path) -> bool:
        return path.is_dir() and any(path.rglob("*.md"))

    def load(self, path: Path, options: ImportOptions) -> ImportResult:
        b = VaultBuilder("manual", allow_health=options.allow_health, do_route=False)
        notes: list[str] = []
        promoted = files = 0
        for p in sorted(path.rglob("*.md")):
            rel = PurePosixPath(p.relative_to(path).as_posix())
            if rel.name in ("README.md", "MEMORY.md"):
                continue
            text = p.read_text(encoding="utf-8")
            try:
                fm, body = split_frontmatter(text)
            except VaultError:
                fm, body = {}, text
            r = _route_for(rel, fm)
            files += 1
            for fact in parse_facts(body):
                b.add(fact, to=r)
            for line in body.splitlines():
                if BULLET_RE.match(line) and not FACT_RE.match(line):
                    t = line.strip().lstrip("-* ").strip()
                    if b.add(Fact("inferred", t), to=r):
                        promoted += 1
            for alias in fm.get("aliases") or []:
                b.add_alias(r.kind, r.slug, str(alias))
        notes.append(f"read {files} file(s); {promoted} untagged bullet(s) tagged [inferred]")
        notes.append(f"dropped {len(b.dropped)} fact(s) by exclusion")
        return ImportResult(vault=b.build(), notes=notes, dropped=b.dropped)


def _route_for(rel: PurePosixPath, fm: dict) -> Route:
    kind = expected_kind(rel) or (fm.get("kind") if fm.get("kind") in KINDS else None)
    name = str(fm.get("name") or rel.stem.replace("-", " ").title())
    desc = str(fm.get("description") or f"Imported from {rel}.")
    if kind == "profile":
        return PROFILE
    if kind == "preferences":
        return PREFERENCES
    return Route(kind or "topic", slugify(rel.stem), name, desc)  # type: ignore[arg-type]
