from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from memory_passport.cli import app
from memory_passport.diff import diff_dirs
from memory_passport.merge import merge_dirs
from memory_passport.model import load_vault, write_vault
from memory_passport.validate import validate_vault
from tests.conftest import SAMPLE_VAULT

runner = CliRunner()


def two_vaults(tmp_path: Path) -> tuple[Path, Path]:
    a = tmp_path / "a"
    b = tmp_path / "b"
    shutil.copytree(SAMPLE_VAULT, a)
    shutil.copytree(SAMPLE_VAULT, b)
    prof = b / "profile.md"
    text = prof.read_text()
    text = text.replace(
        "- [stated] Works four days a week, Monday to Thursday.",
        "- [stated] Works five days a week, Monday to Thursday.",
    )
    text = text.replace(
        "- [inferred] Probably has a background in data science",
        "- [stated] Probably has a background in data science",
    )
    text += "- [stated] Has a cat called Biscuit.\n"
    prof.write_text(text.replace("sources: [chatgpt, claude-code, manual]", "sources: [gemini]"))
    (b / "people" / "priya-nair.md").unlink()
    (b / "topics" / "rust.md").write_text(
        '---\nname: Rust\ndescription: Rust.\nsources: [gemini]\nupdated: "2026-09-01"\n'
        "kind: topic\n---\n\n- [stated] Writes Rust at work.\n"
    )
    return a, b


def test_diff(tmp_path: Path):
    a, b = two_vaults(tmp_path)
    d = diff_dirs(a, b)
    assert [str(p) for p in d.only_a] == ["people/priya-nair.md"]
    assert [str(p) for p in d.only_b] == ["topics/rust.md"]
    (fd,) = d.changed
    assert str(fd.path) == "profile.md"
    assert [f.text for f in fd.added] == [
        "Works five days a week, Monday to Thursday.",
        "Has a cat called Biscuit.",
    ]
    assert [f.text for f in fd.removed] == ["Works four days a week, Monday to Thursday."]
    assert [(x.tag, y.tag) for x, y in fd.retagged] == [("inferred", "stated")]
    assert "sources" in fd.frontmatter
    assert diff_dirs(a, a).empty
    text = d.render()
    assert "+ [stated] Has a cat called Biscuit." in text and "~ [inferred] -> [stated]" in text


def test_merge_with_conflict(tmp_path: Path):
    a, b = two_vaults(tmp_path)
    merged, report = merge_dirs(a, b)
    out = write_vault(merged, tmp_path / "m")
    prof = (out / "profile.md").read_text()
    assert (
        "<<<<<<< a\n- [stated] Works four days a week, Monday to Thursday.\n=======\n"
        "- [stated] Works five days a week, Monday to Thursday.\n>>>>>>> b"
    ) in prof
    assert "- [stated] Probably has a background in data science" in prof  # higher trust wins
    assert "## From b\n- [stated] Has a cat called Biscuit." in prof
    assert "## Languages" in prof  # a's headings survive
    assert "sources: [chatgpt, claude-code, manual, gemini]" in prof
    assert (out / "people" / "priya-nair.md").is_file() and (out / "topics" / "rust.md").is_file()
    assert len(report.conflicts) == 1
    rep = validate_vault(out)
    assert [i.code for i in rep.errors] == ["conflict"] * 3
    # resolving the conflict by hand makes it valid again
    prof = prof.replace(
        "<<<<<<< a\n- [stated] Works four days a week, Monday to Thursday.\n=======\n", ""
    ).replace(">>>>>>> b\n", "")
    (out / "profile.md").write_text(prof)
    assert validate_vault(out).ok()


def test_merge_identity(tmp_path: Path):
    merged, report = merge_dirs(SAMPLE_VAULT, SAMPLE_VAULT)
    assert report.conflicts == []
    out = write_vault(merged, tmp_path / "m")
    assert diff_dirs(SAMPLE_VAULT, out).empty
    assert (
        load_vault(out).get("profile.md").facts == load_vault(SAMPLE_VAULT).get("profile.md").facts
    )


def test_cli_merge_and_diff(tmp_path: Path):
    a, b = two_vaults(tmp_path)
    r = runner.invoke(app, ["diff", str(a), str(b)])
    assert r.exit_code == 1 and "only in b" in r.output
    r = runner.invoke(app, ["diff", str(a), str(a)])
    assert r.exit_code == 0 and "no differences" in r.output
    r = runner.invoke(app, ["merge", str(a), str(b), "--out", str(tmp_path / "m")])
    assert r.exit_code == 3 and "CONFLICT profile.md" in r.output
    r = runner.invoke(app, ["merge", str(a), str(b), "--out", str(tmp_path / "m")])
    assert r.exit_code == 2  # not empty
