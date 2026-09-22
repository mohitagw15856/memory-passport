from __future__ import annotations

from importlib.metadata import entry_points

from memory_passport.exporters.base import Exporter


def _builtins() -> list[type[Exporter]]:
    from memory_passport.exporters.chatgpt import ChatGPTExporter
    from memory_passport.exporters.claude import ClaudeExporter
    from memory_passport.exporters.claude_code import ClaudeCodeExporter
    from memory_passport.exporters.cursor import CursorExporter
    from memory_passport.exporters.markdown import MarkdownExporter

    return [MarkdownExporter, ChatGPTExporter, ClaudeExporter, ClaudeCodeExporter, CursorExporter]


def list_exporters() -> dict[str, type[Exporter]]:
    found = {cls.name: cls for cls in _builtins()}
    for ep in entry_points(group="memory_passport.exporters"):
        try:
            cls = ep.load()
        except Exception:  # noqa: BLE001
            continue
        if isinstance(cls, type) and issubclass(cls, Exporter):
            found.setdefault(cls.name, cls)
    return dict(sorted(found.items()))


def get_exporter(name: str) -> Exporter:
    table = list_exporters()
    if name not in table:
        raise KeyError(f"no exporter named '{name}'; available: {', '.join(table)}")
    return table[name]()
