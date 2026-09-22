"""Validate a vault directory against the memory-passport spec."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Literal

import yaml

from memory_passport import SPEC_VERSION
from memory_passport.exclusions import scan
from memory_passport.merge import has_conflict_markers
from memory_passport.model import (
    FOLDERS,
    MANIFEST_NAME,
    SINGLETONS,
    SLUG_RE,
    VaultError,
    expected_kind,
    parse_file,
    untagged_bullets,
)
from memory_passport.schema import schema_errors

Level = Literal["error", "warning"]

ALLOWED_TOP_LEVEL = {*SINGLETONS, *FOLDERS, MANIFEST_NAME, "README.md", ".gitignore", ".git"}


@dataclass(frozen=True)
class Issue:
    level: Level
    code: str
    path: str
    message: str
    line: int | None = None

    def __str__(self) -> str:
        loc = f"{self.path}:{self.line}" if self.line else self.path
        return f"{self.level.upper():7} {self.code:18} {loc}: {self.message}"


@dataclass
class Report:
    root: Path
    issues: list[Issue]
    file_count: int = 0
    fact_count: int = 0

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]

    def ok(self, *, strict: bool = False) -> bool:
        return not self.errors and not (strict and self.warnings)


def validate_vault(root: Path) -> Report:
    root = Path(root)
    issues: list[Issue] = []
    if not root.is_dir():
        return Report(
            root, [Issue("error", "not-a-directory", str(root), "path is not a directory")]
        )

    manifest = _check_manifest(root, issues)
    allow_health = bool(manifest.get("allow_health", False))

    for entry in sorted(root.iterdir()):
        if entry.name.startswith(".") and entry.name != ".git":
            continue
        if entry.name not in ALLOWED_TOP_LEVEL:
            issues.append(
                Issue(
                    "warning",
                    "unexpected-path",
                    entry.name,
                    "not part of the spec layout; assistants will ignore it",
                )
            )
    for folder in FOLDERS:
        d = root / folder
        if d.is_dir():
            for entry in sorted(d.iterdir()):
                if entry.is_dir() or not entry.name.endswith(".md"):
                    issues.append(
                        Issue(
                            "warning",
                            "unexpected-path",
                            f"{folder}/{entry.name}",
                            "only .md files are read from this folder",
                        )
                    )

    if not (root / "profile.md").is_file():
        issues.append(Issue("warning", "missing-profile", "profile.md", "vault has no profile.md"))

    file_count = fact_count = 0
    seen_names: dict[tuple[str, str], str] = {}
    for rel in _memory_paths(root):
        file_count += 1
        n = _check_file(root, rel, issues, allow_health=allow_health, seen=seen_names)
        fact_count += n

    return Report(root, issues, file_count=file_count, fact_count=fact_count)


def _memory_paths(root: Path) -> list[PurePosixPath]:
    from memory_passport.model import memory_paths

    return memory_paths(root)


def _check_manifest(root: Path, issues: list[Issue]) -> dict:
    mp = root / MANIFEST_NAME
    if not mp.is_file():
        issues.append(
            Issue(
                "warning", "missing-manifest", MANIFEST_NAME, "no passport.yaml; assuming spec 0.1"
            )
        )
        return {}
    try:
        data = yaml.safe_load(mp.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        issues.append(Issue("error", "bad-manifest", MANIFEST_NAME, f"invalid YAML: {e}"))
        return {}
    if not isinstance(data, dict):
        issues.append(Issue("error", "bad-manifest", MANIFEST_NAME, "manifest must be a mapping"))
        return {}
    for msg in schema_errors("manifest", data):
        issues.append(Issue("error", "bad-manifest", MANIFEST_NAME, msg))
    ver = str(data.get("spec_version", ""))
    if ver and ver.split(".")[0] != SPEC_VERSION.split(".")[0]:
        issues.append(
            Issue(
                "error",
                "spec-version",
                MANIFEST_NAME,
                f"spec_version {ver} is not compatible with this validator ({SPEC_VERSION})",
            )
        )
    return data


def _check_file(
    root: Path,
    rel: PurePosixPath,
    issues: list[Issue],
    *,
    allow_health: bool,
    seen: dict[tuple[str, str], str],
) -> int:
    p = str(rel)
    if rel.parts[0] in FOLDERS and not SLUG_RE.match(rel.stem):
        issues.append(Issue("error", "bad-slug", p, "filename must be lower-case kebab-case ASCII"))
    try:
        text = (root / rel).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        issues.append(Issue("error", "not-utf8", p, "file is not valid UTF-8"))
        return 0
    try:
        mf = parse_file(rel, text)
    except VaultError as e:
        issues.append(Issue("error", "bad-frontmatter", p, str(e)))
        return 0

    for msg in schema_errors("frontmatter", mf.frontmatter):
        issues.append(Issue("error", "schema", p, msg))

    want = expected_kind(rel)
    got = mf.frontmatter.get("kind")
    if want and got and got != want:
        issues.append(
            Issue("error", "kind-mismatch", p, f"kind is '{got}' but path implies '{want}'")
        )

    upd = mf.frontmatter.get("updated")
    if isinstance(upd, str):
        try:
            d = date.fromisoformat(upd)
            if d > date.today():
                issues.append(Issue("warning", "future-date", p, f"updated {upd} is in the future"))
        except ValueError:
            issues.append(Issue("error", "schema", p, f"updated: '{upd}' is not a calendar date"))
    elif isinstance(upd, date):
        issues.append(
            Issue("error", "schema", p, "updated must be a quoted string, not a bare YAML date")
        )

    name = mf.frontmatter.get("name")
    if isinstance(name, str) and got:
        k = (got, name.casefold())
        if k in seen:
            issues.append(
                Issue(
                    "warning", "duplicate-name", p, f"same name and kind as {seen[k]}; merge them?"
                )
            )
        seen[k] = p

    for line in has_conflict_markers(mf.body):
        issues.append(Issue("error", "conflict", p, "unresolved merge conflict marker", line))
    for line in untagged_bullets(mf.body):
        issues.append(
            Issue(
                "warning",
                "untagged-fact",
                p,
                "bullet has no [stated]/[observed]/[inferred] tag",
                line,
            )
        )
    if not mf.facts:
        issues.append(Issue("warning", "no-facts", p, "file contains no fact lines"))

    for fact in mf.facts:
        if not fact.text:
            issues.append(Issue("error", "empty-fact", p, "fact line has no text", fact.line_no))
        for hit in scan(fact.text, allow_health=allow_health):
            issues.append(
                Issue(
                    "error",
                    f"excluded:{hit.category}",
                    p,
                    f"{hit.detail}; this category is excluded by the spec (see SPEC.md §7)",
                    fact.line_no,
                )
            )
    return len(mf.facts)
