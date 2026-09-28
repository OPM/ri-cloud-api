"""Typed return values for the grid access layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GridDimensions:
    """Dimensions of a grid, including the number of cells in each direction."""

    i_count: int
    j_count: int
    k_count: int


@dataclass(frozen=True)
class GridInfo:
    """Realizations of a grid name together with the dimensions of each realization."""

    realizations: list[int]
    dimensions_per_realization: list[GridDimensions]


@dataclass(frozen=True)
class GridPropertyInfo:
    """Information about a grid property, including its name and data type."""

    property_name: str
    iso_date_or_interval: str | None = None
