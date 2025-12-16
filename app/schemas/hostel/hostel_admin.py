# --- File: app/schemas/hostel/hostel_admin.py ---
"""
Hostel admin view schemas with enhanced configuration options.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Union

from pydantic import ConfigDict, Field, field_validator

from app.schemas.common.base import BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import HostelStatus, SubscriptionPlan, SubscriptionStatus

__all__ = [
    "HostelAdminView",
    "HostelSettings",
    "HostelVisibilityUpdate",
    "HostelCapacityUpdate",
    "HostelStatusUpdate",
]


class HostelAdminView(BaseSchema):
    """
    Comprehensive hostel view for administrators.
    
    Provides complete hostel information with statistics and metrics.
    """
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="Hostel ID")
    name: str = Field(..., description="Hostel name")
    slug: str = Field(..., description="URL slug")

    # Status
    status: HostelStatus = Field(..., description="Operational status")
    is_active: bool = Field(..., description="Active status")
    is_public: bool = Field(..., description="Public listing visibility")
    is_featured: bool = Field(..., description="Featured in listings")
    is_verified: bool = Field(..., description="Verification status")

    # Capacity stats
    total_rooms: int = Field(..., ge=0, description="Total number of rooms")
    total_beds: int = Field(..., ge=0, description="Total number of beds")
    occupied_beds: int = Field(..., ge=0, description="Currently occupied beds")
    available_beds: int = Field(..., ge=0, description="Available beds")
    occupancy_percentage: Annotated[
        Decimal,
        Field(ge=0, le=100, description="Current occupancy percentage")
    ]

    # Students
    total_students: int = Field(
        ...,
        ge=0,
        description="Total registered students",
    )
    active_students: int = Field(
        ...,
        ge=0,
        description="Currently active students",
    )

    # Financial
    total_revenue_this_month: Annotated[
        Decimal,
        Field(ge=0, description="Total revenue for current month")
    ]
    outstanding_payments: Annotated[
        Decimal,
        Field(ge=0, description="Total outstanding payment amount")
    ]

    # Pending items
    pending_bookings: int = Field(
        ...,
        ge=0,
        description="Number of pending booking requests",
    )
    pending_complaints: int = Field(
        ...,
        ge=0,
        description="Number of open/pending complaints",
    )
    pending_maintenance: int = Field(
        ...,
        ge=0,
        description="Number of pending maintenance requests",
    )

    # Subscription
    subscription_plan: Union[SubscriptionPlan, None] = Field(
        default=None,
        description="Current subscription plan",
    )
    subscription_status: Union[SubscriptionStatus, None] = Field(
        default=None,
        description="Subscription status",
    )
    subscription_expires_at: Union[datetime, None] = Field(
        default=None,
        description="Subscription expiration date",
    )

    # Performance
    average_rating: Annotated[
        Decimal,
        Field(ge=0, le=5, description="Average rating from reviews")
    ]
    total_reviews: int = Field(
        ...,
        ge=0,
        description="Total number of reviews",
    )


class HostelSettings(BaseUpdateSchema):
    """
    Hostel configuration settings.
    
    Manages hostel operational and behavioral settings.
    """
    model_config = ConfigDict(from_attributes=True)

    # Visibility
    is_public: Union[bool, None] = Field(
        default=None,
        description="Make hostel visible in public listings",
    )
    is_active: Union[bool, None] = Field(
        default=None,
        description="Hostel operational status",
    )

    # Booking settings
    auto_approve_bookings: bool = Field(
        default=False,
        description="Automatically approve booking requests",
    )
    booking_advance_percentage: Annotated[
        Decimal,
        Field(
            default=Decimal("20.00"),
            ge=0,
            le=100,
            description="Required advance payment percentage"
        )
    ]
    max_booking_duration_months: int = Field(
        default=12,
        ge=1,
        le=24,
        description="Maximum booking duration in months",
    )
    min_booking_duration_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Minimum booking duration in days",
    )

    # Payment settings
    payment_due_day: int = Field(
        default=5,
        ge=1,
        le=28,
        description="Monthly payment due date",
    )
    late_payment_grace_days: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Grace period for late payments (days)",
    )
    late_payment_penalty_percentage: Annotated[
        Decimal,
        Field(
            default=Decimal("5.00"),
            ge=0,
            le=50,
            description="Late payment penalty percentage"
        )
    ]

    # Attendance settings
    enable_attendance_tracking: bool = Field(
        default=True,
        description="Enable attendance tracking system",
    )
    minimum_attendance_percentage: Annotated[
        Decimal,
        Field(
            default=Decimal("75.00"),
            ge=0,
            le=100,
            description="Minimum required attendance percentage"
        )
    ]
    attendance_grace_period_days: int = Field(
        default=7,
        ge=0,
        le=30,
        description="Attendance tracking grace period for new students",
    )

    # Notification settings
    notify_on_booking: bool = Field(
        default=True,
        description="Send notifications for new bookings",
    )
    notify_on_complaint: bool = Field(
        default=True,
        description="Send notifications for new complaints",
    )
    notify_on_payment: bool = Field(
        default=True,
        description="Send notifications for payments",
    )
    notify_on_maintenance: bool = Field(
        default=True,
        description="Send notifications for maintenance requests",
    )

    # Mess settings
    mess_included: bool = Field(
        default=False,
        description="Mess facility included in rent",
    )
    mess_charges_monthly: Union[Annotated[
        Decimal,
        Field(ge=0, description="Monthly mess charges (if separate)")
    ], None] = None
    mess_advance_booking_days: int = Field(
        default=1,
        ge=0,
        le=7,
        description="Days in advance for mess meal booking",
    )

    # Security settings
    visitor_entry_time_start: Union[str, None] = Field(
        default=None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Visitor entry allowed from (HH:MM)",
    )
    visitor_entry_time_end: Union[str, None] = Field(
        default=None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Visitor entry allowed until (HH:MM)",
    )
    late_entry_time: Union[str, None] = Field(
        default=None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Late entry cutoff time (HH:MM)",
    )


class HostelVisibilityUpdate(BaseUpdateSchema):
    """
    Update hostel visibility settings.
    
    Controls hostel appearance in public listings and searches.
    """
    model_config = ConfigDict(from_attributes=True)

    is_public: bool = Field(
        ...,
        description="Make hostel publicly visible",
    )
    is_featured: bool = Field(
        default=False,
        description="Feature hostel in search results",
    )
    is_verified: bool = Field(
        default=False,
        description="Mark hostel as verified (admin only)",
    )


class HostelCapacityUpdate(BaseUpdateSchema):
    """
    Update hostel capacity information.
    
    Admin-only operation to modify hostel capacity.
    """
    model_config = ConfigDict(from_attributes=True)

    total_rooms: int = Field(
        ...,
        ge=1,
        description="Total number of rooms",
    )
    total_beds: int = Field(
        ...,
        ge=1,
        description="Total number of beds",
    )

    @field_validator("total_beds")
    @classmethod
    def validate_beds_vs_rooms(cls, v: int, info) -> int:
        """Validate that total beds is reasonable compared to rooms."""
        total_rooms = info.data.get("total_rooms")
        if total_rooms is not None and v < total_rooms:
            raise ValueError(
                "Total beds cannot be less than total rooms"
            )
        if total_rooms is not None and v > (total_rooms * 8):
            raise ValueError(
                "Total beds seems unreasonably high compared to rooms"
            )
        return v


class HostelStatusUpdate(BaseUpdateSchema):
    """
    Update hostel operational status.
    
    Tracks status changes with reason.
    """
    model_config = ConfigDict(from_attributes=True)

    status: HostelStatus = Field(
        ...,
        description="New hostel status",
    )
    is_active: bool = Field(
        ...,
        description="Active status",
    )
    reason: Union[str, None] = Field(
        default=None,
        min_length=10,
        max_length=500,
        description="Reason for status change",
    )
    effective_date: Union[datetime, None] = Field(
        default=None,
        description="Effective date of status change",
    )

    @field_validator("reason")
    @classmethod
    def validate_reason_required(cls, v: Union[str, None], info) -> Union[str, None]:
        """Require reason for certain status changes."""
        status = info.data.get("status")
        is_active = info.data.get("is_active")
        
        # Require reason if deactivating or setting to maintenance/closed
        if (
            is_active is False
            or status in [HostelStatus.UNDER_MAINTENANCE, HostelStatus.CLOSED]
        ) and not v:
            raise ValueError(
                "Reason is required when deactivating or changing to "
                "maintenance/closed status"
            )
        return v