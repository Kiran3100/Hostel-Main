# --- File: app/schemas/hostel/hostel_comparison.py ---
"""
Hostel comparison schemas for side-by-side analysis.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Dict, List, Union
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import HostelType

__all__ = [
    "HostelComparisonRequest",
    "ComparisonResult",
    "ComparisonItem",
    "RoomTypeComparison",
    "ComparisonSummary",
    "PriceComparison",
    "AmenityComparison",
]


class HostelComparisonRequest(BaseCreateSchema):
    """
    Request to compare multiple hostels.
    
    Allows comparison of 2-4 hostels side by side.
    """
    model_config = ConfigDict(from_attributes=True)

    hostel_ids: List[UUID] = Field(
        ...,
        min_length=2,
        max_length=4,
        description="2-4 hostel IDs to compare",
    )

    @field_validator("hostel_ids")
    @classmethod
    def validate_unique_ids(cls, v: List[UUID]) -> List[UUID]:
        """Ensure hostel IDs are unique."""
        if len(v) != len(set(v)):
            raise ValueError("Hostel IDs must be unique")
        return v


class RoomTypeComparison(BaseSchema):
    """
    Room type details for comparison.
    
    Provides room-specific information for comparison.
    """
    model_config = ConfigDict(from_attributes=True)

    room_type: str = Field(
        ...,
        description="Room type (single, double, etc.)",
    )
    price_monthly: Annotated[
        Decimal,
        Field(ge=0, description="Monthly price")
    ]
    available_beds: int = Field(
        ...,
        ge=0,
        description="Available beds",
    )
    total_beds: int = Field(
        ...,
        ge=0,
        description="Total beds",
    )
    amenities: List[str] = Field(
        default_factory=list,
        description="Room-specific amenities",
    )


class ComparisonItem(BaseSchema):
    """
    Individual hostel data in comparison.
    
    Complete hostel information formatted for comparison.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Hostel ID")
    name: str = Field(..., description="Hostel name")
    slug: str = Field(..., description="URL slug")
    hostel_type: HostelType = Field(..., description="Hostel type")

    # Location
    city: str = Field(..., description="City")
    state: str = Field(..., description="State")
    address: str = Field(..., description="Full address")
    distance_from_center_km: Union[Annotated[
        Decimal,
        Field(ge=0, description="Distance from city center (km)")
    ], None] = None

    # Pricing
    starting_price_monthly: Annotated[
        Decimal,
        Field(ge=0, description="Starting monthly price")
    ]
    price_range_monthly: str = Field(
        ...,
        description="Price range (e.g., '₹5,000 - ₹15,000')",
    )
    security_deposit: Union[Annotated[
        Decimal,
        Field(ge=0, description="Security deposit amount")
    ], None] = None

    # Capacity
    total_beds: int = Field(
        ...,
        ge=0,
        description="Total bed capacity",
    )
    available_beds: int = Field(
        ...,
        ge=0,
        description="Currently available beds",
    )

    # Ratings
    average_rating: Annotated[
        Decimal,
        Field(ge=0, le=5, description="Average rating")
    ]
    total_reviews: int = Field(
        ...,
        ge=0,
        description="Total number of reviews",
    )
    rating_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Rating distribution (1-5 stars)",
    )

    # Amenities
    amenities: List[str] = Field(
        default_factory=list,
        description="General amenities",
    )
    facilities: List[str] = Field(
        default_factory=list,
        description="Facilities available",
    )
    security_features: List[str] = Field(
        default_factory=list,
        description="Security features",
    )

    # Room types
    room_types_available: List[str] = Field(
        default_factory=list,
        description="Available room types",
    )
    room_type_details: List[RoomTypeComparison] = Field(
        default_factory=list,
        description="Detailed room type information",
    )

    # Policies
    check_in_time: Union[str, None] = Field(
        default=None,
        description="Check-in time",
    )
    check_out_time: Union[str, None] = Field(
        default=None,
        description="Check-out time",
    )
    visitor_allowed: bool = Field(
        ...,
        description="Whether visitors are allowed",
    )

    # Media
    cover_image_url: Union[str, None] = Field(
        default=None,
        description="Cover image URL",
    )
    total_images: int = Field(
        ...,
        ge=0,
        description="Total number of images",
    )
    has_virtual_tour: bool = Field(
        ...,
        description="Virtual tour availability",
    )

    # Highlights
    unique_features: List[str] = Field(
        default_factory=list,
        description="Unique selling points",
    )
    pros: List[str] = Field(
        default_factory=list,
        description="Advantages/pros",
    )
    cons: List[str] = Field(
        default_factory=list,
        description="Disadvantages/cons",
    )


class PriceComparison(BaseSchema):
    """
    Price comparison summary.
    
    Provides price statistics across compared hostels.
    """
    model_config = ConfigDict(from_attributes=True)

    lowest_price: Annotated[
        Decimal,
        Field(ge=0, description="Lowest starting price")
    ]
    highest_price: Annotated[
        Decimal,
        Field(ge=0, description="Highest starting price")
    ]
    average_price: Annotated[
        Decimal,
        Field(ge=0, description="Average starting price")
    ]
    price_difference_percentage: Annotated[
        Decimal,
        Field(ge=0, description="Percentage difference between lowest and highest")
    ]


class AmenityComparison(BaseSchema):
    """
    Amenity comparison summary.
    
    Provides amenity statistics and unique features.
    """
    model_config = ConfigDict(from_attributes=True)

    common_amenities: List[str] = Field(
        default_factory=list,
        description="Amenities present in all compared hostels",
    )
    unique_to_hostel: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Unique amenities per hostel (hostel_id: [amenities])",
    )
    total_unique_amenities: int = Field(
        ...,
        ge=0,
        description="Total number of unique amenity types",
    )


class ComparisonSummary(BaseSchema):
    """
    Comparison summary with recommendations.
    
    Provides quick insights and best options.
    """
    model_config = ConfigDict(from_attributes=True)

    best_for_budget: UUID = Field(
        ...,
        description="Best value for money (hostel ID)",
    )
    best_rated: UUID = Field(
        ...,
        description="Highest rated hostel (hostel ID)",
    )
    best_location: Union[UUID, None] = Field(
        default=None,
        description="Best location (hostel ID)",
    )
    most_amenities: UUID = Field(
        ...,
        description="Most amenities (hostel ID)",
    )
    best_availability: UUID = Field(
        ...,
        description="Best bed availability (hostel ID)",
    )

    price_comparison: PriceComparison = Field(
        ...,
        description="Price comparison statistics",
    )
    amenity_comparison: AmenityComparison = Field(
        ...,
        description="Amenity comparison statistics",
    )


class ComparisonResult(BaseSchema):
    """
    Complete comparison result.
    
    Aggregates all comparison data and insights.
    """
    model_config = ConfigDict(from_attributes=True)

    hostels: List[ComparisonItem] = Field(
        ...,
        description="Hostels being compared",
    )
    comparison_criteria: List[str] = Field(
        ...,
        description="Criteria included in comparison",
    )
    summary: ComparisonSummary = Field(
        ...,
        description="Comparison summary and recommendations",
    )
    generated_at: datetime = Field(
        ...,
        description="Comparison generation timestamp",
    )