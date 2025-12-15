# --- File: app/schemas/visitor/visitor_response.py ---
"""
Visitor response schemas for API responses.

This module defines response schemas for visitor data returned by API endpoints,
including profile information, statistics, and detailed visitor information.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import RoomType

__all__ = [
    "VisitorResponse",
    "VisitorProfile",
    "VisitorDetail",
    "VisitorStats",
]


class VisitorResponse(BaseResponseSchema):
    """
    Standard visitor response schema.
    
    Used for basic visitor information in API responses.
    Contains core profile data and preferences.
    """

    user_id: UUID = Field(
        ...,
        description="Associated user account ID",
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Full name of the visitor",
    )
    email: str = Field(
        ...,
        description="Email address",
    )
    phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Contact phone number",
    )

    # Preferences - Updated for Pydantic v2
    preferred_room_type: Optional[RoomType] = Field(
        default=None,
        description="Preferred room type",
    )
    budget_min: Optional[Annotated[Decimal, Field(ge=0)]] = Field(
        default=None,
        description="Minimum budget per month",
    )
    budget_max: Optional[Annotated[Decimal, Field(ge=0)]] = Field(
        default=None,
        description="Maximum budget per month",
    )
    preferred_cities: List[str] = Field(
        default_factory=list,
        description="Preferred cities for hostel search",
    )

    # Statistics
    total_bookings: int = Field(
        default=0,
        ge=0,
        description="Total number of bookings made by visitor",
    )
    saved_hostels_count: int = Field(
        default=0,
        ge=0,
        description="Number of hostels saved to favorites",
    )

    # Notification Preferences
    email_notifications: bool = Field(
        ...,
        description="Email notifications enabled",
    )
    sms_notifications: bool = Field(
        ...,
        description="SMS notifications enabled",
    )
    push_notifications: bool = Field(
        ...,
        description="Push notifications enabled",
    )

    @computed_field
    @property
    def has_active_notifications(self) -> bool:
        """Check if visitor has any notification channel enabled."""
        return (
            self.email_notifications
            or self.sms_notifications
            or self.push_notifications
        )

    @computed_field
    @property
    def budget_range_display(self) -> Optional[str]:
        """Get formatted budget range for display."""
        if self.budget_min is not None and self.budget_max is not None:
            return f"₹{self.budget_min:,.0f} - ₹{self.budget_max:,.0f}"
        elif self.budget_min is not None:
            return f"₹{self.budget_min:,.0f}+"
        elif self.budget_max is not None:
            return f"Up to ₹{self.budget_max:,.0f}"
        return None


class VisitorProfile(BaseSchema):
    """
    Public visitor profile information.
    
    Contains minimal visitor information suitable for public display
    (e.g., in reviews, comments, etc.).
    """

    id: UUID = Field(
        ...,
        description="Visitor profile ID",
    )
    user_id: UUID = Field(
        ...,
        description="Associated user ID",
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Full name of the visitor",
    )
    profile_image_url: Optional[str] = Field(
        default=None,
        description="URL to profile image",
    )
    member_since: datetime = Field(
        ...,
        description="Date when visitor joined the platform",
    )

    @computed_field
    @property
    def display_name(self) -> str:
        """Get display name (first name only for privacy)."""
        return self.full_name.split()[0] if self.full_name else "Guest"

    @computed_field
    @property
    def membership_days(self) -> int:
        """Calculate number of days since joining."""
        return (datetime.utcnow() - self.member_since).days


class VisitorDetail(BaseResponseSchema):
    """
    Detailed visitor information.
    
    Complete visitor profile with all preferences, activity statistics,
    and account information. Used for profile pages and detailed views.
    """

    # User Information
    user_id: UUID = Field(
        ...,
        description="Associated user account ID",
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Full name",
    )
    email: str = Field(
        ...,
        description="Email address",
    )
    phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Phone number",
    )
    profile_image_url: Optional[str] = Field(
        default=None,
        description="Profile image URL",
    )

    # Preferences - Updated for Pydantic v2
    preferred_room_type: Optional[RoomType] = Field(
        default=None,
        description="Preferred room type",
    )
    budget_min: Optional[Annotated[Decimal, Field(ge=0)]] = Field(
        default=None,
        description="Minimum budget",
    )
    budget_max: Optional[Annotated[Decimal, Field(ge=0)]] = Field(
        default=None,
        description="Maximum budget",
    )
    preferred_cities: List[str] = Field(
        default_factory=list,
        description="Preferred cities",
    )
    preferred_amenities: List[str] = Field(
        default_factory=list,
        description="Preferred amenities",
    )

    # Saved Hostels
    favorite_hostel_ids: List[UUID] = Field(
        default_factory=list,
        description="List of favorite hostel IDs",
    )
    total_saved_hostels: int = Field(
        default=0,
        ge=0,
        description="Total number of saved hostels",
    )

    # Activity Statistics
    total_bookings: int = Field(
        default=0,
        ge=0,
        description="Total bookings made",
    )
    completed_bookings: int = Field(
        default=0,
        ge=0,
        description="Number of completed bookings",
    )
    cancelled_bookings: int = Field(
        default=0,
        ge=0,
        description="Number of cancelled bookings",
    )
    total_inquiries: int = Field(
        default=0,
        ge=0,
        description="Total inquiries made",
    )

    # Review Activity
    total_reviews_written: int = Field(
        default=0,
        ge=0,
        description="Number of reviews written",
    )
    average_rating_given: Optional[Annotated[Decimal, Field(ge=0, le=5)]] = Field(
        default=None,
        description="Average rating given in reviews",
    )

    # Notification Preferences
    email_notifications: bool = Field(
        ...,
        description="Email notifications enabled",
    )
    sms_notifications: bool = Field(
        ...,
        description="SMS notifications enabled",
    )
    push_notifications: bool = Field(
        ...,
        description="Push notifications enabled",
    )

    # Account Information
    created_at: datetime = Field(
        ...,
        description="Account creation timestamp",
    )
    last_login: Optional[datetime] = Field(
        default=None,
        description="Last login timestamp",
    )

    @computed_field
    @property
    def active_bookings(self) -> int:
        """Calculate number of active bookings."""
        return self.total_bookings - self.completed_bookings - self.cancelled_bookings

    @computed_field
    @property
    def booking_completion_rate(self) -> Decimal:
        """Calculate booking completion rate as percentage."""
        if self.total_bookings == 0:
            return Decimal("0")
        return Decimal(
            (self.completed_bookings / self.total_bookings) * 100
        ).quantize(Decimal("0.01"))

    @computed_field
    @property
    def is_active_user(self) -> bool:
        """Determine if user is active (logged in within last 30 days)."""
        if self.last_login is None:
            return False
        days_since_login = (datetime.utcnow() - self.last_login).days
        return days_since_login <= 30

    @computed_field
    @property
    def engagement_score(self) -> Decimal:
        """
        Calculate engagement score (0-100) based on activity.
        
        Weighted formula:
        - Bookings: 40%
        - Reviews: 30%
        - Saved hostels: 20%
        - Inquiries: 10%
        """
        booking_score = min(self.total_bookings * 10, 40)
        review_score = min(self.total_reviews_written * 6, 30)
        saved_score = min(self.total_saved_hostels * 2, 20)
        inquiry_score = min(self.total_inquiries * 2, 10)

        total_score = booking_score + review_score + saved_score + inquiry_score
        return Decimal(total_score).quantize(Decimal("0.01"))


class VisitorStats(BaseSchema):
    """
    Visitor statistics and analytics.
    
    Comprehensive statistics about visitor search behavior,
    engagement, and conversion metrics.
    """

    visitor_id: UUID = Field(
        ...,
        description="Visitor profile ID",
    )

    # Search Activity
    total_searches: int = Field(
        default=0,
        ge=0,
        description="Total number of searches performed",
    )
    unique_hostels_viewed: int = Field(
        default=0,
        ge=0,
        description="Number of unique hostels viewed",
    )
    average_search_filters_used: Annotated[Decimal, Field(ge=0)] = Field(
        default=Decimal("0"),
        description="Average number of filters used per search",
    )

    # Engagement Metrics
    total_hostel_views: int = Field(
        default=0,
        ge=0,
        description="Total hostel detail page views",
    )
    total_comparisons: int = Field(
        default=0,
        ge=0,
        description="Number of hostel comparisons made",
    )
    total_inquiries: int = Field(
        default=0,
        ge=0,
        description="Total inquiries sent",
    )

    # Booking Metrics
    total_bookings: int = Field(
        default=0,
        ge=0,
        description="Total bookings made",
    )
    booking_conversion_rate: Annotated[Decimal, Field(ge=0, le=100)] = Field(
        default=Decimal("0"),
        description="Percentage of views that resulted in bookings",
    )

    # Preference Insights
    most_searched_city: Optional[str] = Field(
        default=None,
        description="City searched most frequently",
    )
    most_viewed_room_type: Optional[RoomType] = Field(
        default=None,
        description="Most frequently viewed room type",
    )
    average_budget: Optional[Annotated[Decimal, Field(ge=0)]] = Field(
        default=None,
        description="Average budget range from searches",
    )

    @computed_field
    @property
    def inquiry_conversion_rate(self) -> Decimal:
        """Calculate inquiry to booking conversion rate."""
        if self.total_inquiries == 0:
            return Decimal("0")
        return Decimal(
            (self.total_bookings / self.total_inquiries) * 100
        ).quantize(Decimal("0.01"))

    @computed_field
    @property
    def average_views_per_search(self) -> Decimal:
        """Calculate average hostel views per search."""
        if self.total_searches == 0:
            return Decimal("0")
        return Decimal(self.total_hostel_views / self.total_searches).quantize(
            Decimal("0.01")
        )

    @computed_field
    @property
    def engagement_level(self) -> str:
        """
        Categorize engagement level based on activity.
        
        Returns: "high", "medium", "low", or "inactive"
        """
        if self.total_searches == 0 and self.total_hostel_views == 0:
            return "inactive"
        elif self.total_bookings >= 3 or self.booking_conversion_rate >= 10:
            return "high"
        elif self.total_searches >= 5 or self.total_hostel_views >= 10:
            return "medium"
        else:
            return "low"