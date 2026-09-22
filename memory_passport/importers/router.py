"""Heuristic routing of a fact sentence to a vault file.

Products export memories as a flat list. This module decides, per sentence, whether it is
about a person, a topic, a project, a preference, or the user in general. It is a set of
keyword rules with no model behind it, so it is wrong sometimes; ``--no-route`` skips it
and puts everything in ``profile.md``, and moving a line between files by hand is cheap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from memory_passport.model import Kind, slugify

_RELATION = (
    r"(?:wife|husband|partner|spouse|girlfriend|boyfriend|fianc[ée]e?|mother|father|mum|dad|"
    r"mom|parent|son|daughter|child|kid|brother|sister|sibling|grandmother|grandfather|"
    r"manager|boss|line manager|colleague|co-?worker|teammate|team lead|mentor|mentee|"
    r"friend|flatmate|roommate|neighbour|neighbor|client|customer|co-?founder|business partner|"
    r"assistant|doctor|therapist|coach|tutor|teacher|student|cat|dog)"
)
_NAME = r"([A-Z][a-z]+(?:\s[A-Z][a-z]+){0,2})"
_STOP_NAMES = {"User", "The", "They", "He", "She", "It", "ChatGPT", "Claude", "I", "Their"}

_PERSON_PATTERNS = [
    re.compile(r"\b" + _RELATION + r"\b,?\s+(?:is\s+)?(?:named|called)?\s*" + _NAME),
    re.compile(_NAME + r"\s*(?:,|\()\s*(?:user's|their|his|her|the user's)\s+" + _RELATION),
    re.compile(_NAME + r"\s+is\s+(?:user's|their|his|her|the user's)\s+" + _RELATION),
    re.compile(r"(?:user's|their|his|her)\s+" + _RELATION + r"\s+" + _NAME),
]
_PREF_RE = re.compile(
    r"\b(prefers?|likes? (?:to be|responses|answers|replies|when)|dislikes?|wants? (?:responses|"
    r"answers|replies|me to|you to|the assistant)|would like|tone|formal|informal|concise|"
    r"brief|detailed|bullet points|british english|american english|address(?:ed)? (?:as|them)|"
    r"call (?:them|me)|respond|response style|writing style|no emojis|use emojis|always|never)\b",
    re.IGNORECASE,
)
_AREA_RE = re.compile(
    r"\b(?:working on|building|developing|launching|writing|running|leading|maintaining|"
    r"project|startup|company|product|app|tool|book|thesis|dissertation|course)\b"
    r"[^.]{0,40}?(?:called|named|titled|,)?\s*[\"“']?([A-Z][\w-]+(?:\s[A-Z][\w-]+){0,2})[\"”']?",
)
_AREA_KEY_RE = re.compile(
    r"\b(working on|building|developing|launching|project|startup|side project|thesis|"
    r"dissertation|migration|rewrite|redesign|launch)\b",
    re.IGNORECASE,
)
_TOPIC_RE = re.compile(
    r"\b(?:interested in|interest in|learning|studying|studies|hobby is|hobbies include|enjoys|"
    r"passionate about|fan of|into|follows|collects|plays|practises|practices|reads about)\s+"
    r"(?:the\s+)?([a-z][\w-]*(?:\s[a-z][\w-]*){0,2})",
    re.IGNORECASE,
)
_TOPIC_STOP = {"a", "an", "the", "to", "how", "and", "it", "them", "that", "this", "with"}


@dataclass(frozen=True)
class Route:
    kind: Kind
    slug: str = ""
    name: str = ""
    description: str = ""
    section: str = ""


PROFILE = Route("profile", name="Profile", description="Who the user is.")
PREFERENCES = Route(
    "preferences", name="Preferences", description="How the user wants assistants to behave."
)


def route(text: str) -> Route:
    for pat in _PERSON_PATTERNS:
        if m := pat.search(text):
            name = next((g for g in m.groups() if g and g.split()[0] not in _STOP_NAMES), None)
            if name:
                return Route(
                    "person", slugify(name), name, f"{name}, as mentioned in the user's memory."
                )
    if _PREF_RE.search(text):
        return PREFERENCES
    if _AREA_KEY_RE.search(text) and (m := _AREA_RE.search(text)):
        name = m.group(1)
        if name.split()[0] not in _STOP_NAMES:
            return Route("area", slugify(name), name, f"Project: {name}.")
    if m := _TOPIC_RE.search(text):
        words = [w for w in m.group(1).split() if w.lower() not in _TOPIC_STOP]
        if words:
            name = " ".join(words[:3]).rstrip(",.")
            return Route("topic", slugify(name), name.capitalize(), f"Interest: {name}.")
    return PROFILE
