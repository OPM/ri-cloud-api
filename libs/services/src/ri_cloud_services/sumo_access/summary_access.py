"""Access class for summary / timeseries data on Sumo.

Wraps fmu-sumo-explorer summary tables so the router layer only has to
deal with simple, typed return values.
"""

from __future__ import annotations

import asyncio

from fmu.sumo.explorer.objects import SearchContext, Table

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

# Aggregation operation used for summary vectors. Must be the same when looking for an existing
# aggregation and when triggering one, or the lookup never matches what was produced.
_AGGREGATION_OPERATION = "collection"


class SummaryAccess:
    """Access summary (timeseries) data for a given Sumo case + ensemble."""

    def __init__(self, access_token: str, case_uuid: str, ensemble_name: str) -> None:
        self._access_token = access_token
        self._case_uuid = case_uuid
        self._ensemble_name = ensemble_name

    @classmethod
    def from_case_uuid(cls, access_token: str, case_uuid: str, ensemble_name: str) -> SummaryAccess:
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

        Aggregation is triggered on Sumo if no usable aggregation exists yet.

        Returns the raw Azure blob ID. The caller should authenticate using
        OAuth Bearer token (same token used for Sumo API access).
        """
        agg_table = await self._get_vector_agg_table(vector_name)

        blob_name = agg_table.metadata["_sumo"]["blob_name"]

        return blob_name

    async def _get_vector_agg_table(self, vector_name: str) -> Table:
        """Get the aggregated table for the given summary vector.

        Reuses an existing aggregation when there is one, and falls back to triggering an
        aggregation on Sumo. Triggering costs several seconds, so the fast path matters.

        Returns the aggregated table object. The caller should authenticate using
        OAuth Bearer token (same token used for Sumo API access).
        """
        case = get_case_by_uuid(self._access_token, self._case_uuid)

        sc_tables_basis = case.tables.filter(
            column=vector_name,
            ensemble=self._ensemble_name,
            standard_result="simulationtimeseries",  # TODO: Use standard_result type from fmu-data-io?
        )

        # Look for an existing aggregation. Note that this filter must not carry realization=True:
        # an object cannot be both a realization and an aggregation, so such a filter never matches.
        # SearchContext.aggregation_async() probes on the context it is called on, which is why
        # calling it on the per-realization context below always ends up re-triggering aggregation.
        sc_existing_agg_tables = sc_tables_basis.filter(aggregation=_AGGREGATION_OPERATION)
        existing_agg_table_count = await sc_existing_agg_tables.length_async()
        if existing_agg_table_count > 1:
            raise MultipleDataMatchesError(
                f"Multiple existing aggregation tables found for vector '{vector_name}' in "
                f"case='{self._case_uuid}', ensemble='{self._ensemble_name}'",
                Service.SUMO,
            )
        if existing_agg_table_count == 1:
            existing_agg_table = await sc_existing_agg_tables.single_async
            if isinstance(existing_agg_table, Table) and await self._is_agg_valid_for_reals_async(
                existing_agg_table, sc_tables_basis
            ):
                return existing_agg_table

        sc_per_real_tables = sc_tables_basis.filter(realization=True)

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
        agg_table = await sc_per_real_tables.aggregation_async(operation=_AGGREGATION_OPERATION, column=vector_name)

        if not isinstance(agg_table, Table):
            raise InvalidDataError(
                f"Did not get expected object type of Table for vector '{vector_name}'",
                Service.SUMO,
            )

        return agg_table

    @staticmethod
    async def _is_agg_valid_for_reals_async(agg_table: Table, sc_tables_basis: SearchContext) -> bool:
        """Tell whether an existing aggregation still covers all realizations.

        Realizations can be added after an aggregation was made, which leaves the aggregation
        holding a subset of the data. This is the same check SearchContext.aggregation_async()
        applies before reusing an aggregation: the realizations that existed when the aggregation
        was made must be exactly the ones it recorded, and no realization may have been added since.
        """
        try:
            recorded_realization_ids = agg_table.metadata["fmu"]["aggregation"]["realization_ids"]
            aggregation_timestamp = agg_table.metadata["_sumo"]["timestamp"]
        except KeyError:
            return False

        sc_real_tables = sc_tables_basis.filter(realization=True)

        # Neither query depends on the other's result, so run them concurrently rather than
        # paying for two sequential round-trips on every call.
        async with asyncio.TaskGroup() as tg:
            older_ids_task = tg.create_task(
                sc_real_tables.filter(
                    complex={"range": {"_sumo.timestamp": {"lt": aggregation_timestamp}}}
                ).realizationids_async
            )
            current_count_task = tg.create_task(sc_real_tables.length_async())

        realization_ids = older_ids_task.result()

        if set(realization_ids) != set(recorded_realization_ids):
            return False

        return len(realization_ids) == current_count_task.result()
