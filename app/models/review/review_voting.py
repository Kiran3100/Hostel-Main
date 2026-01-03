# --- File: C:\Hostel-Main\app\models\review\review_voting.py ---
"""
Review voting models for helpfulness voting system.

Implements voting, helpfulness scoring, and engagement tracking.
"""

from datetime import datetime
from decimal import Decimal
from math import sqrt
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Index,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship, validates

from app.models.base import BaseModel, TimestampMixin
from app.models.common.enums import VoteType

__all__ = [
    "ReviewVote",
    "ReviewHelpfulnessScore",
    "ReviewEngagement",
]


class ReviewVote(BaseModel, TimestampMixin):
    """
    Review helpfulness voting system.
    
    Tracks user votes on review helpfulness with fraud prevention.
    """
    
    __tablename__ = "review_votes"
    
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
    
    voter_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Vote details
    vote_type = Column(
        SQLEnum(VoteType),
        nullable=False,
    )
    
    # Optional feedback with vote
    feedback = Column(Text, nullable=True)
    
    # Vote weight (for weighted voting based on user credibility)
    vote_weight = Column(Numeric(precision=4, scale=3), default=1.0, nullable=False)
    
    # Fraud detection
    is_verified_voter = Column(Boolean, default=False, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    # Vote change tracking
    is_changed = Column(Boolean, default=False, nullable=False)
    previous_vote = Column(SQLEnum(VoteType), nullable=True)
    changed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    metadata = Column(JSONB, nullable=True)
    
    # Relationships
    review = relationship("Review", back_populates="votes")
    
    __table_args__ = (
        # Ensure one vote per user per review
        UniqueConstraint(
            "review_id",
            "voter_id",
            name="uq_review_voter",
        ),
        CheckConstraint(
            "vote_weight >= 0 AND vote_weight <= 10",
            name="check_vote_weight_range",
        ),
        Index("idx_review_vote_type", "review_id", "vote_type"),
        Index("idx_voter_created", "voter_id", "created_at"),
    )
    
    def change_vote(self, new_vote_type: VoteType):
        """Change existing vote."""
        self.previous_vote = self.vote_type
        self.vote_type = new_vote_type
        self.is_changed = True
        self.changed_at = datetime.utcnow()
    
    def __repr__(self):
        return (
            f"<ReviewVote(review_id={self.review_id}, "
            f"voter_id={self.voter_id}, type={self.vote_type})>"
        )


class ReviewHelpfulnessScore(BaseModel, TimestampMixin):
    """
    Review helpfulness scoring for intelligent ranking.
    
    Uses Wilson score for statistically sound ranking.
    """
    
    __tablename__ = "review_helpfulness_scores"
    
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
    
    # Raw vote counts
    helpful_count = Column(Integer, default=0, nullable=False)
    not_helpful_count = Column(Integer, default=0, nullable=False)
    total_votes = Column(Integer, default=0, nullable=False)
    
    # Weighted counts (considering vote weights)
    weighted_helpful = Column(Numeric(precision=10, scale=3), default=0, nullable=False)
    weighted_not_helpful = Column(Numeric(precision=10, scale=3), default=0, nullable=False)
    weighted_total = Column(Numeric(precision=10, scale=3), default=0, nullable=False)
    
    # Helpfulness metrics
    helpfulness_percentage = Column(
        Numeric(precision=5, scale=2),
        default=0,
        nullable=False,
    )
    
    # Wilson score for ranking (high precision for accurate sorting)
    wilson_score = Column(
        Numeric(precision=7, scale=6),
        default=0,
        nullable=False,
        index=True,
    )
    
    # Rank among hostel's reviews
    hostel_rank = Column(Integer, nullable=True, index=True)
    global_rank = Column(Integer, nullable=True)
    
    # Score calculation metadata
    last_calculated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    calculation_version = Column(String(20), default='1.0', nullable=False)
    
    __table_args__ = (
        CheckConstraint(
            "helpful_count >= 0",
            name="check_helpful_count_positive",
        ),
        CheckConstraint(
            "not_helpful_count >= 0",
            name="check_not_helpful_count_positive",
        ),
        CheckConstraint(
            "total_votes >= 0",
            name="check_total_votes_positive",
        ),
        CheckConstraint(
            "helpfulness_percentage >= 0 AND helpfulness_percentage <= 100",
            name="check_helpfulness_percentage_range",
        ),
        CheckConstraint(
            "wilson_score >= 0 AND wilson_score <= 1",
            name="check_wilson_score_range",
        ),
        Index("idx_wilson_score_desc", wilson_score.desc()),
        Index("idx_hostel_rank", "hostel_rank"),
    )
    
    def update_counts(self, helpful: int, not_helpful: int):
        """Update vote counts and recalculate scores."""
        self.helpful_count = helpful
        self.not_helpful_count = not_helpful
        self.total_votes = helpful + not_helpful
        
        self.calculate_helpfulness_percentage()
        self.calculate_wilson_score()
        self.last_calculated_at = datetime.utcnow()
    
    def calculate_helpfulness_percentage(self):
        """Calculate helpfulness percentage."""
        if self.total_votes == 0:
            self.helpfulness_percentage = Decimal('0')
        else:
            percentage = (self.helpful_count / self.total_votes) * 100
            self.helpfulness_percentage = Decimal(str(round(percentage, 2)))
    
    def calculate_wilson_score(self, confidence: float = 0.95):
        """
        Calculate Wilson score for ranking.
        
        Wilson score provides statistically robust ranking that handles
        the case where items with few votes aren't artificially ranked
        higher than those with many votes.
        
        Args:
            confidence: Confidence level (default 0.95 for 95%)
        """
        if self.total_votes == 0:
            self.wilson_score = Decimal('0')
            return
        
        # Z-score for confidence level
        z = 1.96 if confidence == 0.95 else 1.645  # 90% confidence
        
        phat = self.helpful_count / self.total_votes
        n = self.total_votes
        
        denominator = 1 + (z * z / n)
        numerator = (
            phat +
            (z * z / (2 * n)) -
            z * sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)
        )
        
        score = numerator / denominator
        self.wilson_score = Decimal(str(round(max(0, min(1, score)), 6)))
    
    def __repr__(self):
        return (
            f"<ReviewHelpfulnessScore(review_id={self.review_id}, "
            f"wilson_score={self.wilson_score}, votes={self.total_votes})>"
        )


class ReviewEngagement(BaseModel, TimestampMixin):
    """
    Review engagement metrics and analytics.
    
    Tracks various engagement signals for review quality assessment.
    """
    
    __tablename__ = "review_engagement"
    
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
    
    # View metrics
    view_count = Column(Integer, default=0, nullable=False)
    unique_viewers = Column(Integer, default=0, nullable=False)
    
    # Engagement actions
    share_count = Column(Integer, default=0, nullable=False)
    bookmark_count = Column(Integer, default=0, nullable=False)
    report_count = Column(Integer, default=0, nullable=False)
    
    # Time-based metrics
    average_read_time_seconds = Column(
        Numeric(precision=8, scale=2),
        nullable=True,
    )
    total_read_time_seconds = Column(
        Numeric(precision=10, scale=2),
        default=0,
        nullable=False,
    )
    
    # Engagement scores
    engagement_score = Column(
        Numeric(precision=8, scale=3),
        default=0,
        nullable=False,
        index=True,
    )
    quality_score = Column(
        Numeric(precision=8, scale=3),
        default=0,
        nullable=False,
    )
    
    # Influence metrics
    influenced_bookings = Column(Integer, default=0, nullable=False)
    influenced_inquiries = Column(Integer, default=0, nullable=False)
    
    # Recency and decay
    last_viewed_at = Column(DateTime(timezone=True), nullable=True)
    engagement_decay_factor = Column(
        Numeric(precision=4, scale=3),
        default=1.0,
        nullable=False,
    )
    
    # Calculation metadata
    last_calculated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    
    __table_args__ = (
        CheckConstraint(
            "view_count >= 0",
            name="check_view_count_positive",
        ),
        CheckConstraint(
            "unique_viewers >= 0",
            name="check_unique_viewers_positive",
        ),
        CheckConstraint(
            "engagement_score >= 0",
            name="check_engagement_score_positive",
        ),
        CheckConstraint(
            "quality_score >= 0",
            name="check_quality_score_positive",
        ),
        CheckConstraint(
            "engagement_decay_factor >= 0 AND engagement_decay_factor <= 1",
            name="check_decay_factor_range",
        ),
        Index("idx_engagement_score_desc", engagement_score.desc()),
        Index("idx_quality_score_desc", quality_score.desc()),
    )
    
    def increment_view(self, is_unique: bool = False):
        """Increment view count."""
        self.view_count += 1
        if is_unique:
            self.unique_viewers += 1
        self.last_viewed_at = datetime.utcnow()
    
    def add_read_time(self, seconds: float):
        """Add read time to metrics."""
        self.total_read_time_seconds += Decimal(str(seconds))
        if self.view_count > 0:
            avg = float(self.total_read_time_seconds) / self.view_count
            self.average_read_time_seconds = Decimal(str(round(avg, 2)))
    
    def calculate_engagement_score(self):
        """
        Calculate overall engagement score.
        
        Weighted combination of various engagement signals.
        """
        # Weight factors
        view_weight = 0.2
        vote_weight = 0.3
        share_weight = 0.2
        bookmark_weight = 0.15
        influence_weight = 0.15
        
        # Normalize counts (log scale to prevent dominance of high counts)
        from math import log1p
        
        view_score = log1p(self.view_count) * view_weight
        # Vote score would come from ReviewHelpfulnessScore
        share_score = log1p(self.share_count) * share_weight
        bookmark_score = log1p(self.bookmark_count) * bookmark_weight
        influence_score = log1p(
            self.influenced_bookings + self.influenced_inquiries
        ) * influence_weight
        
        raw_score = (
            view_score + share_score + bookmark_score + influence_score
        )
        
        # Apply decay factor for recency
        final_score = raw_score * float(self.engagement_decay_factor)
        
        self.engagement_score = Decimal(str(round(final_score, 3)))
        self.last_calculated_at = datetime.utcnow()
    
    def calculate_quality_score(
        self,
        review_rating: Decimal,
        helpfulness_score: Decimal,
        verification_status: bool,
    ):
        """
        Calculate review quality score.
        
        Combines review rating, helpfulness, and verification status.
        """
        # Base score from review rating (normalized to 0-1)
        rating_score = float(review_rating) / 5.0
        
        # Helpfulness contribution
        helpfulness_contribution = float(helpfulness_score)
        
        # Verification bonus
        verification_bonus = 0.2 if verification_status else 0
        
        # Weighted combination
        quality = (
            rating_score * 0.4 +
            helpfulness_contribution * 0.4 +
            verification_bonus
        )
        
        self.quality_score = Decimal(str(round(quality, 3)))
    
    def __repr__(self):
        return (
            f"<ReviewEngagement(review_id={self.review_id}, "
            f"views={self.view_count}, engagement={self.engagement_score})>"
        )