# --- File: C:\Hostel-Main\app\models\inquiry\inquiry_follow_up.py ---
"""
Inquiry follow-up model for tracking communication and interactions.

This module defines the InquiryFollowUp model for comprehensive
tracking of all follow-up attempts and communications with visitors.
"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel

if TYPE_CHECKING:
    from app.models.inquiry.inquiry import Inquiry
    from app.models.user.user import User

__all__ = ["InquiryFollowUp", "ContactMethod", "ContactOutcome"]


# Enums for follow-up tracking
from enum import Enum as PyEnum


class ContactMethod(str, PyEnum):
    """Contact method for follow-up."""
    PHONE = "phone"
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    IN_PERSON = "in_person"
    OTHER = "other"


class ContactOutcome(str, PyEnum):
    """Outcome of contact attempt."""
    CONNECTED = "connected"
    NO_ANSWER = "no_answer"
    VOICEMAIL = "voicemail"
    EMAIL_SENT = "email_sent"
    EMAIL_BOUNCED = "email_bounced"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    CALLBACK_REQUESTED = "callback_requested"
    WRONG_NUMBER = "wrong_number"
    DO_NOT_CONTACT = "do_not_contact"


class InquiryFollowUp(TimestampModel):
    """
    Inquiry follow-up tracking model.
    
    Records all communication attempts and interactions with
    visitors throughout the inquiry lifecycle.
    """
    
    __tablename__ = "inquiry_follow_ups"
    
    # Primary Key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
    )
    
    # Foreign Keys
    inquiry_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inquiries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    followed_up_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Follow-up Details
    contact_method: Mapped[ContactMethod] = mapped_column(
        Enum(ContactMethod, name="contact_method_enum", create_constraint=True),
        nullable=False,
        index=True,
    )
    
    contact_outcome: Mapped[ContactOutcome] = mapped_column(
        Enum(ContactOutcome, name="contact_outcome_enum", create_constraint=True),
        nullable=False,
        index=True,
    )
    
    # Timing
    attempted_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
    
    duration_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Duration of call or meeting in minutes",
    )
    
    # Notes and Details
    notes: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    
    summary: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Brief summary of the interaction",
    )
    
    # Next Steps
    next_follow_up_date: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
        comment="Scheduled date for next follow-up",
    )
    
    action_items: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Action items and next steps",
    )
    
    # Communication Content (for emails/messages)
    subject: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Email subject or message title",
    )
    
    message_body: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Full message content if applicable",
    )
    
    # Engagement Metrics
    email_opened: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        default=False,
    )
    
    email_clicked: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        default=False,
    )
    
    response_received: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    
    response_time_hours: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Time to response in hours",
    )
    
    # Sentiment and Quality
    sentiment: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="positive, neutral, negative",
    )
    
    interest_level: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Interest level 1-5",
    )
    
    # System Fields
    is_automated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this was an automated follow-up",
    )
    
    template_used: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Template identifier if template was used",
    )
    
    # Tracking
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Sequential attempt number for this inquiry",
    )
    
    is_successful: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether contact was successfully made",
    )
    
    # Relationships
    inquiry: Mapped["Inquiry"] = relationship(
        "Inquiry",
        back_populates="follow_ups",
        lazy="selectin",
    )
    
    followed_up_by_user: Mapped["User"] = relationship(
        "User",
        lazy="selectin",
    )
    
    def __repr__(self) -> str:
        return (
            f"<InquiryFollowUp(id={self.id}, "
            f"inquiry_id={self.inquiry_id}, "
            f"method={self.contact_method.value}, "
            f"outcome={self.contact_outcome.value}, "
            f"attempted_at={self.attempted_at})>"
        )
    
    @property
    def is_recent(self) -> bool:
        """Check if follow-up was recent (within 24 hours)."""
        return (datetime.utcnow() - self.attempted_at).days < 1
    
    @property
    def days_ago(self) -> int:
        """Calculate how many days ago this follow-up occurred."""
        return (datetime.utcnow() - self.attempted_at).days
    
    @property
    def was_positive_outcome(self) -> bool:
        """Check if outcome was positive."""
        positive_outcomes = {
            ContactOutcome.CONNECTED,
            ContactOutcome.INTERESTED,
            ContactOutcome.CALLBACK_REQUESTED,
        }
        return self.contact_outcome in positive_outcomes
    
    @property
    def was_negative_outcome(self) -> bool:
        """Check if outcome was negative."""
        negative_outcomes = {
            ContactOutcome.NOT_INTERESTED,
            ContactOutcome.DO_NOT_CONTACT,
            ContactOutcome.WRONG_NUMBER,
        }
        return self.contact_outcome in negative_outcomes
    
    @property
    def needs_retry(self) -> bool:
        """Check if this follow-up needs a retry."""
        retry_outcomes = {
            ContactOutcome.NO_ANSWER,
            ContactOutcome.VOICEMAIL,
        }
        return self.contact_outcome in retry_outcomes and self.attempt_number < 3