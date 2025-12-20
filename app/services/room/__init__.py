# app/services/room/__init__.py
"""
Room services package.

Exports all room-related service classes.
"""

from app.services.room.room_service import RoomService
from app.services.room.bed_service import BedService
from app.services.room.bed_assignment_service import BedAssignmentService
from app.services.room.room_availability_service import RoomAvailabilityService
from app.services.room.room_amenity_service import RoomAmenityService
from app.services.room.room_maintenance_service import RoomMaintenanceService
from app.services.room.room_pricing_service import RoomPricingService
from app.services.room.room_type_service import RoomTypeService
from app.services.room.room_allocation_service import RoomAllocationService

__all__ = [
    'RoomService',
    'BedService',
    'BedAssignmentService',
    'RoomAvailabilityService',
    'RoomAmenityService',
    'RoomMaintenanceService',
    'RoomPricingService',
    'RoomTypeService',
    'RoomAllocationService',
]


# Service factory
class RoomServiceFactory:
    """
    Factory for creating room service instances.
    
    Provides centralized service instantiation with shared session.
    """
    
    def __init__(self, session):
        self.session = session
        self._services = {}
    
    def get_room_service(self) -> RoomService:
        """Get or create RoomService instance."""
        if 'room' not in self._services:
            self._services['room'] = RoomService(self.session)
        return self._services['room']
    
    def get_bed_service(self) -> BedService:
        """Get or create BedService instance."""
        if 'bed' not in self._services:
            self._services['bed'] = BedService(self.session)
        return self._services['bed']
    
    def get_assignment_service(self) -> BedAssignmentService:
        """Get or create BedAssignmentService instance."""
        if 'assignment' not in self._services:
            self._services['assignment'] = BedAssignmentService(self.session)
        return self._services['assignment']
    
    def get_availability_service(self) -> RoomAvailabilityService:
        """Get or create RoomAvailabilityService instance."""
        if 'availability' not in self._services:
            self._services['availability'] = RoomAvailabilityService(self.session)
        return self._services['availability']
    
    def get_amenity_service(self) -> RoomAmenityService:
        """Get or create RoomAmenityService instance."""
        if 'amenity' not in self._services:
            self._services['amenity'] = RoomAmenityService(self.session)
        return self._services['amenity']
    
    def get_maintenance_service(self) -> RoomMaintenanceService:
        """Get or create RoomMaintenanceService instance."""
        if 'maintenance' not in self._services:
            self._services['maintenance'] = RoomMaintenanceService(self.session)
        return self._services['maintenance']
    
    def get_pricing_service(self) -> RoomPricingService:
        """Get or create RoomPricingService instance."""
        if 'pricing' not in self._services:
            self._services['pricing'] = RoomPricingService(self.session)
        return self._services['pricing']
    
    def get_type_service(self) -> RoomTypeService:
        """Get or create RoomTypeService instance."""
        if 'type' not in self._services:
            self._services['type'] = RoomTypeService(self.session)
        return self._services['type']
    
    def get_allocation_service(self) -> RoomAllocationService:
        """Get or create RoomAllocationService instance."""
        if 'allocation' not in self._services:
            self._services['allocation'] = RoomAllocationService(self.session)
        return self._services['allocation']
    
    def clear_cache(self):
        """Clear cached service instances."""
        self._services.clear()


# Convenience function
def get_service_factory(session) -> RoomServiceFactory:
    """
    Get service factory instance.
    
    Args:
        session: Database session
        
    Returns:
        RoomServiceFactory instance
        
    Example:
        >>> from app.services.room import get_service_factory
        >>> factory = get_service_factory(session)
        >>> room_service = factory.get_room_service()
        >>> result = room_service.create_room_with_beds(...)
    """
    return RoomServiceFactory(session)


# Version
__version__ = '1.0.0'