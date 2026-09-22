"""Merge two vaults. Never silently overwrites: disagreements become conflict markers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from memory_passport.model import FACT_RE, Fact, MemoryFile, Vault, load_vault, parse_facts

TRUST = {"stated": 2, "observed": 1, "inferred": 0}
CONFLICT_RE = re.compile(r"^(<{7}|={7}|>{7})( |$)")

_NEG = r"\b(not|no|never|isn't|aren't|doesn't|don't|didn't|wasn't|no longer|stopped|used to)\b"
_NUMWORDS = (
    r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|"
    r"forty|fifty|hundred|thousand|\d+(?:[.,]\d+)?)\b"
)
_STEM_RE = re.compile(f"{_NEG}|{_NUMWORDS}", re.IGNORECASE)


def _stem(fact: Fact) -> str:
    """Fact text with negations and numbers removed: two facts with the same stem but
    different keys are treated as contradicting each other."""
    s = _STEM_RE.sub(" ", fact.key)
    return " ".join(s.split())


@dataclass
class MergeReport:
    files: int = 0
    facts: int = 0
    conflicts: list[tuple[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def merge_vaults(
    a: Vault, b: Vault, *, label_a: str = "a", label_b: str = "b"
) -> tuple[Vault, MergeReport]:
    report = MergeReport()
    fa = {f.path: f for f in a.files}
    fb = {f.path: f for f in b.files}
    out: list[MemoryFile] = []
    for p in sorted(fa.keys() | fb.keys(), key=lambda p: (len(p.parts), str(p))):
        if p in fa and p in fb:
            mf = _merge_file(fa[p], fb[p], label_a, label_b, report)
        else:
            mf = fa.get(p) or fb[p]
        out.append(mf)
        report.files += 1
        report.facts += len(mf.facts)
    manifest = dict(a.manifest)
    if b.manifest.get("allow_health"):
        manifest["allow_health"] = True
    return Vault(root=Path("."), manifest=manifest, files=out), report


def _union(a: list, b: list) -> list:
    return list(a) + [x for x in b if x not in a]


def _merge_file(a: MemoryFile, b: MemoryFile, la: str, lb: str, report: MergeReport) -> MemoryFile:
    fm = dict(a.frontmatter)
    fm["sources"] = _union(a.sources, b.sources)
    aliases = _union(a.frontmatter.get("aliases") or [], b.frontmatter.get("aliases") or [])
    if aliases:
        fm["aliases"] = aliases
    ua, ub = str(a.frontmatter.get("updated", "")), str(b.frontmatter.get("updated", ""))
    fm["updated"] = max(ua, ub) or date.today().isoformat()

    body: list[str] = []
    for key in ("name", "description"):
        va, vb = a.frontmatter.get(key), b.frontmatter.get(key)
        if va != vb and va and vb:
            report.conflicts.append((str(a.path), f"{key}: {va!r} vs {vb!r}"))
            body += [
                f"<<<<<<< {la}",
                f"{key}: {va}",
                "=======",
                f"{key}: {vb}",
                f">>>>>>> {lb}",
                "",
            ]

    ka = {f.key: f for f in a.facts}
    kb = {f.key: f for f in b.facts}
    stems_b: dict[str, Fact] = {}
    for f in b.facts:
        stems_b.setdefault(_stem(f), f)

    # Decide, per fact of a, what replaces it: the merged fact or a conflict block.
    replacement: dict[str, list[str]] = {}
    used_b: set[str] = set()
    for f in a.facts:
        if f.key in kb:
            g = kb[f.key]
            used_b.add(g.key)
            best = f if TRUST[f.tag] >= TRUST[g.tag] else g
            merged = Fact(
                best.tag,
                best.text,
                best.source or g.source or f.source,
                best.date or g.date or f.date,
            )
            replacement[f.key] = [merged.render()]
            continue
        g = stems_b.get(_stem(f))
        if g is not None and g.key not in ka and g.key not in used_b:
            used_b.add(g.key)
            report.conflicts.append((str(a.path), f"{f.text!r} vs {g.text!r}"))
            replacement[f.key] = [
                f"<<<<<<< {la}",
                f.render(),
                "=======",
                g.render(),
                f">>>>>>> {lb}",
            ]
            continue
        replacement[f.key] = [f.render()]

    # Walk a's body so its headings and prose survive; swap fact lines for their replacements.
    for line in a.body.splitlines():
        m = FACT_RE.match(line)
        if m:
            key = Fact(m.group("tag"), m.group("text").strip()).key  # type: ignore[arg-type]
            body.extend(replacement.pop(key, [line]))
        else:
            body.append(line)
    new_facts = [g for g in b.facts if g.key not in ka and g.key not in used_b]
    if new_facts:
        if body and body[-1].strip():
            body.append("")
        body.append(f"## From {lb}")
        body.extend(g.render() for g in new_facts)

    body_text = "\n".join(body).strip("\n") + "\n"
    facts = parse_facts(body_text)
    return MemoryFile(path=a.path, frontmatter=fm, body=body_text, facts=facts)


def merge_dirs(a: Path, b: Path) -> tuple[Vault, MergeReport]:
    return merge_vaults(load_vault(a), load_vault(b), label_a=a.name or "a", label_b=b.name or "b")


def has_conflict_markers(text: str) -> list[int]:
    return [i for i, line in enumerate(text.splitlines(), 1) if CONFLICT_RE.match(line)]
