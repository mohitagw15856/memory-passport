"""Claude Code export: a memory directory in the layout Claude Code's auto-memory uses.

Writes ``MEMORY.md`` (the index Claude Code loads each session) and one file per vault
file with ``name``, ``description`` and ``metadata.type`` frontmatter. Drop the folder
into ``~/.claude/projects/<project>/memory/`` or point ``--out`` there directly.
"""

from __future__ import annotations

from memory_passport.exporters.base import Exporter, ExportResult, ordered
from memory_passport.model import Vault

_KIND_TO_TYPE = {
    "profile": "user",
    "preferences": "feedback",
    "person": "reference",
    "topic": "reference",
    "area": "project",
}


class ClaudeCodeExporter(Exporter):
    name = "claude-code"
    help = "a Claude Code memory folder (MEMORY.md index + one file per subject)"
    default_out = "memory"

    def render(self, vault: Vault) -> ExportResult:
        files: dict[str, str] = {}
        index = ["# Memory index", ""]
        for f in ordered(vault):
            fname = (
                f"{f.kind}_{f.path.stem}.md"
                if f.kind not in ("profile", "preferences")
                else f"{f.kind}.md"
            )
            body = "\n".join(
                f"- {x.text}" + (f" _({x.tag})_" if x.tag != "stated" else "") for x in f.facts
            )
            files[fname] = (
                "---\n"
                f"name: {f.name}\n"
                f"description: {f.frontmatter.get('description', '')}\n"
                "metadata:\n"
                f"  type: {_KIND_TO_TYPE.get(f.kind or '', 'reference')}\n"
                "---\n\n"
                f"{body}\n"
            )
            index.append(f"- [{f.name}]({fname}) — {f.frontmatter.get('description', '')}")
        files["MEMORY.md"] = "\n".join(index) + "\n"
        return ExportResult(files)
