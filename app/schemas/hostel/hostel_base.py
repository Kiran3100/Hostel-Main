# --- File: app/schemas/hostel/hostel_base.py ---
"""
Hostel base schemas with enhanced validation and type safety.
"""

from datetime import time
from decimal import Decimal
from typing import Annotated, Dict, List, Union

from pydantic import ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.schemas.common.base import (
    BaseCreateSchema,
    BaseSchema,
    BaseUpdateSchema,
)
from app.schemas.common.enums import HostelStatus, HostelType
from app.schemas.common.mixins import AddressMixin, ContactMixin, LocationMixin

__all__ = [
    "HostelBase",
    "HostelCreate",
    "HostelUpdate",
    "HostelMediaUpdate",
    "HostelSEOUpdate",
]


class HostelBase(BaseSchema, AddressMixin, ContactMixin, LocationMixin):
    """
    Base hostel schema with common fields.
    
    Combines address, contact, and location information with hostel-specific fields.
    """
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Hostel name",
        examples=["Green Valley Hostel"],
    )
    slug: str = Field(
        ...,
        min_length=3,
        max_length=255,
        pattern=r"^[a-z0-9-]+$",
        description="URL-friendly slug (lowercase, alphanumeric, hyphens only)",
        examples=["green-valley-hostel"],
    )
    description: Union[str, None] = Field(
        default=None,
        max_length=2000,
        description="Detailed hostel description",
    )

    # Type
    hostel_type: HostelType = Field(
        ...,
        description="Hostel type (boys/girls/co-ed)",
    )

    # Website
    website_url: Union[HttpUrl, None] = Field(
        default=None,
        description="Hostel official website URL",
    )

    # Pricing - Using Annotated for Decimal constraints
    starting_price_monthly: Union[Annotated[
        Decimal,
        Field(ge=0, description="Starting monthly price (lowest room type)")
    ], None] = None
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="Currency code (ISO 4217)",
        examples=["INR", "USD"],
    )

    # Amenities and facilities
    amenities: List[str] = Field(
        default_factory=list,
        description="List of amenities (WiFi, AC, etc.)",
        examples=[["WiFi", "AC", "Laundry", "Hot Water"]],
    )
    facilities: List[str] = Field(
        default_factory=list,
        description="List of facilities (Gym, Library, etc.)",
        examples=[["Gym", "Library", "Common Room"]],
    )
    security_features: List[str] = Field(
        default_factory=list,
        description="Security features (CCTV, Guards, etc.)",
        examples=[["CCTV", "24/7 Security", "Biometric Access"]],
    )

    # Policies
    rules: Union[str, None] = Field(
        default=None,
        max_length=5000,
        description="Hostel rules and regulations",
    )
    check_in_time: Union[time, None] = Field(
        default=None,
        description="Standard check-in time",
        examples=["10:00:00"],
    )
    check_out_time: Union[time, None] = Field(
        default=None,
        description="Standard check-out time",
        examples=["11:00:00"],
    )
    visitor_policy: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Visitor policy details",
    )
    late_entry_policy: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Late entry policy and timings",
    )

    # Location info
    nearby_landmarks: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Nearby landmarks with name, type, and distance",
        examples=[[{"name": "Metro Station", "type": "transport", "distance": "500m"}]],
    )
    connectivity_info: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Public transport and connectivity information",
    )

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """
        Validate and normalize slug format.
        
        Ensures slug contains only lowercase letters, numbers, and hyphens.
        """
        v = v.lower().strip()
        if not v.replace("-", "").isalnum():
            raise ValueError(
                "Slug can only contain lowercase letters, numbers, and hyphens"
            )
        # Remove consecutive hyphens
        while "--" in v:
            v = v.replace("--", "-")
        # Remove leading/trailing hyphens
        v = v.strip("-")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and normalize hostel name."""
        v = v.strip()
        # Remove excessive whitespace
        v = " ".join(v.split())
        if v.isdigit():
            raise ValueError("Hostel name cannot be only numbers")
        return v

    @field_validator("amenities", "facilities", "security_features")
    @classmethod
    def validate_and_clean_lists(cls, v: List[str]) -> List[str]:
        """
        Validate and clean list fields.
        
        Removes empty strings, duplicates, and normalizes values.
        """
        if not v:
            return []
        # Clean and normalize
        cleaned = [item.strip() for item in v if item and item.strip()]
        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for item in cleaned:
            item_lower = item.lower()
            if item_lower not in seen:
                seen.add(item_lower)
                unique.append(item)
        return unique

    @field_validator("nearby_landmarks")
    @classmethod
    def validate_landmarks(cls, v: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Validate nearby landmarks structure."""
        if not v:
            return []
        validated = []
        for landmark in v:
            if not isinstance(landmark, dict):
                continue
            if "name" in landmark and landmark["name"].strip():
                validated.append({
                    "name": landmark.get("name", "").strip(),
                    "type": landmark.get("type", "other").strip(),
                    "distance": landmark.get("distance", "").strip(),
                })
        return validated

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Normalize currency code to uppercase."""
        return v.upper().strip()

    @model_validator(mode="after")
    def validate_check_times(self):
        """Validate check-in and check-out times."""
        if (
            self.check_in_time is not None
            and self.check_out_time is not None
            and self.check_in_time >= self.check_out_time
        ):
            raise ValueError("Check-in time must be before check-out time")
        return self


class HostelCreate(HostelBase, BaseCreateSchema):
    """
    Schema for creating a hostel.
    
    Enforces required fields for hostel creation.
    """
    model_config = ConfigDict(from_attributes=True)

    # Override to enforce requirements
    name: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Hostel name (required)",
    )
    hostel_type: HostelType = Field(
        ...,
        description="Hostel type (required)",
    )
    contact_phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Primary contact phone (required)",
    )
    address_line1: str = Field(
        ...,
        min_length=5,
        max_length=255,
        description="Address line 1 (required)",
    )
    city: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="City (required)",
    )
    state: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="State (required)",
    )
    pincode: str = Field(
        ...,
        pattern=r"^\d{6}$",
        description="6-digit pincode (required)",
    )


class HostelUpdate(BaseUpdateSchema):
    """
    Schema for updating hostel information.
    
    All fields are optional for partial updates.
    """
    model_config = ConfigDict(from_attributes=True)

    # Basic info
    name: Union[str, None] = Field(
        default=None,
        min_length=3,
        max_length=255,
        description="Hostel name",
    )
    slug: Union[str, None] = Field(
        default=None,
        min_length=3,
        max_length=255,
        pattern=r"^[a-z0-9-]+$",
        description="URL slug",
    )
    description: Union[str, None] = Field(
        default=None,
        max_length=2000,
        description="Description",
    )
    hostel_type: Union[HostelType, None] = Field(
        default=None,
        description="Hostel type",
    )

    # Address fields
    address_line1: Union[str, None] = Field(
        default=None,
        min_length=5,
        max_length=255,
        description="Address line 1",
    )
    address_line2: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Address line 2",
    )
    city: Union[str, None] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="City",
    )
    state: Union[str, None] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="State",
    )
    pincode: Union[str, None] = Field(
        default=None,
        pattern=r"^\d{6}$",
        description="Pincode",
    )
    country: Union[str, None] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="Country",
    )

    # Contact
    contact_phone: Union[str, None] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Contact phone",
    )
    alternate_phone: Union[str, None] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Alternate phone",
    )
    contact_email: Union[str, None] = Field(
        default=None,
        description="Contact email",
    )
    website_url: Union[HttpUrl, None] = Field(
        default=None,
        description="Website URL",
    )

    # Location - Using Annotated for Decimal constraints
    latitude: Union[Annotated[
        Decimal,
        Field(ge=-90, le=90, description="Latitude")
    ], None] = None
    longitude: Union[Annotated[
        Decimal,
        Field(ge=-180, le=180, description="Longitude")
    ], None] = None

    # Pricing
    starting_price_monthly: Union[Annotated[
        Decimal,
        Field(ge=0, description="Starting monthly price")
    ], None] = None
    currency: Union[str, None] = Field(
        default=None,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
        description="Currency code",
    )

    # Lists
    amenities: Union[List[str], None] = Field(
        default=None,
        description="Amenities list",
    )
    facilities: Union[List[str], None] = Field(
        default=None,
        description="Facilities list",
    )
    security_features: Union[List[str], None] = Field(
        default=None,
        description="Security features list",
    )

    # Policies
    rules: Union[str, None] = Field(
        default=None,
        max_length=5000,
        description="Rules and regulations",
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
        max_length=1000,
        description="Visitor policy",
    )
    late_entry_policy: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Late entry policy",
    )

    # Location info
    nearby_landmarks: Union[List[Dict[str, str]], None] = Field(
        default=None,
        description="Nearby landmarks",
    )
    connectivity_info: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Connectivity info",
    )

    # Media
    cover_image_url: Union[str, None] = Field(
        default=None,
        description="Cover image URL",
    )
    gallery_images: Union[List[str], None] = Field(
        default=None,
        description="Gallery image URLs",
    )
    virtual_tour_url: Union[HttpUrl, None] = Field(
        default=None,
        description="Virtual tour URL",
    )

    # Status
    status: Union[HostelStatus, None] = Field(
        default=None,
        description="Operational status",
    )
    is_active: Union[bool, None] = Field(
        default=None,
        description="Active status",
    )

    # Apply same validators as base
    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: Union[str, None]) -> Union[str, None]:
        if v is not None:
            return HostelBase.validate_slug(v)
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Union[str, None]) -> Union[str, None]:
        if v is not None:
            return HostelBase.validate_name(v)
        return v

    @field_validator("amenities", "facilities", "security_features")
    @classmethod
    def validate_lists(cls, v: Union[List[str], None]) -> Union[List[str], None]:
        if v is not None:
            return HostelBase.validate_and_clean_lists(v)
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: Union[str, None]) -> Union[str, None]:
        if v is not None:
            return HostelBase.validate_currency(v)
        return v

    @field_validator("contact_phone", "alternate_phone")
    @classmethod
    def normalize_phone(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize phone numbers."""
        if v is not None:
            return v.replace(" ", "").replace("-", "").strip()
        return v


class HostelMediaUpdate(BaseUpdateSchema):
    """
    Update hostel media (images, videos, virtual tours).
    
    Manages hostel visual content.
    """
    model_config = ConfigDict(from_attributes=True)

    cover_image_url: Union[str, None] = Field(
        default=None,
        description="Cover/main image URL",
    )
    gallery_images: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Gallery image URLs (max 20)",
    )
    virtual_tour_url: Union[HttpUrl, None] = Field(
        default=None,
        description="360° virtual tour URL",
    )
    video_urls: Union[List[HttpUrl], None] = Field(
        default=None,
        max_length=5,
        description="Video URLs (max 5)",
    )

    @field_validator("gallery_images")
    @classmethod
    def validate_gallery_images(cls, v: List[str]) -> List[str]:
        """Validate gallery images."""
        if not v:
            return []
        # Remove empty strings and duplicates
        cleaned = [img.strip() for img in v if img and img.strip()]
        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for img in cleaned:
            if img not in seen:
                seen.add(img)
                unique.append(img)
        return unique[:20]  # Limit to 20


class HostelSEOUpdate(BaseUpdateSchema):
    """
    Update hostel SEO metadata.
    
    Manages search engine optimization fields.
    """
    model_config = ConfigDict(from_attributes=True)

    meta_title: Union[str, None] = Field(
        default=None,
        min_length=10,
        max_length=60,
        description="SEO meta title (optimal: 50-60 chars)",
    )
    meta_description: Union[str, None] = Field(
        default=None,
        min_length=50,
        max_length=160,
        description="SEO meta description (optimal: 150-160 chars)",
    )
    meta_keywords: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="SEO keywords (comma-separated)",
    )
    og_title: Union[str, None] = Field(
        default=None,
        max_length=95,
        description="Open Graph title",
    )
    og_description: Union[str, None] = Field(
        default=None,
        max_length=200,
        description="Open Graph description",
    )
    og_image_url: Union[HttpUrl, None] = Field(
        default=None,
        description="Open Graph image URL",
    )

    @field_validator("meta_keywords")
    @classmethod
    def validate_keywords(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate and clean meta keywords."""
        if v is None:
            return v
        # Split, clean, and rejoin
        keywords = [kw.strip() for kw in v.split(",") if kw.strip()]
        # Limit to 10 keywords
        return ", ".join(keywords[:10])