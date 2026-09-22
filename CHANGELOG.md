# Changelog

## 0.2.1 — 2026-09-22

- Fix: `passport export --budget` was documented but missing from the CLI in 0.2.0.

## 0.2.0 — 2026-09-22

- `passport show`, `passport add`, `passport forget`: use the vault day to day, not just for migration.
- `passport-mcp`: an MCP server (`pip install "memory-passport[mcp]"`) exposing `list_subjects`, `read_memory`, `remember`, `forget`.
- `--to prompt` exporter with `--budget`, a `<user_memory>` block for any model or agent.
- Gemini and Copilot importers from pasted text (`TextListImporter` base for others).
- Redaction instead of dropping for card, bank, ID and secret spans; health is still dropped.
- Semantic dedupe: common rewordings ("based in" / "lives in") collapse to one fact in import, merge and diff.
- `passport validate --stale DAYS` warns about old observed/inferred facts; stated facts never go stale.
- `passport inspect` reports what an export contains, for bug reports when a product changes its format.
- Browser playground at mohitagw15856.github.io/memory-passport (Pyodide; nothing uploaded).
- Release workflow with PyPI trusted publishing on `v*` tags.

## 0.1.0 — 2026-09-22

- Spec 0.1, JSON Schemas, validator, ChatGPT/Claude/markdown importers, five exporters, merge and diff.
