from __future__ import annotations

import shutil
from pathlib import Path

from memory_passport import mcp_server
from tests.conftest import SAMPLE_VAULT


def test_mcp_tool_functions(tmp_path: Path, monkeypatch):
    v = tmp_path / "v"
    shutil.copytree(SAMPLE_VAULT, v)
    monkeypatch.setenv("PASSPORT_VAULT", str(v))
    assert (
        "## Basics" in mcp_server.read_memory_text()
        or "Product engineer" in mcp_server.read_memory_text()
    )
    assert "priya-nair" in mcp_server.read_memory_text("ADRs")
    assert mcp_server.read_memory_text("zzz-nothing") == "no matching facts"
    out = mcp_server.remember_text("User's sister is called Ada Okafor.")
    assert out.startswith("saved to people/ada-okafor.md (created)")
    assert "already known" in mcp_server.remember_text("User's sister is called Ada Okafor")
    assert mcp_server.remember_text("x", tag="maybe").startswith("tag must be")
    assert "refused" in mcp_server.remember_text("Diagnosed with ADHD.", subject="profile")
    assert mcp_server.forget_text("User's sister is called Ada Okafor.").startswith(
        "removed people/ada-okafor.md"
    )
    assert mcp_server.forget_text("nothing here") == "nothing matched"
