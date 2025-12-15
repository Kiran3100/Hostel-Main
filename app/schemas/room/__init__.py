# --- File: app/schemas/room/__init__.py ---
"""
Room schemas package.

Re-exports commonly used room and bed-related schemas for convenient imports.

Example:
    from app.schemas.room import RoomCreate, BedAssignment, AvailabilityResponse
"""

from __future__ import annotations

from app.schemas.room.bed_base import (
    BedAssignmentRequest,
    BedBase,
    BedCreate,
    BedReleaseRequest,
    BedSwapRequest,
    BedUpdate,
    BulkBedCreate,
    BulkBedStatusUpdate,
)
from app.schemas.room.bed_response import (
    BedAssignment,
    BedAssignmentHistory,
    BedAvailability,
    BedDetailedStatus,
    BedHistory,
    BedResponse,
)
from app.schemas.room.room_availability import (
    AvailabilityCalendar,
    AvailabilityResponse,
    AvailableRoom,
    BulkAvailabilityRequest,
    DayAvailability,
    RoomAvailabilityRequest,
)
from app.schemas.room.room_base import (
    BulkRoomCreate,
    RoomBase,
    RoomCreate,
    RoomMediaUpdate,
    RoomPricingUpdate,
    RoomStatusUpdate,
    RoomUpdate,
)
from app.schemas.room.room_response import (
    BedDetail,
    BedInfo,
    RoomDetail,
    RoomFinancialSummary,
    RoomListItem,
    RoomOccupancyStats,
    RoomResponse,
    RoomWithBeds,
)

__all__ = [
    # Room base
    "RoomBase",
    "RoomCreate",
    "RoomUpdate",
    "BulkRoomCreate",
    "RoomPricingUpdate",
    "RoomStatusUpdate",
    "RoomMediaUpdate",
    # Room response
    "RoomResponse",
    "RoomDetail",
    "RoomListItem",
    "RoomWithBeds",
    "RoomOccupancyStats",
    "RoomFinancialSummary",
    "BedDetail",
    "BedInfo",
    # Bed base
    "BedBase",
    "BedCreate",
    "BedUpdate",
    "BulkBedCreate",
    "BedAssignmentRequest",
    "BedReleaseRequest",
    "BedSwapRequest",
    "BulkBedStatusUpdate",
    # Bed response
    "BedResponse",
    "BedAvailability",
    "BedAssignment",
    "BedHistory",
    "BedAssignmentHistory",
    "BedDetailedStatus",
    # Availability
    "RoomAvailabilityRequest",
    "AvailabilityResponse",
    "AvailableRoom",
    "AvailabilityCalendar",
    "DayAvailability",
    "BulkAvailabilityRequest",
]