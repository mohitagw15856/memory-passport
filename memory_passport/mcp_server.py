"""``passport-mcp``: expose a vault to any MCP client (Claude Code, Cursor, Claude Desktop…).

Install with ``pip install "memory-passport[mcp]"`` and register it, for example in
Claude Code::

    claude mcp add passport -e PASSPORT_VAULT=~/passport -- passport-mcp

Tools: ``list_subjects``, ``read_memory``, ``remember``, ``forget``. Everything goes through
:mod:`memory_passport.store`, so exclusions and dedupe apply exactly as on the CLI. The
vault stays plain files: a client writing through this server and a person editing in a
text editor see the same thing.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from memory_passport.model import load_vault
from memory_passport.store import add_fact, remove_fact, render_file, render_subjects, search


def _vault_root() -> Path:
    raw = os.environ.get("PASSPORT_VAULT") or (sys.argv[1] if len(sys.argv) > 1 else "passport")
    return Path(raw).expanduser()


def build_server():  # pragma: no cover - needs the optional mcp dependency
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise SystemExit(
            'passport-mcp needs the "mcp" extra: pip install "memory-passport[mcp]"'
        ) from None

    mcp = FastMCP("memory-passport")

    @mcp.tool()
    def list_subjects() -> str:
        """List every subject (file) in the user's memory passport with fact counts."""
        return render_subjects(load_vault(_vault_root()))

    @mcp.tool()
    def read_memory(query: str = "", subject: str = "") -> str:
        """Read facts from the passport. Empty query and subject returns everything.
        query: words that must all appear (in the fact or its subject's name).
        subject: a path like people/priya-nair, a kind like preferences, or a name."""
        return read_memory_text(query, subject)

    @mcp.tool()
    def remember(text: str, subject: str = "", tag: str = "stated", section: str = "") -> str:
        """Save one fact. tag is stated (the user said it), observed (you saw it happen) or
        inferred (a guess). subject may be profile, preferences, person:<Name>, topic:<Name>,
        area:<Name>, or empty to let the passport route it."""
        return remember_text(text, subject, tag, section)

    @mcp.tool()
    def forget(text: str) -> str:
        """Remove a fact by its text (matched loosely: case, punctuation and phrasing)."""
        return forget_text(text)

    return mcp


def read_memory_text(query: str = "", subject: str = "") -> str:
    vault = load_vault(_vault_root())
    if not query and not subject:
        return "\n".join(render_file(mf) for mf in vault.files) or "(empty passport)"
    hits = search(vault, query, subject or None)
    if not hits:
        return "no matching facts"
    return "\n".join(f"{mf.path}: {f.render()}" for mf, f in hits)


def remember_text(text: str, subject: str = "", tag: str = "stated", section: str = "") -> str:
    if tag not in ("stated", "observed", "inferred"):
        return "tag must be stated, observed or inferred"
    r = add_fact(
        _vault_root(), text, subject=subject or None, tag=tag, section=section, source="mcp"
    )  # type: ignore[arg-type]
    if r.dropped:
        return f"refused: this looks like {r.dropped}, which the passport spec excludes"
    if r.duplicate:
        return f"already known in {r.path}"
    note = " (sensitive span redacted)" if r.redacted else ""
    verb = "created" if r.created_file else "updated"
    return f"saved to {r.path} ({verb}){note}"


def forget_text(text: str) -> str:
    removed = remove_fact(_vault_root(), text)
    if not removed:
        return "nothing matched"
    return "removed " + ", ".join(f"{p}:{n}" for p, n in removed)


def main() -> None:  # pragma: no cover
    build_server().run()


if __name__ == "__main__":  # pragma: no cover
    main()
