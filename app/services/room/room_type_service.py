# app/services/room/room_type_service.py
"""
Room type service with type management and comparisons.
"""

from typing import Dict, Any, List, Optional
from decimal import Decimal

from app.services.room.base_service import BaseService
from app.repositories.room import RoomTypeRepository


class RoomTypeService(BaseService):
    """
    Room type service handling type operations.
    
    Features:
    - Type definitions
    - Feature management
    - Type comparisons
    - Upgrade paths
    """
    
    def __init__(self, session):
        super().__init__(session)
        self.type_repo = RoomTypeRepository(session)
    
    def create_room_type(
        self,
        type_data: Dict[str, Any],
        features: Optional[List[Dict[str, Any]]] = None,
        pricing: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create room type with features and pricing.
        
        Args:
            type_data: Type definition data
            features: List of features
            pricing: Pricing configuration
            
        Returns:
            Response with created type
        """
        try:
            room_type = self.type_repo.create_room_type_with_details(
                type_data,
                features,
                pricing,
                commit=True
            )
            
            return self.success_response(
                {'room_type': room_type},
                f"Room type {room_type.type_name} created"
            )
            
        except Exception as e:
            return self.handle_exception(e, "create room type")
    
    def get_type_comparison(
        self,
        type_id_1: str,
        type_id_2: str
    ) -> Dict[str, Any]:
        """
        Compare two room types.
        
        Args:
            type_id_1: First type ID
            type_id_2: Second type ID
            
        Returns:
            Response with comparison
        """
        try:
            # Get or create comparison
            comparisons = self.type_repo.get_type_comparisons(type_id_1)
            
            comparison = next(
                (c for c in comparisons if c.compared_with_type_id == type_id_2),
                None
            )
            
            if not comparison:
                comparison = self.type_repo.create_type_comparison(
                    type_id_1,
                    type_id_2,
                    commit=True
                )
            
            # Get feature comparison
            feature_comparison = self.type_repo.compare_type_features(
                type_id_1,
                type_id_2
            )
            
            return self.success_response(
                {
                    'comparison': comparison,
                    'feature_comparison': feature_comparison
                },
                "Types compared"
            )
            
        except Exception as e:
            return self.handle_exception(e, "compare types")
    
    def get_upgrade_options(
        self,
        from_type_id: str
    ) -> Dict[str, Any]:
        """
        Get upgrade options from a room type.
        
        Args:
            from_type_id: Source type ID
            
        Returns:
            Response with upgrade options
        """
        try:
            upgrades = self.type_repo.get_upgrade_options(
                from_type_id,
                is_available=True
            )
            
            # Sort by price difference
            upgrades.sort(key=lambda x: x.price_difference_monthly)
            
            return self.success_response(
                {
                    'upgrade_options': upgrades,
                    'count': len(upgrades)
                },
                f"Found {len(upgrades)} upgrade options"
            )
            
        except Exception as e:
            return self.handle_exception(e, "get upgrade options")
    
    def recommend_room_type(
        self,
        hostel_id: str,
        preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Recommend room types based on preferences.
        
        Args:
            hostel_id: Hostel ID
            preferences: User preferences
            
        Returns:
            Response with recommendations
        """
        try:
            recommendations = self.type_repo.recommend_type_for_student(
                hostel_id,
                preferences
            )
            
            return self.success_response(
                {
                    'recommendations': recommendations,
                    'count': len(recommendations)
                },
                f"Generated {len(recommendations)} recommendations"
            )
            
        except Exception as e:
            return self.handle_exception(e, "recommend room type")
    
    def get_type_statistics(
        self,
        hostel_id: str
    ) -> Dict[str, Any]:
        """
        Get statistics for all room types.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Response with type statistics
        """
        try:
            stats = self.type_repo.get_type_statistics(hostel_id)
            capacity = self.type_repo.get_capacity_summary(hostel_id)
            popular = self.type_repo.get_popular_types_ranking(hostel_id)
            
            return self.success_response(
                {
                    'type_statistics': stats,
                    'capacity_summary': capacity,
                    'popular_types': popular
                },
                "Type statistics retrieved"
            )
            
        except Exception as e:
            return self.handle_exception(e, "get type statistics")