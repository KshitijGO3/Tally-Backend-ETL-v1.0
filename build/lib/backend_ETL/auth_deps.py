"""FastAPI dependencies for user authentication and authorization."""

from __future__ import annotations

import logging
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, Header, Request, status

from backend_ETL.security import decode_jwt_access_token

logger = logging.getLogger(__name__)


def extract_bearer_token_string(authorization_header_value: str | None) -> str:
    """Extracts the raw token string from an 'Authorization: Bearer <token>' header."""
    if not authorization_header_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    header_parts = authorization_header_value.strip().split(" ", 1)
    if (
        len(header_parts) != 2
        or header_parts[0].lower() != "bearer"
        or not header_parts[1].strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return header_parts[1].strip()


def get_current_authenticated_user(
    request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> dict[str, Any]:
    """FastAPI dependency that decodes the JWT access token and verifies the user is active.

    Returns:
        Dictionary containing verified user claims (user_id, client_id, email, full_name, role).

    Raises:
        HTTPException 401 if token is missing, expired, or invalid.
        HTTPException 403 if the user account has been deactivated.
    """
    raw_token_string: str = extract_bearer_token_string(authorization)

    try:
        token_claims_payload: dict[str, Any] = decode_jwt_access_token(raw_token_string)
    except jwt.ExpiredSignatureError:
        logger.warning("Authentication rejected: access token has expired.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as jwt_decoding_error:
        logger.warning("Authentication rejected: invalid JWT token (%s).", jwt_decoding_error)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    authenticated_user_id: str | None = token_claims_payload.get("user_id")
    if not authenticated_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is missing user_id claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate against database if PostgresManager is attached to app state
    database_manager = getattr(request.app.state, "db", None)
    if database_manager is not None:
        user_record_from_database = database_manager.get_user_by_id(authenticated_user_id)
        if not user_record_from_database:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account no longer exists.",
            )
        if not user_record_from_database.get("is_active", 1):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated. Please contact your administrator.",
            )

    return token_claims_payload
