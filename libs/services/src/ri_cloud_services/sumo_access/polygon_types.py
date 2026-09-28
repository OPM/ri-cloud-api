from dataclasses import dataclass
from enum import StrEnum

from fmu.datamodels.fmu_results.enums import Content, FluidContactType
from fmu.datamodels.standard_results.enums import StandardResultName


class PolygonStandardResult(StrEnum):
    FIELD_OUTLINE = StandardResultName.field_outline.value
    FLUID_CONTACT_OUTLINE = StandardResultName.fluid_contact_outline.value
    STRUCTURE_DEPTH_FAULT_LINE = StandardResultName.structure_depth_fault_lines.value


@dataclass(frozen=True, kw_only=True)
class PolygonMeta:
    name: str  # Svarte fm. top / Svarte fm. / Svarte fm. base


@dataclass(frozen=True, kw_only=True)
class FluidContactPolygonMeta(PolygonMeta):
    contact_type: FluidContactType


@dataclass(frozen=True)
class PolygonData:
    x_arr: list[float]
    y_arr: list[float]
    z_arr: list[float]
    poly_id: int | str
    name: str | None


# Sumo field holding the value that a sub_name is matched against, per standard result.
# Standard results without an entry here do not support a sub_name.
STD_RES_SUB_NAME_FIELD: dict[PolygonStandardResult, str] = {
    PolygonStandardResult.FLUID_CONTACT_OUTLINE: "data.fluid_contact.contact.keyword",
}

# Sumo `data.content` value that corresponds to each polygon standard result.
STD_RES_CONTENT: dict[PolygonStandardResult, str] = {
    PolygonStandardResult.FIELD_OUTLINE: Content.field_outline.value,
    PolygonStandardResult.FLUID_CONTACT_OUTLINE: Content.fluid_contact.value,
    PolygonStandardResult.STRUCTURE_DEPTH_FAULT_LINE: Content.fault_lines.value,
}
