# --- File: app/schemas/notification/sms_notification.py ---
"""
SMS notification schemas.

This module provides schemas for SMS-specific notifications including
sending, delivery tracking, templates, and bulk operations.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "SMSRequest",
    "SMSConfig",
    "DeliveryStatus",
    "SMSTemplate",
    "BulkSMSRequest",
    "SMSStats",
    "SMSQuota",
]


class SMSRequest(BaseCreateSchema):
    """
    Send SMS notification request.

    Supports both direct message and template-based SMS with
    delivery tracking and priority handling.
    """

    # Recipient
    recipient_phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Recipient phone number in E.164 format",
    )

    # Message content
    message: str = Field(
        ...,
        min_length=1,
        max_length=1600,  # 10 SMS segments max
        description="SMS message content (max 1600 chars)",
    )

    # Template support
    template_code: Union[str, None] = Field(
        default=None,
        min_length=3,
        max_length=100,
        description="Template code (overrides direct message)",
    )
    template_variables: Union[Dict[str, str], None] = Field(
        default=None,
        description="Variables for template rendering",
    )

    # Sender configuration
    sender_id: Union[str, None] = Field(
        default=None,
        min_length=3,
        max_length=11,
        pattern="^[a-zA-Z0-9]+$",
        description="Sender ID/Name (alphanumeric, max 11 chars)",
    )

    # Priority
    priority: str = Field(
        default="normal",
        pattern="^(low|normal|high)$",
        description="SMS delivery priority",
    )

    # DLT compliance (India-specific)
    dlt_template_id: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="DLT template ID for regulatory compliance (India)",
    )
    dlt_entity_id: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="DLT entity ID (India)",
    )

    # Scheduling
    send_at: Union[datetime, None] = Field(
        default=None,
        description="Schedule SMS for future delivery",
    )

    # Tracking
    track_delivery: bool = Field(
        default=True,
        description="Enable delivery status tracking",
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

    @field_validator("message")
    @classmethod
    def validate_message_length(cls, v: str) -> str:
        """Validate message length and estimate segments."""
        # GSM-7 encoding: 160 chars per segment
        # Unicode encoding: 70 chars per segment
        if len(v) > 1600:
            raise ValueError("Message cannot exceed 1600 characters (10 segments)")
        return v

    @field_validator("recipient_phone")
    @classmethod
    def normalize_phone_number(cls, v: str) -> str:
        """Normalize phone number to E.164 format."""
        # Remove any spaces, hyphens, or parentheses
        normalized = v.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Ensure it starts with +
        if not normalized.startswith("+"):
            # Assume +91 for India if no country code
            if len(normalized) == 10:
                normalized = f"+91{normalized}"
            else:
                normalized = f"+{normalized}"
        
        return normalized

    @field_validator("send_at")
    @classmethod
    def validate_send_time(cls, v: Union[datetime, None]) -> Union[datetime, None]:
        """Validate scheduled send time is in the future."""
        if v is not None and v <= datetime.utcnow():
            raise ValueError("Scheduled send time must be in the future")
        return v

    @model_validator(mode="after")
    def validate_content_or_template(self) -> "SMSRequest":
        """Ensure either direct message or template is provided."""
        if self.template_code:
            if not self.template_variables:
                raise ValueError(
                    "template_variables required when using template_code"
                )
        else:
            if not self.message:
                raise ValueError(
                    "message required when not using template_code"
                )
        return self


class SMSConfig(BaseSchema):
    """
    SMS service configuration.

    Supports multiple SMS gateway providers with unified configuration.
    """

    # Service provider
    service_provider: str = Field(
        ...,
        pattern="^(twilio|aws_sns|msg91|vonage|plivo|custom)$",
        description="SMS service provider",
    )

    # API credentials
    account_sid: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Account SID/ID",
    )
    auth_token: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Authentication token/API key",
    )
    api_key: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="API key (alternative to auth_token)",
    )

    # Sender configuration
    default_sender_id: str = Field(
        ...,
        min_length=3,
        max_length=11,
        description="Default sender ID",
    )

    # Rate limiting
    max_sms_per_hour: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum SMS per hour",
    )
    max_sms_per_day: int = Field(
        default=1000,
        ge=1,
        le=100000,
        description="Maximum SMS per day",
    )
    max_sms_per_recipient_per_day: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum SMS per recipient per day",
    )

    # Country settings
    default_country_code: str = Field(
        default="+91",
        pattern=r"^\+\d{1,3}$",
        description="Default country code",
    )
    allowed_country_codes: List[str] = Field(
        default_factory=lambda: ["+91"],
        description="Allowed destination country codes",
    )

    # DLT settings (India)
    dlt_enabled: bool = Field(
        default=False,
        description="Enable DLT compliance checking",
    )
    dlt_entity_id: Union[str, None] = Field(
        default=None,
        description="Default DLT entity ID",
    )

    # Delivery reports
    delivery_report_webhook_url: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Webhook URL for delivery reports",
    )

    # Cost settings
    # Note: Pydantic v2 - Using Annotated for Decimal constraints
    cost_per_sms: Union[Annotated[Decimal, Field(ge=0)], None] = Field(
        default=None,
        description="Cost per SMS unit",
    )
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        description="Currency code (ISO 4217)",
    )


class DeliveryStatus(BaseSchema):
    """
    SMS delivery status and tracking information.

    Tracks the complete lifecycle of an SMS from queue to delivery.
    """

    sms_id: UUID = Field(
        ...,
        description="SMS notification ID",
    )
    recipient_phone: str = Field(
        ...,
        description="Recipient phone number",
    )

    # Delivery status
    status: str = Field(
        ...,
        pattern="^(queued|sent|delivered|failed|undelivered|expired|rejected)$",
        description="Current delivery status",
    )

    # Timeline
    queued_at: datetime = Field(
        ...,
        description="When SMS was queued",
    )
    sent_at: Union[datetime, None] = Field(
        default=None,
        description="When SMS was sent to provider",
    )
    delivered_at: Union[datetime, None] = Field(
        default=None,
        description="When SMS was delivered to recipient",
    )
    failed_at: Union[datetime, None] = Field(
        default=None,
        description="When delivery failed",
    )

    # Error information
    error_code: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="Error code from provider",
    )
    error_message: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Human-readable error message",
    )

    # Provider details
    provider_message_id: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Provider's unique message ID",
    )
    provider_status: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Raw status from provider",
    )

    # Message details
    segments_count: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Number of SMS segments used",
    )
    character_count: int = Field(
        ...,
        ge=1,
        description="Total character count",
    )
    encoding: str = Field(
        default="GSM-7",
        pattern="^(GSM-7|Unicode)$",
        description="Message encoding used",
    )

    # Cost
    cost: Union[Annotated[Decimal, Field(ge=0)], None] = Field(
        default=None,
        description="Cost for this SMS",
    )
    currency: Union[str, None] = Field(
        default=None,
        min_length=3,
        max_length=3,
        description="Currency code",
    )

    # Retry information
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of retry attempts",
    )


class SMSTemplate(BaseSchema):
    """
    SMS-specific template configuration.

    Optimized for SMS constraints with character counting and
    DLT compliance support.
    """

    template_code: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Unique template identifier",
    )

    # Message template
    message_template: str = Field(
        ...,
        min_length=1,
        max_length=1600,
        description="SMS message template with {{variables}}",
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

    # Character analysis
    estimated_length: int = Field(
        ...,
        ge=1,
        description="Estimated character length (without variables)",
    )
    estimated_segments: int = Field(
        ...,
        ge=1,
        le=10,
        description="Estimated SMS segments",
    )

    # DLT compliance (India)
    dlt_template_id: Union[str, None] = Field(
        default=None,
        max_length=50,
        description="DLT approved template ID",
    )
    dlt_approved: bool = Field(
        default=False,
        description="Whether template is DLT approved",
    )
    dlt_approval_date: Union[Date, None] = Field(
        default=None,
        description="Date of DLT approval",
    )

    # Category
    category: Union[str, None] = Field(
        default=None,
        max_length=50,
        pattern="^(transactional|promotional|otp|alert)$",
        description="SMS category",
    )


class BulkSMSRequest(BaseCreateSchema):
    """
    Send bulk SMS to multiple recipients.

    Optimized for batch sending with rate limiting and cost estimation.
    """

    recipients: List[str] = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="List of recipient phone numbers (max 10,000)",
    )

    # Message content
    message: str = Field(
        ...,
        min_length=1,
        max_length=1600,
        description="SMS message content",
    )

    # Template support
    template_code: Union[str, None] = Field(
        default=None,
        description="Template code for all SMS",
    )

    # Per-recipient customization
    recipient_variables: Union[Dict[str, Dict[str, str]], None] = Field(
        default=None,
        description="Per-recipient variable mapping (phone -> variables)",
    )

    # Sender
    sender_id: Union[str, None] = Field(
        default=None,
        max_length=11,
        description="Sender ID for all SMS",
    )

    # Batch settings
    batch_size: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Number of SMS per batch",
    )
    delay_between_batches_seconds: int = Field(
        default=2,
        ge=1,
        le=10,
        description="Delay between batches in seconds",
    )

    # Scheduling
    send_at: Union[datetime, None] = Field(
        default=None,
        description="Schedule bulk send for future",
    )

    # DLT (India)
    dlt_template_id: Union[str, None] = Field(
        default=None,
        description="DLT template ID for all SMS",
    )

    # Metadata
    campaign_name: Union[str, None] = Field(
        default=None,
        max_length=100,
        description="Campaign name for tracking",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for this bulk send",
    )

    @field_validator("recipients")
    @classmethod
    def validate_unique_recipients(cls, v: List[str]) -> List[str]:
        """Ensure recipient list doesn't contain duplicates."""
        if len(v) != len(set(v)):
            raise ValueError("Duplicate phone numbers in recipients list")
        return v

    @field_validator("recipients")
    @classmethod
    def validate_phone_numbers(cls, v: List[str]) -> List[str]:
        """Validate all phone numbers are in correct format."""
        import re
        phone_pattern = r"^\+?[1-9]\d{9,14}$"
        for phone in v:
            if not re.match(phone_pattern, phone):
                raise ValueError(f"Invalid phone number format: {phone}")
        return v


class SMSStats(BaseSchema):
    """
    SMS campaign statistics and metrics.

    Provides comprehensive analytics for SMS performance and costs.
    """

    # Send statistics
    total_sent: int = Field(
        ...,
        ge=0,
        description="Total SMS sent",
    )
    total_delivered: int = Field(
        ...,
        ge=0,
        description="Total SMS delivered",
    )
    total_failed: int = Field(
        ...,
        ge=0,
        description="Total SMS failed",
    )
    total_pending: int = Field(
        default=0,
        ge=0,
        description="Total SMS pending delivery",
    )

    # Delivery rates
    delivery_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Delivery rate percentage",
    )
    failure_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        ...,
        description="Failure rate percentage",
    )

    # Cost analysis
    total_cost: Annotated[Decimal, Field(ge=0)] = Field(
        ...,
        description="Total cost for period",
    )
    average_cost_per_sms: Annotated[Decimal, Field(ge=0)] = Field(
        ...,
        description="Average cost per SMS",
    )
    currency: str = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Currency code",
    )

    # Segment analysis
    total_segments: int = Field(
        ...,
        ge=0,
        description="Total SMS segments used",
    )
    average_segments_per_sms: Annotated[Decimal, Field(ge=0)] = Field(
        ...,
        description="Average segments per SMS",
    )

    # Breakdown by status
    delivered_count: int = Field(..., ge=0)
    failed_count: int = Field(..., ge=0)
    pending_count: int = Field(..., ge=0)
    expired_count: int = Field(default=0, ge=0)
    rejected_count: int = Field(default=0, ge=0)

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


class SMSQuota(BaseSchema):
    """
    SMS quota and usage tracking.

    Tracks SMS usage against configured limits.
    """

    # Quotas
    hourly_quota: int = Field(..., ge=0, description="Hourly SMS quota")
    daily_quota: int = Field(..., ge=0, description="Daily SMS quota")
    monthly_quota: int = Field(..., ge=0, description="Monthly SMS quota")

    # Usage
    hourly_usage: int = Field(..., ge=0, description="SMS sent this hour")
    daily_usage: int = Field(..., ge=0, description="SMS sent today")
    monthly_usage: int = Field(..., ge=0, description="SMS sent this month")

    # Remaining
    hourly_remaining: int = Field(..., ge=0, description="Remaining hourly quota")
    daily_remaining: int = Field(..., ge=0, description="Remaining daily quota")
    monthly_remaining: int = Field(..., ge=0, description="Remaining monthly quota")

    # Reset times
    hourly_reset_at: datetime = Field(..., description="When hourly quota resets")
    daily_reset_at: datetime = Field(..., description="When daily quota resets")
    monthly_reset_at: datetime = Field(..., description="When monthly quota resets")

    # Status
    is_quota_exceeded: bool = Field(
        ...,
        description="Whether any quota is exceeded",
    )