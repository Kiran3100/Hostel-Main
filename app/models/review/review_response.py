# --- File: C:\Hostel-Main\app\models\review\review_response.py ---
"""
Review response models for hostel management responses to reviews.

Implements hostel response system with templates and tracking.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
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

from app.models.base import BaseModel, TimestampMixin, AuditMixin

__all__ = [
    "ReviewResponse",
    "ResponseTemplate",
    "ResponseStatistics",
]


class ReviewResponse(BaseModel, TimestampMixin, AuditMixin):
    """
    Hostel management response to reviews.
    
    Allows hostel owners/admins to respond to customer feedback.
    """
    
    __tablename__ = "review_responses"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    review_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One response per review
        index=True,
    )
    
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Response content
    response_text = Column(Text, nullable=False)
    
    # Responder information
    responded_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    responded_by_name = Column(String(255), nullable=True)
    responded_by_role = Column(String(50), nullable=True)
    # Roles: hostel_admin, owner, manager, supervisor
    
    responded_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )
    
    # Template usage
    template_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("response_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_from_template = Column(Boolean, default=False, nullable=False)
    
    # Edit tracking
    is_edited = Column(Boolean, default=False, nullable=False)
    edit_count = Column(Integer, default=0, nullable=False)
    last_edited_at = Column(DateTime(timezone=True), nullable=True)
    edit_reason = Column(String(255), nullable=True)
    
    # Edit history (stores previous versions)
    edit_history = Column(JSONB, nullable=True)
    
    # Approval workflow
    requires_approval = Column(Boolean, default=False, nullable=False)
    is_approved = Column(Boolean, default=True, nullable=False)
    approved_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Visibility
    is_published = Column(Boolean, default=True, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    
    # Engagement metrics
    helpful_count = Column(Integer, default=0, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)
    
    # Response time metrics
    response_time_hours = Column(Numeric(precision=10, scale=2), nullable=True)
    
    # Quality metrics
    tone_score = Column(Numeric(precision=4, scale=3), nullable=True)
    # Automated tone analysis: professional, friendly, defensive, etc.
    
    professionalism_score = Column(Numeric(precision=4, scale=3), nullable=True)
    
    # Additional metadata
    language = Column(String(10), default='en', nullable=False)
    metadata = Column(JSONB, nullable=True)
    
    # Relationships
    review = relationship("Review", back_populates="hostel_response")
    template = relationship("ResponseTemplate", back_populates="responses")
    
    __table_args__ = (
        CheckConstraint(
            "helpful_count >= 0",
            name="check_helpful_count_positive",
        ),
        CheckConstraint(
            "view_count >= 0",
            name="check_view_count_positive",
        ),
        CheckConstraint(
            "edit_count >= 0",
            name="check_edit_count_positive",
        ),
        CheckConstraint(
            "response_time_hours IS NULL OR response_time_hours >= 0",
            name="check_response_time_positive",
        ),
        CheckConstraint(
            "tone_score IS NULL OR (tone_score >= 0 AND tone_score <= 1)",
            name="check_tone_score_range",
        ),
        CheckConstraint(
            "professionalism_score IS NULL OR (professionalism_score >= 0 AND professionalism_score <= 1)",
            name="check_professionalism_score_range",
        ),
        Index("idx_hostel_responded", "hostel_id", "responded_at"),
        Index("idx_responder_created", "responded_by", "created_at"),
    )
    
    @validates("response_text")
    def validate_response_text(self, key, value):
        """Validate response text."""
        if not value or not value.strip():
            raise ValueError("Response text cannot be empty")
        
        value = value.strip()
        
        # Minimum word count
        word_count = len(value.split())
        if word_count < 5:
            raise ValueError("Response should be more detailed (minimum 5 words)")
        
        if len(value) > 2000:
            raise ValueError("Response text must not exceed 2000 characters")
        
        # Check for placeholder text
        placeholder_phrases = [
            'lorem ipsum', 'test response', '[insert', 'placeholder'
        ]
        lower_text = value.lower()
        for phrase in placeholder_phrases:
            if phrase in lower_text:
                raise ValueError(f"Response contains placeholder text: '{phrase}'")
        
        return value
    
    @validates("responded_by_role")
    def validate_role(self, key, value):
        """Validate responder role."""
        if value is None:
            return value
        
        valid_roles = {
            'hostel_admin', 'owner', 'manager', 'supervisor', 'staff'
        }
        if value.lower() not in valid_roles:
            raise ValueError(f"Invalid responder role: {value}")
        return value.lower()
    
    def mark_as_edited(self, reason: str = None):
        """Mark response as edited and update history."""
        # Store current version in history
        if self.edit_history is None:
            self.edit_history = []
        
        self.edit_history.append({
            'version': self.edit_count + 1,
            'text': self.response_text,
            'edited_at': datetime.utcnow().isoformat(),
            'reason': self.edit_reason,
        })
        
        self.is_edited = True
        self.edit_count += 1
        self.last_edited_at = datetime.utcnow()
        self.edit_reason = reason
    
    def calculate_response_time(self, review_created_at: datetime):
        """Calculate response time from review creation."""
        if review_created_at and self.responded_at:
            delta = self.responded_at - review_created_at
            hours = delta.total_seconds() / 3600
            self.response_time_hours = Decimal(str(round(hours, 2)))
    
    def increment_helpful(self):
        """Increment helpful count."""
        self.helpful_count += 1
    
    def increment_view(self):
        """Increment view count."""
        self.view_count += 1
    
    def publish(self):
        """Publish the response."""
        self.is_published = True
        self.published_at = datetime.utcnow()
    
    def unpublish(self):
        """Unpublish the response."""
        self.is_published = False
    
    def __repr__(self):
        return (
            f"<ReviewResponse(id={self.id}, review_id={self.review_id}, "
            f"responded_by={self.responded_by})>"
        )


class ResponseTemplate(BaseModel, TimestampMixin):
    """
    Pre-approved response templates for quick responses.
    
    Helps staff respond professionally and consistently.
    """
    
    __tablename__ = "response_templates"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,  # NULL means global template
        index=True,
    )
    
    # Template identification
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Template category
    category = Column(String(50), nullable=False, index=True)
    # Categories: positive, negative, neutral, specific_issue
    
    # Template content
    template_text = Column(Text, nullable=False)
    
    # Available placeholders
    available_placeholders = Column(
        ARRAY(String),
        default=list,
        server_default='{}',
    )
    # Common placeholders: {reviewer_name}, {hostel_name}, {rating}, 
    # {responder_name}, {custom_message}
    
    # Usage tracking
    usage_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Template status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_approved = Column(Boolean, default=False, nullable=False)
    approved_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at = Column(DateTime(timezone=True), nullable=True)
    
    # Template performance metrics
    average_rating = Column(Numeric(precision=3, scale=2), nullable=True)
    effectiveness_score = Column(Numeric(precision=4, scale=3), nullable=True)
    
    # Created by
    created_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Additional metadata
    tags = Column(ARRAY(String), default=list, server_default='{}')
    metadata = Column(JSONB, nullable=True)
    
    # Relationships
    responses = relationship(
        "ReviewResponse",
        back_populates="template",
    )
    
    __table_args__ = (
        CheckConstraint(
            "usage_count >= 0",
            name="check_usage_count_positive",
        ),
        CheckConstraint(
            "average_rating IS NULL OR (average_rating >= 1 AND average_rating <= 5)",
            name="check_average_rating_range",
        ),
        CheckConstraint(
            "effectiveness_score IS NULL OR (effectiveness_score >= 0 AND effectiveness_score <= 1)",
            name="check_effectiveness_score_range",
        ),
        Index("idx_category_active", "category", "is_active"),
        Index("idx_hostel_category", "hostel_id", "category"),
    )
    
    @validates("category")
    def validate_category(self, key, value):
        """Validate template category."""
        valid_categories = {
            'positive', 'negative', 'neutral', 'specific_issue',
            'complaint', 'praise', 'mixed'
        }
        if value.lower() not in valid_categories:
            raise ValueError(f"Invalid template category: {value}")
        return value.lower()
    
    @validates("template_text")
    def validate_template_text(self, key, value):
        """Validate template text."""
        if not value or not value.strip():
            raise ValueError("Template text cannot be empty")
        
        value = value.strip()
        
        if len(value) < 50:
            raise ValueError("Template text must be at least 50 characters")
        
        if len(value) > 2000:
            raise ValueError("Template text must not exceed 2000 characters")
        
        return value
    
    def increment_usage(self):
        """Increment usage count and update last used timestamp."""
        self.usage_count += 1
        self.last_used_at = datetime.utcnow()
    
    def apply_placeholders(self, **kwargs) -> str:
        """
        Apply placeholder values to template.
        
        Args:
            **kwargs: Placeholder values (e.g., reviewer_name='John')
            
        Returns:
            Template text with placeholders replaced
        """
        text = self.template_text
        
        for placeholder, value in kwargs.items():
            text = text.replace(f"{{{placeholder}}}", str(value))
        
        return text
    
    def __repr__(self):
        return (
            f"<ResponseTemplate(id={self.id}, name={self.name}, "
            f"category={self.category}, usage={self.usage_count})>"
        )


class ResponseStatistics(BaseModel, TimestampMixin):
    """
    Response statistics for hostels.
    
    Tracks response performance and metrics.
    """
    
    __tablename__ = "response_statistics"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    hostel_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Time period for statistics
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    period_type = Column(String(20), nullable=False)
    # Types: daily, weekly, monthly, quarterly, yearly
    
    # Volume metrics
    total_reviews = Column(Integer, default=0, nullable=False)
    total_responses = Column(Integer, default=0, nullable=False)
    
    # Response rate metrics
    response_rate = Column(Numeric(precision=5, scale=2), default=0, nullable=False)
    
    # Rating-specific response rates
    response_rate_5_star = Column(Numeric(precision=5, scale=2), default=0, nullable=False)
    response_rate_4_star = Column(Numeric(precision=5, scale=2), default=0, nullable=False)
    response_rate_3_star = Column(Numeric(precision=5, scale=2), default=0, nullable=False)
    response_rate_2_star = Column(Numeric(precision=5, scale=2), default=0, nullable=False)
    response_rate_1_star = Column(Numeric(precision=5, scale=2), default=0, nullable=False)
    
    # Timing metrics
    average_response_time_hours = Column(
        Numeric(precision=8, scale=2),
        nullable=True,
    )
    median_response_time_hours = Column(
        Numeric(precision=8, scale=2),
        nullable=True,
    )
    fastest_response_hours = Column(
        Numeric(precision=8, scale=2),
        nullable=True,
    )
    slowest_response_hours = Column(
        Numeric(precision=8, scale=2),
        nullable=True,
    )
    
    # Quality metrics
    average_response_length = Column(Integer, default=0, nullable=False)
    average_tone_score = Column(Numeric(precision=4, scale=3), nullable=True)
    average_professionalism_score = Column(Numeric(precision=4, scale=3), nullable=True)
    
    # Pending responses
    pending_responses = Column(Integer, default=0, nullable=False)
    oldest_unanswered_days = Column(Integer, nullable=True)
    
    # Performance indicators
    response_health_score = Column(
        Numeric(precision=5, scale=2),
        nullable=True,
        index=True,
    )
    # Composite score: excellent (90+), good (70-89), needs_improvement (50-69), poor (<50)
    
    # Template usage
    template_usage_count = Column(Integer, default=0, nullable=False)
    template_usage_rate = Column(Numeric(precision=5, scale=2), default=0, nullable=False)
    
    # Calculation metadata
    last_calculated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    
    __table_args__ = (
        CheckConstraint(
            "total_reviews >= 0",
            name="check_total_reviews_positive",
        ),
        CheckConstraint(
            "total_responses >= 0",
            name="check_total_responses_positive",
        ),
        CheckConstraint(
            "response_rate >= 0 AND response_rate <= 100",
            name="check_response_rate_range",
        ),
        CheckConstraint(
            "response_health_score IS NULL OR (response_health_score >= 0 AND response_health_score <= 100)",
            name="check_health_score_range",
        ),
        CheckConstraint(
            "period_end > period_start",
            name="check_period_order",
        ),
        Index("idx_hostel_period", "hostel_id", "period_start", "period_end"),
        Index("idx_period_type", "period_type", "period_start"),
    )
    
    @validates("period_type")
    def validate_period_type(self, key, value):
        """Validate period type."""
        valid_types = {
            'daily', 'weekly', 'monthly', 'quarterly', 'yearly'
        }
        if value.lower() not in valid_types:
            raise ValueError(f"Invalid period type: {value}")
        return value.lower()
    
    def calculate_response_rate(self):
        """Calculate overall response rate."""
        if self.total_reviews == 0:
            self.response_rate = Decimal('0')
        else:
            rate = (self.total_responses / self.total_reviews) * 100
            self.response_rate = Decimal(str(round(rate, 2)))
    
    def calculate_health_score(self):
        """
        Calculate response health score.
        
        Based on response rate, timing, and quality metrics.
        """
        # Response rate contribution (max 50 points)
        rate_score = float(self.response_rate) / 2
        
        # Timing contribution (max 30 points)
        if self.average_response_time_hours:
            avg_hours = float(self.average_response_time_hours)
            if avg_hours <= 24:
                time_score = 30
            elif avg_hours <= 48:
                time_score = 20
            elif avg_hours <= 72:
                time_score = 10
            else:
                time_score = 5
        else:
            time_score = 0
        
        # Quality contribution (max 20 points)
        if self.average_professionalism_score:
            quality_score = float(self.average_professionalism_score) * 20
        else:
            quality_score = 10  # Neutral
        
        total_score = rate_score + time_score + quality_score
        self.response_health_score = Decimal(str(round(total_score, 2)))
    
    def get_health_status(self) -> str:
        """
        Get health status label based on score.
        
        Returns:
            Health status: excellent, good, needs_improvement, or poor
        """
        if self.response_health_score is None:
            return 'unknown'
        
        score = float(self.response_health_score)
        if score >= 90:
            return 'excellent'
        elif score >= 70:
            return 'good'
        elif score >= 50:
            return 'needs_improvement'
        else:
            return 'poor'
    
    def __repr__(self):
        return (
            f"<ResponseStatistics(hostel_id={self.hostel_id}, "
            f"period={self.period_type}, rate={self.response_rate}%)>"
        )