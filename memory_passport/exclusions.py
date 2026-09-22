"""Detectors for categories the spec excludes from a passport by default.

Detection is deliberately conservative and heuristic: it exists to stop the
obvious cases (a card number pasted into a fact line) rather than to be a
complete data-loss-prevention system. See SPEC.md §7 for the rationale.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Category = Literal["card-number", "bank-account", "government-id", "secret", "health"]


@dataclass(frozen=True)
class Hit:
    category: Category
    detail: str


def _luhn_ok(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _iban_ok(s: str) -> bool:
    s = s.upper()
    rearranged = s[4:] + s[:4]
    numeric = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)
    return int(numeric) % 97 == 1


_CARD_RE = re.compile(r"(?<![\d-])(?:\d[ -]?){12,18}\d(?![\d-])")
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}[ ]?[A-Z0-9]{1,4}\b")
_UK_SORT_ACCT_RE = re.compile(r"\b\d{2}-\d{2}-\d{2}\b[^\n]{0,20}\b\d{8}\b")
_US_SSN_RE = re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")
_UK_NINO_RE = re.compile(
    r"\b(?!BG|GB|NK|KN|TN|NT|ZZ)[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z]\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b"
)
_ID_KEYWORD_RE = re.compile(
    r"\b(passport|national insurance|social security|driving licence|driver'?s licen[cs]e|"
    r"nhs|aadhaar|pan card|tax id|ssn|nino)\b\s*(number|no\.?|#|:)?\s*(is\s+)?[:#]?\s*"
    r"((?=[A-Z -]*\d)[A-Z0-9][A-Z0-9 -]{5,})",
    re.IGNORECASE,
)
_SECRET_RE = re.compile(
    r"(sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|"
    r"xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}|-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)
_PASSWORD_RE = re.compile(
    r"\b(password|passcode|pin)\b\s*(is|:|=)\s*(?!\[redacted)\S+", re.IGNORECASE
)

_HEALTH_CONDITIONS = (
    "adhd|autism|autistic|anxiety disorder|depression|depressive|bipolar|schizophreni|ptsd|ocd|"
    "eating disorder|anorexi|bulimi|diabet|cancer|tumour|tumor|hiv|aids|hepatitis|epilep|"
    "asthma|crohn|coeliac|celiac|arthritis|fibromyalgia|dementia|alzheimer|parkinson|"
    "multiple sclerosis|chronic fatigue|long covid|hypertension|heart disease|stroke|"
    "pregnan|miscarriage|infertil|erectile|std|sti|herpes|chlamydia"
)
_HEALTH_RE = re.compile(
    r"\b(diagnos(?:ed|is)|prescri(?:bed|ption)|medication|antidepressant|therapist|psychiatrist|"
    r"\d+\s?mg\b|" + _HEALTH_CONDITIONS + r")",
    re.IGNORECASE,
)


REDACTABLE: tuple[Category, ...] = ("card-number", "bank-account", "government-id", "secret")


def redact(text: str, *, allow_health: bool = False) -> tuple[str, list[Hit]]:
    """Replace every redactable span with ``[redacted <category>]``.

    Returns the new text and the hits that could *not* be redacted (currently only
    ``health``, which is a topic rather than a token and so must be dropped instead).
    """
    out = text
    for m in list(_CARD_RE.finditer(out))[::-1]:
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            out = out[: m.start()] + "[redacted card-number]" + out[m.end() :]
    for m in list(_IBAN_RE.finditer(out))[::-1]:
        compact = m.group().replace(" ", "")
        if 15 <= len(compact) <= 34 and _iban_ok(compact):
            out = out[: m.start()] + "[redacted bank-account]" + out[m.end() :]
    out = _UK_SORT_ACCT_RE.sub("[redacted bank-account]", out)
    out = _US_SSN_RE.sub("[redacted government-id]", out)
    out = _UK_NINO_RE.sub("[redacted government-id]", out)
    out = _ID_KEYWORD_RE.sub(
        lambda m: m.group(0)[: m.start(4) - m.start(0)] + "[redacted government-id]", out
    )
    out = _SECRET_RE.sub("[redacted secret]", out)
    out = _PASSWORD_RE.sub(lambda m: f"{m.group(1)} {m.group(2)} [redacted secret]", out)
    return out, scan(out, allow_health=allow_health)


def scan(text: str, *, allow_health: bool = False) -> list[Hit]:
    """Return every exclusion hit in ``text``. Empty list means clean."""
    hits: list[Hit] = []

    for m in _CARD_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            hits.append(Hit("card-number", f"Luhn-valid {len(digits)}-digit number"))

    for m in _IBAN_RE.finditer(text):
        compact = m.group().replace(" ", "")
        if 15 <= len(compact) <= 34 and _iban_ok(compact):
            hits.append(Hit("bank-account", f"IBAN starting {compact[:4]}"))
    if _UK_SORT_ACCT_RE.search(text):
        hits.append(Hit("bank-account", "UK sort code with account number"))

    if _US_SSN_RE.search(text):
        hits.append(Hit("government-id", "US social security number pattern"))
    if _UK_NINO_RE.search(text):
        hits.append(Hit("government-id", "UK national insurance number pattern"))
    for m in _ID_KEYWORD_RE.finditer(text):
        hits.append(Hit("government-id", f"'{m.group(1)}' followed by an identifier"))

    if _SECRET_RE.search(text):
        hits.append(Hit("secret", "API key or private key pattern"))
    if m := _PASSWORD_RE.search(text):
        hits.append(Hit("secret", f"'{m.group(1)}' with a value"))

    if not allow_health and (m := _HEALTH_RE.search(text)):
        hits.append(Hit("health", f"health term '{m.group(1)}'"))

    return hits
