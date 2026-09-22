"""ChatGPT importer.

Reads two real inputs:

1. **The data export** (Settings → Data controls → Export data), as the ``.zip`` OpenAI
   emails, the unpacked folder, or ``conversations.json`` on its own. The export has no
   memory file, but every time ChatGPT saves a memory it emits an assistant message
   addressed to its ``bio`` tool, and those messages are in ``conversations.json``:

   ``message.author.role == "assistant"`` and ``message.recipient == "bio"`` with the
   memory sentence in ``message.content.parts[0]``. This importer walks every
   conversation's ``mapping`` and collects them, with ``create_time`` as the fact date.

2. **A pasted memory list** (Settings → Personalisation → Manage memories, select all,
   copy), or the output of asking ChatGPT to list everything it remembers. Pass it as a
   ``.txt``/``.md`` file directly, or alongside the export with ``--memory-text``.
   Accepted line shapes: ``1. [2025-05-02]. The user ...``, ``[date] - ...``, ``- ...``
   or a bare sentence.

Provenance rule: the ``bio`` tool is only invoked to record what the user shared in
conversation, so entries default to ``[stated]``. A sentence with a hedge (seems, likely,
probably, may ...) is tagged ``[inferred]`` because that is ChatGPT recording a guess.
"""

from __future__ import annotations

import json
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

from memory_passport.importers.base import Importer, ImportOptions, ImportResult
from memory_passport.importers.builder import VaultBuilder
from memory_passport.importers.text import Line, is_hedged, parse_memory_lines, tidy
from memory_passport.model import Fact


class ChatGPTImporter(Importer):
    name = "chatgpt"
    help = "ChatGPT data export (.zip, folder or conversations.json) or a pasted memory list"

    def detect(self, path: Path) -> bool:
        if path.is_file() and path.suffix == ".zip":
            with zipfile.ZipFile(path) as z:
                return any(n.endswith("conversations.json") for n in z.namelist())
        if path.is_dir():
            return (path / "conversations.json").is_file()
        return path.name == "conversations.json" or path.suffix in (".txt", ".md")

    def load(self, path: Path, options: ImportOptions) -> ImportResult:
        b = VaultBuilder(self.name, allow_health=options.allow_health, do_route=options.route)
        notes: list[str] = []
        lines: list[Line] = []

        if path.suffix in (".txt", ".md") and not options.memory_text:
            lines = parse_memory_lines(path.read_text(encoding="utf-8"))
            notes.append(f"read {len(lines)} memory line(s) from {path.name}")
        else:
            convs = _load_conversations(path)
            found = _bio_messages(convs)
            notes.append(
                f"scanned {len(convs)} conversation(s), found {len(found)} saved memory(ies)"
            )
            lines.extend(found)

        if options.memory_text:
            extra = parse_memory_lines(options.memory_text.read_text(encoding="utf-8"))
            notes.append(f"read {len(extra)} memory line(s) from {options.memory_text.name}")
            lines.extend(extra)

        added = 0
        for ln in lines:
            text = tidy(ln.text)
            tag = "inferred" if is_hedged(text) else "stated"
            if b.add(Fact(tag, text, date=ln.date)):
                added += 1
        notes.append(
            f"kept {added} fact(s), dropped {len(b.dropped)} by exclusion or as duplicates"
        )
        return ImportResult(vault=b.build(), notes=notes, dropped=b.dropped, redacted=b.redacted)


def _load_conversations(path: Path) -> list[dict]:
    if path.is_file() and path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.endswith("conversations.json"))
            data = json.loads(z.read(name))
    elif path.is_dir():
        data = json.loads((path / "conversations.json").read_text(encoding="utf-8"))
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = [data]
    return [c for c in data if isinstance(c, dict)]


def _bio_messages(convs: list[dict]) -> list[Line]:
    out: list[Line] = []
    for conv in convs:
        for node in (conv.get("mapping") or {}).values():
            msg = (node or {}).get("message") or {}
            author = msg.get("author") or {}
            recipient = str(msg.get("recipient") or "")
            if not (recipient == "bio" or recipient.startswith("bio.")):
                continue
            if author.get("role") != "assistant":
                continue
            content = msg.get("content") or {}
            parts = content.get("parts") or []
            if not parts and isinstance(content.get("text"), str):
                parts = [content["text"]]
            text = " ".join(_part_text(p) for p in parts).strip()
            if not text:
                continue
            ts = msg.get("create_time")
            d: date | None = None
            if isinstance(ts, int | float):
                d = datetime.fromtimestamp(ts, tz=UTC).date()
            elif isinstance(ts, str):
                try:
                    d = datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
                except ValueError:
                    d = None
            for sentence in _split_bio(text):
                out.append(Line(sentence, d))
    return out


def _part_text(p: object) -> str:
    """Parts are usually strings; newer exports sometimes wrap them in dicts."""
    if isinstance(p, str):
        return p
    if isinstance(p, dict):
        return str(p.get("text") or p.get("content") or "")
    return ""


def _split_bio(text: str) -> list[str]:
    """A single bio call can carry several memories separated by newlines."""
    return [s.strip() for s in text.splitlines() if s.strip()]
