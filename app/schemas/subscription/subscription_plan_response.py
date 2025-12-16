"""
Subscription plan response and comparison schemas.

Provides structured responses for plan details, feature listings,
and plan comparison functionality.
"""

from decimal import Decimal
from typing import Any, Dict, List, Union, Annotated

from pydantic import Field, computed_field, ConfigDict

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import SubscriptionPlan

__all__ = [
    "PlanResponse",
    "PlanFeatures",
    "PlanComparison",
    "PlanSummary",
]


class PlanResponse(BaseResponseSchema):
    """
    Complete subscription plan response.

    Returns all plan details including pricing, features,
    limits, and computed properties.
    """
    model_config = ConfigDict(populate_by_name=True)

    plan_name: str = Field(..., description="Plan internal identifier")
    display_name: str = Field(..., description="Plan display name")
    plan_type: SubscriptionPlan = Field(..., description="Plan tier")

    description: Union[str, None] = Field(None, description="Full description")
    short_description: Union[str, None] = Field(
        None, description="Short description"
    )

    # Pricing
    price_monthly: Annotated[Decimal, Field(..., description="Monthly price")]
    price_yearly: Annotated[Decimal, Field(..., description="Yearly price")]
    currency: str = Field(..., description="Currency code")

    # Features
    features: Dict[str, Any] = Field(
        default_factory=dict, description="Feature configuration"
    )

    # Limits
    max_hostels: Union[int, None] = Field(None, description="Max hostels")
    max_rooms_per_hostel: Union[int, None] = Field(
        None, description="Max rooms per hostel"
    )
    max_students: Union[int, None] = Field(None, description="Max students")
    max_admins: Union[int, None] = Field(None, description="Max admin users")

    # Status
    is_active: bool = Field(..., description="Plan is active")
    is_public: bool = Field(..., description="Visible on pricing page")
    is_featured: bool = Field(
        default=False, description="Featured/recommended plan"
    )
    sort_order: int = Field(..., description="Display order")

    # Trial
    trial_days: int = Field(default=0, description="Trial period days")

    @computed_field  # type: ignore[misc]
    @property
    def price_monthly_formatted(self) -> str:
        """Format monthly price with currency."""
        return f"{self.currency} {self.price_monthly:,.2f}"

    @computed_field  # type: ignore[misc]
    @property
    def price_yearly_formatted(self) -> str:
        """Format yearly price with currency."""
        return f"{self.currency} {self.price_yearly:,.2f}"

    @computed_field  # type: ignore[misc]
    @property
    def yearly_savings(self) -> Decimal:
        """Calculate yearly savings vs monthly billing."""
        return (self.price_monthly * 12 - self.price_yearly).quantize(
            Decimal("0.01")
        )

    @computed_field  # type: ignore[misc]
    @property
    def yearly_discount_percent(self) -> Decimal:
        """Calculate yearly discount percentage."""
        if self.price_monthly == Decimal("0"):
            return Decimal("0")
        monthly_yearly = self.price_monthly * 12
        if monthly_yearly == Decimal("0"):
            return Decimal("0")
        return (
            (monthly_yearly - self.price_yearly) / monthly_yearly * 100
        ).quantize(Decimal("0.01"))

    @computed_field  # type: ignore[misc]
    @property
    def has_trial(self) -> bool:
        """Check if plan offers trial."""
        return self.trial_days > 0

    @computed_field  # type: ignore[misc]
    @property
    def limits_display(self) -> Dict[str, str]:
        """Format limits for display."""
        return {
            "hostels": str(self.max_hostels) if self.max_hostels else "Unlimited",
            "rooms_per_hostel": (
                str(self.max_rooms_per_hostel)
                if self.max_rooms_per_hostel
                else "Unlimited"
            ),
            "students": str(self.max_students) if self.max_students else "Unlimited",
            "admins": str(self.max_admins) if self.max_admins else "Unlimited",
        }


class PlanSummary(BaseSchema):
    """
    Condensed plan summary for listings.

    Provides essential plan information for cards and lists.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Plan ID")
    plan_name: str = Field(..., description="Plan identifier")
    display_name: str = Field(..., description="Display name")
    plan_type: SubscriptionPlan = Field(..., description="Plan tier")

    price_monthly: Annotated[Decimal, Field(..., description="Monthly price")]
    price_yearly: Annotated[Decimal, Field(..., description="Yearly price")]
    currency: str = Field(..., description="Currency")

    short_description: Union[str, None] = Field(None)
    is_featured: bool = Field(default=False)
    trial_days: int = Field(default=0)


class PlanFeatures(BaseSchema):
    """
    Human-friendly plan feature matrix.

    Formats features for display in comparison tables
    and feature lists.
    """
    model_config = ConfigDict(populate_by_name=True)

    plan_name: str = Field(..., description="Plan identifier")
    display_name: str = Field(..., description="Plan display name")
    plan_type: SubscriptionPlan = Field(..., description="Plan tier")

    # Feature categories with human-readable values
    features: Dict[str, str] = Field(
        ...,
        description="Feature key to display value mapping",
    )
    feature_categories: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Category to feature keys mapping",
    )

    # Highlight features
    highlight_features: List[str] = Field(
        default_factory=list,
        description="Key features to highlight",
    )

    @classmethod
    def from_plan_response(
        cls,
        plan: PlanResponse,
        feature_labels: Dict[str, str],
    ) -> "PlanFeatures":
        """
        Create PlanFeatures from PlanResponse.

        Args:
            plan: The plan response to convert.
            feature_labels: Mapping of feature keys to display labels.

        Returns:
            PlanFeatures instance with formatted features.
        """
        formatted_features = {}
        for key, value in plan.features.items():
            label = feature_labels.get(key, key.replace("_", " ").title())
            if isinstance(value, bool):
                formatted_features[label] = "✓" if value else "✗"
            elif value is None:
                formatted_features[label] = "Unlimited"
            else:
                formatted_features[label] = str(value)

        return cls(
            plan_name=plan.plan_name,
            display_name=plan.display_name,
            plan_type=plan.plan_type,
            features=formatted_features,
        )


class PlanComparison(BaseSchema):
    """
    Compare multiple plans side by side.

    Provides a structured comparison matrix for displaying
    multiple plans with their features.
    """
    model_config = ConfigDict(populate_by_name=True)

    plans: List[PlanResponse] = Field(
        ...,
        min_length=2,
        description="Plans to compare",
    )
    feature_matrix: Dict[str, Dict[str, Any]] = Field(
        ...,
        description="Feature key -> plan_name -> value matrix",
    )
    feature_order: List[str] = Field(
        default_factory=list,
        description="Ordered list of feature keys for display",
    )
    category_order: List[str] = Field(
        default_factory=list,
        description="Ordered list of feature categories",
    )

    # Recommendations
    recommended_plan: Union[str, None] = Field(
        None, description="Recommended plan name"
    )
    recommendation_reason: Union[str, None] = Field(
        None, description="Reason for recommendation"
    )

    @classmethod
    def create(
        cls,
        plans: List[PlanResponse],
        feature_order: Union[List[str], None] = None,
    ) -> "PlanComparison":
        """
        Create comparison from list of plans.

        Args:
            plans: List of plans to compare.
            feature_order: Optional ordered list of features to include.

        Returns:
            PlanComparison instance with feature matrix.
        """
        # Build feature matrix
        all_features: set = set()
        for plan in plans:
            all_features.update(plan.features.keys())

        # Use provided order or alphabetical
        ordered_features = feature_order or sorted(all_features)

        feature_matrix: Dict[str, Dict[str, Any]] = {}
        for feature in ordered_features:
            feature_matrix[feature] = {}
            for plan in plans:
                feature_matrix[feature][plan.plan_name] = plan.features.get(
                    feature
                )

        # Add limit comparisons
        limit_features = ["max_hostels", "max_rooms_per_hostel", "max_students"]
        for limit in limit_features:
            feature_matrix[limit] = {}
            for plan in plans:
                feature_matrix[limit][plan.plan_name] = getattr(plan, limit)

        # Find featured plan as recommended
        recommended = next(
            (p.plan_name for p in plans if p.is_featured), None
        )

        return cls(
            plans=plans,
            feature_matrix=feature_matrix,
            feature_order=ordered_features + limit_features,
            recommended_plan=recommended,
        )