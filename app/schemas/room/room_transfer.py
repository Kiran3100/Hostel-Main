# --- File: app/schemas/room/room_transfer.py ---
"""
Room Transfer schemas with enhanced validation and status management.

Provides schemas for room transfer requests, approvals, history tracking,
and room swap operations between students.

Pydantic v2 Migration Notes:
- field_validator and model_validator already use v2 syntax
- All validators properly typed with @classmethod decorator
- mode="after" for model validators (v2 pattern)
- Date type works identically in v1 and v2
"""

from datetime import date as Date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, List, Union

from pydantic import Field, field_validator, model_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema, BaseResponseSchema
from app.schemas.common.enums import RoomType

__all__ = [
    "TransferStatus",
    "SwapStatus",
    "RoomTransferRequestCreate",
    "RoomTransferRequest",
    "RoomTransferUpdate",
    "RoomTransferHistory",
    "RoomSwapRequestCreate", 
    "RoomSwapRequest",
    "TransferApproval",
    "TransferRejection",
]


class TransferStatus(str, Enum):
    """
    Room transfer request status enumeration.
    
    Tracks the lifecycle of a transfer request from submission to completion.
    """
    
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class SwapStatus(str, Enum):
    """
    Room swap request status enumeration.
    
    Tracks the status of room swap requests between students.
    """
    
    PENDING = "pending"
    STUDENT_CONSENT_PENDING = "student_consent_pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class RoomTransferRequestCreate(BaseCreateSchema):
    """
    Schema for creating a room transfer request.
    
    Used when students submit requests to change rooms.
    """
    
    target_room_id: str = Field(
        ...,
        description="ID of the room to transfer to",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for requesting the transfer",
        examples=[
            "Need quieter environment for studies",
            "Roommate compatibility issues",
            "Prefer ground floor room due to mobility",
            "Want to be closer to friends",
        ],
    )
    preferred_move_date: Union[Date, None] = Field(
        default=None,
        description="Preferred date for the room change",
    )
    urgency_level: str = Field(
        default="normal",
        description="Urgency level of the transfer request",
        examples=["low", "normal", "high", "urgent"],
    )
    additional_notes: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Additional notes or specific requirements",
    )
    willing_to_pay_difference: bool = Field(
        default=True,
        description="Whether student is willing to pay price difference",
    )
    
    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate and clean transfer reason."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Transfer reason must be at least 10 characters")
        return v
    
    @field_validator("preferred_move_date")
    @classmethod
    def validate_preferred_move_date(cls, v: Union[Date, None]) -> Union[Date, None]:
        """Validate preferred move date is not in the past."""
        if v is not None:
            if v < Date.today():
                raise ValueError("Preferred move date cannot be in the past")
        return v
    
    @field_validator("urgency_level")
    @classmethod
    def validate_urgency_level(cls, v: str) -> str:
        """Validate urgency level."""
        valid_levels = ["low", "normal", "high", "urgent"]
        v = v.lower().strip()
        if v not in valid_levels:
            raise ValueError(f"Urgency level must be one of: {valid_levels}")
        return v


class RoomTransferRequest(BaseResponseSchema):
    """
    Complete room transfer request with all details.
    
    Represents a transfer request throughout its lifecycle.
    """
    
    # Basic info
    student_id: str = Field(..., description="Student requesting transfer")
    current_room_id: str = Field(..., description="Student's current room")
    current_room_number: str = Field(..., description="Current room number")
    target_room_id: str = Field(..., description="Requested target room")
    target_room_number: str = Field(..., description="Target room number")
    
    # Request details
    reason: str = Field(..., description="Transfer reason")
    preferred_move_date: Union[Date, None] = Field(
        default=None,
        description="Preferred move date",
    )
    urgency_level: str = Field(..., description="Urgency level")
    additional_notes: Union[str, None] = Field(
        default=None,
        description="Additional notes",
    )
    willing_to_pay_difference: bool = Field(
        ...,
        description="Willing to pay price difference",
    )
    
    # Status and workflow
    status: TransferStatus = Field(..., description="Current status")
    requested_by: str = Field(..., description="Who submitted the request")
    requested_at: datetime = Field(..., description="Request timestamp")
    
    # Review and approval
    reviewed_by: Union[str, None] = Field(
        default=None,
        description="Staff member who reviewed",
    )
    reviewed_at: Union[datetime, None] = Field(
        default=None,
        description="Review timestamp",
    )
    approved_by: Union[str, None] = Field(
        default=None,
        description="Who approved the transfer",
    )
    approved_at: Union[datetime, None] = Field(
        default=None,
        description="Approval timestamp",
    )
    rejection_reason: Union[str, None] = Field(
        default=None,
        description="Reason for rejection (if applicable)",
    )
    
    # Execution
    scheduled_move_date: Union[Date, None] = Field(
        default=None,
        description="Scheduled date for room change",
    )
    actual_move_date: Union[Date, None] = Field(
        default=None,
        description="Actual date when transfer was completed",
    )
    completed_by: Union[str, None] = Field(
        default=None,
        description="Staff who completed the transfer",
    )
    
    # Pricing impact
    current_rent_monthly: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Current monthly rent",
            ),
        ],
        None,
    ] = None
    target_rent_monthly: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Target room monthly rent",
            ),
        ],
        None,
    ] = None
    
    # Student info
    student_name: Union[str, None] = Field(
        default=None,
        description="Student name",
    )
    student_email: Union[str, None] = Field(
        default=None,
        description="Student email",
    )
    
    # Room details
    current_room_type: Union[RoomType, None] = Field(
        default=None,
        description="Current room type",
    )
    target_room_type: Union[RoomType, None] = Field(
        default=None,
        description="Target room type",
    )
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def rent_difference_monthly(self) -> Union[Decimal, None]:
        """Calculate monthly rent difference."""
        if self.current_rent_monthly is None or self.target_rent_monthly is None:
            return None
        return self.target_rent_monthly - self.current_rent_monthly
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_upgrade(self) -> Union[bool, None]:
        """Determine if transfer is an upgrade based on rent."""
        rent_diff = self.rent_difference_monthly
        if rent_diff is None:
            return None
        return rent_diff > 0
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def days_since_request(self) -> int:
        """Calculate days since request was submitted."""
        return (datetime.now() - self.requested_at).days
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_pending(self) -> bool:
        """Check if transfer is in pending status."""
        return self.status in [TransferStatus.PENDING, TransferStatus.UNDER_REVIEW]


class RoomTransferUpdate(BaseUpdateSchema):
    """
    Schema for updating transfer request details.
    
    Allows partial updates to transfer requests.
    """
    
    status: Union[TransferStatus, None] = Field(
        default=None,
        description="Transfer status",
    )
    reviewed_by: Union[str, None] = Field(
        default=None,
        description="Reviewer ID",
    )
    approved_by: Union[str, None] = Field(
        default=None,
        description="Approver ID",
    )
    rejection_reason: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Rejection reason",
    )
    scheduled_move_date: Union[Date, None] = Field(
        default=None,
        description="Scheduled move date",
    )
    actual_move_date: Union[Date, None] = Field(
        default=None,
        description="Actual move date",
    )
    completed_by: Union[str, None] = Field(
        default=None,
        description="Who completed the transfer",
    )
    admin_notes: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Internal admin notes",
    )


class RoomTransferHistory(BaseSchema):
    """
    Historical record of a completed room transfer.
    
    Provides a chronological view of room changes.
    """
    
    transfer_id: str = Field(..., description="Transfer request ID")
    student_id: str = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")
    
    # Room change details
    previous_room_id: str = Field(..., description="Previous room ID")
    previous_room_number: str = Field(..., description="Previous room number")
    new_room_id: str = Field(..., description="New room ID")
    new_room_number: str = Field(..., description="New room number")
    
    # Transfer details
    transfer_date: Date = Field(..., description="Date of transfer")
    reason: str = Field(..., description="Transfer reason")
    transfer_type: str = Field(
        default="request",
        description="Type of transfer (request, administrative, emergency)",
    )
    
    # Approval details
    approved_by: Union[str, None] = Field(
        default=None,
        description="Who approved the transfer",
    )
    approval_date: Union[Date, None] = Field(
        default=None,
        description="Approval date",
    )
    
    # Financial impact
    previous_rent: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="Previous monthly rent",
            ),
        ],
        None,
    ] = None
    new_rent: Union[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=10,
                decimal_places=2,
                description="New monthly rent",
            ),
        ],
        None,
    ] = None
    
    # Duration in previous room
    duration_in_previous_room_days: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Days spent in previous room",
    )
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def rent_change_amount(self) -> Union[Decimal, None]:
        """Calculate rent change amount."""
        if self.previous_rent is None or self.new_rent is None:
            return None
        return self.new_rent - self.previous_rent
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def was_upgrade(self) -> Union[bool, None]:
        """Determine if transfer was an upgrade."""
        rent_change = self.rent_change_amount
        if rent_change is None:
            return None
        return rent_change > 0


class RoomSwapRequestCreate(BaseCreateSchema):
    """
    Schema for creating a room swap request between two students.
    
    Allows students to exchange rooms with proper validation.
    """
    
    student_2_id: str = Field(
        ...,
        description="Second student ID (first student is from URL path)",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for room swap",
        examples=[
            "Better compatibility with roommates",
            "Study preferences alignment",
            "Closer to common areas",
        ],
    )
    student_1_consent: bool = Field(
        default=True,
        description="First student's consent to swap",
    )
    student_2_consent: bool = Field(
        default=False,
        description="Second student's consent to swap",
    )
    preferred_swap_date: Union[Date, None] = Field(
        default=None,
        description="Preferred date for the swap",
    )
    additional_notes: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Additional notes about the swap",
    )
    
    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate swap reason."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Swap reason must be at least 10 characters")
        return v
    
    @field_validator("preferred_swap_date")
    @classmethod
    def validate_preferred_swap_date(cls, v: Union[Date, None]) -> Union[Date, None]:
        """Validate preferred swap date."""
        if v is not None:
            if v < Date.today():
                raise ValueError("Preferred swap date cannot be in the past")
        return v


class RoomSwapRequest(BaseResponseSchema):
    """
    Complete room swap request between two students.
    
    Manages the exchange of rooms between students.
    """
    
    # Student details
    student_1_id: str = Field(..., description="First student ID")
    student_1_name: str = Field(..., description="First student name")
    student_1_room_id: str = Field(..., description="First student's room ID")
    student_1_room_number: str = Field(..., description="First student's room number")
    student_1_consent: bool = Field(..., description="First student's consent")
    
    student_2_id: str = Field(..., description="Second student ID")
    student_2_name: str = Field(..., description="Second student name")
    student_2_room_id: str = Field(..., description="Second student's room ID")
    student_2_room_number: str = Field(..., description="Second student's room number")
    student_2_consent: bool = Field(..., description="Second student's consent")
    
    # Swap details
    reason: str = Field(..., description="Swap reason")
    status: SwapStatus = Field(..., description="Swap status")
    preferred_swap_date: Union[Date, None] = Field(
        default=None,
        description="Preferred swap date",
    )
    additional_notes: Union[str, None] = Field(
        default=None,
        description="Additional notes",
    )
    
    # Request workflow
    requested_by: str = Field(..., description="Who initiated the swap")
    requested_at: datetime = Field(..., description="Request timestamp")
    
    # Approvals
    approved_by: Union[str, None] = Field(
        default=None,
        description="Admin who approved",
    )
    approved_at: Union[datetime, None] = Field(
        default=None,
        description="Approval timestamp",
    )
    rejection_reason: Union[str, None] = Field(
        default=None,
        description="Rejection reason",
    )
    
    # Execution
    scheduled_swap_date: Union[Date, None] = Field(
        default=None,
        description="Scheduled swap date",
    )
    actual_swap_date: Union[Date, None] = Field(
        default=None,
        description="Actual swap completion date",
    )
    completed_by: Union[str, None] = Field(
        default=None,
        description="Staff who completed the swap",
    )
    
    # Room compatibility
    rooms_compatible: Union[bool, None] = Field(
        default=None,
        description="Whether rooms are compatible for swap",
    )
    price_difference_notes: Union[str, None] = Field(
        default=None,
        description="Notes about any price differences",
    )
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def both_students_consented(self) -> bool:
        """Check if both students have given consent."""
        return self.student_1_consent and self.student_2_consent
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def can_be_approved(self) -> bool:
        """Check if swap can be approved."""
        return (
            self.both_students_consented and
            self.status == SwapStatus.PENDING and
            self.rooms_compatible is not False
        )
    
    @computed_field  # type: ignore[prop-decorator]
    @property
    def days_since_request(self) -> int:
        """Days since swap was requested."""
        return (datetime.now() - self.requested_at).days


class TransferApproval(BaseCreateSchema):
    """
    Schema for approving a transfer request.
    
    Captures approval details and scheduling information.
    """
    
    approval_notes: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Notes about the approval",
    )
    scheduled_move_date: Union[Date, None] = Field(
        default=None,
        description="When the transfer should take effect",
    )
    conditions: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Any conditions for the transfer",
    )
    
    @field_validator("scheduled_move_date")
    @classmethod
    def validate_scheduled_move_date(cls, v: Union[Date, None]) -> Union[Date, None]:
        """Validate scheduled move date."""
        if v is not None:
            if v < Date.today():
                raise ValueError("Scheduled move date cannot be in the past")
        return v


class TransferRejection(BaseCreateSchema):
    """
    Schema for rejecting a transfer request.
    
    Captures rejection details and reasoning.
    """
    
    rejection_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Detailed reason for rejection",
        examples=[
            "Target room is not available",
            "Insufficient justification provided",
            "Student has pending payments",
            "Transfer would violate occupancy limits",
        ],
    )
    suggestions: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Alternative suggestions or recommendations",
    )
    can_reapply: bool = Field(
        default=True,
        description="Whether student can reapply later",
    )
    reapply_after_date: Union[Date, None] = Field(
        default=None,
        description="Earliest date for reapplication",
    )
    
    @field_validator("rejection_reason")
    @classmethod
    def validate_rejection_reason(cls, v: str) -> str:
        """Validate rejection reason."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Rejection reason must be at least 10 characters")
        return v
    
    @model_validator(mode="after")
    def validate_reapply_date(self) -> "TransferRejection":
        """Validate reapply date logic."""
        if self.reapply_after_date and self.can_reapply is False:
            raise ValueError("Cannot set reapply date if reapplication is not allowed")
        
        if self.reapply_after_date and self.reapply_after_date < Date.today():
            raise ValueError("Reapply date cannot be in the past")
        
        return self