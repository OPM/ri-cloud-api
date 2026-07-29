from __future__ import annotations

import asyncio
from typing import Optional
from fmu.sumo.explorer.objects import CPGrid
from fmu.sumo.explorer import TimeFilter, TimeType

from ri_cloud_core_utils.timestamp_utils import (
    iso_str_to_date_str,
    timestamp_utc_ms_to_iso_str,
)
from ri_cloud_services.service_exceptions import (
    InvalidDataError,
    InvalidParameterError,
    MultipleDataMatchesError,
    NoDataError,
    Service,
)

from ._explorer import get_case_by_uuid
from .grid_types import GridInfo, GridPropertyInfo


def get_time_filter(time_or_interval_str: Optional[str]) -> TimeFilter:
    """Convert a time_or_interval_str to a TimeFilter."""
    if time_or_interval_str is None:
        time_filter = TimeFilter(TimeType.NONE)

    else:
        timestamp_arr = time_or_interval_str.split("/", 1)
        if timestamp_arr[0] == "" or (len(timestamp_arr) == 2 and timestamp_arr[1] == ""):
            raise InvalidParameterError(
                "time_or_interval_str must contain a single timestamp or interval",
                Service.SUMO,
            )
        if len(timestamp_arr) == 1:
            time_filter = TimeFilter(
                TimeType.TIMESTAMP,
                start=timestamp_arr[0],
                end=timestamp_arr[0],
                exact=True,
            )
        else:
            time_filter = TimeFilter(
                TimeType.INTERVAL,
                start=timestamp_arr[0],
                end=timestamp_arr[1],
                exact=True,
            )
    return time_filter


class GridAccess:
    """Access grid data for a given Sumo case + ensemble."""

    def __init__(self, access_token: str, case_uuid: str, ensemble_name: str) -> None:
        self._access_token = access_token
        self._case_uuid = case_uuid
        self._ensemble_name = ensemble_name

    @classmethod
    def from_case_uuid(cls, access_token: str, case_uuid: str, ensemble_name: str) -> "GridAccess":
        return cls(access_token=access_token, case_uuid=case_uuid, ensemble_name=ensemble_name)

    async def get_available_grid_info_list_async(self) -> list[GridInfo]:
        """Return the list of available grids with their realizations."""
        case = get_case_by_uuid(self._access_token, self._case_uuid)

        grid_context = case.grids.grids.filter(ensemble=self._ensemble_name)
        if await grid_context.length_async() == 0:
            raise NoDataError(
                f"No grid tables found for ensemble '{self._ensemble_name}' " f"in case '{self._case_uuid}'",
                Service.SUMO,
            )

        grid_names = await grid_context.names_async

        grid_infos: list[GridInfo] = []
        for grid_name in grid_names:
            realization_context = grid_context.filter(name=grid_name, realization=True)
            realization_ids = await realization_context.realizationids_async
            grid_infos.append(
                GridInfo(
                    name=grid_name,
                    realizations=sorted(int(r) for r in realization_ids),
                )
            )
        return grid_infos

    async def get_grid_blob_id_async(self, grid_name: str, realization: int) -> str:
        """Get the blob ID for the grid data for the given case + ensemble."""
        case = get_case_by_uuid(self._access_token, self._case_uuid)

        grid_context = case.grids.filter(ensemble=self._ensemble_name, name=grid_name, realization=realization)
        num_grids = await grid_context.length_async()

        if num_grids == 0:
            raise NoDataError(
                f"No grid table named '{grid_name}' found for ensemble '{self._ensemble_name}' "
                f"in case '{self._case_uuid}', and realization {realization}",
                Service.SUMO,
            )

        # Expect unique grid:
        if num_grids != 1:
            raise MultipleDataMatchesError(
                f"Expected exactly one grid with name '{grid_name}', found {num_grids}",
                Service.SUMO,
            )

        grid_document = await grid_context.getitem_async(0)
        if not isinstance(grid_document, CPGrid):
            raise InvalidDataError(f"Expected CPGrid, got {type(grid_document)}", Service.SUMO)

        blob_id = grid_document.metadata["_sumo"]["blob_name"]
        return blob_id

    async def get_grid_properties_async(self, grid_name: str, realization: int) -> list[GridPropertyInfo]:
        """Get the properties for a grid.

        The valid timestamps/intervals are resolved per property using composite aggregations, so that
        each property only reports the time points/intervals that actually exist for that property.
        """
        case = get_case_by_uuid(self._access_token, self._case_uuid)

        grid_context = case.grids.filter(ensemble=self._ensemble_name, name=grid_name, realization=realization)
        if await grid_context.length_async() == 0:
            raise NoDataError(
                f"No grid table named '{grid_name}' found for ensemble '{self._ensemble_name}' "
                f"in case '{self._case_uuid}', and realization {realization}",
                Service.SUMO,
            )

        # Expect unique grid:
        if len(grid_context) != 1:
            raise MultipleDataMatchesError(
                f"Expected exactly one grid with name '{grid_name}', found {len(grid_context)}",
                Service.SUMO,
            )

        grid_document = await grid_context.getitem_async(0)
        if not isinstance(grid_document, CPGrid):
            raise InvalidDataError(f"Expected CPGrid, got {type(grid_document)}", Service.SUMO)

        no_time_context = grid_document.grid_properties.filter(time=TimeFilter(time_type=TimeType.NONE))
        timestamp_context = grid_document.grid_properties.filter(time=TimeFilter(time_type=TimeType.TIMESTAMP))
        interval_context = grid_document.grid_properties.filter(time=TimeFilter(time_type=TimeType.INTERVAL))

        async with asyncio.TaskGroup() as tg:
            no_time_property_names_task = tg.create_task(no_time_context.names_async)
            timestamp_buckets_task = tg.create_task(
                timestamp_context.get_composite_agg_async({"name": "data.name.keyword", "t0": "data.time.t0.value"})
            )
            interval_buckets_task = tg.create_task(
                interval_context.get_composite_agg_async(
                    {
                        "name": "data.name.keyword",
                        "t0": "data.time.t0.value",
                        "t1": "data.time.t1.value",
                    }
                )
            )

        no_time_property_names = no_time_property_names_task.result()
        timestamp_buckets = timestamp_buckets_task.result()
        interval_buckets = interval_buckets_task.result()

        property_info_arr: list[GridPropertyInfo] = []

        for property_name in no_time_property_names:
            property_info_arr.append(GridPropertyInfo(property_name=property_name, iso_date_or_interval=None))

        # Each bucket is a unique (property name, timestamp) combination that actually exists in Sumo.
        # The time field values are returned as epoch milliseconds by the composite aggregation.
        for bucket in timestamp_buckets:
            property_info_arr.append(
                GridPropertyInfo(
                    property_name=bucket["name"],
                    iso_date_or_interval=iso_str_to_date_str(timestamp_utc_ms_to_iso_str(bucket["t0"])),
                )
            )

        # Each bucket is a unique (property name, interval) combination that actually exists in Sumo.
        for bucket in interval_buckets:
            start_date = iso_str_to_date_str(timestamp_utc_ms_to_iso_str(bucket["t0"]))
            end_date = iso_str_to_date_str(timestamp_utc_ms_to_iso_str(bucket["t1"]))
            property_info_arr.append(
                GridPropertyInfo(
                    property_name=bucket["name"],
                    iso_date_or_interval=f"{start_date}/{end_date}",
                )
            )

        return property_info_arr

    async def get_grid_property_blob_id_async(
        self,
        grid_name: str,
        realization: int,
        property_name: str,
        iso_date_or_interval: str | None,
    ) -> str:
        """Get the blob ID for a grid property."""
        case = get_case_by_uuid(self._access_token, self._case_uuid)

        grid_context = case.grids.filter(ensemble=self._ensemble_name, name=grid_name, realization=realization)
        num_grids = await grid_context.length_async()

        if num_grids == 0:
            raise NoDataError(
                f"No grid table named '{grid_name}' found for ensemble '{self._ensemble_name}' "
                f"in case '{self._case_uuid}', and realization {realization}",
                Service.SUMO,
            )

        # Expect unique grid:
        if num_grids != 1:
            raise MultipleDataMatchesError(
                f"Expected exactly one grid with name '{grid_name}', found {num_grids}",
                Service.SUMO,
            )

        grid_document = await grid_context.getitem_async(0)
        if not isinstance(grid_document, CPGrid):
            raise InvalidDataError(f"Expected CPGrid, got {type(grid_document)}", Service.SUMO)

        time_filter = get_time_filter(iso_date_or_interval)

        property_context = grid_document.grid_properties.filter(name=property_name, time=time_filter)
        if await property_context.length_async() == 0:
            raise NoDataError(
                f"No grid property named '{property_name}' with time='{iso_date_or_interval}' found for grid '{grid_name}', ensemble '{self._ensemble_name}', case '{self._case_uuid}', and realization {realization}",
                Service.SUMO,
            )

        # Expect unique property:
        num_grid_properties = await property_context.length_async()
        if num_grid_properties != 1:
            raise MultipleDataMatchesError(
                f"Expected exactly one grid property with name='{property_name}' and time='{iso_date_or_interval}', found {num_grid_properties}",
                Service.SUMO,
            )

        grid_property = await property_context.getitem_async(0)
        blob_id = grid_property.metadata["_sumo"]["blob_name"]
        return blob_id
