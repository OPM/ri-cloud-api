from enum import StrEnum

from pydantic import BaseModel


class PolygonResult(StrEnum):
    """
    API-layer identifier for a category of polygons, decoupled from Sumo's
    ``PolygonStandardResult``/FMU standard-result terminology. Currently mirrors it 1:1, but is
    free to diverge in the future without changing the Sumo-specific access layer.
    """

    FIELD_OUTLINE = "field_outline"
    STRUCTURE_DEPTH_FAULT_LINE = "structure_depth_fault_lines"
    FLUID_CONTACT_OUTLINE = "fluid_contact_outline"


class PolygonMeta(BaseModel):
    name: str  # Svarte fm. top / Svarte fm. / Svarte fm. base

class FluidContactPolygonMeta(PolygonMeta):
    contactType: str  # fwl / owc / goc / gwc

class PolygonData(BaseModel):
    xUtmEArr: list[float]
    yUtmNArray: list[float]
    zTvdSSArray: list[float]
    polyId: int | str
    name: str | None
