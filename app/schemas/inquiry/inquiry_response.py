"""
Inquiry response schemas for API responses.

This module defines response schemas for inquiry data including
basic responses, detailed information, and list items.
"""

from datetime import date as Date, datetime
from typing import Dict, Union
from uuid import UUID

from pydantic import ConfigDict, Field, computed_field

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import InquirySource, InquiryStatus, RoomType

__all__ = [
    "InquiryResponse",
    "InquiryDetail",
    "InquiryListItem",
    "InquiryStats",
]


class InquiryResponse(BaseResponseSchema):
    """
    Standard inquiry response schema.
    
    Contains core inquiry information for API responses.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "hostel_id": "123e4567-e89b-12d3-a456-426614174001",
                "hostel_name": "North Campus Hostel A",
                "visitor_name": "John Smith",
                "visitor_email": "john.smith@example.com",
                "visitor_phone": "+919876543210",
                "preferred_check_in_date": "2024-03-01",
                "stay_duration_months": 6,
                "room_type_preference": "single",
                "status": "new",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    )

    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Name of the hostel",
    )

    # Visitor Information
    visitor_name: str = Field(
        ...,
        description="Visitor full name",
    )
    visitor_email: str = Field(
        ...,
        description="Visitor email",
    )
    visitor_phone: str = Field(
        ...,
        description="Visitor phone",
    )

    # Preferences
    preferred_check_in_date: Union[Date, None] = Field(
        default=None,
        description="Preferred check-in Date",
    )
    stay_duration_months: Union[int, None] = Field(
        default=None,
        description="Intended stay duration",
    )
    room_type_preference: Union[RoomType, None] = Field(
        default=None,
        description="Room type preference",
    )

    # Status
    status: InquiryStatus = Field(
        ...,
        description="Current inquiry status",
    )

    created_at: datetime = Field(
        ...,
        description="When inquiry was created",
    )

    @computed_field  # type: ignore[misc]
    @property
    def age_days(self) -> int:
        """Calculate age of inquiry in days."""
        return (datetime.utcnow() - self.created_at).days

    @computed_field  # type: ignore[misc]
    @property
    def is_new(self) -> bool:
        """Check if inquiry is new (less than 24 hours old)."""
        return self.age_days < 1

    @computed_field  # type: ignore[misc]
    @property
    def is_stale(self) -> bool:
        """Check if inquiry is stale (older than 7 days without contact)."""
        return self.age_days > 7 and self.status == InquiryStatus.NEW

    @computed_field  # type: ignore[misc]
    @property
    def urgency_level(self) -> str:
        """
        Determine urgency level.
        
        Returns: "high", "medium", or "low"
        """
        if self.status == InquiryStatus.NEW and self.age_days < 1:
            return "high"
        elif self.status == InquiryStatus.NEW and self.age_days < 3:
            return "medium"
        else:
            return "low"


class InquiryDetail(BaseResponseSchema):
    """
    Detailed inquiry information.
    
    Contains complete inquiry details including contact history,
    notes, and assignment information.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "hostel_id": "123e4567-e89b-12d3-a456-426614174001",
                "hostel_name": "North Campus Hostel A",
                "visitor_name": "John Smith",
                "visitor_email": "john.smith@example.com",
                "visitor_phone": "+919876543210",
                "preferred_check_in_date": "2024-03-01",
                "stay_duration_months": 6,
                "message": "I am interested in a single room.",
                "inquiry_source": "website",
                "status": "contacted",
                "contacted_by_name": "Admin User",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    )

    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )

    # Visitor Information
    visitor_name: str = Field(
        ...,
        description="Visitor name",
    )
    visitor_email: str = Field(
        ...,
        description="Visitor email",
    )
    visitor_phone: str = Field(
        ...,
        description="Visitor phone",
    )

    # Preferences
    preferred_check_in_date: Union[Date, None] = Field(
        default=None,
        description="Preferred check-in Date",
    )
    stay_duration_months: Union[int, None] = Field(
        default=None,
        description="Stay duration in months",
    )
    room_type_preference: Union[RoomType, None] = Field(
        default=None,
        description="Room type preference",
    )

    # Inquiry Details
    message: Union[str, None] = Field(
        default=None,
        description="Visitor's message or questions",
    )

    # Metadata
    inquiry_source: InquirySource = Field(
        ...,
        description="Source of the inquiry",
    )
    status: InquiryStatus = Field(
        ...,
        description="Current status",
    )

    # Contact/Follow-up Information
    contacted_by: Union[UUID, None] = Field(
        default=None,
        description="Admin who contacted the visitor",
    )
    contacted_by_name: Union[str, None] = Field(
        default=None,
        description="Name of admin who made contact",
    )
    contacted_at: Union[datetime, None] = Field(
        default=None,
        description="When visitor was contacted",
    )

    # Assignment Information
    assigned_to: Union[UUID, None] = Field(
        default=None,
        description="Admin assigned to handle this inquiry",
    )
    assigned_to_name: Union[str, None] = Field(
        default=None,
        description="Name of assigned admin",
    )
    assigned_at: Union[datetime, None] = Field(
        default=None,
        description="When inquiry was assigned",
    )

    # Internal Notes
    notes: Union[str, None] = Field(
        default=None,
        description="Internal notes about this inquiry",
    )

    # Timestamps
    created_at: datetime = Field(
        ...,
        description="Creation timestamp",
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp",
    )

    @computed_field  # type: ignore[misc]
    @property
    def age_days(self) -> int:
        """Calculate inquiry age in days."""
        return (datetime.utcnow() - self.created_at).days

    @computed_field  # type: ignore[misc]
    @property
    def has_been_contacted(self) -> bool:
        """Check if visitor has been contacted."""
        return self.contacted_at is not None

    @computed_field  # type: ignore[misc]
    @property
    def is_assigned(self) -> bool:
        """Check if inquiry has been assigned to someone."""
        return self.assigned_to is not None

    @computed_field  # type: ignore[misc]
    @property
    def response_time_hours(self) -> Union[float, None]:
        """Calculate response time in hours if contacted."""
        if self.contacted_at is None:
            return None
        
        delta = self.contacted_at - self.created_at
        return round(delta.total_seconds() / 3600, 2)

    @computed_field  # type: ignore[misc]
    @property
    def days_since_contact(self) -> Union[int, None]:
        """Calculate days since last contact."""
        if self.contacted_at is None:
            return None
        
        return (datetime.utcnow() - self.contacted_at).days


class InquiryListItem(BaseSchema):
    """
    Inquiry list item for summary views.
    
    Optimized schema for displaying multiple inquiries
    with essential information only.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "hostel_name": "North Campus Hostel A",
                "visitor_name": "John Smith",
                "visitor_phone": "+919876543210",
                "preferred_check_in_date": "2024-03-01",
                "status": "new",
                "created_at": "2024-01-15T10:30:00Z",
                "is_urgent": True,
                "is_assigned": False
            }
        }
    )

    id: UUID = Field(
        ...,
        description="Inquiry ID",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    visitor_name: str = Field(
        ...,
        description="Visitor name",
    )
    visitor_phone: str = Field(
        ...,
        description="Visitor phone",
    )

    # Preferences
    preferred_check_in_date: Union[Date, None] = Field(
        default=None,
        description="Preferred check-in Date",
    )
    stay_duration_months: Union[int, None] = Field(
        default=None,
        description="Stay duration",
    )
    room_type_preference: Union[RoomType, None] = Field(
        default=None,
        description="Room type preference",
    )

    # Status and Timing
    status: InquiryStatus = Field(
        ...,
        description="Current status",
    )
    created_at: datetime = Field(
        ...,
        description="Creation timestamp",
    )

    # Quick Indicators
    is_urgent: bool = Field(
        ...,
        description="Whether inquiry requires urgent attention",
    )
    is_assigned: bool = Field(
        ...,
        description="Whether inquiry is assigned to someone",
    )

    @computed_field  # type: ignore[misc]
    @property
    def age_days(self) -> int:
        """Calculate inquiry age."""
        return (datetime.utcnow() - self.created_at).days

    @computed_field  # type: ignore[misc]
    @property
    def status_badge_color(self) -> str:
        """Get color code for status badge."""
        color_map = {
            InquiryStatus.NEW: "#FFA500",  # Orange
            InquiryStatus.CONTACTED: "#2196F3",  # Blue
            InquiryStatus.INTERESTED: "#4CAF50",  # Green
            InquiryStatus.NOT_INTERESTED: "#9E9E9E",  # Gray
            InquiryStatus.CONVERTED: "#9C27B0",  # Purple
        }
        return color_map.get(self.status, "#000000")


class InquiryStats(BaseSchema):
    """
    Inquiry statistics and analytics.
    
    Provides metrics about inquiry performance and conversion.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "total_inquiries": 150,
                "new_inquiries": 25,
                "contacted_inquiries": 100,
                "converted_inquiries": 50,
                "average_response_time_hours": 4.5,
                "conversion_rate": 50.0,
                "interest_rate": 75.0,
                "inquiries_by_source": {
                    "website": 80,
                    "phone": 40,
                    "walkin": 30
                }
            }
        }
    )

    # Volume Metrics
    total_inquiries: int = Field(
        ...,
        ge=0,
        description="Total number of inquiries",
    )
    new_inquiries: int = Field(
        ...,
        ge=0,
        description="Inquiries with NEW status",
    )
    contacted_inquiries: int = Field(
        ...,
        ge=0,
        description="Inquiries that have been contacted",
    )
    converted_inquiries: int = Field(
        ...,
        ge=0,
        description="Inquiries converted to bookings",
    )

    # Response Metrics
    average_response_time_hours: Union[float, None] = Field(
        default=None,
        ge=0,
        description="Average time to first contact in hours",
    )
    
    # Conversion Metrics
    conversion_rate: float = Field(
        ...,
        ge=0,
        le=100,
        description="Inquiry to booking conversion rate (%)",
    )
    interest_rate: float = Field(
        ...,
        ge=0,
        le=100,
        description="Percentage of inquiries showing interest",
    )

    # Source Breakdown
    inquiries_by_source: Dict[str, int] = Field(
        default_factory=dict,
        description="Breakdown of inquiries by source",
    )

    @computed_field  # type: ignore[misc]
    @property
    def pending_action_count(self) -> int:
        """Count inquiries needing action (NEW + CONTACTED)."""
        return self.new_inquiries + self.contacted_inquiries

    @computed_field  # type: ignore[misc]
    @property
    def response_rate(self) -> float:
        """Calculate percentage of inquiries that were contacted."""
        if self.total_inquiries == 0:
            return 0.0
        return round((self.contacted_inquiries / self.total_inquiries) * 100, 2)