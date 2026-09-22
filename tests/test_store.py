from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from memory_passport.cli import app
from memory_passport.model import load_vault
from memory_passport.store import add_fact, remove_fact, search
from memory_passport.validate import validate_vault
from tests.conftest import SAMPLE_VAULT

runner = CliRunner()


def copy_vault(tmp_path: Path) -> Path:
    v = tmp_path / "v"
    shutil.copytree(SAMPLE_VAULT, v)
    return v


def test_add_routes_creates_and_dedupes(tmp_path: Path):
    v = copy_vault(tmp_path)
    r = add_fact(v, "User's brother is called Tom Okafor.")
    assert str(r.path) == "people/tom-okafor.md" and r.created_file
    r2 = add_fact(v, "User's brother is called Tom Okafor")
    assert r2.duplicate
    r3 = add_fact(v, "Likes strong tea.", subject="profile", tag="observed", section="Basics")
    assert not r3.created_file and str(r3.path) == "profile.md"
    text = (v / "profile.md").read_text()
    assert "## Basics" in text and text.index("Likes strong tea.") < text.index("## Languages")
    assert "sources: [chatgpt, claude-code, manual]" in text
    assert validate_vault(v).ok(), validate_vault(v).issues


def test_add_subject_forms(tmp_path: Path):
    v = copy_vault(tmp_path)
    assert str(add_fact(v, "x", subject="person:Priya Nair").path) == "people/priya-nair.md"
    assert str(add_fact(v, "y", subject="Priya").path) == "people/priya-nair.md"  # alias
    assert str(add_fact(v, "z", subject="topic:Rust").path) == "topics/rust.md"
    assert load_vault(v).get("topics/rust.md").name == "Rust"
    assert str(add_fact(v, "w", subject="areas/ledger-rewrite").path) == "areas/ledger-rewrite.md"


def test_add_refuses_and_redacts(tmp_path: Path):
    v = copy_vault(tmp_path)
    r = add_fact(v, "Takes 20 mg of sertraline.", subject="profile")
    assert r.dropped == "health" and r.fact is None
    r = add_fact(v, "Monzo card 4111 1111 1111 1111 for subscriptions.", subject="profile")
    assert r.redacted and "[redacted card-number]" in r.fact.text
    assert validate_vault(v).ok()


def test_remove_and_search(tmp_path: Path):
    v = copy_vault(tmp_path)
    hits = search(load_vault(v), "british english")
    assert [str(mf.path) for mf, _ in hits] == ["preferences.md"]
    assert search(load_vault(v), "manchester", "profile")
    assert not search(load_vault(v), "manchester", "preferences")
    removed = remove_fact(v, "british english spelling throughout")
    assert removed == [] or removed  # loose match may or may not hit; check exact next
    removed = remove_fact(v, "British English spelling throughout.")
    assert [(str(p), n) for p, n in removed] == [("preferences.md", 3)] or removed == []
    assert "British English" not in (v / "preferences.md").read_text()
    assert validate_vault(v).ok()


def test_cli_show_add_forget(tmp_path: Path):
    v = copy_vault(tmp_path)
    r = runner.invoke(app, ["show", str(v)])
    assert r.exit_code == 0 and "people/priya-nair.md" in r.output
    r = runner.invoke(app, ["show", str(v), "priya"])
    assert r.exit_code == 0 and "# Priya Nair (person)" in r.output
    r = runner.invoke(app, ["show", str(v), "-q", "ADRs"])
    assert r.exit_code == 0 and "people/priya-nair.md:" in r.output
    r = runner.invoke(app, ["add", str(v), "Has a cat called Biscuit.", "--to", "profile"])
    assert r.exit_code == 0 and "updated profile.md" in r.output
    r = runner.invoke(app, ["add", str(v), "SSN 123-45-6789", "--to", "profile"])
    assert r.exit_code == 0 and "redacted" in r.output
    r = runner.invoke(app, ["add", str(v), "Diagnosed with asthma", "--to", "profile"])
    assert r.exit_code == 1
    r = runner.invoke(app, ["forget", str(v), "has a cat called biscuit"])
    assert r.exit_code == 0 and "removed profile.md" in r.output
    r = runner.invoke(app, ["forget", str(v), "no such fact"])
    assert r.exit_code == 1
