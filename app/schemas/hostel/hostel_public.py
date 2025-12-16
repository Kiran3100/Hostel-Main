# --- File: app/schemas/hostel/hostel_public.py ---
"""
Public hostel profile schemas for visitor-facing content.
"""

from datetime import time
from decimal import Decimal
from typing import Annotated, Dict, List, Union
from uuid import UUID

from pydantic import ConfigDict, Field

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import HostelType

__all__ = [
    "PublicHostelCard",
    "PublicRoomType",
    "PublicHostelProfile",
    "PublicHostelList",
]


class PublicHostelCard(BaseSchema):
    """
    Hostel card for public listing/search results.
    
    Provides essential information for hostel browsing.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Hostel ID")
    name: str = Field(..., description="Hostel name")
    slug: str = Field(..., description="URL slug")
    hostel_type: HostelType = Field(..., description="Hostel type")
    city: str = Field(..., description="City")
    state: str = Field(..., description="State")
    starting_price_monthly: Annotated[
        Decimal,
        Field(ge=0, description="Starting monthly price")
    ]
    currency: str = Field(..., description="Currency code")
    average_rating: Annotated[
        Decimal,
        Field(ge=0, le=5, description="Average rating")
    ]
    total_reviews: int = Field(
        ...,
        ge=0,
        description="Total number of reviews",
    )
    available_beds: int = Field(
        ...,
        ge=0,
        description="Available beds",
    )
    cover_image_url: Union[str, None] = Field(
        default=None,
        description="Cover image URL",
    )
    is_featured: bool = Field(
        ...,
        description="Featured status",
    )
    amenities: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Top 5 amenities for quick view",
    )
    distance_km: Union[Annotated[
        Decimal,
        Field(ge=0, description="Distance from search location (if applicable)")
    ], None] = None


class PublicRoomType(BaseSchema):
    """
    Public room type information.
    
    Provides room-specific details for visitors.
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
    price_quarterly: Union[Annotated[
        Decimal,
        Field(ge=0, description="Quarterly price (if available)")
    ], None] = None
    price_yearly: Union[Annotated[
        Decimal,
        Field(ge=0, description="Yearly price (if available)")
    ], None] = None
    available_beds: int = Field(
        ...,
        ge=0,
        description="Available beds of this type",
    )
    total_beds: int = Field(
        ...,
        ge=0,
        description="Total beds of this type",
    )
    room_amenities: List[str] = Field(
        default_factory=list,
        description="Room-specific amenities",
    )
    room_images: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Room images (max 10)",
    )
    room_size_sqft: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Room size in square feet",
    )


class PublicHostelProfile(BaseSchema):
    """
    Complete public hostel profile.
    
    Comprehensive hostel information for detail pages.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Hostel ID")
    name: str = Field(..., description="Hostel name")
    slug: str = Field(..., description="URL slug")
    description: Union[str, None] = Field(
        default=None,
        description="Hostel description",
    )
    hostel_type: HostelType = Field(..., description="Hostel type")

    # Contact (public)
    contact_phone: str = Field(..., description="Contact phone number")
    contact_email: Union[str, None] = Field(
        default=None,
        description="Contact email",
    )
    website_url: Union[str, None] = Field(
        default=None,
        description="Official website URL",
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
    latitude: Union[Decimal, None] = Field(
        default=None,
        description="Latitude for map display",
    )
    longitude: Union[Decimal, None] = Field(
        default=None,
        description="Longitude for map display",
    )

    # Pricing
    starting_price_monthly: Annotated[
        Decimal,
        Field(ge=0, description="Starting monthly price")
    ]
    currency: str = Field(..., description="Currency code")

    # Availability
    available_beds: int = Field(
        ...,
        ge=0,
        description="Total available beds",
    )
    total_beds: int = Field(
        ...,
        ge=0,
        description="Total bed capacity",
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
        description="Rating distribution {1: count, 2: count, ...}",
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
        description="Hostel rules and regulations",
    )
    check_in_time: Union[time, None] = Field(
        default=None,
        description="Standard check-in time",
    )
    check_out_time: Union[time, None] = Field(
        default=None,
        description="Standard check-out time",
    )
    visitor_policy: Union[str, None] = Field(
        default=None,
        description="Visitor policy",
    )

    # Location
    nearby_landmarks: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Nearby landmarks with details",
    )
    connectivity_info: Union[str, None] = Field(
        default=None,
        description="Public transport connectivity",
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
        description="360° virtual tour URL",
    )

    # Room types available
    room_types: List[PublicRoomType] = Field(
        default_factory=list,
        description="Available room types with pricing",
    )

    # Additional info
    established_year: Union[int, None] = Field(
        default=None,
        ge=1900,
        le=2100,
        description="Year established",
    )
    total_rooms: int = Field(
        ...,
        ge=0,
        description="Total number of rooms",
    )


class PublicHostelList(BaseSchema):
    """
    List of public hostels with metadata.
    
    Response schema for hostel listing pages.
    """
    model_config = ConfigDict(from_attributes=True)

    hostels: List[PublicHostelCard] = Field(
        ...,
        description="List of hostels",
    )
    total_count: int = Field(
        ...,
        ge=0,
        description="Total number of hostels matching criteria",
    )
    filters_applied: Dict[str, str] = Field(
        default_factory=dict,
        description="Summary of applied filters",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Current page number",
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Items per page",
    )
    total_pages: int = Field(
        ...,
        ge=0,
        description="Total number of pages",
    )