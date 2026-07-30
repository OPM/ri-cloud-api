from pydantic import BaseModel


class BlobAccessInfo(BaseModel):
    """info needed to access a blob in the blob store"""

    sasToken: str
    blobStoreBaseUri: str
