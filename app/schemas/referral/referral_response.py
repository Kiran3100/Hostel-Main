# --- File: app/schemas/referral/referral_response.py ---
"""
Referral record response schemas.

This module provides response schemas for referral queries including
detailed information, statistics, and analytics.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Union
from uuid import UUID

from pydantic import Field, computed_field

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import ReferralStatus, RewardStatus

__all__ = [
    "ReferralResponse",
    "ReferralDetail",
    "ReferralStats",
    "ReferralLeaderboard",
    "ReferralTimeline",
]


class ReferralResponse(BaseResponseSchema):
    """
    Standard referral response schema.

    Used for single referral queries and list items.
    """

    # Program information
    program_id: UUID = Field(..., description="Referral program ID")
    program_name: str = Field(..., description="Program name")
    program_type: str = Field(..., description="Program type")

    # Referrer information
    referrer_id: UUID = Field(..., description="Referrer user ID")
    referrer_name: str = Field(..., description="Referrer name")
    referrer_email: Union[str, None] = Field(None, description="Referrer email")

    # Referee information
    referee_email: Union[str, None] = Field(None, description="Referee email")
    referee_phone: Union[str, None] = Field(None, description="Referee phone")
    referee_user_id: Union[UUID, None] = Field(None, description="Referee user ID")
    referee_name: Union[str, None] = Field(None, description="Referee name")

    # Referral details
    referral_code: str = Field(..., description="Referral code used")
    status: ReferralStatus = Field(..., description="Referral status")
    referral_source: Union[str, None] = Field(None, description="Referral source")

    # Conversion information
    booking_id: Union[UUID, None] = Field(None, description="Associated booking ID")
    conversion_date: Union[datetime, None] = Field(None, description="Conversion Date")
    booking_amount: Union[Decimal, None] = Field(None, description="Booking amount")

    # Reward information
    referrer_reward_amount: Union[Decimal, None] = Field(
        None,
        description="Referrer reward amount",
    )
    referee_reward_amount: Union[Decimal, None] = Field(
        None,
        description="Referee reward amount",
    )
    currency: str = Field(..., description="Currency code")

    # Reward status
    referrer_reward_status: RewardStatus = Field(
        ...,
        description="Referrer reward status",
    )
    referee_reward_status: RewardStatus = Field(
        ...,
        description="Referee reward status",
    )

    # Timestamps
    created_at: datetime = Field(..., description="Referral creation time")
    updated_at: datetime = Field(..., description="Last update time")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_converted(self) -> bool:
        """Check if referral has converted to booking."""
        return self.status == ReferralStatus.COMPLETED and self.booking_id is not None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_reward_amount(self) -> Decimal:
        """Calculate total reward amount (referrer + referee)."""
        referrer = self.referrer_reward_amount or Decimal("0")
        referee = self.referee_reward_amount or Decimal("0")
        return referrer + referee

    @computed_field  # type: ignore[prop-decorator]
    @property
    def days_since_referral(self) -> int:
        """Calculate days since referral was created."""
        return (datetime.utcnow() - self.created_at).days


class ReferralDetail(BaseResponseSchema):
    """
    Detailed referral information.

    Includes extended fields for comprehensive referral data and history.
    """

    # Program information
    program_id: UUID = Field(..., description="Program ID")
    program_name: str = Field(..., description="Program name")
    program_type: str = Field(..., description="Program type")
    program_description: Union[str, None] = Field(None, description="Program description")

    # Referrer information
    referrer_id: UUID = Field(..., description="Referrer ID")
    referrer_name: str = Field(..., description="Referrer name")
    referrer_email: Union[str, None] = Field(None, description="Referrer email")
    referrer_phone: Union[str, None] = Field(None, description="Referrer phone")
    referrer_total_referrals: int = Field(
        default=0,
        ge=0,
        description="Total referrals made by referrer",
    )

    # Referee information
    referee_email: Union[str, None] = Field(None, description="Referee email")
    referee_phone: Union[str, None] = Field(None, description="Referee phone")
    referee_user_id: Union[UUID, None] = Field(None, description="Referee user ID")
    referee_name: Union[str, None] = Field(None, description="Referee name")
    referee_registration_date: Union[datetime, None] = Field(
        None,
        description="When referee registered",
    )

    # Referral details
    referral_code: str = Field(..., description="Referral code")
    status: ReferralStatus = Field(..., description="Current status")
    referral_source: Union[str, None] = Field(None, description="Referral source")
    campaign_id: Union[UUID, None] = Field(None, description="Campaign ID")

    # Conversion tracking
    booking_id: Union[UUID, None] = Field(None, description="Booking ID")
    booking_amount: Union[Decimal, None] = Field(None, description="Booking amount")
    booking_date: Union[datetime, None] = Field(None, description="Booking Date")
    conversion_date: Union[datetime, None] = Field(None, description="Conversion Date")
    stay_duration_months: Union[int, None] = Field(None, description="Stay duration")
    hostel_id: Union[UUID, None] = Field(None, description="Hostel ID")
    hostel_name: Union[str, None] = Field(None, description="Hostel name")

    # Reward information
    referrer_reward_amount: Union[Decimal, None] = Field(
        None,
        description="Referrer reward",
    )
    referee_reward_amount: Union[Decimal, None] = Field(
        None,
        description="Referee reward",
    )
    currency: str = Field(..., description="Currency")

    # Reward status and payment
    referrer_reward_status: RewardStatus = Field(..., description="Referrer reward status")
    referee_reward_status: RewardStatus = Field(..., description="Referee reward status")
    referrer_reward_paid_at: Union[datetime, None] = Field(
        None,
        description="When referrer reward was paid",
    )
    referee_reward_paid_at: Union[datetime, None] = Field(
        None,
        description="When referee reward was paid",
    )

    # Status history
    status_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="History of status changes",
    )

    # Notes and metadata
    notes: Union[str, None] = Field(None, description="Additional notes")
    admin_notes: Union[str, None] = Field(None, description="Admin-only notes")

    # Timestamps
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update time")
    completed_at: Union[datetime, None] = Field(None, description="Completion time")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def conversion_time_days(self) -> Union[int, None]:
        """Calculate days from referral to conversion."""
        if self.conversion_date:
            return (self.conversion_date - self.created_at).days
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_reward_value(self) -> Decimal:
        """Calculate total reward value."""
        referrer = self.referrer_reward_amount or Decimal("0")
        referee = self.referee_reward_amount or Decimal("0")
        return referrer + referee

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_reward_fully_paid(self) -> bool:
        """Check if both rewards have been paid."""
        return (
            self.referrer_reward_status == RewardStatus.PAID
            and self.referee_reward_status == RewardStatus.PAID
        )


class ReferralStats(BaseSchema):
    """
    Referral statistics for a user.

    Provides comprehensive analytics for a referrer's performance.
    """

    user_id: UUID = Field(..., description="User ID")
    user_name: str = Field(..., description="User name")

    # Referral counts
    total_referrals: int = Field(
        ...,
        ge=0,
        description="Total referrals made",
    )
    successful_referrals: int = Field(
        ...,
        ge=0,
        description="Successfully converted referrals",
    )
    pending_referrals: int = Field(
        ...,
        ge=0,
        description="Pending referrals",
    )
    failed_referrals: int = Field(
        ...,
        ge=0,
        description="Failed/expired referrals",
    )
    cancelled_referrals: int = Field(
        ...,
        ge=0,
        description="Cancelled referrals",
    )

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
        description="Average days to convert",
    )

    # Reward statistics
    total_earned: Decimal = Field(
        ...,
        ge=0,
        description="Total rewards earned",
    )
    total_paid_out: Decimal = Field(
        ...,
        ge=0,
        description="Total rewards paid out",
    )
    total_pending_rewards: Decimal = Field(
        ...,
        ge=0,
        description="Total pending rewards",
    )
    currency: str = Field(default="INR", description="Currency code")

    # Breakdown by program
    referrals_by_program: Dict[str, int] = Field(
        default_factory=dict,
        description="Referral count by program",
    )
    rewards_by_program: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Rewards earned by program",
    )

    # Time-based statistics
    referrals_this_month: int = Field(
        default=0,
        ge=0,
        description="Referrals made this month",
    )
    referrals_last_month: int = Field(
        default=0,
        ge=0,
        description="Referrals made last month",
    )

    # Ranking
    user_rank: Union[int, None] = Field(
        None,
        ge=1,
        description="User's rank among all referrers",
    )
    total_referrers: Union[int, None] = Field(
        None,
        ge=1,
        description="Total number of active referrers",
    )

    # Activity
    last_referral_date: Union[datetime, None] = Field(
        None,
        description="Date of last referral",
    )
    most_active_program: Union[str, None] = Field(
        None,
        description="Program with most referrals",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def success_rate(self) -> Decimal:
        """Calculate success rate percentage."""
        if self.total_referrals == 0:
            return Decimal("0")
        return Decimal(
            (self.successful_referrals / self.total_referrals * 100)
        ).quantize(Decimal("0.01"))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pending_payout_amount(self) -> Decimal:
        """Calculate amount pending for payout."""
        return self.total_pending_rewards

    @computed_field  # type: ignore[prop-decorator]
    @property
    def average_reward_per_referral(self) -> Decimal:
        """Calculate average reward per successful referral."""
        if self.successful_referrals == 0:
            return Decimal("0")
        return (self.total_earned / self.successful_referrals).quantize(
            Decimal("0.01")
        )


class ReferralLeaderboard(BaseSchema):
    """
    Leaderboard of top referrers.

    Ranks users by referral performance.
    """

    period: str = Field(
        ...,
        pattern="^(all_time|this_month|last_month|this_year)$",
        description="Time period for leaderboard",
    )
    total_users: int = Field(
        ...,
        ge=0,
        description="Total users on leaderboard",
    )
    top_referrers: List["LeaderboardEntry"] = Field(
        ...,
        max_length=100,
        description="Top referrers list",
    )
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When leaderboard was generated",
    )


class LeaderboardEntry(BaseSchema):
    """Individual leaderboard entry."""

    rank: int = Field(..., ge=1, description="User's rank")
    user_id: UUID = Field(..., description="User ID")
    user_name: str = Field(..., description="User name")
    user_avatar: Union[str, None] = Field(None, description="User avatar URL")

    total_referrals: int = Field(..., ge=0, description="Total referrals")
    successful_referrals: int = Field(..., ge=0, description="Successful referrals")
    total_rewards_earned: Decimal = Field(..., ge=0, description="Total rewards earned")
    
    conversion_rate: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Conversion rate percentage",
    )

    # Badge/achievement
    badge: Union[str, None] = Field(
        None,
        description="Achievement badge (e.g., 'Top Referrer', 'Rising Star')",
    )


class ReferralTimeline(BaseSchema):
    """
    Timeline of referral activities.

    Chronological view of referral events and milestones.
    """

    referral_id: UUID = Field(..., description="Referral ID")
    timeline_events: List["TimelineEvent"] = Field(
        ...,
        description="Chronological events",
    )


class TimelineEvent(BaseSchema):
    """Single timeline event."""

    event_type: str = Field(
        ...,
        pattern="^(created|shared|clicked|registered|booked|converted|reward_approved|reward_paid|cancelled|expired)$",
        description="Event type",
    )
    event_title: str = Field(..., description="Event title")
    event_description: Union[str, None] = Field(None, description="Event description")
    event_date: datetime = Field(..., description="Event timestamp")
    event_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional event data",
    )
    actor_id: Union[UUID, None] = Field(None, description="User who triggered event")
    actor_name: Union[str, None] = Field(None, description="Actor name")


class ReferralAnalytics(BaseSchema):
    """
    Advanced analytics for referral performance.

    Provides insights and trends for referral programs.
    """

    program_id: Union[UUID, None] = Field(None, description="Program ID (null for all)")
    
    # Time period
    period_start: datetime = Field(..., description="Analysis start Date")
    period_end: datetime = Field(..., description="Analysis end Date")

    # Overall metrics
    total_referrals: int = Field(..., ge=0, description="Total referrals")
    total_conversions: int = Field(..., ge=0, description="Total conversions")
    total_revenue_generated: Decimal = Field(
        ...,
        ge=0,
        description="Total revenue from referrals",
    )
    total_rewards_distributed: Decimal = Field(
        ...,
        ge=0,
        description="Total rewards paid",
    )

    # Performance metrics
    conversion_rate: Decimal = Field(..., ge=0, le=100, description="Conversion rate")
    average_conversion_time_days: Decimal = Field(
        ...,
        ge=0,
        description="Average conversion time",
    )
    average_booking_value: Decimal = Field(
        ...,
        ge=0,
        description="Average booking value from referrals",
    )

    # ROI metrics
    roi_percentage: Decimal = Field(
        ...,
        description="Return on investment percentage",
    )
    cost_per_acquisition: Decimal = Field(
        ...,
        ge=0,
        description="Cost per acquired customer",
    )

    # Trends
    referral_trend: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Daily/weekly referral trend data",
    )
    conversion_trend: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Conversion trend data",
    )

    # Top performers
    top_referrers: List[Dict[str, Any]] = Field(
        default_factory=list,
        max_length=10,
        description="Top 10 referrers",
    )
    top_sources: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top referral sources",
    )

    # Geographic distribution
    referrals_by_location: Dict[str, int] = Field(
        default_factory=dict,
        description="Referrals by city/region",
    )

    # Status breakdown
    status_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Referrals by status",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effective_conversion_rate(self) -> Decimal:
        """Calculate effective conversion rate."""
        if self.total_referrals == 0:
            return Decimal("0")
        return Decimal(
            (self.total_conversions / self.total_referrals * 100)
        ).quantize(Decimal("0.01"))