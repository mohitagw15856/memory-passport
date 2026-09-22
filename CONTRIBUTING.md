# Contributing

Thanks for helping make memory portable. The most useful contribution is an importer or exporter for a product we do not cover yet, and this guide is mostly about that.

## Setup

```bash
git clone https://github.com/mohitagw15856/memory-passport
cd memory-passport
uv sync --group dev
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
```

Python 3.11+. British English in prose and docstrings. Keep the CLI output terse.

## Adding an importer

An importer turns a product's export into a `Vault`. Two ways to ship one:

- **In this repo:** add `memory_passport/importers/<product>.py` and register it in `registry.py` and `pyproject.toml`.
- **In your own package:** expose an entry point in the `memory_passport.importers` group. `passport import --from <name>` will find it with no change here.

### 1. Find the real export format

Do not guess. Download an export from the product, open it, and put a **trimmed, fake-data** copy in `tests/fixtures/<product>/`. Every importer in this repo is written against a fixture that mirrors the real file layout. Note where memory actually lives; often it is not where you expect (ChatGPT's is inside `conversations.json`, addressed to a tool called `bio`).

### 2. Implement the class

```python
# memory_passport/importers/acme.py
from pathlib import Path

from memory_passport.importers.base import Importer, ImportOptions, ImportResult
from memory_passport.importers.builder import VaultBuilder
from memory_passport.importers.text import is_hedged, tidy
from memory_passport.model import Fact


class AcmeImporter(Importer):
    name = "acme"                      # used by --from and written into `sources`
    help = "Acme Assistant memory export (memories.json)"

    def detect(self, path: Path) -> bool:
        return path.name == "memories.json"

    def load(self, path: Path, options: ImportOptions) -> ImportResult:
        b = VaultBuilder(self.name, allow_health=options.allow_health, do_route=options.route)
        notes = []
        for entry in read_acme(path):          # your parsing
            text = tidy(entry["text"])
            tag = "inferred" if is_hedged(text) else "stated"   # document your rule!
            b.add(Fact(tag, text, date=entry.get("date")))
        notes.append(f"read {len(...)} memories")
        return ImportResult(vault=b.build(), notes=notes, dropped=b.dropped)
```

`VaultBuilder` does the boring parts: exclusion scanning (facts that trip a detector go to `dropped`, never into the vault), dedupe by fact key, routing to `people/`, `topics/`, `areas/` or `preferences.md` (pass `to=Route(...)` to override), and frontmatter generation.

### 3. Decide the provenance rule, and write it down

The spec says importers MUST default to `[inferred]` unless they have a documented reason to do better. Put the reason in the module docstring. "The product only stores what the user typed" is a reason. "It is probably fine" is not.

### 4. Register it

In-repo:

```python
# registry.py
from memory_passport.importers.acme import AcmeImporter
return [ChatGPTImporter, ClaudeImporter, MarkdownImporter, AcmeImporter]
```

```toml
# pyproject.toml
[project.entry-points."memory_passport.importers"]
acme = "memory_passport.importers.acme:AcmeImporter"
```

External package:

```toml
[project.entry-points."memory_passport.importers"]
acme = "passport_acme:AcmeImporter"
```

### 5. Test it

`tests/test_importers.py` shows the pattern. At minimum:

- `detect()` is true for the fixture and false for the other fixtures.
- The vault it produces passes `validate_vault()` with no errors.
- A fact that should be excluded (put a test card number in the fixture) ends up in `dropped`, not in the vault.
- Tags are what your documented rule says.

### 6. Update the README comparison table

Add a row for the product: what its memory can and cannot express, and how the export and import actually work for users.

## Adding an exporter

Same shape, smaller. Subclass `Exporter` in `memory_passport/exporters/`, return an `ExportResult` whose `files` map paths to content (use the single key `"-"` for "print to stdout"), and register it. Read `base.fact_sentence()` before writing: it is how inferred facts get hedged for products that have no provenance, and you should use it rather than dropping the distinction.

## Changing the spec

Open an issue first. SPEC.md is versioned; anything that would break a 0.1 reader is a major bump and needs an ADR in `docs/`.

## Pull requests

- One importer, exporter or fix per PR.
- CI runs ruff and pytest on 3.11, 3.12 and 3.13; it must be green.
- Commit messages in the imperative mood.
