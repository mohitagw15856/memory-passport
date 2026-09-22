from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from memory_passport.cli import app
from tests.conftest import ROOT, SAMPLE_VAULT

runner = CliRunner()
FIX = ROOT / "tests" / "fixtures"


def test_import_autodetect_and_export_roundtrip(tmp_path: Path):
    out = tmp_path / "v"
    r = runner.invoke(app, ["import", str(FIX / "chatgpt"), "--out", str(out)])
    assert r.exit_code == 0, r.output
    assert "found 6 saved memory(ies)" in r.output and "redacted:" in r.output
    r = runner.invoke(app, ["validate", str(out)])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["export", str(out), "--to", "claude"])
    assert r.exit_code == 0 and "Memories to import" in r.output
    r = runner.invoke(
        app, ["export", str(out), "--to", "claude-code", "--out", str(tmp_path / "cc")]
    )
    assert r.exit_code == 0 and (tmp_path / "cc" / "MEMORY.md").is_file()
    r = runner.invoke(app, ["export", str(out), "--to", "cursor", "--out", str(tmp_path / "r.mdc")])
    assert r.exit_code == 0 and (tmp_path / "r.mdc").read_text().startswith("---")


def test_import_ambiguous_needs_from(tmp_path: Path):
    r = runner.invoke(
        app, ["import", str(FIX / "chatgpt" / "memories.txt"), "--out", str(tmp_path / "v")]
    )
    assert r.exit_code == 2 and "pass --from" in r.output
    r = runner.invoke(
        app,
        [
            "import",
            str(FIX / "chatgpt" / "memories.txt"),
            "--from",
            "chatgpt",
            "--out",
            str(tmp_path / "v"),
        ],
    )
    assert r.exit_code == 0, r.output


def test_import_refuses_non_empty(tmp_path: Path):
    r = runner.invoke(app, ["import", str(FIX / "chatgpt"), "--out", str(SAMPLE_VAULT)])
    assert r.exit_code == 2 and "--force" in r.output


def test_lists_and_version():
    assert "chatgpt" in runner.invoke(app, ["importers"]).output
    assert "claude-code" in runner.invoke(app, ["exporters"]).output
    assert runner.invoke(app, ["--version"]).output.startswith("memory-passport")


def test_unknown_names():
    assert runner.invoke(app, ["export", str(SAMPLE_VAULT), "--to", "nope"]).exit_code == 2
    assert (
        runner.invoke(
            app, ["import", str(FIX / "chatgpt"), "--from", "nope", "--out", "/tmp/x-nope"]
        ).exit_code
        == 2
    )
