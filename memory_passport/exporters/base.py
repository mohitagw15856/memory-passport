from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

from memory_passport.model import Fact, MemoryFile, Vault


@dataclass
class ExportResult:
    files: dict[str, str]
    """Relative path -> content. A single entry named ``-`` means "print to stdout"."""
    notes: list[str] = field(default_factory=list)

    @property
    def single(self) -> str | None:
        return next(iter(self.files.values())) if len(self.files) == 1 else None


class Exporter(ABC):
    name: ClassVar[str]
    help: ClassVar[str] = ""
    default_out: ClassVar[str] = "-"

    @abstractmethod
    def render(self, vault: Vault) -> ExportResult: ...


def fact_sentence(fact: Fact, *, hedge: bool = True) -> str:
    """A fact as plain prose for products with no provenance. Inferred facts are hedged."""
    if hedge and fact.tag == "inferred":
        return f"Possibly: {fact.text}"
    if hedge and fact.tag == "observed":
        return f"Observed: {fact.text}"
    return fact.text


def ordered(vault: Vault) -> list[MemoryFile]:
    order = {"profile": 0, "preferences": 1, "person": 2, "area": 3, "topic": 4}
    return sorted(vault.files, key=lambda f: (order.get(f.kind or "", 9), str(f.path)))
