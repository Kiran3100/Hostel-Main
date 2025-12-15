# --- File: app/schemas/notification/email_notification.py ---
"""
Email notification schemas.

This module provides schemas for email-specific notifications including
sending, tracking, templates, and bulk operations.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Optional
from uuid import UUID

from pydantic import EmailStr, Field, HttpUrl, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "EmailRequest",
    "EmailConfig",
    "EmailTracking",
    "EmailTemplate",
    "BulkEmailRequest",
    "EmailStats",
    "EmailAttachment",
    "EmailSchedule",
]


class EmailAttachment(BaseSchema):
    """Email attachment details."""

    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Attachment filename",
    )
    url: HttpUrl = Field(
        ...,
        description="URL to attachment file",
    )
    mime_type: Optional[str] = Field(
        default=None,
        max_length=100,
        description="MIME type of attachment",
    )
    size_bytes: Optional[int] = Field(
        default=None,
        ge=0,
        le=26214400,  # 25MB max
        description="File size in bytes",
    )


class EmailRequest(BaseCreateSchema):
    """
    Send email notification request.

    Supports both direct content and template-based emails with
    advanced features like CC/BCC, attachments, and tracking.
    """

    # Recipients
    recipient_email: EmailStr = Field(
        ...,
        description="Primary recipient email address",
    )
    cc_emails: List[EmailStr] = Field(
        default_factory=list,
        max_length=10,
        description="CC recipients (max 10)",
    )
    bcc_emails: List[EmailStr] = Field(
        default_factory=list,
        max_length=10,
        description="BCC recipients (max 10)",
    )

    # Content
    subject: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Email subject line",
    )
    body_html: str = Field(
        ...,
        min_length=1,
        max_length=102400,  # 100KB max
        description="HTML email body",
    )
    body_text: Optional[str] = Field(
        default=None,
        max_length=102400,
        description="Plain text fallback body",
    )

    # Attachments
    attachments: List[EmailAttachment] = Field(
        default_factory=list,
        max_length=10,
        description="Email attachments (max 10)",
    )

    # Template support
    template_code: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=100,
        description="Template code (overrides direct content)",
    )
    template_variables: Optional[Dict[str, str]] = Field(
        default=None,
        description="Variables for template rendering",
    )

    # Sender customization
    reply_to: Optional[EmailStr] = Field(
        default=None,
        description="Reply-to email address",
    )
    from_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Sender display name",
    )

    # Tracking settings
    track_opens: bool = Field(
        default=True,
        description="Enable open tracking",
    )
    track_clicks: bool = Field(
        default=True,
        description="Enable click tracking",
    )

    # Priority
    priority: str = Field(
        default="normal",
        pattern="^(low|normal|high)$",
        description="Email priority level",
    )

    # Scheduling
    send_at: Optional[datetime] = Field(
        default=None,
        description="Schedule email for future delivery",
    )

    # Metadata
    tags: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Tags for categorization and filtering",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom metadata",
    )

    @field_validator("cc_emails", "bcc_emails")
    @classmethod
    def validate_unique_emails(cls, v: List[EmailStr]) -> List[EmailStr]:
        """Ensure email lists don't contain duplicates."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate email addresses not allowed")
        return v

    @field_validator("send_at")
    @classmethod
    def validate_send_time(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate scheduled send time is in the future."""
        if v is not None and v <= datetime.utcnow():
            raise ValueError("Scheduled send time must be in the future")
        return v

    @model_validator(mode="after")
    def validate_content_or_template(self) -> "EmailRequest":
        """Ensure either direct content or template is provided."""
        if self.template_code:
            # Template mode - variables should be provided
            if not self.template_variables:
                raise ValueError(
                    "template_variables required when using template_code"
                )
        else:
            # Direct content mode - HTML body is required
            if not self.body_html:
                raise ValueError(
                    "body_html required when not using template_code"
                )
        return self

    @model_validator(mode="after")
    def validate_total_attachments_size(self) -> "EmailRequest":
        """Validate total attachments size doesn't exceed limit."""
        if self.attachments:
            total_size = sum(
                att.size_bytes for att in self.attachments if att.size_bytes
            )
            if total_size > 26214400:  # 25MB total
                raise ValueError("Total attachments size cannot exceed 25MB")
        return self


class EmailConfig(BaseSchema):
    """
    Email service configuration.

    Supports multiple email service providers with unified configuration.
    """

    # Service provider
    service_provider: str = Field(
        ...,
        pattern="^(sendgrid|ses|smtp|mailgun|postmark)$",
        description="Email service provider",
    )

    # SMTP configuration (for SMTP provider)
    smtp_host: Optional[str] = Field(
        default=None,
        max_length=255,
        description="SMTP server hostname",
    )
    smtp_port: Optional[int] = Field(
        default=None,
        ge=1,
        le=65535,
        description="SMTP server port",
    )
    smtp_username: Optional[str] = Field(
        default=None,
        max_length=255,
        description="SMTP authentication username",
    )
    smtp_use_tls: bool = Field(
        default=True,
        description="Use TLS for SMTP connection",
    )

    # API configuration (for API-based providers)
    api_key: Optional[str] = Field(
        default=None,
        max_length=500,
        description="API key for email service",
    )

    # Sender configuration
    from_email: EmailStr = Field(
        ...,
        description="Default sender email address",
    )
    from_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Default sender name",
    )
    reply_to_email: Optional[EmailStr] = Field(
        default=None,
        description="Default reply-to address",
    )

    # Rate limiting
    max_emails_per_hour: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum emails per hour",
    )
    max_emails_per_day: int = Field(
        default=1000,
        ge=1,
        le=100000,
        description="Maximum emails per day",
    )

    # Tracking defaults
    enable_open_tracking: bool = Field(
        default=True,
        description="Enable open tracking by default",
    )
    enable_click_tracking: bool = Field(
        default=True,
        description="Enable click tracking by default",
    )

    # Bounce handling
    bounce_webhook_url: Optional[HttpUrl] = Field(
        default=None,
        description="Webhook URL for bounce notifications",
    )

    @model_validator(mode="after")
    def validate_smtp_config(self) -> "EmailConfig":
        """Validate SMTP-specific configuration."""
        if self.service_provider == "smtp":
            if not all([self.smtp_host, self.smtp_port, self.smtp_username]):
                raise ValueError(
                    "SMTP configuration requires host, port, and username"
                )
        return self

    @model_validator(mode="after")
    def validate_api_config(self) -> "EmailConfig":
        """Validate API-based provider configuration."""
        if self.service_provider in ["sendgrid", "ses", "mailgun", "postmark"]:
            if not self.api_key:
                raise ValueError(
                    f"API key required for {self.service_provider}"
                )
        return self


class EmailTracking(BaseSchema):
    """
    Email tracking and delivery information.

    Tracks the complete lifecycle of an email from send to engagement.
    """

    email_id: UUID = Field(
        ...,
        description="Email notification ID",
    )
    recipient_email: EmailStr = Field(
        ...,
        description="Recipient email address",
    )

    # Delivery status
    sent_at: datetime = Field(
        ...,
        description="When email was sent",
    )
    delivered_at: Optional[datetime] = Field(
        default=None,
        description="When email was delivered",
    )
    bounced_at: Optional[datetime] = Field(
        default=None,
        description="When email bounced",
    )

    delivery_status: str = Field(
        ...,
        pattern="^(sent|delivered|bounced|failed|spam|rejected)$",
        description="Current delivery status",
    )

    # Engagement tracking
    opened: bool = Field(
        default=False,
        description="Whether email was opened",
    )
    first_opened_at: Optional[datetime] = Field(
        default=None,
        description="When email was first opened",
    )
    last_opened_at: Optional[datetime] = Field(
        default=None,
        description="When email was last opened",
    )
    open_count: int = Field(
        default=0,
        ge=0,
        description="Number of times email was opened",
    )

    clicked: bool = Field(
        default=False,
        description="Whether any link was clicked",
    )
    first_clicked_at: Optional[datetime] = Field(
        default=None,
        description="When first link was clicked",
    )
    last_clicked_at: Optional[datetime] = Field(
        default=None,
        description="When last link was clicked",
    )
    click_count: int = Field(
        default=0,
        ge=0,
        description="Total number of link clicks",
    )

    # Link-level tracking
    clicked_links: List[str] = Field(
        default_factory=list,
        description="URLs that were clicked",
    )

    # Error information
    bounce_type: Optional[str] = Field(
        default=None,
        pattern="^(hard|soft|complaint)$",
        description="Type of bounce if bounced",
    )
    error_message: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Error or bounce reason",
    )

    # Provider information
    provider_message_id: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Provider's message ID",
    )

    # Spam reports
    marked_as_spam: bool = Field(
        default=False,
        description="Whether recipient marked as spam",
    )
    spam_reported_at: Optional[datetime] = Field(
        default=None,
        description="When marked as spam",
    )


class EmailTemplate(BaseSchema):
    """
    Email-specific template configuration.

    Extends base template with email-specific features like
    header images and footer text.
    """

    template_code: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Unique template identifier",
    )

    # Email content
    subject: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Email subject template",
    )
    html_body: str = Field(
        ...,
        min_length=1,
        max_length=102400,
        description="HTML body template",
    )
    text_body: Optional[str] = Field(
        default=None,
        max_length=102400,
        description="Plain text body template",
    )

    # Styling and branding
    header_image_url: Optional[HttpUrl] = Field(
        default=None,
        description="Header/logo image URL",
    )
    footer_text: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Footer text (company info, unsubscribe link, etc.)",
    )
    primary_color: Optional[str] = Field(
        default=None,
        pattern="^#[0-9A-Fa-f]{6}$",
        description="Primary brand color (hex code)",
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

    # Preheader
    preheader_text: Optional[str] = Field(
        default=None,
        max_length=150,
        description="Email preheader/preview text",
    )


class BulkEmailRequest(BaseCreateSchema):
    """
    Send bulk emails to multiple recipients.

    Optimized for batch sending with per-recipient variable substitution.
    """

    recipients: List[EmailStr] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="List of recipient email addresses (max 1000)",
    )

    # Content (same for all recipients or use template)
    subject: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Email subject",
    )
    body_html: str = Field(
        ...,
        min_length=1,
        max_length=102400,
        description="HTML email body",
    )

    # Template support
    template_code: Optional[str] = Field(
        default=None,
        description="Template code for all emails",
    )

    # Per-recipient customization
    recipient_variables: Optional[Dict[EmailStr, Dict[str, str]]] = Field(
        default=None,
        description="Per-recipient variable mapping (email -> variables)",
    )

    # Batch settings
    batch_size: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Number of emails per batch",
    )
    delay_between_batches_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Delay between batches in seconds",
    )

    # Tracking
    track_opens: bool = Field(
        default=True,
        description="Enable open tracking",
    )
    track_clicks: bool = Field(
        default=True,
        description="Enable click tracking",
    )

    # Metadata
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for this bulk send campaign",
    )

    @field_validator("recipients")
    @classmethod
    def validate_unique_recipients(cls, v: List[EmailStr]) -> List[EmailStr]:
        """Ensure recipient list doesn't contain duplicates."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate email addresses in recipients list")
        return v

    @model_validator(mode="after")
    def validate_recipient_variables(self) -> "BulkEmailRequest":
        """Validate recipient variables match recipients list."""
        if self.recipient_variables:
            # Check all recipients have variables if any are provided
            missing = set(self.recipients) - set(self.recipient_variables.keys())
            if missing:
                raise ValueError(
                    f"Missing variables for recipients: {', '.join(str(m) for m in missing)}"
                )
        return self


class EmailStats(BaseSchema):
    """
    Email campaign statistics and metrics.

    Provides comprehensive analytics for email performance.
    """

    # Send statistics
    total_sent: int = Field(
        ...,
        ge=0,
        description="Total emails sent",
    )
    total_delivered: int = Field(
        ...,
        ge=0,
        description="Total emails delivered",
    )
    total_bounced: int = Field(
        ...,
        ge=0,
        description="Total emails bounced",
    )
    total_failed: int = Field(
        ...,
        ge=0,
        description="Total send failures",
    )

    # Delivery rates
    # Note: Pydantic v2 - Decimal fields with percentage constraints
    delivery_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Delivery rate percentage",
    )
    bounce_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Bounce rate percentage",
    )

    # Engagement statistics
    total_opened: int = Field(
        ...,
        ge=0,
        description="Total unique opens",
    )
    total_opens: int = Field(
        ...,
        ge=0,
        description="Total opens (including repeats)",
    )
    open_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Open rate percentage",
    )

    total_clicked: int = Field(
        ...,
        ge=0,
        description="Total unique clicks",
    )
    total_clicks: int = Field(
        ...,
        ge=0,
        description="Total clicks (including repeats)",
    )
    click_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Click rate percentage",
    )
    click_to_open_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Click-to-open rate percentage",
    )

    # Spam and complaints
    total_spam_reports: int = Field(
        default=0,
        ge=0,
        description="Number of spam complaints",
    )
    spam_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        default=Decimal("0"),
        description="Spam complaint rate percentage",
    )

    # Unsubscribes
    total_unsubscribed: int = Field(
        default=0,
        ge=0,
        description="Number of unsubscribes",
    )
    unsubscribe_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        default=Decimal("0"),
        description="Unsubscribe rate percentage",
    )

    # Time period
    period_start: Date = Field(
        ...,
        description="Statistics period start Date",
    )
    period_end: Date = Field(
        ...,
        description="Statistics period end Date",
    )

    @field_validator("period_end")
    @classmethod
    def validate_period(cls, v: Date, info) -> Date:
        """Validate period end is after period start."""
        period_start = info.data.get("period_start")
        if period_start and v < period_start:
            raise ValueError("period_end must be after or equal to period_start")
        return v


class EmailSchedule(BaseCreateSchema):
    """
    Schedule an email for future delivery.

    Supports recurring emails and timezone-aware scheduling.
    """

    email_request: EmailRequest = Field(
        ...,
        description="Email to schedule",
    )
    scheduled_for: datetime = Field(
        ...,
        description="When to send the email",
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone for scheduled time",
    )
    is_recurring: bool = Field(
        default=False,
        description="Whether this is a recurring email",
    )
    recurrence_pattern: Optional[str] = Field(
        default=None,
        pattern="^(daily|weekly|monthly|yearly)$",
        description="Recurrence pattern if recurring",
    )
    recurrence_end_date: Optional[Date] = Field(
        default=None,
        description="When to stop recurring",
    )

    @field_validator("scheduled_for")
    @classmethod
    def validate_scheduled_time(cls, v: datetime) -> datetime:
        """Validate scheduled time is in the future."""
        if v <= datetime.utcnow():
            raise ValueError("Scheduled time must be in the future")
        return v

    @model_validator(mode="after")
    def validate_recurrence(self) -> "EmailSchedule":
        """Validate recurrence configuration."""
        if self.is_recurring:
            if not self.recurrence_pattern:
                raise ValueError(
                    "recurrence_pattern required for recurring emails"
                )
            if not self.recurrence_end_date:
                raise ValueError(
                    "recurrence_end_date required for recurring emails"
                )
            if self.recurrence_end_date <= Date.today():
                raise ValueError(
                    "recurrence_end_date must be in the future"
                )
        return self