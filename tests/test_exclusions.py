from __future__ import annotations

import pytest

from memory_passport.exclusions import scan


def cats(text: str, **kw) -> set[str]:
    return {h.category for h in scan(text, **kw)}


@pytest.mark.parametrize(
    "text",
    [
        "Card number 4111 1111 1111 1111 expires next year.",
        "Visa 4242-4242-4242-4242",
        "Amex 378282246310005",
    ],
)
def test_card_numbers(text):
    assert "card-number" in cats(text)


def test_luhn_invalid_number_is_not_a_card():
    assert "card-number" not in cats("Order reference 4111 1111 1111 1112")


def test_iban_and_uk_account():
    assert "bank-account" in cats("IBAN GB82 WEST 1234 5698 7654 32")
    assert "bank-account" in cats("sort code 40-47-84 account 12345678")
    assert "bank-account" not in cats("IBAN GB00 WEST 1234 5698 7654 32")


def test_government_ids():
    assert "government-id" in cats("SSN 123-45-6789")
    assert "government-id" in cats("NI number AB 12 34 56 C")
    assert "government-id" in cats("Passport number: 123456789")
    assert "government-id" not in cats("Renewed their passport last spring.")


def test_secrets():
    assert "secret" in cats("key sk-abcdefghijklmnopqrstuvwxyz1234")
    assert "secret" in cats("AKIAIOSFODNN7EXAMPLE")
    assert "secret" in cats("The wifi password is hunter2")
    assert "secret" not in cats("Uses a password manager.")


def test_health_opt_in():
    text = "Was diagnosed with ADHD in 2020."
    assert "health" in cats(text)
    assert cats(text, allow_health=True) == set()


def test_clean_text():
    assert scan("Product engineer in Manchester who likes tea.") == []
    assert scan("Phone 0161 496 0000, met on 2026-01-02.") == []


def test_redact():
    from memory_passport.exclusions import redact

    t, hits = redact(
        "Card 4111 1111 1111 1111 and IBAN GB82 WEST 1234 5698 7654 32, SSN 123-45-6789."
    )
    assert t == (
        "Card [redacted card-number] and IBAN [redacted bank-account], "
        "SSN [redacted government-id]."
    )
    assert hits == []
    t, hits = redact(
        "Passport number: 123456789; wifi password is hunter2; "
        "key sk-abcdefghijklmnopqrstuvwxyz1234"
    )
    assert (
        "[redacted government-id]" in t
        and "password is [redacted secret]" in t
        and "[redacted secret]" in t
    )
    assert hits == []
    t, hits = redact("Diagnosed with asthma; card 4242 4242 4242 4242")
    assert "[redacted card-number]" in t and [h.category for h in hits] == ["health"]
