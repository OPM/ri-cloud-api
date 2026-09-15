"""Converters from service-layer polygon dataclasses to router-layer pydantic schemas."""

from __future__ import annotations

from fmu.datamodels.fmu_results.enums import FluidContactType
from ri_cloud_services.sumo_access import polygon_types

from . import schemas


def fluid_contact_type_from_api_str(contact_type: str) -> FluidContactType | None:
    """Convert the API-layer plain-string contact type to a service-layer FluidContactType.

    Returns None if the string does not match a known fluid contact type.
    """
    if contact_type in FluidContactType.__members__:
        return FluidContactType(contact_type)
    return None


def to_api_field_outline_meta(polygon_meta: polygon_types.PolygonMeta) -> schemas.PolygonMeta:
    return schemas.PolygonMeta(name=polygon_meta.name)


def to_api_depth_fault_polygon_meta(polygon_meta: polygon_types.DepthFaultPolygonMeta) -> schemas.DepthFaultPolygonMeta:
    return schemas.DepthFaultPolygonMeta(
        name=polygon_meta.name,
        nameIsStratigraphicOffical=polygon_meta.name_is_stratigraphic_offical,
        stratigraphicIdentifier=polygon_meta.stratigraphic_identifier,
    )


def to_api_fluid_contact_polygon_meta(
    polygon_meta: polygon_types.FluidContactPolygonMeta,
) -> schemas.FluidContactPolygonMeta:
    return schemas.FluidContactPolygonMeta(
        name=polygon_meta.name,
        nameIsStratigraphicOffical=polygon_meta.name_is_stratigraphic_offical,
        stratigraphicIdentifier=polygon_meta.stratigraphic_identifier,
        contactType=polygon_meta.contact_type.value,
    )


def to_api_polygons_data(polygon_data: polygon_types.PolygonData) -> schemas.PolygonData:
    return schemas.PolygonData(
        xUtmEArr=polygon_data.x_arr,
        yUtmNArray=polygon_data.y_arr,
        zTvdSSArray=polygon_data.z_arr,
        polyId=polygon_data.poly_id,
        name=polygon_data.name,
    )


def to_api_polygons_data_list(polygons_data_list: list[polygon_types.PolygonData]) -> list[schemas.PolygonData]:
    return [to_api_polygons_data(polygons_data) for polygons_data in polygons_data_list]


def to_api_polygons_directory(
    field_outline_meta: list[polygon_types.PolygonMeta],
    structure_depth_fault_lines_meta: list[polygon_types.DepthFaultPolygonMeta],
    fluid_contact_outline_meta: list[polygon_types.FluidContactPolygonMeta],
) -> dict[str, list[schemas.PolygonMeta] | list[schemas.DepthFaultPolygonMeta] | list[schemas.FluidContactPolygonMeta]]:
    """Assemble the per-standard-result metadata lists into the API directory response.

    A standard result with no matches is omitted from the returned dict.
    """
    directory: dict[
        str, list[schemas.PolygonMeta] | list[schemas.DepthFaultPolygonMeta] | list[schemas.FluidContactPolygonMeta]
    ] = {}

    if field_outline_meta:
        directory[schemas.PolygonResult.FIELD_OUTLINE.value] = [
            to_api_field_outline_meta(meta) for meta in field_outline_meta
        ]

    if structure_depth_fault_lines_meta:
        directory[schemas.PolygonResult.STRUCTURE_DEPTH_FAULT_LINE.value] = [
            to_api_depth_fault_polygon_meta(meta) for meta in structure_depth_fault_lines_meta
        ]

    if fluid_contact_outline_meta:
        directory[schemas.PolygonResult.FLUID_CONTACT_OUTLINE.value] = [
            to_api_fluid_contact_polygon_meta(meta) for meta in fluid_contact_outline_meta
        ]

    return directory
