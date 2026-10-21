"""FastAPI app factory, lifespan (policy store, health sync, telemetry writer), ddtrace init."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from reflex_mongo.client import get_db, make_client

from reflex_gateway.api import chat, health
from reflex_gateway.engine.orchestrator import Orchestrator
from reflex_gateway.policy_store import PolicyStore
from reflex_gateway.settings import Settings
from reflex_gateway.target_catalog import TargetCatalog
from reflex_gateway.telemetry.mongo_writer import MongoBatchWriter
from reflex_gateway.telemetry.queue import TelemetryQueue


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db = None
        client = None
        if cfg.mongodb_uri:
            try:
                client = make_client(cfg.mongodb_uri, app_name=f"reflex-gateway-{cfg.gateway_id}")
                db = get_db(client, cfg.mongodb_db)
            except Exception as e:
                pass

        target_catalog = TargetCatalog(db=db)
        await target_catalog.load()

        policy_store = PolicyStore(db=db)
        await policy_store.start()

        telemetry_queue = TelemetryQueue(maxsize=cfg.telemetry_queue_max)
        writer = None
        if db is not None:
            writer = MongoBatchWriter(
                db=db,
                queue=telemetry_queue,
                batch_size=cfg.telemetry_batch_size,
                flush_ms=cfg.telemetry_flush_ms,
            )
            await writer.start()

        orchestrator = Orchestrator(
            policy_store=policy_store,
            target_catalog=target_catalog,
            telemetry_queue=telemetry_queue,
            gateway_id=cfg.gateway_id,
            env=cfg.reflex_env,
        )

        app.state.settings = cfg
        app.state.target_catalog = target_catalog
        app.state.policy_store = policy_store
        app.state.telemetry_queue = telemetry_queue
        app.state.orchestrator = orchestrator
        app.state.mongo_writer = writer

        yield

        if writer:
            await writer.stop()
        await policy_store.stop()
        if client:
            await client.close()

    app = FastAPI(title="Reflex Gateway", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(chat.router)
    return app


def run() -> None:
    """Entry point `reflex-gateway` (uvicorn)."""
    cfg = Settings()
    uvicorn.run("reflex_gateway.main:create_app", factory=True, host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    run()
