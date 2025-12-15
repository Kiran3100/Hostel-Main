"""
Subscription plan definition schemas.

Defines the structure for subscription plans including pricing,
features, limits, and configuration options.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Annotated

from pydantic import Field, field_validator, model_validator, computed_field, ConfigDict

from app.schemas.common.base import (
    BaseCreateSchema,
    BaseSchema,
    BaseUpdateSchema,
)
from app.schemas.common.enums import SubscriptionPlan

__all__ = [
    "SubscriptionPlanBase",
    "PlanCreate",
    "PlanUpdate",
    "PlanFeatureConfig",
]


class PlanFeatureConfig(BaseSchema):
    """
    Configuration for a single plan feature.

    Provides structured feature definition with value,
    display label, and enablement status.
    """
    model_config = ConfigDict(populate_by_name=True)

    key: str = Field(..., description="Feature identifier key")
    label: str = Field(..., description="Human-readable feature label")
    value: Any = Field(..., description="Feature value")
    enabled: bool = Field(default=True, description="Feature enabled status")
    description: Optional[str] = Field(
        None, description="Feature description"
    )


class SubscriptionPlanBase(BaseSchema):
    """
    Base subscription plan schema.

    Contains all fields that define a subscription plan including
    identification, pricing, features, and limits.
    """
    model_config = ConfigDict(populate_by_name=True)

    plan_name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Plan internal identifier (lowercase, underscores)",
    )
    display_name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Plan display name for UI",
    )
    plan_type: SubscriptionPlan = Field(
        ..., description="Plan tier/type"
    )

    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Plan description",
    )
    short_description: Optional[str] = Field(
        None,
        max_length=200,
        description="Short description for cards/listings",
    )

    # Pricing
    price_monthly: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Monthly subscription price",
    )]
    price_yearly: Annotated[Decimal, Field(
        ...,
        ge=Decimal("0"),
        description="Yearly subscription price",
    )]
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="ISO 4217 currency code",
    )

    # Features as structured dict
    features: Dict[str, Any] = Field(
        default_factory=dict,
        description="Feature flags and configurations",
    )

    # Usage limits
    max_hostels: Optional[int] = Field(
        None,
        ge=1,
        description="Maximum number of hostels (None = unlimited)",
    )
    max_rooms_per_hostel: Optional[int] = Field(
        None,
        ge=1,
        description="Maximum rooms per hostel (None = unlimited)",
    )
    max_students: Optional[int] = Field(
        None,
        ge=1,
        description="Maximum total students (None = unlimited)",
    )
    max_admins: Optional[int] = Field(
        None,
        ge=1,
        description="Maximum admin users (None = unlimited)",
    )

    # Status and display
    is_active: bool = Field(
        default=True, description="Plan is available for new subscriptions"
    )
    is_public: bool = Field(
        default=True, description="Show on public pricing page"
    )
    is_featured: bool = Field(
        default=False, description="Highlight as featured/recommended plan"
    )
    sort_order: int = Field(
        default=0, description="Display ordering (lower = first)"
    )

    # Trial configuration
    trial_days: int = Field(
        default=0,
        ge=0,
        le=90,
        description="Trial period in days (0 = no trial)",
    )

    @model_validator(mode="after")
    def validate_pricing(self) -> "SubscriptionPlanBase":
        """Validate pricing logic."""
        # Yearly price should typically be discounted vs 12x monthly
        yearly_monthly_equivalent = self.price_monthly * 12
        if self.price_yearly > yearly_monthly_equivalent:
            raise ValueError(
                "price_yearly should not exceed 12x price_monthly"
            )
        return self

    @field_validator("plan_name")
    @classmethod
    def normalize_plan_name(cls, v: str) -> str:
        """Normalize plan name to lowercase."""
        return v.lower().strip()

    @computed_field
    def yearly_savings(self) -> Decimal:
        """Calculate yearly savings compared to monthly billing."""
        monthly_yearly = self.price_monthly * 12
        return (monthly_yearly - self.price_yearly).quantize(Decimal("0.01"))

    @computed_field
    def yearly_discount_percent(self) -> Decimal:
        """Calculate yearly discount percentage."""
        if self.price_monthly == Decimal("0"):
            return Decimal("0")
        monthly_yearly = self.price_monthly * 12
        if monthly_yearly == Decimal("0"):
            return Decimal("0")
        discount = (
            (monthly_yearly - self.price_yearly) / monthly_yearly * 100
        )
        return discount.quantize(Decimal("0.01"))


class PlanCreate(SubscriptionPlanBase, BaseCreateSchema):
    """
    Create new subscription plan.

    Inherits all fields from SubscriptionPlanBase for plan creation.
    """
    model_config = ConfigDict(populate_by_name=True)

    # Additional creation-specific fields
    created_by: Optional[str] = Field(
        None, description="Admin user who created the plan"
    )

    @field_validator("features")
    @classmethod
    def validate_features(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate feature dictionary structure."""
        if not isinstance(v, dict):
            raise ValueError("features must be a dictionary")
        return v


class PlanUpdate(BaseUpdateSchema):
    """
    Update subscription plan.

    All fields are optional to support partial updates.
    """
    model_config = ConfigDict(populate_by_name=True)

    display_name: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100,
        description="Updated display name",
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Updated description",
    )
    short_description: Optional[str] = Field(
        None,
        max_length=200,
        description="Updated short description",
    )

    # Pricing updates
    price_monthly: Optional[Annotated[Decimal, Field(
        None,
        ge=Decimal("0"),
        description="Updated monthly price",
    )]]
    price_yearly: Optional[Annotated[Decimal, Field(
        None,
        ge=Decimal("0"),
        description="Updated yearly price",
    )]]
    currency: Optional[str] = Field(
        None,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="Updated currency",
    )

    # Feature updates
    features: Optional[Dict[str, Any]] = Field(
        None, description="Updated features"
    )

    # Limit updates
    max_hostels: Optional[int] = Field(None, ge=1)
    max_rooms_per_hostel: Optional[int] = Field(None, ge=1)
    max_students: Optional[int] = Field(None, ge=1)
    max_admins: Optional[int] = Field(None, ge=1)

    # Status updates
    is_active: Optional[bool] = Field(None)
    is_public: Optional[bool] = Field(None)
    is_featured: Optional[bool] = Field(None)
    sort_order: Optional[int] = Field(None)

    # Trial updates
    trial_days: Optional[int] = Field(None, ge=0, le=90)

    @model_validator(mode="after")
    def validate_pricing_update(self) -> "PlanUpdate":
        """Validate pricing updates if both provided."""
        if self.price_monthly is not None and self.price_yearly is not None:
            yearly_monthly_equivalent = self.price_monthly * 12
            if self.price_yearly > yearly_monthly_equivalent:
                raise ValueError(
                    "price_yearly should not exceed 12x price_monthly"
                )
        return self