# --- File: app/schemas/visitor/visitor_favorites.py ---
"""
Visitor favorites/wishlist schemas.

This module defines schemas for managing visitor's favorite hostels,
including adding, removing, updating notes, and comparing favorites.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "FavoriteRequest",
    "FavoritesList",
    "FavoriteHostelItem",
    "FavoriteUpdate",
    "FavoritesExport",
    "FavoriteComparison",
]


class FavoriteRequest(BaseCreateSchema):
    """
    Request to add or remove hostel from favorites.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel ID to add/remove from favorites",
    )
    is_favorite: bool = Field(
        ...,
        description="True to add to favorites, False to remove",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional personal notes about this hostel",
    )

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: Optional[str]) -> Optional[str]:
        """Validate and clean notes."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
            if len(v) > 500:
                raise ValueError("Notes must not exceed 500 characters")
        return v


class FavoriteHostelItem(BaseSchema):
    """
    Individual favorite hostel with detailed information.
    
    Contains hostel details, pricing tracking, availability,
    rating information, and favorite metadata.
    """

    favorite_id: UUID = Field(
        ...,
        description="Unique favorite record identifier",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )
    hostel_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Hostel name",
    )
    hostel_slug: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="URL-friendly hostel slug",
    )
    hostel_city: str = Field(
        ...,
        description="City where hostel is located",
    )
    hostel_type: str = Field(
        ...,
        description="Hostel type (boys/girls/co-ed)",
    )

    # Pricing Information - Updated for Pydantic v2
    starting_price_monthly: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Current starting price per month",
    )
    price_when_saved: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Price when hostel was saved",
    )
    current_price: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Field(
        ...,
        description="Current price",
    )
    has_price_drop: bool = Field(
        ...,
        description="Whether price has dropped since saving",
    )
    price_drop_percentage: Optional[Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)]] = Field(
        default=None,
        description="Price drop percentage if applicable",
    )

    # Availability
    available_beds: int = Field(
        ...,
        ge=0,
        description="Number of available beds",
    )
    has_availability: bool = Field(
        ...,
        description="Whether hostel has available beds",
    )

    # Rating Information
    average_rating: Annotated[Decimal, Field(ge=0, le=5, decimal_places=2)] = Field(
        ...,
        description="Average rating (0-5)",
    )
    total_reviews: int = Field(
        ...,
        ge=0,
        description="Total number of reviews",
    )

    # Media
    cover_image_url: Optional[str] = Field(
        default=None,
        description="Cover image URL",
    )

    # Favorite Metadata
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Personal notes about this hostel",
    )
    added_to_favorites: datetime = Field(
        ...,
        description="When hostel was added to favorites",
    )

    # View Tracking
    times_viewed: int = Field(
        ...,
        ge=0,
        description="Number of times hostel was viewed",
    )
    last_viewed: Optional[datetime] = Field(
        default=None,
        description="When hostel was last viewed",
    )

    @computed_field
    @property
    def price_savings(self) -> Optional[Decimal]:
        """Calculate price savings if price dropped."""
        if self.has_price_drop:
            return (self.price_when_saved - self.current_price).quantize(
                Decimal("0.01")
            )
        return None

    @computed_field
    @property
    def days_in_favorites(self) -> int:
        """Calculate days since hostel was added to favorites."""
        return (datetime.utcnow() - self.added_to_favorites).days

    @computed_field
    @property
    def is_highly_rated(self) -> bool:
        """Check if hostel is highly rated (>= 4.0 stars)."""
        return self.average_rating >= Decimal("4.0")

    @computed_field
    @property
    def is_popular(self) -> bool:
        """Check if hostel is popular (many reviews)."""
        return self.total_reviews >= 50

    @computed_field
    @property
    def is_frequently_viewed(self) -> bool:
        """Check if visitor views this hostel frequently."""
        return self.times_viewed >= 3


class FavoritesList(BaseSchema):
    """
    List of favorite hostels with summary statistics.
    """

    visitor_id: UUID = Field(
        ...,
        description="Visitor identifier",
    )
    total_favorites: int = Field(
        ...,
        ge=0,
        description="Total number of favorite hostels",
    )
    favorites: List[FavoriteHostelItem] = Field(
        default_factory=list,
        description="List of favorite hostel items",
    )

    @computed_field
    @property
    def favorites_with_availability(self) -> int:
        """Count favorites with available beds."""
        return sum(1 for fav in self.favorites if fav.has_availability)

    @computed_field
    @property
    def favorites_with_price_drops(self) -> int:
        """Count favorites with price drops."""
        return sum(1 for fav in self.favorites if fav.has_price_drop)

    @computed_field
    @property
    def total_potential_savings(self) -> Decimal:
        """Calculate total potential savings from price drops."""
        total = Decimal("0")
        for fav in self.favorites:
            if fav.price_savings:
                total += fav.price_savings
        return total.quantize(Decimal("0.01"))


class FavoriteUpdate(BaseCreateSchema):
    """
    Update notes for a favorite hostel.
    """

    favorite_id: UUID = Field(
        ...,
        description="Favorite record identifier",
    )
    notes: str = Field(
        ...,
        max_length=500,
        description="Updated personal notes",
    )

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: str) -> str:
        """Validate and clean notes."""
        v = v.strip()
        if len(v) > 500:
            raise ValueError("Notes must not exceed 500 characters")
        return v


class FavoritesExport(BaseSchema):
    """
    Export favorites list in various formats.
    """

    format: str = Field(
        default="pdf",
        pattern=r"^(pdf|csv|json)$",
        description="Export format: pdf, csv, or json",
    )
    include_prices: bool = Field(
        default=True,
        description="Include pricing information in export",
    )
    include_notes: bool = Field(
        default=True,
        description="Include personal notes in export",
    )

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate and normalize format."""
        v = v.lower().strip()
        if v not in ["pdf", "csv", "json"]:
            raise ValueError("Format must be one of: pdf, csv, json")
        return v


class FavoriteComparison(BaseSchema):
    """
    Compare multiple favorite hostels side-by-side.
    """

    favorite_ids: List[UUID] = Field(
        ...,
        min_length=2,
        max_length=4,
        description="2-4 favorite hostel IDs to compare",
    )

    @field_validator("favorite_ids")
    @classmethod
    def validate_favorite_ids(cls, v: List[UUID]) -> List[UUID]:
        """Validate favorite IDs list."""
        if len(v) < 2:
            raise ValueError("At least 2 favorites required for comparison")
        if len(v) > 4:
            raise ValueError("Maximum 4 favorites can be compared at once")

        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for fav_id in v:
            if fav_id not in seen:
                seen.add(fav_id)
                unique_ids.append(fav_id)

        if len(unique_ids) < 2:
            raise ValueError(
                "At least 2 unique favorites required for comparison"
            )

        return unique_ids