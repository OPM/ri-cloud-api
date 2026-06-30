

from fastapi import Header, Path
from ri_cloud_services.sumo_access.sumo_client_factory import create_sumo_client

from ri_cloud_api.primary.utils.router_headers import extract_required_token

from . import schemas

async def get_sas_token_and_blob_base_uri_for_blob_id_async(
    authorization: str | None = Header(None, description="Authorization bearer token for Sumo API"),
    blob_id: str = Path(description="Sumo blob id"),
) -> tuple[str, str]:
    """
    Get a SAS token and a base URI that allows reading of all children of blob_id
    The returned base uri looks something like this:
        https://xxxsumoxxx.blob.core.windows.net/{blob_id}
    """
    access_token = extract_required_token(authorization)

    sumo_client = create_sumo_client(access_token)

    sas_token, blob_store_base_uri = await get_sas_token_and_blob_base_uri_for_blob_id_async(sumo_client, blob_id)

    return schemas.BlobAccessInfo(sasToken=sas_token, blobStoreBaseUri=blob_store_base_uri)
