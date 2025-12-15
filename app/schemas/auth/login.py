# --- File: app/schemas/auth/login.py ---
"""
Login schemas with enhanced validation and type safety.
Pydantic v2 compliant.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import UserRole

__all__ = [
    "LoginRequest",
    "PhoneLoginRequest",
    "TokenData",
    "UserLoginInfo",
    "LoginResponse",
]


class LoginRequest(BaseCreateSchema):
    """
    Email/password-based login request.
    
    Validates email format and password length constraints.
    """

    email: EmailStr = Field(
        ...,
        description="User email address",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User password",
    )
    remember_me: bool = Field(
        default=False,
        description="Remember user session for extended period",
    )

    @field_validator("password", mode="after")
    @classmethod
    def validate_password_not_empty(cls, v: str) -> str:
        """Ensure password is not just whitespace."""
        if not v or not v.strip():
            raise ValueError("Password cannot be empty or whitespace")
        return v


class PhoneLoginRequest(BaseCreateSchema):
    """
    Phone-based login request.
    
    Supports international phone numbers in E.164 format.
    """

    phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Phone number (E.164 format recommended)",
        examples=["+919876543210", "9876543210"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User password",
    )
    remember_me: bool = Field(
        default=False,
        description="Remember user session for extended period",
    )

    @field_validator("phone", mode="after")
    @classmethod
    def normalize_phone(cls, v: str) -> str:
        """Normalize phone number by removing spaces and dashes."""
        return v.replace(" ", "").replace("-", "")

    @field_validator("password", mode="after")
    @classmethod
    def validate_password_not_empty(cls, v: str) -> str:
        """Ensure password is not just whitespace."""
        if not v or not v.strip():
            raise ValueError("Password cannot be empty or whitespace")
        return v


class TokenData(BaseSchema):
    """
    Token data embedded in JWT payload.
    
    Contains minimal user identification and context information.
    """

    user_id: UUID = Field(
        ...,
        description="User unique identifier",
    )
    email: str = Field(
        ...,
        description="User email address",
        examples=["user@example.com"],
    )
    role: UserRole = Field(
        ...,
        description="User role for authorization",
    )
    hostel_id: Optional[UUID] = Field(
        default=None,
        description="Active hostel context for multi-hostel admins",
    )


class UserLoginInfo(BaseSchema):
    """
    User information included in login response.
    
    Provides essential user profile data without sensitive information.
    """

    id: UUID = Field(
        ...,
        description="User unique identifier",
    )
    email: str = Field(
        ...,
        description="User email address",
    )
    full_name: str = Field(
        ...,
        description="User full name",
        examples=["John Doe"],
    )
    role: UserRole = Field(
        ...,
        description="User role",
    )
    is_email_verified: bool = Field(
        ...,
        description="Email verification status",
    )
    is_phone_verified: bool = Field(
        ...,
        description="Phone verification status",
    )
    profile_image_url: Optional[str] = Field(
        default=None,
        description="Profile image URL",
        examples=["https://example.com/images/profile.jpg"],
    )


class LoginResponse(BaseSchema):
    """
    Login response with JWT tokens and user information.
    
    Follows OAuth 2.0 token response format.
    """

    access_token: str = Field(
        ...,
        description="JWT access token for API authentication",
    )
    refresh_token: str = Field(
        ...,
        description="JWT refresh token for obtaining new access tokens",
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
    user: UserLoginInfo = Field(
        ...,
        description="Authenticated user information",
    )