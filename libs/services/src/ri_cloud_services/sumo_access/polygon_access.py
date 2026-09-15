from __future__ import annotations

import polars as pl
from fmu.datamodels.fmu_results.enums import FluidContactType
from fmu.sumo.explorer.objects import Polygons, SearchContext
from sumo.wrapper import SumoClient

from ri_cloud_services.service_exceptions import InvalidDataError, MultipleDataMatchesError, NoDataError, Service

from .polygon_types import (
    STD_RES_CONTENT,
    STD_RES_SUB_NAME_FIELD,
    DepthFaultPolygonMeta,
    FluidContactPolygonMeta,
    PolygonData,
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

    async def get_field_outline_polygon_data_async(self, realization: int) -> list[PolygonData]:
        """
        Get the polygon geometry for the `field_outline` standard result polygon in the given
        realization. There is exactly one field outline polygon per ensemble, so no name is
        needed to identify it.
        """
        document = await self._get_single_polygon_document_async(
            PolygonStandardResult.FIELD_OUTLINE, realization=realization
        )
        return _polygon_data_list_from_document(await _read_polygon_table_async(document))

    async def get_structure_depth_fault_lines_polygon_data_async(
        self, realization: int, name: str
    ) -> list[PolygonData]:
        """Get the polygon geometry for a named `structure_depth_fault_lines` polygon."""
        document = await self._get_single_polygon_document_async(
            PolygonStandardResult.STRUCTURE_DEPTH_FAULT_LINE, realization=realization, name=name
        )
        return _polygon_data_list_from_document(await _read_polygon_table_async(document))

    async def get_fluid_contact_outline_polygon_data_async(
        self, realization: int, name: str, contact_type: FluidContactType
    ) -> list[PolygonData]:
        """Get the polygon geometry for a named `fluid_contact_outline` polygon with the given contact."""
        contact_field = STD_RES_SUB_NAME_FIELD[PolygonStandardResult.FLUID_CONTACT_OUTLINE]
        document = await self._get_single_polygon_document_async(
            PolygonStandardResult.FLUID_CONTACT_OUTLINE,
            realization=realization,
            name=name,
            complex_filter={"term": {contact_field: contact_type.value}},
        )
        return _polygon_data_list_from_document(await _read_polygon_table_async(document))

    async def _get_single_polygon_document_async(
        self,
        standard_result: PolygonStandardResult,
        realization: int,
        name: str | None = None,
        complex_filter: dict | None = None,
    ) -> Polygons:
        """
        Fetch the single polygon document matching a standard result (+ name/contact) in one
        realization. Raises `NoDataError`/`MultipleDataMatchesError` if the match is not
        exactly one.
        """
        filter_kwargs: dict = {
            "realization": realization,
            "content": STD_RES_CONTENT[standard_result],
            "standard_result": standard_result.value,
        }
        if name is not None:
            filter_kwargs["name"] = name
        if complex_filter is not None:
            filter_kwargs["complex"] = complex_filter

        polygons_context = self._ensemble_context.polygons.filter(**filter_kwargs)

        match_count = await polygons_context.length_async()
        if match_count == 0:
            raise NoDataError(
                f"No polygons found in case='{self._case_uuid}', ensemble='{self._ensemble_name}', "
                f"realization={realization}, standard_result='{standard_result.value}', name={name!r}",
                Service.SUMO,
            )
        if match_count > 1:
            raise MultipleDataMatchesError(
                f"Expected a single polygon match in case='{self._case_uuid}', "
                f"ensemble='{self._ensemble_name}', realization={realization}, "
                f"standard_result='{standard_result.value}', name={name!r}, got {match_count}",
                Service.SUMO,
            )

        return await polygons_context.getitem_async(0)

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


_XYZ_ID_COLUMNS = ("X_UTME", "Y_UTMN", "Z_TVDSS", "POLY_ID")
_LEGACY_XYZ_ID_COLUMNS = ("X", "Y", "Z", "ID")
_LEGACY_TO_XYZ_ID_COLUMN_RENAME = dict(zip(_LEGACY_XYZ_ID_COLUMNS, _XYZ_ID_COLUMNS))


async def _read_polygon_table_async(document: Polygons) -> pl.DataFrame:
    """
    Read a polygon document's raw column data directly as a `polars.DataFrame`, without going
    through pandas (we only need to read/group columns, not process them). `polars` reads CSV
    and parquet natively, so no `pyarrow` dependency is required.
    """
    blob = await document.blob_async
    if document.format == "csv":
        return pl.read_csv(blob)
    if document.format == "parquet":
        return pl.read_parquet(blob)

    raise InvalidDataError(f"Unknown polygons format '{document.format}'", Service.SUMO)


def _polygon_data_list_from_document(table: pl.DataFrame) -> list[PolygonData]:
    """
    Convert a polygons table (as read by `_read_polygon_table_async`) into one `PolygonData`
    per `POLY_ID` group. A single named polygon set can contain multiple geometrically
    distinct polygons (e.g. fault networks).
    """
    if not all(column in table.columns for column in _XYZ_ID_COLUMNS):
        if all(column in table.columns for column in _LEGACY_XYZ_ID_COLUMNS):
            table = table.rename(_LEGACY_TO_XYZ_ID_COLUMN_RENAME)
        else:
            raise InvalidDataError(
                f"Invalid polygons data, expected columns {_XYZ_ID_COLUMNS}, got {table.columns}",
                Service.SUMO,
            )

    has_name = "NAME" in table.columns
    poly_ids = table.get_column("POLY_ID").to_list()
    x_arr = table.get_column("X_UTME").to_list()
    y_arr = table.get_column("Y_UTMN").to_list()
    z_arr = table.get_column("Z_TVDSS").to_list()
    names = table.get_column("NAME").to_list() if has_name else None

    row_indices_by_poly_id: dict[int | str, list[int]] = {}
    for row_index, poly_id in enumerate(poly_ids):
        row_indices_by_poly_id.setdefault(poly_id, []).append(row_index)

    polygon_data_list: list[PolygonData] = []
    for poly_id, row_indices in row_indices_by_poly_id.items():
        name = names[row_indices[0]] if names is not None else "NO_NAME_IN_METADATA"
        poly_id_value = poly_id if isinstance(poly_id, (int, str)) else str(poly_id)
        polygon_data_list.append(
            PolygonData(
                x_arr=[x_arr[i] for i in row_indices],
                y_arr=[y_arr[i] for i in row_indices],
                z_arr=[z_arr[i] for i in row_indices],
                poly_id=poly_id_value,
                name=name,
            )
        )

    return polygon_data_list
