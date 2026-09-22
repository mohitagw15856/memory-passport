from __future__ import annotations

from datetime import date
from pathlib import PurePosixPath

import pytest

from memory_passport.model import (
    Fact,
    VaultError,
    expected_kind,
    parse_facts,
    parse_file,
    path_for,
    slugify,
    split_frontmatter,
    untagged_bullets,
)


def test_parse_fact_lines_with_and_without_metadata():
    body = (
        "## Heading\n"
        "- [stated] Likes tea.\n"
        "* [observed] Drinks it at 9am. <!-- src: claude-code, 2026-02-03 -->\n"
        "- [inferred] Probably British <!-- src: chatgpt -->\n"
        "- untagged bullet\n"
        "Plain prose line.\n"
    )
    facts = parse_facts(body)
    assert [f.tag for f in facts] == ["stated", "observed", "inferred"]
    assert facts[0].text == "Likes tea."
    assert facts[0].source is None
    assert facts[1].source == "claude-code" and facts[1].date == date(2026, 2, 3)
    assert facts[2].source == "chatgpt" and facts[2].date is None
    assert [f.line_no for f in facts] == [2, 3, 4]
    assert untagged_bullets(body) == [5]


def test_fact_render_round_trips():
    for line in (
        "- [stated] Likes tea.",
        "- [observed] Drinks it at 9am. <!-- src: claude-code, 2026-02-03 -->",
        "- [inferred] Probably British <!-- src: chatgpt -->",
    ):
        (fact,) = parse_facts(line)
        assert fact.render() == line


def test_fact_key_normalises():
    assert Fact("stated", "Likes  Tea.").key == Fact("inferred", "likes tea").key


def test_split_frontmatter_errors():
    with pytest.raises(VaultError, match="missing YAML frontmatter"):
        split_frontmatter("no frontmatter here")
    with pytest.raises(VaultError, match="mapping"):
        split_frontmatter("---\n- a list\n---\nbody")
    with pytest.raises(VaultError, match="invalid YAML"):
        split_frontmatter("---\nname: [unclosed\n---\nbody")


def test_parse_file_and_render_round_trip():
    text = (
        "---\nname: X\ndescription: Y\nsources:\n- manual\n"
        "updated: '2026-01-01'\nkind: topic\n---\n\n- [stated] A fact.\n"
    )
    mf = parse_file(PurePosixPath("topics/x.md"), text)
    assert mf.name == "X" and mf.kind == "topic" and len(mf.facts) == 1
    assert mf.render() == text


def test_expected_kind_and_path_for():
    assert expected_kind(PurePosixPath("profile.md")) == "profile"
    assert expected_kind(PurePosixPath("people/bob.md")) == "person"
    assert expected_kind(PurePosixPath("random.md")) is None
    assert expected_kind(PurePosixPath("people/nested/bob.md")) is None
    assert path_for("area", "ledger") == PurePosixPath("areas/ledger.md")
    assert path_for("preferences") == PurePosixPath("preferences.md")


def test_slugify():
    assert slugify("Priya  Nair!") == "priya-nair"
    assert slugify("   ") == "untitled"
