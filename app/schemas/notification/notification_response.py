# --- File: app/schemas/notification/notification_response.py ---
"""
Notification response schemas.

This module provides response models for notification queries, lists,
and detailed information returned by the API.
"""

from datetime import datetime
from typing import Any, Dict, List, Union
from uuid import UUID

from pydantic import Field, computed_field

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import NotificationStatus, NotificationType, Priority

__all__ = [
    "NotificationResponse",
    "NotificationDetail",
    "NotificationList",
    "NotificationListItem",
    "UnreadCount",
    "NotificationSummary",
]


class NotificationResponse(BaseResponseSchema):
    """
    Standard notification response.

    Used for single notification queries and list items.
    """

    # Recipient information
    recipient_user_id: Union[UUID, None] = Field(
        default=None,
        description="Recipient user ID",
    )
    recipient_email: Union[str, None] = Field(
        default=None,
        description="Recipient email address",
    )
    recipient_phone: Union[str, None] = Field(
        default=None,
        description="Recipient phone number",
    )

    # Notification details
    notification_type: NotificationType = Field(
        ...,
        description="Notification delivery channel",
    )
    subject: Union[str, None] = Field(
        default=None,
        description="Notification subject/title",
    )
    message_body: str = Field(
        ...,
        description="Notification message content",
    )

    # Status and priority
    priority: Priority = Field(
        ...,
        description="Notification priority level",
    )
    status: NotificationStatus = Field(
        ...,
        description="Current notification status",
    )

    # Timing
    scheduled_at: Union[datetime, None] = Field(
        default=None,
        description="Scheduled delivery time",
    )
    sent_at: Union[datetime, None] = Field(
        default=None,
        description="Actual send time",
    )
    created_at: datetime = Field(
        ...,
        description="Creation timestamp",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_sent(self) -> bool:
        """Check if notification has been sent."""
        return self.status in [
            NotificationStatus.SENT,
            NotificationStatus.COMPLETED,
        ]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_pending(self) -> bool:
        """Check if notification is pending delivery."""
        return self.status in [
            NotificationStatus.QUEUED,
            NotificationStatus.PROCESSING,
        ]


class NotificationDetail(BaseResponseSchema):
    """
    Detailed notification information.

    Includes extended fields for comprehensive notification data,
    delivery tracking, and metadata.
    """

    # Recipient information
    recipient_user_id: Union[UUID, None] = Field(
        default=None,
        description="Recipient user ID",
    )
    recipient_email: Union[str, None] = Field(
        default=None,
        description="Recipient email address",
    )
    recipient_phone: Union[str, None] = Field(
        default=None,
        description="Recipient phone number",
    )

    # Template and content
    notification_type: NotificationType = Field(
        ...,
        description="Notification delivery channel",
    )
    template_code: Union[str, None] = Field(
        default=None,
        description="Template code used",
    )
    subject: Union[str, None] = Field(
        default=None,
        description="Notification subject/title",
    )
    message_body: str = Field(
        ...,
        description="Notification message content",
    )

    # Status and priority
    priority: Priority = Field(
        ...,
        description="Notification priority level",
    )
    status: NotificationStatus = Field(
        ...,
        description="Current notification status",
    )

    # Scheduling and delivery
    scheduled_at: Union[datetime, None] = Field(
        default=None,
        description="Scheduled delivery time",
    )
    sent_at: Union[datetime, None] = Field(
        default=None,
        description="Actual send time",
    )
    delivered_at: Union[datetime, None] = Field(
        default=None,
        description="Delivery confirmation time",
    )
    failed_at: Union[datetime, None] = Field(
        default=None,
        description="Failure timestamp",
    )

    # Retry and error handling
    failure_reason: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Reason for delivery failure",
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of retry attempts",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum allowed retries",
    )

    # Engagement tracking
    read_at: Union[datetime, None] = Field(
        default=None,
        description="When the notification was read",
    )
    clicked_at: Union[datetime, None] = Field(
        default=None,
        description="When any link in the notification was clicked",
    )

    # Metadata and context
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional notification metadata",
    )

    # Related entities
    hostel_id: Union[UUID, None] = Field(
        default=None,
        description="Associated hostel ID",
    )

    # Audit timestamps
    created_at: datetime = Field(
        ...,
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_read(self) -> bool:
        """Check if notification has been read."""
        return self.read_at is not None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def can_retry(self) -> bool:
        """Check if notification can be retried."""
        return (
            self.status == NotificationStatus.FAILED
            and self.retry_count < self.max_retries
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def delivery_duration_seconds(self) -> Union[int, None]:
        """Calculate delivery duration in seconds."""
        if self.sent_at and self.delivered_at:
            return int((self.delivered_at - self.sent_at).total_seconds())
        return None


class NotificationListItem(BaseSchema):
    """
    Compact notification item for list views.

    Optimized for performance with minimal data for displaying
    notification lists efficiently.
    """

    id: UUID = Field(
        ...,
        description="Notification ID",
    )
    notification_type: NotificationType = Field(
        ...,
        description="Notification channel",
    )

    # Content preview
    subject: Union[str, None] = Field(
        default=None,
        description="Notification subject",
    )
    message_preview: str = Field(
        ...,
        max_length=150,
        description="Message preview (first 150 characters)",
    )

    # Status
    priority: Priority = Field(
        ...,
        description="Priority level",
    )
    status: NotificationStatus = Field(
        ...,
        description="Current status",
    )

    # Read status
    is_read: bool = Field(
        default=False,
        description="Whether notification has been read",
    )
    read_at: Union[datetime, None] = Field(
        default=None,
        description="When notification was read",
    )

    # Timing
    created_at: datetime = Field(
        ...,
        description="Creation timestamp",
    )

    # Actions and UI
    action_url: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="URL to navigate to when notification is clicked",
    )
    icon: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="Icon identifier for UI rendering",
    )
    category: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="Notification category for grouping",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_urgent(self) -> bool:
        """Check if notification is urgent."""
        return self.priority in [Priority.URGENT, Priority.CRITICAL]


class NotificationList(BaseSchema):
    """
    Paginated list of notifications for a user.

    Includes summary statistics and list items.
    """

    user_id: UUID = Field(
        ...,
        description="User ID for this notification list",
    )
    total_notifications: int = Field(
        ...,
        ge=0,
        description="Total number of notifications",
    )
    unread_count: int = Field(
        ...,
        ge=0,
        description="Number of unread notifications",
    )
    notifications: List[NotificationListItem] = Field(
        ...,
        description="List of notification items",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def read_count(self) -> int:
        """Calculate number of read notifications."""
        return self.total_notifications - self.unread_count

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_unread(self) -> bool:
        """Check if there are any unread notifications."""
        return self.unread_count > 0


class UnreadCount(BaseSchema):
    """
    Unread notification count breakdown.

    Provides granular unread counts by type and priority.
    """

    user_id: UUID = Field(
        ...,
        description="User ID",
    )

    # Total unread
    total_unread: int = Field(
        ...,
        ge=0,
        description="Total unread notifications",
    )

    # By notification type
    email_unread: int = Field(
        default=0,
        ge=0,
        description="Unread email notifications",
    )
    sms_unread: int = Field(
        default=0,
        ge=0,
        description="Unread SMS notifications",
    )
    push_unread: int = Field(
        default=0,
        ge=0,
        description="Unread push notifications",
    )
    in_app_unread: int = Field(
        default=0,
        ge=0,
        description="Unread in-app notifications",
    )

    # By priority
    urgent_unread: int = Field(
        default=0,
        ge=0,
        description="Unread urgent/critical notifications",
    )
    high_unread: int = Field(
        default=0,
        ge=0,
        description="Unread high priority notifications",
    )

    # Timestamp
    last_checked_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When counts were last calculated",
    )


class NotificationSummary(BaseSchema):
    """
    Comprehensive notification summary for a user.

    Provides aggregate statistics and insights.
    """

    user_id: UUID = Field(
        ...,
        description="User ID",
    )

    # Overall counts
    total_notifications: int = Field(
        ...,
        ge=0,
        description="Total notifications received",
    )
    unread_notifications: int = Field(
        ...,
        ge=0,
        description="Unread notification count",
    )

    # Recent activity
    last_notification_at: Union[datetime, None] = Field(
        default=None,
        description="Timestamp of most recent notification",
    )
    last_read_at: Union[datetime, None] = Field(
        default=None,
        description="When user last read a notification",
    )

    # Breakdown by type
    notifications_by_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of notifications by type",
    )

    # Breakdown by status
    notifications_by_status: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of notifications by status",
    )

    # Breakdown by priority
    notifications_by_priority: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of notifications by priority",
    )

    # Summary period
    summary_period_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Number of days included in summary",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def read_percentage(self) -> float:
        """Calculate percentage of read notifications."""
        if self.total_notifications == 0:
            return 0.0
        read_count = self.total_notifications - self.unread_notifications
        return round((read_count / self.total_notifications) * 100, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_recent_activity(self) -> bool:
        """Check if there's been activity in the last 24 hours."""
        if not self.last_notification_at:
            return False
        time_diff = datetime.utcnow() - self.last_notification_at
        return time_diff.total_seconds() < 86400  # 24 hours