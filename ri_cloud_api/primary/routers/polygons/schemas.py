from fmu.datamodels.fmu_results.enums import FluidContactType
from pydantic import BaseModel


class PolygonMeta(BaseModel):
    name: str  # Svarte fm. top / Svarte fm. / Svarte fm. base


class DepthFaultPolygonMeta(PolygonMeta):
    name_is_stratigraphic_offical: bool
    stratigraphic_identifier: str | None = None  # Svarte fm.


class FluidContactPolygonMeta(DepthFaultPolygonMeta):
    contact_type: FluidContactType
