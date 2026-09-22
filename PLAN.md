# memory-passport — plan

Portable AI-assistant memory: one plain-text format any product can export to and import from, plus converters.

## 1. Schema

### Vault layout

```
vault/
  profile.md              # who the user is (role, location, languages, timezone)
  preferences.md          # how they like things done (tone, formats, tools, workflows)
  people/<slug>.md        # one file per person (partner, colleague, client)
  topics/<slug>.md        # one file per domain of interest or expertise
  areas/<slug>.md         # one file per ongoing project or responsibility
  passport.yaml           # vault manifest: spec_version, created, exported_by
```

Slugs are lower-case kebab-case ASCII. `profile.md` and `preferences.md` are singletons; the three folders hold zero or more files.

### Frontmatter (YAML)

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | Human-readable subject name |
| `description` | string | yes | One line, used for recall ranking |
| `sources` | list of strings | yes | Products this file draws from, e.g. `chatgpt`, `claude`, `claude-code`, `cursor`, `manual` |
| `aliases` | list of strings | no | Other names for the subject |
| `updated` | ISO 8601 date | yes | Last time any fact line changed |
| `kind` | enum | yes | `profile`, `preferences`, `person`, `topic`, `area` — derived from path, but stored so a file is self-describing when moved |

A JSON Schema (draft 2020-12) in `spec/frontmatter.schema.json` is the normative definition; SPEC.md prose explains it.

### Body

- Markdown. Optional `##` sections for grouping; sections are free-form and not part of the spec.
- Every fact is one bullet line: `- [tag] fact text` where tag is `stated`, `observed`, or `inferred`.
  - `[stated]` — the user said it explicitly.
  - `[observed]` — the product saw it happen (files edited, timezone of activity, tools used).
  - `[inferred]` — the product guessed it from patterns. Least trusted; importers should default here when the source product does not distinguish.
- Optional trailing metadata on a fact line: `<!-- src: chatgpt, 2025-11-03 -->` (kept as an HTML comment so it survives any markdown renderer and can be stripped for paste-export).
- Lines that are not fact lines (headings, blank, prose) are allowed but the validator warns if a bullet lacks a tag.

### Exclusions

The spec forbids by default, and the validator rejects: government ID numbers, payment card / bank account numbers, passwords and API keys, and health diagnoses / medications. Detection is regex plus a small keyword list; health can be opted in per vault via `passport.yaml: allow_health: true`. Rationale in SPEC.md: a passport is designed to be pasted into many products, so it is the worst place to keep anything you would not want a third party to hold; the format should make the safe thing the default.

## 2. Converter architecture

```
memory_passport/
  model.py        # Vault, MemoryFile, Fact dataclasses; parse/serialise
  schema.py       # loads JSON Schema; validate_frontmatter()
  validate.py     # structural + provenance + exclusion checks -> list[Issue]
  exclusions.py   # sensitive-data detectors
  merge.py        # three-way-ish merge with <<<<<<< a / ======= / >>>>>>> b markers on conflicting fact lines
  diff.py         # per-file, per-fact added/removed/changed
  importers/
    base.py       # class Importer(Protocol): name, detect(path) -> bool, load(path) -> Vault
    registry.py   # entry-point group `memory_passport.importers` + built-ins
    chatgpt.py
    claude.py
    markdown.py
  exporters/
    base.py       # class Exporter(Protocol): name, render(vault) -> str | Path
    registry.py
    chatgpt.py    # paste-ready block for Custom Instructions / "remember this"
    claude.py     # paste-ready block for Claude project instructions / user preferences
    claude_code.py# writes CLAUDE.md-style + memory/*.md
    cursor.py     # .cursor/rules/user.mdc
    markdown.py   # identity export
  cli.py          # Typer: validate, import, export, merge, diff, list-importers
```

Importers are pluggable two ways: register in `registry.py`, or expose a `memory_passport.importers` entry point in any third-party package. `passport import --from <name>` looks up the registry by name.

### Real export formats (verified before coding; to be re-checked with web search at implementation time)

**ChatGPT** — the data export zip contains `conversations.json`, `user.json`, `message_feedback.json`, `shared_conversations.json`, `chat.html`. There is no memory file. Memories are recoverable from `conversations.json`: when ChatGPT saves a memory it emits an assistant message with `recipient: "bio"` whose `content.parts[0]` is the memory sentence. The importer will:
1. Walk every conversation's `mapping`, collect messages where `author.role == "assistant"` and `recipient == "bio"`.
2. Also accept a plain-text file pasted from Settings → Personalisation → Manage memories (one memory per line), because many users will find that easier.
3. Default tag `[stated]` for bio entries phrased "User said/prefers", `[inferred]` otherwise; heuristic and documented.
4. Route each memory to a file by simple classifier (name mentions → people/, "working on/project" → areas/, "prefers/likes" → preferences.md, else profile.md). Anything unrouted lands in `profile.md` under `## Unsorted`.

**Claude** — two real inputs:
1. claude.ai data export zip: `conversations.json` (list of conversations with `chat_messages[].text`, `sender`), `projects.json`, `users.json`. No memory file. The importer extracts `projects.json` prompt templates as `[stated]` preferences and offers `--from claude --memory-text <file>` for the memory summary pasted from Settings → Memory.
2. Claude Code auto-memory dir (`~/.claude/projects/<slug>/memory/*.md`, frontmatter `name`, `description`, `metadata.type` in `user|feedback|project|reference`) plus any `CLAUDE.md`. This is a near-native mapping: `user` → profile/preferences, `project` → areas/, `reference` → topics/, `feedback` → preferences. Tag `[stated]`.

**markdown** — any folder of `.md` files; frontmatter fields present are kept, missing ones synthesised; untagged bullets become `[inferred]` with a warning.

### Exporters

Each exporter renders the vault into what the target accepts, noting the target's limits in the README comparison table (e.g. ChatGPT Custom Instructions ≈ 1,500 chars each box, no provenance; Claude user preferences free text; Cursor rules files; Hermes/custom bots = the markdown vault itself).

## 3. MVP cut

Ship in this order, stopping where you asked:

1. **Spec + validator** — SPEC.md, JSON Schema, `model.py`, `validate.py`, `exclusions.py`, `passport validate`, tests, examples/sample-vault. **→ Stop and show you the spec.**
2. **First importer: ChatGPT** — zip + pasted-memories text, fixture export in `tests/fixtures/chatgpt/`. **→ Stop after it works.**
3. Claude importer (export zip + Claude Code memory dir), markdown importer.
4. Exporters (markdown, claude, claude-code, chatgpt, cursor).
5. `merge` and `diff`.
6. README quickstart + comparison table, CONTRIBUTING.md, docs/ADR-001.md, CI (ruff + pytest on 3.11–3.13), LICENSE.

Out of scope for MVP: Gemini/Cursor importers (no stable export), semantic dedupe on merge (exact-line and normalised-whitespace only), encryption.

## Tooling

- Python ≥ 3.11, `uv` for env, `pyproject.toml` (hatchling), deps: `typer`, `pyyaml`, `jsonschema`, `python-frontmatter`. Dev: `pytest`, `ruff`.
- British English in all prose; MIT, author mohitagw15856.
