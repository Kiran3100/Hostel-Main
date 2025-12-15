# app/core/security.py
from __future__ import annotations

"""
Core security helpers.

These re-export password hashing and JWT helpers from
`app.services.common.security` so you can import them
from a single core module if needed, for example:

    from app.core.security import hash_password, create_access_token
"""

from app.services.common.security import (
    JWTSettings,
    TokenDecodeError,
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)

__all__ = [
    "JWTSettings",
    "TokenDecodeError",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
]