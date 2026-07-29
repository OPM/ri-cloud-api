"""Parameters router.

Exposes endpoints for discovering and (eventually) fetching parameters
data from Sumo. All Sumo Explorer interactions are delegated
to ``ParameterAccess`` in the service layer.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, Path

from ri_cloud_services.sumo_access.parameter_access import ParameterAccess

from ri_cloud_api.primary.utils.router_headers import extract_required_token

router = APIRouter(tags=["parameters"])


@router.get("/cases/{case_uuid}/ensembles/{ensemble_name}/parameters/blob_id")
async def get_parameters_blob_id(
    authorization: str | None = Header(None, description="Authorization bearer token for Sumo API"),
    case_uuid: str = Path(description="Sumo case uuid"),
    ensemble_name: str = Path(description="Ensemble name"),
) -> str:
    """Get the blob ID for the parameters table for the given case + ensemble"""
    access_token = extract_required_token(authorization)
    access = ParameterAccess.from_case_uuid(access_token, case_uuid, ensemble_name)

    blob_id = await access.get_parameters_blob_id_async()
    return blob_id
