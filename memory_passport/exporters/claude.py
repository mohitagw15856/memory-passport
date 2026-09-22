"""Claude export: the memory-import format claude.ai asks for.

Settings → Memory → Start import accepts pasted text. Anthropic's own recommended
export prompt for other assistants produces lines of the form
``[date saved, if available] - memory content``, so that is what this writes, grouped
under headings Claude can use to organise its summary. Provenance survives as a prefix.
"""

from __future__ import annotations

from memory_passport.exporters.base import Exporter, ExportResult, fact_sentence, ordered
from memory_passport.model import Vault


class ClaudeExporter(Exporter):
    name = "claude"
    help = "text for claude.ai Settings > Memory > Start import"

    def render(self, vault: Vault) -> ExportResult:
        out = ["Memories to import. Each line is one memory.", ""]
        for f in ordered(vault):
            out.append(f"## {f.name}" + (f" ({f.kind})" if f.kind not in ("profile",) else ""))
            for x in f.facts:
                d = (x.date or None) and x.date.isoformat()
                stamp = f"[{d}] - " if d else "- "
                out.append(f"{stamp}{fact_sentence(x)}")
            out.append("")
        return ExportResult({"-": "\n".join(out).rstrip() + "\n"})
