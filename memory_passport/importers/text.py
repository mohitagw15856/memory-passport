"""Text helpers shared by importers: splitting pasted memory lists and prose into facts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

_DATE = r"(\d{4}-\d{2}-\d{2})"
# "1. [2025-05-02]. The user likes ice cream."   (ChatGPT model-set-context style)
# "[2025-05-02] - The user likes ice cream."     (Claude's recommended import format)
# "- The user likes ice cream."                  (a plain bullet)
# "The user likes ice cream."                    (a plain line)
_LINE_RE = re.compile(
    r"^\s*(?:\d+[.)]\s*)?(?:[-*•]\s*)?(?:\[" + _DATE + r"\]\.?\s*[-–—:]?\s*)?(?P<text>.+?)\s*$"
)
_HEDGE_RE = re.compile(
    r"\b(seems?|appears?|likely|probably|possibly|may|might|perhaps|presumably|suggest(?:s|ed)?)\b",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[\"'(])")


@dataclass
class Line:
    text: str
    date: date | None = None


def parse_memory_lines(text: str) -> list[Line]:
    """Split a pasted list of memories into one entry per non-empty line, dropping headings."""
    out: list[Line] = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#") or (s.startswith("**") and s.endswith("**")):
            continue
        m = _LINE_RE.match(s)
        if not m:
            continue
        d = m.group(1)
        body = m.group("text").strip()
        if not body or body in {"-", "•"}:
            continue
        out.append(Line(body, date.fromisoformat(d) if d else None))
    return out


def split_prose(text: str) -> list[str]:
    """Split prose into sentences, keeping bullets and headings out of it."""
    out: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        for raw in para.splitlines():
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            s = re.sub(r"^[-*•]\s+", "", s)
            s = re.sub(r"^\d+[.)]\s+", "", s)
            out.extend(p.strip() for p in _SENTENCE_RE.split(s) if p.strip())
    return out


def is_hedged(text: str) -> bool:
    return bool(_HEDGE_RE.search(text))


def tidy(text: str) -> str:
    """Normalise a memory sentence: single spaces, 'The user' -> 'User', trailing full stop."""
    s = " ".join(text.split())
    s = re.sub(r"^the user\b", "User", s, flags=re.IGNORECASE)
    s = re.sub(r"^user's\b", "User's", s, flags=re.IGNORECASE)
    s = re.sub(r"^user\b", "User", s, flags=re.IGNORECASE)
    s = s.strip(" -–—:")
    if s and s[-1] not in ".!?":
        s += "."
    return s
