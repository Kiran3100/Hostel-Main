# --- File: app/schemas/mess/menu_feedback.py ---
"""
Mess menu feedback and rating schemas.

Provides comprehensive feedback collection, rating analysis,
and quality metrics for menu improvement.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import Field, field_validator, model_validator, computed_field
from uuid import UUID

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema
from app.schemas.common.enums import MealType
from app.schemas.common.filters import DateRangeFilter

__all__ = [
    "FeedbackRequest",
    "FeedbackResponse",
    "RatingsSummary",
    "QualityMetrics",
    "ItemRating",
    "FeedbackAnalysis",
    "SentimentAnalysis",
]


class FeedbackRequest(BaseCreateSchema):
    """
    Submit menu feedback and ratings.
    
    Allows students to rate menu quality and provide detailed feedback
    with multi-dimensional ratings.
    """

    menu_id: UUID = Field(
        ...,
        description="Menu unique identifier",
    )
    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    meal_type: MealType = Field(
        ...,
        description="Which meal is being rated",
    )
    
    # Overall rating
    rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Overall rating (1-5 stars)",
    )
    
    # Detailed feedback
    comments: Optional[str] = Field(
        None,
        max_length=1000,
        description="Detailed comments and feedback",
    )
    
    # Aspect-specific ratings
    taste_rating: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Taste rating (1-5)",
    )
    quantity_rating: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Portion size rating (1-5)",
    )
    quality_rating: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Food quality rating (1-5)",
    )
    hygiene_rating: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Hygiene and cleanliness rating (1-5)",
    )
    presentation_rating: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Food presentation rating (1-5)",
    )
    service_rating: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="Service quality rating (1-5)",
    )
    
    # Item-specific feedback
    liked_items: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Items student liked",
    )
    disliked_items: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Items student disliked",
    )
    
    # Suggestions
    improvement_suggestions: Optional[str] = Field(
        None,
        max_length=500,
        description="Suggestions for improvement",
    )
    
    # Would recommend
    would_recommend: Optional[bool] = Field(
        None,
        description="Would recommend this menu to others",
    )

    @field_validator("comments", "improvement_suggestions", mode="before")
    @classmethod
    def validate_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize text fields."""
        if v is not None:
            v = v.strip()
            
            # Check for meaningful content
            if len(v) > 0 and len(set(v.lower().replace(" ", ""))) < 3:
                raise ValueError("Please provide meaningful feedback")
            
            return v if v else None
        return None

    @field_validator("liked_items", "disliked_items", mode="after")
    @classmethod
    def validate_item_lists(cls, v: List[str]) -> List[str]:
        """Validate and normalize item lists."""
        if not v:
            return v
        
        # Normalize and deduplicate
        normalized = []
        seen = set()
        
        for item in v:
            item = item.strip()
            if item and len(item) >= 2:
                item_lower = item.lower()
                if item_lower not in seen:
                    seen.add(item_lower)
                    normalized.append(item)
        
        return normalized

    @model_validator(mode="after")
    def validate_feedback_completeness(self) -> "FeedbackRequest":
        """
        Validate feedback has sufficient information.
        
        Low ratings should have comments explaining the issue.
        """
        # If overall rating is low, encourage detailed feedback
        if self.rating <= 2:
            if not self.comments and not self.improvement_suggestions:
                raise ValueError(
                    "Please provide comments or suggestions for low ratings"
                )
        
        return self


class FeedbackResponse(BaseResponseSchema):
    """
    Feedback submission response.
    
    Provides confirmation of feedback submission with context.
    """

    menu_id: UUID = Field(
        ...,
        description="Menu unique identifier",
    )
    menu_date: Date = Field(
        ...,
        description="Menu Date",
    )
    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    student_name: str = Field(
        ...,
        description="Student full name",
    )
    meal_type: MealType = Field(
        ...,
        description="Meal type rated",
    )
    rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Overall rating",
    )
    comments: Optional[str] = Field(
        None,
        description="Feedback comments",
    )
    submitted_at: datetime = Field(
        ...,
        description="Submission timestamp",
    )
    is_verified: bool = Field(
        default=False,
        description="Whether feedback is verified",
    )
    helpful_count: int = Field(
        default=0,
        ge=0,
        description="Number of users who found this helpful",
    )

    @computed_field
    @property
    def rating_display(self) -> str:
        """Get star rating display."""
        return "★" * self.rating + "☆" * (5 - self.rating)


class ItemRating(BaseSchema):
    """
    Rating for specific menu item.
    
    Aggregates ratings for individual food items.
    """

    item_name: str = Field(
        ...,
        description="Menu item name",
    )
    item_category: Optional[str] = Field(
        None,
        description="Item category",
    )
    average_rating: Decimal = Field(
        ...,
        ge=0,
        le=5,
        description="Average rating for this item",
    )
    feedback_count: int = Field(
        ...,
        ge=0,
        description="Number of feedbacks received",
    )
    liked_count: int = Field(
        default=0,
        ge=0,
        description="Times marked as liked",
    )
    disliked_count: int = Field(
        default=0,
        ge=0,
        description="Times marked as disliked",
    )
    popularity_score: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=100,
        description="Popularity score (0-100)",
    )
    last_served: Optional[Date] = Field(
        None,
        description="Last Date item was served",
    )

    @field_validator("average_rating", "popularity_score", mode="after")
    @classmethod
    def round_decimals(cls, v: Decimal) -> Decimal:
        """Round decimal values to 2 decimal places."""
        return v.quantize(Decimal("0.01"))

    @computed_field
    @property
    def sentiment(self) -> str:
        """Calculate overall sentiment for item."""
        if self.feedback_count == 0:
            return "neutral"
        
        rating = float(self.average_rating)
        
        if rating >= 4.0:
            return "positive"
        elif rating >= 3.0:
            return "neutral"
        else:
            return "negative"

    @computed_field
    @property
    def like_ratio(self) -> Decimal:
        """Calculate like to dislike ratio."""
        total = self.liked_count + self.disliked_count
        
        if total == 0:
            return Decimal("0.00")
        
        return round(
            Decimal(self.liked_count) / Decimal(total) * 100,
            2,
        )


class RatingsSummary(BaseSchema):
    """
    Comprehensive ratings summary for menu.
    
    Provides aggregated statistics and distribution of ratings.
    """

    menu_id: UUID = Field(
        ...,
        description="Menu unique identifier",
    )
    menu_date: Date = Field(
        ...,
        description="Menu Date",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    
    # Overall statistics
    total_feedbacks: int = Field(
        ...,
        ge=0,
        description="Total feedback count",
    )
    average_rating: Decimal = Field(
        ...,
        ge=0,
        le=5,
        description="Overall average rating",
    )
    median_rating: Optional[Decimal] = Field(
        None,
        ge=0,
        le=5,
        description="Median rating",
    )
    
    # Meal-specific ratings
    breakfast_rating: Optional[Decimal] = Field(
        None,
        ge=0,
        le=5,
        description="Breakfast average rating",
    )
    breakfast_feedback_count: int = Field(
        default=0,
        ge=0,
        description="Breakfast feedback count",
    )
    
    lunch_rating: Optional[Decimal] = Field(
        None,
        ge=0,
        le=5,
        description="Lunch average rating",
    )
    lunch_feedback_count: int = Field(
        default=0,
        ge=0,
        description="Lunch feedback count",
    )
    
    snacks_rating: Optional[Decimal] = Field(
        None,
        ge=0,
        le=5,
        description="Snacks average rating",
    )
    snacks_feedback_count: int = Field(
        default=0,
        ge=0,
        description="Snacks feedback count",
    )
    
    dinner_rating: Optional[Decimal] = Field(
        None,
        ge=0,
        le=5,
        description="Dinner average rating",
    )
    dinner_feedback_count: int = Field(
        default=0,
        ge=0,
        description="Dinner feedback count",
    )
    
    # Rating distribution
    rating_5_count: int = Field(
        ...,
        ge=0,
        description="5-star ratings count",
    )
    rating_4_count: int = Field(
        ...,
        ge=0,
        description="4-star ratings count",
    )
    rating_3_count: int = Field(
        ...,
        ge=0,
        description="3-star ratings count",
    )
    rating_2_count: int = Field(
        ...,
        ge=0,
        description="2-star ratings count",
    )
    rating_1_count: int = Field(
        ...,
        ge=0,
        description="1-star ratings count",
    )
    
    # Aspect ratings
    average_taste_rating: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=5,
        description="Average taste rating",
    )
    average_quantity_rating: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=5,
        description="Average quantity rating",
    )
    average_quality_rating: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=5,
        description="Average quality rating",
    )
    average_hygiene_rating: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=5,
        description="Average hygiene rating",
    )
    average_presentation_rating: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=5,
        description="Average presentation rating",
    )
    average_service_rating: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=5,
        description="Average service rating",
    )
    
    # Recommendation
    would_recommend_percentage: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=100,
        description="Percentage who would recommend",
    )

    @field_validator(
        "average_rating", "median_rating", "breakfast_rating", "lunch_rating",
        "snacks_rating", "dinner_rating", "average_taste_rating",
        "average_quantity_rating", "average_quality_rating",
        "average_hygiene_rating", "average_presentation_rating",
        "average_service_rating", "would_recommend_percentage",
        mode="after"
    )
    @classmethod
    def round_decimals(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Round decimal values to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v

    @computed_field
    @property
    def participation_rate(self) -> Decimal:
        """Calculate feedback participation rate (if total students known)."""
        # This would need total students count from context
        # Placeholder for illustration
        return Decimal("0.00")

    @computed_field
    @property
    def satisfaction_level(self) -> str:
        """Determine overall satisfaction level."""
        rating = float(self.average_rating)
        
        if rating >= 4.5:
            return "excellent"
        elif rating >= 4.0:
            return "very_good"
        elif rating >= 3.5:
            return "good"
        elif rating >= 3.0:
            return "satisfactory"
        elif rating >= 2.0:
            return "needs_improvement"
        else:
            return "poor"


class SentimentAnalysis(BaseSchema):
    """
    Sentiment analysis of feedback comments.
    
    Analyzes text feedback for sentiment and themes.
    """

    menu_id: UUID = Field(
        ...,
        description="Menu unique identifier",
    )
    total_comments: int = Field(
        ...,
        ge=0,
        description="Total comments analyzed",
    )
    
    # Sentiment distribution
    positive_count: int = Field(
        ...,
        ge=0,
        description="Positive sentiment count",
    )
    neutral_count: int = Field(
        ...,
        ge=0,
        description="Neutral sentiment count",
    )
    negative_count: int = Field(
        ...,
        ge=0,
        description="Negative sentiment count",
    )
    
    # Percentages
    positive_percentage: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Positive sentiment percentage",
    )
    negative_percentage: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Negative sentiment percentage",
    )
    
    # Common themes
    common_positive_keywords: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Most frequent positive keywords",
    )
    common_negative_keywords: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Most frequent negative keywords",
    )

    @field_validator("positive_percentage", "negative_percentage", mode="after")
    @classmethod
    def round_percentages(cls, v: Decimal) -> Decimal:
        """Round percentage values to 2 decimal places."""
        return v.quantize(Decimal("0.01"))


class QualityMetrics(BaseSchema):
    """
    Menu quality metrics and trends.
    
    Provides insights into menu quality over time with
    comparative analysis.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    period_start: Date = Field(
        ...,
        description="Analysis period start",
    )
    period_end: Date = Field(
        ...,
        description="Analysis period end",
    )
    
    # Overall metrics
    overall_average_rating: Decimal = Field(
        ...,
        ge=0,
        le=5,
        description="Overall average rating for period",
    )
    total_feedbacks: int = Field(
        ...,
        ge=0,
        description="Total feedback count",
    )
    total_menus_rated: int = Field(
        ...,
        ge=0,
        description="Number of menus that received ratings",
    )
    
    # Trends
    rating_trend: str = Field(
        ...,
        pattern=r"^(improving|declining|stable)$",
        description="Rating trend direction",
    )
    trend_percentage: Optional[Decimal] = Field(
        None,
        description="Trend change percentage",
    )
    
    # Best and worst performers
    best_rated_items: List[ItemRating] = Field(
        default_factory=list,
        max_length=10,
        description="Top rated items",
    )
    worst_rated_items: List[ItemRating] = Field(
        default_factory=list,
        max_length=10,
        description="Lowest rated items",
    )
    most_popular_items: List[ItemRating] = Field(
        default_factory=list,
        max_length=10,
        description="Most popular items by feedback count",
    )
    
    # Day of week analysis
    ratings_by_day: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Average rating by day of week",
    )
    best_day: Optional[str] = Field(
        None,
        description="Day with highest average rating",
    )
    worst_day: Optional[str] = Field(
        None,
        description="Day with lowest average rating",
    )
    
    # Meal analysis
    best_meal_type: Optional[str] = Field(
        None,
        description="Meal type with highest rating",
    )
    worst_meal_type: Optional[str] = Field(
        None,
        description="Meal type with lowest rating",
    )
    
    # Satisfaction metrics
    satisfaction_rate: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=100,
        description="Percentage of ratings >= 4 stars",
    )
    dissatisfaction_rate: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=100,
        description="Percentage of ratings <= 2 stars",
    )

    @field_validator(
        "overall_average_rating", "trend_percentage",
        "satisfaction_rate", "dissatisfaction_rate",
        mode="after"
    )
    @classmethod
    def round_decimals(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Round decimal values to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v

    @computed_field
    @property
    def quality_score(self) -> Decimal:
        """
        Calculate overall quality score (0-100).
        
        Composite metric based on ratings and satisfaction.
        """
        # Simple formula: (avg_rating / 5) * 100
        return round(
            self.overall_average_rating / Decimal("5") * 100,
            2,
        )


class FeedbackAnalysis(BaseSchema):
    """
    Comprehensive feedback analysis with actionable insights.
    
    Provides detailed analysis of feedback data with recommendations
    for menu improvement.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    analysis_period: DateRangeFilter = Field(
        ...,
        description="Analysis time period",
    )
    generated_at: datetime = Field(
        ...,
        description="Analysis generation timestamp",
    )
    
    # Sentiment analysis
    positive_feedback_percentage: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Positive feedback percentage",
    )
    negative_feedback_percentage: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Negative feedback percentage",
    )
    neutral_feedback_percentage: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=100,
        description="Neutral feedback percentage",
    )
    
    # Common themes
    common_complaints: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Most common complaints/issues",
    )
    common_compliments: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Most common positive feedback",
    )
    recurring_issues: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Issues appearing repeatedly",
    )
    
    # Item-level insights
    items_to_keep: List[str] = Field(
        default_factory=list,
        max_length=30,
        description="High-rated items to continue serving",
    )
    items_to_improve: List[str] = Field(
        default_factory=list,
        max_length=30,
        description="Items needing quality improvement",
    )
    items_to_remove: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Consistently low-rated items to remove",
    )
    items_to_introduce: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Suggested new items based on requests",
    )
    
    # Improvement recommendations
    priority_improvements: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="High-priority improvement areas",
    )
    quick_wins: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Easy improvements with high impact",
    )
    
    # Cost-benefit analysis
    high_satisfaction_low_cost_items: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Items with good rating and low cost",
    )
    
    # Student preferences
    dietary_preference_trends: Dict[str, int] = Field(
        default_factory=dict,
        description="Emerging dietary preference trends",
    )
    requested_cuisines: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Cuisines students are requesting",
    )
    
    # Timing insights
    peak_feedback_times: List[str] = Field(
        default_factory=list,
        description="Times when most feedback is received",
    )
    low_engagement_meals: List[str] = Field(
        default_factory=list,
        description="Meals with low feedback participation",
    )

    @field_validator(
        "positive_feedback_percentage", "negative_feedback_percentage",
        "neutral_feedback_percentage",
        mode="after"
    )
    @classmethod
    def round_percentages(cls, v: Decimal) -> Decimal:
        """Round percentage values to 2 decimal places."""
        return v.quantize(Decimal("0.01"))