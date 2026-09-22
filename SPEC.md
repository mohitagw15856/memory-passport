# memory-passport specification

**Version 0.1 — draft.** Normative words (MUST, SHOULD, MAY) follow RFC 2119.

## 1. Purpose

Every AI assistant keeps its own memory of you, and none of it moves. A *passport* is a small folder of plain-text files that any product can write out and any product can read back in. It is designed to be:

- **Readable by a person** in any text editor, without tooling.
- **Readable by a model** by pasting a file straight into a prompt.
- **Diffable and mergeable** with ordinary text tools and version control.
- **Honest about provenance**: every fact says whether you said it, the product saw it, or the product guessed it.
- **Safe by default**: the categories most dangerous to spread across products are excluded unless you opt in.

Two normative JSON Schema documents accompany this text: `spec/frontmatter.schema.json` and `spec/manifest.schema.json`. Where prose and schema disagree, the schema wins for structure and this document wins for meaning.

## 2. Terminology

| Term | Meaning |
|---|---|
| **Vault** | A directory laid out as in §3. The unit of import, export, merge and diff. |
| **Memory file** | One markdown file in the vault describing one *subject*. |
| **Subject** | The person, topic, project or the user themselves that a file is about. |
| **Fact line** | A bullet line carrying one provenance-tagged statement (§5). |
| **Provenance tag** | `[stated]`, `[observed]` or `[inferred]` (§6). |
| **Source** | A product identifier such as `chatgpt` or `claude-code` (§4.3). |
| **Manifest** | `passport.yaml` at the vault root (§7). |

## 3. Vault layout

```
<vault>/
  passport.yaml          manifest (SHOULD be present)
  profile.md             the user: role, location, hours, languages (SHOULD be present)
  preferences.md         how the user wants assistants to behave (MAY be present)
  people/<slug>.md       one file per person the user has talked about
  topics/<slug>.md       one file per domain of interest or expertise
  areas/<slug>.md        one file per ongoing project or responsibility
```

Rules:

- `<slug>` MUST match `^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$` (lower-case kebab-case ASCII). Tools SHOULD derive it from the subject's name.
- Readers MUST ignore any other paths (a `README.md`, a `.git` directory). Validators SHOULD warn about them.
- Sub-directories inside `people/`, `topics/` and `areas/` are not part of the spec and MUST be ignored.
- Files MUST be UTF-8 with `\n` line endings. Writers MUST NOT emit a byte-order mark.

The five *kinds* — `profile`, `preferences`, `person`, `topic`, `area` — are the whole taxonomy. A subject that fits none of them goes in `profile.md` under an `## Unsorted` heading rather than in a new folder, so that every reader agrees on where to look.

## 4. Memory file format

A memory file is YAML frontmatter followed by a markdown body.

```markdown
---
name: Priya Nair
description: Sam's manager; sets quarterly priorities and reviews design docs.
sources: [chatgpt, claude]
aliases: [Priya, PN]
updated: "2026-06-11"
kind: person
---

## Working style

- [stated] Prefers decisions written up as one-page ADRs before a meeting.
- [inferred] Likely based in the Edinburgh office, given meeting times. <!-- src: chatgpt, 2026-05-02 -->
```

### 4.1 Frontmatter

The file MUST begin with `---` on the first line, a YAML mapping, and a closing `---` line. The mapping MUST validate against `spec/frontmatter.schema.json`:

| Field | Type | Required | Rule |
|---|---|---|---|
| `name` | string | yes | Human-readable subject name. 1–200 characters. |
| `description` | string | yes | One line. Assistants use it to decide whether to load the file, so it SHOULD say what is in the file, not restate the name. 1–500 characters. |
| `sources` | list of strings | yes | Product identifiers (§4.3) whose memory contributed. At least one. Unique. |
| `aliases` | list of strings | no | Other names for the subject. Unique. |
| `updated` | string | yes | `YYYY-MM-DD`, the day any fact line last changed. MUST be quoted so YAML does not parse it as a date object. |
| `kind` | enum | yes | One of `profile`, `preferences`, `person`, `topic`, `area`. MUST agree with the file's path (§3). |

No other keys are permitted (`additionalProperties: false`). This is deliberate: an open frontmatter would let each product smuggle its own fields back in, and the point of the format is that there is nothing product-specific to lose.

`kind` is redundant with the path. It is required anyway so that a single file pasted into a chat, or copied out of the tree, still says what it is.

### 4.2 Body

The body is CommonMark. Only two constructs carry meaning:

1. **Fact lines** (§5). These are the data.
2. **`##` headings**. These group fact lines for human readers. Headings are free-form and MUST NOT be relied on by readers; a reader that flattens every fact into one list has lost nothing the spec guarantees.

Everything else (prose, `#` titles, links, tables) is allowed, is preserved by conforming tools where practical, and carries no meaning.

### 4.3 Source identifiers

A source is a lower-case kebab-case token identifying the product a fact came from. Known values:

`chatgpt`, `claude`, `claude-code`, `cursor`, `gemini`, `copilot`, `hermes`, `manual`

`manual` means a person typed it. Tools MUST accept unknown tokens that match the pattern, so new products need no spec change.

## 5. Fact lines

A fact line is a markdown bullet whose first token is a provenance tag:

```
- [stated] <text> [<!-- src: <source>[, <YYYY-MM-DD>] -->]
```

Precisely, a line is a fact line if it matches:

```
^\s*[-*]\s+\[(stated|observed|inferred)\]\s+(.*?)(\s*<!--\s*src:\s*([a-z0-9-]+)(\s*,\s*(\d{4}-\d{2}-\d{2}))?\s*-->)?\s*$
```

- The text MUST be non-empty. One line, one fact. A fact that needs two sentences is still one line.
- The optional trailing HTML comment records per-fact source and date. It is a comment so that every markdown renderer hides it and every paste-export can strip it with one regex.
- A bullet line without a tag is **not** a fact. Validators MUST warn (`untagged-fact`); importers MUST NOT silently promote it. The `markdown` importer tags such lines `[inferred]` and reports that it did so.
- Nested bullets are permitted but are still independent facts; indentation carries no meaning.

Two facts are *the same fact* when their text is equal after collapsing whitespace, case-folding and stripping a trailing full stop. This *fact key* is what merge and diff compare. Tags and source comments are not part of the key.

## 6. Provenance tags

| Tag | Meaning | Trust |
|---|---|---|
| `[stated]` | The user said it, in so many words. | Highest. A reader MAY treat it as true until the user contradicts it. |
| `[observed]` | The product saw it happen: files edited, the timezone of activity, a tool being used. Not asserted by the user. | Medium. True of the past; may no longer hold. |
| `[inferred]` | The product guessed it from patterns. | Lowest. A reader SHOULD hedge when acting on it and SHOULD prefer to confirm. |

Importers MUST choose a tag for every fact. When the source product does not record provenance (most do not), the importer MUST default to `[inferred]` unless it has a documented reason to do better. The ChatGPT importer, for example, defaults to `[stated]` because ChatGPT's `bio` tool is only invoked to record what the user shared in conversation, and downgrades to `[inferred]` any sentence containing a hedge ("seems", "likely", "probably"), since that is the model recording a guess. Each importer's rule is documented in its module docstring.

When the same fact appears with different tags, merge keeps the highest-trust tag (`stated` > `observed` > `inferred`).

## 7. Excluded categories

A passport is designed to be pasted into many products, some of which will retain it in their own memory, and it is therefore the worst possible place to keep anything you would not hand to a third party. The spec makes the safe outcome the default rather than relying on every importer to be careful.

The following MUST NOT appear in a fact line. The validator reports them as errors under `excluded:<category>` and conforming importers MUST drop or redact any fact that trips a detector, reporting the count.

| Category | Examples | Why it is excluded rather than merely discouraged |
|---|---|---|
| `card-number` | Payment card numbers (Luhn-valid 13–19 digits) | Enables fraud directly; no assistant needs it to be helpful. |
| `bank-account` | IBANs, UK sort code + account pairs | As above. |
| `government-id` | Social security, national insurance, passport, driving licence, NHS and similar numbers | Identity theft; often unchangeable once leaked. |
| `secret` | API keys, tokens, private keys, passwords | Credential exposure across every product the passport touches. |
| `health` | Diagnoses, medications, conditions, treatment | Special-category data under GDPR and most other regimes. Products vary enormously in how they protect it. **Opt-in only**: set `allow_health: true` in the manifest. |

Health is the only opt-in category because it is the only one with a legitimate everyday use (an assistant that knows about your dietary restriction or accessibility need is genuinely more helpful). The others have no such use.

Detection is heuristic. It uses check digits where they exist (Luhn, IBAN mod-97), format patterns for the rest, and a keyword list for health. It will miss things and it will occasionally fire on innocent text. A false positive is a nuisance you can reword; a false negative is why the spec also asks people to read what they export. The detectors are in `memory_passport/exclusions.py` and every rule has a test.

Things the spec deliberately does **not** exclude: names of other people, employers, locations, opinions, politics, religion, relationships. These are the substance of a useful memory, and their sensitivity depends entirely on the person. They are the user's call, and the `[stated]` tag plus per-file layout make it easy to delete a whole subject with one `rm`.

## 8. Manifest

`passport.yaml` at the vault root MUST validate against `spec/manifest.schema.json`:

```yaml
spec_version: "0.1"          # required; major version must match the reader's
created: "2026-09-22"        # optional
exported_by: memory-passport 0.1.0   # optional, free text
allow_health: false          # optional, default false (§7)
```

A vault without a manifest is read as spec 0.1 with defaults, and the validator warns.

## 9. Validation

A conforming validator distinguishes **errors** (the vault violates a MUST; readers may misinterpret it) from **warnings** (the vault is readable but something is off). `passport validate` exits non-zero on errors, or on warnings too with `--strict`.

| Code | Level | Meaning |
|---|---|---|
| `bad-frontmatter` | error | No frontmatter, or it is not a YAML mapping. |
| `schema` | error | Frontmatter fails the JSON Schema. |
| `kind-mismatch` | error | `kind` disagrees with the path. |
| `bad-slug` | error | Filename in a folder is not kebab-case. |
| `not-utf8` | error | File is not UTF-8. |
| `empty-fact` | error | A tagged line has no text. |
| `excluded:<category>` | error | A fact line trips an exclusion detector (§7). |
| `bad-manifest` | error | Manifest is not valid YAML or fails its schema. |
| `conflict` | error | An unresolved merge conflict marker (§10). |
| `spec-version` | error | Manifest major version differs from the validator's. |
| `untagged-fact` | warning | A bullet with no provenance tag. |
| `no-facts` | warning | A memory file with no fact lines. |
| `missing-profile` | warning | No `profile.md`. |
| `missing-manifest` | warning | No `passport.yaml`. |
| `unexpected-path` | warning | A path the spec does not define. |
| `duplicate-name` | warning | Two files of the same kind share a name. |
| `future-date` | warning | `updated` is after today. |

## 10. Merge and diff semantics

*Normative for tools that claim to merge or diff passports; the reference implementation is in `memory_passport/merge.py` and `diff.py`.*

- Files are matched by path. Within a file, facts are matched by fact key (§5).
- **Diff** reports, per file: facts added, facts removed, facts whose tag or source changed, and frontmatter fields that changed.
- **Merge** of vault A and vault B into a new vault:
  - A file in only one vault is copied.
  - A fact in only one vault is kept.
  - The same fact in both keeps the higher-trust tag and the union of source comments.
  - Frontmatter: `sources` and `aliases` are unioned; `updated` takes the later date; `name` and `description` differing is a **conflict**.
  - Two facts that are not the same fact but that a tool judges to be contradictory (the reference implementation uses a small negation heuristic and otherwise leaves this to the user) are written out with conflict markers, never silently resolved:

    ```
    <<<<<<< a
    - [stated] Works four days a week.
    =======
    - [stated] Works five days a week.
    >>>>>>> b
    ```

  - A merged vault containing conflict markers MUST fail validation (error `conflict` on each marker line) until a person resolves it.

## 11. Versioning

`spec_version` is `MAJOR.MINOR`. Minor versions only add optional fields or relax rules; a 0.1 reader can read a 0.2 vault. Major versions may break. This document is 0.1 and will move to 1.0 once two independent importers have been written against it without needing a change.

## 12. What the format cannot express

Being honest about the ceiling:

- **No confidence scores.** Three tags, not a probability. Finer grades were considered and rejected because no product exports them and people cannot calibrate them.
- **No relationships between subjects** beyond a mention in text. `people/priya-nair.md` does not link to `areas/ledger-rewrite.md`. Wiki-links (`[[ledger-rewrite]]`) are permitted in fact text as ordinary markdown and readers MAY resolve them, but the spec does not require it.
- **No history.** A vault is the current state. Put it in git if you want history.
- **No structured values.** A birthday is a fact line, not a `birthday:` field. This is the cost of the "one file per subject, five kinds, nothing else" rule and it is paid on purpose.
