"""The pluggable importer interface.

To add a product, subclass :class:`Importer`, set ``name`` and ``help``, implement
``detect`` and ``load``, and either add it to the built-in list in ``registry.py``
or expose it from your own package as a ``memory_passport.importers`` entry point.
See CONTRIBUTING.md for a worked example.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

from memory_passport.model import Vault


@dataclass
class ImportOptions:
    route: bool = True
    """Sort facts into people/, topics/, areas/ and preferences.md; else all go in profile.md."""
    allow_health: bool = False
    """Keep facts that trip the health detector and set ``allow_health`` in the manifest."""
    memory_text: Path | None = None
    """An extra file of pasted memories to combine with the main input (product-specific)."""


@dataclass
class ImportResult:
    vault: Vault
    notes: list[str] = field(default_factory=list)
    """Human-readable remarks about what was done, printed by the CLI."""
    dropped: list[tuple[str, str]] = field(default_factory=list)
    """``(category, text)`` for every fact removed by an exclusion detector."""
    redacted: list[tuple[str, str]] = field(default_factory=list)
    """``("redacted", original_text)`` for every fact kept with a span replaced."""

    @property
    def fact_count(self) -> int:
        return sum(len(f.facts) for f in self.vault.files)


class Importer(ABC):
    name: ClassVar[str]
    """Token used with ``--from`` and written into ``sources``. Lower-case kebab-case."""
    help: ClassVar[str] = ""
    """One line shown by ``passport importers``."""

    @abstractmethod
    def detect(self, path: Path) -> bool:
        """Return True if ``path`` looks like something this importer can read."""

    @abstractmethod
    def load(self, path: Path, options: ImportOptions) -> ImportResult:
        """Read ``path`` and build a vault. Must not write to disk."""
