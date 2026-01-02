# --- File: app/schemas/hostel/hostel_admin.py ---
"""
Hostel admin view schemas with enhanced configuration options.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Dict, List, Union

from pydantic import ConfigDict, Field, field_validator

from app.schemas.common.base import BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import HostelStatus, SubscriptionPlan, SubscriptionStatus

__all__ = [
    "HostelAdminView",
    "HostelSettings",
    "HostelSettingsUpdate",
    "HostelVisibilityUpdate",
    "HostelCapacityUpdate",
    "HostelStatusUpdate",
    "NotificationSettings",
    "BookingSettings", 
    "PaymentSettings",
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


class NotificationSettings(BaseSchema):
    """
    Notification preferences schema.
    
    Controls how and when notifications are sent to admins.
    """
    model_config = ConfigDict(from_attributes=True)
    
    # Channel preferences
    email_enabled: bool = Field(
        default=True,
        description="Enable email notifications"
    )
    sms_enabled: bool = Field(
        default=False,
        description="Enable SMS notifications"
    )
    push_enabled: bool = Field(
        default=True,
        description="Enable push notifications"
    )
    in_app_enabled: bool = Field(
        default=True,
        description="Enable in-app notifications"
    )
    
    # Event-specific settings
    booking_notifications: bool = Field(
        default=True,
        description="Notify on booking events"
    )
    payment_notifications: bool = Field(
        default=True,
        description="Notify on payment events"
    )
    complaint_notifications: bool = Field(
        default=True,
        description="Notify on complaint events"
    )
    maintenance_notifications: bool = Field(
        default=True,
        description="Notify on maintenance requests"
    )
    review_notifications: bool = Field(
        default=True,
        description="Notify on new reviews"
    )
    inquiry_notifications: bool = Field(
        default=True,
        description="Notify on new inquiries"
    )
    
    # Frequency settings
    daily_digest: bool = Field(
        default=False,
        description="Send daily summary email"
    )
    weekly_digest: bool = Field(
        default=True,
        description="Send weekly summary email"
    )
    real_time_alerts: bool = Field(
        default=True,
        description="Send immediate alerts for urgent events"
    )
    
    # Contact preferences
    notification_email: Union[str, None] = Field(
        default=None,
        description="Override email for notifications"
    )
    notification_phone: Union[str, None] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="SMS phone number"
    )
    
    # Quiet hours
    quiet_hours_enabled: bool = Field(
        default=False,
        description="Enable quiet hours (no non-urgent notifications)"
    )
    quiet_hours_start: Union[str, None] = Field(
        default=None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Quiet hours start time (HH:MM)"
    )
    quiet_hours_end: Union[str, None] = Field(
        default=None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Quiet hours end time (HH:MM)"
    )


class BookingSettings(BaseSchema):
    """
    Booking rules and preferences schema.
    
    Controls how bookings are handled and processed.
    """
    model_config = ConfigDict(from_attributes=True)
    
    # Approval settings
    auto_approve: bool = Field(
        default=False,
        description="Automatically approve new bookings"
    )
    require_admin_approval: bool = Field(
        default=True,
        description="Require admin approval for bookings"
    )
    approval_timeout_hours: int = Field(
        default=48,
        ge=1,
        le=168,  # 1 week max
        description="Hours before pending booking expires"
    )
    
    # Timing settings
    advance_booking_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Maximum days in advance for booking"
    )
    min_stay_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Minimum stay duration in days"
    )
    max_stay_days: int = Field(
        default=365,
        ge=30,
        le=730,
        description="Maximum stay duration in days"
    )
    same_day_booking_allowed: bool = Field(
        default=False,
        description="Allow same-day bookings"
    )
    
    # Deposit settings
    security_deposit_required: bool = Field(
        default=True,
        description="Require security deposit"
    )
    deposit_amount_type: str = Field(
        default="percentage",
        pattern=r"^(fixed|percentage|monthly_rent)$",
        description="How deposit amount is calculated"
    )
    deposit_percentage: Annotated[Decimal, Field(
        default=Decimal("100.00"),
        ge=0,
        le=500,
        description="Deposit percentage of monthly rent"
    )]
    deposit_fixed_amount: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        ge=0,
        description="Fixed deposit amount"
    )]
    
    # Cancellation settings
    free_cancellation_hours: int = Field(
        default=24,
        ge=0,
        le=168,
        description="Hours for free cancellation"
    )
    cancellation_fee_percentage: Annotated[Decimal, Field(
        default=Decimal("10.00"),
        ge=0,
        le=100,
        description="Cancellation fee percentage"
    )]
    refund_processing_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Days to process refunds"
    )
    
    # Requirements
    require_id_verification: bool = Field(
        default=True,
        description="Require ID verification for booking"
    )
    require_emergency_contact: bool = Field(
        default=True,
        description="Require emergency contact details"
    )
    max_occupants_per_booking: int = Field(
        default=1,
        ge=1,
        le=4,
        description="Maximum occupants per booking"
    )
    
    # Special settings
    allow_waitlist: bool = Field(
        default=True,
        description="Allow waitlist when no rooms available"
    )
    waitlist_expiry_days: int = Field(
        default=30,
        ge=1,
        le=90,
        description="Days before waitlist entry expires"
    )


class PaymentSettings(BaseSchema):
    """
    Payment processing preferences schema.
    
    Controls payment methods, schedules, and processing rules.
    """
    model_config = ConfigDict(from_attributes=True)
    
    # Accepted payment methods
    accept_cash: bool = Field(
        default=True,
        description="Accept cash payments"
    )
    accept_card: bool = Field(
        default=True,
        description="Accept credit/debit card payments"
    )
    accept_upi: bool = Field(
        default=True,
        description="Accept UPI payments"
    )
    accept_net_banking: bool = Field(
        default=True,
        description="Accept net banking"
    )
    accept_bank_transfer: bool = Field(
        default=True,
        description="Accept direct bank transfers"
    )
    accept_cheque: bool = Field(
        default=False,
        description="Accept cheque payments"
    )
    
    # Payment schedule
    payment_due_day: int = Field(
        default=5,
        ge=1,
        le=28,
        description="Monthly payment due date (day of month)"
    )
    grace_period_days: int = Field(
        default=3,
        ge=0,
        le=15,
        description="Grace period after due date"
    )
    late_fee_percentage: Annotated[Decimal, Field(
        default=Decimal("5.00"),
        ge=0,
        le=25,
        description="Late payment fee percentage"
    )]
    late_fee_max_amount: Annotated[Decimal, Field(
        default=Decimal("1000.00"),
        ge=0,
        description="Maximum late fee amount"
    )]
    
    # Processing settings
    auto_generate_invoices: bool = Field(
        default=True,
        description="Automatically generate invoices"
    )
    send_payment_reminders: bool = Field(
        default=True,
        description="Send payment reminders"
    )
    reminder_days_before: List[int] = Field(
        default=[7, 3, 1],
        description="Days before due date to send reminders"
    )
    
    # Gateway settings
    preferred_gateway: Union[str, None] = Field(
        default=None,
        description="Preferred payment gateway"
    )
    gateway_config: Dict[str, str] = Field(
        default_factory=dict,
        description="Gateway-specific configuration"
    )
    
    # Refund settings
    auto_process_refunds: bool = Field(
        default=False,
        description="Automatically process eligible refunds"
    )
    refund_processing_days: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Days to process refund requests"
    )
    partial_payments_allowed: bool = Field(
        default=True,
        description="Allow partial payment of dues"
    )
    
    # Currency and pricing
    default_currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        description="Default currency code"
    )
    tax_inclusive_pricing: bool = Field(
        default=True,
        description="Whether displayed prices include taxes"
    )
    tax_percentage: Annotated[Decimal, Field(
        default=Decimal("0.00"),
        ge=0,
        le=50,
        description="Tax percentage on rent"
    )]


class HostelSettings(BaseSchema):
    """
    Complete hostel configuration settings.
    
    Aggregates all hostel operational and behavioral settings.
    """
    model_config = ConfigDict(from_attributes=True)

    hostel_id: str = Field(..., description="Hostel identifier")

    # Visibility and operational settings
    is_public: bool = Field(
        default=True,
        description="Make hostel visible in public listings",
    )
    is_active: bool = Field(
        default=True,
        description="Hostel operational status",
    )
    is_featured: bool = Field(
        default=False,
        description="Feature hostel in listings"
    )

    # Core settings groups
    notifications: NotificationSettings = Field(
        ...,
        description="Notification preferences"
    )
    bookings: BookingSettings = Field(
        ...,
        description="Booking rules and settings"
    )
    payments: PaymentSettings = Field(
        ...,
        description="Payment processing settings"
    )

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
    
    # Metadata
    last_updated_by: Union[str, None] = Field(
        default=None,
        description="User who last updated settings"
    )
    settings_version: int = Field(
        default=1,
        ge=1,
        description="Settings version number"
    )


class HostelSettingsUpdate(BaseUpdateSchema):
    """
    Update hostel settings schema.
    
    Partial updates for hostel configuration with all fields optional.
    """
    model_config = ConfigDict(from_attributes=True)
    
    # Visibility settings
    is_public: Union[bool, None] = Field(
        default=None,
        description="Make hostel publicly visible"
    )
    is_active: Union[bool, None] = Field(
        default=None,
        description="Hostel operational status"
    )
    is_featured: Union[bool, None] = Field(
        default=None,
        description="Feature hostel in listings"
    )

    # Settings groups (partial updates)
    notifications: Union[NotificationSettings, None] = Field(
        default=None,
        description="Notification settings update"
    )
    bookings: Union[BookingSettings, None] = Field(
        default=None,
        description="Booking settings update"
    )
    payments: Union[PaymentSettings, None] = Field(
        default=None,
        description="Payment settings update"
    )

    # Individual setting overrides
    enable_attendance_tracking: Union[bool, None] = Field(
        default=None,
        description="Enable attendance tracking"
    )
    minimum_attendance_percentage: Union[Annotated[
        Decimal,
        Field(ge=0, le=100, description="Minimum attendance percentage")
    ], None] = None
    
    # Mess settings
    mess_included: Union[bool, None] = Field(
        default=None,
        description="Include mess in rent"
    )
    mess_charges_monthly: Union[Annotated[
        Decimal,
        Field(ge=0, description="Monthly mess charges")
    ], None] = None
    
    # Security settings
    visitor_entry_time_start: Union[str, None] = Field(
        default=None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Visitor entry start time"
    )
    visitor_entry_time_end: Union[str, None] = Field(
        default=None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Visitor entry end time"
    )
    late_entry_time: Union[str, None] = Field(
        default=None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Late entry cutoff time"
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