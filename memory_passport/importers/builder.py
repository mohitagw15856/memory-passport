"""Accumulate routed facts and produce a Vault, applying exclusions and dedupe."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path, PurePosixPath

from memory_passport.exclusions import scan
from memory_passport.importers.router import PREFERENCES, PROFILE, Route, route
from memory_passport.model import Fact, MemoryFile, Vault, path_for, render_body


@dataclass
class _Bucket:
    route: Route
    sections: dict[str, list[Fact]] = field(default_factory=dict)
    keys: set[str] = field(default_factory=set)
    aliases: set[str] = field(default_factory=set)


@dataclass
class VaultBuilder:
    source: str
    allow_health: bool = False
    do_route: bool = True
    dropped: list[tuple[str, str]] = field(default_factory=list)
    _buckets: dict[PurePosixPath, _Bucket] = field(default_factory=dict)

    def add(
        self,
        fact: Fact,
        *,
        to: Route | None = None,
        section: str = "",
    ) -> bool:
        """Add a fact. Returns False if it was dropped by an exclusion or as a duplicate."""
        hits = scan(fact.text, allow_health=self.allow_health)
        if hits:
            self.dropped.append((hits[0].category, fact.text))
            return False
        if to is None:
            to = route(fact.text) if self.do_route else PROFILE
        if fact.source is None:
            fact.source = self.source
        path = path_for(to.kind, to.slug)
        bucket = self._buckets.setdefault(path, _Bucket(to))
        if fact.key in bucket.keys:
            return False
        bucket.keys.add(fact.key)
        bucket.sections.setdefault(section or to.section, []).append(fact)
        return True

    def add_alias(self, kind: str, slug: str, alias: str) -> None:
        p = path_for(kind, slug)  # type: ignore[arg-type]
        if p in self._buckets:
            self._buckets[p].aliases.add(alias)

    def build(self, root: Path | None = None) -> Vault:
        files: list[MemoryFile] = []
        for path in sorted(self._buckets, key=lambda p: (len(p.parts), str(p))):
            b = self._buckets[path]
            facts = [f for fs in b.sections.values() for f in fs]
            dates = [f.date for f in facts if f.date]
            r = b.route
            if r.kind == "profile":
                r = PROFILE
            elif r.kind == "preferences":
                r = PREFERENCES
            fm: dict = {
                "name": r.name,
                "description": r.description,
                "sources": [self.source],
            }
            if b.aliases:
                fm["aliases"] = sorted(b.aliases)
            fm["updated"] = (max(dates) if dates else date.today()).isoformat()
            fm["kind"] = r.kind
            files.append(
                MemoryFile(path=path, frontmatter=fm, body=render_body(b.sections), facts=facts)
            )
        manifest = {"allow_health": True} if self.allow_health else {}
        return Vault(root=Path(root or "."), manifest=manifest, files=files)
