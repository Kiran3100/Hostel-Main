# --- File: app/schemas/notification/push_notification.py ---
"""
Push notification schemas.

This module provides schemas for push notification delivery across
mobile platforms (iOS, Android) and web with device management.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema
from app.schemas.common.enums import DeviceType

__all__ = [
    "PushRequest",
    "PushConfig",
    "DeviceToken",
    "DeviceRegistration",
    "DeviceUnregistration",
    "PushTemplate",
    "PushDeliveryStatus",
    "PushStats",
    "BulkPushRequest",
    "PushAction",
]


class PushAction(BaseSchema):
    """
    Push notification action button.

    Allows users to take quick actions from notification.
    """

    action_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Unique action identifier",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Action button text",
    )
    action_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="URL to open when action is tapped",
    )
    icon: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Action icon identifier",
    )


class PushRequest(BaseCreateSchema):
    """
    Send push notification request.

    Supports targeted delivery to specific users/devices with rich
    content including images, actions, and custom data.
    """

    # Recipients (at least one required)
    user_id: Optional[UUID] = Field(
        default=None,
        description="Send to all active devices of this user",
    )
    device_token: Optional[str] = Field(
        default=None,
        min_length=10,
        max_length=500,
        description="Send to specific device token",
    )
    device_tokens: Optional[List[str]] = Field(
        default=None,
        max_length=1000,
        description="Send to multiple specific devices (max 1000)",
    )
    segment: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Send to user segment",
    )

    # Content
    title: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Notification title",
    )
    body: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Notification body text",
    )

    # Rich content
    image_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Large image URL for rich notification",
    )
    icon: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Small icon identifier",
    )

    # Custom data payload
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom data payload (sent to app)",
    )

    # Actions
    action_url: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Deep link or URL to open on tap",
    )
    actions: List[PushAction] = Field(
        default_factory=list,
        max_length=3,
        description="Action buttons (max 3)",
    )

    # Badge (iOS)
    badge_count: Optional[int] = Field(
        default=None,
        ge=0,
        le=99999,
        description="Badge count for app icon",
    )
    badge_strategy: Optional[str] = Field(
        default=None,
        pattern="^(set|increment|decrement)$",
        description="How to update badge count",
    )

    # Sound
    sound: str = Field(
        default="default",
        max_length=100,
        description="Notification sound (default or custom)",
    )
    sound_volume: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Sound volume (0.0 to 1.0)",
    )

    # Priority and delivery
    priority: str = Field(
        default="normal",
        pattern="^(low|normal|high)$",
        description="Notification priority",
    )
    ttl: int = Field(
        default=86400,  # 24 hours
        ge=0,
        le=2419200,  # 28 days max
        description="Time to live in seconds",
    )

    # Collapse/grouping
    collapse_key: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Collapse key for grouping notifications",
    )
    thread_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Thread ID for notification grouping",
    )

    # Platform-specific
    android_channel_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Android notification channel ID",
    )
    ios_category: Optional[str] = Field(
        default=None,
        max_length=100,
        description="iOS notification category",
    )

    # Scheduling
    send_at: Optional[datetime] = Field(
        default=None,
        description="Schedule for future delivery",
    )

    # Metadata
    tags: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Tags for categorization",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom metadata",
    )

    @model_validator(mode="after")
    def validate_recipients(self) -> "PushRequest":
        """Ensure at least one recipient target is provided."""
        if not any([self.user_id, self.device_token, self.device_tokens, self.segment]):
            raise ValueError(
                "At least one recipient (user_id, device_token, device_tokens, or segment) required"
            )
        
        # Ensure only one targeting method is used
        targets = sum([
            bool(self.user_id),
            bool(self.device_token),
            bool(self.device_tokens),
            bool(self.segment),
        ])
        if targets > 1:
            raise ValueError(
                "Only one targeting method allowed (user_id, device_token, device_tokens, or segment)"
            )
        
        return self

    @field_validator("data")
    @classmethod
    def validate_data_size(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data payload size."""
        import json
        if len(json.dumps(v)) > 4096:  # 4KB limit
            raise ValueError("Data payload cannot exceed 4KB")
        return v

    @field_validator("send_at")
    @classmethod
    def validate_send_time(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate scheduled send time is in the future."""
        if v is not None and v <= datetime.utcnow():
            raise ValueError("Scheduled send time must be in the future")
        return v


class PushConfig(BaseSchema):
    """
    Push notification service configuration.

    Supports Firebase Cloud Messaging (FCM) and Apple Push Notification
    Service (APNs) with unified configuration.
    """

    # Firebase (Android + Web)
    firebase_project_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Firebase project ID",
    )
    firebase_server_key: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Firebase server key / FCM API key",
    )
    firebase_service_account_json: Optional[str] = Field(
        default=None,
        description="Firebase service account JSON (for v1 API)",
    )

    # APNs (iOS)
    apns_enabled: bool = Field(
        default=False,
        description="Enable APNs for iOS",
    )
    apns_key_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="APNs key ID",
    )
    apns_team_id: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Apple team ID",
    )
    apns_bundle_id: Optional[str] = Field(
        default=None,
        max_length=255,
        description="iOS app bundle ID",
    )
    apns_key_path: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Path to APNs .p8 key file",
    )
    apns_production: bool = Field(
        default=False,
        description="Use production APNs (vs sandbox)",
    )

    # Default settings
    default_sound: str = Field(
        default="default",
        description="Default notification sound",
    )
    default_priority: str = Field(
        default="normal",
        pattern="^(low|normal|high)$",
        description="Default priority",
    )
    default_ttl: int = Field(
        default=86400,
        ge=0,
        description="Default TTL in seconds",
    )

    # Collapse key
    collapse_key: Optional[str] = Field(
        default=None,
        description="Default collapse key for grouping",
    )

    # Badge management
    auto_increment_badge: bool = Field(
        default=True,
        description="Auto-increment badge count",
    )

    # Rate limiting
    max_notifications_per_hour: int = Field(
        default=1000,
        ge=1,
        description="Max push notifications per hour",
    )

    @model_validator(mode="after")
    def validate_apns_config(self) -> "PushConfig":
        """Validate APNs configuration if enabled."""
        if self.apns_enabled:
            required_fields = [
                self.apns_key_id,
                self.apns_team_id,
                self.apns_bundle_id,
                self.apns_key_path,
            ]
            if not all(required_fields):
                raise ValueError(
                    "APNs requires key_id, team_id, bundle_id, and key_path"
                )
        return self


class DeviceToken(BaseResponseSchema):
    """
    Registered device token for push notifications.

    Tracks device information and token lifecycle.
    """

    user_id: UUID = Field(
        ...,
        description="User who owns this device",
    )
    device_token: str = Field(
        ...,
        description="Device push token",
    )
    device_type: DeviceType = Field(
        ...,
        description="Device platform",
    )

    # Device details
    device_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="User-set device name",
    )
    device_model: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Device model",
    )
    os_version: Optional[str] = Field(
        default=None,
        max_length=50,
        description="OS version",
    )
    app_version: Optional[str] = Field(
        default=None,
        max_length=50,
        description="App version",
    )

    # Location and timezone
    timezone: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Device timezone",
    )
    locale: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Device locale (e.g., en_US)",
    )

    # Status
    is_active: bool = Field(
        ...,
        description="Whether device token is active",
    )
    last_used_at: datetime = Field(
        ...,
        description="When device was last active",
    )
    registered_at: datetime = Field(
        ...,
        description="When device was registered",
    )

    # Badge count
    current_badge_count: int = Field(
        default=0,
        ge=0,
        description="Current badge count for this device",
    )


class DeviceRegistration(BaseCreateSchema):
    """
    Register a device for push notifications.

    Associates a device token with a user account.
    """

    user_id: UUID = Field(
        ...,
        description="User ID to register device for",
    )
    device_token: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Device push notification token",
    )
    device_type: DeviceType = Field(
        ...,
        description="Device platform type",
    )

    # Optional device details
    device_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Device name",
    )
    device_model: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Device model",
    )
    os_version: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Operating system version",
    )
    app_version: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Application version",
    )

    # Timezone
    timezone: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Device timezone",
    )
    locale: Optional[str] = Field(
        default=None,
        max_length=10,
        description="Device locale",
    )


class DeviceUnregistration(BaseCreateSchema):
    """
    Unregister a device from push notifications.

    Removes device token to stop receiving notifications.
    """

    device_token: str = Field(
        ...,
        description="Device token to unregister",
    )
    user_id: Optional[UUID] = Field(
        default=None,
        description="User ID (for verification)",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Reason for unregistration",
    )


class PushTemplate(BaseSchema):
    """
    Push notification template.

    Defines reusable push notification structures with variables.
    """

    template_code: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Unique template identifier",
    )

    # Content templates
    title: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Title template with {{variables}}",
    )
    body: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Body template with {{variables}}",
    )

    # Default settings
    default_icon: Optional[str] = Field(
        default=None,
        description="Default notification icon",
    )
    default_sound: str = Field(
        default="default",
        description="Default notification sound",
    )
    default_image_url: Optional[str] = Field(
        default=None,
        description="Default image URL",
    )

    # Variables
    required_variables: List[str] = Field(
        ...,
        description="Required template variables",
    )
    optional_variables: List[str] = Field(
        default_factory=list,
        description="Optional template variables",
    )

    # Actions
    default_action_url: Optional[str] = Field(
        default=None,
        description="Default deep link/URL",
    )
    default_actions: List[PushAction] = Field(
        default_factory=list,
        description="Default action buttons",
    )

    # Platform-specific
    android_channel_id: Optional[str] = Field(
        default=None,
        description="Default Android channel ID",
    )
    ios_category: Optional[str] = Field(
        default=None,
        description="Default iOS category",
    )


class PushDeliveryStatus(BaseSchema):
    """
    Push notification delivery status.

    Tracks delivery and engagement for individual notifications.
    """

    notification_id: UUID = Field(
        ...,
        description="Push notification ID",
    )
    device_token: str = Field(
        ...,
        description="Target device token",
    )

    # Delivery status
    status: str = Field(
        ...,
        pattern="^(queued|sent|delivered|failed|expired|clicked)$",
        description="Current delivery status",
    )

    # Timeline
    sent_at: Optional[datetime] = Field(
        default=None,
        description="When notification was sent",
    )
    delivered_at: Optional[datetime] = Field(
        default=None,
        description="When notification was delivered to device",
    )
    clicked_at: Optional[datetime] = Field(
        default=None,
        description="When notification was clicked",
    )
    failed_at: Optional[datetime] = Field(
        default=None,
        description="When delivery failed",
    )

    # Error information
    error_code: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Error code from provider",
    )
    error_message: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Error message",
    )

    # Provider details
    provider_message_id: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Provider's message ID",
    )
    provider_response: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Raw provider response",
    )

    # Engagement
    was_clicked: bool = Field(
        default=False,
        description="Whether notification was clicked",
    )
    action_taken: Optional[str] = Field(
        default=None,
        description="Which action button was clicked (if any)",
    )


class PushStats(BaseSchema):
    """
    Push notification campaign statistics.

    Provides analytics for push notification performance.
    """

    # Send statistics
    total_sent: int = Field(
        ...,
        ge=0,
        description="Total notifications sent",
    )
    total_delivered: int = Field(
        ...,
        ge=0,
        description="Total notifications delivered",
    )
    total_failed: int = Field(
        ...,
        ge=0,
        description="Total delivery failures",
    )

    # Delivery rate
    delivery_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Delivery rate percentage",
    )

    # Platform breakdown
    ios_sent: int = Field(default=0, ge=0, description="iOS notifications sent")
    android_sent: int = Field(default=0, ge=0, description="Android notifications sent")
    web_sent: int = Field(default=0, ge=0, description="Web notifications sent")

    ios_delivered: int = Field(default=0, ge=0, description="iOS delivered")
    android_delivered: int = Field(default=0, ge=0, description="Android delivered")
    web_delivered: int = Field(default=0, ge=0, description="Web delivered")

    # Engagement statistics
    total_opened: int = Field(
        ...,
        ge=0,
        description="Total notifications clicked/opened",
    )
    open_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Click/open rate percentage",
    )

    # Action engagement
    total_action_clicks: int = Field(
        default=0,
        ge=0,
        description="Total action button clicks",
    )
    actions_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Click count by action ID",
    )

    # Time period
    period_start: Date = Field(
        ...,
        description="Statistics period start",
    )
    period_end: Date = Field(
        ...,
        description="Statistics period end",
    )

    @field_validator("period_end")
    @classmethod
    def validate_period(cls, v: Date, info) -> Date:
        """Validate period end is after period start."""
        period_start = info.data.get("period_start")
        if period_start and v < period_start:
            raise ValueError("period_end must be after or equal to period_start")
        return v


class BulkPushRequest(BaseCreateSchema):
    """
    Send push notifications to multiple users/devices in bulk.

    Optimized for mass delivery with batching and rate limiting.
    """

    # Recipients
    user_ids: Optional[List[UUID]] = Field(
        default=None,
        max_length=100000,
        description="List of user IDs (max 100,000)",
    )
    device_tokens: Optional[List[str]] = Field(
        default=None,
        max_length=100000,
        description="List of device tokens (max 100,000)",
    )
    segment: Optional[str] = Field(
        default=None,
        description="User segment to target",
    )

    # Content
    title: str = Field(..., min_length=1, max_length=100)
    body: str = Field(..., min_length=1, max_length=500)

    # Template support
    template_code: Optional[str] = Field(default=None, description="Template to use")

    # Per-user customization
    user_variables: Optional[Dict[UUID, Dict[str, str]]] = Field(
        default=None,
        description="Per-user variable mapping",
    )

    # Default settings
    image_url: Optional[str] = None
    icon: Optional[str] = None
    sound: str = Field(default="default")
    priority: str = Field(default="normal", pattern="^(low|normal|high)$")

    # Batch settings
    batch_size: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Notifications per batch",
    )
    delay_between_batches_seconds: int = Field(
        default=1,
        ge=0,
        le=10,
        description="Delay between batches",
    )

    # Metadata
    campaign_name: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Campaign name",
    )
    tags: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_recipients(self) -> "BulkPushRequest":
        """Ensure at least one recipient group is provided."""
        if not any([self.user_ids, self.device_tokens, self.segment]):
            raise ValueError(
                "At least one recipient group (user_ids, device_tokens, or segment) required"
            )
        return self