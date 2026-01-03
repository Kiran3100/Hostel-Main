# --- File: app/schemas/hostel/hostel_public.py ---
"""
Public hostel profile schemas for visitor-facing content.
"""

from datetime import time
from decimal import Decimal
from typing import Annotated, Dict, List, Union
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.common.base import BaseSchema, BaseFilterSchema
from app.schemas.common.enums import HostelType

__all__ = [
    "PublicHostelCard",
    "PublicRoomType",
    "PublicHostelProfile",
    "PublicHostelList",
    "PublicHostelListItem",
    "PublicHostelSearch",
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


class PublicHostelListItem(BaseSchema):
    """
    Simplified hostel item for search results and lists.
    
    Compact version optimized for list views and search results.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Hostel ID")
    name: str = Field(..., description="Hostel name")
    slug: str = Field(..., description="URL slug")
    hostel_type: HostelType = Field(..., description="Hostel type")
    city: str = Field(..., description="City")
    state: str = Field(..., description="State")
    
    # Pricing
    starting_price_monthly: Union[Annotated[
        Decimal,
        Field(ge=0, description="Starting monthly price")
    ], None] = None
    currency: str = Field(default="INR", description="Currency code")
    
    # Ratings
    average_rating: Annotated[
        Decimal,
        Field(ge=0, le=5, description="Average rating")
    ] = Decimal("0.0")
    total_reviews: int = Field(
        default=0,
        ge=0,
        description="Review count",
    )
    
    # Availability
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
    
    # Visual
    cover_image_url: Union[str, None] = Field(
        default=None,
        description="Cover image URL",
    )
    is_featured: bool = Field(
        default=False,
        description="Featured status",
    )
    
    # Quick info
    key_amenities: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Top 5 amenities for quick view",
    )
    
    # Distance (for location-based searches)
    distance_km: Union[Annotated[
        Decimal,
        Field(ge=0, description="Distance from search location")
    ], None] = None
    
    # Quick stats
    occupancy_percentage: Union[Annotated[
        Decimal,
        Field(ge=0, le=100, description="Current occupancy percentage")
    ], None] = None


class PublicHostelSearch(BaseFilterSchema):
    """
    Public hostel search request schema.
    
    Used for filtering and searching publicly available hostels.
    """
    model_config = ConfigDict(from_attributes=True)

    # Location filters
    city: Union[str, None] = Field(
        default=None,
        min_length=2,
        description="Filter by city name"
    )
    state: Union[str, None] = Field(
        default=None,
        min_length=2,
        description="Filter by state name"
    )
    pincode: Union[str, None] = Field(
        default=None,
        pattern=r"^\d{6}$",
        description="Filter by pincode"
    )
    
    # Geolocation search
    latitude: Union[Annotated[
        Decimal,
        Field(ge=-90, le=90, description="Latitude for location-based search")
    ], None] = None
    longitude: Union[Annotated[
        Decimal,
        Field(ge=-180, le=180, description="Longitude for location-based search")
    ], None] = None
    radius_km: Union[Annotated[
        Decimal,
        Field(ge=0.1, le=50, description="Search radius in kilometers")
    ], None] = None

    # Text search
    search: Union[str, None] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="Search query across name, description, location"
    )

    # Price filters
    min_price: Union[Annotated[
        Decimal,
        Field(ge=0, description="Minimum monthly price")
    ], None] = None
    max_price: Union[Annotated[
        Decimal,
        Field(ge=0, description="Maximum monthly price")
    ], None] = None

    # Hostel characteristics
    room_type: Union[str, None] = Field(
        default=None,
        description="Preferred room type (single, double, shared, etc.)"
    )
    gender: Union[str, None] = Field(
        default=None,
        pattern=r"^(male|female|co-ed)$",
        description="Gender preference (male/female/co-ed)"
    )
    hostel_type: Union[HostelType, None] = Field(
        default=None,
        description="Filter by hostel type"
    )

    # Amenities and features
    amenities: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Required amenities (all must be present)"
    )
    has_wifi: Union[bool, None] = Field(
        default=None,
        description="Must have WiFi"
    )
    has_ac: Union[bool, None] = Field(
        default=None,
        description="Must have AC"
    )
    has_parking: Union[bool, None] = Field(
        default=None,
        description="Must have parking"
    )
    has_laundry: Union[bool, None] = Field(
        default=None,
        description="Must have laundry"
    )
    has_gym: Union[bool, None] = Field(
        default=None,
        description="Must have gym"
    )
    has_mess: Union[bool, None] = Field(
        default=None,
        description="Must have mess/canteen"
    )

    # Quality filters
    min_rating: Union[Annotated[
        Decimal,
        Field(ge=0, le=5, description="Minimum average rating")
    ], None] = None
    min_reviews: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Minimum number of reviews"
    )

    # Availability
    available_beds_min: Union[int, None] = Field(
        default=None,
        ge=1,
        description="Minimum available beds required"
    )
    verified_only: bool = Field(
        default=False,
        description="Show only verified hostels"
    )
    featured_only: bool = Field(
        default=False,
        description="Show only featured hostels"
    )

    # Sorting and pagination
    sort_by: str = Field(
        default="featured",
        pattern=r"^(featured|price_low|price_high|rating|newest|closest|popular)$",
        description="Sort order preference"
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed)"
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Results per page"
    )

    @field_validator("amenities")
    @classmethod
    def validate_amenities(cls, v: List[str]) -> List[str]:
        """Clean and validate amenities list."""
        if not v:
            return []
        # Remove duplicates and empty strings
        cleaned = list(set(item.strip().lower() for item in v if item.strip()))
        return cleaned[:10]  # Limit to 10 amenities

    @model_validator(mode="after")
    def validate_search_params(self):
        """Validate search parameters consistency."""
        # Validate price range
        if (self.min_price is not None and 
            self.max_price is not None and 
            self.min_price > self.max_price):
            raise ValueError("min_price must be less than or equal to max_price")
        
        # Validate location search - if one geo param provided, all should be provided
        geo_params = [self.latitude, self.longitude, self.radius_km]
        geo_provided = sum(1 for p in geo_params if p is not None)
        
        if geo_provided > 0 and geo_provided < 3:
            raise ValueError(
                "For location-based search, latitude, longitude, and radius_km are all required"
            )
        
        return self


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