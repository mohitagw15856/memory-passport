"""Prompt export: a compact system-prompt block any model can use.

This is the one exporter that works everywhere: paste it at the top of a system prompt,
a Hermes Agent persona, a custom GPT, or an API call. Provenance survives as a legend
plus the tag on each line, and inferred facts are grouped last so a model reads the
certain things first. ``--budget`` trims to a character budget, dropping inferred facts
first, then observed, then the oldest stated.
"""

from __future__ import annotations

from memory_passport.exporters.base import Exporter, ExportResult, ordered
from memory_passport.model import Fact, Vault

TRUST = {"stated": 2, "observed": 1, "inferred": 0}


class PromptExporter(Exporter):
    name = "prompt"
    help = "a system-prompt block for any model, API or agent (--budget trims by trust)"

    def __init__(self, budget: int | None = None) -> None:
        self.budget = budget

    def render(self, vault: Vault) -> ExportResult:
        files = ordered(vault)
        # Rank every fact; higher rank survives a budget cut.
        ranked: list[tuple[int, str, str, Fact]] = []
        for f in files:
            for x in f.facts:
                ranked.append((TRUST[x.tag], x.date.isoformat() if x.date else "", str(f.path), x))
        ranked.sort(key=lambda r: (-r[0], r[1]))
        keep = {id(r[3]) for r in ranked}
        notes: list[str] = []
        if self.budget:
            body = _render(files, keep)
            dropped = 0
            while len(body) > self.budget and ranked:
                _, _, _, victim = ranked.pop()
                keep.discard(id(victim))
                dropped += 1
                body = _render(files, keep)
            if dropped:
                notes.append(
                    f"dropped {dropped} lowest-trust fact(s) to fit {self.budget} characters"
                )
        return ExportResult({"-": _render(files, keep)}, notes)


def _render(files, keep: set[int]) -> str:
    out = [
        "<user_memory>",
        "Facts about the user. Tags: [stated] they said it; [observed] seen in their activity;",
        "[inferred] a guess, treat with care. Prefer stated over observed over inferred.",
        "",
    ]
    for f in files:
        facts = [x for x in f.facts if id(x) in keep]
        if not facts:
            continue
        label = f.name if f.kind in ("profile", "preferences") else f"{f.kind}: {f.name}"
        out.append(f"## {label}")
        for x in sorted(facts, key=lambda x: -TRUST[x.tag]):
            out.append(f"- [{x.tag}] {x.text}")
        out.append("")
    out.append("</user_memory>")
    return "\n".join(out) + "\n"
