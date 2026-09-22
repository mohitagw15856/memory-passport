from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from memory_passport.cli import app
from memory_passport.validate import validate_vault
from tests.conftest import MINIMAL_PROFILE, SAMPLE_VAULT, write

runner = CliRunner()


def codes(root: Path) -> list[str]:
    return sorted(i.code for i in validate_vault(root).issues)


def test_sample_vault_is_clean():
    report = validate_vault(SAMPLE_VAULT)
    assert report.issues == []
    assert report.file_count == 5
    assert report.fact_count > 10


def test_minimal_vault_ok(vault: Path):
    report = validate_vault(vault)
    assert report.ok(strict=True), report.issues


def test_missing_manifest_and_profile_warn(tmp_path: Path):
    write(tmp_path, "topics/tea.md", MINIMAL_PROFILE.replace("kind: profile", "kind: topic"))
    assert codes(tmp_path) == ["missing-manifest", "missing-profile"]
    assert validate_vault(tmp_path).ok()
    assert not validate_vault(tmp_path).ok(strict=True)


def test_schema_errors(vault: Path):
    write(vault, "profile.md", MINIMAL_PROFILE.replace("sources: [manual]\n", ""))
    assert "schema" in codes(vault)
    write(vault, "profile.md", MINIMAL_PROFILE.replace("sources: [manual]", "sources: [Chat GPT]"))
    assert "schema" in codes(vault)
    write(
        vault,
        "profile.md",
        MINIMAL_PROFILE.replace("kind: profile\n", "kind: profile\nextra: field\n"),
    )
    assert "bad-frontmatter" in codes(vault) or "schema" in codes(vault)


def test_bare_yaml_date_rejected(vault: Path):
    write(
        vault, "profile.md", MINIMAL_PROFILE.replace('updated: "2026-01-01"', "updated: 2026-01-01")
    )
    assert "schema" in codes(vault)


def test_kind_mismatch_and_bad_slug(vault: Path):
    write(vault, "people/Bad Name.md", MINIMAL_PROFILE)
    c = codes(vault)
    assert "kind-mismatch" in c and "bad-slug" in c


def test_untagged_and_no_facts(vault: Path):
    write(
        vault,
        "profile.md",
        MINIMAL_PROFILE.replace("- [stated] Lives in Leeds.", "- Lives in Leeds."),
    )
    c = codes(vault)
    assert "untagged-fact" in c and "no-facts" in c


def test_excluded_categories(vault: Path):
    write(vault, "profile.md", MINIMAL_PROFILE + "- [stated] Card 4111 1111 1111 1111.\n")
    assert "excluded:card-number" in codes(vault)
    write(vault, "profile.md", MINIMAL_PROFILE + "- [stated] Takes 20 mg of sertraline.\n")
    assert "excluded:health" in codes(vault)
    write(vault, "passport.yaml", 'spec_version: "0.1"\nallow_health: true\n')
    assert "excluded:health" not in codes(vault)


def test_spec_version_mismatch(vault: Path):
    write(vault, "passport.yaml", 'spec_version: "2.0"\n')
    assert "spec-version" in codes(vault)


def test_duplicate_names_warn(vault: Path):
    person = MINIMAL_PROFILE.replace("kind: profile", "kind: person")
    write(vault, "people/a.md", person)
    write(vault, "people/b.md", person)
    assert "duplicate-name" in codes(vault)


def test_unexpected_paths_warn(vault: Path):
    write(vault, "notes.txt", "hi")
    write(vault, "people/photo.png", "x")
    assert codes(vault).count("unexpected-path") == 2


def test_cli_validate(vault: Path):
    result = runner.invoke(app, ["validate", str(vault)])
    assert result.exit_code == 0, result.output
    assert result.output.startswith("OK")
    write(vault, "profile.md", "no frontmatter")
    result = runner.invoke(app, ["validate", str(vault), "--json"])
    assert result.exit_code == 1
    assert '"bad-frontmatter"' in result.output
