# app/models/room/__init__.py
"""
Room models package.

Re-exports all room-related models for convenient imports.

Example:
    from app.models.room import Room, Bed, BedAssignment, RoomAvailability
"""

from app.models.room.bed import (
    Bed,
    BedAccessibility,
    BedCondition,
    BedConfiguration,
    BedPreference,
    BedUtilization,
)
from app.models.room.bed_assignment import (
    AssignmentConflict,
    AssignmentHistory,
    AssignmentOptimization,
    AssignmentPreference,
    AssignmentRule,
    BedAssignment,
)
from app.models.room.room import (
    Room,
    RoomAccessControl,
    RoomMaintenanceStatus,
    RoomOccupancyLimit,
    RoomPricingHistory,
    RoomSpecification,
)
from app.models.room.room_amenity import (
    AmenityCondition,
    AmenityFeedback,
    AmenityInventory,
    AmenityMaintenance,
    AmenityUsage,
    RoomAmenity,
)
from app.models.room.room_availability import (
    AvailabilityAlert,
    AvailabilityForecast,
    AvailabilityOptimization,
    AvailabilityRule,
    AvailabilityWindow,
    RoomAvailability,
)
from app.models.room.room_type import (
    RoomTypeAvailability,
    RoomTypeComparison,
    RoomTypeDefinition,
    RoomTypeFeature,
    RoomTypePricing,
    RoomTypeUpgrade,
)

__all__ = [
    # Room models
    "Room",
    "RoomSpecification",
    "RoomPricingHistory",
    "RoomMaintenanceStatus",
    "RoomAccessControl",
    "RoomOccupancyLimit",
    # Room Type models
    "RoomTypeDefinition",
    "RoomTypeFeature",
    "RoomTypePricing",
    "RoomTypeAvailability",
    "RoomTypeComparison",
    "RoomTypeUpgrade",
    # Room Amenity models
    "RoomAmenity",
    "AmenityCondition",
    "AmenityMaintenance",
    "AmenityUsage",
    "AmenityFeedback",
    "AmenityInventory",
    # Bed models
    "Bed",
    "BedCondition",
    "BedConfiguration",
    "BedAccessibility",
    "BedPreference",
    "BedUtilization",
    # Bed Assignment models
    "BedAssignment",
    "AssignmentRule",
    "AssignmentConflict",
    "AssignmentOptimization",
    "AssignmentHistory",
    "AssignmentPreference",
    # Room Availability models
    "RoomAvailability",
    "AvailabilityWindow",
    "AvailabilityRule",
    "AvailabilityForecast",
    "AvailabilityAlert",
    "AvailabilityOptimization",
]


# Version info
__version__ = "1.0.0"

# Model registry for migrations and introspection
ROOM_MODELS = {
    # Core models
    "room": Room,
    "room_specification": RoomSpecification,
    "room_pricing_history": RoomPricingHistory,
    "room_maintenance_status": RoomMaintenanceStatus,
    "room_access_control": RoomAccessControl,
    "room_occupancy_limit": RoomOccupancyLimit,
    
    # Room type models
    "room_type_definition": RoomTypeDefinition,
    "room_type_feature": RoomTypeFeature,
    "room_type_pricing": RoomTypePricing,
    "room_type_availability": RoomTypeAvailability,
    "room_type_comparison": RoomTypeComparison,
    "room_type_upgrade": RoomTypeUpgrade,
    
    # Amenity models
    "room_amenity": RoomAmenity,
    "amenity_condition": AmenityCondition,
    "amenity_maintenance": AmenityMaintenance,
    "amenity_usage": AmenityUsage,
    "amenity_feedback": AmenityFeedback,
    "amenity_inventory": AmenityInventory,
    
    # Bed models
    "bed": Bed,
    "bed_condition": BedCondition,
    "bed_configuration": BedConfiguration,
    "bed_accessibility": BedAccessibility,
    "bed_preference": BedPreference,
    "bed_utilization": BedUtilization,
    
    # Assignment models
    "bed_assignment": BedAssignment,
    "assignment_rule": AssignmentRule,
    "assignment_conflict": AssignmentConflict,
    "assignment_optimization": AssignmentOptimization,
    "assignment_history": AssignmentHistory,
    "assignment_preference": AssignmentPreference,
    
    # Availability models
    "room_availability": RoomAvailability,
    "availability_window": AvailabilityWindow,
    "availability_rule": AvailabilityRule,
    "availability_forecast": AvailabilityForecast,
    "availability_alert": AvailabilityAlert,
    "availability_optimization": AvailabilityOptimization,
}


def get_all_models():
    """
    Get all room-related model classes.
    
    Returns:
        List of all model classes in the room module
    """
    return list(ROOM_MODELS.values())


def get_model_by_table_name(table_name: str):
    """
    Get model class by table name.
    
    Args:
        table_name: Database table name
        
    Returns:
        Model class or None if not found
    """
    return ROOM_MODELS.get(table_name)