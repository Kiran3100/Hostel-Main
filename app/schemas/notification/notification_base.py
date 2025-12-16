# --- File: app/schemas/notification/notification_base.py ---
"""
Notification base schemas.

This module provides core notification schemas for creating, updating,
and managing notifications across different channels (email, SMS, push).
"""

from datetime import datetime
from typing import Any, Dict, List, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import NotificationType, Priority

__all__ = [
    "NotificationBase",
    "NotificationCreate",
    "NotificationUpdate",
    "MarkAsRead",
    "BulkMarkAsRead",
    "NotificationDelete",
]


class NotificationBase(BaseSchema):
    """
    Base notification schema with common fields.

    Contains recipient information, content, priority, and scheduling options
    for notifications across all channels.
    """

    # Recipient information (at least one must be provided)
    recipient_user_id: Union[UUID, None] = Field(
        default=None,
        description="Recipient user ID for user-based routing",
    )
    recipient_email: Union[str, None] = Field(
        default=None,
        description="Recipient email address for email notifications",
    )
    recipient_phone: Union[str, None] = Field(
        default=None,
        description="Recipient phone number for SMS notifications",
    )

    # Notification channel
    notification_type: NotificationType = Field(
        ...,
        description="Notification delivery channel (email/sms/push)",
    )

    # Template support
    template_code: Union[str, None] = Field(
        default=None,
        min_length=3,
        max_length=100,
        description="Template code for pre-defined notification templates",
    )

    # Content
    subject: Union[str, None] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Notification subject/title (required for email and push)",
    )
    message_body: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Notification message content",
    )

    # Priority and scheduling
    priority: Priority = Field(
        default=Priority.MEDIUM,
        description="Notification delivery priority",
    )
    scheduled_at: Union[datetime, None] = Field(
        default=None,
        description="Scheduled delivery time (null for immediate delivery)",
    )

    # Metadata and context
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context data for the notification",
    )

    # Related entity
    hostel_id: Union[UUID, None] = Field(
        default=None,
        description="Associated hostel ID for hostel-specific notifications",
    )

    @field_validator("recipient_email")
    @classmethod
    def validate_email(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate email format if provided."""
        if v is not None:
            # Basic email validation
            import re
            email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(email_pattern, v):
                raise ValueError("Invalid email format")
        return v

    @field_validator("recipient_phone")
    @classmethod
    def validate_phone(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate phone number format if provided."""
        if v is not None:
            import re
            # International phone number pattern
            phone_pattern = r"^\+?[1-9]\d{9,14}$"
            if not re.match(phone_pattern, v):
                raise ValueError(
                    "Invalid phone number format. Must be 10-15 digits, optionally starting with +"
                )
        return v

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_time(cls, v: Union[datetime, None]) -> Union[datetime, None]:
        """Validate scheduled time is in the future."""
        if v is not None and v <= datetime.utcnow():
            raise ValueError("Scheduled time must be in the future")
        return v

    @model_validator(mode="after")
    def validate_recipients(self) -> "NotificationBase":
        """Ensure at least one recipient identifier is provided."""
        if not any([
            self.recipient_user_id,
            self.recipient_email,
            self.recipient_phone,
        ]):
            raise ValueError(
                "At least one recipient identifier (user_id, email, or phone) must be provided"
            )
        return self

    @model_validator(mode="after")
    def validate_subject_requirement(self) -> "NotificationBase":
        """Validate subject is provided for email and push notifications."""
        if self.notification_type in [NotificationType.EMAIL, NotificationType.PUSH]:
            if not self.subject:
                raise ValueError(
                    f"Subject is required for {self.notification_type.value} notifications"
                )
        return self

    @model_validator(mode="after")
    def validate_message_length(self) -> "NotificationBase":
        """Validate message length based on notification type."""
        if self.notification_type == NotificationType.SMS:
            # SMS has stricter length limits
            if len(self.message_body) > 1600:  # 10 segments max
                raise ValueError(
                    "SMS message body cannot exceed 1600 characters (10 segments)"
                )
        return self


class NotificationCreate(NotificationBase, BaseCreateSchema):
    """
    Schema for creating a new notification.

    Inherits all fields from NotificationBase with creation-specific validation.
    """

    @field_validator("metadata")
    @classmethod
    def validate_metadata_size(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure metadata doesn't exceed reasonable size."""
        import json
        if len(json.dumps(v)) > 10000:  # 10KB limit
            raise ValueError("Metadata size cannot exceed 10KB")
        return v


class NotificationUpdate(BaseUpdateSchema):
    """
    Schema for updating an existing notification.

    Only allows updating limited fields: scheduling, priority, and status.
    Content updates are not permitted to maintain audit trail.
    """

    scheduled_at: Union[datetime, None] = Field(
        default=None,
        description="Update scheduled delivery time",
    )
    priority: Union[Priority, None] = Field(
        default=None,
        description="Update notification priority",
    )
    status: Union[str, None] = Field(
        default=None,
        pattern="^(queued|processing|sent|delivered|failed|cancelled)$",
        description="Update notification status",
    )

    @field_validator("scheduled_at")
    @classmethod
    def validate_scheduled_time(cls, v: Union[datetime, None]) -> Union[datetime, None]:
        """Validate scheduled time is in the future if provided."""
        if v is not None and v <= datetime.utcnow():
            raise ValueError("Scheduled time must be in the future")
        return v

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "NotificationUpdate":
        """Ensure at least one field is being updated."""
        if not any([self.scheduled_at, self.priority, self.status]):
            raise ValueError("At least one field must be provided for update")
        return self


class MarkAsRead(BaseCreateSchema):
    """Schema for marking a notification as read by a user."""

    notification_id: UUID = Field(
        ...,
        description="ID of the notification to mark as read",
    )
    user_id: UUID = Field(
        ...,
        description="ID of the user marking the notification as read",
    )
    read_at: Union[datetime, None] = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the notification was read",
    )


class BulkMarkAsRead(BaseCreateSchema):
    """Schema for marking multiple notifications as read in a single operation."""

    notification_ids: List[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of notification IDs to mark as read (max 100)",
    )
    user_id: UUID = Field(
        ...,
        description="ID of the user marking notifications as read",
    )
    read_at: Union[datetime, None] = Field(
        default_factory=datetime.utcnow,
        description="Timestamp for all read operations",
    )

    @field_validator("notification_ids")
    @classmethod
    def validate_unique_ids(cls, v: List[UUID]) -> List[UUID]:
        """Ensure notification IDs are unique."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate notification IDs are not allowed")
        return v


class NotificationDelete(BaseCreateSchema):
    """
    Schema for deleting a notification.

    Supports both soft delete (default) and permanent deletion.
    """

    notification_id: UUID = Field(
        ...,
        description="ID of the notification to delete",
    )
    user_id: UUID = Field(
        ...,
        description="ID of the user performing the deletion",
    )
    permanent: bool = Field(
        default=False,
        description="If True, permanently delete; if False, soft delete",
    )
    deletion_reason: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Reason for deletion (optional, for audit purposes)",
    )