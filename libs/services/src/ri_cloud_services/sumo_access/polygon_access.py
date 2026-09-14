from __future__ import annotations

from fmu.datamodels.fmu_results.enums import FluidContactType
from fmu.sumo.explorer.objects import Polygons, SearchContext
from sumo.wrapper import SumoClient

from ri_cloud_services.service_exceptions import MultipleDataMatchesError, NoDataError, Service

from .polygon_types import (
    STD_RES_CONTENT,
    DepthFaultPolygonMeta,
    FluidContactPolygonMeta,
    PolygonMeta,
    PolygonStandardResult,
)
from .sumo_client_factory import create_sumo_client


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

        There should be exactly one distinct polygon name; raises `MultipleDataMatchesError`
        if more than one is found. Assumes the match is valid for every realization;
        per-realization existence is not verified here.
        """
        documents = await self._get_single_realization_polygons_documents_async(PolygonStandardResult.FIELD_OUTLINE)

        if len(documents) > 1:
            raise MultipleDataMatchesError(
                f"Expected a single field outline polygon name in case='{self._case_uuid}', "
                f"ensemble='{self._ensemble_name}', got {[document.name for document in documents]}",
                Service.SUMO,
            )

        return [PolygonMeta(name=document.name) for document in documents]

    async def get_structure_depth_fault_lines_polygons_meta_async(self) -> list[DepthFaultPolygonMeta]:
        """
        Get metadata for the `structure_depth_fault_lines` standard result polygons in this
        ensemble, unique per polygon name.

        Assumes each match is valid for every realization; per-realization existence is not
        verified here.
        """
        documents = await self._get_single_realization_polygons_documents_async(
            PolygonStandardResult.STRUCTURE_DEPTH_FAULT_LINE
        )
        return [_depth_fault_polygon_meta_from_document(document) for document in documents]

    async def get_fluid_contact_outline_polygons_meta_async(self) -> list[FluidContactPolygonMeta]:
        """
        Get metadata for the `fluid_contact_outline` standard result polygons in this ensemble,
        unique per (polygon name, contact) combination.

        Assumes each match is valid for every realization; per-realization existence is not
        verified here.
        """
        documents = await self._get_single_realization_polygons_documents_async(
            PolygonStandardResult.FLUID_CONTACT_OUTLINE
        )
        return [_fluid_contact_polygon_meta_from_document(document) for document in documents]

    async def _get_single_realization_polygons_documents_async(
        self, standard_result: PolygonStandardResult
    ) -> list[Polygons]:
        """
        Fetch the polygon documents for a standard result within a single, arbitrary
        realization (no aggregation is performed). Since a metadata match is assumed valid for
        every realization, one realization is enough to discover the full set of distinct
        polygons for the standard result.
        """
        realization_ids = await self._ensemble_context.realizationids_async
        if not realization_ids:
            raise NoDataError(
                f"No realizations found in case='{self._case_uuid}', ensemble='{self._ensemble_name}'",
                Service.SUMO,
            )

        polygons_context = self._ensemble_context.polygons.filter(
            realization=realization_ids[0],
            content=STD_RES_CONTENT[standard_result],
            standard_result=standard_result.value,
        )

        documents: list[Polygons] = []
        sumo_polygons_object: Polygons
        async for sumo_polygons_object in polygons_context:
            documents.append(sumo_polygons_object)

        return documents


def _depth_fault_polygon_meta_from_document(document: Polygons) -> DepthFaultPolygonMeta:
    name = document.name
    is_stratigraphic = bool(document.stratigraphic)
    return DepthFaultPolygonMeta(
        name=name,
        name_is_stratigraphic_offical=is_stratigraphic,
        stratigraphic_identifier=name if is_stratigraphic else None,
    )


def _fluid_contact_polygon_meta_from_document(document: Polygons) -> FluidContactPolygonMeta:
    name = document.name
    is_stratigraphic = bool(document.stratigraphic)
    contact = document.get_property("data.fluid_contact.contact")
    return FluidContactPolygonMeta(
        name=name,
        name_is_stratigraphic_offical=is_stratigraphic,
        stratigraphic_identifier=name if is_stratigraphic else None,
        contact_type=FluidContactType(contact),
    )
