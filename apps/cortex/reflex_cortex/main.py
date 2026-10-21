"""CLI `reflex-cortex`: serve (Change Stream consumer trên incidents) | eval | investigate."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def serve() -> None:
    """Watch incidents (detected/investigating) → chạy investigation."""
    raise NotImplementedError


@app.command()
def investigate(incident_key: str) -> None:
    """Chạy một investigation thủ công (debug)."""
    raise NotImplementedError


@app.command()
def eval(scenarios: str = "") -> None:
    """Offline eval trên scenario (side/cause/action/evidence accuracy)."""
    raise NotImplementedError


if __name__ == "__main__":
    app()
