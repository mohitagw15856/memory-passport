"""Microsoft Copilot importer.

Copilot's memory ("what Copilot knows about you") has no export. Ask it: "List every
memory you have stored about me, one per line." Save the answer as a text file and pass
it here.
"""

from __future__ import annotations

from memory_passport.importers.textlist import TextListImporter


class CopilotImporter(TextListImporter):
    name = "copilot"
    help = "Microsoft Copilot memory pasted as text (no export exists)"
    prompt = "List every memory you have stored about me, one per line."
