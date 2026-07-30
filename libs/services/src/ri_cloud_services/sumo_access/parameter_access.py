"""Access class for summary / timeseries data on Sumo.

Wraps fmu-sumo-explorer summary tables so the router layer only has to
deal with simple, typed return values.
"""

from __future__ import annotations

from fmu.sumo.explorer.objects import Table

from ri_cloud_services.service_exceptions import (
    InvalidDataError,
    NoDataError,
    Service,
    ServiceRequestError,
)

from ._explorer import get_case_by_uuid


class ParameterAccess:
    """Access parameter data for a given Sumo case + ensemble."""

    def __init__(self, access_token: str, case_uuid: str, ensemble_name: str) -> None:
        self._access_token = access_token
        self._case_uuid = case_uuid
        self._ensemble_name = ensemble_name

    @classmethod
    def from_case_uuid(cls, access_token: str, case_uuid: str, ensemble_name: str) -> ParameterAccess:
        return cls(access_token=access_token, case_uuid=case_uuid, ensemble_name=ensemble_name)

    async def get_parameters_blob_id_async(self) -> str:
        """Get the blob ID for the given parameter table

        The temporary solution is not optimized, so we trigger aggregation to ensure the blob ID is available, this triggers an aggregation

        Returns the raw Azure blob ID. The caller should authenticate using
        OAuth Bearer token (same token used for Sumo API access).
        """
        parameter_agg = await self.get_parameters_agg_table_async()

        blob_name = parameter_agg.metadata["_sumo"]["blob_name"]

        return blob_name

    async def get_parameters_agg_table_async(self) -> Table:
        """Get the aggregated table for the given parameter table

        The temporary solution is not optimized, so we trigger aggregation to ensure the aggregated table is available, this triggers an aggregation

        Returns the aggregated table object. The caller should authenticate using
        OAuth Bearer token (same token used for Sumo API access).
        """

        case = get_case_by_uuid(self._access_token, self._case_uuid)

        sc_ensemble = case.filter(ensemble=self._ensemble_name)
        sc_parameters_per_real = sc_ensemble.filter(realization=True, aggregation=False).parameters

        realization_count = await sc_parameters_per_real.length_async()
        if realization_count == 0:
            raise NoDataError(
                f"No parameters found for case {self._case_uuid} and ensemble {self._ensemble_name}",
                Service.SUMO,
            )

        sc_param_table = sc_ensemble.parameters
        try:
            # Trigger aggregation if not existing
            parameter_agg = await sc_param_table.aggregation_async(operation="collection")
        except Exception as exp:
            raise ServiceRequestError(
                f"Parameter aggregation failed for case {self._case_uuid} and ensemble {self._ensemble_name}",
                Service.SUMO,
            ) from exp

        if not isinstance(parameter_agg, Table):
            raise InvalidDataError(
                "Did not get expected object type of Table for parameter aggregation",
                Service.SUMO,
            )

        return parameter_agg
