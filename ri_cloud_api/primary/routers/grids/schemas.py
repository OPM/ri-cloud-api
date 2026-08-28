from pydantic import BaseModel


class GridPropertyInfo(BaseModel):
    propertyName: str
    isoDateOrInterval: str | None = None


class GridDimensions(BaseModel):
    iCount: int
    jCount: int
    kCount: int


class GridRealizationInfo(BaseModel):
    realization: int
    dimensions: GridDimensions
