# --- File: app/schemas/review/review_response.py ---
"""
Review response schemas for API responses.

Provides comprehensive response formats for reviews.

Pydantic v2 Migration Notes:
- Uses Annotated pattern for Decimal fields with precision constraints
- @computed_field with @property decorator for computed properties
- Rating fields use max_digits=2, decimal_places=1 for 1.0-5.0 range
- Percentage fields use max_digits=5, decimal_places=2 for 0.00-100.00 range
- Average rating fields use max_digits=3, decimal_places=2 for more precision
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, List, Union
from uuid import UUID

from pydantic import Field, computed_field

from app.schemas.common.base import BaseResponseSchema, BaseSchema

__all__ = [
    "ReviewResponse",
    "ReviewDetail",
    "ReviewListItem",
    "ReviewSummary",
    "HostelResponseDetail",
    "PaginatedReviewResponse",
]


class HostelResponseDetail(BaseSchema):
    """
    Hostel's response to a review.
    
    Represents management's reply to customer feedback.
    """
    
    response_id: UUID = Field(..., description="Response ID")
    response_text: str = Field(
        ...,
        min_length=20,
        max_length=2000,
        description="Response text from hostel management",
    )
    responded_by: UUID = Field(..., description="User who responded")
    responded_by_name: str = Field(..., description="Responder's name")
    responded_by_role: str = Field(
        ...,
        description="Responder's role (admin, owner, manager)",
    )
    responded_at: datetime = Field(..., description="Response timestamp")
    
    # Metadata
    is_edited: bool = Field(
        default=False,
        description="Whether response has been edited",
    )
    edited_at: Union[datetime, None] = Field(
        default=None,
        description="Last edit timestamp",
    )


class ReviewResponse(BaseResponseSchema):
    """
    Basic review response.
    
    Minimal review information for list views.
    """
    
    # Hostel info
    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    
    # Reviewer info
    reviewer_id: UUID = Field(..., description="Reviewer user ID")
    reviewer_name: str = Field(..., description="Reviewer display name")
    
    # Review content with proper rating constraints
    overall_rating: Annotated[
        Decimal,
        Field(
            ge=Decimal("1.0"),
            le=Decimal("5.0"),
            max_digits=2,
            decimal_places=1,
            description="Overall rating",
        ),
    ]
    title: str = Field(..., description="Review title")
    review_text: str = Field(..., description="Review text")
    
    # Verification
    is_verified_stay: bool = Field(
        ...,
        description="Whether stay is verified",
    )
    verified_at: Union[datetime, None] = Field(
        default=None,
        description="Verification timestamp",
    )
    
    # Status
    is_approved: bool = Field(..., description="Approval status")
    
    # Engagement
    helpful_count: int = Field(..., ge=0, description="Helpful votes count")
    not_helpful_count: int = Field(..., ge=0, description="Not helpful votes")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    
    @computed_field  # type: ignore[misc]
    @property
    def helpfulness_ratio(self) -> Decimal:
        """Calculate helpfulness ratio."""
        total_votes = self.helpful_count + self.not_helpful_count
        if total_votes == 0:
            return Decimal("0.5")  # Neutral
        return Decimal(str(round(self.helpful_count / total_votes, 3)))


class ReviewDetail(BaseResponseSchema):
    """
    Detailed review information.
    
    Complete review data including all ratings, media, and metadata.
    """
    
    # Hostel info
    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    
    # Reviewer info
    reviewer_id: UUID = Field(..., description="Reviewer ID")
    reviewer_name: str = Field(..., description="Reviewer name")
    reviewer_profile_image: Union[str, None] = Field(
        default=None,
        description="Reviewer profile image URL",
    )
    
    # References
    student_id: Union[UUID, None] = Field(default=None, description="Student profile ID")
    booking_id: Union[UUID, None] = Field(default=None, description="Related booking ID")
    
    # Ratings with proper constraints
    overall_rating: Annotated[
        Decimal,
        Field(
            ge=Decimal("1.0"),
            le=Decimal("5.0"),
            max_digits=2,
            decimal_places=1,
            description="Overall rating",
        ),
    ]
    cleanliness_rating: Union[int, None] = Field(default=None, ge=1, le=5)
    food_quality_rating: Union[int, None] = Field(default=None, ge=1, le=5)
    staff_behavior_rating: Union[int, None] = Field(default=None, ge=1, le=5)
    security_rating: Union[int, None] = Field(default=None, ge=1, le=5)
    value_for_money_rating: Union[int, None] = Field(default=None, ge=1, le=5)
    amenities_rating: Union[int, None] = Field(default=None, ge=1, le=5)
    location_rating: Union[int, None] = Field(default=None, ge=1, le=5)
    wifi_quality_rating: Union[int, None] = Field(default=None, ge=1, le=5)
    
    # Content
    title: str = Field(..., description="Review title")
    review_text: str = Field(..., description="Full review text")
    
    # Media
    photos: List[str] = Field(
        default_factory=list,
        description="Review photo URLs",
    )
    
    # Verification
    is_verified_stay: bool = Field(..., description="Verification status")
    verified_at: Union[datetime, None] = Field(default=None, description="Verification time")
    verification_method: Union[str, None] = Field(
        default=None,
        description="How the stay was verified",
    )
    
    # Moderation
    is_approved: bool = Field(..., description="Approval status")
    approved_by: Union[UUID, None] = Field(default=None, description="Approver ID")
    approved_at: Union[datetime, None] = Field(default=None, description="Approval time")
    
    is_flagged: bool = Field(default=False, description="Flagged status")
    flag_reason: Union[str, None] = Field(default=None, description="Flag reason")
    flagged_by: Union[UUID, None] = Field(default=None, description="Flagger ID")
    flagged_at: Union[datetime, None] = Field(default=None, description="Flag time")
    
    # Engagement
    helpful_count: int = Field(..., ge=0, description="Helpful votes")
    not_helpful_count: int = Field(..., ge=0, description="Not helpful votes")
    report_count: int = Field(..., ge=0, description="Report count")
    
    # Hostel response
    hostel_response: Union[HostelResponseDetail, None] = Field(
        default=None,
        description="Hostel's response to this review",
    )
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    # Visibility
    is_published: bool = Field(..., description="Publication status")
    
    # Additional metadata
    would_recommend: Union[bool, None] = Field(
        default=None,
        description="Whether reviewer recommends the hostel",
    )
    stay_duration_months: Union[int, None] = Field(
        default=None,
        ge=1,
        le=24,
        description="Duration of stay",
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def total_votes(self) -> int:
        """Total votes on this review."""
        return self.helpful_count + self.not_helpful_count
    
    @computed_field  # type: ignore[misc]
    @property
    def average_detailed_rating(self) -> Union[Decimal, None]:
        """Calculate average of detailed ratings."""
        ratings = [
            r for r in [
                self.cleanliness_rating,
                self.food_quality_rating,
                self.staff_behavior_rating,
                self.security_rating,
                self.value_for_money_rating,
                self.amenities_rating,
                self.location_rating,
                self.wifi_quality_rating,
            ]
            if r is not None
        ]
        
        if not ratings:
            return None
        
        return Decimal(str(round(sum(ratings) / len(ratings), 2)))


class ReviewListItem(BaseSchema):
    """
    Review list item for paginated lists.
    
    Optimized for list views with essential information only.
    """
    
    id: UUID = Field(..., description="Review ID")
    reviewer_name: str = Field(..., description="Reviewer name")
    reviewer_image: Union[str, None] = Field(default=None, description="Profile image URL")
    
    overall_rating: Annotated[
        Decimal,
        Field(
            ge=Decimal("1.0"),
            le=Decimal("5.0"),
            max_digits=2,
            decimal_places=1,
            description="Overall rating",
        ),
    ]
    title: str = Field(..., description="Review title")
    review_excerpt: str = Field(
        ...,
        max_length=150,
        description="Review text excerpt (first 150 chars)",
    )
    
    is_verified_stay: bool = Field(..., description="Verification status")
    helpful_count: int = Field(..., ge=0, description="Helpful votes")
    
    has_photos: bool = Field(..., description="Has photos attached")
    photo_count: int = Field(..., ge=0, description="Number of photos")
    
    created_at: datetime = Field(..., description="Creation timestamp")
    
    has_hostel_response: bool = Field(
        ...,
        description="Whether hostel has responded",
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def days_ago(self) -> int:
        """Days since review was posted."""
        delta = datetime.utcnow() - self.created_at
        return delta.days


class ReviewSummary(BaseSchema):
    """
    Review summary for a hostel.
    
    Aggregated review statistics and recent reviews.
    """
    
    hostel_id: UUID = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    
    # Aggregate metrics with proper rating constraints
    total_reviews: int = Field(..., ge=0, description="Total reviews count")
    average_rating: Annotated[
        Decimal,
        Field(
            ge=Decimal("1.0"),
            le=Decimal("5.0"),
            max_digits=3,
            decimal_places=2,
            description="Average overall rating",
        ),
    ]
    
    # Rating distribution
    rating_5_count: int = Field(..., ge=0)
    rating_4_count: int = Field(..., ge=0)
    rating_3_count: int = Field(..., ge=0)
    rating_2_count: int = Field(..., ge=0)
    rating_1_count: int = Field(..., ge=0)
    
    # Verified reviews
    verified_reviews_count: int = Field(..., ge=0)
    verified_reviews_percentage: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Percentage of verified reviews",
        ),
    ]
    
    # Average detailed ratings with proper constraints
    average_cleanliness: Union[
        Annotated[
            Decimal,
            Field(
                ge=Decimal("1"),
                le=Decimal("5"),
                max_digits=3,
                decimal_places=2,
            ),
        ],
        None,
    ] = None
    average_food_quality: Union[
        Annotated[
            Decimal,
            Field(
                ge=Decimal("1"),
                le=Decimal("5"),
                max_digits=3,
                decimal_places=2,
            ),
        ],
        None,
    ] = None
    average_staff_behavior: Union[
        Annotated[
            Decimal,
            Field(
                ge=Decimal("1"),
                le=Decimal("5"),
                max_digits=3,
                decimal_places=2,
            ),
        ],
        None,
    ] = None
    average_security: Union[
        Annotated[
            Decimal,
            Field(
                ge=Decimal("1"),
                le=Decimal("5"),
                max_digits=3,
                decimal_places=2,
            ),
        ],
        None,
    ] = None
    average_value_for_money: Union[
        Annotated[
            Decimal,
            Field(
                ge=Decimal("1"),
                le=Decimal("5"),
                max_digits=3,
                decimal_places=2,
            ),
        ],
        None,
    ] = None
    average_amenities: Union[
        Annotated[
            Decimal,
            Field(
                ge=Decimal("1"),
                le=Decimal("5"),
                max_digits=3,
                decimal_places=2,
            ),
        ],
        None,
    ] = None
    
    # Recent reviews
    recent_reviews: List[ReviewListItem] = Field(
        default_factory=list,
        max_length=5,
        description="5 most recent reviews",
    )
    
    # Recommendation metric with percentage constraints
    would_recommend_percentage: Annotated[
        Decimal,
        Field(
            ge=Decimal("0"),
            le=Decimal("100"),
            max_digits=5,
            decimal_places=2,
            description="Percentage of reviewers who would recommend",
        ),
    ]
    
    @computed_field  # type: ignore[misc]
    @property
    def positive_review_percentage(self) -> Decimal:
        """Percentage of 4-5 star reviews."""
        if self.total_reviews == 0:
            return Decimal("0")
        
        positive = self.rating_5_count + self.rating_4_count
        return Decimal(str(round((positive / self.total_reviews) * 100, 2)))
    
    @computed_field  # type: ignore[misc]
    @property
    def rating_quality_score(self) -> str:
        """
        Qualitative rating description.
        
        Returns: excellent, very_good, good, average, or poor
        """
        rating = float(self.average_rating)
        if rating >= 4.5:
            return "excellent"
        elif rating >= 4.0:
            return "very_good"
        elif rating >= 3.5:
            return "good"
        elif rating >= 3.0:
            return "average"
        else:
            return "poor"


class PaginatedReviewResponse(BaseSchema):
    """
    Paginated review response.
    
    Standard pagination wrapper for review lists.
    """
    
    items: List[ReviewListItem] = Field(
        ...,
        description="List of review items for current page",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of items across all pages",
    )
    page: int = Field(
        ...,
        ge=1,
        description="Current page number",
    )
    page_size: int = Field(
        ...,
        ge=1,
        description="Number of items per page",
    )
    pages: int = Field(
        ...,
        ge=1,
        description="Total number of pages",
    )
    
    @computed_field  # type: ignore[misc]
    @property
    def has_next(self) -> bool:
        """Whether there are more pages after current."""
        return self.page < self.pages
    
    @computed_field  # type: ignore[misc]
    @property
    def has_previous(self) -> bool:
        """Whether there are pages before current."""
        return self.page > 1
    
    @computed_field  # type: ignore[misc]
    @property
    def next_page(self) -> Union[int, None]:
        """Next page number or None if last page."""
        return self.page + 1 if self.has_next else None
    
    @computed_field  # type: ignore[misc]
    @property
    def previous_page(self) -> Union[int, None]:
        """Previous page number or None if first page."""
        return self.page - 1 if self.has_previous else None