# --- File: app/schemas/review/review_submission.py ---
"""
Review submission and verification schemas.

Handles the complete review submission workflow including
verification and eligibility checks.

Pydantic v2 Migration Notes:
- Uses Annotated pattern for Decimal fields with precision constraints
- @computed_field with @property decorator for computed properties
- field_validator and model_validator already use v2 syntax
- Rating fields use max_digits=2, decimal_places=1 for 1.0-5.0 range
- Confidence scores use max_digits=4, decimal_places=3 for 0.000-1.000 range
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Annotated, Dict, List, Optional

from pydantic import Field, HttpUrl, field_validator, model_validator, computed_field
from uuid import UUID

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "ReviewSubmissionRequest",
    "DetailedRatingsInput",
    "VerifiedReview",
    "ReviewGuidelines",
    "ReviewEligibility",
    "ReviewDraft",
]


class DetailedRatingsInput(BaseSchema):
    """
    Detailed aspect ratings for review submission.
    
    Allows reviewers to rate specific aspects of their experience.
    """
    
    cleanliness: int = Field(
        ...,
        ge=1,
        le=5,
        description="Cleanliness and hygiene rating",
    )
    food_quality: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Food quality rating (if mess facility used)",
    )
    staff_behavior: int = Field(
        ...,
        ge=1,
        le=5,
        description="Staff behavior and helpfulness rating",
    )
    security: int = Field(
        ...,
        ge=1,
        le=5,
        description="Safety and security measures rating",
    )
    value_for_money: int = Field(
        ...,
        ge=1,
        le=5,
        description="Value for money rating",
    )
    amenities: int = Field(
        ...,
        ge=1,
        le=5,
        description="Facilities and amenities quality rating",
    )
    location: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Location convenience rating",
    )
    wifi_quality: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Internet/WiFi quality rating",
    )
    maintenance: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Maintenance responsiveness rating",
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def average_rating(self) -> Decimal:
        """Calculate average of all provided ratings."""
        ratings = [
            self.cleanliness,
            self.staff_behavior,
            self.security,
            self.value_for_money,
            self.amenities,
        ]
        
        # Add optional ratings if provided
        optional = [
            self.food_quality,
            self.location,
            self.wifi_quality,
            self.maintenance,
        ]
        ratings.extend([r for r in optional if r is not None])
        
        return Decimal(str(round(sum(ratings) / len(ratings), 2)))


class ReviewSubmissionRequest(BaseCreateSchema):
    """
    Complete review submission request.
    
    Contains all data needed to submit a new review.
    """
    
    hostel_id: UUID = Field(..., description="Hostel to review")
    
    # Verification references (optional but help verify stay)
    booking_id: Optional[UUID] = Field(
        default=None,
        description="Related booking ID for stay verification",
    )
    student_id: Optional[UUID] = Field(
        default=None,
        description="Student profile ID for stay verification",
    )
    
    # Basic review content with proper rating constraints
    overall_rating: Annotated[
        Decimal,
        Field(
            ge=Decimal("1.0"),
            le=Decimal("5.0"),
            max_digits=2,
            decimal_places=1,
            description="Overall rating (1-5, in 0.5 increments)",
            examples=[Decimal("4.5")],
        ),
    ]
    title: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="Review title",
        examples=["Excellent hostel with great facilities"],
    )
    review_text: str = Field(
        ...,
        min_length=50,
        max_length=5000,
        description="Detailed review text",
    )
    
    # Detailed ratings
    detailed_ratings: DetailedRatingsInput = Field(
        ...,
        description="Detailed aspect-specific ratings",
    )
    
    # Media
    photos: List[HttpUrl] = Field(
        default_factory=list,
        max_length=10,
        description="Review photos (max 10)",
    )
    
    # Recommendation
    would_recommend: bool = Field(
        ...,
        description="Would you recommend this hostel?",
    )
    
    # Stay details (helps with verification)
    stay_duration_months: Optional[int] = Field(
        default=None,
        ge=1,
        le=24,
        description="Duration of stay in months",
    )
    check_in_date: Optional[Date] = Field(
        default=None,
        description="Approximate check-in date",
    )
    check_out_date: Optional[Date] = Field(
        default=None,
        description="Approximate check-out date (if moved out)",
    )
    
    # Specific feedback (optional)
    pros: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Things you liked (max 5)",
    )
    cons: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Things that could be improved (max 5)",
    )
    
    # Terms acceptance
    agree_to_guidelines: bool = Field(
        ...,
        description="Confirms agreement to review guidelines",
    )
    
    @field_validator("overall_rating")
    @classmethod
    def round_to_half(cls, v: Decimal) -> Decimal:
        """Round overall rating to nearest 0.5."""
        return Decimal(str(round(float(v) * 2) / 2))
    
    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate and clean title."""
        v = v.strip()
        if not v:
            raise ValueError("Review title cannot be empty")
        
        if len(v) > 10 and v.isupper():
            raise ValueError("Please avoid using all caps in the title")
        
        return v
    
    @field_validator("review_text")
    @classmethod
    def validate_review_text(cls, v: str) -> str:
        """Validate and clean review text."""
        v = v.strip()
        if not v:
            raise ValueError("Review text cannot be empty")
        
        word_count = len(v.split())
        if word_count < 10:
            raise ValueError(
                "Please provide a more detailed review (minimum 10 words)"
            )
        
        return v
    
    @field_validator("agree_to_guidelines")
    @classmethod
    def must_agree(cls, v: bool) -> bool:
        """Ensure user agrees to guidelines."""
        if not v:
            raise ValueError(
                "You must agree to the review guidelines to submit a review"
            )
        return v
    
    @field_validator("pros", "cons")
    @classmethod
    def validate_feedback_items(cls, v: List[str]) -> List[str]:
        """Validate and clean feedback items."""
        cleaned = []
        for item in v:
            item = item.strip()
            if item:
                if len(item) > 200:
                    raise ValueError(
                        "Each feedback item must be 200 characters or less"
                    )
                cleaned.append(item)
        return cleaned
    
    @model_validator(mode="after")
    def validate_dates(self) -> "ReviewSubmissionRequest":
        """
        Validate check-in and check-out dates.
        
        Pydantic v2: mode="after" validators receive the model instance.
        """
        if self.check_in_date and self.check_out_date:
            if self.check_out_date <= self.check_in_date:
                raise ValueError(
                    "Check-out date must be after check-in date"
                )
        
        if self.check_in_date and self.check_in_date > Date.today():
            raise ValueError("Check-in date cannot be in the future")
        
        return self
    
    @model_validator(mode="after")
    def validate_rating_consistency(self) -> "ReviewSubmissionRequest":
        """
        Validate overall rating aligns with detailed ratings.
        
        Pydantic v2: mode="after" validators receive the model instance.
        """
        overall = float(self.overall_rating)
        detailed_avg = float(self.detailed_ratings.average_rating)
        
        # Allow ±1.5 variance
        if abs(overall - detailed_avg) > 1.5:
            raise ValueError(
                "Overall rating seems inconsistent with detailed ratings. "
                "Please review your ratings."
            )
        
        return self


class VerifiedReview(BaseSchema):
    """
    Verified review marker.
    
    Indicates that a review is from a verified stay.
    """
    
    review_id: UUID = Field(..., description="Review ID")
    
    is_verified: bool = Field(..., description="Verification status")
    verification_method: str = Field(
        ...,
        pattern=r"^(booking_verified|student_verified|admin_verified|auto_verified|manual_verified)$",
        description="Method used for verification",
    )
    
    verified_by: Optional[UUID] = Field(
        default=None,
        description="Admin who verified (for manual verification)",
    )
    verified_at: datetime = Field(..., description="Verification timestamp")
    
    # Verification details
    verification_details: Optional[Dict[str, str]] = Field(
        default=None,
        description="Additional verification information",
        examples=[
            {
                "booking_id": "123e4567-e89b-12d3-a456-426614174000",
                "stay_duration": "6 months",
                "verified_via": "booking_system",
            }
        ],
    )
    
    # Confidence score for auto-verification with proper constraints
    verification_confidence: Optional[
        Annotated[
            Decimal,
            Field(
                ge=Decimal("0"),
                le=Decimal("1"),
                max_digits=4,
                decimal_places=3,
                description="Confidence score for auto-verification (0-1)",
            ),
        ]
    ] = None
    
    @field_validator("verification_method")
    @classmethod
    def normalize_method(cls, v: str) -> str:
        """Normalize verification method."""
        return v.lower().strip()


class ReviewGuidelines(BaseSchema):
    """
    Review guidelines and prohibited content.
    
    Helps users understand what makes a good review.
    """
    
    guidelines: List[str] = Field(
        default_factory=lambda: [
            "Be honest and fair in your assessment",
            "Focus on your personal experience",
            "Avoid offensive or abusive language",
            "Don't include personal contact information",
            "Be specific and constructive with feedback",
            "Reviews are public and visible to all users",
            "Rate based on your actual experience, not expectations",
            "Consider both pros and cons objectively",
        ],
        description="Guidelines for writing reviews",
    )
    
    prohibited_content: List[str] = Field(
        default_factory=lambda: [
            "Offensive, abusive, or threatening language",
            "Personal attacks on staff or other residents",
            "Spam, advertising, or promotional content",
            "Fake, fraudulent, or misleading reviews",
            "Reviews for competing businesses",
            "Personal contact information (phone, email, address)",
            "Illegal content or content promoting illegal activities",
            "Discriminatory content based on race, religion, gender, etc.",
        ],
        description="Content that is not allowed in reviews",
    )
    
    tips_for_good_review: List[str] = Field(
        default_factory=lambda: [
            "Describe specific experiences (room quality, food, staff)",
            "Mention the duration of your stay",
            "Include photos if possible",
            "Be balanced - mention both positives and areas for improvement",
            "Update your review if significant changes occur",
        ],
        description="Tips for writing helpful reviews",
    )
    
    minimum_requirements: Dict[str, int] = Field(
        default_factory=lambda: {
            "title_min_length": 5,
            "title_max_length": 255,
            "review_min_length": 50,
            "review_max_length": 5000,
            "min_overall_rating": 1,
            "max_overall_rating": 5,
            "max_photos": 10,
        },
        description="Minimum requirements for review submission",
    )


class ReviewEligibility(BaseSchema):
    """
    Check if user is eligible to review a hostel.
    
    Validates eligibility based on stay history and existing reviews.
    """
    
    user_id: UUID = Field(..., description="User to check eligibility for")
    hostel_id: UUID = Field(..., description="Hostel to review")
    
    can_review: bool = Field(
        ...,
        description="Whether user can submit a review",
    )
    reason: str = Field(
        ...,
        description="Reason for eligibility decision",
        examples=[
            "Eligible to review",
            "Already reviewed this hostel",
            "No verified stay at this hostel",
        ],
    )
    
    # Stay verification
    has_stayed: bool = Field(
        ...,
        description="Whether user has stayed at this hostel",
    )
    has_booking: bool = Field(
        ...,
        description="Whether user has a booking at this hostel",
    )
    stay_verified: bool = Field(
        ...,
        description="Whether stay is verified",
    )
    
    # Existing review
    already_reviewed: bool = Field(
        ...,
        description="Whether user already has a review for this hostel",
    )
    existing_review_id: Optional[UUID] = Field(
        default=None,
        description="ID of existing review (if any)",
    )
    can_edit: bool = Field(
        default=False,
        description="Whether user can edit their existing review",
    )
    edit_deadline: Optional[datetime] = Field(
        default=None,
        description="Deadline for editing existing review",
    )
    
    # Additional info
    last_stay_date: Optional[Date] = Field(
        default=None,
        description="Date of last stay (if applicable)",
    )
    stay_duration_days: Optional[int] = Field(
        default=None,
        ge=1,
        description="Duration of stay in days",
    )


class ReviewDraft(BaseSchema):
    """
    Saved review draft.
    
    Allows users to save incomplete reviews for later.
    """
    
    draft_id: UUID = Field(..., description="Draft ID")
    user_id: UUID = Field(..., description="User who created the draft")
    hostel_id: UUID = Field(..., description="Target hostel")
    
    # Partial content with proper rating constraints
    overall_rating: Optional[
        Annotated[
            Decimal,
            Field(
                ge=Decimal("1.0"),
                le=Decimal("5.0"),
                max_digits=2,
                decimal_places=1,
                description="Overall rating (if set)",
            ),
        ]
    ] = None
    title: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Review title (if set)",
    )
    review_text: Optional[str] = Field(
        default=None,
        max_length=5000,
        description="Review text (if set)",
    )
    
    # Detailed ratings
    detailed_ratings: Optional[Dict[str, int]] = Field(
        default=None,
        description="Detailed ratings (if any set)",
    )
    
    # Photos
    photos: List[str] = Field(
        default_factory=list,
        description="Uploaded photo URLs",
    )
    
    # Timestamps
    created_at: datetime = Field(..., description="Draft creation time")
    updated_at: datetime = Field(..., description="Last update time")
    expires_at: datetime = Field(
        ...,
        description="When draft expires and will be deleted",
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def completion_percentage(self) -> int:
        """Estimate completion percentage."""
        total_fields = 5  # rating, title, text, detailed_ratings, photos
        completed = 0
        
        if self.overall_rating is not None:
            completed += 1
        if self.title:
            completed += 1
        if self.review_text and len(self.review_text) >= 50:
            completed += 1
        if self.detailed_ratings and len(self.detailed_ratings) >= 3:
            completed += 1
        if self.photos:
            completed += 1
        
        return int((completed / total_fields) * 100)
    
    @computed_field  # type: ignore[misc]
    @property
    def is_expired(self) -> bool:
        """Check if draft is expired."""
        return datetime.utcnow() > self.expires_at