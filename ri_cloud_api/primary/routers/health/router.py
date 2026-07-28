"""
Health-check router.
"""

from fastapi import APIRouter

from . import schemas

router = APIRouter(tags=["health"])

@router.get("/alive")
def alive() -> schemas.HealthCheckResponse:
    """Health-check endpoint polled by ResInsight for service life cycle management."""
    return schemas.HealthCheckResponse()
