"""Polygons router.

Exposes endpoints for discovering and (eventually) fetching polygon data from Sumo. All
Sumo Explorer interactions are delegated to ``PolygonsAccess`` in the service layer.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Header, Path
from ri_cloud_services.sumo_access.polygon_access import PolygonsAccess

from ri_cloud_api.primary.utils.router_headers import extract_required_token

from . import converters, schemas

router = APIRouter(tags=["polygons"])


@router.get("/cases/{case_uuid}/ensembles/{ensemble_name}/polygons")
def get_polygons(case_uuid: str, ensemble_name: str) -> list[dict[str, str]]:
    """Placeholder polygons endpoint until PolygonsAccess is implemented."""
    _ = (case_uuid, ensemble_name)
    return []


@router.get("/cases/{case_uuid}/ensembles/{ensemble_name}/polygons_directory")
async def get_polygons_directory(
    authorization: str | None = Header(None, description="Authorization bearer token for Sumo API"),
    case_uuid: str = Path(description="Sumo case uuid"),
    ensemble_name: str = Path(description="Ensemble name"),
) -> dict[str, list[schemas.PolygonMeta] | list[schemas.DepthFaultPolygonMeta] | list[schemas.FluidContactPolygonMeta]]:
    """Get a directory of polygons tagged with an FMU standard result, categorized per standard result."""
    access_token = extract_required_token(authorization)
    access = PolygonsAccess.from_ensemble_name(access_token, case_uuid, ensemble_name)

    async with asyncio.TaskGroup() as tg:
        field_outline_task = tg.create_task(access.get_field_outline_polygons_meta_async())
        structure_depth_fault_lines_task = tg.create_task(
            access.get_structure_depth_fault_lines_polygons_meta_async()
        )
        fluid_contact_outline_task = tg.create_task(access.get_fluid_contact_outline_polygons_meta_async())

    return converters.to_api_polygons_directory(
        field_outline_task.result(),
        structure_depth_fault_lines_task.result(),
        fluid_contact_outline_task.result(),
    )
