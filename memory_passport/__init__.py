"""memory-passport: a portable, plain-text format for AI assistant memory."""

from memory_passport.model import Fact, MemoryFile, Vault

SPEC_VERSION = "0.1"
__version__ = "0.1.0"

__all__ = ["SPEC_VERSION", "Fact", "MemoryFile", "Vault", "__version__"]
