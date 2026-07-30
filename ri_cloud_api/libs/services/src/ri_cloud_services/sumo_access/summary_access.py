"""Access class for summary / timeseries data on Sumo.

Wraps fmu-sumo-explorer summary tables so the router layer only has to
deal with simple, typed return values.
"""

from __future__ import annotations

from fmu.sumo.explorer.objects import Table

from ri_cloud_services.service_exceptions import (
    InvalidDataError,
    MultipleDataMatchesError,
    NoDataError,
    Service,
)

from ._explorer import get_case_by_uuid

# Non-vector columns that may appear in a summary table and should be filtered
# out when listing available vectors.
_SUMMARY_METADATA_COLUMNS = {"DATE", "REAL", "ENSEMBLE", "ITER"}


class SummaryAccess:
    """Access summary (timeseries) data for a given Sumo case + ensemble."""

    def __init__(self, access_token: str, case_uuid: str, ensemble_name: str) -> None:
        self._access_token = access_token
        self._case_uuid = case_uuid
        self._ensemble_name = ensemble_name

    @classmethod
    def from_case_uuid(cls, access_token: str, case_uuid: str, ensemble_name: str) -> "SummaryAccess":
        return cls(access_token=access_token, case_uuid=case_uuid, ensemble_name=ensemble_name)

    async def get_available_vectors_async(self) -> list[str]:
        """Return the list of available summary vector names.

        Uses the summary table associated with the ensemble. Metadata
        columns (DATE, REAL, ENSEMBLE, ITER) are filtered out.
        """
        case = get_case_by_uuid(self._access_token, self._case_uuid)

        table_context = case.tables.filter(ensemble=self._ensemble_name, standard_result="simulationtimeseries")

        if await table_context.length_async() == 0:
            raise NoDataError(
                f"No summary tables found for ensemble '{self._ensemble_name}' in case '{self._case_uuid}'",
                Service.SUMO,
            )

        table_names = await table_context.names_async
        if len(table_names) == 0:
            raise NoDataError(
                f"No summary tables found in case={self._case_uuid}, ensemble={self._ensemble_name}",
                Service.SUMO,
            )
        if len(table_names) > 1:
            raise MultipleDataMatchesError(
                f"Multiple summary tables found in case={self._case_uuid}, ensemble={self._ensemble_name}: {table_names=}",
                Service.SUMO,
            )

        column_names = await table_context.columns_async

        # Get set of columns names, not among ["YEARS", "DATE", "REAL"]
        vector_names = list(set(column_names) - _SUMMARY_METADATA_COLUMNS)
        return vector_names

    async def get_vector_blob_id_async(self, vector_name: str) -> str:
        """Get the blob ID for the given summary vector.

        The temporary solution is not optimized, so we trigger aggregation to ensure the blob ID is available,
        this triggers an aggregation

        Returns the raw Azure blob ID. The caller should authenticate using
        OAuth Bearer token (same token used for Sumo API access).
        """
        agg_table = await self._get_vector_agg_table(vector_name)

        blob_name = agg_table.metadata["_sumo"]["blob_name"]

        return blob_name

    async def _get_vector_agg_table(self, vector_name: str) -> Table:
        """Get the aggregated table for the given summary vector.

        The temporary solution is not optimized, so we trigger aggregation to ensure the aggregated table is available,
        this triggers an aggregation

        Returns the aggregated table object. The caller should authenticate using
        OAuth Bearer token (same token used for Sumo API access).
        """
        case = get_case_by_uuid(self._access_token, self._case_uuid)

        sc_per_real_tables = case.tables.filter(
            ensemble=self._ensemble_name,
            column=vector_name,
            standard_result="simulationtimeseries",  # TODO: Use standard_result type from fmu-data-io?
            realization=True,
        )

        table_names = await sc_per_real_tables.names_async
        num_tables = len(table_names)
        if num_tables == 0:
            raise NoDataError(
                f"No tables found for vector '{vector_name}' in case='{self._case_uuid}', ensemble='{self._ensemble_name}'",
                Service.SUMO,
            )
        if num_tables > 1:
            raise MultipleDataMatchesError(
                f"Multiple tables found for vector '{vector_name}' in case='{self._case_uuid}', ensemble='{self._ensemble_name}': {table_names}",
                Service.SUMO,
            )

        # Trigger aggregation if not existing
        agg_table = await sc_per_real_tables.aggregation_async(operation="collection", column=vector_name)

        if not isinstance(agg_table, Table):
            raise InvalidDataError(
                f"Did not get expected object type of Table for vector '{vector_name}'",
                Service.SUMO,
            )

        return agg_table
