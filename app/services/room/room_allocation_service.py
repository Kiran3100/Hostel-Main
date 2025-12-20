# app/services/room/room_allocation_service.py
"""
Room allocation service with intelligent allocation algorithms.
"""

from typing import Dict, Any, List, Optional
from datetime import date
from decimal import Decimal

from app.services.room.base_service import BaseService
from app.repositories.room import (
    RoomRepository,
    BedRepository,
    BedAssignmentRepository,
    RoomAvailabilityRepository
)


class RoomAllocationService(BaseService):
    """
    Room allocation service for intelligent room/bed allocation.
    
    Features:
    - Batch allocation
    - Preference matching
    - Optimization algorithms
    - Conflict resolution
    """
    
    def __init__(self, session):
        super().__init__(session)
        self.room_repo = RoomRepository(session)
        self.bed_repo = BedRepository(session)
        self.assignment_repo = BedAssignmentRepository(session)
        self.availability_repo = RoomAvailabilityRepository(session)
    
    def allocate_students_batch(
        self,
        hostel_id: str,
        student_requests: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Allocate multiple students to rooms/beds.
        
        Business Logic:
        1. Collect all student requests
        2. Get available beds
        3. Match preferences
        4. Optimize assignments
        5. Create all assignments
        
        Args:
            hostel_id: Hostel ID
            student_requests: List of student allocation requests
            
        Returns:
            Response with allocation results
        """
        try:
            successful_allocations = []
            failed_allocations = []
            
            # Get all available beds
            available_beds = self.bed_repo.find_available_beds(
                hostel_id=hostel_id
            )
            
            if len(student_requests) > len(available_beds):
                return self.error_response(
                    "Insufficient beds available",
                    {
                        'requested': len(student_requests),
                        'available': len(available_beds)
                    }
                )
            
            # Process each request
            for request in student_requests:
                student_id = request['student_id']
                preferences = request.get('preferences', {})
                
                # Find best matching bed
                best_bed = self._find_best_bed_for_student(
                    student_id,
                    available_beds,
                    preferences
                )
                
                if not best_bed:
                    failed_allocations.append({
                        'student_id': student_id,
                        'reason': 'No suitable bed found'
                    })
                    continue
                
                # Create assignment
                assignment, warnings = self.assignment_repo.create_assignment_with_validation(
                    {
                        'bed_id': best_bed.id,
                        'student_id': student_id,
                        'room_id': best_bed.room_id,
                        'hostel_id': hostel_id,
                        'occupied_from': request.get('start_date', date.today()),
                        'expected_vacate_date': request.get('end_date'),
                        'monthly_rent': best_bed.room.price_monthly,
                        'assignment_type': 'REGULAR',
                        'assignment_source': 'BATCH_ALLOCATION'
                    },
                    validate_conflicts=True,
                    commit=False
                )
                
                if assignment:
                    successful_allocations.append({
                        'student_id': student_id,
                        'assignment': assignment,
                        'bed': best_bed,
                        'room': best_bed.room,
                        'warnings': warnings
                    })
                    # Remove from available
                    available_beds.remove(best_bed)
                else:
                    failed_allocations.append({
                        'student_id': student_id,
                        'reason': 'Assignment creation failed',
                        'warnings': warnings
                    })
            
            # Commit all if successful
            if successful_allocations and not failed_allocations:
                if self.commit_or_rollback():
                    return self.success_response(
                        {
                            'successful': successful_allocations,
                            'failed': failed_allocations,
                            'success_count': len(successful_allocations),
                            'failed_count': len(failed_allocations)
                        },
                        f"Allocated {len(successful_allocations)} students"
                    )
            
            # Partial success
            self.session.rollback()
            return self.error_response(
                "Batch allocation partially failed",
                {
                    'successful': len(successful_allocations),
                    'failed': len(failed_allocations),
                    'failed_details': failed_allocations
                }
            )
            
        except Exception as e:
            return self.handle_exception(e, "batch allocation")
    
    def _find_best_bed_for_student(
        self,
        student_id: str,
        available_beds: List,
        preferences: Dict[str, Any]
    ):
        """Find best matching bed for student."""
        if not available_beds:
            return None
        
        # Score each bed
        scored_beds = []
        for bed in available_beds:
            score = self._calculate_bed_match_score(bed, preferences)
            scored_beds.append((bed, score))
        
        # Sort by score
        scored_beds.sort(key=lambda x: x[1], reverse=True)
        
        return scored_beds[0][0] if scored_beds else None
    
    def _calculate_bed_match_score(
        self,
        bed,
        preferences: Dict[str, Any]
    ) -> float:
        """Calculate match score between bed and preferences."""
        score = 50.0
        
        # Bed type preference
        if preferences.get('bed_type') == bed.bed_type:
            score += 20
        
        # Bunk preference
        if preferences.get('prefers_upper_bunk') and bed.is_upper_bunk:
            score += 15
        if preferences.get('prefers_lower_bunk') and bed.is_lower_bunk:
            score += 15
        
        # Room features
        room = bed.room
        if preferences.get('is_ac') is not None:
            if room.is_ac == preferences['is_ac']:
                score += 10
        
        if preferences.get('has_bathroom') is not None:
            if room.has_attached_bathroom == preferences['has_bathroom']:
                score += 10
        
        # Price
        if preferences.get('max_price'):
            if room.price_monthly <= Decimal(str(preferences['max_price'])):
                score += 15
        
        return score
    
    def optimize_room_allocation(
        self,
        hostel_id: str
    ) -> Dict[str, Any]:
        """
        Run optimization algorithm for room allocation.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Response with optimization results
        """
        try:
            # Run optimization
            optimization = self.assignment_repo.run_assignment_optimization(
                hostel_id,
                'INITIAL_PLACEMENT',
                commit=True
            )
            
            return self.success_response(
                {
                    'optimization': optimization,
                    'assignments_generated': optimization.assignments_generated,
                    'score': float(optimization.overall_optimization_score or 0)
                },
                "Optimization completed"
            )
            
        except Exception as e:
            return self.handle_exception(e, "optimize allocation")