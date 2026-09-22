from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from memory_passport.importers import ImportOptions, get_importer, list_importers
from memory_passport.importers.router import route
from memory_passport.importers.text import parse_memory_lines, tidy
from memory_passport.model import write_vault
from memory_passport.validate import validate_vault
from tests.conftest import ROOT

FIX = ROOT / "tests" / "fixtures"


def facts_of(vault, rel: str) -> list[str]:
    f = vault.get(rel)
    assert f is not None, f"{rel} missing; have {[str(x.path) for x in vault.files]}"
    return [x.text for x in f.facts]


def test_registry_lists_builtins():
    assert set(list_importers()) >= {"chatgpt", "claude", "markdown"}


def test_parse_memory_lines_shapes():
    lines = parse_memory_lines(
        "# heading\n1. [2025-05-02]. The user likes tea.\n[2025-06-01] - Lives in Leeds\n"
        "- bullet one\nplain line\n\n"
    )
    assert [ln.text for ln in lines] == [
        "The user likes tea.",
        "Lives in Leeds",
        "bullet one",
        "plain line",
    ]
    assert lines[0].date.isoformat() == "2025-05-02" and lines[1].date.isoformat() == "2025-06-01"
    assert tidy("the user likes tea") == "User likes tea."


def test_router():
    assert route("User's partner is named Priya.").kind == "person"
    assert route("User's partner is named Priya.").slug == "priya"
    assert route("User prefers responses in British English.").kind == "preferences"
    assert route("User is working on a project called Ledger Rewrite.").kind == "area"
    assert route("User is learning Mandarin.").kind == "topic"
    assert route("User lives in Seattle.").kind == "profile"


def test_chatgpt_zip_export(tmp_path: Path):
    zp = tmp_path / "chatgpt-export.zip"
    with zipfile.ZipFile(zp, "w") as z:
        for name in ("conversations.json", "user.json"):
            z.write(FIX / "chatgpt" / name, name)
    imp = get_importer("chatgpt")
    assert imp.detect(zp)
    res = imp.load(zp, ImportOptions())
    v = res.vault
    assert "User is a product engineer at a fintech in Manchester." in facts_of(v, "profile.md")
    assert facts_of(v, "people/priya.md") == ["User's partner is named Priya."]
    assert facts_of(v, "preferences.md") == ["User prefers responses in British English."]
    assert facts_of(v, "areas/ledger-rewrite.md")
    hiking = v.get("topics/hiking.md")
    assert hiking is not None and hiking.facts[0].tag == "inferred"
    assert [c for c, _ in res.dropped] == ["card-number"]
    # dates come from create_time
    assert v.get("profile.md").facts[0].date.isoformat() == "2025-03-03"
    out = write_vault(v, tmp_path / "vault")
    assert validate_vault(out).ok(), validate_vault(out).issues


def test_chatgpt_folder_and_conversations_json():
    imp = get_importer("chatgpt")
    assert imp.detect(FIX / "chatgpt")
    assert imp.detect(FIX / "chatgpt" / "conversations.json")
    n = imp.load(FIX / "chatgpt" / "conversations.json", ImportOptions()).fact_count
    assert n == 5


def test_chatgpt_pasted_memories_and_health_opt_in(tmp_path: Path):
    imp = get_importer("chatgpt")
    res = imp.load(FIX / "chatgpt" / "memories.txt", ImportOptions())
    assert [c for c, _ in res.dropped] == ["health"]
    assert facts_of(res.vault, "people/dana-whitfield.md") == [
        "User's manager is called Dana Whitfield."
    ]
    assert res.vault.get("topics/mandarin.md")
    res2 = imp.load(FIX / "chatgpt" / "memories.txt", ImportOptions(allow_health=True))
    assert res2.dropped == [] and res2.vault.manifest["allow_health"] is True
    out = write_vault(res2.vault, tmp_path / "v")
    assert validate_vault(out).ok()


def test_chatgpt_no_route_puts_everything_in_profile():
    res = get_importer("chatgpt").load(FIX / "chatgpt" / "memories.txt", ImportOptions(route=False))
    assert [str(f.path) for f in res.vault.files] == ["profile.md"]


def test_chatgpt_memory_text_option_combines():
    res = get_importer("chatgpt").load(
        FIX / "chatgpt" / "conversations.json",
        ImportOptions(memory_text=FIX / "chatgpt" / "memories.txt"),
    )
    assert res.fact_count == 5 + 4


def test_claude_export_projects(tmp_path: Path):
    zp = tmp_path / "claude-export.zip"
    with zipfile.ZipFile(zp, "w") as z:
        for name in ("conversations.json", "projects.json", "users.json"):
            z.write(FIX / "claude-export" / name, name)
    imp = get_importer("claude")
    assert imp.detect(zp) and imp.detect(FIX / "claude-export")
    res = imp.load(zp, ImportOptions())
    assert [str(f.path) for f in res.vault.files] == ["areas/ledger-rewrite.md"]
    texts = facts_of(res.vault, "areas/ledger-rewrite.md")
    assert "Always answer in British English." in texts
    assert "The codebase is a Rust workspace with three crates." in texts
    assert res.vault.files[0].sources == ["claude"]
    assert validate_vault(write_vault(res.vault, tmp_path / "v")).ok()


def test_claude_memory_text():
    res = get_importer("claude").load(FIX / "claude-memory.txt", ImportOptions())
    v = res.vault
    prof = v.get("profile.md")
    assert prof and any("Manchester" in f.text for f in prof.facts)
    tags = {f.text: f.tag for f in v.facts() and [x for _, x in v.facts()]}
    assert tags["You seem to prefer terse answers."] == "inferred"


def test_claude_code_memory_dir(tmp_path: Path):
    src = tmp_path / "memory"
    shutil.copytree(FIX / "claude-code", src)
    (tmp_path / "CLAUDE.md").write_text("# Rules\n\n- Never re-read a file already read.\n")
    imp = get_importer("claude")
    assert imp.detect(src)
    res = imp.load(src, ImportOptions())
    v = res.vault
    assert v.files[0].sources == ["claude-code"]
    assert "Target cut-over is the end of Q4 2026." in facts_of(v, "areas/ledger.md")
    assert "All commits must be authored as sam." in facts_of(v, "preferences.md")
    assert "Never re-read a file already read." in facts_of(v, "preferences.md")
    assert any("Manchester" in t for t in facts_of(v, "profile.md"))
    assert all(f.tag == "stated" for _, f in v.facts())
    assert validate_vault(write_vault(v, tmp_path / "v")).ok()


def test_markdown_importer(tmp_path: Path):
    imp = get_importer("markdown")
    assert imp.detect(FIX / "markdown")
    res = imp.load(FIX / "markdown", ImportOptions())
    v = res.vault
    notes = v.get("topics/notes.md")
    assert notes is not None
    by_text = {f.text: f for f in notes.facts}
    assert by_text["Probably a morning person."].tag == "inferred"
    assert (
        by_text["Commits at 7am."].tag == "observed"
        and by_text["Commits at 7am."].source == "claude-code"
    )
    dana = v.get("people/dana.md")
    assert dana and dana.frontmatter["aliases"] == ["Dana"] and dana.name == "Dana Whitfield"
    assert "1 untagged bullet(s)" in res.notes[0]
    assert validate_vault(write_vault(v, tmp_path / "v")).ok()
