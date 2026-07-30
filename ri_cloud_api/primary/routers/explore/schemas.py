from pydantic import BaseModel


class AssetInfo(BaseModel):
    name: str


class CaseInfo(BaseModel):
    # Could add ensemble info here, to avoid an extra query per case
    id: str
    name: str
    asset: str | None = None
    field: str | None = None
    status: str | None = None
    user: str | None = None


class EnsembleInfo(BaseModel):
    # Could include realization ids once we can get them cheaply per ensemble
    name: str
