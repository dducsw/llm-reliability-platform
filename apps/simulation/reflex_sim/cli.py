"""CLI `reflex-sim`: mock-llm | chaos-proxy | traffic | prober | run <scenario> | bench import."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True)
bench = typer.Typer(no_args_is_help=True)
app.add_typer(bench, name="bench")


@app.command("mock-llm")
def mock_llm(port: int = 8060) -> None:
    raise NotImplementedError


@app.command("chaos-proxy")
def chaos_proxy(port: int = 8070) -> None:
    raise NotImplementedError


@app.command()
def traffic(rps: float = 8.0) -> None:
    """ShopMate traffic generator."""
    raise NotImplementedError


@app.command()
def prober() -> None:
    raise NotImplementedError


@app.command()
def run(scenario: str, seed: int = 42, fast: bool = False) -> None:
    """Chạy scenario YAML trong scenarios/."""
    raise NotImplementedError


@bench.command("import")
def bench_import(days: int = 60) -> None:
    """Import Jwrede/llm-bench-data vào bench_ts."""
    raise NotImplementedError


if __name__ == "__main__":
    app()
