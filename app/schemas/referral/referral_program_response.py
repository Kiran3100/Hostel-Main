# --- File: app/schemas/referral/referral_program_response.py ---
"""
Referral program response schemas.

This module provides response schemas for referral program queries,
including detailed program information, lists, and statistics.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Union
from uuid import UUID

from pydantic import Field, computed_field

from app.schemas.common.base import BaseResponseSchema, BaseSchema

__all__ = [
    "ProgramResponse",
    "ProgramList",
    "ProgramStats",
    "ProgramAnalytics",
    "ProgramPerformance",
]


class ProgramResponse(BaseResponseSchema):
    """
    Referral program response schema.

    Includes program details and basic statistics.
    """

    # Basic information
    program_name: str = Field(..., description="Program name")
    program_code: str = Field(..., description="Program code")
    program_type: str = Field(..., description="Program type")
    description: Union[str, None] = Field(None, description="Program description")

    # Reward details
    reward_type: str = Field(..., description="Reward type")
    referrer_reward_amount: Union[Decimal, None] = Field(None, description="Referrer reward")
    referee_reward_amount: Union[Decimal, None] = Field(None, description="Referee reward")
    currency: str = Field(..., description="Currency code")

    # Reward caps
    max_referrer_rewards_per_month: Union[int, None] = Field(
        None,
        description="Max rewards per month",
    )
    max_total_reward_amount: Union[Decimal, None] = Field(
        None,
        description="Max total reward amount",
    )

    # Eligibility criteria
    min_booking_amount: Union[Decimal, None] = Field(None, description="Minimum booking amount")
    min_stay_months: Union[int, None] = Field(None, description="Minimum stay duration")
    min_referrer_stay_months: Union[int, None] = Field(None, description="Minimum referrer stay")
    max_referrals_per_user: Union[int, None] = Field(None, description="Max referrals per user")
    allowed_user_roles: List[str] = Field(
        default_factory=list,
        description="Allowed user roles",
    )

    # Status
    is_active: bool = Field(..., description="Active status")
    valid_from: Union[Date, None] = Field(None, description="Start Date")
    valid_to: Union[Date, None] = Field(None, description="End Date")

    # Terms
    terms_and_conditions: Union[str, None] = Field(None, description="T&C")
    auto_approve_rewards: bool = Field(..., description="Auto-approve rewards")
    track_conversion: bool = Field(default=True, description="Track conversion metrics")

    # Basic statistics
    total_referrals: int = Field(default=0, ge=0, description="Total referrals made")
    successful_referrals: int = Field(default=0, ge=0, description="Successful referrals")
    pending_referrals: int = Field(default=0, ge=0, description="Pending referrals")
    total_rewards_distributed: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Total rewards paid out",
    )

    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Union[UUID, None] = Field(None, description="Creator user ID")
    updated_by: Union[UUID, None] = Field(None, description="Last updater user ID")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_expired(self) -> bool:
        """Check if program has expired."""
        if self.valid_to is None:
            return False
        return Date.today() > self.valid_to

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_upcoming(self) -> bool:
        """Check if program hasn't started yet."""
        if self.valid_from is None:
            return False
        return Date.today() < self.valid_from

    @computed_field  # type: ignore[prop-decorator]
    @property
    def conversion_rate(self) -> Decimal:
        """Calculate conversion rate percentage."""
        if self.total_referrals == 0:
            return Decimal("0")
        rate = (self.successful_referrals / self.total_referrals) * 100
        return Decimal(str(rate)).quantize(Decimal("0.01"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def days_remaining(self) -> Union[int, None]:
        """Calculate days remaining until expiration."""
        if self.valid_to is None:
            return None
        delta = self.valid_to - Date.today()
        return max(0, delta.days)


class ProgramList(BaseSchema):
    """
    List of referral programs with pagination.

    Provides summary and pagination for multiple programs.
    """

    total_programs: int = Field(
        ...,
        ge=0,
        description="Total number of programs",
    )
    active_programs: int = Field(
        ...,
        ge=0,
        description="Number of active programs",
    )
    inactive_programs: int = Field(
        default=0,
        ge=0,
        description="Number of inactive programs",
    )
    expired_programs: int = Field(
        default=0,
        ge=0,
        description="Number of expired programs",
    )
    programs: List[ProgramResponse] = Field(
        ...,
        description="List of referral programs",
    )

    # Pagination
    page: int = Field(default=1, ge=1, description="Current page number")
    page_size: int = Field(default=10, ge=1, le=100, description="Items per page")
    total_pages: int = Field(default=1, ge=1, description="Total number of pages")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_next_page(self) -> bool:
        """Check if there are more pages."""
        return self.page < self.total_pages

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_previous_page(self) -> bool:
        """Check if there are previous pages."""
        return self.page > 1


class ProgramStats(BaseSchema):
    """
    Detailed program statistics.

    Provides comprehensive analytics for a referral program.
    """

    program_id: UUID = Field(..., description="Program ID")
    program_name: str = Field(..., description="Program name")
    program_code: str = Field(..., description="Program code")
    program_type: str = Field(..., description="Program type")

    # Referral statistics
    total_referrals: int = Field(..., ge=0, description="Total referrals")
    pending_referrals: int = Field(..., ge=0, description="Pending referrals")
    successful_referrals: int = Field(..., ge=0, description="Successful referrals")
    failed_referrals: int = Field(..., ge=0, description="Failed referrals")
    cancelled_referrals: int = Field(default=0, ge=0, description="Cancelled referrals")
    expired_referrals: int = Field(default=0, ge=0, description="Expired referrals")

    # Conversion metrics
    conversion_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Conversion rate percentage",
    )
    average_conversion_time_days: Decimal = Field(
        ...,
        ge=0,
        description="Average time to convert in days",
    )

    # Revenue impact
    total_booking_value: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Total booking value from referrals",
    )
    average_booking_value: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Average booking value",
    )

    # Reward statistics
    total_rewards_earned: Decimal = Field(..., ge=0, description="Total rewards earned")
    total_rewards_paid: Decimal = Field(..., ge=0, description="Total rewards paid")
    pending_rewards: Decimal = Field(..., ge=0, description="Pending reward payments")
    rewards_in_process: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Rewards being processed",
    )
    currency: str = Field(default="INR", description="Currency code")

    # User engagement
    total_referrers: int = Field(
        default=0,
        ge=0,
        description="Total unique referrers",
    )
    active_referrers: int = Field(
        default=0,
        ge=0,
        description="Currently active referrers",
    )
    top_referrers: List[Dict[str, Any]] = Field(
        default_factory=list,
        max_length=10,
        description="Top 10 referrers",
    )

    # Time period
    period_start: Date = Field(..., description="Statistics start Date")
    period_end: Date = Field(..., description="Statistics end Date")
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When statistics were generated",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def roi_percentage(self) -> Decimal:
        """Calculate return on investment percentage."""
        if self.total_rewards_paid == 0:
            return Decimal("0")
        
        profit = self.total_booking_value - self.total_rewards_paid
        roi = (profit / self.total_rewards_paid) * 100
        return Decimal(str(roi)).quantize(Decimal("0.01"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def average_reward_per_conversion(self) -> Decimal:
        """Calculate average reward per successful conversion."""
        if self.successful_referrals == 0:
            return Decimal("0")
        
        avg = self.total_rewards_paid / self.successful_referrals
        return Decimal(str(avg)).quantize(Decimal("0.01"))


class ProgramAnalytics(BaseSchema):
    """
    Advanced analytics for referral program performance.

    Provides trend analysis and predictive metrics.
    """

    program_id: UUID = Field(..., description="Program ID")
    program_name: str = Field(..., description="Program name")

    # Time-based trends
    daily_referral_trend: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Daily referral counts",
    )
    weekly_conversion_trend: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Weekly conversion data",
    )
    monthly_revenue_trend: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Monthly revenue from referrals",
    )

    # Comparative metrics
    month_over_month_growth: Decimal = Field(
        default=Decimal("0"),
        description="Month-over-month growth percentage",
    )
    year_over_year_growth: Decimal = Field(
        default=Decimal("0"),
        description="Year-over-year growth percentage",
    )

    # Segmentation
    referrals_by_source: Dict[str, int] = Field(
        default_factory=dict,
        description="Referrals by source/channel",
    )
    conversions_by_user_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Conversions by user role",
    )
    revenue_by_hostel: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Revenue by hostel location",
    )

    # Performance indicators
    best_performing_day: Union[str, None] = Field(
        None,
        description="Day with highest conversions",
    )
    best_performing_month: Union[str, None] = Field(
        None,
        description="Month with highest conversions",
    )
    peak_referral_time: Union[str, None] = Field(
        None,
        description="Time of day with most referrals",
    )

    # Predictive metrics
    projected_monthly_referrals: int = Field(
        default=0,
        ge=0,
        description="Projected referrals for current month",
    )
    projected_monthly_revenue: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Projected revenue for current month",
    )

    # Quality metrics
    average_referee_lifetime_value: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="Average LTV of referred customers",
    )
    referee_retention_rate: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        le=100,
        description="Retention rate of referred customers",
    )

    # Analysis period
    analysis_start_date: datetime = Field(..., description="Analysis start")
    analysis_end_date: datetime = Field(..., description="Analysis end")
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Generation timestamp",
    )


class ProgramPerformance(BaseSchema):
    """
    Program performance comparison.

    Compares multiple programs or tracks single program over time.
    """

    comparison_type: str = Field(
        ...,
        pattern="^(multi_program|time_series)$",
        description="Type of comparison",
    )
    
    # Program comparisons
    programs: List[Dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="Programs being compared",
    )

    # Key metrics comparison
    metrics_comparison: Dict[str, List[Any]] = Field(
        default_factory=dict,
        description="Side-by-side metrics comparison",
    )

    # Rankings
    best_conversion_rate: Union[str, None] = Field(
        None,
        description="Program with best conversion rate",
    )
    highest_revenue: Union[str, None] = Field(
        None,
        description="Program with highest revenue",
    )
    most_cost_effective: Union[str, None] = Field(
        None,
        description="Program with best ROI",
    )

    # Insights
    insights: List[str] = Field(
        default_factory=list,
        description="Key insights from comparison",
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommendations for improvement",
    )

    # Time period
    comparison_period_start: datetime = Field(..., description="Comparison start")
    comparison_period_end: datetime = Field(..., description="Comparison end")
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Generation timestamp",
    )