# --- File: app/schemas/auth/social_auth.py ---
"""
Social authentication schemas with provider-specific validation.
Pydantic v2 compliant.
"""

from enum import Enum
from typing import Union
from uuid import UUID

from pydantic import EmailStr, Field, HttpUrl, field_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import Gender, UserRole


class SocialProvider(str, Enum):
    """Social authentication provider types."""
    
    GOOGLE = "google"
    FACEBOOK = "facebook"
    APPLE = "apple"


__all__ = [
    "SocialProvider",
    "SocialAuthRequest",
    "GoogleAuthRequest",
    "FacebookAuthRequest",
    "SocialUserInfo",
    "SocialProfileData",
    "SocialAuthResponse",
]


class SocialAuthRequest(BaseCreateSchema):
    """
    Base social authentication request.
    
    Generic schema for OAuth providers.
    """

    access_token: str = Field(
        ...,
        min_length=1,
        description="OAuth access token from provider",
    )
    provider: str = Field(
        ...,
        pattern=r"^(google|facebook|apple)$",
        description="OAuth provider name",
        examples=["google", "facebook"],
    )

    @field_validator("provider", mode="after")
    @classmethod
    def normalize_provider(cls, v: str) -> str:
        """Normalize provider name to lowercase."""
        return v.lower().strip()

    @field_validator("access_token", mode="after")
    @classmethod
    def validate_token_not_empty(cls, v: str) -> str:
        """Ensure access token is not empty or whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("Access token cannot be empty")
        return v


class GoogleAuthRequest(BaseCreateSchema):
    """
    Google OAuth authentication request.
    
    Uses Google ID token for secure authentication.
    """

    id_token: str = Field(
        ...,
        min_length=1,
        description="Google ID token (JWT) from OAuth flow",
    )
    access_token: Union[str, None] = Field(
        default=None,
        description="Google access token (optional, for additional API access)",
    )

    @field_validator("id_token", mode="after")
    @classmethod
    def validate_id_token_format(cls, v: str) -> str:
        """Validate token format and strip whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("Token cannot be empty or whitespace")
        return v

    @field_validator("access_token", mode="before")
    @classmethod
    def validate_access_token_format(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate token format and strip whitespace."""
        if v is not None:
            v = v.strip() if isinstance(v, str) else v
            if not v:
                raise ValueError("Token cannot be empty or whitespace")
        return v


class FacebookAuthRequest(BaseCreateSchema):
    """
    Facebook OAuth authentication request.
    
    Uses Facebook access token and user ID for authentication.
    """

    access_token: str = Field(
        ...,
        min_length=1,
        description="Facebook access token from OAuth flow",
    )
    user_id: str = Field(
        ...,
        min_length=1,
        description="Facebook user ID",
    )

    @field_validator("access_token", "user_id", mode="after")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """Ensure field is not empty or whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("Field cannot be empty or whitespace")
        return v


class SocialUserInfo(BaseSchema):
    """
    User information from social authentication.
    
    Minimal user profile data returned after social auth.
    """

    id: UUID = Field(
        ...,
        description="User ID in our system",
    )
    email: str = Field(
        ...,
        description="User email address",
    )
    full_name: str = Field(
        ...,
        description="User full name",
    )
    role: UserRole = Field(
        ...,
        description="User role",
    )
    profile_image_url: Union[str, None] = Field(
        default=None,
        description="Profile image URL from social provider",
    )
    is_email_verified: bool = Field(
        default=True,
        description="Email verification status (auto-verified via social auth)",
    )


class SocialProfileData(BaseSchema):
    """
    Profile data extracted from social provider.
    
    Comprehensive user information from OAuth provider.
    """

    provider_user_id: str = Field(
        ...,
        description="Unique user ID from OAuth provider",
    )
    email: EmailStr = Field(
        ...,
        description="Email address from provider",
    )
    full_name: str = Field(
        ...,
        description="Full name from provider",
    )
    first_name: Union[str, None] = Field(
        default=None,
        description="First name",
    )
    last_name: Union[str, None] = Field(
        default=None,
        description="Last name",
    )
    profile_picture_url: Union[HttpUrl, None] = Field(
        default=None,
        description="Profile picture URL from provider",
    )
    gender: Union[Gender, None] = Field(
        default=None,
        description="Gender (if provided by provider)",
    )
    locale: Union[str, None] = Field(
        default=None,
        description="User locale/language preference",
        examples=["en_US", "hi_IN"],
    )
    raw_data: Union[dict, None] = Field(
        default=None,
        description="Raw profile data from provider",
    )

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        """Normalize email to lowercase."""
        return str(v).lower().strip()


class SocialAuthResponse(BaseSchema):
    """
    Social authentication response.
    
    Follows OAuth 2.0 token response format with user information.
    """

    access_token: str = Field(
        ...,
        description="JWT access token for API authentication",
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
        description="Access token expiration in seconds",
        examples=[3600],
    )
    user: SocialUserInfo = Field(
        ...,
        description="Authenticated user information",
    )
    is_new_user: bool = Field(
        ...,
        description="Whether this is a new user (first-time registration)",
    )
    provider: str = Field(
        ...,
        description="Social authentication provider used",
    )