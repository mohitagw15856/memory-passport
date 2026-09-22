"""Lookup of importers by name: built-ins plus ``memory_passport.importers`` entry points."""

from __future__ import annotations

from importlib.metadata import entry_points

from memory_passport.importers.base import Importer


def _builtins() -> list[type[Importer]]:
    from memory_passport.importers.chatgpt import ChatGPTImporter
    from memory_passport.importers.claude import ClaudeImporter
    from memory_passport.importers.copilot import CopilotImporter
    from memory_passport.importers.gemini import GeminiImporter
    from memory_passport.importers.markdown import MarkdownImporter

    return [ChatGPTImporter, ClaudeImporter, MarkdownImporter, GeminiImporter, CopilotImporter]


def list_importers() -> dict[str, type[Importer]]:
    found: dict[str, type[Importer]] = {cls.name: cls for cls in _builtins()}
    for ep in entry_points(group="memory_passport.importers"):
        try:
            cls = ep.load()
        except Exception:  # noqa: BLE001 - a broken plugin must not break the CLI
            continue
        if isinstance(cls, type) and issubclass(cls, Importer):
            found.setdefault(cls.name, cls)
    return dict(sorted(found.items()))


def get_importer(name: str) -> Importer:
    table = list_importers()
    if name not in table:
        raise KeyError(f"no importer named '{name}'; available: {', '.join(table)}")
    return table[name]()
