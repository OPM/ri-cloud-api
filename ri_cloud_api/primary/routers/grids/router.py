"""
Grids router

Exposes endpoints for discovering and (eventually) fetching grid data from Sumo.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Path, Query
from ri_cloud_services.sumo_access.grid_access import GridAccess

from ri_cloud_api.primary.utils.router_headers import extract_required_token

from . import converters, schemas

router = APIRouter(tags=["grids"])


@router.get("/cases/{case_uuid}/ensembles/{ensemble_name}/grid_names")
async def get_grid_names(
    authorization: str | None = Header(None, description="Authorization bearer token for Sumo API"),
    case_uuid: str = Path(description="Sumo case uuid"),
    ensemble_name: str = Path(description="Ensemble name"),
) -> list[str]:
    """List available grid names for the given case + ensemble."""
    access_token = extract_required_token(authorization)
    access = GridAccess.from_case_uuid(access_token, case_uuid, ensemble_name)
    grid_names = await access.get_available_grid_names_async()
    return grid_names


@router.get("/cases/{case_uuid}/ensembles/{ensemble_name}/grid_info/{grid_name}")
async def get_grid_info(
    authorization: str | None = Header(None, description="Authorization bearer token for Sumo API"),
    case_uuid: str = Path(description="Sumo case uuid"),
    ensemble_name: str = Path(description="Ensemble name"),
    grid_name: str = Path(description="Grid name"),
) -> list[schemas.GridRealizationInfo]:
    """List available grids, with their realizations, for the given case + ensemble."""
    access_token = extract_required_token(authorization)
    access = GridAccess.from_case_uuid(access_token, case_uuid, ensemble_name)
    grid = await access.get_grid_info_async(grid_name)
    try:
        return converters.to_api_grid_info(grid)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Error converting grid info for grid '{grid_name}': {e}") from e


@router.get("/cases/{case_uuid}/ensembles/{ensemble_name}/grids/{grid_name}/realizations/{realization}/blob_id")
async def get_grid_blob_id(
    authorization: str | None = Header(None, description="Authorization bearer token for Sumo API"),
    case_uuid: str = Path(description="Sumo case uuid"),
    ensemble_name: str = Path(description="Ensemble name"),
    grid_name: str = Path(description="Grid name"),
    realization: int = Path(description="Realization id"),
) -> str:
    """Get the blob ID for the grid data for the given case + ensemble."""
    access_token = extract_required_token(authorization)
    access = GridAccess.from_case_uuid(access_token, case_uuid, ensemble_name)
    blob_id = await access.get_grid_blob_id_async(grid_name, realization)
    return blob_id


@router.get(
    "/cases/{case_uuid}/ensembles/{ensemble_name}/grids/{grid_name}/realizations/{realization}/property_info_list"
)
async def get_grid_property_info_list(
    authorization: str | None = Header(None, description="Authorization bearer token for Sumo API"),
    case_uuid: str = Path(description="Sumo case uuid"),
    ensemble_name: str = Path(description="Ensemble name"),
    grid_name: str = Path(description="Grid name"),
    realization: int = Path(description="Realization id"),
) -> list[schemas.GridPropertyInfo]:
    """Get grid property metadata for the given case + ensemble + grid + realization."""
    access_token = extract_required_token(authorization)
    access = GridAccess.from_case_uuid(access_token, case_uuid, ensemble_name)
    properties = await access.get_grid_properties_async(grid_name, realization)
    return [
        schemas.GridPropertyInfo(
            propertyName=prop.property_name,
            isoDateOrInterval=prop.iso_date_or_interval,
        )
        for prop in properties
    ]


@router.get(
    "/cases/{case_uuid}/ensembles/{ensemble_name}/grids/{grid_name}/realizations/{realization}/properties/{property_name}/blob_id"
)
# pylint: disable=too-many-arguments
async def get_grid_property_blob_id(
    authorization: str | None = Header(None, description="Authorization bearer token for Sumo API"),
    case_uuid: str = Path(description="Sumo case uuid"),
    ensemble_name: str = Path(description="Ensemble name"),
    grid_name: str = Path(description="Grid name"),
    realization: int = Path(description="Realization id"),
    property_name: str = Path(description="Property name"),
    property_iso_date_or_interval: str | None = Query(default=None, description="Time point or time interval string"),
) -> str:
    """Get the blob ID for a grid property."""
    access_token = extract_required_token(authorization)
    access = GridAccess.from_case_uuid(access_token, case_uuid, ensemble_name)
    blob_id = await access.get_grid_property_blob_id_async(
        grid_name, realization, property_name, property_iso_date_or_interval
    )
    return blob_id
