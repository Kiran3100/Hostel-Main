"""
User preference schemas for notification settings and user configurations.
"""

from typing import Union

from pydantic import BaseModel, Field, field_validator

from app.schemas.common.base import BaseResponseSchema, BaseUpdateSchema

__all__ = [
    "UserNotificationPreferences",
    "UserNotificationPreferencesUpdate",
]


class UserNotificationPreferences(BaseResponseSchema):
    """
    User notification preferences response schema.
    
    Complete notification preference configuration.
    """

    # Channel preferences
    email_notifications: bool = Field(
        default=True,
        description="Enable email notifications",
    )
    sms_notifications: bool = Field(
        default=True,
        description="Enable SMS notifications",
    )
    push_notifications: bool = Field(
        default=True,
        description="Enable push notifications",
    )

    # Notification type preferences
    booking_notifications: bool = Field(
        default=True,
        description="Receive booking-related notifications",
    )
    payment_notifications: bool = Field(
        default=True,
        description="Receive payment notifications",
    )
    complaint_notifications: bool = Field(
        default=True,
        description="Receive complaint status updates",
    )
    announcement_notifications: bool = Field(
        default=True,
        description="Receive hostel announcements",
    )
    maintenance_notifications: bool = Field(
        default=True,
        description="Receive maintenance updates",
    )
    marketing_notifications: bool = Field(
        default=False,
        description="Receive marketing communications (opt-in)",
    )

    # Advanced preferences
    digest_frequency: Union[str, None] = Field(
        default="immediate",
        description="Notification digest frequency",
        examples=["immediate", "daily", "weekly", "never"],
    )
    quiet_hours_start: Union[str, None] = Field(
        default=None,
        description="Quiet hours start time (HH:MM format)",
        examples=["22:00"],
    )
    quiet_hours_end: Union[str, None] = Field(
        default=None,
        description="Quiet hours end time (HH:MM format)",
        examples=["08:00"],
    )


class UserNotificationPreferencesUpdate(BaseUpdateSchema):
    """
    Update user notification preferences.
    
    Granular control over different notification channels and types.
    """

    # Channel preferences
    email_notifications: Union[bool, None] = Field(
        default=None,
        description="Enable email notifications",
    )
    sms_notifications: Union[bool, None] = Field(
        default=None,
        description="Enable SMS notifications",
    )
    push_notifications: Union[bool, None] = Field(
        default=None,
        description="Enable push notifications",
    )

    # Notification type preferences
    booking_notifications: Union[bool, None] = Field(
        default=None,
        description="Receive booking-related notifications",
    )
    payment_notifications: Union[bool, None] = Field(
        default=None,
        description="Receive payment notifications",
    )
    complaint_notifications: Union[bool, None] = Field(
        default=None,
        description="Receive complaint status updates",
    )
    announcement_notifications: Union[bool, None] = Field(
        default=None,
        description="Receive hostel announcements",
    )
    maintenance_notifications: Union[bool, None] = Field(
        default=None,
        description="Receive maintenance updates",
    )
    marketing_notifications: Union[bool, None] = Field(
        default=None,
        description="Receive marketing communications (opt-in)",
    )

    # Advanced preferences
    digest_frequency: Union[str, None] = Field(
        default=None,
        pattern=r"^(immediate|daily|weekly|never)$",
        description="Notification digest frequency",
        examples=["immediate", "daily", "weekly", "never"],
    )
    quiet_hours_start: Union[str, None] = Field(
        default=None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Quiet hours start time (HH:MM format)",
        examples=["22:00"],
    )
    quiet_hours_end: Union[str, None] = Field(
        default=None,
        pattern=r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
        description="Quiet hours end time (HH:MM format)",
        examples=["08:00"],
    )

    @field_validator("digest_frequency")
    @classmethod
    def normalize_digest_frequency(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize digest frequency to lowercase."""
        if v is not None:
            return v.lower().strip()
        return v