# --- File: app/schemas/payment/payment_reminder.py ---
"""
Payment reminder schemas.

This module defines schemas for payment reminder configuration,
sending reminders, and tracking reminder history.
"""

from datetime import datetime, timedelta
from typing import List, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema

__all__ = [
    "ReminderConfig",
    "ReminderLog",
    "SendReminderRequest",
    "ReminderBatch",
    "ReminderStats",
]


class ReminderConfig(BaseCreateSchema):
    """
    Payment reminder configuration schema.
    
    Defines when and how payment reminders should be sent.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel ID for this configuration",
    )

    # Reminder Timing
    days_before_due: List[int] = Field(
        ...,
        min_length=1,
        description="Days before due Date to send reminders (e.g., [7, 3, 1])",
    )
    days_after_due: List[int] = Field(
        default_factory=lambda: [1, 3, 7, 14],
        description="Days after due Date to send overdue reminders",
    )

    # Reminder Settings
    is_enabled: bool = Field(
        True,
        description="Whether reminders are enabled",
    )
    max_reminders: int = Field(
        5,
        ge=1,
        le=10,
        description="Maximum number of reminders to send per payment",
    )

    # Communication Channels
    send_email: bool = Field(
        True,
        description="Send email reminders",
    )
    send_sms: bool = Field(
        False,
        description="Send SMS reminders",
    )
    send_push: bool = Field(
        False,
        description="Send push notifications",
    )

    # Template Configuration
    email_template_id: Union[str, None] = Field(
        None,
        max_length=100,
        description="Custom email template ID",
    )
    sms_template_id: Union[str, None] = Field(
        None,
        max_length=100,
        description="Custom SMS template ID",
    )

    # Escalation
    enable_escalation: bool = Field(
        False,
        description="Enable escalation to hostel admin after X reminders",
    )
    escalation_after_reminders: int = Field(
        3,
        ge=1,
        le=10,
        description="Escalate after this many reminders",
    )

    @field_validator("days_before_due")
    @classmethod
    def validate_days_before_due(cls, v: List[int]) -> List[int]:
        """Validate days before due."""
        if not v:
            raise ValueError("At least one reminder day is required")
        
        # Ensure all values are positive
        if any(day <= 0 for day in v):
            raise ValueError("Days before due must be positive")
        
        # Sort in descending order
        return sorted(v, reverse=True)

    @field_validator("days_after_due")
    @classmethod
    def validate_days_after_due(cls, v: List[int]) -> List[int]:
        """Validate days after due."""
        # Ensure all values are positive
        if any(day <= 0 for day in v):
            raise ValueError("Days after due must be positive")
        
        # Sort in ascending order
        return sorted(v)

    @model_validator(mode="after")
    def validate_channels(self) -> "ReminderConfig":
        """Ensure at least one communication channel is enabled."""
        if not any([self.send_email, self.send_sms, self.send_push]):
            raise ValueError(
                "At least one communication channel must be enabled "
                "(email, SMS, or push notification)"
            )
        return self

    @model_validator(mode="after")
    def validate_escalation(self) -> "ReminderConfig":
        """Validate escalation settings."""
        if self.enable_escalation:
            if self.escalation_after_reminders > self.max_reminders:
                raise ValueError(
                    f"escalation_after_reminders ({self.escalation_after_reminders}) "
                    f"cannot exceed max_reminders ({self.max_reminders})"
                )
        return self


class ReminderLog(BaseResponseSchema):
    """
    Payment reminder log entry.
    
    Records when a reminder was sent and its outcome.
    """

    payment_id: UUID = Field(
        ...,
        description="Payment ID",
    )
    payment_reference: str = Field(
        ...,
        description="Payment reference",
    )

    # Student/Payer Information
    student_id: UUID = Field(
        ...,
        description="Student ID",
    )
    student_name: str = Field(
        ...,
        description="Student name",
    )
    payer_email: str = Field(
        ...,
        description="Payer email",
    )
    payer_phone: Union[str, None] = Field(
        None,
        description="Payer phone",
    )

    # Reminder Details
    reminder_type: str = Field(
        ...,
        pattern=r"^(before_due|on_due|after_due|overdue|escalation)$",
        description="Type of reminder",
    )
    reminder_number: int = Field(
        ...,
        ge=1,
        description="Reminder sequence number",
    )

    # Communication Channels
    sent_via_email: bool = Field(
        False,
        description="Whether sent via email",
    )
    sent_via_sms: bool = Field(
        False,
        description="Whether sent via SMS",
    )
    sent_via_push: bool = Field(
        False,
        description="Whether sent via push notification",
    )

    # Status
    is_successful: bool = Field(
        ...,
        description="Whether reminder was sent successfully",
    )
    error_message: Union[str, None] = Field(
        None,
        description="Error message if failed",
    )

    # Timing
    sent_at: datetime = Field(
        ...,
        description="When reminder was sent",
    )
    scheduled_for: Union[datetime, None] = Field(
        None,
        description="When reminder was scheduled for",
    )

    # Response Tracking
    email_opened: bool = Field(
        False,
        description="Whether email was opened",
    )
    email_clicked: bool = Field(
        False,
        description="Whether email link was clicked",
    )
    opened_at: Union[datetime, None] = Field(
        None,
        description="When email was opened",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def channels_used(self) -> List[str]:
        """Get list of channels used."""
        channels = []
        if self.sent_via_email:
            channels.append("email")
        if self.sent_via_sms:
            channels.append("sms")
        if self.sent_via_push:
            channels.append("push")
        return channels

    @computed_field  # type: ignore[prop-decorator]
    @property
    def reminder_type_display(self) -> str:
        """Get user-friendly reminder type."""
        type_map = {
            "before_due": "Before Due Date",
            "on_due": "On Due Date",
            "after_due": "After Due Date",
            "overdue": "Overdue",
            "escalation": "Escalation",
        }
        return type_map.get(self.reminder_type, self.reminder_type)


class SendReminderRequest(BaseCreateSchema):
    """
    Send payment reminder request.
    
    Used to manually trigger sending of payment reminders.
    """

    # Target Selection
    payment_ids: Union[List[UUID], None] = Field(
        None,
        min_length=1,
        max_length=1000,
        description="Specific payment IDs to remind (null = all eligible)",
    )
    hostel_id: Union[UUID, None] = Field(
        None,
        description="Send reminders for specific hostel",
    )

    # Filter Criteria
    only_overdue: bool = Field(
        False,
        description="Only send reminders for overdue payments",
    )
    days_overdue_min: Union[int, None] = Field(
        None,
        ge=0,
        description="Minimum days overdue",
    )
    days_overdue_max: Union[int, None] = Field(
        None,
        ge=0,
        description="Maximum days overdue",
    )

    # Reminder Options
    reminder_type: str = Field(
        "manual",
        pattern=r"^(manual|scheduled|overdue|escalation)$",
        description="Type of reminder to send",
    )
    force_send: bool = Field(
        False,
        description="Force send even if reminder was recently sent",
    )

    # Communication Channels
    via_email: bool = Field(
        True,
        description="Send via email",
    )
    via_sms: bool = Field(
        False,
        description="Send via SMS",
    )
    via_push: bool = Field(
        False,
        description="Send via push notification",
    )

    # Custom Message
    custom_message: Union[str, None] = Field(
        None,
        max_length=500,
        description="Custom message to include (optional)",
    )

    @model_validator(mode="after")
    def validate_channels(self) -> "SendReminderRequest":
        """Ensure at least one channel is selected."""
        if not any([self.via_email, self.via_sms, self.via_push]):
            raise ValueError("At least one communication channel must be selected")
        return self

    @model_validator(mode="after")
    def validate_days_overdue_range(self) -> "SendReminderRequest":
        """Validate days overdue range."""
        if self.days_overdue_min is not None and self.days_overdue_max is not None:
            if self.days_overdue_min > self.days_overdue_max:
                raise ValueError(
                    f"days_overdue_min ({self.days_overdue_min}) cannot be greater than "
                    f"days_overdue_max ({self.days_overdue_max})"
                )
        return self

    @field_validator("payment_ids")
    @classmethod
    def validate_payment_ids(cls, v: Union[List[UUID], None]) -> Union[List[UUID], None]:
        """Validate payment IDs list."""
        if v is not None:
            if len(v) == 0:
                raise ValueError("If payment_ids is specified, it cannot be empty")
            
            if len(v) > 1000:
                raise ValueError("Cannot send reminders to more than 1000 payments at once")
            
            # Check for duplicates
            if len(v) != len(set(v)):
                raise ValueError("Duplicate payment IDs found")
        
        return v


class ReminderBatch(BaseSchema):
    """
    Reminder batch execution result.
    
    Contains information about a batch of reminders sent.
    """

    batch_id: UUID = Field(
        ...,
        description="Unique batch ID",
    )

    # Execution Details
    started_at: datetime = Field(
        ...,
        description="When batch started",
    )
    completed_at: Union[datetime, None] = Field(
        None,
        description="When batch completed",
    )
    is_completed: bool = Field(
        ...,
        description="Whether batch is completed",
    )

    # Counts
    total_payments: int = Field(
        ...,
        ge=0,
        description="Total payments targeted",
    )
    reminders_sent: int = Field(
        ...,
        ge=0,
        description="Number of reminders successfully sent",
    )
    reminders_failed: int = Field(
        ...,
        ge=0,
        description="Number of reminders that failed",
    )
    reminders_skipped: int = Field(
        ...,
        ge=0,
        description="Number of reminders skipped",
    )

    # Channel Breakdown
    sent_via_email: int = Field(
        ...,
        ge=0,
        description="Sent via email",
    )
    sent_via_sms: int = Field(
        ...,
        ge=0,
        description="Sent via SMS",
    )
    sent_via_push: int = Field(
        ...,
        ge=0,
        description="Sent via push",
    )

    # Error Summary
    error_summary: Union[List[str], None] = Field(
        None,
        description="Summary of errors encountered",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_payments == 0:
            return 0.0
        return round((self.reminders_sent / self.total_payments) * 100, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def duration_seconds(self) -> Union[float, None]:
        """Calculate batch duration in seconds."""
        if self.completed_at:
            delta = self.completed_at - self.started_at
            return round(delta.total_seconds(), 2)
        return None


class ReminderStats(BaseSchema):
    """
    Payment reminder statistics.
    
    Provides aggregate statistics about payment reminders.
    """

    # Time Period
    period_start: datetime = Field(
        ...,
        description="Statistics period start",
    )
    period_end: datetime = Field(
        ...,
        description="Statistics period end",
    )

    # Hostel Filter
    hostel_id: Union[UUID, None] = Field(
        None,
        description="Statistics for specific hostel",
    )

    # Overall Counts
    total_reminders_sent: int = Field(
        ...,
        ge=0,
        description="Total reminders sent",
    )
    total_payments_reminded: int = Field(
        ...,
        ge=0,
        description="Unique payments reminded",
    )
    total_students_reminded: int = Field(
        ...,
        ge=0,
        description="Unique students reminded",
    )

    # Channel Breakdown
    email_count: int = Field(
        ...,
        ge=0,
        description="Reminders sent via email",
    )
    sms_count: int = Field(
        ...,
        ge=0,
        description="Reminders sent via SMS",
    )
    push_count: int = Field(
        ...,
        ge=0,
        description="Reminders sent via push",
    )

    # Success Metrics
    successful_reminders: int = Field(
        ...,
        ge=0,
        description="Successfully sent reminders",
    )
    failed_reminders: int = Field(
        ...,
        ge=0,
        description="Failed reminders",
    )

    # Engagement Metrics
    emails_opened: int = Field(
        ...,
        ge=0,
        description="Number of emails opened",
    )
    emails_clicked: int = Field(
        ...,
        ge=0,
        description="Number of email links clicked",
    )

    # Effectiveness
    payments_made_after_reminder: int = Field(
        ...,
        ge=0,
        description="Payments completed after reminder was sent",
    )

    # Reminder Type Breakdown
    before_due_reminders: int = Field(
        ...,
        ge=0,
        description="Before due Date reminders",
    )
    overdue_reminders: int = Field(
        ...,
        ge=0,
        description="Overdue reminders",
    )
    escalation_reminders: int = Field(
        ...,
        ge=0,
        description="Escalation reminders",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_reminders_sent == 0:
            return 0.0
        return round((self.successful_reminders / self.total_reminders_sent) * 100, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def email_open_rate(self) -> float:
        """Calculate email open rate."""
        if self.email_count == 0:
            return 0.0
        return round((self.emails_opened / self.email_count) * 100, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def email_click_rate(self) -> float:
        """Calculate email click rate."""
        if self.emails_opened == 0:
            return 0.0
        return round((self.emails_clicked / self.emails_opened) * 100, 2)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def effectiveness_rate(self) -> float:
        """Calculate reminder effectiveness (payment conversion rate)."""
        if self.total_payments_reminded == 0:
            return 0.0
        return round(
            (self.payments_made_after_reminder / self.total_payments_reminded) * 100,
            2
        )