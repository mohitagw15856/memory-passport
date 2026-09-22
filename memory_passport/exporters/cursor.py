"""Cursor export: a project rule file.

Cursor reads ``.cursor/rules/*.mdc`` (frontmatter + markdown) and applies rules marked
``alwaysApply: true`` to every chat. It has no user-level memory, so this is per repo.
"""

from __future__ import annotations

from memory_passport.exporters.base import Exporter, ExportResult, fact_sentence, ordered
from memory_passport.model import Vault


class CursorExporter(Exporter):
    name = "cursor"
    help = "a .cursor/rules/user-memory.mdc rule file"
    default_out = ".cursor/rules/user-memory.mdc"

    def render(self, vault: Vault) -> ExportResult:
        out = [
            "---",
            "description: Who the user is and how they want the assistant to behave",
            "alwaysApply: true",
            "---",
            "",
        ]
        for f in ordered(vault):
            out.append(f"## {f.name}")
            out.extend(f"- {fact_sentence(x)}" for x in f.facts)
            out.append("")
        return ExportResult({"-": "\n".join(out).rstrip() + "\n"})
