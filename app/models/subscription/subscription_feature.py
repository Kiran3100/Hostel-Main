"""
Subscription Feature Models.

Tracks feature usage, limits, and configurations
for active subscriptions.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.subscription.subscription import Subscription

__all__ = [
    "SubscriptionFeatureUsage",
    "SubscriptionLimit",
]


class SubscriptionFeatureUsage(UUIDMixin, TimestampModel):
    """
    Feature usage tracking for subscriptions.

    Monitors usage of individual features against
    plan limits and quotas.
    """

    __tablename__ = "subscription_feature_usage"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "feature_key",
            name="uq_subscription_feature_usage",
        ),
        CheckConstraint(
            "current_usage >= 0",
            name="ck_feature_usage_current_positive",
        ),
        CheckConstraint(
            "usage_limit IS NULL OR usage_limit > 0",
            name="ck_feature_usage_limit_positive",
        ),
        Index(
            "ix_feature_usage_subscription_feature",
            "subscription_id",
            "feature_key",
        ),
        {"schema": "public"},
    )

    # Subscription Reference
    subscription_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Subscription ID",
    )

    # Feature Identification
    feature_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Feature identifier key",
    )
    feature_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Human-readable feature name",
    )

    # Usage Tracking
    current_usage: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Current usage count",
    )
    usage_limit: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Usage limit (NULL = unlimited)",
    )

    # Status
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Feature enabled status",
    )
    is_limit_exceeded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether usage limit has been exceeded",
    )

    # Last Usage
    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last feature usage timestamp",
    )

    # Usage Period
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Usage period start",
    )
    period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Usage period end",
    )

    # Metadata
    usage_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Additional usage metadata",
    )

    # Relationships
    subscription: Mapped["Subscription"] = relationship(
        "Subscription",
        backref="feature_usage",
    )

    def __repr__(self) -> str:
        return f"<SubscriptionFeatureUsage(id={self.id}, subscription_id={self.subscription_id}, feature_key={self.feature_key})>"

    @property
    def usage_percentage(self) -> Optional[float]:
        """Calculate usage as percentage of limit."""
        if self.usage_limit is None:
            return None
        if self.usage_limit == 0:
            return 100.0
        return (self.current_usage / self.usage_limit) * 100

    @property
    def remaining_usage(self) -> Optional[int]:
        """Calculate remaining usage allowance."""
        if self.usage_limit is None:
            return None
        remaining = self.usage_limit - self.current_usage
        return max(0, remaining)

    @property
    def is_near_limit(self, threshold: float = 0.8) -> bool:
        """Check if usage is near limit (default 80%)."""
        if self.usage_limit is None:
            return False
        return self.current_usage >= (self.usage_limit * threshold)

    def can_use(self, amount: int = 1) -> bool:
        """Check if feature can be used for specified amount."""
        if not self.is_enabled:
            return False
        if self.usage_limit is None:
            return True
        return (self.current_usage + amount) <= self.usage_limit

    def increment_usage(self, amount: int = 1) -> None:
        """Increment usage count."""
        self.current_usage += amount
        self.last_used_at = datetime.utcnow()
        if self.usage_limit is not None:
            self.is_limit_exceeded = self.current_usage > self.usage_limit

    def reset_usage(self) -> None:
        """Reset usage count to zero."""
        self.current_usage = 0
        self.is_limit_exceeded = False
        self.period_start = datetime.utcnow()


class SubscriptionLimit(UUIDMixin, TimestampModel):
    """
    Subscription limits configuration.

    Stores configured limits for various subscription
    resources and features.
    """

    __tablename__ = "subscription_limits"
    __table_args__ = (
        UniqueConstraint(
            "subscription_id",
            "limit_type",
            name="uq_subscription_limit_type",
        ),
        CheckConstraint(
            "limit_value IS NULL OR limit_value > 0",
            name="ck_subscription_limit_value_positive",
        ),
        CheckConstraint(
            "current_value >= 0",
            name="ck_subscription_limit_current_positive",
        ),
        Index(
            "ix_subscription_limit_subscription_type",
            "subscription_id",
            "limit_type",
        ),
        {"schema": "public"},
    )

    # Subscription Reference
    subscription_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Subscription ID",
    )

    # Limit Configuration
    limit_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Type of limit (hostels, rooms, students, etc.)",
    )
    limit_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Human-readable limit name",
    )
    limit_value: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Limit value (NULL = unlimited)",
    )
    current_value: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Current value/usage",
    )

    # Status
    is_enforced: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether limit is actively enforced",
    )
    is_exceeded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether limit has been exceeded",
    )

    # Warning Configuration
    warning_threshold: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Threshold for warning notification",
    )
    warning_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether warning has been sent",
    )

    # Description
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Limit description",
    )

    # Relationships
    subscription: Mapped["Subscription"] = relationship(
        "Subscription",
        backref="limits",
    )

    def __repr__(self) -> str:
        return f"<SubscriptionLimit(id={self.id}, subscription_id={self.subscription_id}, limit_type={self.limit_type})>"

    @property
    def remaining_limit(self) -> Optional[int]:
        """Calculate remaining limit allowance."""
        if self.limit_value is None:
            return None
        remaining = self.limit_value - self.current_value
        return max(0, remaining)

    @property
    def usage_percentage(self) -> Optional[float]:
        """Calculate usage as percentage of limit."""
        if self.limit_value is None:
            return None
        if self.limit_value == 0:
            return 100.0
        return (self.current_value / self.limit_value) * 100

    @property
    def is_near_limit(self) -> bool:
        """Check if current value is near warning threshold."""
        if self.warning_threshold is None:
            return False
        return self.current_value >= self.warning_threshold

    def can_add(self, amount: int = 1) -> bool:
        """Check if amount can be added within limit."""
        if not self.is_enforced:
            return True
        if self.limit_value is None:
            return True
        return (self.current_value + amount) <= self.limit_value

    def increment(self, amount: int = 1) -> None:
        """Increment current value."""
        self.current_value += amount
        if self.limit_value is not None:
            self.is_exceeded = self.current_value > self.limit_value
        if self.warning_threshold is not None and not self.warning_sent:
            if self.current_value >= self.warning_threshold:
                self.warning_sent = True

    def decrement(self, amount: int = 1) -> None:
        """Decrement current value."""
        self.current_value = max(0, self.current_value - amount)
        if self.limit_value is not None:
            self.is_exceeded = self.current_value > self.limit_value