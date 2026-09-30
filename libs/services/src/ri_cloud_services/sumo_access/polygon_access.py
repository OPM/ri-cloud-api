from __future__ import annotations

import polars as pl
from fmu.datamodels.fmu_results.enums import FluidContactType
from fmu.sumo.explorer.objects import Polygons, SearchContext
from sumo.wrapper import SumoClient

from ri_cloud_services.service_exceptions import InvalidDataError, MultipleDataMatchesError, NoDataError, Service

from .polygon_types import (
    STD_RES_CONTENT,
    STD_RES_INDEX_COLUMNS,
    STD_RES_SUB_NAME_FIELD,
    FluidContactPolygonMeta,
    PolygonData,
    PolygonMeta,
    PolygonStandardResult,
)
from .sumo_client_factory import create_sumo_client

_NAME_COMPOSITE_SOURCE = {"name": {"terms": {"field": "data.name.keyword"}}}
_IS_STRATIGRAPHIC_SUB_AGG = {"is_stratigraphic": {"min": {"field": "data.stratigraphic"}}}

# The base geometry columns this module reads unconditionally (hardcoded, independent of
# `STD_RES_INDEX_COLUMNS`/`fmu.datamodels`). Checked separately from `STD_RES_INDEX_COLUMNS` below
# since the two can drift apart for different reasons: this one only changes if we change what
# columns we read here, the other changes if `fmu.datamodels.standard_results` changes.
_REQUIRED_POLYGONS_TABLE_IDX_COLUMNS = ("X_UTME", "Y_UTMN", "Z_TVDSS", "POLY_ID")


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
    def from_ensemble_name(cls, access_token: str, case_uuid: str, ensemble_name: str) -> PolygonsAccess:
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

        return [_polygon_meta_from_bucket(bucket) for bucket in buckets]

    async def get_structure_depth_fault_lines_polygons_meta_async(self) -> list[PolygonMeta]:
        """
        Get metadata for the `structure_depth_fault_lines` standard result polygons in this
        ensemble, unique per polygon name.

        Assumes each match is valid for every realization; per-realization existence is not
        verified here.
        """
        buckets = await self._get_composite_buckets_async(PolygonStandardResult.STRUCTURE_DEPTH_FAULT_LINE)
        return [_polygon_meta_from_bucket(bucket) for bucket in buckets]

    async def get_fluid_contact_outline_polygons_meta_async(self) -> list[FluidContactPolygonMeta]:
        """
        Get metadata for the `fluid_contact_outline` standard result polygons in this ensemble,
        unique per (polygon name, contact) combination.

        Assumes each match is valid for every realization; per-realization existence is not
        verified here.
        """
        buckets = await self._get_composite_buckets_async(PolygonStandardResult.FLUID_CONTACT_OUTLINE)
        return [_fluid_contact_polygon_meta_from_bucket(bucket) for bucket in buckets]

    async def get_field_outline_polygon_data_async(self, realization: int) -> list[PolygonData]:
        """
        Get the polygon geometry for the `field_outline` standard result polygon in the given
        realization. There is exactly one field outline polygon per ensemble, so no name is
        needed to identify it.
        """
        document = await self._get_single_polygon_document_async(
            PolygonStandardResult.FIELD_OUTLINE, realization=realization
        )

        polygon_df = await _read_polygon_document_as_df_async(document)
        _validate_polygons_df_std_res_index_columns(polygon_df, PolygonStandardResult.FIELD_OUTLINE)

        return _polygon_data_list_from_polars_df(polygon_df)

    async def get_structure_depth_fault_lines_polygon_data_async(
        self, realization: int, name: str
    ) -> list[PolygonData]:
        """Get the polygon geometry for a named `structure_depth_fault_lines` polygon."""
        document = await self._get_single_polygon_document_async(
            PolygonStandardResult.STRUCTURE_DEPTH_FAULT_LINE, realization=realization, name=name
        )

        polygon_df = await _read_polygon_document_as_df_async(document)
        _validate_polygons_df_std_res_index_columns(polygon_df, PolygonStandardResult.STRUCTURE_DEPTH_FAULT_LINE)

        return _polygon_data_list_from_polars_df(polygon_df)

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

        polygon_df = await _read_polygon_document_as_df_async(document)
        _validate_polygons_df_std_res_index_columns(polygon_df, PolygonStandardResult.FLUID_CONTACT_OUTLINE)

        return _polygon_data_list_from_polars_df(polygon_df)

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

    async def _get_composite_buckets_async(self, standard_result: PolygonStandardResult) -> list[dict]:
        """
        Aggregate the distinct polygons for a standard result across all realizations, using a
        composite terms aggregation on polygon name (+ contact sub-name for fluid contacts).
        Since a metadata match is assumed valid for every realization, this yields the full set
        of distinct polygons for the standard result without needing to iterate documents.
        """
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


def _polygon_meta_from_bucket(bucket: dict) -> PolygonMeta:
    name = bucket["key"]["name"]
    return PolygonMeta(
        name=name,
    )


def _fluid_contact_polygon_meta_from_bucket(bucket: dict) -> FluidContactPolygonMeta:
    name = bucket["key"]["name"]
    return FluidContactPolygonMeta(
        name=name,
        contact_type=FluidContactType(bucket["key"]["sub_name"]),
    )


async def _read_polygon_document_as_df_async(document: Polygons) -> pl.DataFrame:
    """
    Read a polygon document's raw column data directly as a `polars.DataFrame`,
    (we only need to read/group columns, not process them). `polars` reads CSV
    and parquet natively, so no `pyarrow` dependency is required.
    """
    blob = await document.blob_async
    if document.format == "csv":
        return pl.read_csv(blob)
    if document.format == "parquet":
        return pl.read_parquet(blob)

    raise InvalidDataError(f"Unknown polygons format '{document.format}'", Service.SUMO)


def _validate_polygons_df_std_res_index_columns(df: pl.DataFrame, standard_result: PolygonStandardResult) -> None:
    """
    Validates that the given polygons DataFrame contains all required index columns for the specified 
    standard result.
    """
    index_columns = STD_RES_INDEX_COLUMNS[standard_result]
    missing_columns = set(index_columns) - set(df.columns)
    if missing_columns:
        raise InvalidDataError(
            f"Polygons data for '{standard_result.value}' is missing required column(s) "
            f"{sorted(missing_columns)}, got {df.columns}",
            Service.SUMO,
        )


def _polygon_data_list_from_polars_df(df: pl.DataFrame) -> list[PolygonData]:
    """
    Convert a polygons df (as read by `_read_polygon_document_as_df_async`) into one `PolygonData`
    per `POLY_ID` group. A single named polygon set can contain multiple geometrically
    distinct polygons (e.g. fault networks).
    """
    missing_required_columns = set(_REQUIRED_POLYGONS_TABLE_IDX_COLUMNS) - set(df.columns)
    if missing_required_columns:
        raise InvalidDataError(
            f"Polygons data for is missing required column(s): {sorted(missing_required_columns)}, got {df.columns}",
            Service.SUMO,
        )

    has_name = "NAME" in df.columns
    poly_ids = df.get_column("POLY_ID").to_list()
    x_arr = df.get_column("X_UTME").to_list()
    y_arr = df.get_column("Y_UTMN").to_list()
    z_arr = df.get_column("Z_TVDSS").to_list()
    names = df.get_column("NAME").to_list() if has_name else None

    row_indices_by_poly_id: dict[int | str, list[int]] = {}
    for row_index, poly_id in enumerate(poly_ids):
        row_indices_by_poly_id.setdefault(poly_id, []).append(row_index)

    polygon_data_list: list[PolygonData] = []
    for poly_id, row_indices in row_indices_by_poly_id.items():
        name = names[row_indices[0]] if names is not None else None
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
