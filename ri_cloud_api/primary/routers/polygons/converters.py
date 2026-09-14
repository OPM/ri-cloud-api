"""Converters from service-layer polygon dataclasses to router-layer pydantic schemas."""

from __future__ import annotations

from ri_cloud_services.sumo_access import polygon_types

from . import schemas


def to_api_field_outline_meta(polygon_meta: polygon_types.PolygonMeta) -> schemas.PolygonMeta:
    return schemas.PolygonMeta(name=polygon_meta.name)


def to_api_depth_fault_polygon_meta(polygon_meta: polygon_types.DepthFaultPolygonMeta) -> schemas.DepthFaultPolygonMeta:
    return schemas.DepthFaultPolygonMeta(
        name=polygon_meta.name,
        name_is_stratigraphic_offical=polygon_meta.name_is_stratigraphic_offical,
        stratigraphic_identifier=polygon_meta.stratigraphic_identifier,
    )


def to_api_fluid_contact_polygon_meta(polygon_meta: polygon_types.FluidContactPolygonMeta) -> schemas.FluidContactPolygonMeta:
    return schemas.FluidContactPolygonMeta(
        name=polygon_meta.name,
        name_is_stratigraphic_offical=polygon_meta.name_is_stratigraphic_offical,
        stratigraphic_identifier=polygon_meta.stratigraphic_identifier,
        contact_type=polygon_meta.contact_type,
    )


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
        directory[polygon_types.PolygonStandardResult.FIELD_OUTLINE.value] = [
            to_api_field_outline_meta(meta) for meta in field_outline_meta
        ]

    if structure_depth_fault_lines_meta:
        directory[polygon_types.PolygonStandardResult.STRUCTURE_DEPTH_FAULT_LINE.value] = [
            to_api_depth_fault_polygon_meta(meta) for meta in structure_depth_fault_lines_meta
        ]

    if fluid_contact_outline_meta:
        directory[polygon_types.PolygonStandardResult.FLUID_CONTACT_OUTLINE.value] = [
            to_api_fluid_contact_polygon_meta(meta) for meta in fluid_contact_outline_meta
        ]

    return directory
