# --- File: C:\Hostel-Main\app\models\review\review_moderation.py ---
"""
Review moderation models for content moderation and approval workflows.

Implements moderation queue, flags, and approval processes.
"""

from datetime import datetime
from decimal import Decimal
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
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship, validates

from app.models.base import BaseModel, TimestampMixin, AuditMixin

__all__ = [
    "ReviewModerationLog",
    "ReviewFlag",
    "ReviewModerationQueue",
    "ReviewAutoModeration",
]


class ReviewModerationLog(BaseModel, TimestampMixin, AuditMixin):
    """
    Review moderation action log.
    
    Tracks all moderation actions for audit and compliance.
    """
    
    __tablename__ = "review_moderation_logs"
    
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
    
    # Moderation action
    action = Column(String(50), nullable=False)
    # Actions: approve, reject, flag, unflag, hold, escalate
    
    # Moderator information
    moderator_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    moderator_name = Column(String(255), nullable=True)
    
    # Action details
    action_reason = Column(Text, nullable=True)
    previous_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=True)
    
    # Moderation metadata
    moderation_notes = Column(Text, nullable=True)
    is_automated = Column(Boolean, default=False, nullable=False)
    automation_confidence = Column(Numeric(precision=4, scale=3), nullable=True)
    
    # Notification tracking
    reviewer_notified = Column(Boolean, default=False, nullable=False)
    notification_sent_at = Column(DateTime(timezone=True), nullable=True)
    
    # Additional context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    metadata = Column(JSONB, nullable=True)
    
    # Relationships
    review = relationship("Review", back_populates="moderation_logs")
    
    __table_args__ = (
        Index("idx_review_action_created", "review_id", "action", "created_at"),
        Index("idx_moderator_created", "moderator_id", "created_at"),
    )
    
    @validates("action")
    def validate_action(self, key, value):
        """Validate moderation action."""
        valid_actions = {
            'approve', 'reject', 'flag', 'unflag', 
            'hold', 'escalate', 'auto_approve', 'auto_reject'
        }
        if value.lower() not in valid_actions:
            raise ValueError(f"Invalid moderation action: {value}")
        return value.lower()
    
    def __repr__(self):
        return (
            f"<ReviewModerationLog(review_id={self.review_id}, "
            f"action={self.action}, moderator_id={self.moderator_id})>"
        )


class ReviewFlag(BaseModel, TimestampMixin):
    """
    Review flag for user-reported issues.
    
    Allows users to report inappropriate or problematic reviews.
    """
    
    __tablename__ = "review_flags"
    
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
    
    # Reporter information
    reporter_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reporter_email = Column(String(255), nullable=True)
    
    # Flag details
    flag_reason = Column(String(100), nullable=False)
    # Reasons: inappropriate, spam, fake, offensive, profanity, not_relevant, other
    
    flag_description = Column(Text, nullable=True)
    flag_category = Column(String(50), nullable=True)
    
    # Status
    is_resolved = Column(Boolean, default=False, nullable=False, index=True)
    resolved_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    resolution_action = Column(String(50), nullable=True)
    
    # Priority
    priority = Column(String(20), default='medium', nullable=False)
    # Priority levels: low, medium, high, urgent
    
    # Additional metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    metadata = Column(JSONB, nullable=True)
    
    __table_args__ = (
        Index("idx_review_flag_status", "review_id", "is_resolved"),
        Index("idx_reporter_created", "reporter_id", "created_at"),
        Index("idx_priority_resolved", "priority", "is_resolved"),
    )
    
    @validates("flag_reason")
    def validate_flag_reason(self, key, value):
        """Validate flag reason."""
        valid_reasons = {
            'inappropriate', 'spam', 'fake', 'offensive',
            'profanity', 'not_relevant', 'other'
        }
        if value.lower() not in valid_reasons:
            raise ValueError(f"Invalid flag reason: {value}")
        return value.lower()
    
    @validates("priority")
    def validate_priority(self, key, value):
        """Validate priority level."""
        valid_priorities = {'low', 'medium', 'high', 'urgent'}
        if value.lower() not in valid_priorities:
            raise ValueError(f"Invalid priority: {value}")
        return value.lower()
    
    def resolve(self, admin_id: UUID, action: str, notes: str = None):
        """Resolve the flag."""
        self.is_resolved = True
        self.resolved_by = admin_id
        self.resolved_at = datetime.utcnow()
        self.resolution_action = action
        self.resolution_notes = notes
    
    def __repr__(self):
        return (
            f"<ReviewFlag(review_id={self.review_id}, "
            f"reason={self.flag_reason}, resolved={self.is_resolved})>"
        )


class ReviewModerationQueue(BaseModel, TimestampMixin):
    """
    Review moderation queue management.
    
    Tracks reviews pending moderation with priority and assignment.
    """
    
    __tablename__ = "review_moderation_queue"
    
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
    
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Queue status
    queue_status = Column(String(50), default='pending', nullable=False, index=True)
    # Status: pending, in_review, escalated, completed, cancelled
    
    # Assignment
    assigned_to = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    
    # Priority calculation
    priority_score = Column(Integer, default=0, nullable=False, index=True)
    requires_immediate_attention = Column(Boolean, default=False, nullable=False)
    
    # Queue metrics
    flag_count = Column(Integer, default=0, nullable=False)
    time_in_queue_hours = Column(Numeric(precision=8, scale=2), nullable=True)
    
    # AI moderation scores
    spam_score = Column(Numeric(precision=4, scale=3), nullable=True)
    sentiment_score = Column(Numeric(precision=4, scale=3), nullable=True)
    toxicity_score = Column(Numeric(precision=4, scale=3), nullable=True)
    
    # Auto-moderation recommendation
    auto_recommendation = Column(String(50), nullable=True)
    # Recommendations: auto_approve, manual_review, auto_reject
    recommendation_confidence = Column(Numeric(precision=4, scale=3), nullable=True)
    
    # Processing tracking
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Notes and metadata
    moderator_notes = Column(Text, nullable=True)
    metadata = Column(JSONB, nullable=True)
    
    __table_args__ = (
        CheckConstraint(
            "priority_score >= 0 AND priority_score <= 100",
            name="check_priority_score_range",
        ),
        Index("idx_queue_status_priority", "queue_status", "priority_score"),
        Index("idx_assigned_status", "assigned_to", "queue_status"),
        Index("idx_hostel_queue", "hostel_id", "queue_status"),
    )
    
    @validates("queue_status")
    def validate_queue_status(self, key, value):
        """Validate queue status."""
        valid_statuses = {
            'pending', 'in_review', 'escalated', 'completed', 'cancelled'
        }
        if value.lower() not in valid_statuses:
            raise ValueError(f"Invalid queue status: {value}")
        return value.lower()
    
    def assign_to_moderator(self, moderator_id: UUID):
        """Assign review to moderator."""
        self.assigned_to = moderator_id
        self.assigned_at = datetime.utcnow()
        self.queue_status = 'in_review'
        self.processing_started_at = datetime.utcnow()
    
    def escalate(self):
        """Escalate review for higher-level moderation."""
        self.queue_status = 'escalated'
        self.requires_immediate_attention = True
        self.priority_score = min(self.priority_score + 20, 100)
    
    def complete(self):
        """Mark moderation as completed."""
        self.queue_status = 'completed'
        self.processing_completed_at = datetime.utcnow()
    
    def calculate_time_in_queue(self):
        """Calculate time spent in queue."""
        if self.created_at:
            delta = datetime.utcnow() - self.created_at
            self.time_in_queue_hours = Decimal(str(round(delta.total_seconds() / 3600, 2)))
    
    def __repr__(self):
        return (
            f"<ReviewModerationQueue(review_id={self.review_id}, "
            f"status={self.queue_status}, priority={self.priority_score})>"
        )


class ReviewAutoModeration(BaseModel, TimestampMixin):
    """
    Automated review moderation results.
    
    Stores AI/ML-based moderation analysis and decisions.
    """
    
    __tablename__ = "review_auto_moderation"
    
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
    
    # Analysis scores
    spam_score = Column(Numeric(precision=4, scale=3), nullable=False)
    sentiment_score = Column(Numeric(precision=4, scale=3), nullable=False)
    toxicity_score = Column(Numeric(precision=4, scale=3), nullable=False)
    profanity_score = Column(Numeric(precision=4, scale=3), nullable=True)
    
    # Classification results
    is_spam = Column(Boolean, default=False, nullable=False)
    is_toxic = Column(Boolean, default=False, nullable=False)
    has_profanity = Column(Boolean, default=False, nullable=False)
    is_authentic = Column(Boolean, default=True, nullable=False)
    
    # Sentiment classification
    sentiment_label = Column(String(20), nullable=True)
    # Labels: positive, neutral, negative
    
    # Language detection
    detected_language = Column(String(10), nullable=True)
    language_confidence = Column(Numeric(precision=4, scale=3), nullable=True)
    
    # Content analysis
    contains_personal_info = Column(Boolean, default=False, nullable=False)
    contains_promotional_content = Column(Boolean, default=False, nullable=False)
    contains_hate_speech = Column(Boolean, default=False, nullable=False)
    
    # Auto-decision
    auto_decision = Column(String(50), nullable=False)
    # Decisions: auto_approve, manual_review, auto_reject, auto_flag
    decision_confidence = Column(Numeric(precision=4, scale=3), nullable=False)
    
    # Detected issues
    detected_issues = Column(ARRAY(String), default=list, server_default='{}')
    flagged_keywords = Column(ARRAY(String), default=list, server_default='{}')
    
    # Model information
    model_version = Column(String(50), nullable=True)
    model_timestamp = Column(DateTime(timezone=True), nullable=True)
    
    # Processing metadata
    processing_time_ms = Column(Integer, nullable=True)
    metadata = Column(JSONB, nullable=True)
    
    __table_args__ = (
        CheckConstraint(
            "spam_score >= 0 AND spam_score <= 1",
            name="check_spam_score_range",
        ),
        CheckConstraint(
            "sentiment_score >= -1 AND sentiment_score <= 1",
            name="check_sentiment_score_range",
        ),
        CheckConstraint(
            "toxicity_score >= 0 AND toxicity_score <= 1",
            name="check_toxicity_score_range",
        ),
        CheckConstraint(
            "decision_confidence >= 0 AND decision_confidence <= 1",
            name="check_decision_confidence_range",
        ),
        Index("idx_auto_decision", "auto_decision", "decision_confidence"),
        Index("idx_spam_toxic", "is_spam", "is_toxic"),
    )
    
    @validates("auto_decision")
    def validate_auto_decision(self, key, value):
        """Validate auto-decision value."""
        valid_decisions = {
            'auto_approve', 'manual_review', 'auto_reject', 'auto_flag'
        }
        if value.lower() not in valid_decisions:
            raise ValueError(f"Invalid auto-decision: {value}")
        return value.lower()
    
    @validates("sentiment_label")
    def validate_sentiment_label(self, key, value):
        """Validate sentiment label."""
        if value is None:
            return value
        valid_labels = {'positive', 'neutral', 'negative'}
        if value.lower() not in valid_labels:
            raise ValueError(f"Invalid sentiment label: {value}")
        return value.lower()
    
    def should_auto_approve(self) -> bool:
        """Determine if review should be auto-approved."""
        return (
            self.auto_decision == 'auto_approve' and
            self.decision_confidence >= Decimal('0.9') and
            not self.is_spam and
            not self.is_toxic and
            self.is_authentic
        )
    
    def should_auto_reject(self) -> bool:
        """Determine if review should be auto-rejected."""
        return (
            self.auto_decision == 'auto_reject' and
            self.decision_confidence >= Decimal('0.9') and
            (self.is_spam or self.is_toxic or not self.is_authentic)
        )
    
    def needs_manual_review(self) -> bool:
        """Determine if review needs manual review."""
        return (
            self.auto_decision == 'manual_review' or
            self.decision_confidence < Decimal('0.7') or
            self.contains_personal_info or
            self.contains_hate_speech
        )
    
    def __repr__(self):
        return (
            f"<ReviewAutoModeration(review_id={self.review_id}, "
            f"decision={self.auto_decision}, confidence={self.decision_confidence})>"
        )