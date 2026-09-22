from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_VAULT = ROOT / "examples" / "sample-vault"


def write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


MINIMAL_PROFILE = """---
name: Test User
description: A minimal profile.
sources: [manual]
updated: "2026-01-01"
kind: profile
---

- [stated] Lives in Leeds.
"""


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """A minimal valid vault."""
    write(tmp_path, "passport.yaml", 'spec_version: "0.1"\n')
    write(tmp_path, "profile.md", MINIMAL_PROFILE)
    return tmp_path
