"""
Subscription Plan Models.

Defines subscription plan structure including pricing,
features, limits, and configuration options.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import AuditMixin, UUIDMixin
from app.schemas.common.enums import SubscriptionPlan as SubscriptionPlanEnum

__all__ = [
    "SubscriptionPlan",
    "PlanFeature",
]


class SubscriptionPlan(UUIDMixin, TimestampModel, AuditMixin):
    """
    Subscription plan definition.

    Stores plan configurations including pricing tiers,
    feature sets, usage limits, and availability.
    """

    __tablename__ = "subscription_plans"
    __table_args__ = (
        UniqueConstraint("plan_name", name="uq_subscription_plan_name"),
        CheckConstraint(
            "price_monthly >= 0",
            name="ck_subscription_plan_price_monthly_positive",
        ),
        CheckConstraint(
            "price_yearly >= 0",
            name="ck_subscription_plan_price_yearly_positive",
        ),
        CheckConstraint(
            "price_yearly <= (price_monthly * 12)",
            name="ck_subscription_plan_yearly_not_exceed_monthly",
        ),
        CheckConstraint(
            "max_hostels IS NULL OR max_hostels > 0",
            name="ck_subscription_plan_max_hostels_positive",
        ),
        CheckConstraint(
            "max_rooms_per_hostel IS NULL OR max_rooms_per_hostel > 0",
            name="ck_subscription_plan_max_rooms_positive",
        ),
        CheckConstraint(
            "max_students IS NULL OR max_students > 0",
            name="ck_subscription_plan_max_students_positive",
        ),
        CheckConstraint(
            "max_admins IS NULL OR max_admins > 0",
            name="ck_subscription_plan_max_admins_positive",
        ),
        CheckConstraint(
            "trial_days >= 0 AND trial_days <= 90",
            name="ck_subscription_plan_trial_days_range",
        ),
        {"schema": "public"},
    )

    # Plan Identification
    plan_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Internal plan identifier (lowercase, underscores)",
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Plan display name for UI",
    )
    plan_type: Mapped[SubscriptionPlanEnum] = mapped_column(
        nullable=False,
        index=True,
        comment="Plan tier/type",
    )

    # Description
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed plan description",
    )
    short_description: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Short description for cards/listings",
    )

    # Pricing
    price_monthly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Monthly subscription price",
    )
    price_yearly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Yearly subscription price",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        comment="ISO 4217 currency code",
    )

    # Features (stored as JSON for flexibility)
    features: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Feature flags and configurations",
    )

    # Usage Limits (NULL = unlimited)
    max_hostels: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum number of hostels (NULL = unlimited)",
    )
    max_rooms_per_hostel: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum rooms per hostel (NULL = unlimited)",
    )
    max_students: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum total students (NULL = unlimited)",
    )
    max_admins: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum admin users (NULL = unlimited)",
    )

    # Status and Display
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Plan is available for new subscriptions",
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Show on public pricing page",
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Highlight as featured/recommended plan",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Display ordering (lower = first)",
    )

    # Trial Configuration
    trial_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Trial period in days (0 = no trial)",
    )

    # Relationships
    subscriptions: Mapped[List["Subscription"]] = relationship(
        "Subscription",
        back_populates="plan",
        lazy="dynamic",
    )
    plan_features: Mapped[List["PlanFeature"]] = relationship(
        "PlanFeature",
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<SubscriptionPlan(id={self.id}, plan_name={self.plan_name}, plan_type={self.plan_type})>"

    @property
    def yearly_savings(self) -> Decimal:
        """Calculate yearly savings compared to monthly billing."""
        monthly_yearly = self.price_monthly * 12
        return (monthly_yearly - self.price_yearly).quantize(Decimal("0.01"))

    @property
    def yearly_discount_percent(self) -> Decimal:
        """Calculate yearly discount percentage."""
        if self.price_monthly == Decimal("0"):
            return Decimal("0")
        monthly_yearly = self.price_monthly * 12
        if monthly_yearly == Decimal("0"):
            return Decimal("0")
        discount = (monthly_yearly - self.price_yearly) / monthly_yearly * 100
        return discount.quantize(Decimal("0.01"))

    @property
    def has_trial(self) -> bool:
        """Check if plan offers trial."""
        return self.trial_days > 0

    def get_feature_value(self, feature_key: str, default: Any = None) -> Any:
        """Get feature value by key with optional default."""
        return self.features.get(feature_key, default)

    def has_feature(self, feature_key: str) -> bool:
        """Check if plan has specific feature enabled."""
        value = self.features.get(feature_key)
        if isinstance(value, bool):
            return value
        return value is not None

    def is_within_limits(
        self,
        hostels: int = 0,
        rooms: int = 0,
        students: int = 0,
        admins: int = 0,
    ) -> bool:
        """Check if usage is within plan limits."""
        if self.max_hostels is not None and hostels > self.max_hostels:
            return False
        if self.max_rooms_per_hostel is not None and rooms > self.max_rooms_per_hostel:
            return False
        if self.max_students is not None and students > self.max_students:
            return False
        if self.max_admins is not None and admins > self.max_admins:
            return False
        return True


class PlanFeature(UUIDMixin, TimestampModel):
    """
    Individual plan feature definition.

    Provides structured feature definitions with values,
    labels, and enablement status.
    """

    __tablename__ = "plan_features"
    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "feature_key",
            name="uq_plan_feature_plan_key",
        ),
        {"schema": "public"},
    )

    # Plan Reference
    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Subscription plan ID",
    )

    # Feature Definition
    feature_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Feature identifier key",
    )
    feature_label: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Human-readable feature label",
    )
    feature_value: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Feature value (can be any type)",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Feature enabled status",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Feature description",
    )

    # Display
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Display ordering",
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Feature category for grouping",
    )

    # Relationships
    plan: Mapped["SubscriptionPlan"] = relationship(
        "SubscriptionPlan",
        back_populates="plan_features",
    )

    def __repr__(self) -> str:
        return f"<PlanFeature(id={self.id}, plan_id={self.plan_id}, feature_key={self.feature_key})>"