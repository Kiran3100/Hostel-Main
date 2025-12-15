"""
Student response schemas for API responses.

Provides various response formats for student data including
detailed views, list items, profiles, and specialized information.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Optional, Annotated

from pydantic import Field, computed_field, ConfigDict

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import (
    DietaryPreference,
    IDProofType,
    StudentStatus,
)

__all__ = [
    "StudentResponse",
    "StudentDetail",
    "StudentProfile",
    "StudentListItem",
    "StudentFinancialInfo",
    "StudentContactInfo",
    "StudentDocumentInfo",
]

# Type aliases for Pydantic v2 decimal constraints
MoneyAmount = Annotated[Decimal, Field(max_digits=10, decimal_places=2, ge=0)]


class StudentResponse(BaseResponseSchema):
    """
    Standard student response schema.
    
    Basic student information for general API responses.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    user_id: str = Field(..., description="User ID")
    hostel_id: str = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    room_id: Optional[str] = Field(default=None, description="Room ID")
    room_number: Optional[str] = Field(default=None, description="Room number")
    bed_id: Optional[str] = Field(default=None, description="Bed ID")
    bed_number: Optional[str] = Field(default=None, description="Bed number")

    # Personal info (from user)
    full_name: str = Field(..., description="Student full name")
    email: str = Field(..., description="Email address")
    phone: str = Field(..., description="Phone number")
    profile_image_url: Optional[str] = Field(
        default=None,
        description="Profile image URL",
    )

    # Guardian
    guardian_name: str = Field(..., description="Guardian name")
    guardian_phone: str = Field(..., description="Guardian phone")

    # Status
    student_status: StudentStatus = Field(..., description="Student status")
    check_in_date: Optional[Date] = Field(
        default=None,
        description="Check-in Date",
    )
    expected_checkout_date: Optional[Date] = Field(
        default=None,
        description="Expected checkout Date",
    )

    # Financial
    monthly_rent_amount: Optional[MoneyAmount] = Field(
        default=None,
        description="Monthly rent",
    )
    security_deposit_amount: MoneyAmount = Field(
        ...,
        description="Security deposit amount",
    )
    security_deposit_paid: bool = Field(
        ...,
        description="Security deposit paid status",
    )

    # Meal
    mess_subscribed: bool = Field(..., description="Mess subscription status")

    @computed_field
    @property
    def days_in_hostel(self) -> Optional[int]:
        """Calculate days stayed in hostel."""
        if not self.check_in_date:
            return None
        end_date = getattr(self, 'actual_checkout_date', None) or Date.today()
        return (end_date - self.check_in_date).days

    @computed_field
    @property
    def is_checked_in(self) -> bool:
        """Check if student is currently checked in."""
        return (
            self.check_in_date is not None
            and getattr(self, 'actual_checkout_date', None) is None
        )


class StudentDetail(BaseResponseSchema):
    """
    Detailed student information.
    
    Comprehensive student profile with all attributes.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # User information
    user_id: str = Field(..., description="User ID")
    full_name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email")
    phone: str = Field(..., description="Phone")
    gender: Optional[str] = Field(default=None, description="Gender")
    date_of_birth: Optional[Date] = Field(default=None, description="Date of birth")
    profile_image_url: Optional[str] = Field(
        default=None,
        description="Profile image",
    )

    # Hostel assignment
    hostel_id: str = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    room_id: Optional[str] = Field(default=None, description="Room ID")
    room_number: Optional[str] = Field(default=None, description="Room number")
    room_type: Optional[str] = Field(default=None, description="Room type")
    floor_number: Optional[int] = Field(default=None, description="Floor number")
    bed_id: Optional[str] = Field(default=None, description="Bed ID")
    bed_number: Optional[str] = Field(default=None, description="Bed number")

    # Identification
    id_proof_type: Optional[IDProofType] = Field(
        default=None,
        description="ID proof type",
    )
    id_proof_number: Optional[str] = Field(
        default=None,
        description="ID proof number",
    )
    id_proof_document_url: Optional[str] = Field(
        default=None,
        description="ID proof document URL",
    )
    id_proof_verified: bool = Field(
        default=False,
        description="ID proof verification status",
    )

    # Guardian information
    guardian_name: str = Field(..., description="Guardian name")
    guardian_phone: str = Field(..., description="Guardian phone")
    guardian_email: Optional[str] = Field(default=None, description="Guardian email")
    guardian_relation: Optional[str] = Field(
        default=None,
        description="Guardian relation",
    )
    guardian_address: Optional[str] = Field(
        default=None,
        description="Guardian address",
    )

    # Institutional information
    institution_name: Optional[str] = Field(
        default=None,
        description="Institution name",
    )
    course: Optional[str] = Field(default=None, description="Course")
    year_of_study: Optional[str] = Field(default=None, description="Year of study")
    student_id_number: Optional[str] = Field(
        default=None,
        description="Student ID number",
    )
    institutional_id_url: Optional[str] = Field(
        default=None,
        description="Institutional ID URL",
    )

    # Employment information
    company_name: Optional[str] = Field(default=None, description="Company name")
    designation: Optional[str] = Field(default=None, description="Designation")
    company_id_url: Optional[str] = Field(
        default=None,
        description="Company ID URL",
    )

    # Dates
    check_in_date: Optional[Date] = Field(default=None, description="Check-in Date")
    expected_checkout_date: Optional[Date] = Field(
        default=None,
        description="Expected checkout",
    )
    actual_checkout_date: Optional[Date] = Field(
        default=None,
        description="Actual checkout",
    )

    # Financial
    security_deposit_amount: MoneyAmount = Field(
        ...,
        description="Security deposit amount",
    )
    security_deposit_paid: bool = Field(
        ...,
        description="Security deposit paid",
    )
    security_deposit_paid_date: Optional[Date] = Field(
        default=None,
        description="Deposit paid Date",
    )
    monthly_rent_amount: Optional[MoneyAmount] = Field(
        default=None,
        description="Monthly rent",
    )

    # Meal preferences
    mess_subscribed: bool = Field(..., description="Mess subscription")
    dietary_preference: Optional[DietaryPreference] = Field(
        default=None,
        description="Dietary preference",
    )
    food_allergies: Optional[str] = Field(
        default=None,
        description="Food allergies",
    )

    # Status
    student_status: StudentStatus = Field(..., description="Student status")
    notice_period_start: Optional[Date] = Field(
        default=None,
        description="Notice period start",
    )
    notice_period_end: Optional[Date] = Field(
        default=None,
        description="Notice period end",
    )

    # Source
    booking_id: Optional[str] = Field(
        default=None,
        description="Source booking ID",
    )

    # Additional documents
    additional_documents: List[dict] = Field(
        default_factory=list,
        description="Additional uploaded documents",
    )

    @computed_field
    @property
    def age(self) -> Optional[int]:
        """Calculate age from Date of birth."""
        if not self.date_of_birth:
            return None
        today = Date.today()
        return (
            today.year
            - self.date_of_birth.year
            - (
                (today.month, today.day)
                < (self.date_of_birth.month, self.date_of_birth.day)
            )
        )

    @computed_field
    @property
    def days_in_hostel(self) -> Optional[int]:
        """Calculate total days in hostel."""
        if not self.check_in_date:
            return None
        end_date = self.actual_checkout_date or Date.today()
        return (end_date - self.check_in_date).days

    @computed_field
    @property
    def is_currently_resident(self) -> bool:
        """Check if currently a resident."""
        return (
            self.check_in_date is not None
            and self.actual_checkout_date is None
            and self.student_status == StudentStatus.ACTIVE
        )

    @computed_field
    @property
    def is_student(self) -> bool:
        """Check if institutional student."""
        return bool(self.institution_name or self.course)

    @computed_field
    @property
    def is_working_professional(self) -> bool:
        """Check if working professional."""
        return bool(self.company_name or self.designation)


class StudentProfile(BaseSchema):
    """
    Public student profile.
    
    Limited information suitable for public/peer viewing.
    """

    id: str = Field(..., description="Student ID")
    full_name: str = Field(..., description="Full name")
    profile_image_url: Optional[str] = Field(
        default=None,
        description="Profile image",
    )
    hostel_name: str = Field(..., description="Hostel name")
    room_number: Optional[str] = Field(default=None, description="Room number")
    check_in_date: Optional[Date] = Field(default=None, description="Check-in Date")

    # Optional info (based on privacy settings)
    institution_name: Optional[str] = Field(
        default=None,
        description="Institution name",
    )
    course: Optional[str] = Field(default=None, description="Course")
    year_of_study: Optional[str] = Field(default=None, description="Year")
    company_name: Optional[str] = Field(default=None, description="Company")

    @computed_field
    @property
    def duration_in_hostel(self) -> Optional[str]:
        """Human-readable duration in hostel."""
        if not self.check_in_date:
            return None

        days = (Date.today() - self.check_in_date).days
        if days < 30:
            return f"{days} days"
        elif days < 365:
            months = days // 30
            return f"{months} month{'s' if months > 1 else ''}"
        else:
            years = days // 365
            return f"{years} year{'s' if years > 1 else ''}"


class StudentListItem(BaseSchema):
    """
    Student list item for admin views.
    
    Optimized for list rendering with essential information.
    """

    id: str = Field(..., description="Student ID")
    user_id: str = Field(..., description="User ID")
    full_name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email")
    phone: str = Field(..., description="Phone")
    profile_image_url: Optional[str] = Field(
        default=None,
        description="Profile image",
    )

    # Room assignment
    room_number: Optional[str] = Field(default=None, description="Room number")
    bed_number: Optional[str] = Field(default=None, description="Bed number")

    # Status
    student_status: StudentStatus = Field(..., description="Status")
    check_in_date: Optional[Date] = Field(default=None, description="Check-in Date")

    # Financial
    monthly_rent: Optional[MoneyAmount] = Field(default=None, description="Monthly rent")
    payment_status: str = Field(
        ...,
        description="Payment status (current/overdue/advance)",
    )
    overdue_amount: MoneyAmount = Field(
        default=Decimal("0.00"),
        description="Overdue amount",
    )

    # Timestamps
    created_at: datetime = Field(..., description="Registration timestamp")

    @computed_field
    @property
    def days_in_hostel(self) -> Optional[int]:
        """Calculate days in hostel."""
        if not self.check_in_date:
            return None
        return (Date.today() - self.check_in_date).days


class StudentFinancialInfo(BaseSchema):
    """
    Student financial information.
    
    Comprehensive financial details for a student.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    student_id: str = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")

    # Rent
    monthly_rent_amount: MoneyAmount = Field(..., description="Monthly rent")
    rent_due_day: int = Field(..., description="Monthly due day")

    # Security deposit
    security_deposit_amount: MoneyAmount = Field(..., description="Security deposit")
    security_deposit_paid: bool = Field(..., description="Deposit paid status")
    security_deposit_paid_date: Optional[Date] = Field(
        default=None,
        description="Deposit paid Date",
    )
    security_deposit_refundable: MoneyAmount = Field(
        ...,
        description="Refundable amount",
    )

    # Payments
    total_paid: MoneyAmount = Field(..., description="Total amount paid")
    total_due: MoneyAmount = Field(..., description="Total amount due")
    last_payment_date: Optional[Date] = Field(
        default=None,
        description="Last payment Date",
    )
    next_due_date: Optional[Date] = Field(default=None, description="Next due Date")

    # Outstanding
    overdue_amount: MoneyAmount = Field(..., description="Overdue amount")
    advance_amount: MoneyAmount = Field(..., description="Advance balance")

    # Mess
    mess_charges_monthly: MoneyAmount = Field(
        default=Decimal("0.00"),
        description="Monthly mess charges",
    )
    mess_balance: MoneyAmount = Field(
        default=Decimal("0.00"),
        description="Mess account balance",
    )

    # Other charges
    other_charges: MoneyAmount = Field(
        default=Decimal("0.00"),
        description="Other charges",
    )

    @computed_field
    @property
    def payment_status(self) -> str:
        """Determine payment status."""
        if self.overdue_amount > 0:
            return "overdue"
        elif self.advance_amount > 0:
            return "advance"
        else:
            return "current"

    @computed_field
    @property
    def total_outstanding(self) -> Decimal:
        """Calculate total outstanding amount."""
        return self.total_due - self.advance_amount

    @computed_field
    @property
    def net_balance(self) -> Decimal:
        """Calculate net balance (advance - dues)."""
        return self.advance_amount - self.total_due


class StudentContactInfo(BaseSchema):
    """
    Student contact information.
    
    Comprehensive contact details for emergency and communication.
    """

    student_id: str = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")

    # Student contact
    email: str = Field(..., description="Email")
    phone: str = Field(..., description="Phone")
    alternate_phone: Optional[str] = Field(default=None, description="Alternate phone")

    # Guardian contact
    guardian_name: str = Field(..., description="Guardian name")
    guardian_phone: str = Field(..., description="Guardian phone")
    guardian_email: Optional[str] = Field(default=None, description="Guardian email")
    guardian_relation: Optional[str] = Field(
        default=None,
        description="Guardian relation",
    )
    guardian_address: Optional[str] = Field(
        default=None,
        description="Guardian address",
    )

    # Emergency contact (from user profile)
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
        description="Emergency relation",
    )

    # Current address (hostel)
    current_hostel: str = Field(..., description="Current hostel")
    current_room: Optional[str] = Field(default=None, description="Current room")

    # Forwarding address (if checked out)
    forwarding_address: Optional[str] = Field(
        default=None,
        description="Forwarding address",
    )


class StudentDocumentInfo(BaseSchema):
    """
    Student document information.
    
    Details about uploaded documents and verification status.
    """

    student_id: str = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")

    # ID documents
    id_proof_type: Optional[IDProofType] = Field(
        default=None,
        description="ID proof type",
    )
    id_proof_number: Optional[str] = Field(
        default=None,
        description="ID proof number",
    )
    id_proof_url: Optional[str] = Field(
        default=None,
        description="ID proof document URL",
    )
    id_proof_verified: bool = Field(
        default=False,
        description="ID verification status",
    )
    id_proof_verified_at: Optional[datetime] = Field(
        default=None,
        description="Verification timestamp",
    )

    # Institutional documents
    institutional_id_url: Optional[str] = Field(
        default=None,
        description="College/University ID",
    )
    institutional_id_verified: bool = Field(
        default=False,
        description="Institutional ID verified",
    )

    # Employment documents
    company_id_url: Optional[str] = Field(
        default=None,
        description="Company ID card",
    )
    company_id_verified: bool = Field(
        default=False,
        description="Company ID verified",
    )

    # Additional documents
    additional_documents: List[dict] = Field(
        default_factory=list,
        description="Other uploaded documents",
    )

    @computed_field
    @property
    def verification_status(self) -> str:
        """Overall verification status."""
        if self.id_proof_verified:
            return "verified"
        elif self.id_proof_url:
            return "pending_verification"
        else:
            return "not_uploaded"

    @computed_field
    @property
    def documents_complete(self) -> bool:
        """Check if all required documents are uploaded."""
        return bool(self.id_proof_url)