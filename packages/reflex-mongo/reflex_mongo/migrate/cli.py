"""CLI `reflex-mongo` — migrate | seed | drop (chỉ local)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import typer

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from reflex_mongo.client import get_db, make_client
from reflex_mongo.migrate.collections import ensure_collections
from reflex_mongo.migrate.indexes import ensure_indexes
from reflex_mongo.migrate.search_indexes import ensure_search_indexes
from reflex_mongo.migrate.seed import seed_all
from reflex_mongo.migrate.validators import apply_validators

app = typer.Typer(no_args_is_help=True)

# Cho B008 (mypy/ruff): Option khai báo một lần ở module-level
SEEDS_DIR_OPT = typer.Option("seeds")

# Đường dẫn mặc định tính theo root repo (cwd khi chạy `uv run reflex-mongo`)
SEARCH_DIR = Path("infra/mongo/search")
VALIDATOR_DIR = Path("infra/mongo/validators")
DEFAULT_DB = "reflex"


async def _migrate(uri: str, db_name: str) -> None:
    client = make_client(uri, app_name="reflex-mongo")
    db = get_db(client, db_name)
    await ensure_collections(db)
    created = await ensure_indexes(db)
    validators = await apply_validators(db, VALIDATOR_DIR)
    search = await ensure_search_indexes(db, SEARCH_DIR)
    print(
        f"migrate {db_name}: indexes mới={sum(created.values())}, "
        f"validators={validators or '—'}, search={search or '—'}"
    )
    await client.close()


@app.command()
def migrate(
    uri: str = typer.Option(..., envvar="MONGODB_URI"),
) -> None:
    """Tạo/đồng bộ toàn bộ schema (collections, TS, index, validator, search index)."""
    asyncio.run(_migrate(uri, DEFAULT_DB))


@app.command()
def seed(
    dir: Path = SEEDS_DIR_OPT,
    uri: str = typer.Option(..., envvar="MONGODB_URI"),
) -> None:
    """Seed targets, slos, policies (upsert theo _id, idempotent)."""

    async def run() -> None:
        client = make_client(uri, app_name="reflex-mongo")
        try:
            counts = await seed_all(get_db(client, DEFAULT_DB), dir)
        finally:
            await client.close()
        print(f"seed {DEFAULT_DB}: {counts or '—'}")

    asyncio.run(run())


@app.command()
def drop(db_name: str, uri: str = typer.Option(..., envvar="MONGODB_URI")) -> None:
    """Xoá một database — dùng khi muốn migrate lại sạch; cấm khi REFLEX_ENV != local."""

    async def run() -> None:
        client = make_client(uri, app_name="reflex-mongo")
        try:
            await client.drop_database(db_name)
        finally:
            await client.close()

    confirm = typer.confirm(f"Xoá toàn bộ database {db_name}?")
    if not confirm:
        raise typer.Abort()
    if os.environ.get("REFLEX_ENV", "local") != "local":
        raise typer.BadParameter("drop chỉ chạy khi REFLEX_ENV=local")
    asyncio.run(run())
    print(f"dropped {db_name}")


if __name__ == "__main__":
    app()
