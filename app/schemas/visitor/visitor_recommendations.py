# --- File: app/schemas/visitor/visitor_recommendations.py ---
"""
Visitor recommendation schemas.

This module defines schemas for personalized hostel recommendations,
feedback collection, and recommendation explanations.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Dict, List, Union
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common.base import BaseSchema

__all__ = [
    "RecommendationFeedback",
    "RecommendationExplanation",
    "RecommendationReason",
]


class RecommendationFeedback(BaseSchema):
    """
    Feedback on a hostel recommendation to improve future suggestions.
    """

    action: str = Field(
        ...,
        description="Action taken by user",
        pattern="^(clicked|viewed|favorited|booked|dismissed|not_relevant|helpful|not_helpful)$",
    )
    relevant: Union[bool, None] = Field(
        default=None,
        description="Whether the recommendation was relevant to user preferences",
    )
    reason: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Optional explanation of feedback",
    )
    rating: Union[Annotated[int, Field(ge=1, le=5)], None] = Field(
        default=None,
        description="Rating of the recommendation quality (1-5)",
    )

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate and clean reason text."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
            if len(v) > 500:
                raise ValueError("Reason must not exceed 500 characters")
        return v


class RecommendationReason(BaseSchema):
    """
    Individual reason for why a hostel was recommended.
    """

    type: str = Field(
        ...,
        description="Type of recommendation reason",
        pattern="^(preference_match|similar_to_favorites|popular_with_similar_users|location_based|price_match|trending|seasonal)$",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Short title for the reason",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Detailed explanation",
    )
    confidence_score: Annotated[Decimal, Field(ge=0, le=1, decimal_places=3)] = Field(
        ...,
        description="Confidence score for this reason (0.0-1.0)",
    )
    weight: Annotated[Decimal, Field(ge=0, le=1, decimal_places=3)] = Field(
        ...,
        description="Weight of this reason in overall recommendation (0.0-1.0)",
    )


class RecommendationExplanation(BaseSchema):
    """
    Detailed explanation of why a hostel was recommended.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )
    overall_score: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] = Field(
        ...,
        description="Overall recommendation score (0-100)",
    )
    reasons: List[RecommendationReason] = Field(
        ...,
        min_length=1,
        description="List of reasons for recommendation",
    )
    
    # Preference matching details
    preference_matches: Dict[str, Union[str, bool, List[str]]] = Field(
        default_factory=dict,
        description="How hostel matches user preferences",
    )
    
    # Similarity details
    similar_to_favorites: List[str] = Field(
        default_factory=list,
        description="Names of favorite hostels this one is similar to",
    )
    
    # Social proof
    popular_with_similar_users: bool = Field(
        default=False,
        description="Whether this hostel is popular with users having similar preferences",
    )
    
    # Additional context
    explanation_generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this explanation was generated",
    )

    @field_validator("reasons")
    @classmethod
    def validate_reasons(cls, v: List[RecommendationReason]) -> List[RecommendationReason]:
        """Validate reasons list is not empty."""
        if not v or len(v) == 0:
            raise ValueError("At least one reason must be provided")
        
        # Validate total weight doesn't exceed 1.0
        total_weight = sum(reason.weight for reason in v)
        if total_weight > 1.0:
            raise ValueError("Total weight of reasons cannot exceed 1.0")
        
        return v