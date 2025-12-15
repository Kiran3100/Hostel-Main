# app/core/constants.py
from __future__ import annotations

"""
Core application constants.

These values centralize common configuration-like constants such as:
- Pagination defaults.
- JWT token lifetimes (defaults, can be overridden by settings).
- API prefixes.
- Common HTTP header names.
- Environment variable keys.

Note:
    These constants are intended to be imported and used throughout the
    application rather than hard-coding literals in multiple places.
"""

from datetime import timedelta  # Note: imported for potential external usage

# Pagination defaults
DEFAULT_PAGE: int = 1
DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 100

# JWT defaults (used if not overridden by settings)
ACCESS_TOKEN_EXPIRE_MINUTES_DEFAULT: int = 60
REFRESH_TOKEN_EXPIRE_DAYS_DEFAULT: int = 30

# API prefixes
API_PREFIX: str = "/api"
API_V1_PREFIX: str = "/api/v1"

# Common HTTP header names
HEADER_REQUEST_ID: str = "X-Request-ID"
HEADER_USER_ID: str = "X-User-ID"
HEADER_CORRELATION_ID: str = "X-Correlation-ID"

# Environment keys (optional; align with your settings)
ENV_DATABASE_URL: str = "DATABASE_URL"
ENV_JWT_SECRET_KEY: str = "JWT_SECRET_KEY"