"""Compare two vaults fact by fact."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from memory_passport.model import Fact, Vault, load_vault


@dataclass
class FileDiff:
    path: PurePosixPath
    added: list[Fact] = field(default_factory=list)
    removed: list[Fact] = field(default_factory=list)
    retagged: list[tuple[Fact, Fact]] = field(default_factory=list)
    frontmatter: dict[str, tuple[object, object]] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return not (self.added or self.removed or self.retagged or self.frontmatter)


@dataclass
class VaultDiff:
    only_a: list[PurePosixPath]
    only_b: list[PurePosixPath]
    changed: list[FileDiff]

    @property
    def empty(self) -> bool:
        return not (self.only_a or self.only_b or self.changed)

    def render(self) -> str:
        out: list[str] = []
        for p in self.only_a:
            out.append(f"--- {p} (only in a)")
        for p in self.only_b:
            out.append(f"+++ {p} (only in b)")
        for fd in self.changed:
            out.append(f"=== {fd.path}")
            for k, (a, b) in fd.frontmatter.items():
                out.append(f"  ~ {k}: {a!r} -> {b!r}")
            for f in fd.removed:
                out.append(f"  - [{f.tag}] {f.text}")
            for f in fd.added:
                out.append(f"  + [{f.tag}] {f.text}")
            for a, b in fd.retagged:
                out.append(f"  ~ [{a.tag}] -> [{b.tag}] {b.text}")
        return "\n".join(out) + ("\n" if out else "no differences\n")


_IGNORED = {"updated"}


def diff_vaults(a: Vault, b: Vault) -> VaultDiff:
    fa = {f.path: f for f in a.files}
    fb = {f.path: f for f in b.files}
    changed: list[FileDiff] = []
    for p in sorted(fa.keys() & fb.keys()):
        fd = FileDiff(p)
        ka = {f.key: f for f in fa[p].facts}
        kb = {f.key: f for f in fb[p].facts}
        fd.removed = [ka[k] for k in ka if k not in kb]
        fd.added = [kb[k] for k in kb if k not in ka]
        fd.retagged = [(ka[k], kb[k]) for k in ka if k in kb and ka[k].tag != kb[k].tag]
        for key in sorted((set(fa[p].frontmatter) | set(fb[p].frontmatter)) - _IGNORED):
            va, vb = fa[p].frontmatter.get(key), fb[p].frontmatter.get(key)
            if isinstance(va, list) and isinstance(vb, list) and set(va) == set(vb):
                continue
            if va != vb:
                fd.frontmatter[key] = (va, vb)
        if not fd.empty:
            changed.append(fd)
    return VaultDiff(
        only_a=sorted(fa.keys() - fb.keys()), only_b=sorted(fb.keys() - fa.keys()), changed=changed
    )


def diff_dirs(a: Path, b: Path) -> VaultDiff:
    return diff_vaults(load_vault(a), load_vault(b))
