"""Identity export: the vault itself. Useful for ``--to markdown --out other-dir``."""

from __future__ import annotations

from memory_passport.exporters.base import Exporter, ExportResult
from memory_passport.model import Vault


class MarkdownExporter(Exporter):
    name = "markdown"
    help = "the vault as-is (also what Hermes Agent and most custom bots read directly)"
    default_out = "passport-export"

    def render(self, vault: Vault) -> ExportResult:
        return ExportResult({str(f.path): f.render() for f in vault.files})
