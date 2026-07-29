"""Shared Sumo Explorer wiring.

 Explorer wiring for this process.
 The case-lookup helper centralizes error handling so individual accessors don't need to repeat it.
"""

from __future__ import annotations

import logging

from fmu.sumo.explorer import Explorer
from fmu.sumo.explorer.objects import Case

from ri_cloud_services.services_config import get_services_config
from ri_cloud_services.service_exceptions import NoDataError, Service

logger = logging.getLogger("ri_cloud_api.sumo_access")

def get_explorer(access_token: str) -> Explorer:
    """Return a process-wide cached Explorer instance."""
    services_config = get_services_config()

    return Explorer(env=services_config.sumo_env, token=access_token)


def get_case_by_uuid(access_token: str, case_uuid: str) -> Case:
    """Look up a Sumo case by uuid.

    Raises NoDataError if the case cannot be found.
    """
    try:
        return get_explorer(access_token).get_case_by_uuid(case_uuid)
    except Exception as exc:  # fmu-sumo raises a variety of error types
        raise NoDataError(f"Case '{case_uuid}' not found: {exc}", Service.SUMO) from exc
