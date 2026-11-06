"""Security and cryptographic utilities for human user authentication.

Provides:
  - Secure, one-way password hashing and verification using Argon2id.
  - Signed JSON Web Token (JWT) creation and decoding for stateless user sessions.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

logger = logging.getLogger(__name__)

# Standard secret key for signing JWTs. In production, provide JWT_SECRET_KEY via environment variable.
JWT_SECRET_KEY: str = os.environ.get(
    "JWT_SECRET_KEY", "tally_backend_etl_default_secure_secret_key_change_in_production"
)
JWT_SIGNING_ALGORITHM: str = "HS256"
DEFAULT_ACCESS_TOKEN_LIFETIME_MINUTES: int = 60 * 24  # 24 hours for dashboard user convenience

# Argon2id password hasher with secure, standardized memory and iteration parameters
argon2_password_hasher = PasswordHasher(
    time_cost=3,        # 3 computational iterations
    memory_cost=32768,  # 32 megabytes of memory usage to thwart GPU cracking
    parallelism=1,      # Single lane execution to prevent Windows virtual memory exhaustion
    hash_len=32,        # 32-byte final output hash length
    salt_len=16,        # 16-byte cryptographically random salt per user
)


def hash_user_password(plain_text_password: str) -> str:
    """Computes a cryptographically secure, salted one-way Argon2id hash of a plain text password.

    Args:
        plain_text_password: The raw password supplied by the user during onboarding or registration.

    Returns:
        The full encoded Argon2id hash string including salt and algorithm parameters.
    """
    if not plain_text_password or not isinstance(plain_text_password, str):
        raise ValueError("Password must be a non-empty string.")

    hashed_password_result: str = argon2_password_hasher.hash(plain_text_password)
    return hashed_password_result


def verify_user_password(
    plain_text_password_candidate: str,
    hashed_password_from_database: str,
) -> bool:
    """Verifies a candidate plain text password against a stored Argon2id hash in constant time.

    Args:
        plain_text_password_candidate: The plain text password entered by the user at login.
        hashed_password_from_database: The stored Argon2id hash string retrieved from the database.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    if not plain_text_password_candidate or not hashed_password_from_database:
        return False

    try:
        argon2_password_hasher.verify(
            hashed_password_from_database,
            plain_text_password_candidate,
        )
        return True
    except VerifyMismatchError:
        logger.warning("Password verification failed: hash mismatch.")
        return False
    except Exception as unexpected_error:
        logger.error("Unexpected error during password verification: %s", unexpected_error)
        return False


def create_jwt_access_token(
    token_payload_claims: dict[str, Any],
    expiration_time_delta: timedelta | None = None,
) -> str:
    """Creates a signed JSON Web Token (JWT) containing user identity and tenant claims.

    Args:
        token_payload_claims: Dictionary containing claims (e.g. user_id, client_id, email, role).
        expiration_time_delta: Optional custom lifetime. Defaults to 24 hours.

    Returns:
        A compact signed JWT string ready to be returned in HTTP response.
    """
    claims_to_encode: dict[str, Any] = token_payload_claims.copy()
    current_utc_timestamp: datetime = datetime.now(UTC)

    if expiration_time_delta is not None:
        token_expiration_timestamp = current_utc_timestamp + expiration_time_delta
    else:
        token_expiration_timestamp = current_utc_timestamp + timedelta(
            minutes=DEFAULT_ACCESS_TOKEN_LIFETIME_MINUTES
        )

    # Standard JWT registered claims
    claims_to_encode["iat"] = int(current_utc_timestamp.timestamp())
    claims_to_encode["exp"] = int(token_expiration_timestamp.timestamp())

    encoded_jwt_token_string: str = jwt.encode(
        payload=claims_to_encode,
        key=JWT_SECRET_KEY,
        algorithm=JWT_SIGNING_ALGORITHM,
    )
    return encoded_jwt_token_string


def decode_jwt_access_token(encoded_jwt_token_string: str) -> dict[str, Any]:
    """Decodes and cryptographically verifies a signed JSON Web Token.

    Args:
        encoded_jwt_token_string: The compact JWT string extracted from the Authorization header or cookie.

    Returns:
        The decoded claims payload dictionary.

    Raises:
        jwt.PyJWTError: If the token signature is invalid or expired.
    """
    decoded_token_claims: dict[str, Any] = jwt.decode(
        jwt=encoded_jwt_token_string,
        key=JWT_SECRET_KEY,
        algorithms=[JWT_SIGNING_ALGORITHM],
    )
    return decoded_token_claims
