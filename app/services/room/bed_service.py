# app/services/room/bed_service.py
"""
Bed service with bed management operations.
"""

from typing import Dict, Any, List, Optional
from datetime import date
from decimal import Decimal

from app.services.room.base_service import BaseService
from app.repositories.room import BedRepository, RoomRepository


class BedService(BaseService):
    """
    Bed service handling bed business logic.
    
    Operations:
    - Bed CRUD
    - Condition management
    - Configuration updates
    - Utilization tracking
    """
    
    def __init__(self, session):
        super().__init__(session)
        self.bed_repo = BedRepository(session)
        self.room_repo = RoomRepository(session)
    
    def create_bed(
        self,
        bed_data: Dict[str, Any],
        with_configuration: bool = True
    ) -> Dict[str, Any]:
        """
        Create a new bed with optional configuration.
        
        Args:
            bed_data: Bed creation data
            with_configuration: Whether to create default configuration
            
        Returns:
            Response with created bed
        """
        try:
            # Validate room exists
            room = self.room_repo.find_by_id(bed_data['room_id'])
            if not room:
                return self.error_response("Room not found")
            
            # Check if bed number already exists in room
            existing = self.bed_repo.find_by_bed_number(
                bed_data['room_id'],
                bed_data['bed_number']
            )
            if existing:
                return self.error_response(
                    f"Bed number {bed_data['bed_number']} already exists in this room"
                )
            
            # Create bed with details
            bed = self.bed_repo.create_bed_with_details(
                bed_data,
                commit=False
            )
            
            # Update room totals
            room.total_beds += 1
            room.available_beds += 1
            
            if not self.commit_or_rollback():
                return self.error_response("Failed to create bed")
            
            return self.success_response(
                {'bed': bed},
                f"Bed {bed.bed_number} created successfully"
            )
            
        except Exception as e:
            return self.handle_exception(e, "create bed")
    
    def update_bed_condition(
        self,
        bed_id: str,
        condition_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update bed condition and assessment.
        
        Args:
            bed_id: Bed ID
            condition_data: Condition update data
            
        Returns:
            Response with updated condition
        """
        try:
            bed = self.bed_repo.find_by_id(bed_id)
            if not bed:
                return self.error_response("Bed not found")
            
            condition = self.bed_repo.update_bed_condition(
                bed_id,
                condition_data,
                commit=False
            )
            
            # Update bed functional status if needed
            if 'is_fully_functional' in condition_data:
                bed.is_functional = condition_data['is_fully_functional']
                
                # If not functional, mark as unavailable
                if not bed.is_functional:
                    bed.is_available = False
                    bed.status = 'MAINTENANCE'
            
            if not self.commit_or_rollback():
                return self.error_response("Failed to update condition")
            
            return self.success_response(
                {'condition': condition},
                "Bed condition updated"
            )
            
        except Exception as e:
            return self.handle_exception(e, "update bed condition")
    
    def get_bed_utilization_report(
        self,
        bed_id: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive bed utilization report.
        
        Args:
            bed_id: Bed ID
            
        Returns:
            Response with utilization data
        """
        try:
            stats = self.bed_repo.get_bed_utilization_stats(bed_id)
            if not stats:
                return self.error_response("Bed not found or no utilization data")
            
            # Get condition
            condition = self.bed_repo.get_bed_condition(bed_id)
            
            # Get configuration
            config = self.bed_repo.get_bed_configuration(bed_id)
            
            return self.success_response(
                {
                    'utilization': stats,
                    'condition': condition,
                    'configuration': config
                },
                "Utilization report generated"
            )
            
        except Exception as e:
            return self.handle_exception(e, "get utilization report")
    
    def find_available_beds(
        self,
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Find available beds with filters.
        
        Args:
            filters: Search filters
            
        Returns:
            Response with available beds
        """
        try:
            beds = self.bed_repo.find_available_beds(
                room_id=filters.get('room_id'),
                hostel_id=filters.get('hostel_id'),
                bed_type=filters.get('bed_type'),
                is_upper_bunk=filters.get('is_upper_bunk'),
                is_lower_bunk=filters.get('is_lower_bunk')
            )
            
            return self.success_response(
                {
                    'beds': beds,
                    'count': len(beds)
                },
                f"Found {len(beds)} available beds"
            )
            
        except Exception as e:
            return self.handle_exception(e, "find available beds")
    
    def schedule_bed_maintenance(
        self,
        bed_id: str,
        maintenance_type: str,
        scheduled_date: date,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Schedule bed for maintenance.
        
        Args:
            bed_id: Bed ID
            maintenance_type: Type of maintenance
            scheduled_date: Scheduled date
            notes: Additional notes
            
        Returns:
            Response with maintenance schedule
        """
        try:
            bed = self.bed_repo.find_by_id(bed_id)
            if not bed:
                return self.error_response("Bed not found")
            
            # Check if bed is occupied
            if bed.is_occupied:
                return self.error_response(
                    "Cannot schedule maintenance for occupied bed"
                )
            
            # Update bed status
            bed = self.bed_repo.update_bed_status(
                bed_id,
                'MAINTENANCE',
                reason=f"Scheduled {maintenance_type} maintenance",
                commit=False
            )
            
            # Update condition to track maintenance need
            self.bed_repo.update_bed_condition(
                bed_id,
                {
                    'requires_maintenance': True,
                    'maintenance_type': maintenance_type,
                    'maintenance_priority': 'MEDIUM'
                },
                commit=False
            )
            
            if not self.commit_or_rollback():
                return self.error_response("Failed to schedule maintenance")
            
            return self.success_response(
                {'bed': bed},
                f"Maintenance scheduled for {scheduled_date}"
            )
            
        except Exception as e:
            return self.handle_exception(e, "schedule maintenance")