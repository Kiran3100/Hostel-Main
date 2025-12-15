"""
Complaint feedback and satisfaction schemas.

Handles student feedback collection, ratings, and
feedback analytics for service improvement.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Annotated, Dict, List, Optional

from pydantic import ConfigDict, Field, field_validator

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema

__all__ = [
    "FeedbackRequest",
    "FeedbackResponse",
    "FeedbackSummary",
    "FeedbackAnalysis",
    "RatingTrendPoint",
]


class FeedbackRequest(BaseCreateSchema):
    """
    Submit feedback on resolved complaint.
    
    Collects rating, detailed feedback, and satisfaction metrics.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(
        ...,
        description="Complaint identifier to provide feedback for",
    )

    rating: int = Field(
        ...,
        ge=1,
        le=5,
        description="Overall rating (1-5 stars)",
    )

    feedback: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Detailed feedback comments",
    )

    # Satisfaction questions
    issue_resolved_satisfactorily: bool = Field(
        ...,
        description="Was the issue resolved to your satisfaction?",
    )
    response_time_satisfactory: bool = Field(
        ...,
        description="Was the response time acceptable?",
    )
    staff_helpful: bool = Field(
        ...,
        description="Was the staff helpful and professional?",
    )

    would_recommend: Optional[bool] = Field(
        default=None,
        description="Would you recommend this complaint system?",
    )

    @field_validator("feedback")
    @classmethod
    def validate_feedback(cls, v: Optional[str]) -> Optional[str]:
        """Normalize feedback text if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    @field_validator("rating")
    @classmethod
    def validate_rating_for_poor_scores(cls, v: int) -> int:
        """
        Encourage feedback text for low ratings.
        
        Note: This is advisory validation, not enforced.
        """
        # Could log warning if rating <= 2 and no feedback
        # but not enforcing to avoid friction
        return v


class FeedbackResponse(BaseResponseSchema):
    """
    Feedback submission response.
    
    Confirms feedback receipt and provides summary.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(..., description="Complaint ID")
    complaint_number: str = Field(..., description="Complaint reference number")

    rating: int = Field(..., description="Submitted rating")
    feedback: Optional[str] = Field(default=None, description="Submitted feedback")

    submitted_by: str = Field(..., description="Feedback submitter user ID")
    submitted_at: datetime = Field(..., description="Submission timestamp")

    message: str = Field(
        ...,
        description="Confirmation message",
        examples=["Thank you for your feedback!"],
    )


class FeedbackSummary(BaseSchema):
    """
    Feedback summary for hostel or supervisor.
    
    Provides aggregate feedback metrics and insights.
    """
    model_config = ConfigDict(from_attributes=True)

    entity_id: str = Field(
        ...,
        description="Entity identifier (hostel or supervisor)",
    )
    entity_type: str = Field(
        ...,
        pattern=r"^(hostel|supervisor)$",
        description="Entity type: hostel or supervisor",
    )

    # Time period
    period_start: Date = Field(..., description="Summary period start Date")
    period_end: Date = Field(..., description="Summary period end Date")

    # Overall statistics
    total_feedbacks: int = Field(..., ge=0, description="Total feedback count")
    average_rating: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("5"),
            description="Average rating (0-5)"
        )
    ]

    # Rating distribution
    rating_5_count: int = Field(..., ge=0, description="5-star rating count")
    rating_4_count: int = Field(..., ge=0, description="4-star rating count")
    rating_3_count: int = Field(..., ge=0, description="3-star rating count")
    rating_2_count: int = Field(..., ge=0, description="2-star rating count")
    rating_1_count: int = Field(..., ge=0, description="1-star rating count")

    # Satisfaction metrics (percentages)
    resolution_satisfaction_rate: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            description="% satisfied with issue resolution"
        )
    ]
    response_time_satisfaction_rate: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            description="% satisfied with response time"
        )
    ]
    staff_helpfulness_rate: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            description="% who found staff helpful"
        )
    ]

    # Recommendation
    recommendation_rate: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            description="% who would recommend the system"
        )
    ]

    # Sentiment analysis
    positive_feedback_count: int = Field(
        ...,
        ge=0,
        description="Positive feedback count",
    )
    negative_feedback_count: int = Field(
        ...,
        ge=0,
        description="Negative feedback count",
    )
    common_themes: List[str] = Field(
        default_factory=list,
        description="Common themes from feedback analysis",
    )


class RatingTrendPoint(BaseSchema):
    """
    Data point for rating trend analysis.
    
    Represents rating metrics for a specific time period.
    """
    model_config = ConfigDict(from_attributes=True)

    period: str = Field(
        ...,
        description="Time period (Date, week, or month)",
        examples=["2024-01", "Week 1", "2024-01-15"],
    )
    average_rating: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("5"),
            description="Average rating for period"
        )
    ]
    feedback_count: int = Field(
        ...,
        ge=0,
        description="Number of feedbacks in period",
    )


class FeedbackAnalysis(BaseSchema):
    """
    Detailed feedback analysis with trends.
    
    Provides deep insights into feedback patterns.
    """
    model_config = ConfigDict(from_attributes=True)

    hostel_id: str = Field(..., description="Hostel identifier")
    period_start: Date = Field(..., description="Analysis period start")
    period_end: Date = Field(..., description="Analysis period end")

    # Trend data
    rating_trend: List[RatingTrendPoint] = Field(
        default_factory=list,
        description="Rating trend over time",
    )

    # Category analysis
    feedback_by_category: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Average rating by complaint category",
    )

    # Priority analysis
    feedback_by_priority: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Average rating by priority level",
    )

    # Response time impact
    avg_rating_quick_response: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("5"),
            description="Average rating for quick responses"
        )
    ]
    avg_rating_slow_response: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("5"),
            description="Average rating for slow responses"
        )
    ]