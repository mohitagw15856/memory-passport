"""Read and write single facts in a vault on disk. Shared by the CLI and the MCP server."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath

from memory_passport.exclusions import redact
from memory_passport.importers.router import PREFERENCES, PROFILE, route
from memory_passport.model import (
    FACT_RE,
    KINDS,
    Fact,
    MemoryFile,
    Tag,
    Vault,
    VaultError,
    expected_kind,
    load_vault,
    parse_file,
    path_for,
    slugify,
)

_SUBJECT_RE = re.compile(r"^(person|topic|area|people|topics|areas)[:/](.+)$")


@dataclass
class AddResult:
    path: PurePosixPath
    fact: Fact | None
    created_file: bool
    dropped: str | None = None
    redacted: bool = False
    duplicate: bool = False


def resolve_subject(vault: Vault, subject: str | None, text: str) -> tuple[PurePosixPath, str, str]:
    """Turn a subject spec into ``(path, name, description)``.

    Accepts ``profile``, ``preferences``, ``people/priya-nair``, ``person:Priya Nair``,
    an existing file's name ("Priya Nair"), or nothing (routed from the text).
    """
    if not subject:
        r = route(text)
        return path_for(r.kind, r.slug), r.name, r.description
    s = subject.strip().removesuffix(".md")
    if s in ("profile", "preferences"):
        r = PROFILE if s == "profile" else PREFERENCES
        return path_for(r.kind), r.name, r.description
    if m := _SUBJECT_RE.match(s):
        kind_word, rest = m.group(1), m.group(2).strip()
        kind = {"people": "person", "topics": "topic", "areas": "area"}.get(kind_word, kind_word)
        slug = slugify(rest)
        existing = vault.get(str(path_for(kind, slug)))  # type: ignore[arg-type]
        if existing:
            return existing.path, existing.name, str(existing.frontmatter.get("description", ""))
        name = rest if rest != slug else rest.replace("-", " ").title()
        return path_for(kind, slug), name, f"{name}."  # type: ignore[arg-type]
    for f in vault.files:
        names = {
            f.name.casefold(),
            *(str(a).casefold() for a in f.frontmatter.get("aliases") or []),
        }
        if s.casefold() in names:
            return f.path, f.name, str(f.frontmatter.get("description", ""))
    raise VaultError(
        f"unknown subject '{subject}'; use profile, preferences, people/<slug>, person:<Name>, "
        "topic:<Name>, area:<Name>, or an existing subject name"
    )


def add_fact(
    root: Path,
    text: str,
    *,
    subject: str | None = None,
    tag: Tag = "stated",
    section: str = "",
    source: str = "manual",
    when: date | None = None,
) -> AddResult:
    vault = load_vault(root)
    allow_health = bool(vault.manifest.get("allow_health"))
    text = " ".join(text.split())
    new_text, hits = redact(text, allow_health=allow_health)
    path, name, description = resolve_subject(vault, subject, text)
    if hits:
        return AddResult(path, None, False, dropped=hits[0].category)
    fact = Fact(tag, new_text, source=source, date=when or date.today())
    target = root / Path(*path.parts)
    created = not target.exists()
    if created:
        kind = expected_kind(path)
        assert kind in KINDS
        mf = MemoryFile(
            path=path,
            frontmatter={
                "name": name,
                "description": description,
                "sources": [source],
                "updated": date.today().isoformat(),
                "kind": kind,
            },
            body="",
        )
    else:
        mf = parse_file(path, target.read_text(encoding="utf-8"))
        if any(f.key == fact.key for f in mf.facts):
            return AddResult(path, fact, False, duplicate=True)
    body = mf.body.rstrip("\n")
    if section and f"## {section}" not in body:
        body += f"\n\n## {section}"
    elif section:
        body = _insert_under(body, section, fact.render())
        fact_inserted = True
    else:
        fact_inserted = False
    if not (section and fact_inserted):
        body += ("\n" if body else "") + fact.render()
    mf.body = body.strip("\n") + "\n"
    if source not in (mf.frontmatter.get("sources") or []):
        mf.frontmatter["sources"] = [*(mf.frontmatter.get("sources") or []), source]
    mf.frontmatter["updated"] = date.today().isoformat()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(mf.render(), encoding="utf-8")
    return AddResult(path, fact, created, redacted=new_text != text)


def _insert_under(body: str, section: str, line: str) -> str:
    lines = body.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip() == f"## {section}":
            j = i + 1
            while j < len(lines) and not lines[j].startswith("## "):
                j += 1
            while j > i + 1 and not lines[j - 1].strip():
                j -= 1
            lines.insert(j, line)
            return "\n".join(lines)
    return body + f"\n\n## {section}\n{line}"


def remove_fact(root: Path, text: str) -> list[tuple[PurePosixPath, int]]:
    """Remove every fact whose key matches ``text``. Returns ``(path, line)`` per removal."""
    vault = load_vault(root)
    key = Fact("stated", text).key
    removed: list[tuple[PurePosixPath, int]] = []
    for mf in vault.files:
        if not any(f.key == key for f in mf.facts):
            continue
        kept = []
        for i, ln in enumerate(mf.body.splitlines(), 1):
            m = FACT_RE.match(ln)
            if m and Fact("stated", m.group("text").strip()).key == key:
                removed.append((mf.path, i))
                continue
            kept.append(ln)
        mf.body = "\n".join(kept).strip("\n") + "\n"
        mf.frontmatter["updated"] = date.today().isoformat()
        (root / Path(*mf.path.parts)).write_text(mf.render(), encoding="utf-8")
    return removed


def search(
    vault: Vault, query: str = "", subject: str | None = None
) -> list[tuple[MemoryFile, Fact]]:
    """Facts whose text, or whose file's name/aliases, contain every word of ``query``."""
    words = [w.casefold() for w in query.split()]
    out = []
    for mf in vault.files:
        if subject and not _file_matches(mf, subject):
            continue
        hay_file = " ".join([mf.name, *map(str, mf.frontmatter.get("aliases") or [])]).casefold()
        for fact in mf.facts:
            hay = f"{hay_file} {fact.text.casefold()}"
            if all(w in hay for w in words):
                out.append((mf, fact))
    return out


def _file_matches(mf: MemoryFile, subject: str) -> bool:
    s = subject.casefold().removesuffix(".md")
    return s in (
        str(mf.path).casefold(),
        mf.path.stem.casefold(),
        mf.name.casefold(),
        mf.kind or "",
    ) or s in {str(a).casefold() for a in mf.frontmatter.get("aliases") or []}


def render_subjects(vault: Vault) -> str:
    rows = [f"{'path':32} {'kind':11} {'facts':>5}  name"]
    for mf in sorted(vault.files, key=lambda f: (len(f.path.parts), str(f.path))):
        rows.append(f"{str(mf.path):32} {mf.kind or '?':11} {len(mf.facts):>5}  {mf.name}")
    return "\n".join(rows) + "\n"


def render_file(mf: MemoryFile) -> str:
    head = f"# {mf.name} ({mf.kind}) — {mf.frontmatter.get('description', '')}\n"
    src = ", ".join(mf.sources)
    head += f"sources: {src} · updated: {mf.frontmatter.get('updated', '?')}\n\n"
    return head + "\n".join(f.render() for f in mf.facts) + "\n"
