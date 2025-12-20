# app/services/room/bed_assignment_service.py
"""
Bed assignment service with intelligent assignment logic.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import date, timedelta
from decimal import Decimal

from app.services.room.base_service import BaseService
from app.repositories.room import (
    BedAssignmentRepository,
    BedRepository,
    RoomRepository,
    RoomAvailabilityRepository
)


class BedAssignmentService(BaseService):
    """
    Bed assignment service handling assignment operations.
    
    Features:
    - Intelligent bed assignment
    - Preference matching
    - Conflict resolution
    - Transfer management
    """
    
    def __init__(self, session):
        super().__init__(session)
        self.assignment_repo = BedAssignmentRepository(session)
        self.bed_repo = BedRepository(session)
        self.room_repo = RoomRepository(session)
        self.availability_repo = RoomAvailabilityRepository(session)
    
    def assign_student_to_bed(
        self,
        student_id: str,
        bed_id: Optional[str] = None,
        room_id: Optional[str] = None,
        preferences: Optional[Dict[str, Any]] = None,
        assignment_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Assign student to a bed with intelligent matching.
        
        Business Rules:
        1. If bed_id provided, use that bed
        2. If room_id provided, find best bed in room
        3. Otherwise, find best bed based on preferences
        4. Validate conflicts
        5. Create assignment
        6. Update room/bed status
        7. Create alerts if needed
        
        Args:
            student_id: Student ID
            bed_id: Specific bed ID (optional)
            room_id: Specific room ID (optional)
            preferences: Student preferences
            assignment_data: Additional assignment data
            
        Returns:
            Response with assignment details
        """
        try:
            assignment_data = assignment_data or {}
            preferences = preferences or {}
            
            # Find best bed
            if bed_id:
                bed = self.bed_repo.find_by_id(bed_id)
                if not bed:
                    return self.error_response("Bed not found")
                if not bed.is_available:
                    return self.error_response("Bed is not available")
                room = bed.room
            elif room_id:
                result = self._find_best_bed_in_room(room_id, student_id, preferences)
                if not result['success']:
                    return result
                bed = result['data']['bed']
                room = bed.room
            else:
                result = self._find_best_bed_anywhere(student_id, preferences)
                if not result['success']:
                    return result
                bed = result['data']['bed']
                room = bed.room
            
            # Prepare assignment data
            assignment_info = {
                'bed_id': bed.id,
                'student_id': student_id,
                'room_id': room.id,
                'hostel_id': room.hostel_id,
                'occupied_from': assignment_data.get('occupied_from', date.today()),
                'expected_vacate_date': assignment_data.get('expected_vacate_date'),
                'monthly_rent': assignment_data.get('monthly_rent', room.price_monthly),
                'assignment_type': assignment_data.get('assignment_type', 'REGULAR'),
                'assignment_source': assignment_data.get('assignment_source', 'MANUAL'),
                'is_confirmed': assignment_data.get('is_confirmed', True)
            }
            
            # Create assignment with validation
            assignment, warnings = self.assignment_repo.create_assignment_with_validation(
                assignment_info,
                validate_conflicts=True,
                commit=False
            )
            
            if not assignment:
                return self.error_response(
                    "Failed to create assignment",
                    {'warnings': warnings}
                )
            
            # Update room occupancy
            self.room_repo.update_room_occupancy(
                room.id,
                room.occupied_beds + 1,
                commit=False
            )
            
            # Sync availability
            self.availability_repo.sync_availability_with_room(
                room.id,
                commit=False
            )
            
            # Check for alerts
            if room.availability:
                self.availability_repo.check_and_create_alerts(
                    room.availability.id,
                    commit=False
                )
            
            if not self.commit_or_rollback():
                return self.error_response("Failed to save assignment")
            
            return self.success_response(
                {
                    'assignment': assignment,
                    'bed': bed,
                    'room': room,
                    'warnings': warnings
                },
                f"Student assigned to bed {bed.bed_number} in room {room.room_number}"
            )
            
        except Exception as e:
            return self.handle_exception(e, "assign student to bed")
    
    def _find_best_bed_in_room(
        self,
        room_id: str,
        student_id: str,
        preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Find best bed in specific room."""
        try:
            available_beds = self.bed_repo.find_available_beds(room_id=room_id)
            
            if not available_beds:
                return self.error_response("No available beds in room")
            
            # Match with preferences
            if preferences:
                matched = self.bed_repo.match_bed_preferences(
                    student_id,
                    [bed.id for bed in available_beds]
                )
                
                if matched:
                    best_bed = next(
                        (bed for bed in available_beds if bed.id == matched[0]['bed_id']),
                        available_beds[0]
                    )
                else:
                    best_bed = available_beds[0]
            else:
                best_bed = available_beds[0]
            
            return self.success_response({'bed': best_bed})
            
        except Exception as e:
            return self.handle_exception(e, "find best bed in room")
    
    def _find_best_bed_anywhere(
        self,
        student_id: str,
        preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Find best bed across all rooms."""
        try:
            if 'hostel_id' not in preferences:
                return self.error_response("Hostel ID required")
            
            # Search rooms
            rooms = self.room_repo.search_available_rooms(
                hostel_id=preferences['hostel_id'],
                room_type=preferences.get('room_type'),
                is_ac=preferences.get('is_ac'),
                has_attached_bathroom=preferences.get('has_bathroom'),
                max_price=preferences.get('max_price')
            )
            
            if not rooms:
                return self.error_response("No available rooms matching preferences")
            
            # Find best bed
            for room in rooms:
                beds = self.bed_repo.find_available_beds(room_id=room.id)
                if beds:
                    return self.success_response({'bed': beds[0]})
            
            return self.error_response("No available beds found")
            
        except Exception as e:
            return self.handle_exception(e, "find best bed")
    
    def transfer_student(
        self,
        assignment_id: str,
        new_bed_id: str,
        transfer_date: date,
        reason: str,
        approved_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transfer student to different bed.
        
        Args:
            assignment_id: Current assignment ID
            new_bed_id: New bed ID
            transfer_date: Transfer date
            reason: Transfer reason
            approved_by: Approver user ID
            
        Returns:
            Response with new assignment
        """
        try:
            # Validate new bed
            new_bed = self.bed_repo.find_by_id(new_bed_id)
            if not new_bed or not new_bed.is_available:
                return self.error_response("New bed is not available")
            
            # Transfer
            new_assignment = self.assignment_repo.transfer_assignment(
                assignment_id,
                new_bed_id,
                transfer_date,
                reason,
                approved_by,
                commit=False
            )
            
            if not new_assignment:
                return self.error_response("Transfer failed")
            
            # Update both rooms
            old_assignment = self.assignment_repo.find_by_id(assignment_id)
            if old_assignment:
                # Decrease old room occupancy
                old_room = old_assignment.room
                self.room_repo.update_room_occupancy(
                    old_room.id,
                    old_room.occupied_beds - 1,
                    commit=False
                )
            
            # Increase new room occupancy
            new_room = new_bed.room
            self.room_repo.update_room_occupancy(
                new_room.id,
                new_room.occupied_beds + 1,
                commit=False
            )
            
            if not self.commit_or_rollback():
                return self.error_response("Failed to complete transfer")
            
            return self.success_response(
                {'assignment': new_assignment},
                "Transfer completed successfully"
            )
            
        except Exception as e:
            return self.handle_exception(e, "transfer student")
    
    def complete_assignment(
        self,
        assignment_id: str,
        vacate_date: date,
        completion_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Complete bed assignment when student leaves.
        
        Args:
            assignment_id: Assignment ID
            vacate_date: Actual vacate date
            completion_data: Additional completion data
            
        Returns:
            Response with completed assignment
        """
        try:
            assignment = self.assignment_repo.complete_assignment(
                assignment_id,
                vacate_date,
                completion_data,
                commit=False
            )
            
            if not assignment:
                return self.error_response("Assignment not found")
            
            # Update room occupancy
            room = assignment.room
            self.room_repo.update_room_occupancy(
                room.id,
                room.occupied_beds - 1,
                commit=False
            )
            
            # Sync availability
            self.availability_repo.sync_availability_with_room(
                room.id,
                commit=False
            )
            
            if not self.commit_or_rollback():
                return self.error_response("Failed to complete assignment")
            
            return self.success_response(
                {'assignment': assignment},
                "Assignment completed successfully"
            )
            
        except Exception as e:
            return self.handle_exception(e, "complete assignment")
    
    def get_assignment_statistics(
        self,
        hostel_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get assignment statistics for hostel."""
        try:
            stats = self.assignment_repo.get_assignment_statistics(
                hostel_id,
                start_date,
                end_date
            )
            
            # Get expiring and overdue
            expiring = self.assignment_repo.find_expiring_assignments(hostel_id, 30)
            overdue = self.assignment_repo.find_overdue_assignments(hostel_id)
            
            return self.success_response(
                {
                    'statistics': stats,
                    'expiring_soon': len(expiring),
                    'overdue': len(overdue)
                },
                "Statistics retrieved"
            )
            
        except Exception as e:
            return self.handle_exception(e, "get statistics")