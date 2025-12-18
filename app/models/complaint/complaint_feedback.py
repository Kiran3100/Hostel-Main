"""
Complaint feedback and satisfaction tracking model.

Handles student feedback collection, ratings, and feedback analytics
for service improvement and quality monitoring.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.complaint.complaint import Complaint
    from app.models.user.user import User

__all__ = ["ComplaintFeedback"]


class ComplaintFeedback(BaseModel, TimestampMixin):
    """
    Complaint feedback and satisfaction tracking.
    
    Collects detailed feedback from students after complaint resolution
    with multi-dimensional ratings and satisfaction metrics.
    
    Attributes:
        complaint_id: Associated complaint identifier
        submitted_by: User ID who submitted feedback
        submitted_at: Feedback submission timestamp
        
        rating: Overall rating (1-5 stars)
        feedback_text: Detailed feedback comments
        
        issue_resolved_satisfactorily: Was issue resolved satisfactorily?
        response_time_satisfactory: Was response time acceptable?
        staff_helpful: Was staff helpful and professional?
        would_recommend: Would recommend complaint system?
        
        resolution_quality_rating: Resolution quality (1-5)
        communication_rating: Communication quality (1-5)
        professionalism_rating: Staff professionalism (1-5)
        
        improvement_suggestions: Suggestions for improvement
        positive_aspects: What went well
        
        is_verified: Feedback verification flag
        verified_at: Verification timestamp
        verified_by: User who verified feedback
        
        sentiment_score: Calculated sentiment score (-1 to 1)
        sentiment_label: Sentiment classification (POSITIVE, NEGATIVE, NEUTRAL)
        
        follow_up_required: Flag if follow-up needed
        follow_up_notes: Follow-up action notes
        
        metadata: Additional feedback metadata
    """

    __tablename__ = "complaint_feedbacks"
    __table_args__ = (
        # Indexes
        Index("ix_complaint_feedbacks_complaint_id", "complaint_id"),
        Index("ix_complaint_feedbacks_submitted_by", "submitted_by"),
        Index("ix_complaint_feedbacks_submitted_at", "submitted_at"),
        Index("ix_complaint_feedbacks_rating", "rating"),
        Index("ix_complaint_feedbacks_verified", "is_verified"),
        Index("ix_complaint_feedbacks_sentiment", "sentiment_label"),
        
        # Unique constraint - one feedback per complaint
        Index(
            "ix_complaint_feedbacks_unique_complaint",
            "complaint_id",
            unique=True,
        ),
        
        # Check constraints
        CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name="check_rating_range",
        ),
        CheckConstraint(
            "resolution_quality_rating IS NULL OR "
            "(resolution_quality_rating >= 1 AND resolution_quality_rating <= 5)",
            name="check_resolution_quality_rating_range",
        ),
        CheckConstraint(
            "communication_rating IS NULL OR "
            "(communication_rating >= 1 AND communication_rating <= 5)",
            name="check_communication_rating_range",
        ),
        CheckConstraint(
            "professionalism_rating IS NULL OR "
            "(professionalism_rating >= 1 AND professionalism_rating <= 5)",
            name="check_professionalism_rating_range",
        ),
        CheckConstraint(
            "sentiment_score IS NULL OR (sentiment_score >= -1 AND sentiment_score <= 1)",
            name="check_sentiment_score_range",
        ),
        CheckConstraint(
            "verified_at IS NULL OR verified_at >= submitted_at",
            name="check_verified_after_submitted",
        ),
        
        {"comment": "Complaint feedback and satisfaction tracking"},
    )

    # Foreign Keys
    complaint_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Associated complaint identifier",
    )
    
    submitted_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="User ID who submitted feedback",
    )

    # Submission Details
    submitted_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Feedback submission timestamp",
    )

    # Core Feedback
    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Overall rating (1-5 stars)",
    )
    
    feedback_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed feedback comments",
    )

    # Satisfaction Questions (Boolean Flags)
    issue_resolved_satisfactorily: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="Was the issue resolved to satisfaction?",
    )
    
    response_time_satisfactory: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="Was the response time acceptable?",
    )
    
    staff_helpful: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="Was the staff helpful and professional?",
    )
    
    would_recommend: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="Would recommend this complaint system?",
    )

    # Detailed Ratings
    resolution_quality_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Resolution quality rating (1-5)",
    )
    
    communication_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Communication quality rating (1-5)",
    )
    
    professionalism_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Staff professionalism rating (1-5)",
    )

    # Additional Feedback
    improvement_suggestions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Suggestions for improvement",
    )
    
    positive_aspects: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="What went well",
    )

    # Verification
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Feedback verification flag",
    )
    
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Verification timestamp",
    )
    
    verified_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who verified feedback",
    )

    # Sentiment Analysis
    sentiment_score: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="Calculated sentiment score (-1 to 1)",
    )
    
    sentiment_label: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="Sentiment classification (POSITIVE, NEGATIVE, NEUTRAL)",
    )

    # Follow-up
    follow_up_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Flag if follow-up needed based on feedback",
    )
    
    follow_up_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Follow-up action notes",
    )

    # Metadata
    metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Additional feedback metadata",
    )

    # Relationships
    complaint: Mapped["Complaint"] = relationship(
        "Complaint",
        back_populates="feedback_records",
        lazy="joined",
    )
    
    submitter: Mapped["User"] = relationship(
        "User",
        foreign_keys=[submitted_by],
        lazy="joined",
    )
    
    verifier: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[verified_by],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        """String representation of ComplaintFeedback."""
        return (
            f"<ComplaintFeedback(id={self.id}, "
            f"complaint_id={self.complaint_id}, "
            f"rating={self.rating}, "
            f"sentiment={self.sentiment_label})>"
        )

    @property
    def overall_satisfaction_score(self) -> float:
        """Calculate overall satisfaction score (0-100)."""
        # Weight different factors
        rating_score = (self.rating / 5.0) * 100
        
        boolean_factors = [
            self.issue_resolved_satisfactorily,
            self.response_time_satisfactory,
            self.staff_helpful,
        ]
        boolean_score = (sum(boolean_factors) / len(boolean_factors)) * 100
        
        # Weighted average (60% rating, 40% boolean factors)
        return (rating_score * 0.6) + (boolean_score * 0.4)

    @property
    def average_detailed_rating(self) -> Optional[float]:
        """Calculate average of detailed ratings if available."""
        ratings = [
            r for r in [
                self.resolution_quality_rating,
                self.communication_rating,
                self.professionalism_rating,
            ]
            if r is not None
        ]
        
        if not ratings:
            return None
        
        return sum(ratings) / len(ratings)