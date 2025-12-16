# --- File: app/schemas/notification/notification_preferences.py ---
"""
Notification preferences schemas.

This module provides schemas for managing user notification preferences
including channel selection, frequency settings, and quiet hours.
"""

from typing import Dict, List, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import UserRole

__all__ = [
    "UserPreferences",
    "ChannelPreferences",
    "EmailPreferences",
    "SMSPreferences",
    "PushPreferences",
    "FrequencySettings",
    "PreferenceUpdate",
    "UnsubscribeRequest",
    "QuietHours",
]


class FrequencySettings(BaseSchema):
    """
    Notification frequency settings.

    Controls how often and when notifications are delivered.
    """

    # Delivery mode
    immediate_notifications: bool = Field(
        default=True,
        description="Send notifications immediately",
    )

    # Batching
    batch_notifications: bool = Field(
        default=False,
        description="Batch notifications instead of immediate delivery",
    )
    batch_interval_hours: int = Field(
        default=4,
        ge=1,
        le=24,
        description="Hours between batched notifications",
    )

    # Digest
    daily_digest_enabled: bool = Field(
        default=False,
        description="Enable daily digest",
    )
    daily_digest_time: Union[str, None] = Field(
        default=None,
        pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Daily digest time in HH:MM format (24-hour)",
    )

    weekly_digest_enabled: bool = Field(
        default=False,
        description="Enable weekly digest",
    )
    weekly_digest_day: Union[str, None] = Field(
        default=None,
        pattern="^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$",
        description="Day for weekly digest",
    )
    weekly_digest_time: Union[str, None] = Field(
        default=None,
        pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Weekly digest time in HH:MM format",
    )

    @model_validator(mode="after")
    def validate_digest_settings(self) -> "FrequencySettings":
        """Validate digest configuration."""
        if self.daily_digest_enabled and not self.daily_digest_time:
            raise ValueError("daily_digest_time required when daily digest is enabled")

        if self.weekly_digest_enabled:
            if not self.weekly_digest_day or not self.weekly_digest_time:
                raise ValueError(
                    "weekly_digest_day and weekly_digest_time required when weekly digest is enabled"
                )

        return self


class QuietHours(BaseSchema):
    """
    Quiet hours configuration.

    Defines time periods when notifications should not be sent.
    """

    enabled: bool = Field(
        default=False,
        description="Enable quiet hours",
    )

    start_time: Union[str, None] = Field(
        default=None,
        pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Quiet hours start time (HH:MM, 24-hour format)",
    )
    end_time: Union[str, None] = Field(
        default=None,
        pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Quiet hours end time (HH:MM, 24-hour format)",
    )

    # Days of week
    apply_on_weekdays: bool = Field(
        default=True,
        description="Apply quiet hours on weekdays",
    )
    apply_on_weekends: bool = Field(
        default=True,
        description="Apply quiet hours on weekends",
    )

    # Exceptions
    allow_urgent: bool = Field(
        default=True,
        description="Allow urgent/critical notifications during quiet hours",
    )

    # Timezone
    timezone: str = Field(
        default="UTC",
        max_length=100,
        description="Timezone for quiet hours",
    )

    @model_validator(mode="after")
    def validate_quiet_hours(self) -> "QuietHours":
        """Validate quiet hours configuration."""
        if self.enabled:
            if not self.start_time or not self.end_time:
                raise ValueError(
                    "start_time and end_time required when quiet hours are enabled"
                )
        return self


class EmailPreferences(BaseSchema):
    """
    Email notification preferences.

    Fine-grained control over email notifications.
    """

    enabled: bool = Field(
        default=True,
        description="Enable email notifications",
    )

    # Digest settings
    daily_digest: bool = Field(
        default=False,
        description="Receive daily digest email",
    )
    weekly_digest: bool = Field(
        default=False,
        description="Receive weekly digest email",
    )

    # Category preferences
    receive_payment_emails: bool = Field(
        default=True,
        description="Receive payment-related emails",
    )
    receive_booking_emails: bool = Field(
        default=True,
        description="Receive booking-related emails",
    )
    receive_complaint_emails: bool = Field(
        default=True,
        description="Receive complaint-related emails",
    )
    receive_announcement_emails: bool = Field(
        default=True,
        description="Receive announcement emails",
    )
    receive_maintenance_emails: bool = Field(
        default=True,
        description="Receive maintenance notification emails",
    )
    receive_marketing_emails: bool = Field(
        default=False,
        description="Receive marketing and promotional emails",
    )

    # Format preferences
    html_emails: bool = Field(
        default=True,
        description="Receive HTML formatted emails",
    )
    text_emails_fallback: bool = Field(
        default=True,
        description="Include plain text fallback",
    )


class SMSPreferences(BaseSchema):
    """
    SMS notification preferences.

    Control over SMS delivery with cost considerations.
    """

    enabled: bool = Field(
        default=True,
        description="Enable SMS notifications",
    )

    # Filtering
    urgent_only: bool = Field(
        default=True,
        description="Only receive urgent/high priority SMS",
    )

    # Category preferences
    receive_payment_sms: bool = Field(
        default=True,
        description="Receive payment-related SMS",
    )
    receive_booking_sms: bool = Field(
        default=True,
        description="Receive booking-related SMS",
    )
    receive_emergency_sms: bool = Field(
        default=True,
        description="Receive emergency SMS",
    )
    receive_otp_sms: bool = Field(
        default=True,
        description="Receive OTP and verification SMS",
    )

    # Frequency limits
    max_sms_per_day: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum SMS per day",
    )


class PushPreferences(BaseSchema):
    """
    Push notification preferences.

    Control over mobile and web push notifications.
    """

    enabled: bool = Field(
        default=True,
        description="Enable push notifications",
    )

    # Sound and alerts
    sound_enabled: bool = Field(
        default=True,
        description="Play notification sound",
    )
    vibration_enabled: bool = Field(
        default=True,
        description="Enable vibration",
    )

    # Badge
    badge_enabled: bool = Field(
        default=True,
        description="Show badge count on app icon",
    )

    # Preview
    show_preview: bool = Field(
        default=True,
        description="Show message preview on lock screen",
    )

    # Lock screen
    show_on_lock_screen: bool = Field(
        default=True,
        description="Show notifications on lock screen",
    )

    # Category preferences
    receive_payment_push: bool = Field(
        default=True,
        description="Receive payment push notifications",
    )
    receive_booking_push: bool = Field(
        default=True,
        description="Receive booking push notifications",
    )
    receive_complaint_push: bool = Field(
        default=True,
        description="Receive complaint push notifications",
    )
    receive_announcement_push: bool = Field(
        default=True,
        description="Receive announcement push notifications",
    )


class ChannelPreferences(BaseSchema):
    """
    Channel-specific notification preferences.

    Aggregates preferences for all notification channels.
    """

    user_id: UUID = Field(
        ...,
        description="User ID",
    )

    # Email preferences
    email: EmailPreferences = Field(
        default_factory=EmailPreferences,
        description="Email notification preferences",
    )

    # SMS preferences
    sms: SMSPreferences = Field(
        default_factory=SMSPreferences,
        description="SMS notification preferences",
    )

    # Push preferences
    push: PushPreferences = Field(
        default_factory=PushPreferences,
        description="Push notification preferences",
    )


class UserPreferences(BaseSchema):
    """
    Complete user notification preferences.

    Master preferences including global settings, channel preferences,
    and scheduling options.
    """

    user_id: UUID = Field(
        ...,
        description="User ID",
    )

    # Global settings
    notifications_enabled: bool = Field(
        default=True,
        description="Master notification toggle",
    )

    # Channel toggles
    email_enabled: bool = Field(
        default=True,
        description="Enable email notifications",
    )
    sms_enabled: bool = Field(
        default=True,
        description="Enable SMS notifications",
    )
    push_enabled: bool = Field(
        default=True,
        description="Enable push notifications",
    )

    # Frequency
    frequency_settings: FrequencySettings = Field(
        default_factory=FrequencySettings,
        description="Notification frequency settings",
    )

    # Quiet hours
    quiet_hours: QuietHours = Field(
        default_factory=QuietHours,
        description="Quiet hours configuration",
    )

    # Category preferences (global overrides)
    payment_notifications: bool = Field(
        default=True,
        description="Receive payment notifications",
    )
    booking_notifications: bool = Field(
        default=True,
        description="Receive booking notifications",
    )
    complaint_notifications: bool = Field(
        default=True,
        description="Receive complaint notifications",
    )
    announcement_notifications: bool = Field(
        default=True,
        description="Receive announcement notifications",
    )
    maintenance_notifications: bool = Field(
        default=True,
        description="Receive maintenance notifications",
    )
    attendance_notifications: bool = Field(
        default=True,
        description="Receive attendance notifications",
    )
    marketing_notifications: bool = Field(
        default=False,
        description="Receive marketing notifications",
    )

    # Language
    preferred_language: str = Field(
        default="en",
        min_length=2,
        max_length=5,
        description="Preferred language for notifications",
    )

    # Timezone
    timezone: str = Field(
        default="UTC",
        max_length=100,
        description="User timezone for scheduling",
    )


class PreferenceUpdate(BaseUpdateSchema):
    """
    Update notification preferences.

    Allows partial updates to user preferences.
    """

    # Global toggles
    notifications_enabled: Union[bool, None] = Field(
        default=None,
        description="Update master notification toggle",
    )
    email_enabled: Union[bool, None] = Field(
        default=None,
        description="Update email notifications",
    )
    sms_enabled: Union[bool, None] = Field(
        default=None,
        description="Update SMS notifications",
    )
    push_enabled: Union[bool, None] = Field(
        default=None,
        description="Update push notifications",
    )

    # Quiet hours
    quiet_hours_enabled: Union[bool, None] = Field(
        default=None,
        description="Enable/disable quiet hours",
    )
    quiet_hours_start: Union[str, None] = Field(
        default=None,
        pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Update quiet hours start time",
    )
    quiet_hours_end: Union[str, None] = Field(
        default=None,
        pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Update quiet hours end time",
    )

    # Category toggles
    payment_notifications: Union[bool, None] = None
    booking_notifications: Union[bool, None] = None
    complaint_notifications: Union[bool, None] = None
    announcement_notifications: Union[bool, None] = None
    maintenance_notifications: Union[bool, None] = None
    attendance_notifications: Union[bool, None] = None
    marketing_notifications: Union[bool, None] = None

    # Frequency
    immediate_notifications: Union[bool, None] = None
    batch_notifications: Union[bool, None] = None
    daily_digest_enabled: Union[bool, None] = None
    weekly_digest_enabled: Union[bool, None] = None

    # Language and timezone
    preferred_language: Union[str, None] = Field(
        default=None,
        min_length=2,
        max_length=5,
        description="Update preferred language",
    )
    timezone: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Update timezone",
    )


class UnsubscribeRequest(BaseSchema):
    """
    Unsubscribe from notifications.

    Allows users to opt-out of specific notification types.
    """

    user_id: UUID = Field(
        ...,
        description="User ID to unsubscribe",
    )
    unsubscribe_token: str = Field(
        ...,
        min_length=32,
        max_length=128,
        description="Secure unsubscribe token",
    )

    # What to unsubscribe from
    unsubscribe_type: str = Field(
        ...,
        pattern="^(all|email|sms|push|marketing|specific_category)$",
        description="Type of unsubscription",
    )

    # Category (if specific_category)
    category: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Specific category to unsubscribe from",
    )

    # Reason
    reason: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Reason for unsubscribing (optional)",
    )

    @model_validator(mode="after")
    def validate_category_requirement(self) -> "UnsubscribeRequest":
        """Validate category is provided when needed."""
        if self.unsubscribe_type == "specific_category" and not self.category:
            raise ValueError(
                "category required when unsubscribe_type is 'specific_category'"
            )
        return self

    @field_validator("unsubscribe_token")
    @classmethod
    def validate_token_format(cls, v: str) -> str:
        """Validate token is alphanumeric."""
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Invalid unsubscribe token format")
        return v