from __future__ import annotations

from memory_passport.exporters import get_exporter, list_exporters
from memory_passport.model import load_vault
from tests.conftest import SAMPLE_VAULT


def test_registry():
    assert set(list_exporters()) >= {"markdown", "chatgpt", "claude", "claude-code", "cursor"}


def test_chatgpt_blocks():
    out = get_exporter("chatgpt").render(load_vault(SAMPLE_VAULT))
    text = out.single
    assert "know about you" in text and "How would you like ChatGPT to respond" in text
    assert "- British English spelling throughout." in text
    assert "Possibly: Probably has a background in data science" in text
    assert out.notes == []


def test_claude_import_format():
    text = get_exporter("claude").render(load_vault(SAMPLE_VAULT)).single
    assert "[2026-03-02] - Product engineer at a small fintech in Manchester." in text
    assert "## Preferences (preferences)" in text


def test_claude_code_dir():
    res = get_exporter("claude-code").render(load_vault(SAMPLE_VAULT))
    assert (
        "MEMORY.md" in res.files
        and "profile.md" in res.files
        and "area_ledger-rewrite.md" in res.files
    )
    assert "type: project" in res.files["area_ledger-rewrite.md"]
    assert res.files["MEMORY.md"].count("\n- [") == 5


def test_cursor_rule():
    text = get_exporter("cursor").render(load_vault(SAMPLE_VAULT)).single
    assert text.startswith("---\ndescription:") and "alwaysApply: true" in text
    assert "## Priya Nair" in text


def test_markdown_identity():
    v = load_vault(SAMPLE_VAULT)
    res = get_exporter("markdown").render(v)
    assert res.files["profile.md"] == (SAMPLE_VAULT / "profile.md").read_text()


def test_prompt_exporter_and_budget():
    from memory_passport.exporters.prompt import PromptExporter

    v = load_vault(SAMPLE_VAULT)
    text = PromptExporter().render(v).single
    assert text.startswith("<user_memory>") and text.rstrip().endswith("</user_memory>")
    assert "## person: Priya Nair" in text and "- [inferred]" in text
    # stated facts precede inferred within a section
    sec = text.split("## Sam Okafor")[1].split("##")[0]
    assert sec.index("[stated]") < sec.index("[inferred]")
    small = PromptExporter(budget=600).render(v)
    assert len(small.single) <= 600 and small.notes and "- [inferred]" not in small.single
