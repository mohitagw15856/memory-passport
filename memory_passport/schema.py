"""Loading and applying the JSON Schemas that ship in ``spec/``."""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from pathlib import Path

from jsonschema import Draft202012Validator

_SPEC_DIR = Path(__file__).resolve().parent.parent / "spec"


@cache
def load_schema(name: str) -> dict:
    """Load ``spec/<name>.schema.json`` (installed copy first, repo checkout second)."""
    try:
        text = resources.files("memory_passport").joinpath(f"spec/{name}.schema.json").read_text()
    except (FileNotFoundError, TypeError, ModuleNotFoundError):
        text = (_SPEC_DIR / f"{name}.schema.json").read_text(encoding="utf-8")
    return json.loads(text)


def schema_errors(name: str, instance: object) -> list[str]:
    """Human-readable schema violations for ``instance`` against schema ``name``."""
    v = Draft202012Validator(load_schema(name))
    out = []
    for err in sorted(v.iter_errors(instance), key=lambda e: list(e.path)):
        loc = ".".join(str(p) for p in err.path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return out
