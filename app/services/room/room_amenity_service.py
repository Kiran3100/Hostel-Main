# app/services/room/room_amenity_service.py
"""
Room amenity service with amenity management operations.
"""

from typing import Dict, Any, List, Optional
from datetime import date
from decimal import Decimal

from app.services.room.base_service import BaseService
from app.repositories.room import RoomAmenityRepository


class RoomAmenityService(BaseService):
    """
    Room amenity service handling amenity operations.
    
    Features:
    - Amenity CRUD
    - Condition tracking
    - Maintenance scheduling
    - Usage analytics
    - Feedback management
    """
    
    def __init__(self, session):
        super().__init__(session)
        self.amenity_repo = RoomAmenityRepository(session)
    
    def create_amenity(
        self,
        amenity_data: Dict[str, Any],
        with_inventory: bool = True
    ) -> Dict[str, Any]:
        """
        Create room amenity with tracking.
        
        Args:
            amenity_data: Amenity creation data
            with_inventory: Whether to create inventory record
            
        Returns:
            Response with created amenity
        """
        try:
            inventory_data = None
            if with_inventory:
                inventory_data = {
                    'unit_cost': amenity_data.get('purchase_cost', Decimal('0.00')),
                    'acquisition_date': amenity_data.get('purchase_date', date.today()),
                    'is_active': True
                }
            
            amenity = self.amenity_repo.create_amenity_with_details(
                amenity_data,
                inventory_data=inventory_data,
                commit=True
            )
            
            return self.success_response(
                {'amenity': amenity},
                f"Amenity {amenity.amenity_name} created"
            )
            
        except Exception as e:
            return self.handle_exception(e, "create amenity")
    
    def update_amenity_condition(
        self,
        amenity_id: str,
        condition_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update amenity condition assessment.
        
        Args:
            amenity_id: Amenity ID
            condition_data: Condition update data
            
        Returns:
            Response with updated condition
        """
        try:
            condition = self.amenity_repo.update_amenity_condition(
                amenity_id,
                condition_data,
                commit=True
            )
            
            if not condition:
                return self.error_response("Amenity not found")
            
            # Check if maintenance needed
            message = "Condition updated"
            if condition.requires_maintenance:
                message = "Condition updated - Maintenance required"
            elif condition.requires_replacement:
                message = "Condition updated - Replacement recommended"
            
            return self.success_response(
                {'condition': condition},
                message
            )
            
        except Exception as e:
            return self.handle_exception(e, "update amenity condition")
    
    def schedule_maintenance(
        self,
        amenity_id: str,
        maintenance_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Schedule amenity maintenance.
        
        Args:
            amenity_id: Amenity ID
            maintenance_data: Maintenance details
            
        Returns:
            Response with maintenance record
        """
        try:
            maintenance = self.amenity_repo.schedule_amenity_maintenance(
                amenity_id,
                maintenance_data,
                commit=True
            )
            
            return self.success_response(
                {'maintenance': maintenance},
                "Maintenance scheduled"
            )
            
        except Exception as e:
            return self.handle_exception(e, "schedule maintenance")
    
    def complete_maintenance(
        self,
        maintenance_id: str,
        completion_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Complete amenity maintenance.
        
        Args:
            maintenance_id: Maintenance record ID
            completion_data: Completion details
            
        Returns:
            Response with completed maintenance
        """
        try:
            maintenance = self.amenity_repo.complete_amenity_maintenance(
                maintenance_id,
                completion_data,
                commit=True
            )
            
            if not maintenance:
                return self.error_response("Maintenance record not found")
            
            return self.success_response(
                {'maintenance': maintenance},
                "Maintenance completed"
            )
            
        except Exception as e:
            return self.handle_exception(e, "complete maintenance")
    
    def submit_feedback(
        self,
        amenity_id: str,
        student_id: str,
        feedback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Submit amenity feedback.
        
        Args:
            amenity_id: Amenity ID
            student_id: Student ID
            feedback_data: Feedback details
            
        Returns:
            Response with feedback record
        """
        try:
            feedback = self.amenity_repo.submit_amenity_feedback(
                amenity_id,
                student_id,
                feedback_data,
                commit=True
            )
            
            return self.success_response(
                {'feedback': feedback},
                "Feedback submitted"
            )
            
        except Exception as e:
            return self.handle_exception(e, "submit feedback")
    
    def get_amenity_statistics(
        self,
        hostel_id: str,
        amenity_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get amenity statistics for hostel.
        
        Args:
            hostel_id: Hostel ID
            amenity_type: Amenity type filter
            
        Returns:
            Response with statistics
        """
        try:
            stats = self.amenity_repo.get_amenity_statistics(
                hostel_id,
                amenity_type
            )
            
            value_summary = self.amenity_repo.get_amenity_value_summary(
                hostel_id
            )
            
            maintenance_summary = self.amenity_repo.get_maintenance_cost_summary(
                hostel_id
            )
            
            return self.success_response(
                {
                    'statistics': stats,
                    'value_summary': value_summary,
                    'maintenance_summary': maintenance_summary
                },
                "Statistics retrieved"
            )
            
        except Exception as e:
            return self.handle_exception(e, "get amenity statistics")
    
    def find_amenities_needing_attention(
        self,
        hostel_id: str
    ) -> Dict[str, Any]:
        """
        Find amenities requiring attention.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Response with amenities needing attention
        """
        try:
            # Get maintenance needed
            maintenance_needed = self.amenity_repo.find_amenities_requiring_maintenance(
                hostel_id,
                min_priority='MEDIUM'
            )
            
            # Get replacement needed
            replacement_needed = self.amenity_repo.find_amenities_requiring_replacement(
                hostel_id
            )
            
            # Get defective
            defective = self.amenity_repo.find_defective_amenities(hostel_id)
            
            # Get verification due
            verification_due = self.amenity_repo.find_amenities_for_verification(
                hostel_id,
                overdue_only=True
            )
            
            return self.success_response(
                {
                    'maintenance_needed': maintenance_needed,
                    'replacement_needed': replacement_needed,
                    'defective': defective,
                    'verification_due': verification_due,
                    'total_requiring_attention': (
                        len(maintenance_needed) +
                        len(replacement_needed) +
                        len(defective)
                    )
                },
                "Amenities requiring attention identified"
            )
            
        except Exception as e:
            return self.handle_exception(e, "find amenities needing attention")
    
    def get_low_rated_amenities(
        self,
        hostel_id: str,
        max_rating: float = 3.0,
        min_feedback_count: int = 3
    ) -> Dict[str, Any]:
        """
        Get amenities with low ratings.
        
        Args:
            hostel_id: Hostel ID
            max_rating: Maximum average rating
            min_feedback_count: Minimum feedback count
            
        Returns:
            Response with low-rated amenities
        """
        try:
            low_rated = self.amenity_repo.find_low_rated_amenities(
                hostel_id,
                Decimal(str(max_rating)),
                min_feedback_count
            )
            
            return self.success_response(
                {
                    'low_rated_amenities': low_rated,
                    'count': len(low_rated)
                },
                f"Found {len(low_rated)} low-rated amenities"
            )
            
        except Exception as e:
            return self.handle_exception(e, "get low rated amenities")