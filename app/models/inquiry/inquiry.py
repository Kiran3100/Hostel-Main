# --- File: C:\Hostel-Main\app\models\inquiry\inquiry.py ---
"""
Inquiry model for visitor inquiries and lead management.

This module defines the core Inquiry model with comprehensive
tracking of visitor inquiries, preferences, and conversion lifecycle.
"""

from datetime import date as Date, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date as SQLDate,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.schemas.common.enums import InquirySource, InquiryStatus, RoomType

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel
    from app.models.user.user import User
    from app.models.inquiry.inquiry_follow_up import InquiryFollowUp

__all__ = ["Inquiry"]


class Inquiry(TimestampModel):
    """
    Visitor inquiry model for managing hostel inquiries and lead conversion.
    
    Tracks visitor contact information, preferences, inquiry source,
    status, and conversion lifecycle.
    """
    
    __tablename__ = "inquiries"
    
    # Primary Key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
    )
    
    # Foreign Keys
    hostel_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Visitor Contact Information
    visitor_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    visitor_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    visitor_phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    
    # Inquiry Preferences
    preferred_check_in_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        index=True,
    )
    stay_duration_months: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    room_type_preference: Mapped[RoomType | None] = mapped_column(
        Enum(RoomType, name="room_type_enum", create_constraint=True),
        nullable=True,
        index=True,
    )
    
    # Inquiry Details
    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Metadata
    inquiry_source: Mapped[InquirySource] = mapped_column(
        Enum(InquirySource, name="inquiry_source_enum", create_constraint=True),
        nullable=False,
        default=InquirySource.WEBSITE,
        index=True,
    )
    
    status: Mapped[InquiryStatus] = mapped_column(
        Enum(InquiryStatus, name="inquiry_status_enum", create_constraint=True),
        nullable=False,
        default=InquiryStatus.NEW,
        index=True,
    )
    
    # Contact/Follow-up Information
    contacted_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    contacted_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
    )
    
    # Assignment Information
    assigned_to: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    
    # Internal Notes
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Conversion Tracking
    converted_to_booking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    booking_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    converted_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    converted_by: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Priority and Urgency
    is_urgent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    priority_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Calculated priority score for lead scoring",
    )
    
    # Source Tracking Details
    source_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="URL where inquiry originated",
    )
    utm_source: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    utm_medium: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    utm_campaign: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    referrer: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    
    # Device and Location Information
    device_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="mobile, desktop, tablet",
    )
    browser: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IPv4 or IPv6 address",
    )
    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    country: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    
    # Follow-up Tracking
    follow_up_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of follow-up attempts",
    )
    last_follow_up_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
    )
    next_follow_up_due: Mapped[datetime | None] = mapped_column(
        nullable=True,
        index=True,
    )
    
    # Quality and Engagement Metrics
    inquiry_quality_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Quality score based on completeness and engagement",
    )
    response_time_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Time taken to first response in minutes",
    )
    
    # Soft Delete
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )
    
    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="inquiries",
        lazy="selectin",
    )
    
    contacted_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[contacted_by],
        lazy="selectin",
    )
    
    assigned_to_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[assigned_to],
        lazy="selectin",
    )
    
    converted_by_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[converted_by],
        lazy="selectin",
    )
    
    follow_ups: Mapped[list["InquiryFollowUp"]] = relationship(
        "InquiryFollowUp",
        back_populates="inquiry",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    # Table Constraints
    __table_args__ = (
        UniqueConstraint(
            "visitor_email",
            "hostel_id",
            "created_at",
            name="uq_inquiry_email_hostel_date",
        ),
    )
    
    def __repr__(self) -> str:
        return (
            f"<Inquiry(id={self.id}, "
            f"visitor_name='{self.visitor_name}', "
            f"hostel_id={self.hostel_id}, "
            f"status={self.status.value}, "
            f"source={self.inquiry_source.value})>"
        )
    
    @property
    def age_days(self) -> int:
        """Calculate age of inquiry in days."""
        return (datetime.utcnow() - self.created_at).days
    
    @property
    def is_new(self) -> bool:
        """Check if inquiry is new (less than 24 hours old)."""
        return self.age_days < 1
    
    @property
    def is_stale(self) -> bool:
        """Check if inquiry is stale (older than 7 days without contact)."""
        return self.age_days > 7 and self.status == InquiryStatus.NEW
    
    @property
    def has_been_contacted(self) -> bool:
        """Check if visitor has been contacted."""
        return self.contacted_at is not None
    
    @property
    def is_assigned(self) -> bool:
        """Check if inquiry has been assigned."""
        return self.assigned_to is not None
    
    @property
    def has_date_preference(self) -> bool:
        """Check if visitor specified a check-in date."""
        return self.preferred_check_in_date is not None
    
    @property
    def has_duration_preference(self) -> bool:
        """Check if visitor specified stay duration."""
        return self.stay_duration_months is not None
    
    @property
    def has_room_preference(self) -> bool:
        """Check if visitor specified room type preference."""
        return self.room_type_preference is not None
    
    @property
    def is_detailed_inquiry(self) -> bool:
        """Check if inquiry has detailed information."""
        return (
            self.has_date_preference
            and self.has_duration_preference
            and self.has_room_preference
        )
    
    @property
    def urgency_level(self) -> str:
        """
        Determine urgency level.
        
        Returns: "high", "medium", or "low"
        """
        if self.is_urgent:
            return "high"
        elif self.status == InquiryStatus.NEW and self.age_days < 1:
            return "high"
        elif self.status == InquiryStatus.NEW and self.age_days < 3:
            return "medium"
        else:
            return "low"
    
    @property
    def days_since_contact(self) -> int | None:
        """Calculate days since last contact."""
        if self.contacted_at is None:
            return None
        return (datetime.utcnow() - self.contacted_at).days
    
    @property
    def needs_follow_up(self) -> bool:
        """Check if inquiry needs follow-up."""
        if self.next_follow_up_due is None:
            return False
        return datetime.utcnow() >= self.next_follow_up_due
    
    def calculate_priority_score(self) -> int:
        """
        Calculate priority score based on various factors.
        
        Returns: Priority score (0-100)
        """
        score = 50  # Base score
        
        # Recency bonus
        if self.age_days < 1:
            score += 20
        elif self.age_days < 3:
            score += 10
        elif self.age_days > 7:
            score -= 10
        
        # Completeness bonus
        if self.is_detailed_inquiry:
            score += 15
        
        # Engagement bonus
        if self.follow_up_count > 0:
            score += min(self.follow_up_count * 5, 15)
        
        # Source bonus
        if self.inquiry_source == InquirySource.REFERRAL:
            score += 10
        elif self.inquiry_source == InquirySource.WALKIN:
            score += 15
        
        # Status penalty
        if self.status == InquiryStatus.NOT_INTERESTED:
            score = 0
        elif self.status == InquiryStatus.CONVERTED:
            score = 0
        
        return max(0, min(100, score))