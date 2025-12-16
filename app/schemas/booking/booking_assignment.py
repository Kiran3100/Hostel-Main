"""
Booking room and bed assignment schemas.

This module defines schemas for assigning rooms and beds to bookings,
including bulk operations and reassignment workflows.
"""

from datetime import date as Date, datetime
from typing import List, Union
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "RoomAssignment",
    "BedAssignment",
    "AssignmentRequest",
    "BulkAssignmentRequest",
    "SingleAssignment",
    "AssignmentResponse",
    "ReassignmentRequest",
]


class RoomAssignment(BaseSchema):
    """
    Room assignment record for a booking.
    
    Represents the assignment of a specific room to a booking.
    """

    booking_id: UUID = Field(
        ...,
        description="Booking identifier",
    )
    booking_reference: str = Field(
        ...,
        description="Booking reference number",
    )

    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )
    room_id: UUID = Field(
        ...,
        description="Assigned room identifier",
    )
    room_number: str = Field(
        ...,
        description="Assigned room number",
    )
    room_type: str = Field(
        ...,
        description="Room type",
    )

    assigned_by: UUID = Field(
        ...,
        description="Admin who made the assignment",
    )
    assigned_by_name: str = Field(
        ...,
        description="Name of admin who assigned",
    )
    assigned_at: datetime = Field(
        ...,
        description="Assignment timestamp",
    )

    check_in_date: Date = Field(
        ...,
        description="Scheduled check-in Date",
    )


class BedAssignment(BaseSchema):
    """
    Bed assignment record for a booking.
    
    Represents the assignment of a specific bed within a room.
    """

    booking_id: UUID = Field(
        ...,
        description="Booking identifier",
    )
    booking_reference: str = Field(
        ...,
        description="Booking reference number",
    )

    room_id: UUID = Field(
        ...,
        description="Room identifier",
    )
    room_number: str = Field(
        ...,
        description="Room number",
    )
    bed_id: UUID = Field(
        ...,
        description="Assigned bed identifier",
    )
    bed_number: str = Field(
        ...,
        description="Assigned bed number",
    )

    assigned_by: UUID = Field(
        ...,
        description="Admin who made the assignment",
    )
    assigned_by_name: str = Field(
        ...,
        description="Name of admin who assigned",
    )
    assigned_at: datetime = Field(
        ...,
        description="Assignment timestamp",
    )


class AssignmentRequest(BaseCreateSchema):
    """
    Request to assign room and bed to a booking.
    
    Used by admins to manually assign specific room and bed
    to an approved booking.
    """

    booking_id: UUID = Field(
        ...,
        description="Booking ID to assign room/bed to",
    )
    room_id: UUID = Field(
        ...,
        description="Room ID to assign",
    )
    bed_id: UUID = Field(
        ...,
        description="Bed ID to assign within the room",
    )

    # Optional Override
    override_check_in_date: Union[Date, None] = Field(
        None,
        description="Override the preferred check-in Date if needed",
    )

    notes: Union[str, None] = Field(
        None,
        max_length=500,
        description="Assignment notes for internal reference",
    )

    @field_validator("override_check_in_date")
    @classmethod
    def validate_override_date(cls, v: Union[Date, None]) -> Union[Date, None]:
        """Validate override check-in Date."""
        if v is not None and v < Date.today():
            raise ValueError(
                f"Override check-in Date ({v}) cannot be in the past"
            )
        return v

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, v: Union[str, None]) -> Union[str, None]:
        """Clean notes field."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


class SingleAssignment(BaseSchema):
    """
    Single assignment in bulk operation.
    
    Minimal schema for individual assignment within bulk request.
    """

    booking_id: UUID = Field(
        ...,
        description="Booking ID",
    )
    room_id: UUID = Field(
        ...,
        description="Room ID to assign",
    )
    bed_id: UUID = Field(
        ...,
        description="Bed ID to assign",
    )


class BulkAssignmentRequest(BaseCreateSchema):
    """
    Bulk assign rooms to multiple bookings.
    
    Used for batch assignment operations.
    """

    assignments: List[SingleAssignment] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of room/bed assignments (max 100)",
    )

    auto_approve: bool = Field(
        False,
        description="Automatically approve bookings after assignment",
    )

    @field_validator("assignments")
    @classmethod
    def validate_assignments(cls, v: List[SingleAssignment]) -> List[SingleAssignment]:
        """Validate assignments list."""
        if len(v) == 0:
            raise ValueError("At least one assignment is required")
        
        if len(v) > 100:
            raise ValueError("Maximum 100 assignments allowed per bulk operation")
        
        # Check for duplicate booking IDs
        booking_ids = [a.booking_id for a in v]
        if len(booking_ids) != len(set(booking_ids)):
            raise ValueError("Duplicate booking IDs found in assignments list")
        
        return v


class AssignmentResponse(BaseSchema):
    """
    Response after assignment operation.
    
    Provides feedback on assignment success and next steps.
    """

    booking_id: UUID = Field(
        ...,
        description="Booking identifier",
    )
    booking_reference: str = Field(
        ...,
        description="Booking reference",
    )

    room_assigned: bool = Field(
        ...,
        description="Whether room was successfully assigned",
    )
    room_number: Union[str, None] = Field(
        None,
        description="Assigned room number if successful",
    )
    bed_number: Union[str, None] = Field(
        None,
        description="Assigned bed number if successful",
    )

    message: str = Field(
        ...,
        description="Result message",
    )
    next_steps: List[str] = Field(
        default_factory=list,
        description="List of next steps required",
    )


class ReassignmentRequest(BaseCreateSchema):
    """
    Request to reassign booking to different room/bed.
    
    Used when guest needs to be moved to a different room
    or bed after initial assignment.
    """

    booking_id: UUID = Field(
        ...,
        description="Booking ID to reassign",
    )
    current_room_id: UUID = Field(
        ...,
        description="Current room assignment",
    )
    new_room_id: UUID = Field(
        ...,
        description="New room to assign",
    )
    new_bed_id: UUID = Field(
        ...,
        description="New bed to assign",
    )

    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for reassignment",
    )
    notify_guest: bool = Field(
        True,
        description="Send notification to guest about reassignment",
    )

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate reassignment reason."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError(
                "Reassignment reason must be at least 10 characters"
            )
        return v

    @field_validator("new_room_id")
    @classmethod
    def validate_different_room(cls, v: UUID, info) -> UUID:
        """Ensure new room is different from current."""
        # In Pydantic v2, info.data contains previously validated fields
        current_room_id = info.data.get("current_room_id")
        if current_room_id and v == current_room_id:
            raise ValueError(
                "New room must be different from current room"
            )
        return v