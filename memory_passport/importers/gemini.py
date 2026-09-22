"""Gemini importer.

Gemini has no data export for its memory ("Saved info"). Open Settings → Saved info and
copy the list, or ask Gemini: "List everything you have saved about me, one item per
line, with the date if you have it." Save the answer as a text file and pass it here.
"""

from __future__ import annotations

from memory_passport.importers.textlist import TextListImporter


class GeminiImporter(TextListImporter):
    name = "gemini"
    help = "Gemini 'Saved info' pasted as text (no export exists)"
    prompt = (
        "List everything you have saved about me, one item per line, with the date if you have it."
    )
