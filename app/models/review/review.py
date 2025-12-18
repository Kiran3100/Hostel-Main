# --- File: C:\Hostel-Main\app\models\review\review.py ---
"""
Review models for hostel review management.

Implements comprehensive review system with multi-aspect ratings,
verification, moderation, and lifecycle management.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Index,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship, validates

from app.models.base import BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin
from app.models.enums import ReviewStatus

__all__ = [
    "Review",
    "ReviewAspect",
    "ReviewVerification",
    "ReviewStatusHistory",
]


class Review(BaseModel, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """
    Core review entity with comprehensive review management.
    
    Supports multi-aspect ratings, verification, media attachments,
    and complete lifecycle tracking.
    """
    
    __tablename__ = "reviews"
    
    # Primary identification
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
    )
    
    # Foreign keys
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    booking_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Overall rating (stored as Decimal for precision)
    overall_rating = Column(
        Numeric(precision=2, scale=1),
        nullable=False,
        index=True,
    )
    
    # Review content
    title = Column(String(255), nullable=False)
    review_text = Column(Text, nullable=False)
    
    # Detailed aspect ratings (1-5 scale)
    cleanliness_rating = Column(Integer, nullable=True)
    food_quality_rating = Column(Integer, nullable=True)
    staff_behavior_rating = Column(Integer, nullable=True)
    security_rating = Column(Integer, nullable=True)
    value_for_money_rating = Column(Integer, nullable=True)
    amenities_rating = Column(Integer, nullable=True)
    location_rating = Column(Integer, nullable=True)
    wifi_quality_rating = Column(Integer, nullable=True)
    maintenance_rating = Column(Integer, nullable=True)
    
    # Media attachments (array of URLs)
    photos = Column(ARRAY(String), default=list, server_default='{}')
    
    # Recommendation
    would_recommend = Column(Boolean, nullable=False, default=True)
    
    # Stay details
    stay_duration_months = Column(Integer, nullable=True)
    check_in_date = Column(DateTime(timezone=True), nullable=True)
    check_out_date = Column(DateTime(timezone=True), nullable=True)
    
    # Feedback categorization
    pros = Column(ARRAY(String), default=list, server_default='{}')
    cons = Column(ARRAY(String), default=list, server_default='{}')
    
    # Verification status
    is_verified_stay = Column(Boolean, default=False, nullable=False, index=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verification_method = Column(String(50), nullable=True)
    
    # Moderation and approval
    is_approved = Column(Boolean, default=False, nullable=False, index=True)
    approved_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Flagging
    is_flagged = Column(Boolean, default=False, nullable=False, index=True)
    flag_reason = Column(String(100), nullable=True)
    flagged_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    flagged_at = Column(DateTime(timezone=True), nullable=True)
    
    # Rejection
    rejection_reason = Column(Text, nullable=True)
    rejected_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    
    # Engagement metrics
    helpful_count = Column(Integer, default=0, nullable=False)
    not_helpful_count = Column(Integer, default=0, nullable=False)
    report_count = Column(Integer, default=0, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)
    
    # Status and visibility
    status = Column(
        Enum(ReviewStatus),
        default=ReviewStatus.DRAFT,
        nullable=False,
        index=True,
    )
    is_published = Column(Boolean, default=False, nullable=False, index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    
    # AI moderation scores
    spam_score = Column(Numeric(precision=4, scale=3), nullable=True)
    sentiment_score = Column(Numeric(precision=4, scale=3), nullable=True)
    toxicity_score = Column(Numeric(precision=4, scale=3), nullable=True)
    
    # Edit tracking
    is_edited = Column(Boolean, default=False, nullable=False)
    edit_count = Column(Integer, default=0, nullable=False)
    last_edited_at = Column(DateTime(timezone=True), nullable=True)
    
    # Additional metadata
    language = Column(String(10), default='en', nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Relationships
    hostel = relationship("Hostel", back_populates="reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_id], back_populates="reviews")
    student = relationship("Student", back_populates="reviews")
    booking = relationship("Booking", back_populates="review")
    
    aspects = relationship(
        "ReviewAspect",
        back_populates="review",
        cascade="all, delete-orphan",
    )
    verification = relationship(
        "ReviewVerification",
        back_populates="review",
        uselist=False,
        cascade="all, delete-orphan",
    )
    status_history = relationship(
        "ReviewStatusHistory",
        back_populates="review",
        cascade="all, delete-orphan",
        order_by="ReviewStatusHistory.changed_at.desc()",
    )
    votes = relationship(
        "ReviewVote",
        back_populates="review",
        cascade="all, delete-orphan",
    )
    media = relationship(
        "ReviewMedia",
        back_populates="review",
        cascade="all, delete-orphan",
    )
    moderation_logs = relationship(
        "ReviewModerationLog",
        back_populates="review",
        cascade="all, delete-orphan",
    )
    hostel_response = relationship(
        "ReviewResponse",
        back_populates="review",
        uselist=False,
        cascade="all, delete-orphan",
    )
    
    # Table constraints
    __table_args__ = (
        # Ensure overall rating is within valid range
        CheckConstraint(
            "overall_rating >= 1.0 AND overall_rating <= 5.0",
            name="check_overall_rating_range",
        ),
        # Ensure aspect ratings are within valid range
        CheckConstraint(
            "cleanliness_rating IS NULL OR (cleanliness_rating >= 1 AND cleanliness_rating <= 5)",
            name="check_cleanliness_rating_range",
        ),
        CheckConstraint(
            "food_quality_rating IS NULL OR (food_quality_rating >= 1 AND food_quality_rating <= 5)",
            name="check_food_quality_rating_range",
        ),
        CheckConstraint(
            "staff_behavior_rating IS NULL OR (staff_behavior_rating >= 1 AND staff_behavior_rating <= 5)",
            name="check_staff_behavior_rating_range",
        ),
        CheckConstraint(
            "security_rating IS NULL OR (security_rating >= 1 AND security_rating <= 5)",
            name="check_security_rating_range",
        ),
        CheckConstraint(
            "value_for_money_rating IS NULL OR (value_for_money_rating >= 1 AND value_for_money_rating <= 5)",
            name="check_value_for_money_rating_range",
        ),
        CheckConstraint(
            "amenities_rating IS NULL OR (amenities_rating >= 1 AND amenities_rating <= 5)",
            name="check_amenities_rating_range",
        ),
        CheckConstraint(
            "location_rating IS NULL OR (location_rating >= 1 AND location_rating <= 5)",
            name="check_location_rating_range",
        ),
        CheckConstraint(
            "wifi_quality_rating IS NULL OR (wifi_quality_rating >= 1 AND wifi_quality_rating <= 5)",
            name="check_wifi_quality_rating_range",
        ),
        CheckConstraint(
            "maintenance_rating IS NULL OR (maintenance_rating >= 1 AND maintenance_rating <= 5)",
            name="check_maintenance_rating_range",
        ),
        # Ensure stay duration is reasonable
        CheckConstraint(
            "stay_duration_months IS NULL OR (stay_duration_months >= 1 AND stay_duration_months <= 24)",
            name="check_stay_duration_range",
        ),
        # Ensure check-out is after check-in
        CheckConstraint(
            "check_out_date IS NULL OR check_in_date IS NULL OR check_out_date > check_in_date",
            name="check_date_order",
        ),
        # Ensure engagement counts are non-negative
        CheckConstraint(
            "helpful_count >= 0",
            name="check_helpful_count_positive",
        ),
        CheckConstraint(
            "not_helpful_count >= 0",
            name="check_not_helpful_count_positive",
        ),
        CheckConstraint(
            "report_count >= 0",
            name="check_report_count_positive",
        ),
        CheckConstraint(
            "view_count >= 0",
            name="check_view_count_positive",
        ),
        # Unique constraint: one review per user per hostel
        UniqueConstraint(
            "reviewer_id",
            "hostel_id",
            name="uq_reviewer_hostel",
        ),
        # Composite indexes for common queries
        Index("idx_hostel_status_published", "hostel_id", "status", "is_published"),
        Index("idx_hostel_rating_published", "hostel_id", "overall_rating", "is_published"),
        Index("idx_reviewer_created", "reviewer_id", "created_at"),
        Index("idx_verified_approved", "is_verified_stay", "is_approved"),
        Index("idx_status_created", "status", "created_at"),
        Index("idx_flagged_status", "is_flagged", "status"),
    )
    
    @validates("overall_rating")
    def validate_overall_rating(self, key, value):
        """Validate and round overall rating to nearest 0.5."""
        if value is None:
            raise ValueError("Overall rating is required")
        
        # Convert to float for calculation
        rating = float(value)
        
        # Validate range
        if rating < 1.0 or rating > 5.0:
            raise ValueError("Overall rating must be between 1.0 and 5.0")
        
        # Round to nearest 0.5
        rounded = round(rating * 2) / 2
        return Decimal(str(rounded))
    
    @validates("title")
    def validate_title(self, key, value):
        """Validate review title."""
        if not value or not value.strip():
            raise ValueError("Review title cannot be empty")
        
        value = value.strip()
        
        if len(value) < 5:
            raise ValueError("Review title must be at least 5 characters")
        
        if len(value) > 255:
            raise ValueError("Review title must not exceed 255 characters")
        
        # Check for excessive capitalization
        if len(value) > 10 and value.isupper():
            raise ValueError("Please avoid using all caps in the title")
        
        return value
    
    @validates("review_text")
    def validate_review_text(self, key, value):
        """Validate review text."""
        if not value or not value.strip():
            raise ValueError("Review text cannot be empty")
        
        value = value.strip()
        
        # Check minimum word count
        word_count = len(value.split())
        if word_count < 10:
            raise ValueError("Review must be at least 10 words")
        
        if len(value) > 5000:
            raise ValueError("Review text must not exceed 5000 characters")
        
        return value
    
    @validates("photos")
    def validate_photos(self, key, value):
        """Validate photo URLs."""
        if not value:
            return []
        
        if len(value) > 10:
            raise ValueError("Maximum 10 photos allowed per review")
        
        return value
    
    def calculate_average_detailed_rating(self) -> Optional[Decimal]:
        """Calculate average of detailed aspect ratings."""
        ratings = [
            r for r in [
                self.cleanliness_rating,
                self.food_quality_rating,
                self.staff_behavior_rating,
                self.security_rating,
                self.value_for_money_rating,
                self.amenities_rating,
                self.location_rating,
                self.wifi_quality_rating,
                self.maintenance_rating,
            ]
            if r is not None
        ]
        
        if not ratings:
            return None
        
        return Decimal(str(round(sum(ratings) / len(ratings), 2)))
    
    def calculate_helpfulness_ratio(self) -> Decimal:
        """Calculate helpfulness ratio."""
        total_votes = self.helpful_count + self.not_helpful_count
        if total_votes == 0:
            return Decimal("0.5")  # Neutral
        return Decimal(str(round(self.helpful_count / total_votes, 3)))
    
    def mark_as_edited(self):
        """Mark review as edited."""
        self.is_edited = True
        self.edit_count += 1
        self.last_edited_at = datetime.utcnow()
    
    def approve(self, admin_id: UUID):
        """Approve review for publication."""
        self.is_approved = True
        self.approved_by = admin_id
        self.approved_at = datetime.utcnow()
        self.status = ReviewStatus.PUBLISHED
        self.is_published = True
        self.published_at = datetime.utcnow()
    
    def reject(self, admin_id: UUID, reason: str):
        """Reject review."""
        self.is_approved = False
        self.rejected_by = admin_id
        self.rejected_at = datetime.utcnow()
        self.rejection_reason = reason
        self.status = ReviewStatus.REJECTED
        self.is_published = False
    
    def flag(self, user_id: UUID, reason: str):
        """Flag review for moderation."""
        self.is_flagged = True
        self.flagged_by = user_id
        self.flagged_at = datetime.utcnow()
        self.flag_reason = reason
    
    def unflag(self):
        """Remove flag from review."""
        self.is_flagged = False
        self.flag_reason = None
        self.flagged_by = None
        self.flagged_at = None
    
    def verify_stay(self, method: str):
        """Mark review as verified stay."""
        self.is_verified_stay = True
        self.verified_at = datetime.utcnow()
        self.verification_method = method
    
    def increment_helpful(self):
        """Increment helpful vote count."""
        self.helpful_count += 1
    
    def decrement_helpful(self):
        """Decrement helpful vote count."""
        if self.helpful_count > 0:
            self.helpful_count -= 1
    
    def increment_not_helpful(self):
        """Increment not helpful vote count."""
        self.not_helpful_count += 1
    
    def decrement_not_helpful(self):
        """Decrement not helpful vote count."""
        if self.not_helpful_count > 0:
            self.not_helpful_count -= 1
    
    def increment_view(self):
        """Increment view count."""
        self.view_count += 1
    
    def __repr__(self):
        return (
            f"<Review(id={self.id}, hostel_id={self.hostel_id}, "
            f"rating={self.overall_rating}, status={self.status})>"
        )


class ReviewAspect(BaseModel, TimestampMixin):
    """
    Individual aspect ratings with detailed analysis.
    
    Allows for granular tracking of specific review aspects
    beyond the standard ratings.
    """
    
    __tablename__ = "review_aspects"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    review_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Aspect details
    aspect_name = Column(String(100), nullable=False)
    aspect_rating = Column(Integer, nullable=False)
    aspect_comment = Column(Text, nullable=True)
    
    # Sentiment analysis
    sentiment_score = Column(Numeric(precision=4, scale=3), nullable=True)
    sentiment_label = Column(String(20), nullable=True)  # positive, neutral, negative
    
    # Mention tracking
    mention_count = Column(Integer, default=1, nullable=False)
    positive_mentions = Column(Integer, default=0, nullable=False)
    negative_mentions = Column(Integer, default=0, nullable=False)
    
    # Relationships
    review = relationship("Review", back_populates="aspects")
    
    __table_args__ = (
        CheckConstraint(
            "aspect_rating >= 1 AND aspect_rating <= 5",
            name="check_aspect_rating_range",
        ),
        Index("idx_review_aspect", "review_id", "aspect_name"),
    )
    
    def __repr__(self):
        return (
            f"<ReviewAspect(review_id={self.review_id}, "
            f"aspect={self.aspect_name}, rating={self.aspect_rating})>"
        )


class ReviewVerification(BaseModel, TimestampMixin):
    """
    Review verification tracking and authenticity validation.
    
    Stores detailed information about how a review was verified
    as authentic from a real stay.
    """
    
    __tablename__ = "review_verifications"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    review_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    
    # Verification status
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_method = Column(String(50), nullable=False)
    # Methods: booking_verified, student_verified, admin_verified, auto_verified
    
    # Verification details
    verified_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Confidence scoring
    verification_confidence = Column(Numeric(precision=4, scale=3), nullable=True)
    
    # Supporting evidence
    booking_reference = Column(String(100), nullable=True)
    student_reference = Column(String(100), nullable=True)
    stay_proof_urls = Column(ARRAY(String), default=list, server_default='{}')
    
    # Verification metadata
    verification_notes = Column(Text, nullable=True)
    verification_metadata = Column(JSONB, nullable=True)
    
    # Auto-verification signals
    email_verified = Column(Boolean, default=False, nullable=False)
    phone_verified = Column(Boolean, default=False, nullable=False)
    booking_confirmed = Column(Boolean, default=False, nullable=False)
    payment_verified = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    review = relationship("Review", back_populates="verification")
    
    __table_args__ = (
        CheckConstraint(
            "verification_confidence IS NULL OR (verification_confidence >= 0 AND verification_confidence <= 1)",
            name="check_verification_confidence_range",
        ),
        Index("idx_verified_method", "is_verified", "verification_method"),
    )
    
    def __repr__(self):
        return (
            f"<ReviewVerification(review_id={self.review_id}, "
            f"verified={self.is_verified}, method={self.verification_method})>"
        )


class ReviewStatusHistory(BaseModel):
    """
    Review status change history for audit trail.
    
    Tracks all status transitions for compliance and debugging.
    """
    
    __tablename__ = "review_status_history"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    review_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Status change details
    previous_status = Column(Enum(ReviewStatus), nullable=True)
    new_status = Column(Enum(ReviewStatus), nullable=False)
    
    # Change metadata
    changed_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    changed_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    change_reason = Column(Text, nullable=True)
    
    # Additional context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    metadata = Column(JSONB, nullable=True)
    
    # Relationships
    review = relationship("Review", back_populates="status_history")
    
    __table_args__ = (
        Index("idx_review_status_changed", "review_id", "changed_at"),
    )
    
    def __repr__(self):
        return (
            f"<ReviewStatusHistory(review_id={self.review_id}, "
            f"{self.previous_status} -> {self.new_status})>"
        )