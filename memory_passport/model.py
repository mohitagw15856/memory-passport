"""Data model and (de)serialisation for a memory-passport vault.

A vault is a directory. Each memory file is markdown with YAML frontmatter.
Fact lines are bullets prefixed with a provenance tag: ``- [stated] ...``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Literal

import yaml

Tag = Literal["stated", "observed", "inferred"]
TAGS: tuple[Tag, ...] = ("stated", "observed", "inferred")
Kind = Literal["profile", "preferences", "person", "topic", "area"]
KINDS: tuple[Kind, ...] = ("profile", "preferences", "person", "topic", "area")

SINGLETONS: dict[str, Kind] = {"profile.md": "profile", "preferences.md": "preferences"}
FOLDERS: dict[str, Kind] = {"people": "person", "topics": "topic", "areas": "area"}
MANIFEST_NAME = "passport.yaml"
SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")

FACT_RE = re.compile(
    r"^(?P<indent>\s*)[-*]\s+\[(?P<tag>stated|observed|inferred)\]\s+(?P<text>.*?)"
    r"(?:\s*<!--\s*src:\s*(?P<src>[a-z0-9-]+)(?:\s*,\s*(?P<date>\d{4}-\d{2}-\d{2}))?\s*-->)?\s*$"
)
BULLET_RE = re.compile(r"^\s*[-*]\s+\S")
FRONTMATTER_RE = re.compile(r"\A---\r?\n(?P<yaml>.*?)\r?\n---\r?\n?(?P<body>.*)\Z", re.DOTALL)


class VaultError(Exception):
    """Raised when a file cannot be parsed at all."""


@dataclass
class Fact:
    tag: Tag
    text: str
    source: str | None = None
    date: date | None = None
    line_no: int = 0

    @property
    def key(self) -> str:
        """Normalised identity used for dedupe and diffing: text only, case-folded."""
        return " ".join(self.text.split()).casefold().rstrip(".")

    def render(self) -> str:
        line = f"- [{self.tag}] {self.text}"
        if self.source:
            meta = self.source if not self.date else f"{self.source}, {self.date.isoformat()}"
            line += f" <!-- src: {meta} -->"
        return line


@dataclass
class MemoryFile:
    path: PurePosixPath
    frontmatter: dict
    body: str
    facts: list[Fact] = field(default_factory=list)

    @property
    def kind(self) -> str | None:
        return self.frontmatter.get("kind")

    @property
    def name(self) -> str:
        return str(self.frontmatter.get("name", self.path.stem))

    @property
    def sources(self) -> list[str]:
        return list(self.frontmatter.get("sources") or [])

    def render(self) -> str:
        fm = yaml.safe_dump(self.frontmatter, sort_keys=False, allow_unicode=True).rstrip()
        body = self.body.strip("\n")
        return f"---\n{fm}\n---\n\n{body}\n" if body else f"---\n{fm}\n---\n"


@dataclass
class Vault:
    root: Path
    manifest: dict = field(default_factory=dict)
    files: list[MemoryFile] = field(default_factory=list)

    def get(self, rel: str) -> MemoryFile | None:
        p = PurePosixPath(rel)
        return next((f for f in self.files if f.path == p), None)

    def facts(self) -> list[tuple[MemoryFile, Fact]]:
        return [(f, fact) for f in self.files for fact in f.facts]


def expected_kind(rel: PurePosixPath) -> Kind | None:
    """Kind implied by a file's position in the vault, or None if the path is not a memory path."""
    parts = rel.parts
    if len(parts) == 1 and parts[0] in SINGLETONS:
        return SINGLETONS[parts[0]]
    if len(parts) == 2 and parts[0] in FOLDERS and parts[1].endswith(".md"):
        return FOLDERS[parts[0]]
    return None


def path_for(kind: Kind, slug: str = "") -> PurePosixPath:
    """Inverse of :func:`expected_kind`."""
    for name, k in SINGLETONS.items():
        if k == kind:
            return PurePosixPath(name)
    for folder, k in FOLDERS.items():
        if k == kind:
            return PurePosixPath(folder) / f"{slug}.md"
    raise ValueError(kind)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    return s or "untitled"


def split_frontmatter(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise VaultError("missing YAML frontmatter (file must start with '---')")
    try:
        fm = yaml.safe_load(m.group("yaml"))
    except yaml.YAMLError as e:
        raise VaultError(f"invalid YAML frontmatter: {e}") from e
    if not isinstance(fm, dict):
        raise VaultError("frontmatter must be a YAML mapping")
    return fm, m.group("body")


def parse_facts(body: str) -> list[Fact]:
    facts: list[Fact] = []
    for i, line in enumerate(body.splitlines(), start=1):
        m = FACT_RE.match(line)
        if not m:
            continue
        d = m.group("date")
        facts.append(
            Fact(
                tag=m.group("tag"),  # type: ignore[arg-type]
                text=m.group("text").strip(),
                source=m.group("src"),
                date=date.fromisoformat(d) if d else None,
                line_no=i,
            )
        )
    return facts


def untagged_bullets(body: str) -> list[int]:
    """Line numbers of bullet lines that are not valid fact lines."""
    return [
        i
        for i, line in enumerate(body.splitlines(), start=1)
        if BULLET_RE.match(line) and not FACT_RE.match(line)
    ]


def parse_file(rel: PurePosixPath, text: str) -> MemoryFile:
    fm, body = split_frontmatter(text)
    return MemoryFile(path=rel, frontmatter=fm, body=body, facts=parse_facts(body))


def memory_paths(root: Path) -> list[PurePosixPath]:
    """All paths under ``root`` that the spec reserves for memory files, sorted."""
    found: list[PurePosixPath] = []
    for name in SINGLETONS:
        if (root / name).is_file():
            found.append(PurePosixPath(name))
    for folder in FOLDERS:
        d = root / folder
        if d.is_dir():
            found.extend(PurePosixPath(folder) / p.name for p in sorted(d.glob("*.md")))
    return found


def load_vault(root: Path) -> Vault:
    """Load a vault, raising :class:`VaultError` on the first unparseable file.

    Use :mod:`memory_passport.validate` for a full report that tolerates bad files.
    """
    root = Path(root)
    if not root.is_dir():
        raise VaultError(f"not a directory: {root}")
    manifest: dict = {}
    mp = root / MANIFEST_NAME
    if mp.is_file():
        loaded = yaml.safe_load(mp.read_text(encoding="utf-8"))
        manifest = loaded if isinstance(loaded, dict) else {}
    files = []
    for rel in memory_paths(root):
        try:
            files.append(parse_file(rel, (root / rel).read_text(encoding="utf-8")))
        except VaultError as e:
            raise VaultError(f"{rel}: {e}") from e
    return Vault(root=root, manifest=manifest, files=files)


def write_vault(vault: Vault, root: Path | None = None) -> Path:
    """Write every file in ``vault`` under ``root`` (default: ``vault.root``)."""
    from memory_passport import SPEC_VERSION, __version__

    root = Path(root or vault.root)
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "spec_version": SPEC_VERSION,
        "created": date.today().isoformat(),
        "exported_by": f"memory-passport {__version__}",
        **vault.manifest,
    }
    (root / MANIFEST_NAME).write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    for f in vault.files:
        target = root / Path(*f.path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f.render(), encoding="utf-8")
    return root


def render_body(sections: dict[str, list[Fact]]) -> str:
    """Render ``{heading: facts}`` into a markdown body. An empty heading means no ``##`` line."""
    out: list[str] = []
    for heading, facts in sections.items():
        if not facts:
            continue
        if heading:
            out.append(f"## {heading}")
        out.extend(f.render() for f in facts)
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n" if out else ""
