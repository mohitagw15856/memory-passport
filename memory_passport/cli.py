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
) -> None:
    """Check a vault against the spec. Exit code 1 on errors (or warnings with --strict)."""
    from memory_passport.validate import validate_vault

    report = validate_vault(vault)
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
