# app/services/room/room_maintenance_service.py
"""
Room maintenance service with scheduling and tracking.
"""

from typing import Dict, Any, List, Optional
from datetime import date, timedelta
from decimal import Decimal

from app.services.room.base_service import BaseService
from app.repositories.room import (
    RoomRepository,
    RoomAmenityRepository,
    BedRepository
)


class RoomMaintenanceService(BaseService):
    """
    Room maintenance service handling maintenance operations.
    
    Features:
    - Maintenance scheduling
    - Work order management
    - Cost tracking
    - Preventive maintenance
    """
    
    def __init__(self, session):
        super().__init__(session)
        self.room_repo = RoomRepository(session)
        self.amenity_repo = RoomAmenityRepository(session)
        self.bed_repo = BedRepository(session)
    
    def schedule_room_maintenance(
        self,
        room_id: str,
        maintenance_type: str,
        start_date: date,
        expected_end_date: Optional[date] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Schedule room for maintenance.
        
        Business Rules:
        1. Check if room can be taken offline
        2. Mark room as under maintenance
        3. Update all beds in room
        4. Create maintenance record
        
        Args:
            room_id: Room ID
            maintenance_type: Type of maintenance
            start_date: Start date
            expected_end_date: Expected completion date
            notes: Additional notes
            
        Returns:
            Response with maintenance details
        """
        try:
            # Check if room is occupied
            room = self.room_repo.find_by_id(room_id)
            if not room:
                return self.error_response("Room not found")
            
            if room.occupied_beds > 0:
                return self.error_response(
                    "Cannot schedule maintenance for occupied room",
                    {'occupied_beds': room.occupied_beds}
                )
            
            # Mark room under maintenance
            success = self.room_repo.mark_room_under_maintenance(
                room_id,
                maintenance_type,
                start_date,
                expected_end_date,
                notes,
                commit=False
            )
            
            if not success:
                return self.error_response("Failed to schedule maintenance")
            
            # Update all beds in room
            beds = self.bed_repo.find_beds_by_room(room_id)
            for bed in beds:
                self.bed_repo.update_bed_status(
                    bed.id,
                    'MAINTENANCE',
                    reason=f"Room maintenance: {maintenance_type}",
                    commit=False
                )
            
            if not self.commit_or_rollback():
                return self.error_response("Failed to save maintenance schedule")
            
            return self.success_response(
                {
                    'room': room,
                    'beds_affected': len(beds),
                    'start_date': start_date,
                    'expected_end_date': expected_end_date
                },
                f"Maintenance scheduled from {start_date}"
            )
            
        except Exception as e:
            return self.handle_exception(e, "schedule room maintenance")
    
    def complete_room_maintenance(
        self,
        room_id: str,
        actual_cost: Optional[Decimal] = None,
        completion_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Complete room maintenance.
        
        Args:
            room_id: Room ID
            actual_cost: Actual maintenance cost
            completion_notes: Completion notes
            
        Returns:
            Response with completion details
        """
        try:
            success = self.room_repo.complete_room_maintenance(
                room_id,
                actual_cost,
                completion_notes,
                commit=False
            )
            
            if not success:
                return self.error_response("Room not under maintenance")
            
            # Update all beds back to available
            beds = self.bed_repo.find_beds_by_room(room_id)
            for bed in beds:
                if not bed.is_occupied:
                    self.bed_repo.update_bed_status(
                        bed.id,
                        'AVAILABLE',
                        reason="Maintenance completed",
                        commit=False
                    )
            
            if not self.commit_or_rollback():
                return self.error_response("Failed to complete maintenance")
            
            room = self.room_repo.find_by_id(room_id)
            
            return self.success_response(
                {
                    'room': room,
                    'beds_updated': len(beds),
                    'actual_cost': float(actual_cost or 0)
                },
                "Maintenance completed successfully"
            )
            
        except Exception as e:
            return self.handle_exception(e, "complete room maintenance")
    
    def get_maintenance_schedule(
        self,
        hostel_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get maintenance schedule for hostel.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Response with scheduled maintenance
        """
        try:
            # Get rooms under maintenance
            rooms_under_maintenance = self.room_repo.find_rooms_under_maintenance(
                hostel_id
            )
            
            # Get amenity maintenance
            amenity_maintenance = self.amenity_repo.get_scheduled_maintenance(
                hostel_id,
                start_date,
                end_date
            )
            
            # Get beds requiring maintenance
            beds_maintenance = self.bed_repo.find_beds_requiring_maintenance(
                hostel_id,
                min_priority='MEDIUM'
            )
            
            return self.success_response(
                {
                    'rooms_under_maintenance': rooms_under_maintenance,
                    'amenity_maintenance_scheduled': amenity_maintenance,
                    'beds_requiring_maintenance': beds_maintenance,
                    'total_scheduled': (
                        len(rooms_under_maintenance) +
                        len(amenity_maintenance)
                    )
                },
                "Maintenance schedule retrieved"
            )
            
        except Exception as e:
            return self.handle_exception(e, "get maintenance schedule")
    
    def get_maintenance_costs(
        self,
        hostel_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get maintenance cost summary.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Response with cost summary
        """
        try:
            amenity_costs = self.amenity_repo.get_maintenance_cost_summary(
                hostel_id,
                start_date,
                end_date
            )
            
            # Get room maintenance costs (simplified - would query maintenance records)
            room_costs = {
                'total_activities': 0,
                'total_cost': 0,
                'avg_cost': 0
            }
            
            total_cost = (
                amenity_costs['total_cost'] +
                room_costs['total_cost']
            )
            
            return self.success_response(
                {
                    'amenity_maintenance': amenity_costs,
                    'room_maintenance': room_costs,
                    'total_cost': total_cost,
                    'period': {
                        'start_date': start_date,
                        'end_date': end_date
                    }
                },
                "Maintenance costs calculated"
            )
            
        except Exception as e:
            return self.handle_exception(e, "get maintenance costs")
    
    def create_preventive_maintenance_plan(
        self,
        hostel_id: str,
        frequency_days: int = 90
    ) -> Dict[str, Any]:
        """
        Create preventive maintenance plan.
        
        Args:
            hostel_id: Hostel ID
            frequency_days: Maintenance frequency in days
            
        Returns:
            Response with maintenance plan
        """
        try:
            # Get all rooms
            rooms = self.room_repo.find_rooms_by_hostel(hostel_id)
            
            plan = []
            today = date.today()
            
            for room in rooms:
                # Calculate next maintenance date
                if room.last_maintenance_date:
                    next_date = room.last_maintenance_date + timedelta(days=frequency_days)
                else:
                    next_date = today + timedelta(days=frequency_days)
                
                # Only include if due or overdue
                if next_date <= today + timedelta(days=30):
                    plan.append({
                        'room_id': room.id,
                        'room_number': room.room_number,
                        'last_maintenance': room.last_maintenance_date,
                        'next_maintenance_due': next_date,
                        'days_until_due': (next_date - today).days,
                        'is_overdue': next_date < today
                    })
            
            # Sort by urgency
            plan.sort(key=lambda x: x['days_until_due'])
            
            return self.success_response(
                {
                    'maintenance_plan': plan,
                    'total_rooms': len(plan),
                    'overdue': len([p for p in plan if p['is_overdue']]),
                    'due_soon': len([p for p in plan if 0 <= p['days_until_due'] <= 7])
                },
                "Preventive maintenance plan created"
            )
            
        except Exception as e:
            return self.handle_exception(e, "create maintenance plan")