from __future__ import annotations

import zipfile
from pathlib import Path

from typer.testing import CliRunner

from memory_passport.cli import app
from memory_passport.inspect_export import inspect_path
from tests.conftest import ROOT

FIX = ROOT / "tests" / "fixtures"
runner = CliRunner()


def test_inspect_chatgpt_and_claude(tmp_path: Path):
    lines = inspect_path(FIX / "chatgpt")
    text = "\n".join(lines)
    assert "ChatGPT export, 2 conversation(s)" in text
    assert "saved memories (assistant -> bio): 2" in text
    assert "tools:      bio=2" in text
    zp = tmp_path / "c.zip"
    with zipfile.ZipFile(zp, "w") as z:
        for n in ("conversations.json", "projects.json"):
            z.write(FIX / "claude-export" / n, n)
    text = "\n".join(inspect_path(zp))
    assert (
        "claude.ai export, 1 conversation(s)" in text
        and "2 project(s), 1 with instructions" in text
    )
    r = runner.invoke(app, ["inspect", str(FIX / "claude-code")])
    assert r.exit_code == 0 and "Claude Code memory index" in r.output


def test_inspect_reports_missing_bio(tmp_path: Path):
    (tmp_path / "conversations.json").write_text(
        '[{"mapping": {"a": {"message": {"author": {"role": "user"}, "recipient": "all", '
        '"content": {"parts": ["hi"]}}}}}]'
    )
    text = "\n".join(inspect_path(tmp_path / "conversations.json"))
    assert "no bio messages found" in text
