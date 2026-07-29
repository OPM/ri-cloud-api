"""ResInsight Cloud API — FastAPI application.

Setup:
    pip install poetry
    python -m venv .venv
    source .venv/bin/activate
    poetry install

Run (from the repository root):
    uvicorn ri_cloud_api.primary.main:app --host 0.0.0.0 --port 8000 --reload

Docs:
    http://localhost:8000/docs
"""

from __future__ import annotations

import logging

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from ri_cloud_services.utils.httpx_async_client_wrapper import HTTPX_ASYNC_CLIENT_WRAPPER
from ri_cloud_services.services_config import ServicesConfig, init_services_config

from .utils.exception_handlers import add_exception_handlers
from .routers.blob_access.router import router as blob_access_router
from .routers.explore.router import router as explore_router
from .routers.grids.router import router as grids_router
from .routers.health.router import router as health_router
from .routers.polygons.router import router as polygons_router
from .routers.surfaces.router import router as surfaces_router
from .routers.timeseries.router import router as timeseries_router

from . import config

logger = logging.getLogger("ri_cloud_api")
logging.basicConfig(level=logging.INFO)

services_config = ServicesConfig(
    sumo_env=config.SUMO_ENV
)
init_services_config(services_config)

@asynccontextmanager
async def lifespan_handler_async(_fastapi_app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan handler for the FastAPI application."""
    # The first part of this function, before the yield, will be executed before the FastAPI
    # application starts.
    HTTPX_ASYNC_CLIENT_WRAPPER.start()
    # This part, after the yield, will be executed after the application has finished.
    yield

    await HTTPX_ASYNC_CLIENT_WRAPPER.stop_async()


app = FastAPI(
    title="ResInsight Cloud API",
    lifespan=lifespan_handler_async
)

add_exception_handlers(app)

app.include_router(health_router)
app.include_router(blob_access_router)
app.include_router(explore_router)
app.include_router(timeseries_router)
app.include_router(polygons_router)
app.include_router(surfaces_router)
app.include_router(grids_router)
