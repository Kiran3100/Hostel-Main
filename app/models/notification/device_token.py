# --- File: C:\Hostel-Main\app\models\notification\device_token.py ---
"""
Device token management for push notifications.

Tracks registered devices and their push notification tokens.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin
from app.schemas.common.enums import DeviceType

if TYPE_CHECKING:
    from app.models.user.user import User


class DeviceToken(BaseModel, TimestampMixin):
    """
    Registered device tokens for push notifications.
    
    Manages device registration, token lifecycle, and badge counts
    for iOS, Android, and web push notifications.
    """

    __tablename__ = "device_tokens"

    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # User association
    user_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who owns this device",
    )

    # Device token
    device_token = Column(
        String(500),
        nullable=False,
        unique=True,
        index=True,
        comment="Device push notification token",
    )
    device_type = Column(
        String(20),
        nullable=False,
        index=True,
        comment="Device platform (ios/android/web)",
    )

    # Device details
    device_name = Column(
        String(100),
        nullable=True,
        comment="User-set device name",
    )
    device_model = Column(
        String(100),
        nullable=True,
        comment="Device model (iPhone 12, Samsung Galaxy, etc.)",
    )
    os_version = Column(
        String(50),
        nullable=True,
        comment="Operating system version",
    )
    app_version = Column(
        String(50),
        nullable=True,
        comment="Application version",
    )

    # Location and timezone
    timezone = Column(
        String(100),
        nullable=True,
        comment="Device timezone",
    )
    locale = Column(
        String(10),
        nullable=True,
        comment="Device locale (e.g., en_US, hi_IN)",
    )

    # Status
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether device token is active",
    )
    last_used_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When device was last active",
    )
    registered_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When device was registered",
    )

    # Badge count (iOS)
    current_badge_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Current badge count for this device",
    )

    # Token management
    token_invalid = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether provider reported token as invalid",
    )
    invalidated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When token was marked invalid",
    )

    # Relationships
    user = relationship(
        "User",
        backref="device_tokens",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "device_token",
            name="uq_user_device_token",
        ),
        Index(
            "ix_device_tokens_user_active",
            "user_id",
            "is_active",
        ),
        Index(
            "ix_device_tokens_type_active",
            "device_type",
            "is_active",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DeviceToken(id={self.id}, user_id={self.user_id}, "
            f"type={self.device_type}, active={self.is_active})>"
        )

    def increment_badge(self, amount: int = 1) -> None:
        """Increment badge count."""
        self.current_badge_count += amount

    def decrement_badge(self, amount: int = 1) -> None:
        """Decrement badge count (minimum 0)."""
        self.current_badge_count = max(0, self.current_badge_count - amount)

    def reset_badge(self) -> None:
        """Reset badge count to 0."""
        self.current_badge_count = 0

    def mark_invalid(self) -> None:
        """Mark token as invalid."""
        self.token_invalid = True
        self.is_active = False
        self.invalidated_at = datetime.utcnow()