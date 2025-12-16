# --- File: app/schemas/review/review_response_schema.py ---
"""
Hostel response to review schemas.

Handles hostel management responses to customer reviews.

Pydantic v2 Migration Notes:
- Uses Annotated pattern for Decimal fields with precision constraints
- @computed_field with @property decorator for computed properties
- field_validator already uses v2 syntax
- Percentage fields use max_digits=5, decimal_places=2 for 0.00-100.00 range
- Time fields use appropriate precision for hour calculations
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, List, Union
from uuid import UUID

from pydantic import Field, field_validator, computed_field

from app.schemas.common.base import (
    BaseSchema,
    BaseCreateSchema,
    BaseUpdateSchema,
    BaseResponseSchema,
)

__all__ = [
    "HostelResponseCreate",
    "HostelResponseUpdate",
    "OwnerResponse",
    "ResponseGuidelines",
    "ResponseStats",
    "ResponseTemplate",
]


class HostelResponseCreate(BaseCreateSchema):
    """
    Create hostel response to a review.
    
    Allows hostel management to respond to customer feedback.
    """
    
    review_id: UUID = Field(
        ...,
        description="Review being responded to",
    )
    
    response_text: str = Field(
        ...,
        min_length=20,
        max_length=2000,
        description="Response text from hostel management",
        examples=[
            "Thank you for your feedback. We appreciate your kind words "
            "about our staff and facilities. We are always striving to "
            "improve and provide the best experience for our residents."
        ],
    )
    
    responded_by: UUID = Field(
        ...,
        description="Admin/owner user ID who is responding",
    )
    
    # Optional template reference
    template_id: Union[UUID, None] = Field(
        default=None,
        description="Response template used (if any)",
    )
    
    @field_validator("response_text")
    @classmethod
    def validate_response_text(cls, v: str) -> str:
        """Validate and clean response text."""
        v = v.strip()
        if not v:
            raise ValueError("Response text cannot be empty")
        
        # Minimum word count (approximately 5 words)
        word_count = len(v.split())
        if word_count < 5:
            raise ValueError(
                "Response should be more detailed (minimum 5 words)"
            )
        
        # Check for placeholder text
        placeholder_phrases = [
            "lorem ipsum",
            "test response",
            "[insert",
            "placeholder",
        ]
        lower_text = v.lower()
        for phrase in placeholder_phrases:
            if phrase in lower_text:
                raise ValueError(
                    f"Response appears to contain placeholder text: '{phrase}'"
                )
        
        return v


class HostelResponseUpdate(BaseUpdateSchema):
    """
    Update existing hostel response.
    
    Allows editing of response with edit history tracking.
    """
    
    response_id: UUID = Field(..., description="Response to update")
    
    response_text: str = Field(
        ...,
        min_length=20,
        max_length=2000,
        description="Updated response text",
    )
    
    edit_reason: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Reason for editing the response",
    )
    
    @field_validator("response_text")
    @classmethod
    def validate_response_text(cls, v: str) -> str:
        """Validate and clean response text."""
        v = v.strip()
        if not v:
            raise ValueError("Response text cannot be empty")
        
        word_count = len(v.split())
        if word_count < 5:
            raise ValueError(
                "Response should be more detailed (minimum 5 words)"
            )
        
        return v


class OwnerResponse(BaseResponseSchema):
    """
    Owner/hostel response to review.
    
    Complete response information for display.
    """
    
    review_id: UUID = Field(..., description="Associated review ID")
    
    response_text: str = Field(..., description="Response text")
    
    # Responder info
    responded_by: UUID = Field(..., description="Responder user ID")
    responded_by_name: str = Field(..., description="Responder name")
    responded_by_role: str = Field(
        ...,
        description="Responder role in hostel",
        examples=["hostel_admin", "owner", "manager"],
    )
    responded_by_image: Union[str, None] = Field(
        default=None,
        description="Responder profile image URL",
    )
    
    responded_at: datetime = Field(..., description="Response timestamp")
    
    # Edit tracking
    is_edited: bool = Field(default=False, description="Whether edited")
    edited_at: Union[datetime, None] = Field(default=None, description="Last edit time")
    edit_count: int = Field(default=0, ge=0, description="Number of edits")
    
    @computed_field  # type: ignore[misc]
    @property
    def response_age_days(self) -> int:
        """Days since response was posted."""
        delta = datetime.utcnow() - self.responded_at
        return delta.days


class ResponseGuidelines(BaseSchema):
    """
    Guidelines for hostel responses to reviews.
    
    Helps hostel staff craft professional and effective responses.
    """
    
    guidelines: List[str] = Field(
        default_factory=lambda: [
            "Thank the reviewer for their feedback",
            "Address specific concerns mentioned in the review",
            "Be professional and courteous at all times",
            "Explain any misunderstandings clearly and factually",
            "Mention improvements made based on feedback",
            "Invite them to connect directly for unresolved issues",
            "Keep the response focused and relevant",
            "Avoid making excuses or being defensive",
        ],
        description="Response guidelines for hostel staff",
    )
    
    best_practices: List[str] = Field(
        default_factory=lambda: [
            "Respond within 24-48 hours of review posting",
            "Personalize your response with reviewer's name if appropriate",
            "Acknowledge both positive and negative points raised",
            "Never be defensive or argumentative",
            "Keep responses concise (100-300 words ideal)",
            "Use professional and friendly tone",
            "Proofread before publishing",
            "Follow up on promised actions",
        ],
        description="Best practices for responding to reviews",
    )
    
    response_templates_available: bool = Field(
        default=True,
        description="Whether pre-approved templates are available",
    )
    
    # Character limits
    min_length: int = Field(default=20, description="Minimum response length")
    max_length: int = Field(default=2000, description="Maximum response length")
    recommended_length: int = Field(
        default=200,
        description="Recommended response length",
    )


class ResponseStats(BaseSchema):
    """
    Hostel response statistics.
    
    Tracks response rate and performance metrics.
    """
    
    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    
    # Volume metrics
    total_reviews: int = Field(..., ge=0, description="Total reviews received")
    total_responses: int = Field(..., ge=0, description="Total responses given")
    
    # Rate metrics with proper percentage constraints
    response_rate: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Percentage of reviews with responses",
        ),
    ]
    
    # Timing metrics with proper time constraints
    average_response_time_hours: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            max_digits=8,
            decimal_places=2,
            description="Average time to respond in hours",
        ),
    ]
    median_response_time_hours: Union[
        Annotated[
            Decimal,
            Field(
                ge=Decimal("0"),
                max_digits=8,
                decimal_places=2,
                description="Median time to respond",
            ),
        ],
        None,
    ] = None
    
    # Response by rating with percentage constraints
    response_rate_5_star: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Response rate for 5-star reviews",
        ),
    ]
    response_rate_4_star: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Response rate for 4-star reviews",
        ),
    ]
    response_rate_3_star: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Response rate for 3-star reviews",
        ),
    ]
    response_rate_2_star: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Response rate for 2-star reviews",
        ),
    ]
    response_rate_1_star: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Response rate for 1-star reviews",
        ),
    ]
    
    # Response quality
    average_response_length: int = Field(
        ...,
        ge=0,
        description="Average response length in characters",
    )
    
    # Pending responses
    pending_responses: int = Field(
        ...,
        ge=0,
        description="Reviews awaiting response",
    )
    oldest_unanswered_days: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Age of oldest unanswered review in days",
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def negative_review_response_rate(self) -> Decimal:
        """Response rate for negative reviews (1-2 stars)."""
        # Calculate weighted average if counts are known
        # For now, return average of 1 and 2 star rates
        rate_1 = float(self.response_rate_1_star)
        rate_2 = float(self.response_rate_2_star)
        return Decimal(str(round((rate_1 + rate_2) / 2, 2)))
    
    @computed_field  # type: ignore[misc]
    @property
    def response_health(self) -> str:
        """
        Evaluate response health.
        
        Returns: excellent, good, needs_improvement, or poor
        """
        rate = float(self.response_rate)
        time_hours = float(self.average_response_time_hours)
        
        if rate >= 90 and time_hours <= 24:
            return "excellent"
        elif rate >= 70 and time_hours <= 48:
            return "good"
        elif rate >= 50:
            return "needs_improvement"
        else:
            return "poor"


class ResponseTemplate(BaseSchema):
    """
    Pre-approved response template.
    
    Helps staff respond quickly while maintaining quality.
    """
    
    template_id: UUID = Field(..., description="Template ID")
    name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Template name",
        examples=["Positive Review Thank You", "Negative Review Apology"],
    )
    
    category: str = Field(
        ...,
        pattern=r"^(positive|negative|neutral|specific_issue)$",
        description="Template category based on review type",
    )
    
    template_text: str = Field(
        ...,
        min_length=50,
        max_length=2000,
        description="Template text with placeholders",
        examples=[
            "Dear {reviewer_name}, thank you for your {rating}-star review! "
            "We're delighted to hear about your positive experience at "
            "{hostel_name}. {custom_message} We look forward to hosting you "
            "again. Best regards, {responder_name}"
        ],
    )
    
    # Placeholders
    available_placeholders: List[str] = Field(
        default_factory=lambda: [
            "{reviewer_name}",
            "{hostel_name}",
            "{rating}",
            "{responder_name}",
            "{custom_message}",
        ],
        description="Available placeholders in template",
    )
    
    # Usage stats
    usage_count: int = Field(
        default=0,
        ge=0,
        description="Times this template has been used",
    )
    
    is_active: bool = Field(default=True, description="Whether template is active")
    
    @field_validator("category")
    @classmethod
    def normalize_category(cls, v: str) -> str:
        """Normalize category to lowercase."""
        return v.lower().strip()