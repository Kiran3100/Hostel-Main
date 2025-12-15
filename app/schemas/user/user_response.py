# --- File: app/schemas/user/user_response.py ---
"""
User response schemas with comprehensive user information.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import Gender, UserRole

__all__ = [
    "UserResponse",
    "UserDetail",
    "UserListItem",
    "UserProfile",
    "UserStats",
]


class UserResponse(BaseResponseSchema):
    """
    Standard user response schema.
    
    Returns essential user information for general API responses.
    """

    email: str = Field(
        ...,
        description="Email address",
    )
    phone: str = Field(
        ...,
        description="Phone number",
    )
    full_name: str = Field(
        ...,
        description="Full name",
    )
    user_role: UserRole = Field(
        ...,
        description="User role",
    )
    is_active: bool = Field(
        ...,
        description="Account active status",
    )
    is_email_verified: bool = Field(
        ...,
        description="Email verification status",
    )
    is_phone_verified: bool = Field(
        ...,
        description="Phone verification status",
    )
    profile_image_url: Optional[str] = Field(
        default=None,
        description="Profile image URL",
    )
    last_login_at: Optional[datetime] = Field(
        default=None,
        description="Last login timestamp (UTC)",
    )


class UserDetail(BaseResponseSchema):
    """
    Detailed user information schema.
    
    Comprehensive user profile with all available information.
    """

    # Basic information
    email: str = Field(..., description="Email address")
    phone: str = Field(..., description="Phone number")
    full_name: str = Field(..., description="Full name")
    user_role: UserRole = Field(..., description="User role")
    gender: Optional[Gender] = Field(default=None, description="Gender")
    date_of_birth: Optional[Date] = Field(default=None, description="Date of birth")
    profile_image_url: Optional[str] = Field(
        default=None,
        description="Profile image URL",
    )

    # Address information
    address_line1: Optional[str] = Field(
        default=None,
        description="Address line 1",
    )
    address_line2: Optional[str] = Field(
        default=None,
        description="Address line 2",
    )
    city: Optional[str] = Field(default=None, description="City")
    state: Optional[str] = Field(default=None, description="State")
    country: Optional[str] = Field(default=None, description="Country")
    pincode: Optional[str] = Field(default=None, description="Pincode")

    # Emergency contact
    emergency_contact_name: Optional[str] = Field(
        default=None,
        description="Emergency contact name",
    )
    emergency_contact_phone: Optional[str] = Field(
        default=None,
        description="Emergency contact phone",
    )
    emergency_contact_relation: Optional[str] = Field(
        default=None,
        description="Relation to emergency contact",
    )

    # Account status
    is_active: bool = Field(..., description="Account active status")
    is_email_verified: bool = Field(..., description="Email verification status")
    is_phone_verified: bool = Field(..., description="Phone verification status")
    email_verified_at: Optional[datetime] = Field(
        default=None,
        description="Email verification timestamp",
    )
    phone_verified_at: Optional[datetime] = Field(
        default=None,
        description="Phone verification timestamp",
    )
    last_login_at: Optional[datetime] = Field(
        default=None,
        description="Last login timestamp",
    )
    last_password_change_at: Optional[datetime] = Field(
        default=None,
        description="Last password change timestamp",
    )


class UserListItem(BaseSchema):
    """
    User list item schema.
    
    Minimal user information for list views and search results.
    """

    id: UUID = Field(..., description="User ID")
    email: str = Field(..., description="Email address")
    full_name: str = Field(..., description="Full name")
    user_role: UserRole = Field(..., description="User role")
    is_active: bool = Field(..., description="Account active status")
    profile_image_url: Optional[str] = Field(
        default=None,
        description="Profile image URL",
    )
    created_at: datetime = Field(..., description="Registration date")
    last_login_at: Optional[datetime] = Field(
        default=None,
        description="Last login timestamp",
    )


class UserProfile(BaseSchema):
    """
    Public user profile schema.
    
    Limited information suitable for public display.
    """

    id: UUID = Field(..., description="User ID")
    full_name: str = Field(..., description="Full name")
    profile_image_url: Optional[str] = Field(
        default=None,
        description="Profile image URL",
    )
    user_role: UserRole = Field(..., description="User role")
    member_since: datetime = Field(
        ...,
        description="Member since (registration date)",
    )


class UserStats(BaseSchema):
    """
    User statistics schema.
    
    Aggregate statistics about user activity and engagement.
    """

    user_id: UUID = Field(..., description="User ID")
    total_bookings: int = Field(
        default=0,
        ge=0,
        description="Total number of bookings",
    )
    active_bookings: int = Field(
        default=0,
        ge=0,
        description="Number of active bookings",
    )
    completed_bookings: int = Field(
        default=0,
        ge=0,
        description="Number of completed bookings",
    )
    total_payments: int = Field(
        default=0,
        ge=0,
        description="Total number of payments",
    )
    # Note: Using float for monetary amounts - in v2, if this were Decimal,
    # it should be: Annotated[Decimal, Field(max_digits=10, decimal_places=2, ge=0)]
    total_amount_paid: float = Field(
        default=0.0,
        ge=0,
        description="Total amount paid (in currency)",
    )
    total_complaints: int = Field(
        default=0,
        ge=0,
        description="Total number of complaints raised",
    )
    resolved_complaints: int = Field(
        default=0,
        ge=0,
        description="Number of resolved complaints",
    )
    average_rating_given: Optional[float] = Field(
        default=None,
        ge=0,
        le=5,
        description="Average rating given to hostels",
    )
    account_age_days: int = Field(
        ...,
        ge=0,
        description="Account age in days",
    )
    last_activity_at: Optional[datetime] = Field(
        default=None,
        description="Last activity timestamp",
    )