"""ChatGPT export: paste-ready text.

ChatGPT has no memory import. The two routes in are:

- **Custom instructions** (Settings → Personalisation): two boxes, "What would you like
  ChatGPT to know about you" and "How would you like ChatGPT to respond", each capped at
  1,500 characters. This exporter writes both blocks and warns when one is over the cap.
- **Tell it in chat**: paste the "Remember this" block and ChatGPT will save memories
  from it via its bio tool. That block has no cap but long pastes are saved selectively.

Provenance is lost; inferred facts are prefixed "Possibly:" so ChatGPT does not save a
guess as a certainty.
"""

from __future__ import annotations

from memory_passport.exporters.base import Exporter, ExportResult, fact_sentence, ordered
from memory_passport.model import Vault

CAP = 1500


class ChatGPTExporter(Exporter):
    name = "chatgpt"
    help = "custom-instruction blocks (1,500 chars each) plus a 'remember this' paste"

    def render(self, vault: Vault) -> ExportResult:
        about: list[str] = []
        respond: list[str] = []
        for f in ordered(vault):
            target = respond if f.kind == "preferences" else about
            label = "" if f.kind in ("profile", "preferences") else f"{f.name}: "
            target.extend(f"- {label}{fact_sentence(x)}" for x in f.facts)
        about_txt = "\n".join(about)
        respond_txt = "\n".join(respond)
        remember = "\n".join(f"{i}. {line[2:]}" for i, line in enumerate(about + respond, 1))
        notes = []
        for name, txt in (("about you", about_txt), ("how to respond", respond_txt)):
            if len(txt) > CAP:
                notes.append(f"'{name}' block is {len(txt)} characters; ChatGPT caps it at {CAP}")
        out = (
            "=== Custom instructions: What would you like ChatGPT to know about you? ===\n"
            f"{about_txt}\n\n"
            "=== Custom instructions: How would you like ChatGPT to respond? ===\n"
            f"{respond_txt}\n\n"
            "=== Or paste this into a chat ===\n"
            "Please remember the following about me. Save each as a separate memory.\n"
            f"{remember}\n"
        )
        return ExportResult({"-": out}, notes)
