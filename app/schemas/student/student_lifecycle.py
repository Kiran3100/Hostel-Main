"""
Student lifecycle schemas for API compatibility.

Provides schemas for student onboarding, checkout, and status management
operations. Maps to existing check-in/check-out schemas while providing
API-specific interfaces.
"""

from datetime import date as Date
from decimal import Decimal
from typing import Union, List, Annotated

from pydantic import Field, field_validator, model_validator, ConfigDict

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import StudentStatus

__all__ = [
    "OnboardingRequest",
    "CheckoutRequest", 
    "BulkStatusUpdate",
    "StatusUpdateRequest",
    "OnboardingResponse",
    "CheckoutResponse",
]

# Type aliases for Pydantic v2 decimal constraints
MoneyAmount = Annotated[Decimal, Field(max_digits=10, decimal_places=2, ge=0)]


class OnboardingRequest(BaseCreateSchema):
    """
    Student onboarding request.
    
    Used to onboard a student from booking to active residency.
    Maps to StudentCheckInRequest schema with additional onboarding context.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    # Source booking (optional)
    booking_id: Union[str, None] = Field(
        default=None,
        description="Source booking ID (if onboarding from booking)",
    )

    # Onboarding details
    onboarding_date: Date = Field(
        ...,
        description="Student onboarding/check-in date",
    )
    room_id: str = Field(
        ...,
        description="Assigned room ID",
    )
    bed_id: str = Field(
        ...,
        description="Assigned bed ID",
    )

    # Document verification
    documents_verified: bool = Field(
        default=False,
        description="All required documents verified",
    )
    id_proof_verified: bool = Field(
        default=False,
        description="ID proof document verified",
    )
    academic_documents_verified: bool = Field(
        default=False,
        description="Academic documents verified",
    )

    # Payment verification
    security_deposit_paid: bool = Field(
        default=False,
        description="Security deposit payment confirmed",
    )
    security_deposit_amount: Union[MoneyAmount, None] = Field(
        default=None,
        description="Security deposit amount",
    )
    security_deposit_payment_id: Union[str, None] = Field(
        default=None,
        description="Security deposit payment reference",
    )
    
    initial_rent_paid: bool = Field(
        default=False,
        description="First month rent paid",
    )
    initial_rent_amount: Union[MoneyAmount, None] = Field(
        default=None,
        description="Initial rent amount",
    )
    initial_rent_payment_id: Union[str, None] = Field(
        default=None,
        description="Initial rent payment reference",
    )

    # Additional charges
    mess_advance_paid: bool = Field(
        default=False,
        description="Mess advance payment (if applicable)",
    )
    mess_advance_amount: Union[MoneyAmount, None] = Field(
        default=None,
        description="Mess advance amount",
    )
    other_charges_paid: bool = Field(
        default=False,
        description="Other charges payment confirmation",
    )
    other_charges_amount: Union[MoneyAmount, None] = Field(
        default=None,
        description="Other charges amount",
    )

    # Orientation and setup
    orientation_completed: bool = Field(
        default=False,
        description="Hostel orientation completed",
    )
    rules_acknowledged: bool = Field(
        default=False,
        description="Hostel rules acknowledged",
    )
    key_issued: bool = Field(
        default=False,
        description="Room key issued to student",
    )
    id_card_issued: bool = Field(
        default=False,
        description="Hostel ID card issued",
    )

    # Notes and comments
    onboarding_notes: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Onboarding notes and observations",
    )
    special_instructions: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Special instructions for student",
    )

    @field_validator("onboarding_date")
    @classmethod
    def validate_onboarding_date(cls, v: Date) -> Date:
        """Validate onboarding date is reasonable."""
        from datetime import timedelta

        today = Date.today()

        # Allow up to 30 days in the past for data entry
        if v < today - timedelta(days=30):
            raise ValueError(
                "Onboarding date cannot be more than 30 days in the past"
            )

        # Allow up to 7 days in future for scheduled onboarding
        if v > today + timedelta(days=7):
            raise ValueError(
                "Onboarding date cannot be more than 7 days in the future"
            )

        return v

    @model_validator(mode="after")
    def validate_payment_references(self) -> "OnboardingRequest":
        """Validate payment reference IDs when payments are confirmed."""
        if self.security_deposit_paid and not self.security_deposit_payment_id:
            raise ValueError(
                "Security deposit payment ID required when payment is confirmed"
            )

        if self.initial_rent_paid and not self.initial_rent_payment_id:
            raise ValueError(
                "Initial rent payment ID required when payment is confirmed"
            )

        return self

    @model_validator(mode="after")
    def validate_onboarding_requirements(self) -> "OnboardingRequest":
        """Validate basic onboarding requirements are met."""
        if not self.documents_verified:
            # Warning: could be relaxed based on business requirements
            pass

        if not self.security_deposit_paid and not self.initial_rent_paid:
            raise ValueError(
                "At least security deposit or initial rent must be paid for onboarding"
            )

        return self


class CheckoutRequest(BaseCreateSchema):
    """
    Student checkout request.
    
    Used to process student checkout and room vacation.
    Maps to StudentCheckOutRequest schema with additional context.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    checkout_date: Date = Field(
        ...,
        description="Actual checkout date",
    )
    reason: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Reason for checkout",
        examples=[
            "Course completion",
            "Job relocation", 
            "Personal reasons",
            "Transfer to another hostel",
            "Academic suspension",
        ],
    )

    # Financial clearance
    final_dues_cleared: bool = Field(
        default=False,
        description="All outstanding dues cleared",
    )
    outstanding_amount: MoneyAmount = Field(
        default=Decimal("0.00"),
        description="Outstanding amount (if any)",
    )
    dues_clearance_certificate_issued: bool = Field(
        default=False,
        description="Dues clearance certificate issued",
    )

    # Security deposit handling
    refund_security_deposit: bool = Field(
        default=True,
        description="Process security deposit refund",
    )
    security_deposit_refund_amount: Union[MoneyAmount, None] = Field(
        default=None,
        description="Security deposit refund amount (after deductions)",
    )
    deduction_amount: MoneyAmount = Field(
        default=Decimal("0.00"),
        description="Deductions from security deposit",
    )
    deduction_reason: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Detailed reason for deductions",
    )

    # Room inspection and clearance
    room_inspection_completed: bool = Field(
        default=False,
        description="Room inspection completed",
    )
    room_condition_acceptable: bool = Field(
        default=True,
        description="Room condition is acceptable",
    )
    damages_reported: bool = Field(
        default=False,
        description="Any damages reported during inspection",
    )
    damage_charges: MoneyAmount = Field(
        default=Decimal("0.00"),
        description="Charges levied for damages",
    )
    damage_description: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Description of damages (if any)",
    )

    # Property return verification
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
        description="Other borrowed items returned (furniture, equipment, etc.)",
    )
    items_not_returned: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="List of items not returned",
    )

    # Department clearances
    mess_clearance: bool = Field(
        default=True,
        description="Mess dues cleared and clearance obtained",
    )
    library_clearance: bool = Field(
        default=True,
        description="Library clearance obtained (if applicable)",
    )
    maintenance_clearance: bool = Field(
        default=True,
        description="No pending maintenance complaints",
    )
    admin_clearance: bool = Field(
        default=True,
        description="Administrative clearance completed",
    )

    # Exit formalities
    exit_interview_completed: bool = Field(
        default=False,
        description="Exit interview conducted",
    )
    feedback_collected: bool = Field(
        default=False,
        description="Student feedback collected",
    )
    clearance_certificate_issued: bool = Field(
        default=False,
        description="Final clearance certificate issued",
    )

    # Future contact
    forwarding_address: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Forwarding address for correspondence",
    )
    forwarding_phone: Union[str, None] = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Forwarding contact number",
    )

    # Notes
    checkout_notes: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Checkout process notes and observations",
    )
    admin_remarks: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Administrative remarks",
    )

    @field_validator("checkout_date")
    @classmethod
    def validate_checkout_date(cls, v: Date) -> Date:
        """Validate checkout date."""
        from datetime import timedelta

        today = Date.today()

        # Allow past dates for data entry, future dates for scheduled checkout
        if v > today + timedelta(days=90):
            raise ValueError(
                "Checkout date cannot be more than 90 days in the future"
            )

        return v

    @model_validator(mode="after")
    def validate_financial_consistency(self) -> "CheckoutRequest":
        """Validate financial data consistency."""
        if not self.final_dues_cleared and self.outstanding_amount == 0:
            raise ValueError(
                "If dues are not cleared, outstanding amount must be greater than 0"
            )

        if self.refund_security_deposit and self.security_deposit_refund_amount is None:
            raise ValueError(
                "Security deposit refund amount required when processing refund"
            )

        if self.deduction_amount > 0 and not self.deduction_reason:
            raise ValueError(
                "Deduction reason required when deducting from security deposit"
            )

        return self

    @model_validator(mode="after")
    def validate_damage_consistency(self) -> "CheckoutRequest":
        """Validate damage reporting consistency."""
        if self.damages_reported and self.damage_charges == 0:
            if not self.damage_description:
                raise ValueError(
                    "Damage description required when damages are reported"
                )

        if self.damage_charges > 0 and not self.damages_reported:
            raise ValueError(
                "damages_reported must be True when damage charges are applied"
            )

        return self


class StatusUpdateRequest(BaseCreateSchema):
    """
    Student status update request.
    
    Used to update student status with proper documentation and validation.
    Maps to StudentStatusUpdate schema.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    student_id: str = Field(..., description="Student ID to update")
    new_status: StudentStatus = Field(..., description="New student status")
    effective_date: Date = Field(..., description="Status change effective date")
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Detailed reason for status change",
    )

    # Status-specific fields
    notice_period_days: Union[int, None] = Field(
        default=None,
        ge=0,
        le=90,
        description="Notice period duration in days (for notice period status)",
    )
    suspension_end_date: Union[Date, None] = Field(
        default=None,
        description="Suspension end date (for suspended status)",
    )
    graduation_date: Union[Date, None] = Field(
        default=None,
        description="Graduation date (for graduated status)",
    )

    # Administrative notes
    admin_notes: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Administrative notes and comments",
    )
    notification_required: bool = Field(
        default=True,
        description="Send notification to student about status change",
    )

    @model_validator(mode="after")
    def validate_status_specific_fields(self) -> "StatusUpdateRequest":
        """Validate status-specific required fields."""
        if self.new_status == StudentStatus.SUSPENDED and not self.suspension_end_date:
            raise ValueError("Suspension end date required for SUSPENDED status")

        if self.new_status == StudentStatus.NOTICE_PERIOD and not self.notice_period_days:
            raise ValueError("Notice period duration required for NOTICE_PERIOD status")

        if self.new_status == StudentStatus.GRADUATED and not self.graduation_date:
            raise ValueError("Graduation date required for GRADUATED status")

        return self

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, v: Date) -> Date:
        """Validate effective date."""
        from datetime import timedelta

        today = Date.today()
        if v > today + timedelta(days=30):
            raise ValueError(
                "Effective date cannot be more than 30 days in the future"
            )
        return v


class BulkStatusUpdate(BaseCreateSchema):
    """
    Bulk status update request.
    
    Used to update status for multiple students simultaneously.
    Maps to StudentBulkActionRequest schema.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    student_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of student IDs to update (max 100)",
    )
    new_status: StudentStatus = Field(..., description="New status for all students")
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Common reason for status updates",
    )
    effective_date: Union[Date, None] = Field(
        default=None,
        description="Effective date for all updates",
    )

    # Bulk operation options
    skip_on_error: bool = Field(
        default=True,
        description="Skip individual updates that fail, continue with rest",
    )
    send_notifications: bool = Field(
        default=True,
        description="Send notifications to all affected students",
    )
    generate_report: bool = Field(
        default=True,
        description="Generate bulk update report",
    )

    # Confirmation
    confirm_action: bool = Field(
        default=False,
        description="Explicit confirmation for bulk operation",
    )

    @field_validator("student_ids")
    @classmethod
    def validate_unique_student_ids(cls, v: List[str]) -> List[str]:
        """Ensure student IDs are unique."""
        if len(v) != len(set(v)):
            raise ValueError("Student IDs must be unique in bulk update")
        return v

    @model_validator(mode="after")
    def validate_confirmation(self) -> "BulkStatusUpdate":
        """Require explicit confirmation for bulk operations."""
        if not self.confirm_action:
            raise ValueError(
                "Bulk status update requires explicit confirmation (confirm_action=true)"
            )
        return self


class OnboardingResponse(BaseSchema):
    """Response schema for onboarding operations."""
    
    student_id: str = Field(..., description="Student ID")
    onboarding_status: str = Field(..., description="Onboarding result status")
    room_assigned: str = Field(..., description="Assigned room number")
    bed_assigned: str = Field(..., description="Assigned bed number")
    next_steps: List[str] = Field(default_factory=list, description="Next steps for student")
    onboarding_checklist_completed: bool = Field(..., description="All items completed")
    

class CheckoutResponse(BaseSchema):
    """Response schema for checkout operations."""
    
    student_id: str = Field(..., description="Student ID")
    checkout_status: str = Field(..., description="Checkout result status")
    clearance_status: str = Field(..., description="Overall clearance status")
    refund_amount: Union[MoneyAmount, None] = Field(default=None, description="Refund amount")
    clearance_certificate_number: Union[str, None] = Field(default=None, description="Certificate number")
    next_steps: List[str] = Field(default_factory=list, description="Next steps")