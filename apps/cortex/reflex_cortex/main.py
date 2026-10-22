"""CLI `reflex-cortex`: serve (Change Stream consumer trên incidents) | eval | investigate."""

from __future__ import annotations

import asyncio
import json
import logging

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase
from reflex_core.incident import IncidentStatus
from reflex_mongo.collections import INCIDENTS
from reflex_telemetry import setup as telemetry_setup
from reflex_telemetry.datadog_api import DatadogApi
from reflex_telemetry.tags import SVC_CORTEX
import typer

from reflex_cortex.agent import CortexAgent
from reflex_cortex.settings import Settings

app = typer.Typer(no_args_is_help=True)
logger = logging.getLogger(__name__)


def _agent(db: AsyncDatabase | None, settings: Settings) -> CortexAgent:
    datadog = (
        DatadogApi(settings.dd_api_key, settings.dd_app_key, settings.dd_site or "datadoghq.com")
        if settings.dd_api_key and settings.dd_app_key
        else None
    )
    return CortexAgent(db=db, settings=settings, datadog=datadog)


async def claim(db: AsyncDatabase, incident_key: str) -> bool:
    """detected → investigating bằng một update nguyên tử; chỉ một Cortex instance thắng."""
    res = await db[INCIDENTS].update_one(
        {"key": incident_key, "status": IncidentStatus.DETECTED.value},
        {"$set": {"status": IncidentStatus.INVESTIGATING.value}},
    )
    return res.modified_count == 1


async def serve_forever(settings: Settings) -> None:
    client: AsyncMongoClient = AsyncMongoClient(settings.mongodb_uri)
    db = client[settings.mongodb_db]
    agent = _agent(db, settings)
    pipeline = [{"$match": {"operationType": {"$in": ["insert", "update", "replace"]}}}]
    logger.info("Cortex watching incidents in %s", settings.mongodb_db)

    # Incident đã `detected` trước khi Cortex khởi động
    pending = [doc async for doc in db[INCIDENTS].find({"status": IncidentStatus.DETECTED.value})]
    for doc in pending:
        if await claim(db, doc["key"]):
            await agent.investigate(doc["key"])

    async with await db[INCIDENTS].watch(pipeline, full_document="updateLookup") as stream:
        async for change in stream:
            doc = change.get("fullDocument") or {}
            if doc.get("status") == IncidentStatus.DETECTED.value and await claim(db, doc["key"]):
                try:
                    await agent.investigate(doc["key"])
                except Exception:
                    logger.exception("Investigation failed for %s", doc["key"])


@app.command()
def serve() -> None:
    """Watch incidents (detected/investigating) → chạy investigation."""
    telemetry_setup.init(SVC_CORTEX, llmobs=True)
    settings = Settings()
    if not settings.mongodb_uri:
        raise typer.BadParameter("MONGODB_URI is required for `serve`")
    asyncio.run(serve_forever(settings))


@app.command()
def investigate(incident_key: str) -> None:
    """Chạy một investigation thủ công (debug)."""
    telemetry_setup.init(SVC_CORTEX, llmobs=True)
    settings = Settings()

    async def _run() -> dict:
        client: AsyncMongoClient | None = (
            AsyncMongoClient(settings.mongodb_uri) if settings.mongodb_uri else None
        )
        try:
            db = client[settings.mongodb_db] if client else None
            inv = await _agent(db, settings).investigate(incident_key)
            return inv.model_dump(by_alias=True, mode="json")
        finally:
            if client:
                await client.close()

    typer.echo(json.dumps(asyncio.run(_run()), indent=2, ensure_ascii=False))


@app.command()
def eval(scenarios: str = "") -> None:
    """Offline eval trên scenario (side/cause/action/evidence accuracy)."""
    from reflex_cortex.eval import harness

    try:
        report = asyncio.run(harness.run([s for s in scenarios.split(",") if s]))
    except NotImplementedError:
        typer.echo("Eval harness chưa được hiện thực (DE-7.4).", err=True)
        raise typer.Exit(code=2) from None
    typer.echo(json.dumps(report, indent=2))


if __name__ == "__main__":
    app()
