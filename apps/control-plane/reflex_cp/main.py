"""Khởi động FastAPI BFF + các module nền (sentinel, actuator, verifier, outbox) với leader lease."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
from typing import AsyncIterator

from fastapi import FastAPI
from pymongo import AsyncMongoClient
import uvicorn

from reflex_cp.actuator.apply import Actuator
from reflex_cp.api.actions import router as actions_router
from reflex_cp.api.incidents import router as incidents_router
from reflex_cp.api.policies import router as policies_router
from reflex_cp.api.pulse import router as pulse_router
from reflex_cp.api.stream import router as stream_router
from reflex_cp.hooks.datadog import router as datadog_router
from reflex_cp.incidents.service import IncidentService
from reflex_cp.sentinel.loop import Sentinel
from reflex_cp.settings import Settings

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        client: AsyncMongoClient | None = None
        sentinel_task: asyncio.Task | None = None
        actuator_task: asyncio.Task | None = None
        sentinel: Sentinel | None = None
        actuator: Actuator | None = None

        if settings.mongodb_uri:
            try:
                client = AsyncMongoClient(settings.mongodb_uri)
                db = client[settings.mongodb_db]
                app.state.client = client
                app.state.db = db
                app.state.incident_service = IncidentService(db)

                # Khởi động Sentinel background loop
                sentinel = Sentinel(db=db, settings=settings)
                app.state.sentinel = sentinel
                sentinel_task = asyncio.create_task(sentinel.run())
                app.state.sentinel_task = sentinel_task

                # Khởi động Actuator background watcher
                actuator = Actuator(db=db)
                app.state.actuator = actuator
                actuator_task = asyncio.create_task(actuator.run())
                app.state.actuator_task = actuator_task

                logger.info("Control plane connected to MongoDB: %s", settings.mongodb_db)
            except Exception as e:
                logger.error("Failed to initialize MongoDB connection or background tasks: %s", e)

        yield

        # Dọn dẹp tài nguyên khi tắt app
        if sentinel:
            sentinel.stop()
        if sentinel_task and not sentinel_task.done():
            sentinel_task.cancel()
        if actuator_task and not actuator_task.done():
            actuator_task.cancel()

        if client:
            await client.close()
            logger.info("Closed MongoDB connection")

    app = FastAPI(title="Reflex Control Plane", lifespan=lifespan)
    app.state.settings = settings

    # Đăng ký routes
    app.include_router(datadog_router)
    app.include_router(actions_router)
    app.include_router(pulse_router)
    app.include_router(incidents_router)
    app.include_router(policies_router)
    app.include_router(stream_router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


def run() -> None:
    settings = Settings()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    run()
