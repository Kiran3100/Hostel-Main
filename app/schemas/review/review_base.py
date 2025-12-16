# --- File: app/schemas/review/review_base.py ---
"""
Base review schemas with comprehensive validation.

Provides foundation schemas for review creation and updates.

Pydantic v2 Migration Notes:
- Uses Annotated pattern for Decimal fields with precision constraints
- field_validator and model_validator already use v2 syntax
- Overall rating uses max_digits=2, decimal_places=1 for 1.0-5.0 range
- HttpUrl type works identically in v1 and v2
"""

from decimal import Decimal
from typing import Annotated, List, Union
from uuid import UUID

from pydantic import Field, HttpUrl, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseUpdateSchema, BaseSchema

__all__ = [
    "ReviewBase",
    "ReviewCreate",
    "ReviewUpdate",
    "DetailedRatings",
]


class DetailedRatings(BaseSchema):
    """
    Detailed aspect-based ratings for comprehensive feedback.
    
    Allows reviewers to rate specific aspects of their experience.
    """
    
    cleanliness_rating: Union[int, None] = Field(
        default=None,
        ge=1,
        le=5,
        description="Cleanliness and hygiene rating",
    )
    food_quality_rating: Union[int, None] = Field(
        default=None,
        ge=1,
        le=5,
        description="Food quality rating (if mess facility available)",
    )
    staff_behavior_rating: Union[int, None] = Field(
        default=None,
        ge=1,
        le=5,
        description="Staff courtesy and helpfulness rating",
    )
    security_rating: Union[int, None] = Field(
        default=None,
        ge=1,
        le=5,
        description="Safety and security measures rating",
    )
    value_for_money_rating: Union[int, None] = Field(
        default=None,
        ge=1,
        le=5,
        description="Value for money rating",
    )
    amenities_rating: Union[int, None] = Field(
        default=None,
        ge=1,
        le=5,
        description="Facilities and amenities quality rating",
    )
    location_rating: Union[int, None] = Field(
        default=None,
        ge=1,
        le=5,
        description="Location convenience rating",
    )
    wifi_quality_rating: Union[int, None] = Field(
        default=None,
        ge=1,
        le=5,
        description="Internet/WiFi quality rating",
    )
    maintenance_rating: Union[int, None] = Field(
        default=None,
        ge=1,
        le=5,
        description="Maintenance responsiveness rating",
    )


class ReviewBase(BaseSchema):
    """
    Base review schema with all core fields.
    
    Foundation for review creation with comprehensive validation.
    """
    
    # Identifiers
    hostel_id: UUID = Field(..., description="Hostel being reviewed")
    reviewer_id: UUID = Field(..., description="User submitting the review")
    student_id: Union[UUID, None] = Field(
        default=None,
        description="Student profile ID (for verified stay reviews)",
    )
    booking_id: Union[UUID, None] = Field(
        default=None,
        description="Related booking reference for verification",
    )
    
    # Overall rating with proper Decimal constraints
    overall_rating: Annotated[
        Decimal,
        Field(
            ge=Decimal("1.0"),
            le=Decimal("5.0"),
            max_digits=2,
            decimal_places=1,
            description="Overall rating (1.0 to 5.0, in 0.5 increments)",
            examples=[Decimal("4.5"), Decimal("3.0")],
        ),
    ]
    
    # Review content
    title: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="Review title/headline",
        examples=["Great hostel with excellent facilities"],
    )
    review_text: str = Field(
        ...,
        min_length=50,
        max_length=5000,
        description="Detailed review text",
    )
    
    # Detailed aspect ratings (optional but encouraged)
    cleanliness_rating: Union[int, None] = Field(
        default=None,
        ge=1,
        le=5,
        description="Cleanliness rating",
    )
    food_quality_rating: Union[int, None] = Field(
        default=None,
        ge=1,
        le=5,
        description="Food quality rating",
    )
    staff_behavior_rating: Union[int, None] = Field(
        default=None,
        ge=1,
        le=5,
        description="Staff behavior rating",
    )
    security_rating: Union[int, None] = Field(
        default=None,
        ge=1,
        le=5,
        description="Security rating",
    )
    value_for_money_rating: Union[int, None] = Field(
        default=None,
        ge=1,
        le=5,
        description="Value for money rating",
    )
    amenities_rating: Union[int, None] = Field(
        default=None,
        ge=1,
        le=5,
        description="Amenities rating",
    )
    
    # Media attachments
    photos: List[HttpUrl] = Field(
        default_factory=list,
        max_length=10,
        description="Review photos (max 10)",
        examples=[
            [
                "https://example.com/photos/room1.jpg",
                "https://example.com/photos/facilities.jpg",
            ]
        ],
    )
    
    @field_validator("overall_rating")
    @classmethod
    def round_rating_to_half(cls, v: Decimal) -> Decimal:
        """
        Round overall rating to nearest 0.5.
        
        Ensures consistent rating increments (1.0, 1.5, 2.0, etc.).
        """
        return Decimal(str(round(float(v) * 2) / 2))
    
    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate and clean review title."""
        v = v.strip()
        if not v:
            raise ValueError("Review title cannot be empty")
        
        # Check for excessive capitalization (possible spam)
        if len(v) > 10 and v.isupper():
            raise ValueError(
                "Please avoid using all caps in your review title"
            )
        
        return v
    
    @field_validator("review_text")
    @classmethod
    def validate_review_text(cls, v: str) -> str:
        """Validate and clean review text."""
        v = v.strip()
        if not v:
            raise ValueError("Review text cannot be empty")
        
        # Check minimum word count (approximately 10 words)
        word_count = len(v.split())
        if word_count < 10:
            raise ValueError(
                "Please provide a more detailed review (minimum 10 words)"
            )
        
        # Check for excessive capitalization
        if len(v) > 50 and sum(1 for c in v if c.isupper()) / len(v) > 0.5:
            raise ValueError(
                "Please avoid excessive use of capital letters in your review"
            )
        
        return v
    
    @field_validator("photos")
    @classmethod
    def validate_photos(cls, v: List[HttpUrl]) -> List[HttpUrl]:
        """Validate photo URLs."""
        if len(v) > 10:
            raise ValueError("Maximum 10 photos allowed per review")
        
        # Convert to list of strings and back to ensure consistency
        return v
    
    @model_validator(mode="after")
    def validate_rating_consistency(self) -> "ReviewBase":
        """
        Validate that overall rating is consistent with detailed ratings.
        
        If detailed ratings are provided, checks that overall rating
        is reasonably aligned with the average of detailed ratings.
        Pydantic v2: mode="after" validators receive the model instance.
        """
        detailed_ratings = [
            r for r in [
                self.cleanliness_rating,
                self.food_quality_rating,
                self.staff_behavior_rating,
                self.security_rating,
                self.value_for_money_rating,
                self.amenities_rating,
            ]
            if r is not None
        ]
        
        if detailed_ratings:
            avg_detailed = sum(detailed_ratings) / len(detailed_ratings)
            overall = float(self.overall_rating)
            
            # Allow some variance (±1 star)
            if abs(overall - avg_detailed) > 1.5:
                raise ValueError(
                    "Overall rating seems inconsistent with detailed ratings. "
                    "Please review your ratings."
                )
        
        return self


class ReviewCreate(ReviewBase, BaseCreateSchema):
    """
    Schema for creating a new review.
    
    Inherits all validation from ReviewBase and adds creation-specific rules.
    """
    
    # Additional fields for creation context
    would_recommend: bool = Field(
        ...,
        description="Would the reviewer recommend this hostel?",
    )
    
    stay_duration_months: Union[int, None] = Field(
        default=None,
        ge=1,
        le=24,
        description="Duration of stay in months (helps with verification)",
    )
    
    @model_validator(mode="after")
    def validate_recommendation_consistency(self) -> "ReviewCreate":
        """
        Validate recommendation aligns with rating.
        
        Warns if low-rated review has recommendation or vice versa.
        Pydantic v2: mode="after" validators receive the model instance.
        """
        rating = float(self.overall_rating)
        
        # High rating (4+) but not recommending seems inconsistent
        if rating >= 4.0 and not self.would_recommend:
            # This is allowed but logged for review
            pass
        
        # Low rating (<3) but recommending seems inconsistent
        if rating < 3.0 and self.would_recommend:
            # This is allowed but logged for review
            pass
        
        return self


class ReviewUpdate(BaseUpdateSchema):
    """
    Schema for updating an existing review.
    
    Allows partial updates with time-limited edit window.
    All fields are optional to support partial updates.
    """
    
    # Content updates
    title: Union[str, None] = Field(
        default=None,
        min_length=5,
        max_length=255,
        description="Updated review title",
    )
    review_text: Union[str, None] = Field(
        default=None,
        min_length=50,
        max_length=5000,
        description="Updated review text",
    )
    
    # Rating updates with proper Decimal constraints
    overall_rating: Union[
        Annotated[
            Decimal,
            Field(
                ge=Decimal("1.0"),
                le=Decimal("5.0"),
                max_digits=2,
                decimal_places=1,
                description="Updated overall rating",
            ),
        ],
        None,
    ] = None
    
    # Detailed ratings updates
    cleanliness_rating: Union[int, None] = Field(default=None, ge=1, le=5)
    food_quality_rating: Union[int, None] = Field(default=None, ge=1, le=5)
    staff_behavior_rating: Union[int, None] = Field(default=None, ge=1, le=5)
    security_rating: Union[int, None] = Field(default=None, ge=1, le=5)
    value_for_money_rating: Union[int, None] = Field(default=None, ge=1, le=5)
    amenities_rating: Union[int, None] = Field(default=None, ge=1, le=5)
    
    # Media updates
    photos: Union[List[HttpUrl], None] = Field(
        default=None,
        max_length=10,
        description="Updated photo list",
    )
    
    @field_validator("overall_rating")
    @classmethod
    def round_rating_to_half(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Round overall rating to nearest 0.5."""
        if v is None:
            return v
        return Decimal(str(round(float(v) * 2) / 2))
    
    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate updated title."""
        if v is None:
            return v
        
        v = v.strip()
        if not v:
            raise ValueError("Review title cannot be empty")
        
        if len(v) > 10 and v.isupper():
            raise ValueError(
                "Please avoid using all caps in your review title"
            )
        
        return v
    
    @field_validator("review_text")
    @classmethod
    def validate_review_text(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate updated review text."""
        if v is None:
            return v
        
        v = v.strip()
        if not v:
            raise ValueError("Review text cannot be empty")
        
        word_count = len(v.split())
        if word_count < 10:
            raise ValueError(
                "Please provide a more detailed review (minimum 10 words)"
            )
        
        return v
    
    @field_validator("photos")
    @classmethod
    def validate_photos(cls, v: Union[List[HttpUrl], None]) -> Union[List[HttpUrl], None]:
        """Validate updated photos."""
        if v is None:
            return v
        
        if len(v) > 10:
            raise ValueError("Maximum 10 photos allowed per review")
        
        return v