"""Khởi động FastAPI BFF + các module nền (sentinel, actuator, verifier, outbox) với leader lease."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI
from pymongo import AsyncMongoClient
from reflex_telemetry.datadog_api import DatadogApi

from reflex_cp.actuator.apply import Actuator
from reflex_cp.api.actions import router as actions_router
from reflex_cp.api.auth import require_console_token, require_console_token_query
from reflex_cp.api.demo import router as demo_router
from reflex_cp.api.incidents import router as incidents_router
from reflex_cp.api.lab import router as lab_router
from reflex_cp.api.memory import router as memory_router
from reflex_cp.api.pipelines import router as pipelines_router
from reflex_cp.api.policies import router as policies_router
from reflex_cp.api.pulse import router as pulse_router
from reflex_cp.api.replays import router as replays_router
from reflex_cp.api.series import router as series_router
from reflex_cp.api.slos import router as slos_router
from reflex_cp.api.stream import router as stream_router
from reflex_cp.hooks.datadog import router as datadog_router
from reflex_cp.incidents.service import IncidentService
from reflex_cp.incidents.watchdog import CortexWatchdog
from reflex_cp.outbox.publisher import OutboxPublisher
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
        outbox: OutboxPublisher | None = None
        outbox_task: asyncio.Task | None = None
        watchdog: CortexWatchdog | None = None
        watchdog_task: asyncio.Task | None = None

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

                # Outbox publisher: Datadog events (at-least-once)
                datadog = (
                    DatadogApi(settings.dd_api_key, settings.dd_app_key, settings.dd_site)
                    if settings.dd_api_key
                    else None
                )
                outbox = OutboxPublisher(db, datadog)
                outbox_task = asyncio.create_task(outbox.run())
                app.state.outbox_task = outbox_task

                # Watchdog R4: Cortex im lặng → rule engine ngay tại control-plane
                if settings.cortex_watchdog_enabled:
                    unclaimed_s, stale_s = settings.watchdog_thresholds()
                    watchdog = CortexWatchdog(db, unclaimed_s=unclaimed_s, stale_s=stale_s)
                    watchdog_task = asyncio.create_task(watchdog.run())

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
        if outbox:
            outbox.stop()
        if outbox_task and not outbox_task.done():
            outbox_task.cancel()
        if watchdog:
            watchdog.stop()
        if watchdog_task and not watchdog_task.done():
            watchdog_task.cancel()

        if client:
            await client.close()
            logger.info("Closed MongoDB connection")

    app = FastAPI(title="Reflex Control Plane", lifespan=lifespan)
    app.state.settings = settings

    # Đăng ký routes
    app.include_router(datadog_router)
    protected = [Depends(require_console_token)]
    for router in (
        actions_router,
        pulse_router,
        incidents_router,
        policies_router,
        series_router,
        slos_router,
        replays_router,
        pipelines_router,
        memory_router,
        lab_router,
        demo_router,
    ):
        app.include_router(router, dependencies=protected)

    app.include_router(stream_router, dependencies=[Depends(require_console_token_query)])

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
