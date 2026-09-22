"""``passport`` command-line interface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from memory_passport import __version__

app = typer.Typer(
    name="passport",
    help="Portable AI assistant memory: validate, import, export, merge and diff vaults.",
    no_args_is_help=True,
    rich_markup_mode=None,
)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"memory-passport {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True, help="Show version.")
    ] = False,
) -> None:
    """memory-passport CLI."""


@app.command()
def validate(
    vault: Annotated[Path, typer.Argument(help="Vault directory to check.")],
    strict: Annotated[bool, typer.Option(help="Treat warnings as failures.")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable output.")] = False,
    stale: Annotated[
        int | None,
        typer.Option(help="Warn about observed/inferred facts older than this many days."),
    ] = None,
) -> None:
    """Check a vault against the spec. Exit code 1 on errors (or warnings with --strict)."""
    from memory_passport.validate import validate_vault

    report = validate_vault(vault, stale_days=stale)
    if as_json:
        typer.echo(
            json.dumps(
                {
                    "root": str(report.root),
                    "files": report.file_count,
                    "facts": report.fact_count,
                    "ok": report.ok(strict=strict),
                    "issues": [i.__dict__ for i in report.issues],
                },
                indent=2,
            )
        )
    else:
        for issue in report.issues:
            typer.echo(str(issue))
        summary = (
            f"{report.file_count} file(s), {report.fact_count} fact(s), "
            f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)"
        )
        typer.echo(("OK  " if report.ok(strict=strict) else "FAIL  ") + summary)
    raise typer.Exit(code=0 if report.ok(strict=strict) else 1)


@app.command("import")
def import_(
    source: Annotated[Path, typer.Argument(help="Export file, folder or pasted memory text.")],
    from_: Annotated[
        str | None, typer.Option("--from", help="Importer name (see `passport importers`).")
    ] = None,
    out: Annotated[Path, typer.Option("--out", "-o", help="Vault directory to write.")] = Path(
        "passport"
    ),
    memory_text: Annotated[
        Path | None, typer.Option(help="Extra pasted-memory file to combine with the export.")
    ] = None,
    route: Annotated[
        bool, typer.Option(help="Sort facts into people/topics/areas/preferences.")
    ] = True,
    allow_health: Annotated[
        bool, typer.Option(help="Keep health facts and mark the vault as opted in.")
    ] = False,
    force: Annotated[bool, typer.Option(help="Write into a non-empty directory.")] = False,
) -> None:
    """Build a passport vault from a product's export."""
    from memory_passport.importers import ImportOptions, get_importer, list_importers
    from memory_passport.model import VaultError, write_vault

    if not source.exists():
        typer.echo(f"error: {source} does not exist", err=True)
        raise typer.Exit(2)
    if from_ is None:
        matches = [n for n, cls in list_importers().items() if cls().detect(source)]
        if len(matches) != 1:
            typer.echo(
                f"error: could not tell which importer to use ({', '.join(matches) or 'none'} "
                "matched); pass --from",
                err=True,
            )
            raise typer.Exit(2)
        from_ = matches[0]
    try:
        importer = get_importer(from_)
    except KeyError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(2) from None
    if out.exists() and any(out.iterdir()) and not force:
        typer.echo(f"error: {out} is not empty; pass --force to write into it", err=True)
        raise typer.Exit(2)
    opts = ImportOptions(route=route, allow_health=allow_health, memory_text=memory_text)
    try:
        result = importer.load(source, opts)
    except VaultError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from None
    write_vault(result.vault, out)
    for n in result.notes:
        typer.echo(f"  {n}")
    for cat, text in result.dropped:
        typer.echo(f"  dropped ({cat}): {text[:60]}{'…' if len(text) > 60 else ''}")
    for _, text in result.redacted:
        typer.echo(f"  redacted: {text[:60]}{'…' if len(text) > 60 else ''}")
    typer.echo(f"wrote {len(result.vault.files)} file(s), {result.fact_count} fact(s) to {out}")


@app.command()
def export(
    vault: Annotated[Path, typer.Argument(help="Vault directory.")],
    to: Annotated[str, typer.Option("--to", help="Exporter name (see `passport exporters`).")],
    out: Annotated[
        Path | None,
        typer.Option(
            "--out",
            "-o",
            help="File or folder to write; default prints or uses the exporter's name.",
        ),
    ] = None,
) -> None:
    """Render a vault as the text or files a product accepts."""
    from memory_passport.exporters import get_exporter
    from memory_passport.model import VaultError, load_vault

    try:
        exporter = get_exporter(to)
        v = load_vault(vault)
    except (KeyError, VaultError) as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(2) from None
    result = exporter.render(v)
    for n in result.notes:
        typer.echo(f"note: {n}", err=True)
    if result.single is not None and "-" in result.files:
        if out is None:
            typer.echo(result.single, nl=False)
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(result.single, encoding="utf-8")
            typer.echo(f"wrote {out}", err=True)
        return
    target = out or Path(exporter.default_out)
    target.mkdir(parents=True, exist_ok=True)
    for rel, content in result.files.items():
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    typer.echo(f"wrote {len(result.files)} file(s) to {target}", err=True)


@app.command()
def merge(
    vault_a: Annotated[Path, typer.Argument()],
    vault_b: Annotated[Path, typer.Argument()],
    out: Annotated[
        Path, typer.Option("--out", "-o", help="Directory for the merged vault.")
    ] = Path("merged"),
    force: Annotated[bool, typer.Option(help="Write into a non-empty directory.")] = False,
) -> None:
    """Merge two vaults. Disagreements get conflict markers; nothing is resolved silently."""
    from memory_passport.merge import merge_dirs
    from memory_passport.model import VaultError, write_vault

    if out.exists() and any(out.iterdir()) and not force:
        typer.echo(f"error: {out} is not empty; pass --force to write into it", err=True)
        raise typer.Exit(2)
    try:
        merged, report = merge_dirs(vault_a, vault_b)
    except VaultError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(1) from None
    write_vault(merged, out)
    typer.echo(f"merged {report.files} file(s), {report.facts} fact(s) into {out}")
    for path, what in report.conflicts:
        typer.echo(f"  CONFLICT {path}: {what}")
    if report.conflicts:
        typer.echo(
            f"{len(report.conflicts)} conflict(s) need a human; "
            "the vault will not validate until resolved"
        )
        raise typer.Exit(3)


@app.command()
def diff(
    vault_a: Annotated[Path, typer.Argument()],
    vault_b: Annotated[Path, typer.Argument()],
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Show what changed between two vaults, fact by fact. Exit code 1 if they differ."""
    from memory_passport.diff import diff_dirs
    from memory_passport.model import VaultError

    try:
        d = diff_dirs(vault_a, vault_b)
    except VaultError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(2) from None
    if as_json:
        typer.echo(
            json.dumps(
                {
                    "only_a": [str(p) for p in d.only_a],
                    "only_b": [str(p) for p in d.only_b],
                    "changed": [
                        {
                            "path": str(fd.path),
                            "added": [f.render() for f in fd.added],
                            "removed": [f.render() for f in fd.removed],
                            "retagged": [[a.tag, b.tag, b.text] for a, b in fd.retagged],
                            "frontmatter": {k: list(v) for k, v in fd.frontmatter.items()},
                        }
                        for fd in d.changed
                    ],
                },
                indent=2,
                default=str,
            )
        )
    else:
        typer.echo(d.render(), nl=False)
    raise typer.Exit(0 if d.empty else 1)


@app.command()
def show(
    vault: Annotated[Path, typer.Argument(help="Vault directory.")],
    subject: Annotated[
        str | None, typer.Argument(help="profile, preferences, people/<slug>, a kind, or a name.")
    ] = None,
    query: Annotated[str | None, typer.Option("--query", "-q", help="Words to search for.")] = None,
) -> None:
    """Print a vault's subjects, one subject, or the facts matching a query."""
    from memory_passport.model import VaultError, load_vault
    from memory_passport.store import render_file, render_subjects, search

    try:
        v = load_vault(vault)
    except VaultError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(2) from None
    if query:
        hits = search(v, query, subject)
        for mf, f in hits:
            typer.echo(f"{mf.path}: {f.render()}")
        typer.echo(f"{len(hits)} fact(s)", err=True)
        raise typer.Exit(0 if hits else 1)
    if subject is None:
        typer.echo(render_subjects(v), nl=False)
        return
    matches = [mf for mf in v.files if _matches(mf, subject)]
    if not matches:
        typer.echo(f"error: no subject matches '{subject}'", err=True)
        raise typer.Exit(1)
    for mf in matches:
        typer.echo(render_file(mf))


def _matches(mf, subject: str) -> bool:
    from memory_passport.store import _file_matches

    return _file_matches(mf, subject)


@app.command()
def add(
    vault: Annotated[Path, typer.Argument(help="Vault directory.")],
    text: Annotated[str, typer.Argument(help="The fact, one sentence.")],
    to: Annotated[
        str | None,
        typer.Option(
            "--to",
            help=(
                "profile, preferences, people/<slug>, person:<Name>, topic:<Name>, "
                "area:<Name>. Default: routed from the text."
            ),
        ),
    ] = None,
    tag: Annotated[str, typer.Option(help="stated, observed or inferred.")] = "stated",
    section: Annotated[str, typer.Option(help="## heading to file it under.")] = "",
) -> None:
    """Append one fact to a vault, dated today, with exclusions applied."""
    from memory_passport.model import VaultError
    from memory_passport.store import add_fact

    if tag not in ("stated", "observed", "inferred"):
        typer.echo("error: --tag must be stated, observed or inferred", err=True)
        raise typer.Exit(2)
    try:
        r = add_fact(vault, text, subject=to, tag=tag, section=section)  # type: ignore[arg-type]
    except VaultError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(2) from None
    if r.dropped:
        typer.echo(
            f"refused: looks like {r.dropped}, which the spec excludes (SPEC.md §7)", err=True
        )
        raise typer.Exit(1)
    if r.duplicate:
        typer.echo(f"already in {r.path}; nothing written")
        return
    typer.echo(f"{'created' if r.created_file else 'updated'} {r.path}: {r.fact.render()}")
    if r.redacted:
        typer.echo("  a sensitive span was redacted", err=True)


@app.command()
def forget(
    vault: Annotated[Path, typer.Argument(help="Vault directory.")],
    text: Annotated[str, typer.Argument(help="The fact to remove (matched loosely).")],
) -> None:
    """Remove a fact from a vault by its text."""
    from memory_passport.store import remove_fact

    removed = remove_fact(vault, text)
    if not removed:
        typer.echo("nothing matched", err=True)
        raise typer.Exit(1)
    for p, n in removed:
        typer.echo(f"removed {p}:{n}")


@app.command()
def inspect(
    source: Annotated[Path, typer.Argument(help="An export zip, folder or file.")],
) -> None:
    """Report what an export contains, without importing it. Paste the output into bug reports."""
    from memory_passport.inspect_export import inspect_path

    if not source.exists():
        typer.echo(f"error: {source} does not exist", err=True)
        raise typer.Exit(2)
    for line in inspect_path(source):
        typer.echo(line)


@app.command()
def importers() -> None:
    """List available importers (built-in and plugins)."""
    from memory_passport.importers import list_importers

    for name, cls in list_importers().items():
        typer.echo(f"{name:12} {cls.help}")


@app.command()
def exporters() -> None:
    """List available exporters (built-in and plugins)."""
    from memory_passport.exporters import list_exporters

    for name, cls in list_exporters().items():
        typer.echo(f"{name:12} {cls.help}")


if __name__ == "__main__":
    app()
