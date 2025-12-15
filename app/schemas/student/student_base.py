"""
Student base schemas with enhanced validation and type safety.

Provides core student management schemas including creation, updates,
check-in/check-out operations, and student-specific attributes.
"""

from __future__ import annotations

from datetime import date as Date
from decimal import Decimal
from typing import Optional, Annotated

from pydantic import Field, field_validator, model_validator, ConfigDict

from app.schemas.common.base import (
    BaseCreateSchema,
    BaseSchema,
    BaseUpdateSchema,
)
from app.schemas.common.enums import (
    DietaryPreference,
    IDProofType,
    StudentStatus,
)

__all__ = [
    "StudentBase",
    "StudentCreate",
    "StudentUpdate",
    "StudentCheckInRequest",
    "StudentCheckOutRequest",
    "StudentRoomAssignment",
    "StudentStatusUpdate",
]

# Type aliases for common decimal fields to handle v2 constraints properly
MoneyAmount = Annotated[Decimal, Field(max_digits=10, decimal_places=2, ge=0)]


class StudentBase(BaseSchema):
    """
    Base student schema with comprehensive student attributes.
    
    Contains common fields shared across student operations including
    identification, guardian info, institutional/employment details,
    and preferences.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
    )

    user_id: str = Field(
        ...,
        description="Associated user ID",
    )
    hostel_id: str = Field(
        ...,
        description="Current hostel ID",
    )
    room_id: Optional[str] = Field(
        default=None,
        description="Assigned room ID (null if not assigned)",
    )
    bed_id: Optional[str] = Field(
        default=None,
        description="Assigned bed ID (null if not assigned)",
    )

    # Identification documents
    id_proof_type: Optional[IDProofType] = Field(
        default=None,
        description="Type of ID proof submitted",
    )
    id_proof_number: Optional[str] = Field(
        default=None,
        max_length=50,
        description="ID proof number/reference",
    )
    id_proof_document_url: Optional[str] = Field(
        default=None,
        description="Uploaded ID proof document URL",
    )

    # Guardian information (mandatory for students)
    guardian_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Guardian/parent full name",
        examples=["John Smith", "Mrs. Jane Doe"],
    )
    guardian_phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Guardian contact phone (E.164 format)",
        examples=["+919876543210", "9876543210"],
    )
    guardian_email: Optional[str] = Field(
        default=None,
        description="Guardian email address",
    )
    guardian_relation: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Relation to student",
        examples=["Father", "Mother", "Uncle", "Guardian"],
    )
    guardian_address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Guardian residential address",
    )

    # Institutional information (for students)
    institution_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="College/University/School name",
        examples=["IIT Delhi", "Delhi University", "XYZ College"],
    )
    course: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Course/Program name",
        examples=["B.Tech Computer Science", "MBA", "BA Economics"],
    )
    year_of_study: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Current year/semester",
        examples=["1st Year", "3rd Semester", "Final Year"],
    )
    student_id_number: Optional[str] = Field(
        default=None,
        max_length=100,
        description="College/University ID number",
    )
    institutional_id_url: Optional[str] = Field(
        default=None,
        description="Uploaded institutional ID card URL",
    )

    # Employment information (for working professionals)
    company_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Employer/Company name",
        examples=["Google India", "Infosys", "Startup XYZ"],
    )
    designation: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Job title/designation",
        examples=["Software Engineer", "Marketing Manager", "Analyst"],
    )
    company_id_url: Optional[str] = Field(
        default=None,
        description="Company ID card URL",
    )

    # Check-in/Check-out dates
    check_in_date: Optional[Date] = Field(
        default=None,
        description="Actual check-in Date",
    )
    expected_checkout_date: Optional[Date] = Field(
        default=None,
        description="Expected/planned checkout Date",
    )
    actual_checkout_date: Optional[Date] = Field(
        default=None,
        description="Actual checkout Date (when checked out)",
    )

    # Financial information - Fixed for Pydantic v2 decimal constraints
    security_deposit_amount: MoneyAmount = Field(
        default=Decimal("0.00"),
        description="Security deposit amount",
    )
    security_deposit_paid: bool = Field(
        default=False,
        description="Security deposit payment status",
    )
    security_deposit_paid_date: Optional[Date] = Field(
        default=None,
        description="Date security deposit was paid",
    )
    monthly_rent_amount: Optional[MoneyAmount] = Field(
        default=None,
        description="Monthly rent amount for the student",
    )

    # Meal preferences
    mess_subscribed: bool = Field(
        default=False,
        description="Subscribed to mess/canteen facility",
    )
    dietary_preference: Optional[DietaryPreference] = Field(
        default=None,
        description="Dietary preference (veg/non-veg/vegan/jain)",
    )
    food_allergies: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Food allergies and restrictions",
        examples=["Peanuts, Shellfish", "Lactose intolerant", "Gluten allergy"],
    )

    # Status tracking
    student_status: StudentStatus = Field(
        default=StudentStatus.ACTIVE,
        description="Current student status",
    )
    notice_period_start: Optional[Date] = Field(
        default=None,
        description="Notice period start Date (if leaving)",
    )
    notice_period_end: Optional[Date] = Field(
        default=None,
        description="Notice period end Date",
    )

    @field_validator("guardian_name")
    @classmethod
    def validate_guardian_name(cls, v: str) -> str:
        """
        Validate and normalize guardian name.
        
        Ensures name is properly formatted and trimmed.
        """
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Guardian name must be at least 2 characters")
        if v.isdigit():
            raise ValueError("Guardian name cannot be only numbers")
        # Remove excessive whitespace
        v = " ".join(v.split())
        return v

    @field_validator("guardian_phone")
    @classmethod
    def normalize_guardian_phone(cls, v: str) -> str:
        """Normalize guardian phone number."""
        return v.replace(" ", "").replace("-", "").strip()

    @field_validator("guardian_email")
    @classmethod
    def normalize_guardian_email(cls, v: Optional[str]) -> Optional[str]:
        """Normalize guardian email."""
        if v is not None:
            return v.lower().strip()
        return v

    @field_validator("id_proof_number")
    @classmethod
    def validate_id_proof_number(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize ID proof number."""
        if v is not None:
            v = v.strip().upper()
            if not v:
                return None
            # Remove excessive whitespace
            v = " ".join(v.split())
        return v

    @field_validator(
        "institution_name",
        "course",
        "company_name",
        "designation",
    )
    @classmethod
    def normalize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Normalize text fields."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            # Remove excessive whitespace
            v = " ".join(v.split())
        return v

    @model_validator(mode="after")
    def validate_checkout_dates(self) -> "StudentBase":
        """
        Validate checkout Date relationships.
        
        Ensures expected checkout is after check-in and actual is after expected.
        """
        if self.check_in_date and self.expected_checkout_date:
            if self.expected_checkout_date <= self.check_in_date:
                raise ValueError(
                    "Expected checkout Date must be after check-in Date"
                )

        if self.check_in_date and self.actual_checkout_date:
            if self.actual_checkout_date < self.check_in_date:
                raise ValueError(
                    "Actual checkout Date cannot be before check-in Date"
                )

        return self

    @model_validator(mode="after")
    def validate_notice_period(self) -> "StudentBase":
        """Validate notice period dates."""
        if self.notice_period_start and self.notice_period_end:
            if self.notice_period_end <= self.notice_period_start:
                raise ValueError(
                    "Notice period end must be after start Date"
                )
        return self

    @model_validator(mode="after")
    def validate_institutional_or_employment(self) -> "StudentBase":
        """
        Validate that either institutional or employment info is provided.
        
        Students should be either studying or working.
        Note: This is a soft validation - we don't raise error to allow flexibility.
        """
        has_institution = any(
            [
                self.institution_name,
                self.course,
                self.student_id_number,
            ]
        )
        has_employment = any([self.company_name, self.designation])

        # Just log or track - don't enforce strictly
        # This allows for gap year students, etc.

        return self

    @model_validator(mode="after")
    def validate_room_bed_consistency(self) -> "StudentBase":
        """Validate room and bed assignment consistency."""
        # If bed is assigned, room must be assigned
        if self.bed_id and not self.room_id:
            raise ValueError(
                "Cannot assign bed without assigning room"
            )
        return self


class StudentCreate(StudentBase, BaseCreateSchema):
    """
    Schema for creating a new student record.
    
    Used when converting a booking to student or direct student registration.
    """

    # Override to ensure required fields
    user_id: str = Field(
        ...,
        description="User ID (required)",
    )
    hostel_id: str = Field(
        ...,
        description="Hostel ID (required)",
    )
    guardian_name: str = Field(
        ...,
        min_length=2,
        description="Guardian name (required)",
    )
    guardian_phone: str = Field(
        ...,
        description="Guardian phone (required)",
    )

    # Optional link to source booking
    booking_id: Optional[str] = Field(
        default=None,
        description="Source booking ID (if converted from booking)",
    )

    # Initial payment status
    initial_rent_paid: bool = Field(
        default=False,
        description="Whether initial/first month rent is paid",
    )


class StudentUpdate(BaseUpdateSchema):
    """
    Schema for updating student information.
    
    All fields are optional for partial updates.
    """

    # Room assignment updates
    room_id: Optional[str] = Field(
        default=None,
        description="Updated room ID",
    )
    bed_id: Optional[str] = Field(
        default=None,
        description="Updated bed ID",
    )

    # Identification updates
    id_proof_type: Optional[IDProofType] = Field(
        default=None,
        description="ID proof type",
    )
    id_proof_number: Optional[str] = Field(
        default=None,
        max_length=50,
        description="ID proof number",
    )
    id_proof_document_url: Optional[str] = Field(
        default=None,
        description="ID proof document URL",
    )

    # Guardian updates
    guardian_name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=255,
        description="Guardian name",
    )
    guardian_phone: Optional[str] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Guardian phone",
    )
    guardian_email: Optional[str] = Field(
        default=None,
        description="Guardian email",
    )
    guardian_relation: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Guardian relation",
    )
    guardian_address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Guardian address",
    )

    # Institutional updates
    institution_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Institution name",
    )
    course: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Course",
    )
    year_of_study: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Year of study",
    )
    student_id_number: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Student ID number",
    )
    institutional_id_url: Optional[str] = Field(
        default=None,
        description="Institutional ID URL",
    )

    # Employment updates
    company_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Company name",
    )
    designation: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Designation",
    )
    company_id_url: Optional[str] = Field(
        default=None,
        description="Company ID URL",
    )

    # Date updates
    check_in_date: Optional[Date] = Field(
        default=None,
        description="Check-in Date",
    )
    expected_checkout_date: Optional[Date] = Field(
        default=None,
        description="Expected checkout Date",
    )
    actual_checkout_date: Optional[Date] = Field(
        default=None,
        description="Actual checkout Date",
    )

    # Financial updates - Fixed for Pydantic v2
    security_deposit_amount: Optional[MoneyAmount] = Field(
        default=None,
        description="Security deposit amount",
    )
    security_deposit_paid: Optional[bool] = Field(
        default=None,
        description="Security deposit paid status",
    )
    security_deposit_paid_date: Optional[Date] = Field(
        default=None,
        description="Security deposit paid Date",
    )
    monthly_rent_amount: Optional[MoneyAmount] = Field(
        default=None,
        description="Monthly rent amount",
    )

    # Meal updates
    mess_subscribed: Optional[bool] = Field(
        default=None,
        description="Mess subscription status",
    )
    dietary_preference: Optional[DietaryPreference] = Field(
        default=None,
        description="Dietary preference",
    )
    food_allergies: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Food allergies",
    )

    # Status updates
    student_status: Optional[StudentStatus] = Field(
        default=None,
        description="Student status",
    )
    notice_period_start: Optional[Date] = Field(
        default=None,
        description="Notice period start",
    )
    notice_period_end: Optional[Date] = Field(
        default=None,
        description="Notice period end",
    )

    # Apply same validators as base
    @field_validator("guardian_name")
    @classmethod
    def validate_guardian_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return StudentBase.validate_guardian_name(v)
        return v

    @field_validator("guardian_phone")
    @classmethod
    def normalize_guardian_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return StudentBase.normalize_guardian_phone(v)
        return v

    @field_validator("guardian_email")
    @classmethod
    def normalize_guardian_email(cls, v: Optional[str]) -> Optional[str]:
        return StudentBase.normalize_guardian_email(v)

    @field_validator("id_proof_number")
    @classmethod
    def validate_id_proof_number(cls, v: Optional[str]) -> Optional[str]:
        return StudentBase.validate_id_proof_number(v)

    @field_validator(
        "institution_name",
        "course",
        "company_name",
        "designation",
    )
    @classmethod
    def normalize_text_fields(cls, v: Optional[str]) -> Optional[str]:
        return StudentBase.normalize_text_fields(v)


class StudentCheckInRequest(BaseCreateSchema):
    """
    Schema for student check-in operation.
    
    Handles the complete check-in process with room/bed assignment
    and payment verification.
    """

    student_id: str = Field(
        ...,
        description="Student ID to check in",
    )
    check_in_date: Date = Field(
        ...,
        description="Check-in Date",
    )
    room_id: str = Field(
        ...,
        description="Assigned room ID",
    )
    bed_id: str = Field(
        ...,
        description="Assigned bed ID",
    )

    # Payment verification
    security_deposit_paid: bool = Field(
        default=False,
        description="Security deposit payment confirmation",
    )
    security_deposit_payment_id: Optional[str] = Field(
        default=None,
        description="Security deposit payment reference ID",
    )
    initial_rent_paid: bool = Field(
        default=False,
        description="First month rent payment confirmation",
    )
    initial_rent_payment_id: Optional[str] = Field(
        default=None,
        description="Initial rent payment reference ID",
    )

    # Additional charges
    mess_advance_paid: bool = Field(
        default=False,
        description="Mess advance payment (if applicable)",
    )
    other_charges_paid: bool = Field(
        default=False,
        description="Other charges payment confirmation",
    )

    # Documentation
    id_proof_verified: bool = Field(
        default=False,
        description="ID proof verification status",
    )
    documents_collected: bool = Field(
        default=False,
        description="All required documents collected",
    )

    # Notes
    check_in_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Check-in notes and observations",
    )

    @field_validator("check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: Date) -> Date:
        """Validate check-in Date is reasonable."""
        from datetime import timedelta

        today = Date.today()

        # Allow up to 30 days in the past for data entry
        if v < today - timedelta(days=30):
            raise ValueError(
                "Check-in Date cannot be more than 30 days in the past"
            )

        # Warn if more than 7 days in future
        if v > today + timedelta(days=7):
            raise ValueError(
                "Check-in Date cannot be more than 7 days in the future"
            )

        return v

    @model_validator(mode="after")
    def validate_payment_references(self) -> "StudentCheckInRequest":
        """Validate payment reference IDs are provided when payments are confirmed."""
        if self.security_deposit_paid and not self.security_deposit_payment_id:
            raise ValueError(
                "Security deposit payment ID is required when payment is confirmed"
            )

        if self.initial_rent_paid and not self.initial_rent_payment_id:
            raise ValueError(
                "Initial rent payment ID is required when payment is confirmed"
            )

        return self


class StudentCheckOutRequest(BaseCreateSchema):
    """
    Schema for student check-out operation.
    
    Handles the complete checkout process with clearance verification
    and refund processing.
    """

    student_id: str = Field(
        ...,
        description="Student ID to check out",
    )
    checkout_date: Date = Field(
        ...,
        description="Actual checkout Date",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason for checkout",
        examples=[
            "Course completion",
            "Job relocation",
            "Personal reasons",
            "Transferred to another hostel",
        ],
    )

    # Financial clearance - Fixed for Pydantic v2
    final_dues_cleared: bool = Field(
        default=False,
        description="All outstanding dues cleared",
    )
    outstanding_amount: MoneyAmount = Field(
        default=Decimal("0.00"),
        description="Outstanding amount (if any)",
    )
    refund_security_deposit: bool = Field(
        default=True,
        description="Refund security deposit",
    )
    security_deposit_refund_amount: Optional[MoneyAmount] = Field(
        default=None,
        description="Security deposit refund amount (after deductions)",
    )
    deduction_amount: MoneyAmount = Field(
        default=Decimal("0.00"),
        description="Deductions from security deposit",
    )
    deduction_reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason for deductions",
    )

    # Room clearance
    room_condition_acceptable: bool = Field(
        default=True,
        description="Room condition is acceptable",
    )
    damages_reported: bool = Field(
        default=False,
        description="Any damages reported",
    )
    damage_charges: MoneyAmount = Field(
        default=Decimal("0.00"),
        description="Charges for damages",
    )

    # Property return
    key_returned: bool = Field(
        default=False,
        description="Room key returned",
    )
    id_card_returned: bool = Field(
        default=False,
        description="Hostel ID card returned",
    )
    other_items_returned: bool = Field(
        default=False,
        description="Other borrowed items returned",
    )

    # Clearance from departments
    mess_clearance: bool = Field(
        default=True,
        description="Mess dues cleared",
    )
    library_clearance: bool = Field(
        default=True,
        description="Library clearance obtained",
    )
    maintenance_clearance: bool = Field(
        default=True,
        description="No pending maintenance complaints",
    )

    # Notes
    checkout_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Checkout notes and observations",
    )
    forwarding_address: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Forwarding address for correspondence",
    )

    @field_validator("checkout_date")
    @classmethod
    def validate_checkout_date(cls, v: Date) -> Date:
        """Validate checkout Date."""
        from datetime import timedelta

        today = Date.today()

        # Allow past dates for data entry
        # Future dates for scheduled checkout
        if v > today + timedelta(days=90):
            raise ValueError(
                "Checkout Date cannot be more than 90 days in the future"
            )

        return v

    @model_validator(mode="after")
    def validate_financial_consistency(self) -> "StudentCheckOutRequest":
        """Validate financial data consistency."""
        if not self.final_dues_cleared and self.outstanding_amount == 0:
            raise ValueError(
                "If dues are not cleared, outstanding amount must be greater than 0"
            )

        if self.refund_security_deposit and self.security_deposit_refund_amount is None:
            raise ValueError(
                "Security deposit refund amount is required when refunding deposit"
            )

        return self

    @model_validator(mode="after")
    def validate_clearance_requirements(self) -> "StudentCheckOutRequest":
        """Validate clearance requirements."""
        # If damages reported or poor room condition, require damage charges or reason
        if self.damages_reported or not self.room_condition_acceptable:
            if self.damage_charges == 0 and not self.deduction_reason:
                raise ValueError(
                    "Damage charges or deduction reason required for reported damages"
                )

        return self


class StudentRoomAssignment(BaseCreateSchema):
    """
    Schema for assigning/reassigning room and bed to student.
    
    Dedicated schema for room/bed assignment operations.
    """

    student_id: str = Field(
        ...,
        description="Student ID",
    )
    room_id: str = Field(
        ...,
        description="Room ID to assign",
    )
    bed_id: str = Field(
        ...,
        description="Bed ID to assign",
    )
    assignment_date: Date = Field(
        ...,
        description="Assignment effective Date",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason for assignment/reassignment",
    )

    # Financial impact - Fixed for Pydantic v2
    rent_adjustment: Optional[Decimal] = Field(
        default=None,
        description="Rent adjustment due to room change",
    )
    prorated_rent: bool = Field(
        default=True,
        description="Calculate prorated rent for partial month",
    )

    @field_validator("assignment_date")
    @classmethod
    def validate_assignment_date(cls, v: Date) -> Date:
        """Validate assignment Date."""
        from datetime import timedelta

        today = Date.today()

        if v < today - timedelta(days=7):
            raise ValueError(
                "Assignment Date cannot be more than 7 days in the past"
            )

        return v


class StudentStatusUpdate(BaseCreateSchema):
    """
    Schema for updating student status.
    
    Handles status transitions with proper tracking and documentation.
    """

    student_id: str = Field(
        ...,
        description="Student ID",
    )
    new_status: StudentStatus = Field(
        ...,
        description="New student status",
    )
    effective_date: Date = Field(
        ...,
        description="Status change effective Date",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for status change",
    )

    # For notice period status
    notice_period_days: Optional[int] = Field(
        default=None,
        ge=0,
        le=90,
        description="Notice period duration in days",
    )

    # For suspension
    suspension_end_date: Optional[Date] = Field(
        default=None,
        description="Suspension end Date (for SUSPENDED status)",
    )

    # Additional notes
    admin_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Administrative notes",
    )

    @model_validator(mode="after")
    def validate_status_specific_fields(self) -> "StudentStatusUpdate":
        """Validate status-specific required fields."""
        if self.new_status == StudentStatus.SUSPENDED:
            if not self.suspension_end_date:
                raise ValueError(
                    "Suspension end Date is required for SUSPENDED status"
                )

        if self.new_status == StudentStatus.NOTICE_PERIOD:
            if not self.notice_period_days:
                raise ValueError(
                    "Notice period duration is required for NOTICE_PERIOD status"
                )

        return self

    @model_validator(mode="after")
    def validate_suspension_date(self) -> "StudentStatusUpdate":
        """Validate suspension end Date."""
        if self.suspension_end_date:
            if self.suspension_end_date <= self.effective_date:
                raise ValueError(
                    "Suspension end Date must be after effective Date"
                )

        return self