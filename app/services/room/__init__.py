# app/services/room/__init__.py
"""
Room and bed services.

- RoomService:
    Core CRUD, listing, and detail for rooms with occupancy data.

- RoomAvailabilityService:
    Availability checks and basic availability calendar per room.

- BedService:
    CRUD and listing for beds, plus simple availability info.

- BedAssignmentService:
    Assign/release beds to/from students and maintain history.
"""

from .room_service import RoomService
from .room_availability_service import RoomAvailabilityService
from .bed_service import BedService
from .bed_assignment_service import BedAssignmentService

__all__ = [
    "RoomService",
    "RoomAvailabilityService",
    "BedService",
    "BedAssignmentService",
]