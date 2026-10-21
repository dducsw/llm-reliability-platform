"""CLI `reflex-mongo` — migrate | seed | drop (chỉ local)."""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def migrate(uri: str = typer.Option(..., envvar="MONGODB_URI")) -> None:
    """Tạo/đồng bộ toàn bộ schema."""
    raise NotImplementedError


@app.command()
def seed(
    dir: Path = typer.Option(Path("seeds")),
    uri: str = typer.Option(..., envvar="MONGODB_URI"),
) -> None:
    """Seed targets, slos, policies, golden prompts, incident history."""
    raise NotImplementedError


if __name__ == "__main__":
    app()
