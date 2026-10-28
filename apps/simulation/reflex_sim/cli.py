"""CLI `reflex-sim`: mock-llm | chaos-proxy | traffic | prober | run <scenario> | bench.

Làn DE: `bench` đi kèm importer + pipeline trên bench_ts (docs/20-architecture/
simulation-and-chaos.md §4).
"""

from __future__ import annotations

import asyncio
import sys

import typer
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
import uvicorn
from reflex_mongo.client import get_db, make_client
from reflex_mongo.collections import BENCH_TS

from reflex_sim.bench.importer import import_bench
from reflex_sim.bench.runners import rebuild_baselines, top_incidents
from reflex_sim.prober.prober import Prober
from reflex_sim.scenario.loader import load as load_scenario
from reflex_sim.scenario.runner import ScenarioRunner
from reflex_sim.settings import Settings
from reflex_sim.traffic.generator import TrafficGenerator

app = typer.Typer(no_args_is_help=True)
bench = typer.Typer(no_args_is_help=True)
app.add_typer(bench, name="bench")


def _client_db() -> tuple[AsyncMongoClient, AsyncDatabase]:
    settings = Settings()
    client = make_client(settings.mongodb_uri, app_name="reflex-sim")
    return client, get_db(client, settings.mongodb_db)


@app.command("mock-llm")
def mock_llm(port: int = 8060) -> None:
    """Mock LLM server deterministic theo seed."""
    uvicorn.run("reflex_sim.mock_llm.server:create_app", factory=True, host="0.0.0.0", port=port)


@app.command("chaos-proxy")
def chaos_proxy(port: int = 8070) -> None:
    """Chaos Proxy đứng trước upstreams để inject faults."""
    uvicorn.run("reflex_sim.chaos_proxy.server:create_app", factory=True, host="0.0.0.0", port=port)


@app.command()
def traffic(rps: float = 8.0, duration: float = 0.0) -> None:
    """ShopMate traffic generator."""
    gen = TrafficGenerator(gateway_url=Settings().gateway_url, base_rps=rps)
    dur = None if duration <= 0 else duration
    asyncio.run(gen.run(duration_s=dur))


@app.command()
def prober() -> None:
    """Canary prober định kỳ 15s gửi golden prompts."""

    async def _main() -> None:
        client, db = _client_db()
        p = Prober(db=db)
        try:
            await p.run()
        finally:
            await client.close()

    asyncio.run(_main())


@app.command()
def run(scenario: str, seed: int = 42, fast: bool = False) -> None:
    """Chạy scenario YAML trong scenarios/."""

    async def _main() -> None:
        sc = load_scenario(scenario)
        client, db = _client_db()
        runner = ScenarioRunner(db=db)
        try:
            res = await runner.run(sc, seed=seed, fast=fast)
            print(f"Scenario {sc.name}: {res['status'].upper()} (phases: {res['phases_run']})")
            print(f"Expectations check: {'ALL PASSED' if res['all_passed'] else 'FAILED'}")
            for exp in res["expectations"]:
                verdict = {True: "PASS", False: "FAIL", None: "SKIP"}[exp["passed"]]
                print(f"  - {exp['expectation']}: {verdict} ({exp['detail']})")
        finally:
            await client.close()

    asyncio.run(_main())


@bench.command("import")
def bench_import(days: int = 60) -> None:
    """Tải Jwrede/llm-bench-data (`days` ngày gần nhất) và nạp vào bench_ts."""

    async def run() -> None:
        client, db = _client_db()
        try:
            inserted = await import_bench(days, ".cache/llm-bench-data", collection=db[BENCH_TS])
        finally:
            await client.close()
        print(f"import: {inserted} docs -> {db.name}.{BENCH_TS}")

    asyncio.run(run())


@bench.command("baselines")
def bench_baselines(days: int = 60) -> None:
    """A14: rebuild baselines hour-of-week từ bench_ts."""

    async def run() -> None:
        client, db = _client_db()
        try:
            count = await rebuild_baselines(db, days=days)
        finally:
            await client.close()
        print(f"A14: {count} baselines (model, dow, hour) sau khi quét {days} ngày")

    asyncio.run(run())


@bench.command("incidents")
def bench_incidents(days: int = 7, threshold: float = 0.5, limit: int = 10) -> None:
    """A15: top cửa sổ sự cố thật trong bench_ts."""

    async def run() -> None:
        client, db = _client_db()
        try:
            rows = await top_incidents(db, days=days, threshold=threshold, limit=limit)
        finally:
            await client.close()
        print(f"A15: {len(rows)} model có cửa sổ sự cố (err6h >={threshold}) trong {days} ngày")
        for r in rows:
            window = f"{r['first']:%m-%d %H:%M} -> {r['last']:%m-%d %H:%M}"
            print(f"  {r['_id']:<42} worst={r['worst']:.2f} {r['hours']:>3}h  {window}")

    asyncio.run(run())


if __name__ == "__main__":
    app()
