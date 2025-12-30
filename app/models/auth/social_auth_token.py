# --- File: app/models/auth/social_auth_token.py ---
"""
Social authentication token and profile models.
Supports OAuth integration with multiple providers.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel

__all__ = [
    "SocialAuthProvider",
    "SocialAuthToken",
    "SocialAuthProfile",
    "SocialAuthLink",
]


class SocialAuthProvider(TimestampModel):
    """
    OAuth provider configuration.
    
    Manages OAuth provider settings and credentials.
    Supports multiple OAuth providers (Google, Facebook, Apple, etc.).
    """

    __tablename__ = "social_auth_providers"
    __table_args__ = (
        Index("idx_social_auth_providers_provider_name", "provider_name", unique=True),
        Index("idx_social_auth_providers_is_enabled", "is_enabled"),
        {"comment": "OAuth provider configuration and management"},
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Provider configuration unique identifier",
    )

    # Provider Information
    provider_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        comment="Provider name (google, facebook, apple, etc.)",
    )

    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Display name for UI",
    )

    # OAuth Configuration
    client_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="OAuth client ID",
    )

    client_secret: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="OAuth client secret (encrypted)",
    )

    authorization_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="OAuth authorization endpoint URL",
    )

    token_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="OAuth token endpoint URL",
    )

    user_info_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="User profile endpoint URL",
    )

    # Scopes and Permissions
    default_scopes: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Default OAuth scopes to request",
    )

    # Status
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether provider is enabled",
    )

    # Metadata
    icon_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Provider icon URL for UI",
    )

    extra_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional provider configuration",
    )

    # Relationships
    tokens: Mapped[list["SocialAuthToken"]] = relationship(
        "SocialAuthToken",
        back_populates="provider",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    profiles: Mapped[list["SocialAuthProfile"]] = relationship(
        "SocialAuthProfile",
        back_populates="provider",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<SocialAuthProvider(name={self.provider_name}, enabled={self.is_enabled})>"


class SocialAuthToken(TimestampModel):
    """
    OAuth token storage and management.
    
    Stores and manages OAuth access and refresh tokens.
    Implements automatic token refresh when supported.
    """

    __tablename__ = "social_auth_tokens"
    __table_args__ = (
        Index("idx_social_auth_tokens_user_id", "user_id"),
        Index("idx_social_auth_tokens_provider_id", "provider_id"),
        Index("idx_social_auth_tokens_expires_at", "expires_at"),
        UniqueConstraint("user_id", "provider_id", name="uq_user_provider"),
        {"comment": "OAuth token storage and refresh management"},
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Token record unique identifier",
    )

    # Foreign Keys
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to user",
    )

    provider_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("social_auth_providers.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to OAuth provider",
    )

    # Token Information
    access_token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="OAuth access token (encrypted)",
    )

    refresh_token: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="OAuth refresh token (encrypted)",
    )

    token_type: Mapped[str] = mapped_column(
        String(50),
        default="Bearer",
        nullable=False,
        comment="Token type (usually Bearer)",
    )

    # Token Expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Access token expiration timestamp",
    )

    # Scopes
    scopes: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Granted OAuth scopes",
    )

    # Refresh Information
    last_refreshed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last token refresh timestamp",
    )

    refresh_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of times token has been refreshed",
    )

    # Metadata
    extra_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional token metadata from provider",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="social_auth_tokens",
        lazy="selectin",
    )

    provider: Mapped["SocialAuthProvider"] = relationship(
        "SocialAuthProvider",
        back_populates="tokens",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<SocialAuthToken(user_id={self.user_id}, provider={self.provider.provider_name})>"

    def is_expired(self) -> bool:
        """Check if access token is expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() >= self.expires_at

    def update_tokens(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
    ) -> None:
        """
        Update OAuth tokens.
        
        Args:
            access_token: New access token
            refresh_token: New refresh token (optional)
            expires_in: Token expiration in seconds (optional)
        """
        self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token
        if expires_in:
            self.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        self.last_refreshed_at = datetime.utcnow()
        self.refresh_count += 1


class SocialAuthProfile(TimestampModel):
    """
    Social profile data caching.
    
    Caches user profile data from OAuth providers.
    Stores provider-specific user information.
    """

    __tablename__ = "social_auth_profiles"
    __table_args__ = (
        Index("idx_social_auth_profiles_user_id", "user_id"),
        Index("idx_social_auth_profiles_provider_id", "provider_id"),
        Index("idx_social_auth_profiles_provider_user_id", "provider_user_id"),
        UniqueConstraint(
            "provider_id",
            "provider_user_id",
            name="uq_provider_user",
        ),
        {"comment": "Social profile data caching and management"},
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Profile record unique identifier",
    )

    # Foreign Keys
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to user",
    )

    provider_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("social_auth_providers.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to OAuth provider",
    )

    # Provider Profile Information
    provider_user_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="User ID from OAuth provider",
    )

    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Email from provider",
    )

    full_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Full name from provider",
    )

    first_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="First name from provider",
    )

    last_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Last name from provider",
    )

    profile_picture_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Profile picture URL from provider",
    )

    # Additional Profile Data
    gender: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Gender from provider",
    )

    locale: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="Locale/language preference",
    )

    timezone: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Timezone from provider",
    )

    # Verification Status
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether email is verified by provider",
    )

    # Raw Profile Data
    raw_profile_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Complete profile data from provider",
    )

    # Sync Information
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Last profile sync timestamp",
    )

    # Metadata
    extra_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional profile metadata",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="social_auth_profiles",
        lazy="selectin",
    )

    provider: Mapped["SocialAuthProvider"] = relationship(
        "SocialAuthProvider",
        back_populates="profiles",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<SocialAuthProfile(user_id={self.user_id}, provider={self.provider.provider_name})>"

    def sync_profile(self, profile_data: dict) -> None:
        """
        Sync profile data from provider.
        
        Args:
            profile_data: Profile data dictionary from provider
        """
        self.email = profile_data.get("email")
        self.full_name = profile_data.get("name")
        self.first_name = profile_data.get("given_name")
        self.last_name = profile_data.get("family_name")
        self.profile_picture_url = profile_data.get("picture")
        self.gender = profile_data.get("gender")
        self.locale = profile_data.get("locale")
        self.email_verified = profile_data.get("email_verified", False)
        self.raw_profile_data = profile_data
        self.last_synced_at = datetime.utcnow()


class SocialAuthLink(TimestampModel):
    """
    Account linking management.
    
    Manages linking and unlinking of social accounts.
    Tracks account connection history and status.
    """

    __tablename__ = "social_auth_links"
    __table_args__ = (
        Index("idx_social_auth_links_user_id", "user_id"),
        Index("idx_social_auth_links_provider_id", "provider_id"),
        Index("idx_social_auth_links_is_linked", "is_linked"),
        {"comment": "Social account linking and management"},
    )

    # Primary Key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Link record unique identifier",
    )

    # Foreign Keys
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to user",
    )

    provider_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("social_auth_providers.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to OAuth provider",
    )

    # Link Status
    is_linked: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether account is currently linked",
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether this is the primary authentication method",
    )

    # Link Timestamps
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Account linking timestamp",
    )

    unlinked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Account unlinking timestamp",
    )

    # Link Metadata
    link_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="How account was linked (signup, manual_link, etc.)",
    )

    unlink_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Reason for unlinking",
    )

    # Metadata
    extra_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional link metadata",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="social_auth_links",
        lazy="selectin",
    )

    provider: Mapped["SocialAuthProvider"] = relationship(
        "SocialAuthProvider",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<SocialAuthLink(user_id={self.user_id}, provider={self.provider.provider_name}, linked={self.is_linked})>"

    def unlink(self, reason: Optional[str] = None) -> None:
        """Unlink social account."""
        self.is_linked = False
        self.is_primary = False
        self.unlinked_at = datetime.utcnow()
        self.unlink_reason = reason

    def relink(self) -> None:
        """Relink social account."""
        self.is_linked = True
        self.linked_at = datetime.utcnow()
        self.unlinked_at = None
        self.unlink_reason = None