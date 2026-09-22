"""Base for products that have no export but will list their memories when asked.

Subclasses set ``name``, ``help`` and ``prompt`` (what to ask the product). Input is a
``.txt``/``.md`` file of the pasted answer. Every line is a fact; hedged lines are
``[inferred]``, the rest ``[stated]``, on the same reasoning as the ChatGPT importer: the
product only lists what it was told.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from memory_passport.importers.base import Importer, ImportOptions, ImportResult
from memory_passport.importers.builder import VaultBuilder
from memory_passport.importers.text import is_hedged, parse_memory_lines, tidy
from memory_passport.model import Fact


class TextListImporter(Importer):
    prompt: ClassVar[str] = "List every memory you have stored about me, one per line."

    def detect(self, path: Path) -> bool:
        return path.is_file() and path.suffix in (".txt", ".md")

    def load(self, path: Path, options: ImportOptions) -> ImportResult:
        b = VaultBuilder(self.name, allow_health=options.allow_health, do_route=options.route)
        lines = parse_memory_lines(path.read_text(encoding="utf-8"))
        if options.memory_text:
            lines += parse_memory_lines(options.memory_text.read_text(encoding="utf-8"))
        kept = 0
        for ln in lines:
            text = tidy(ln.text)
            if b.add(Fact("inferred" if is_hedged(text) else "stated", text, date=ln.date)):
                kept += 1
        notes = [f"read {len(lines)} line(s), kept {kept} fact(s)"]
        return ImportResult(vault=b.build(), notes=notes, dropped=b.dropped, redacted=b.redacted)
