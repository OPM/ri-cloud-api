from ri_cloud_services.sumo_access.grid_access import GridInfo

from . import schemas


def to_api_grid_info(grid_info: GridInfo) -> list[schemas.GridRealizationInfo]:
    """
    Convert a GridInfo to a schemas.GridInfo.
    """
    if len(grid_info.realizations) != len(grid_info.dimensions_per_realization):
        raise ValueError("Mismatch between realizations and dimensions")

    # Create list of schemas.GridRealizationInfo
    realization_infos = [
        schemas.GridRealizationInfo(
            realization=realization,
            dimensions=schemas.GridDimensions(
                iCount=dimensions.i_count,
                jCount=dimensions.j_count,
                kCount=dimensions.k_count,
            ),
        )
        for realization, dimensions in zip(grid_info.realizations, grid_info.dimensions_per_realization)
    ]
    return realization_infos
