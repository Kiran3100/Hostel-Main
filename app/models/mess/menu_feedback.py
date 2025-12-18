# app/models/mess/menu_feedback.py
"""
Menu Feedback SQLAlchemy Models.

Comprehensive feedback collection, rating analysis, quality metrics,
and sentiment tracking for menu improvement.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Dict, List, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, SoftDeleteModel
from app.models.base.mixins import TimestampMixin, UUIDMixin
from app.models.common.enums import MealType

if TYPE_CHECKING:
    from app.models.mess.mess_menu import MessMenu
    from app.models.mess.meal_item import MealItem
    from app.models.student.student import Student
    from app.models.user.user import User
    from app.models.hostel.hostel import Hostel

__all__ = [
    "MenuFeedback",
    "ItemRating",
    "RatingsSummary",
    "QualityMetrics",
    "SentimentAnalysis",
    "FeedbackAnalysis",
    "FeedbackComment",
    "FeedbackHelpfulness",
]


class MenuFeedback(BaseModel, UUIDMixin, TimestampMixin, SoftDeleteModel):
    """
    Student feedback and ratings for menu.
    
    Comprehensive feedback system with multi-dimensional ratings,
    comments, and engagement tracking.
    """

    __tablename__ = "menu_feedbacks"

    menu_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mess_menus.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Meal information
    meal_type: Mapped[str] = mapped_column(
        Enum(MealType, name="meal_type_enum"),
        nullable=False,
        index=True,
    )
    meal_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    
    # Overall rating
    rating: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )
    
    # Detailed comments
    comments: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    comment_length: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    # Aspect-specific ratings
    taste_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    quantity_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    quality_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    hygiene_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    presentation_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    service_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    temperature_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Food temperature appropriateness",
    )
    freshness_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    # Item-specific feedback
    liked_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    disliked_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    
    # Improvement suggestions
    improvement_suggestions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Recommendation
    would_recommend: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )
    recommendation_score: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Net Promoter Score style: 0-10",
    )
    
    # Portion feedback
    portion_adequate: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )
    portion_feedback: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="too_little, just_right, too_much",
    )
    
    # Waste tracking
    food_wasted: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )
    waste_reason: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="didnt_like, too_much, health_issue, other",
    )
    
    # Verification and moderation
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    verified_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Moderation
    is_moderated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    moderation_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        comment="pending, approved, rejected, flagged",
    )
    moderation_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Engagement metrics
    helpful_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    not_helpful_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    report_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    # Visibility
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    
    # Response from management
    has_response: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    response_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    responded_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    responded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Sentiment analysis (automated)
    sentiment_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Sentiment score -100 to +100",
    )
    sentiment_label: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="very_negative, negative, neutral, positive, very_positive",
    )
    
    # Submission metadata
    submission_device: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="mobile, web, kiosk",
    )
    submission_ip: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
    )
    
    # Additional metadata
    feedback_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    menu: Mapped["MessMenu"] = relationship(
        "MessMenu",
        back_populates="feedbacks",
    )
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="menu_feedbacks",
    )
    verifier: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[verified_by],
        back_populates="verified_feedbacks",
    )
    responder: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[responded_by],
        back_populates="feedback_responses",
    )
    
    comments: Mapped[List["FeedbackComment"]] = relationship(
        "FeedbackComment",
        back_populates="feedback",
        cascade="all, delete-orphan",
    )
    helpfulness_votes: Mapped[List["FeedbackHelpfulness"]] = relationship(
        "FeedbackHelpfulness",
        back_populates="feedback",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "menu_id",
            "student_id",
            "meal_type",
            name="uq_student_menu_meal_feedback",
        ),
        CheckConstraint(
            "rating >= 1 AND rating <= 5",
            name="ck_rating_range",
        ),
        CheckConstraint(
            "taste_rating IS NULL OR (taste_rating >= 1 AND taste_rating <= 5)",
            name="ck_taste_rating_range",
        ),
        CheckConstraint(
            "quantity_rating IS NULL OR (quantity_rating >= 1 AND quantity_rating <= 5)",
            name="ck_quantity_rating_range",
        ),
        CheckConstraint(
            "quality_rating IS NULL OR (quality_rating >= 1 AND quality_rating <= 5)",
            name="ck_quality_rating_range",
        ),
        CheckConstraint(
            "hygiene_rating IS NULL OR (hygiene_rating >= 1 AND hygiene_rating <= 5)",
            name="ck_hygiene_rating_range",
        ),
        CheckConstraint(
            "presentation_rating IS NULL OR (presentation_rating >= 1 AND presentation_rating <= 5)",
            name="ck_presentation_rating_range",
        ),
        CheckConstraint(
            "service_rating IS NULL OR (service_rating >= 1 AND service_rating <= 5)",
            name="ck_service_rating_range",
        ),
        CheckConstraint(
            "recommendation_score IS NULL OR (recommendation_score >= 0 AND recommendation_score <= 10)",
            name="ck_recommendation_score_range",
        ),
        Index("ix_feedback_rating_date", "rating", "meal_date"),
        Index("ix_feedback_menu_rating", "menu_id", "rating"),
        Index("ix_feedback_verified", "is_verified", "moderation_status"),
    )

    def __repr__(self) -> str:
        return (
            f"<MenuFeedback(id={self.id}, menu_id={self.menu_id}, "
            f"student_id={self.student_id}, rating={self.rating})>"
        )

    @property
    def average_aspect_rating(self) -> Optional[Decimal]:
        """Calculate average of all aspect ratings."""
        ratings = [
            r for r in [
                self.taste_rating,
                self.quantity_rating,
                self.quality_rating,
                self.hygiene_rating,
                self.presentation_rating,
                self.service_rating,
            ]
            if r is not None
        ]
        
        if not ratings:
            return None
        
        return Decimal(str(round(sum(ratings) / len(ratings), 2)))

    @property
    def helpfulness_ratio(self) -> float:
        """Calculate helpfulness ratio."""
        total = self.helpful_count + self.not_helpful_count
        if total == 0:
            return 0.0
        return (self.helpful_count / total) * 100


class ItemRating(BaseModel, UUIDMixin, TimestampMixin):
    """
    Aggregated ratings for individual menu items.
    
    Tracks popularity and satisfaction for specific food items
    across multiple menu occurrences.
    """

    __tablename__ = "item_ratings"

    meal_item_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("meal_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Item identification (for non-standardized items)
    item_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    item_category: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    
    # Hostel context
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Rating statistics
    average_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=Decimal("0.00"),
        nullable=False,
        index=True,
    )
    total_ratings: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    # Rating distribution
    rating_5_count: Mapped[int] = mapped_column(Integer, default=0)
    rating_4_count: Mapped[int] = mapped_column(Integer, default=0)
    rating_3_count: Mapped[int] = mapped_column(Integer, default=0)
    rating_2_count: Mapped[int] = mapped_column(Integer, default=0)
    rating_1_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Feedback counts
    liked_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    disliked_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    # Serving statistics
    times_served: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_served: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    
    # Popularity metrics
    popularity_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        nullable=False,
        comment="Calculated popularity 0-100",
    )
    demand_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Student demand score",
    )
    
    # Trend analysis
    trend_direction: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="rising, stable, declining",
    )
    trend_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    
    # Recent performance (last 30 days)
    recent_average_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    recent_ratings_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    # Monthly breakdown
    monthly_stats: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Month-wise rating statistics",
    )
    
    # Last updated
    last_calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    meal_item: Mapped[Optional["MealItem"]] = relationship(
        "MealItem",
        back_populates="aggregated_ratings",
    )
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="item_ratings",
    )

    __table_args__ = (
        UniqueConstraint(
            "hostel_id",
            "item_name",
            name="uq_hostel_item_rating",
        ),
        Index("ix_item_rating_popularity", "popularity_score", "average_rating"),
    )

    def __repr__(self) -> str:
        return (
            f"<ItemRating(id={self.id}, item={self.item_name}, "
            f"avg_rating={self.average_rating}, popularity={self.popularity_score})>"
        )

    @property
    def sentiment(self) -> str:
        """Calculate overall sentiment for item."""
        rating = float(self.average_rating)
        
        if rating >= 4.5:
            return "very_positive"
        elif rating >= 4.0:
            return "positive"
        elif rating >= 3.0:
            return "neutral"
        elif rating >= 2.0:
            return "negative"
        else:
            return "very_negative"

    @property
    def like_ratio(self) -> Decimal:
        """Calculate like to dislike ratio."""
        total = self.liked_count + self.disliked_count
        
        if total == 0:
            return Decimal("0.00")
        
        return round(Decimal(self.liked_count) / Decimal(total) * 100, 2)


class RatingsSummary(BaseModel, UUIDMixin, TimestampMixin):
    """
    Comprehensive ratings summary for menu.
    
    Aggregates all feedback data for a menu with statistical
    analysis and distribution metrics.
    """

    __tablename__ = "ratings_summaries"

    menu_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mess_menus.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    menu_date: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    
    # Overall statistics
    total_feedbacks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    average_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=Decimal("0.00"),
        nullable=False,
        index=True,
    )
    median_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    mode_rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    
    # Meal-specific ratings
    breakfast_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    breakfast_feedback_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    lunch_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    lunch_feedback_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    snacks_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    snacks_feedback_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    dinner_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    dinner_feedback_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    # Rating distribution
    rating_5_count: Mapped[int] = mapped_column(Integer, default=0)
    rating_4_count: Mapped[int] = mapped_column(Integer, default=0)
    rating_3_count: Mapped[int] = mapped_column(Integer, default=0)
    rating_2_count: Mapped[int] = mapped_column(Integer, default=0)
    rating_1_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Aspect ratings
    average_taste_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    average_quantity_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    average_quality_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    average_hygiene_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    average_presentation_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    average_service_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    
    # Recommendation metrics
    would_recommend_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    would_not_recommend_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    would_recommend_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    net_promoter_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="NPS: -100 to +100",
    )
    
    # Participation metrics
    total_students: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Total students in hostel",
    )
    participation_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    
    # Satisfaction levels
    very_satisfied_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Ratings 5",
    )
    satisfied_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Ratings 4",
    )
    neutral_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Ratings 3",
    )
    dissatisfied_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Ratings 2",
    )
    very_dissatisfied_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Ratings 1",
    )
    
    # Satisfaction percentages
    satisfaction_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        nullable=False,
        comment="Percentage of ratings >= 4",
    )
    dissatisfaction_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        nullable=False,
        comment="Percentage of ratings <= 2",
    )
    
    # Top items
    most_liked_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    most_disliked_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    
    # Overall satisfaction level
    satisfaction_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="excellent, very_good, good, satisfactory, needs_improvement, poor",
    )
    
    # Calculation timestamp
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    menu: Mapped["MessMenu"] = relationship(
        "MessMenu",
        back_populates="ratings_summary",
    )
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="menu_ratings_summaries",
    )

    __table_args__ = (
        Index("ix_ratings_summary_satisfaction", "satisfaction_level", "menu_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<RatingsSummary(id={self.id}, menu_id={self.menu_id}, "
            f"avg_rating={self.average_rating}, total={self.total_feedbacks})>"
        )

    @property
    def quality_score(self) -> Decimal:
        """Calculate overall quality score (0-100)."""
        return round(self.average_rating / Decimal("5") * 100, 2)


class QualityMetrics(BaseModel, UUIDMixin, TimestampMixin):
    """
    Menu quality metrics and trends over time.
    
    Provides insights into menu quality with comparative
    analysis and trend tracking.
    """

    __tablename__ = "quality_metrics"

    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Analysis period
    period_start: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    period_end: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
    )
    period_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="weekly, monthly, quarterly, yearly",
    )
    
    # Overall metrics
    overall_average_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        nullable=False,
    )
    total_feedbacks: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_menus_rated: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    # Trends
    rating_trend: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="improving, declining, stable",
    )
    trend_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )
    
    # Comparison with previous period
    previous_period_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    rating_change: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(6, 2),
        nullable=True,
        comment="Percentage change from previous period",
    )
    
    # Best and worst
    best_menu_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    best_menu_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    worst_menu_date: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )
    worst_menu_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    
    # Day of week analysis
    best_day_of_week: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )
    best_day_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    worst_day_of_week: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )
    worst_day_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    
    # Meal type analysis
    best_meal_type: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    best_meal_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    worst_meal_type: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    worst_meal_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2),
        nullable=True,
    )
    
    # Satisfaction metrics
    satisfaction_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        nullable=False,
        comment="Percentage of ratings >= 4",
    )
    dissatisfaction_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        nullable=False,
        comment="Percentage of ratings <= 2",
    )
    
    # Detailed metrics (JSON)
    daily_ratings: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Day-wise rating breakdown",
    )
    meal_type_breakdown: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    aspect_ratings_breakdown: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    
    # Quality score
    quality_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="Overall quality score 0-100",
    )
    consistency_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Rating consistency score",
    )
    
    # Calculation metadata
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="quality_metrics",
    )

    __table_args__ = (
        Index("ix_quality_metrics_period", "hostel_id", "period_start", "period_end"),
    )

    def __repr__(self) -> str:
        return (
            f"<QualityMetrics(id={self.id}, hostel_id={self.hostel_id}, "
            f"period={self.period_start} to {self.period_end}, score={self.quality_score})>"
        )


class SentimentAnalysis(BaseModel, UUIDMixin, TimestampMixin):
    """
    Sentiment analysis of feedback comments.
    
    Analyzes text feedback for sentiment, themes, and insights
    using NLP techniques.
    """

    __tablename__ = "sentiment_analyses"

    menu_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("mess_menus.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    
    # Analysis results
    total_comments: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    analyzed_comments: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    # Sentiment distribution
    positive_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    neutral_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    negative_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    
    # Percentages
    positive_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    neutral_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    negative_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    
    # Overall sentiment
    overall_sentiment: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="very_positive, positive, neutral, negative, very_negative",
    )
    sentiment_score: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        nullable=False,
        comment="Aggregate sentiment score -100 to +100",
    )
    
    # Common themes and keywords
    common_positive_keywords: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )
    common_negative_keywords: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )
    common_topics: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )
    
    # Aspect-based sentiment
    taste_sentiment: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    quantity_sentiment: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    quality_sentiment: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    hygiene_sentiment: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    service_sentiment: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    
    # Emotion detection
    dominant_emotion: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="joy, satisfaction, disappointment, anger, neutral",
    )
    emotion_breakdown: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    
    # Detailed analysis (JSON)
    keyword_frequency: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Word frequency analysis",
    )
    phrase_analysis: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    
    # Analysis metadata
    analysis_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="rule_based, ml_model, hybrid",
    )
    model_version: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    # Relationships
    menu: Mapped["MessMenu"] = relationship(
        "MessMenu",
        back_populates="sentiment_analysis",
    )

    def __repr__(self) -> str:
        return (
            f"<SentimentAnalysis(id={self.id}, menu_id={self.menu_id}, "
            f"sentiment={self.overall_sentiment}, score={self.sentiment_score})>"
        )


class FeedbackAnalysis(BaseModel, UUIDMixin, TimestampMixin):
    """
    Comprehensive feedback analysis with actionable insights.
    
    Provides detailed analysis with recommendations for
    menu improvement.
    """

    __tablename__ = "feedback_analyses"

    hostel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Analysis period
    period_start: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    period_end: Mapped[datetime] = mapped_column(
        Date,
        nullable=False,
    )
    
    # Sentiment summary
    positive_feedback_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )
    negative_feedback_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
    )
    neutral_feedback_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    
    # Common themes
    common_complaints: Mapped[List[str]] = mapped_column(
        ARRAY(String(255)),
        default=list,
        nullable=False,
    )
    common_compliments: Mapped[List[str]] = mapped_column(
        ARRAY(String(255)),
        default=list,
        nullable=False,
    )
    recurring_issues: Mapped[List[str]] = mapped_column(
        ARRAY(String(255)),
        default=list,
        nullable=False,
    )
    
    # Item-level insights
    items_to_keep: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    items_to_improve: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    items_to_remove: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    items_to_introduce: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    
    # Recommendations
    priority_improvements: Mapped[List[str]] = mapped_column(
        ARRAY(String(255)),
        default=list,
        nullable=False,
    )
    quick_wins: Mapped[List[str]] = mapped_column(
        ARRAY(String(255)),
        default=list,
        nullable=False,
    )
    long_term_actions: Mapped[List[str]] = mapped_column(
        ARRAY(String(255)),
        default=list,
        nullable=False,
    )
    
    # Cost-benefit analysis
    high_satisfaction_low_cost_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    low_satisfaction_high_cost_items: Mapped[List[str]] = mapped_column(
        ARRAY(String(100)),
        default=list,
        nullable=False,
    )
    
    # Student preferences
    dietary_preference_trends: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    requested_cuisines: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )
    preferred_cooking_methods: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )
    
    # Timing insights
    peak_feedback_times: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )
    low_engagement_meals: Mapped[List[str]] = mapped_column(
        ARRAY(String(50)),
        default=list,
        nullable=False,
    )
    
    # Detailed analysis (JSON)
    detailed_insights: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    trend_analysis: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    
    # Generation metadata
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    generated_by: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="feedback_analyses",
    )

    __table_args__ = (
        Index("ix_feedback_analysis_period", "hostel_id", "period_start", "period_end"),
    )

    def __repr__(self) -> str:
        return (
            f"<FeedbackAnalysis(id={self.id}, hostel_id={self.hostel_id}, "
            f"period={self.period_start} to {self.period_end})>"
        )


class FeedbackComment(BaseModel, UUIDMixin, TimestampMixin, SoftDeleteModel):
    """
    Comments and discussions on feedback.
    
    Enables threaded discussions and clarifications
    on student feedback.
    """

    __tablename__ = "feedback_comments"

    feedback_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("menu_feedbacks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Comment details
    comment_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    commenter_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    commenter_role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    
    # Threading
    parent_comment_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("feedback_comments.id", ondelete="CASCADE"),
        nullable=True,
    )
    
    # Visibility
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_internal: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    feedback: Mapped["MenuFeedback"] = relationship(
        "MenuFeedback",
        back_populates="comments",
    )
    commenter: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="feedback_comments",
    )
    parent_comment: Mapped[Optional["FeedbackComment"]] = relationship(
        "FeedbackComment",
        remote_side="FeedbackComment.id",
        back_populates="replies",
    )
    replies: Mapped[List["FeedbackComment"]] = relationship(
        "FeedbackComment",
        back_populates="parent_comment",
    )

    def __repr__(self) -> str:
        return f"<FeedbackComment(id={self.id}, feedback_id={self.feedback_id})>"


class FeedbackHelpfulness(BaseModel, UUIDMixin, TimestampMixin):
    """
    Feedback helpfulness voting.
    
    Tracks whether other users found feedback helpful
    for quality ranking.
    """

    __tablename__ = "feedback_helpfulness"

    feedback_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("menu_feedbacks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    voter_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Vote
    is_helpful: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    # Relationships
    feedback: Mapped["MenuFeedback"] = relationship(
        "MenuFeedback",
        back_populates="helpfulness_votes",
    )
    voter: Mapped["User"] = relationship(
        "User",
        back_populates="feedback_helpfulness_votes",
    )

    __table_args__ = (
        UniqueConstraint(
            "feedback_id",
            "voter_id",
            name="uq_feedback_voter",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<FeedbackHelpfulness(id={self.id}, feedback_id={self.feedback_id}, "
            f"helpful={self.is_helpful})>"
        )