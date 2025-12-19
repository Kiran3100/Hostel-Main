# app/repositories/room/__init__.py
"""
Room repositories package.

Exports all room-related repository classes.
"""

from app.repositories.room.room_repository import RoomRepository
from app.repositories.room.bed_repository import BedRepository
from app.repositories.room.bed_assignment_repository import BedAssignmentRepository
from app.repositories.room.room_amenity_repository import RoomAmenityRepository
from app.repositories.room.room_availability_repository import RoomAvailabilityRepository
from app.repositories.room.room_type_repository import RoomTypeRepository
from app.repositories.room.room_aggregate_repository import RoomAggregateRepository

__all__ = [
    "RoomRepository",
    "BedRepository",
    "BedAssignmentRepository",
    "RoomAmenityRepository",
    "RoomAvailabilityRepository",
    "RoomTypeRepository",
    "RoomAggregateRepository",
]

# Repository registry
ROOM_REPOSITORIES = {
    'room': RoomRepository,
    'bed': BedRepository,
    'bed_assignment': BedAssignmentRepository,
    'room_amenity': RoomAmenityRepository,
    'room_availability': RoomAvailabilityRepository,
    'room_type': RoomTypeRepository,
    'aggregate': RoomAggregateRepository,
}


def get_repository(repository_name: str, session):
    """
    Factory function to get repository instance.
    
    Args:
        repository_name: Name of repository
        session: Database session
        
    Returns:
        Repository instance
        
    Example:
        >>> from app.repositories.room import get_repository
        >>> room_repo = get_repository('room', session)
    """
    repository_class = ROOM_REPOSITORIES.get(repository_name)
    if not repository_class:
        raise ValueError(f"Unknown repository: {repository_name}")
    
    return repository_class(session)


# Version
__version__ = "1.0.0"