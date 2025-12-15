# --- File: app/schemas/auth/token.py ---
"""
Token management schemas with enhanced security features.
Pydantic v2 compliant.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import UserRole

__all__ = [
    "Token",
    "TokenPayload",
    "RefreshTokenRequest",
    "RefreshTokenResponse",
    "TokenValidationRequest",
    "TokenValidationResponse",
    "RevokeTokenRequest",
    "LogoutRequest",
]


class Token(BaseSchema):
    """
    JWT token schema.
    
    Standard OAuth 2.0 token response format.
    """

    access_token: str = Field(
        ...,
        description="JWT access token",
    )
    refresh_token: str = Field(
        ...,
        description="JWT refresh token",
    )
    token_type: str = Field(
        default="bearer",
        description="Token type (always 'bearer')",
    )
    expires_in: int = Field(
        ...,
        gt=0,
        description="Access token expiration time in seconds",
        examples=[3600],
    )


class TokenPayload(BaseSchema):
    """
    JWT token payload structure.
    
    Standard JWT claims plus custom application claims.
    """

    sub: str = Field(
        ...,
        description="Subject (user_id as string)",
    )
    user_id: UUID = Field(
        ...,
        description="User unique identifier",
    )
    email: str = Field(
        ...,
        description="User email address",
    )
    role: UserRole = Field(
        ...,
        description="User role for authorization",
    )
    hostel_id: Optional[UUID] = Field(
        default=None,
        description="Active hostel context (for multi-hostel scenarios)",
    )
    exp: int = Field(
        ...,
        gt=0,
        description="Expiration timestamp (Unix epoch)",
    )
    iat: int = Field(
        ...,
        gt=0,
        description="Issued at timestamp (Unix epoch)",
    )
    jti: str = Field(
        ...,
        description="JWT ID (unique token identifier for revocation)",
    )

    @field_validator("exp", "iat", mode="after")
    @classmethod
    def validate_timestamp(cls, v: int) -> int:
        """Validate timestamp is reasonable (not negative, not too far in future)."""
        if v < 0:
            raise ValueError("Timestamp cannot be negative")
        # Check if timestamp is not more than 100 years in the future
        max_future = int(datetime.now().timestamp()) + (100 * 365 * 24 * 3600)
        if v > max_future:
            raise ValueError("Timestamp is too far in the future")
        return v


class RefreshTokenRequest(BaseCreateSchema):
    """
    Refresh token request.
    
    Used to obtain a new access token using a refresh token.
    """

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Refresh token",
    )

    @field_validator("refresh_token", mode="after")
    @classmethod
    def validate_token_not_empty(cls, v: str) -> str:
        """Ensure refresh token is not empty or whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("Refresh token cannot be empty")
        return v


class RefreshTokenResponse(BaseSchema):
    """
    Refresh token response.
    
    Returns new access and refresh tokens.
    """

    access_token: str = Field(
        ...,
        description="New JWT access token",
    )
    refresh_token: str = Field(
        ...,
        description="New refresh token (token rotation)",
    )
    token_type: str = Field(
        default="bearer",
        description="Token type (always 'bearer')",
    )
    expires_in: int = Field(
        ...,
        gt=0,
        description="New access token expiration time in seconds",
        examples=[3600],
    )


class TokenValidationRequest(BaseCreateSchema):
    """
    Token validation request.
    
    Used to validate token without making an authenticated request.
    """

    token: str = Field(
        ...,
        min_length=1,
        description="Token to validate (access or refresh)",
    )

    @field_validator("token", mode="after")
    @classmethod
    def validate_token_not_empty(cls, v: str) -> str:
        """Ensure token is not empty or whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("Token cannot be empty")
        return v


class TokenValidationResponse(BaseSchema):
    """
    Token validation response.
    
    Indicates token validity and provides decoded information.
    """

    is_valid: bool = Field(
        ...,
        description="Whether token is valid and not expired",
    )
    user_id: Optional[UUID] = Field(
        default=None,
        description="User ID if token is valid",
    )
    role: Optional[UserRole] = Field(
        default=None,
        description="User role if token is valid",
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Token expiration datetime (UTC)",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if token is invalid",
        examples=["Token expired", "Invalid signature"],
    )


class RevokeTokenRequest(BaseCreateSchema):
    """
    Revoke token request.
    
    Used to invalidate specific token or all user tokens.
    """

    token: str = Field(
        ...,
        min_length=1,
        description="Token to revoke",
    )
    revoke_all: bool = Field(
        default=False,
        description="Revoke all tokens for this user",
    )

    @field_validator("token", mode="after")
    @classmethod
    def validate_token_not_empty(cls, v: str) -> str:
        """Ensure token is not empty or whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("Token cannot be empty")
        return v


class LogoutRequest(BaseCreateSchema):
    """
    Logout request.
    
    Used to terminate user session(s).
    """

    refresh_token: Optional[str] = Field(
        default=None,
        description="Refresh token to revoke (optional if using access token)",
    )
    logout_all_devices: bool = Field(
        default=False,
        description="Logout from all devices (revoke all user tokens)",
    )

    @field_validator("refresh_token", mode="before")
    @classmethod
    def validate_token_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate refresh token format if provided."""
        if v is not None:
            if isinstance(v, str):
                v = v.strip()
                if not v:
                    raise ValueError("Refresh token cannot be empty if provided")
        return v