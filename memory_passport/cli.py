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


if __name__ == "__main__":
    app()
