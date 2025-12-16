# --- File: app/schemas/hostel/hostel_response.py ---
"""
Hostel response schemas for API responses.
"""

from datetime import datetime, time
from decimal import Decimal
from typing import Annotated, List, Union
from uuid import UUID

from pydantic import ConfigDict, Field

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import HostelStatus, HostelType

__all__ = [
    "HostelResponse",
    "HostelDetail",
    "HostelListItem",
    "HostelStats",
]


class HostelResponse(BaseResponseSchema):
    """
    Basic hostel response schema.
    
    Standard response for hostel operations.
    """
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Hostel name")
    slug: str = Field(..., description="URL slug")
    hostel_type: HostelType = Field(..., description="Hostel type")
    city: str = Field(..., description="City")
    state: str = Field(..., description="State")
    starting_price_monthly: Union[Annotated[
        Decimal,
        Field(description="Starting monthly price")
    ], None] = None
    average_rating: Annotated[
        Decimal,
        Field(ge=0, le=5, description="Average rating")
    ]
    total_reviews: int = Field(
        ...,
        ge=0,
        description="Total number of reviews",
    )
    total_rooms: int = Field(
        ...,
        ge=0,
        description="Total number of rooms",
    )
    available_beds: int = Field(
        ...,
        ge=0,
        description="Available beds",
    )
    is_public: bool = Field(..., description="Public visibility")
    is_featured: bool = Field(..., description="Featured status")
    cover_image_url: Union[str, None] = Field(
        default=None,
        description="Cover image URL",
    )
    status: HostelStatus = Field(..., description="Operational status")


class HostelDetail(BaseResponseSchema):
    """
    Detailed hostel information.
    
    Comprehensive hostel data for detail views.
    """
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="Hostel name")
    slug: str = Field(..., description="URL slug")
    description: Union[str, None] = Field(
        default=None,
        description="Hostel description",
    )

    # Type and contact
    hostel_type: HostelType = Field(..., description="Hostel type")
    contact_email: Union[str, None] = Field(
        default=None,
        description="Contact email",
    )
    contact_phone: str = Field(..., description="Contact phone")
    alternate_phone: Union[str, None] = Field(
        default=None,
        description="Alternate phone",
    )
    website_url: Union[str, None] = Field(
        default=None,
        description="Website URL",
    )

    # Address
    address_line1: str = Field(..., description="Address line 1")
    address_line2: Union[str, None] = Field(
        default=None,
        description="Address line 2",
    )
    city: str = Field(..., description="City")
    state: str = Field(..., description="State")
    pincode: str = Field(..., description="Pincode")
    country: str = Field(..., description="Country")
    latitude: Union[Decimal, None] = Field(
        default=None,
        description="Latitude",
    )
    longitude: Union[Decimal, None] = Field(
        default=None,
        description="Longitude",
    )

    # Pricing
    starting_price_monthly: Union[Annotated[
        Decimal,
        Field(description="Starting monthly price")
    ], None] = None
    currency: str = Field(..., description="Currency code")

    # Capacity
    total_rooms: int = Field(
        ...,
        ge=0,
        description="Total number of rooms",
    )
    total_beds: int = Field(
        ...,
        ge=0,
        description="Total number of beds",
    )
    occupied_beds: int = Field(
        ...,
        ge=0,
        description="Occupied beds",
    )
    available_beds: int = Field(
        ...,
        ge=0,
        description="Available beds",
    )

    # Ratings
    average_rating: Annotated[
        Decimal,
        Field(ge=0, le=5, description="Average rating")
    ]
    total_reviews: int = Field(
        ...,
        ge=0,
        description="Total reviews",
    )

    # Features
    amenities: List[str] = Field(
        default_factory=list,
        description="Available amenities",
    )
    facilities: List[str] = Field(
        default_factory=list,
        description="Available facilities",
    )
    security_features: List[str] = Field(
        default_factory=list,
        description="Security features",
    )

    # Policies
    rules: Union[str, None] = Field(
        default=None,
        description="Hostel rules",
    )
    check_in_time: Union[time, None] = Field(
        default=None,
        description="Check-in time",
    )
    check_out_time: Union[time, None] = Field(
        default=None,
        description="Check-out time",
    )
    visitor_policy: Union[str, None] = Field(
        default=None,
        description="Visitor policy",
    )
    late_entry_policy: Union[str, None] = Field(
        default=None,
        description="Late entry policy",
    )

    # Location info
    nearby_landmarks: List[dict] = Field(
        default_factory=list,
        description="Nearby landmarks",
    )
    connectivity_info: Union[str, None] = Field(
        default=None,
        description="Connectivity information",
    )

    # Media
    cover_image_url: Union[str, None] = Field(
        default=None,
        description="Cover image URL",
    )
    gallery_images: List[str] = Field(
        default_factory=list,
        description="Gallery images",
    )
    virtual_tour_url: Union[str, None] = Field(
        default=None,
        description="Virtual tour URL",
    )

    # Status
    is_public: bool = Field(..., description="Public visibility")
    is_featured: bool = Field(..., description="Featured status")
    is_verified: bool = Field(..., description="Verification status")
    status: HostelStatus = Field(..., description="Operational status")
    is_active: bool = Field(..., description="Active status")

    # SEO
    meta_title: Union[str, None] = Field(
        default=None,
        description="SEO meta title",
    )
    meta_description: Union[str, None] = Field(
        default=None,
        description="SEO meta description",
    )
    meta_keywords: Union[str, None] = Field(
        default=None,
        description="SEO keywords",
    )


class HostelListItem(BaseSchema):
    """
    Hostel list item for list views.
    
    Minimal information for efficient list rendering.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Hostel ID")
    name: str = Field(..., description="Hostel name")
    slug: str = Field(..., description="URL slug")
    hostel_type: HostelType = Field(..., description="Hostel type")
    city: str = Field(..., description="City")
    state: str = Field(..., description="State")
    starting_price_monthly: Union[Annotated[
        Decimal,
        Field(description="Starting price")
    ], None] = None
    average_rating: Annotated[
        Decimal,
        Field(ge=0, le=5, description="Average rating")
    ]
    total_reviews: int = Field(
        ...,
        ge=0,
        description="Total reviews",
    )
    available_beds: int = Field(
        ...,
        ge=0,
        description="Available beds",
    )
    cover_image_url: Union[str, None] = Field(
        default=None,
        description="Cover image",
    )
    is_featured: bool = Field(..., description="Featured status")
    distance_km: Union[Annotated[
        Decimal,
        Field(ge=0, description="Distance from search location")
    ], None] = None


class HostelStats(BaseSchema):
    """
    Hostel statistics summary.
    
    Key metrics and statistics for a hostel.
    """
    model_config = ConfigDict(from_attributes=True)

    hostel_id: UUID = Field(..., description="Hostel ID")

    # Occupancy
    total_rooms: int = Field(
        ...,
        ge=0,
        description="Total rooms",
    )
    total_beds: int = Field(
        ...,
        ge=0,
        description="Total beds",
    )
    occupied_beds: int = Field(
        ...,
        ge=0,
        description="Occupied beds",
    )
    available_beds: int = Field(
        ...,
        ge=0,
        description="Available beds",
    )
    occupancy_percentage: Annotated[
        Decimal,
        Field(ge=0, le=100, description="Occupancy percentage")
    ]

    # Revenue
    total_revenue_monthly: Annotated[
        Decimal,
        Field(ge=0, description="Total monthly revenue")
    ]
    total_outstanding: Annotated[
        Decimal,
        Field(ge=0, description="Total outstanding payments")
    ]

    # Students
    total_students: int = Field(
        ...,
        ge=0,
        description="Total registered students",
    )
    active_students: int = Field(
        ...,
        ge=0,
        description="Active students",
    )

    # Complaints
    open_complaints: int = Field(
        ...,
        ge=0,
        description="Open complaints",
    )
    resolved_complaints: int = Field(
        ...,
        ge=0,
        description="Resolved complaints",
    )

    # Bookings
    pending_bookings: int = Field(
        ...,
        ge=0,
        description="Pending booking requests",
    )
    confirmed_bookings: int = Field(
        ...,
        ge=0,
        description="Confirmed bookings",
    )

    # Reviews
    average_rating: Annotated[
        Decimal,
        Field(ge=0, le=5, description="Average rating")
    ]
    total_reviews: int = Field(
        ...,
        ge=0,
        description="Total reviews",
    )

    # Last updated
    updated_at: datetime = Field(..., description="Last update timestamp")