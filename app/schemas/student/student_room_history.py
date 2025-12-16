"""
Student room history and transfer schemas with enhanced validation.

Provides schemas for tracking room assignments, transfers, and
movement history for students.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Union, Annotated

from pydantic import Field, field_validator, model_validator, computed_field, ConfigDict

from app.schemas.common.base import (
    BaseCreateSchema,
    BaseResponseSchema,
    BaseSchema,
)

__all__ = [
    "RoomHistoryResponse",
    "RoomHistoryItem",
    "RoomTransferRequest",
    "RoomTransferApproval",
    "RoomTransferStatus",
    "BulkRoomTransfer",
    "SingleTransfer",
    "RoomSwapRequest",
]

# Type aliases for Pydantic v2 decimal constraints
MoneyAmount = Annotated[Decimal, Field(max_digits=10, decimal_places=2, ge=0)]


class RoomHistoryItem(BaseResponseSchema):
    """
    Individual room history entry.
    
    Represents a single room assignment period in student's history.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    hostel_id: str = Field(..., description="Hostel ID")
    hostel_name: str = Field(..., description="Hostel name")
    room_id: str = Field(..., description="Room ID")
    room_number: str = Field(..., description="Room number")
    room_type: str = Field(..., description="Room type")
    floor_number: Union[int, None] = Field(default=None, description="Floor number")
    wing: Union[str, None] = Field(default=None, description="Wing/Block")
    bed_id: Union[str, None] = Field(default=None, description="Bed ID")
    bed_number: Union[str, None] = Field(default=None, description="Bed number")

    # Duration
    move_in_date: Date = Field(..., description="Move-in Date")
    move_out_date: Union[Date, None] = Field(
        default=None,
        description="Move-out Date (null if current)",
    )
    duration_days: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Total duration in days",
    )

    # Financial
    rent_amount: Union[MoneyAmount, None] = Field(
        default=None,
        description="Monthly rent for this assignment",
    )
    total_rent_paid: Union[MoneyAmount, None] = Field(
        default=None,
        description="Total rent paid during this period",
    )

    # Transfer details
    reason: Union[str, None] = Field(
        default=None,
        description="Reason for assignment/transfer",
    )
    transfer_type: Union[str, None] = Field(
        default=None,
        description="Transfer type (initial, request, admin)",
    )

    # Audit
    requested_by: Union[str, None] = Field(
        default=None,
        description="User who requested transfer",
    )
    approved_by: Union[str, None] = Field(
        default=None,
        description="Admin who approved assignment",
    )
    assigned_at: datetime = Field(
        ...,
        description="Assignment timestamp",
    )

    @computed_field
    @property
    def is_current(self) -> bool:
        """Check if this is the current assignment."""
        return self.move_out_date is None

    @computed_field
    @property
    def duration_months(self) -> Union[Decimal, None]:
        """Calculate duration in months."""
        if self.duration_days is None:
            return None
        return Decimal(self.duration_days / 30).quantize(Decimal("0.1"))


class RoomHistoryResponse(BaseSchema):
    """
    Complete student room history.
    
    Chronological list of all room assignments for a student.
    """

    student_id: str = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")
    hostel_id: str = Field(..., description="Current hostel ID")
    hostel_name: str = Field(..., description="Current hostel name")

    # Current assignment
    current_room: Union[str, None] = Field(
        default=None,
        description="Current room number",
    )
    current_bed: Union[str, None] = Field(
        default=None,
        description="Current bed number",
    )

    # History
    room_history: List[RoomHistoryItem] = Field(
        ...,
        description="Room assignment history (newest first)",
    )

    # Statistics
    total_assignments: int = Field(
        default=0,
        ge=0,
        description="Total number of room assignments",
    )
    total_transfers: int = Field(
        default=0,
        ge=0,
        description="Total number of room transfers",
    )

    @computed_field
    @property
    def has_changed_rooms(self) -> bool:
        """Check if student has changed rooms."""
        return self.total_assignments > 1


class RoomTransferRequest(BaseCreateSchema):
    """
    Request room transfer.
    
    Student-initiated or admin-initiated room transfer request.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    student_id: str = Field(
        ...,
        description="Student ID requesting transfer",
    )
    current_room_id: str = Field(
        ...,
        description="Current room ID",
    )
    requested_room_id: str = Field(
        ...,
        description="Desired room ID",
    )
    requested_bed_id: Union[str, None] = Field(
        default=None,
        description="Desired bed ID (if specific bed requested)",
    )

    transfer_date: Date = Field(
        ...,
        description="Desired transfer Date",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Detailed reason for transfer",
        examples=[
            "Room too small for my belongings",
            "Prefer ground floor room",
            "Request to be closer to friends",
            "Medical reasons - need AC room",
        ],
    )

    # Preferences
    accept_price_difference: bool = Field(
        default=False,
        description="Accept if new room has different rent",
    )
    flexible_on_bed: bool = Field(
        default=True,
        description="Flexible on specific bed (any bed in room)",
    )

    # Priority
    priority: str = Field(
        default="normal",
        pattern=r"^(low|normal|high|urgent)$",
        description="Transfer priority/urgency",
    )

    # Supporting documents
    supporting_documents: List[str] = Field(
        default_factory=list,
        description="URLs of supporting documents (medical certificates, etc.)",
    )

    @field_validator("transfer_date")
    @classmethod
    def validate_transfer_date(cls, v: Date) -> Date:
        """Validate transfer Date is reasonable."""
        from datetime import timedelta

        today = Date.today()

        # Must be at least today or future
        if v < today:
            raise ValueError("Transfer Date cannot be in the past")

        # Warn if too far in future (more than 90 days)
        if v > today + timedelta(days=90):
            raise ValueError(
                "Transfer Date cannot be more than 90 days in the future"
            )

        return v

    @model_validator(mode="after")
    def validate_different_room(self) -> "RoomTransferRequest":
        """Ensure requested room is different from current room."""
        if self.current_room_id == self.requested_room_id:
            raise ValueError(
                "Requested room must be different from current room"
            )
        return self


class RoomTransferApproval(BaseCreateSchema):
    """
    Approve or reject room transfer request.
    
    Admin action to process transfer requests.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    transfer_request_id: str = Field(
        ...,
        description="Transfer request ID to process",
    )
    approved: bool = Field(
        ...,
        description="Approval decision (true=approved, false=rejected)",
    )

    # If approved
    new_room_id: Union[str, None] = Field(
        default=None,
        description="Approved room (may differ from requested)",
    )
    new_bed_id: Union[str, None] = Field(
        default=None,
        description="Assigned bed in new room",
    )
    transfer_date: Union[Date, None] = Field(
        default=None,
        description="Approved transfer Date (may differ from requested)",
    )

    # If rejected
    rejection_reason: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Detailed rejection reason",
        examples=[
            "Requested room not available",
            "Transfer not justified",
            "Pending payment dues must be cleared first",
        ],
    )

    # Financial implications - Fixed for Pydantic v2
    rent_adjustment: Union[Decimal, None] = Field(
        default=None,
        description="Monthly rent adjustment (positive=increase, negative=decrease)",
    )
    additional_charges: Union[MoneyAmount, None] = Field(
        default=None,
        description="One-time transfer charges",
    )
    prorated_rent_calculation: bool = Field(
        default=True,
        description="Calculate prorated rent for partial month",
    )

    # Notes
    admin_notes: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Administrative notes",
    )

    @model_validator(mode="after")
    def validate_approval_requirements(self) -> "RoomTransferApproval":
        """Validate approval-specific required fields."""
        if self.approved:
            # Approved transfers require room and bed assignment
            if not self.new_room_id:
                raise ValueError(
                    "new_room_id is required when approving transfer"
                )
            if not self.new_bed_id:
                raise ValueError(
                    "new_bed_id is required when approving transfer"
                )
            if not self.transfer_date:
                raise ValueError(
                    "transfer_date is required when approving transfer"
                )
        else:
            # Rejected transfers require rejection reason
            if not self.rejection_reason:
                raise ValueError(
                    "rejection_reason is required when rejecting transfer"
                )

        return self

    @field_validator("transfer_date")
    @classmethod
    def validate_transfer_date(cls, v: Union[Date, None]) -> Union[Date, None]:
        """Validate transfer Date."""
        if v is not None:
            from datetime import timedelta

            today = Date.today()
            if v < today:
                raise ValueError("Transfer Date cannot be in the past")
            if v > today + timedelta(days=90):
                raise ValueError(
                    "Transfer Date cannot be more than 90 days in the future"
                )
        return v


class RoomTransferStatus(BaseSchema):
    """
    Room transfer request status.
    
    Current status and details of a transfer request.
    """

    request_id: str = Field(..., description="Transfer request ID")
    student_id: str = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")

    # Room details
    current_room: str = Field(..., description="Current room number")
    current_bed: Union[str, None] = Field(default=None, description="Current bed")
    requested_room: str = Field(..., description="Requested room number")
    requested_bed: Union[str, None] = Field(default=None, description="Requested bed")
    approved_room: Union[str, None] = Field(
        default=None,
        description="Approved room (if different)",
    )
    approved_bed: Union[str, None] = Field(
        default=None,
        description="Approved bed",
    )

    # Dates
    transfer_date: Date = Field(..., description="Transfer Date")
    requested_at: datetime = Field(..., description="Request timestamp")
    processed_at: Union[datetime, None] = Field(
        default=None,
        description="Processing timestamp",
    )

    # Status
    status: str = Field(
        ...,
        pattern=r"^(pending|approved|rejected|completed|cancelled)$",
        description="Request status",
    )
    priority: str = Field(..., description="Request priority")

    # Details
    reason: str = Field(..., description="Transfer reason")
    approval_notes: Union[str, None] = Field(
        default=None,
        description="Approval/rejection notes",
    )
    processed_by: Union[str, None] = Field(
        default=None,
        description="Admin who processed",
    )
    processed_by_name: Union[str, None] = Field(
        default=None,
        description="Admin name",
    )

    # Financial - Fixed for Pydantic v2
    rent_adjustment: Union[Decimal, None] = Field(
        default=None,
        description="Rent adjustment",
    )
    additional_charges: Union[MoneyAmount, None] = Field(
        default=None,
        description="Transfer charges",
    )

    @computed_field
    @property
    def is_pending(self) -> bool:
        """Check if request is still pending."""
        return self.status == "pending"

    @computed_field
    @property
    def days_pending(self) -> Union[int, None]:
        """Calculate days request has been pending."""
        if self.status != "pending":
            return None
        return (datetime.now() - self.requested_at).days


class SingleTransfer(BaseSchema):
    """
    Single transfer in bulk operation.
    
    Represents one student transfer in a bulk transfer operation.
    """

    student_id: str = Field(..., description="Student ID to transfer")
    new_room_id: str = Field(..., description="New room ID")
    new_bed_id: Union[str, None] = Field(
        default=None,
        description="New bed ID (optional, auto-assign if not specified)",
    )
    reason: Union[str, None] = Field(
        default=None,
        max_length=200,
        description="Transfer reason (optional, uses bulk reason if not specified)",
    )


class BulkRoomTransfer(BaseCreateSchema):
    """
    Bulk room transfer (admin only).
    
    Transfer multiple students simultaneously (e.g., floor reorganization).
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    transfers: List[SingleTransfer] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of transfers to perform (max 50)",
    )
    transfer_date: Date = Field(
        ...,
        description="Transfer Date for all students",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Common reason for bulk transfer",
        examples=[
            "Floor renovation - temporary relocation",
            "Wing reorganization",
            "Room type consolidation",
        ],
    )

    # Options
    skip_on_error: bool = Field(
        default=True,
        description="Skip individual transfers that fail, continue with rest",
    )
    send_notifications: bool = Field(
        default=True,
        description="Send notifications to affected students",
    )
    prorated_rent: bool = Field(
        default=True,
        description="Calculate prorated rent for all transfers",
    )

    # Confirmation
    confirm_bulk_transfer: bool = Field(
        default=False,
        description="Explicit confirmation for bulk operation",
    )

    @field_validator("transfers")
    @classmethod
    def validate_unique_students(cls, v: List[SingleTransfer]) -> List[SingleTransfer]:
        """Ensure each student appears only once."""
        student_ids = [t.student_id for t in v]
        if len(student_ids) != len(set(student_ids)):
            raise ValueError(
                "Each student can only be transferred once in bulk operation"
            )
        return v

    @field_validator("transfer_date")
    @classmethod
    def validate_transfer_date(cls, v: Date) -> Date:
        """Validate transfer Date."""
        from datetime import timedelta

        today = Date.today()
        if v < today:
            raise ValueError("Transfer Date cannot be in the past")
        if v > today + timedelta(days=30):
            raise ValueError(
                "Bulk transfer Date cannot be more than 30 days in the future"
            )
        return v

    @model_validator(mode="after")
    def validate_confirmation(self) -> "BulkRoomTransfer":
        """Require explicit confirmation for bulk operations."""
        if not self.confirm_bulk_transfer:
            raise ValueError(
                "Bulk transfer requires explicit confirmation (confirm_bulk_transfer=true)"
            )
        return self


class RoomSwapRequest(BaseCreateSchema):
    """
    Request room swap between two students.
    
    Mutual room exchange between two students.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    student_1_id: str = Field(
        ...,
        description="First student ID",
    )
    student_2_id: str = Field(
        ...,
        description="Second student ID",
    )
    swap_date: Date = Field(
        ...,
        description="Swap Date",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for swap",
        examples=[
            "Mutual preference exchange",
            "Closer to respective friends",
            "Room size preference swap",
        ],
    )

    # Consent
    student_1_consent: bool = Field(
        default=False,
        description="First student consent",
    )
    student_2_consent: bool = Field(
        default=False,
        description="Second student consent",
    )

    # Financial
    handle_rent_difference: bool = Field(
        default=True,
        description="Automatically handle rent difference between rooms",
    )

    @field_validator("swap_date")
    @classmethod
    def validate_swap_date(cls, v: Date) -> Date:
        """Validate swap Date."""
        from datetime import timedelta

        today = Date.today()
        if v < today:
            raise ValueError("Swap Date cannot be in the past")
        if v > today + timedelta(days=30):
            raise ValueError(
                "Swap Date cannot be more than 30 days in the future"
            )
        return v

    @model_validator(mode="after")
    def validate_different_students(self) -> "RoomSwapRequest":
        """Ensure students are different."""
        if self.student_1_id == self.student_2_id:
            raise ValueError(
                "Cannot swap room for the same student"
            )
        return self

    @model_validator(mode="after")
    def validate_consent(self) -> "RoomSwapRequest":
        """Validate both students have consented."""
        if not self.student_1_consent or not self.student_2_consent:
            raise ValueError(
                "Both students must consent to room swap"
            )
        return self