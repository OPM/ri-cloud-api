"""Polygons router.

Exposes endpoints for discovering and fetching polygon data from Sumo. All Sumo Explorer
interactions are delegated to ``PolygonsAccess`` in the service layer; this router only deals
in plain, Sumo-agnostic parameters and return types.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Header, HTTPException, Path, Query
from ri_cloud_services.sumo_access.polygon_access import PolygonsAccess

from ri_cloud_api.primary.utils.router_headers import extract_required_token

from . import converters, schemas

router = APIRouter(tags=["polygons"])


@router.get("/cases/{case_uuid}/ensembles/{ensemble_name}/polygon_result_directory")
async def get_polygon_result_directory(
    authorization: str | None = Header(None, description="Authorization bearer token for Sumo API"),
    case_uuid: str = Path(description="Sumo case uuid"),
    ensemble_name: str = Path(description="Ensemble name"),
) -> dict[str, list[schemas.PolygonMeta] | list[schemas.FluidContactPolygonMeta]]:
    """Get a directory of polygons metadata, categorized per polygon result type."""
    access_token = extract_required_token(authorization)
    access = PolygonsAccess.from_ensemble_name(access_token, case_uuid, ensemble_name)

    async with asyncio.TaskGroup() as tg:
        field_outline_task = tg.create_task(access.get_field_outline_polygons_meta_async())
        structure_depth_fault_lines_task = tg.create_task(access.get_structure_depth_fault_lines_polygons_meta_async())
        fluid_contact_outline_task = tg.create_task(access.get_fluid_contact_outline_polygons_meta_async())

    return converters.to_api_polygons_directory(
        field_outline_task.result(),
        structure_depth_fault_lines_task.result(),
        fluid_contact_outline_task.result(),
    )


@router.get("/cases/{case_uuid}/ensembles/{ensemble_name}/polygons_data")
async def get_polygons_data(
    authorization: str | None = Header(None, description="Authorization bearer token for Sumo API"),
    case_uuid: str = Path(description="Sumo case uuid"),
    ensemble_name: str = Path(description="Ensemble name"),
    realization: int = Query(description="Realization number"),
    polygon_result: schemas.PolygonResult = Query(description="Polygon result category"),
    name: str | None = Query(None, description="Polygon name, required unless polygon_result is field_outline"),
    contact_type: str | None = Query(
        None, description="Fluid contact type, required when polygon_result is fluid_contact_outline"
    ),
) -> list[schemas.PolygonData]:
    """Get polygon data for a realization in an ensemble.

    ``name`` is required for ``structure_depth_fault_lines``/``fluid_contact_outline`` and must
    be omitted for ``field_outline`` (there is exactly one field outline polygon per ensemble).
    ``contact_type`` is required only when ``polygon_result`` is ``fluid_contact_outline``.
    """
    if polygon_result == schemas.PolygonResult.STRUCTURE_DEPTH_FAULT_LINE and name is None:
        raise HTTPException(status_code=400, detail="Name must be specified for structure depth fault line polygons.")
    if polygon_result == schemas.PolygonResult.FLUID_CONTACT_OUTLINE and name is None:
        raise HTTPException(status_code=400, detail="Name must be specified for fluid contact outline polygons.")

    fluid_contact_type = None
    if polygon_result == schemas.PolygonResult.FLUID_CONTACT_OUTLINE:
        if contact_type is None:
            raise HTTPException(
                status_code=400, detail="Contact type must be specified for fluid contact outline polygons."
            )
        fluid_contact_type = converters.fluid_contact_type_from_api_str(contact_type)
        if fluid_contact_type is None:
            raise HTTPException(status_code=400, detail=f"Unknown contact type: {contact_type}")

    access_token = extract_required_token(authorization)
    access = PolygonsAccess.from_ensemble_name(access_token, case_uuid, ensemble_name)

    if polygon_result == schemas.PolygonResult.FIELD_OUTLINE:
        polygon_data = await access.get_field_outline_polygon_data_async(realization)
        return converters.to_api_polygons_data_list(polygon_data)
    if polygon_result == schemas.PolygonResult.STRUCTURE_DEPTH_FAULT_LINE:
        assert name is not None
        polygon_data = await access.get_structure_depth_fault_lines_polygon_data_async(realization, name)
        return converters.to_api_polygons_data_list(polygon_data)

    assert name is not None
    assert fluid_contact_type is not None
    polygon_data = await access.get_fluid_contact_outline_polygon_data_async(realization, name, fluid_contact_type)
    return converters.to_api_polygons_data_list(polygon_data)
