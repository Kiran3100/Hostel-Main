# --- File: app/schemas/room/bed_response.py ---
"""
Bed response schemas for API responses.

Provides various response formats for bed data including
availability, assignments, and history.

Pydantic v2 Migration Notes:
- Uses Annotated pattern for Decimal fields with precision constraints
- @computed_field with @property decorator for computed properties
- All Decimal fields now have explicit max_digits/decimal_places constraints
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Annotated, List, Optional

from pydantic import Field, computed_field

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import BedStatus

__all__ = [
    "BedResponse",
    "BedAvailability",
    "BedAssignment",
    "BedHistory",
    "BedAssignmentHistory",
    "BedDetailedStatus",
]


class BedResponse(BaseResponseSchema):
    """
    Standard bed response schema.
    
    Basic bed information for general API responses.
    """

    room_id: str = Field(..., description="Room ID")
    bed_number: str = Field(..., description="Bed identifier")
    is_occupied: bool = Field(..., description="Currently occupied")
    status: BedStatus = Field(..., description="Bed status")
    current_student_id: Optional[str] = Field(
        default=None,
        description="Current occupant ID",
    )
    occupied_from: Optional[Date] = Field(
        default=None,
        description="Occupancy start date",
    )

    @computed_field  # type: ignore[misc]
    @property
    def is_available(self) -> bool:
        """Check if bed is available for assignment."""
        return self.status == BedStatus.AVAILABLE and not self.is_occupied


class BedAvailability(BaseSchema):
    """
    Bed availability information.
    
    Detailed availability status for booking purposes.
    """

    bed_id: str = Field(..., description="Bed ID")
    room_id: str = Field(..., description="Room ID")
    room_number: str = Field(..., description="Room number")
    bed_number: str = Field(..., description="Bed identifier")
    
    # Availability
    is_available: bool = Field(..., description="Available for assignment")
    status: BedStatus = Field(..., description="Current status")
    available_from: Optional[Date] = Field(
        default=None,
        description="Date when bed becomes available",
    )
    
    # Current occupant (if any)
    current_student_name: Optional[str] = Field(
        default=None,
        description="Current occupant name",
    )
    current_student_id: Optional[str] = Field(
        default=None,
        description="Current occupant ID",
    )
    expected_vacate_date: Optional[Date] = Field(
        default=None,
        description="Expected checkout date",
    )
    
    # Room info with proper Decimal constraints
    room_type: str = Field(..., description="Room type")
    price_monthly: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Monthly rent",
        ),
    ]
    is_ac: bool = Field(..., description="AC available in room")
    has_attached_bathroom: bool = Field(
        ...,
        description="Attached bathroom",
    )

    @computed_field  # type: ignore[misc]
    @property
    def days_until_available(self) -> Optional[int]:
        """Calculate days until bed becomes available."""
        if not self.available_from:
            return None
        if self.is_available:
            return 0
        today = Date.today()
        if self.available_from <= today:
            return 0
        return (self.available_from - today).days


class BedAssignment(BaseResponseSchema):
    """
    Bed assignment details.
    
    Complete information about a bed assignment.
    """

    bed_id: str = Field(..., description="Bed ID")
    room_id: str = Field(..., description="Room ID")
    room_number: str = Field(..., description="Room number")
    bed_number: str = Field(..., description="Bed identifier")
    
    # Student info
    student_id: str = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")
    student_email: Optional[str] = Field(
        default=None,
        description="Student email",
    )
    student_phone: Optional[str] = Field(
        default=None,
        description="Student phone",
    )
    
    # Assignment dates
    occupied_from: Date = Field(..., description="Occupancy start date")
    expected_vacate_date: Optional[Date] = Field(
        default=None,
        description="Expected checkout date",
    )
    actual_vacate_date: Optional[Date] = Field(
        default=None,
        description="Actual checkout date (if completed)",
    )
    
    # Pricing with proper Decimal constraints
    monthly_rent: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Monthly rent amount",
        ),
    ]
    
    # Related records
    booking_id: Optional[str] = Field(
        default=None,
        description="Related booking ID",
    )
    
    # Status
    is_active: bool = Field(
        default=True,
        description="Assignment is currently active",
    )
    
    # Metadata
    assigned_at: datetime = Field(..., description="Assignment timestamp")
    assigned_by: Optional[str] = Field(
        default=None,
        description="Admin who created assignment",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Assignment notes",
    )

    @computed_field  # type: ignore[misc]
    @property
    def days_occupied(self) -> int:
        """Calculate days occupied."""
        end_date = self.actual_vacate_date or Date.today()
        return (end_date - self.occupied_from).days

    @computed_field  # type: ignore[misc]
    @property
    def expected_duration_days(self) -> Optional[int]:
        """Calculate expected duration in days."""
        if not self.expected_vacate_date:
            return None
        return (self.expected_vacate_date - self.occupied_from).days


class BedAssignmentHistory(BaseSchema):
    """
    Individual bed assignment history entry.
    
    Historical record of a single bed assignment.
    """

    assignment_id: str = Field(..., description="Assignment ID")
    student_id: str = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")
    move_in_date: Date = Field(..., description="Move-in date")
    move_out_date: Optional[Date] = Field(
        default=None,
        description="Move-out date (null if current)",
    )
    duration_days: Optional[int] = Field(
        default=None,
        description="Total duration in days",
    )
    # Pricing fields with proper Decimal constraints
    monthly_rent: Annotated[
        Decimal,
        Field(
            ge=0,
            max_digits=10,
            decimal_places=2,
            description="Monthly rent paid",
        ),
    ]
    total_rent_paid: Annotated[
        Decimal,
        Field(
            default=Decimal("0.00"),
            ge=0,
            max_digits=12,
            decimal_places=2,
            description="Total rent paid during stay",
        ),
    ]
    is_current: bool = Field(
        default=False,
        description="Currently active assignment",
    )

    @computed_field  # type: ignore[misc]
    @property
    def duration_months(self) -> Optional[Decimal]:
        """Calculate duration in months."""
        if self.duration_days is None:
            return None
        return Decimal(self.duration_days / 30).quantize(Decimal("0.1"))


class BedHistory(BaseSchema):
    """
    Complete bed occupancy history.
    
    Historical timeline of all assignments for a bed.
    """

    bed_id: str = Field(..., description="Bed ID")
    room_number: str = Field(..., description="Room number")
    bed_number: str = Field(..., description="Bed identifier")
    
    # Current status
    current_status: BedStatus = Field(..., description="Current bed status")
    is_currently_occupied: bool = Field(
        ...,
        description="Currently occupied",
    )
    
    # Assignment history
    assignments: List[BedAssignmentHistory] = Field(
        default_factory=list,
        description="Historical assignments (newest first)",
    )
    
    # Statistics
    total_assignments: int = Field(
        default=0,
        ge=0,
        description="Total number of assignments",
    )
    total_occupancy_days: int = Field(
        default=0,
        ge=0,
        description="Total days occupied",
    )
    average_stay_duration_days: Optional[
        Annotated[
            Decimal,
            Field(
                ge=0,
                max_digits=8,
                decimal_places=1,
                description="Average stay duration",
            ),
        ]
    ] = None
    last_occupied_date: Optional[Date] = Field(
        default=None,
        description="Last occupancy date",
    )

    @computed_field  # type: ignore[misc]
    @property
    def utilization_rate(self) -> Optional[Decimal]:
        """
        Calculate utilization rate since first assignment.
        
        Returns percentage of time bed has been occupied.
        """
        if not self.assignments:
            return None
        
        # Get earliest assignment
        earliest = min(a.move_in_date for a in self.assignments)
        total_days = (Date.today() - earliest).days
        
        if total_days == 0:
            return None
        
        return Decimal(
            (self.total_occupancy_days / total_days * 100)
        ).quantize(Decimal("0.01"))


class BedDetailedStatus(BaseResponseSchema):
    """
    Detailed bed status with comprehensive information.
    
    Extended bed information including maintenance and condition.
    """

    room_id: str = Field(..., description="Room ID")
    room_number: str = Field(..., description="Room number")
    bed_number: str = Field(..., description="Bed identifier")
    
    # Status
    status: BedStatus = Field(..., description="Current status")
    is_occupied: bool = Field(..., description="Occupied flag")
    is_available: bool = Field(..., description="Available for assignment")
    
    # Current assignment
    current_student_id: Optional[str] = Field(
        default=None,
        description="Current student ID",
    )
    current_student_name: Optional[str] = Field(
        default=None,
        description="Current student name",
    )
    occupied_from: Optional[Date] = Field(
        default=None,
        description="Current occupancy start date",
    )
    expected_vacate_date: Optional[Date] = Field(
        default=None,
        description="Expected checkout date",
    )
    
    # Maintenance
    last_maintenance_date: Optional[Date] = Field(
        default=None,
        description="Last maintenance date",
    )
    next_scheduled_maintenance: Optional[Date] = Field(
        default=None,
        description="Next scheduled maintenance",
    )
    maintenance_notes: Optional[str] = Field(
        default=None,
        description="Maintenance notes",
    )
    
    # Condition
    condition_rating: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Condition rating (1-5, 5 being excellent)",
    )
    last_inspection_date: Optional[Date] = Field(
        default=None,
        description="Last inspection date",
    )
    reported_issues: List[str] = Field(
        default_factory=list,
        description="Currently reported issues",
    )
    
    # History stats
    total_assignments: int = Field(
        default=0,
        ge=0,
        description="Total historical assignments",
    )
    average_stay_duration_days: Optional[int] = Field(
        default=None,
        ge=0,
        description="Average stay duration",
    )
    
    # Metadata
    notes: Optional[str] = Field(
        default=None,
        description="General notes",
    )
    last_status_change: Optional[datetime] = Field(
        default=None,
        description="Last status change timestamp",
    )

    @computed_field  # type: ignore[misc]
    @property
    def needs_maintenance(self) -> bool:
        """Check if bed needs maintenance."""
        # Needs maintenance if:
        # 1. Status is maintenance
        # 2. Has reported issues
        # 3. Condition rating is low (1-2)
        if self.status == BedStatus.MAINTENANCE:
            return True
        if self.reported_issues:
            return True
        if self.condition_rating and self.condition_rating <= 2:
            return True
        return False

    @computed_field  # type: ignore[misc]
    @property
    def current_occupancy_days(self) -> Optional[int]:
        """Calculate days of current occupancy."""
        if not self.occupied_from:
            return None
        return (Date.today() - self.occupied_from).days