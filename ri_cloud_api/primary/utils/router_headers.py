"""Utilities for extracting and validating request headers."""

from __future__ import annotations

from fastapi import HTTPException


def extract_required_token(authorization: str | None) -> str:
    """Extract the token from the Authorization header.

    Raises:
        HTTPException: If the header is missing or malformed
    """
    require_bearer_token(authorization)

    assert authorization is not None
    return extract_bearer_token(authorization)


def require_bearer_token(authorization: str | None) -> None:
    """Require and extract Bearer token from Authorization header.

    Combines the None-check and token extraction into a single call.
    Raises 401 if the header is absent or malformed.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")


def extract_bearer_token(authorization: str) -> str:
    """Extract Bearer token from Authorization header.

    Args:
        authorization: The Authorization header value (e.g., "Bearer <token>")

    Returns:
        The extracted token string

    Raises:
        HTTPException: If the header is missing or malformed
    """
    auth = authorization.strip()

    # Handle "Bearer <token>" format
    if " " in auth:
        scheme, token = auth.split(" ", 1)
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid Authorization header format")
        token = token.strip()
        if not token:
            raise HTTPException(status_code=401, detail="Invalid Authorization header format")
        return token
    # Reject "Bearer" without a token
    if auth.lower() == "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")

    # If no "Bearer " prefix, treat the whole value as the token
    return auth
