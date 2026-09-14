from __future__ import annotations

from fmu.datamodels.fmu_results.enums import FluidContactType
from fmu.sumo.explorer.objects import SearchContext
from sumo.wrapper import SumoClient

from ri_cloud_services.service_exceptions import MultipleDataMatchesError, Service

from .polygon_types import (
    STD_RES_CONTENT,
    STD_RES_SUB_NAME_FIELD,
    DepthFaultPolygonMeta,
    FluidContactPolygonMeta,
    PolygonMeta,
    PolygonStandardResult,
)
from .sumo_client_factory import create_sumo_client

_NAME_COMPOSITE_SOURCE = {"name": {"terms": {"field": "data.name.keyword"}}}
_IS_STRATIGRAPHIC_SUB_AGG = {"is_stratigraphic": {"min": {"field": "data.stratigraphic"}}}


class PolygonsAccess:
    """
    Access class for retrieving sets of polygons from Sumo.

    This class handles polygons stored as individual items in dataio/sumo.
    In practice these are polygon sets, such as fault networks, where each
    polygon object in Sumo contains multiple geometrically distinct polygons
    grouped by POLY_ID. The polygons are defined in UTM coordinates
    (X_UTME, Y_UTMN, Z_TVDSS).
    """

    def __init__(self, sumo_client: SumoClient, case_uuid: str, ensemble_name: str):
        self._sumo_client = sumo_client
        self._case_uuid: str = case_uuid
        self._ensemble_name: str = ensemble_name
        self._ensemble_context = SearchContext(sumo=self._sumo_client).filter(
            uuid=self._case_uuid, ensemble=self._ensemble_name
        )

    @classmethod
    def from_ensemble_name(cls, access_token: str, case_uuid: str, ensemble_name: str) -> "PolygonsAccess":
        sumo_client = create_sumo_client(access_token)
        return cls(sumo_client=sumo_client, case_uuid=case_uuid, ensemble_name=ensemble_name)

    async def get_field_outline_polygons_meta_async(self) -> list[PolygonMeta]:
        """
        Get metadata for the `field_outline` standard result polygon in this ensemble.

        There should be exactly one distinct polygon name across all realizations; raises
        `MultipleDataMatchesError` if more than one is found. Assumes the match is valid for
        every realization; per-realization existence is not verified here.
        """
        buckets = await self._get_composite_buckets_async(PolygonStandardResult.FIELD_OUTLINE)

        if len(buckets) > 1:
            raise MultipleDataMatchesError(
                f"Expected a single field outline polygon name in case='{self._case_uuid}', "
                f"ensemble='{self._ensemble_name}', got {[bucket['key']['name'] for bucket in buckets]}",
                Service.SUMO,
            )

        return [PolygonMeta(name=bucket["key"]["name"]) for bucket in buckets]

    async def get_structure_depth_fault_lines_polygons_meta_async(self) -> list[DepthFaultPolygonMeta]:
        """
        Get metadata for the `structure_depth_fault_lines` standard result polygons in this
        ensemble, unique per polygon name.

        Assumes each match is valid for every realization; per-realization existence is not
        verified here.
        """
        buckets = await self._get_composite_buckets_async(PolygonStandardResult.STRUCTURE_DEPTH_FAULT_LINE)
        return [_depth_fault_polygon_meta_from_bucket(bucket) for bucket in buckets]

    async def get_fluid_contact_outline_polygons_meta_async(self) -> list[FluidContactPolygonMeta]:
        """
        Get metadata for the `fluid_contact_outline` standard result polygons in this ensemble,
        unique per (polygon name, contact) combination.

        Assumes each match is valid for every realization; per-realization existence is not
        verified here.
        """
        buckets = await self._get_composite_buckets_async(PolygonStandardResult.FLUID_CONTACT_OUTLINE)
        return [_fluid_contact_polygon_meta_from_bucket(bucket) for bucket in buckets]

    async def _get_composite_buckets_async(self, standard_result: PolygonStandardResult) -> list[dict]:
        search_context = self._ensemble_context.polygons.filter(
            stage="realization",
            realization=True,
            aggregation=False,
            content=STD_RES_CONTENT[standard_result],
            standard_result=standard_result.value,
        )

        sources = [_NAME_COMPOSITE_SOURCE]
        sub_name_field = STD_RES_SUB_NAME_FIELD.get(standard_result)
        if sub_name_field is not None:
            sources.append({"sub_name": {"terms": {"field": sub_name_field}}})

        return await search_context.get_composite_buckets_async(
            sources=sources,
            sub_aggs=_IS_STRATIGRAPHIC_SUB_AGG,
        )


def _depth_fault_polygon_meta_from_bucket(bucket: dict) -> DepthFaultPolygonMeta:
    name = bucket["key"]["name"]
    is_stratigraphic = bucket["is_stratigraphic"]["value"] == 1
    return DepthFaultPolygonMeta(
        name=name,
        name_is_stratigraphic_offical=is_stratigraphic,
        stratigraphic_identifier=name if is_stratigraphic else None,
    )


def _fluid_contact_polygon_meta_from_bucket(bucket: dict) -> FluidContactPolygonMeta:
    name = bucket["key"]["name"]
    is_stratigraphic = bucket["is_stratigraphic"]["value"] == 1
    return FluidContactPolygonMeta(
        name=name,
        name_is_stratigraphic_offical=is_stratigraphic,
        stratigraphic_identifier=name if is_stratigraphic else None,
        contact_type=FluidContactType(bucket["key"]["sub_name"]),
    )
