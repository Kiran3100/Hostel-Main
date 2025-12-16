"""
Booking response schemas for API responses.

This module defines response schemas for booking data including
basic responses, detailed information, list items, and confirmations.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Union
from uuid import UUID

from pydantic import Field, computed_field

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import BookingSource, BookingStatus, RoomType

__all__ = [
    "BookingResponse",
    "BookingDetail",
    "BookingListItem",
    "BookingConfirmation",
]


class BookingResponse(BaseResponseSchema):
    """
    Standard booking response schema.
    
    Contains core booking information for API responses.
    """

    booking_reference: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Unique human-readable booking reference",
    )
    visitor_id: UUID = Field(
        ...,
        description="Visitor/guest identifier",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Name of the hostel",
    )

    # Booking Details
    room_type_requested: RoomType = Field(
        ...,
        description="Type of room requested",
    )
    preferred_check_in_date: Date = Field(
        ...,
        description="Preferred check-in Date",
    )
    stay_duration_months: int = Field(
        ...,
        ge=1,
        description="Stay duration in months",
    )
    expected_check_out_date: Date = Field(
        ...,
        description="Calculated expected check-out Date",
    )

    # Guest Information
    guest_name: str = Field(
        ...,
        description="Guest full name",
    )
    guest_email: str = Field(
        ...,
        description="Guest email address",
    )
    guest_phone: str = Field(
        ...,
        description="Guest contact phone",
    )

    # Pricing - decimal_places removed
    quoted_rent_monthly: Decimal = Field(
        ...,
        ge=0,
        description="Monthly rent amount (precision: 2 decimal places)",
    )
    total_amount: Decimal = Field(
        ...,
        ge=0,
        description="Total booking amount (precision: 2 decimal places)",
    )
    security_deposit: Decimal = Field(
        ...,
        ge=0,
        description="Security deposit amount (precision: 2 decimal places)",
    )
    advance_amount: Decimal = Field(
        ...,
        ge=0,
        description="Advance payment amount (precision: 2 decimal places)",
    )
    advance_paid: bool = Field(
        ...,
        description="Whether advance payment has been made",
    )

    # Status
    booking_status: BookingStatus = Field(
        ...,
        description="Current booking status",
    )

    # Timestamps
    booking_date: datetime = Field(
        ...,
        description="When booking was created",
    )
    expires_at: Union[datetime, None] = Field(
        None,
        description="When booking expires if not confirmed",
    )

    @computed_field
    @property
    def days_until_check_in(self) -> int:
        """Calculate days until check-in."""
        return (self.preferred_check_in_date - Date.today()).days

    @computed_field
    @property
    def is_expiring_soon(self) -> bool:
        """Check if booking is expiring within 24 hours."""
        if self.expires_at is None:
            return False
        return (self.expires_at - datetime.utcnow()).total_seconds() < 86400

    @computed_field
    @property
    def balance_amount(self) -> Decimal:
        """Calculate remaining balance after advance."""
        if self.advance_paid:
            return (self.total_amount - self.advance_amount).quantize(Decimal("0.01"))
        return self.total_amount


class BookingDetail(BaseResponseSchema):
    """
    Detailed booking information schema.
    
    Contains complete booking information including guest details,
    assignments, workflow status, and all related metadata.
    """

    booking_reference: str = Field(
        ...,
        description="Unique booking reference",
    )
    visitor_id: UUID = Field(
        ...,
        description="Visitor identifier",
    )
    visitor_name: str = Field(
        ...,
        description="Visitor/user name",
    )

    # Hostel Information
    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    hostel_city: str = Field(
        ...,
        description="Hostel city",
    )
    hostel_address: str = Field(
        ...,
        description="Hostel full address",
    )
    hostel_phone: str = Field(
        ...,
        description="Hostel contact phone",
    )

    # Booking Details
    room_type_requested: RoomType = Field(
        ...,
        description="Requested room type",
    )
    preferred_check_in_date: Date = Field(
        ...,
        description="Preferred check-in Date",
    )
    stay_duration_months: int = Field(
        ...,
        ge=1,
        description="Stay duration in months",
    )
    expected_check_out_date: Date = Field(
        ...,
        description="Expected check-out Date",
    )

    # Room Assignment (if approved)
    room_id: Union[UUID, None] = Field(
        None,
        description="Assigned room ID (if approved)",
    )
    room_number: Union[str, None] = Field(
        None,
        description="Assigned room number",
    )
    bed_id: Union[UUID, None] = Field(
        None,
        description="Assigned bed ID (if approved)",
    )
    bed_number: Union[str, None] = Field(
        None,
        description="Assigned bed number",
    )

    # Guest Information
    guest_name: str = Field(
        ...,
        description="Guest full name",
    )
    guest_email: str = Field(
        ...,
        description="Guest email",
    )
    guest_phone: str = Field(
        ...,
        description="Guest phone",
    )
    guest_id_proof_type: Union[str, None] = Field(
        None,
        description="ID proof type",
    )
    guest_id_proof_number: Union[str, None] = Field(
        None,
        description="ID proof number",
    )

    # Emergency Contact
    emergency_contact_name: Union[str, None] = Field(
        None,
        description="Emergency contact name",
    )
    emergency_contact_phone: Union[str, None] = Field(
        None,
        description="Emergency contact phone",
    )
    emergency_contact_relation: Union[str, None] = Field(
        None,
        description="Relation to emergency contact",
    )

    # Institutional/Employment
    institution_or_company: Union[str, None] = Field(
        None,
        description="Institution or company name",
    )
    designation_or_course: Union[str, None] = Field(
        None,
        description="Designation or course",
    )

    # Special Requirements
    special_requests: Union[str, None] = Field(
        None,
        description="Special requests",
    )
    dietary_preferences: Union[str, None] = Field(
        None,
        description="Dietary preferences",
    )
    has_vehicle: bool = Field(
        ...,
        description="Has vehicle",
    )
    vehicle_details: Union[str, None] = Field(
        None,
        description="Vehicle details",
    )

    # Pricing - decimal_places removed
    quoted_rent_monthly: Decimal = Field(
        ...,
        ge=0,
        description="Monthly rent quoted (precision: 2 decimal places)",
    )
    total_amount: Decimal = Field(
        ...,
        ge=0,
        description="Total amount (precision: 2 decimal places)",
    )
    security_deposit: Decimal = Field(
        ...,
        ge=0,
        description="Security deposit (precision: 2 decimal places)",
    )
    advance_amount: Decimal = Field(
        ...,
        ge=0,
        description="Advance amount (precision: 2 decimal places)",
    )
    advance_paid: bool = Field(
        ...,
        description="Advance payment status",
    )
    advance_payment_id: Union[UUID, None] = Field(
        None,
        description="Advance payment transaction ID",
    )

    # Status Workflow
    booking_status: BookingStatus = Field(
        ...,
        description="Current booking status",
    )

    # Approval Details
    approved_by: Union[UUID, None] = Field(
        None,
        description="Admin who approved booking",
    )
    approved_by_name: Union[str, None] = Field(
        None,
        description="Approver name",
    )
    approved_at: Union[datetime, None] = Field(
        None,
        description="Approval timestamp",
    )

    # Rejection Details
    rejected_by: Union[UUID, None] = Field(
        None,
        description="Admin who rejected booking",
    )
    rejected_at: Union[datetime, None] = Field(
        None,
        description="Rejection timestamp",
    )
    rejection_reason: Union[str, None] = Field(
        None,
        description="Reason for rejection",
    )

    # Cancellation Details
    cancelled_by: Union[UUID, None] = Field(
        None,
        description="Who cancelled the booking",
    )
    cancelled_at: Union[datetime, None] = Field(
        None,
        description="Cancellation timestamp",
    )
    cancellation_reason: Union[str, None] = Field(
        None,
        description="Reason for cancellation",
    )

    # Conversion to Student
    converted_to_student: bool = Field(
        ...,
        description="Whether booking was converted to student profile",
    )
    student_profile_id: Union[UUID, None] = Field(
        None,
        description="Student profile ID if converted",
    )
    conversion_date: Union[Date, None] = Field(
        None,
        description="Date of conversion to student",
    )

    # Source
    source: BookingSource = Field(
        ...,
        description="Booking source",
    )
    referral_code: Union[str, None] = Field(
        None,
        description="Referral code used",
    )

    # Timestamps
    booking_date: datetime = Field(
        ...,
        description="Booking creation timestamp",
    )
    expires_at: Union[datetime, None] = Field(
        None,
        description="Booking expiry timestamp",
    )

    @computed_field
    @property
    def is_assigned(self) -> bool:
        """Check if room and bed are assigned."""
        return self.room_id is not None and self.bed_id is not None

    @computed_field
    @property
    def days_until_check_in(self) -> int:
        """Days remaining until check-in."""
        return (self.preferred_check_in_date - Date.today()).days

    @computed_field
    @property
    def balance_amount(self) -> Decimal:
        """Calculate balance amount."""
        if self.advance_paid:
            return (self.total_amount - self.advance_amount).quantize(Decimal("0.01"))
        return self.total_amount


class BookingListItem(BaseSchema):
    """
    Booking list item for summary views.
    
    Optimized schema for listing multiple bookings with
    essential information only.
    """

    id: UUID = Field(
        ...,
        description="Booking ID",
    )
    booking_reference: str = Field(
        ...,
        description="Booking reference",
    )
    guest_name: str = Field(
        ...,
        description="Guest name",
    )
    guest_phone: str = Field(
        ...,
        description="Guest phone",
    )

    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    room_type_requested: str = Field(
        ...,
        description="Requested room type",
    )

    preferred_check_in_date: Date = Field(
        ...,
        description="Check-in Date",
    )
    stay_duration_months: int = Field(
        ...,
        ge=1,
        description="Duration in months",
    )

    # Pricing - decimal_places removed
    total_amount: Decimal = Field(
        ...,
        ge=0,
        description="Total amount (precision: 2 decimal places)",
    )
    advance_paid: bool = Field(
        ...,
        description="Advance payment status",
    )

    booking_status: BookingStatus = Field(
        ...,
        description="Booking status",
    )
    booking_date: datetime = Field(
        ...,
        description="Booking Date",
    )

    # Quick Indicators
    is_urgent: bool = Field(
        ...,
        description="Whether booking is expiring soon or requires urgent attention",
    )
    days_until_checkin: Union[int, None] = Field(
        None,
        description="Days until check-in (if applicable)",
    )

    @computed_field
    @property
    def status_badge_color(self) -> str:
        """Get color code for status badge."""
        status_colors = {
            BookingStatus.PENDING: "warning",
            BookingStatus.APPROVED: "success",
            BookingStatus.CONFIRMED: "info",
            BookingStatus.CHECKED_IN: "primary",
            BookingStatus.COMPLETED: "secondary",
            BookingStatus.REJECTED: "danger",
            BookingStatus.CANCELLED: "dark",
            BookingStatus.EXPIRED: "muted",
        }
        return status_colors.get(self.booking_status, "secondary")


class BookingConfirmation(BaseSchema):
    """
    Booking confirmation response.
    
    Sent to guest after successful booking creation or approval.
    """

    booking_id: UUID = Field(
        ...,
        description="Booking identifier",
    )
    booking_reference: str = Field(
        ...,
        description="Booking reference number",
    )

    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    room_type: str = Field(
        ...,
        description="Room type",
    )
    check_in_date: Date = Field(
        ...,
        description="Check-in Date",
    )

    # Pricing - decimal_places removed
    total_amount: Decimal = Field(
        ...,
        ge=0,
        description="Total booking amount (precision: 2 decimal places)",
    )
    advance_amount: Decimal = Field(
        ...,
        ge=0,
        description="Advance payment required (precision: 2 decimal places)",
    )
    balance_amount: Decimal = Field(
        ...,
        ge=0,
        description="Balance amount to be paid (precision: 2 decimal places)",
    )

    confirmation_message: str = Field(
        ...,
        description="Confirmation message for guest",
    )
    next_steps: List[str] = Field(
        ...,
        description="List of next steps for guest",
    )

    # Contact Information
    hostel_contact_phone: str = Field(
        ...,
        description="Hostel contact phone",
    )
    hostel_contact_email: Union[str, None] = Field(
        None,
        description="Hostel contact email",
    )

    @computed_field
    @property
    def payment_pending(self) -> bool:
        """Check if payment is still pending."""
        return self.balance_amount > Decimal("0")