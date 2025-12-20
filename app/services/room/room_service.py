# app/services/room/room_service.py
"""
Room service with comprehensive room management operations.
"""

from typing import Dict, Any, List, Optional
from datetime import date
from decimal import Decimal

from app.services.room.base_service import BaseService
from app.repositories.room import (
    RoomRepository,
    RoomAvailabilityRepository,
    RoomTypeRepository,
    BedRepository
)


class RoomService(BaseService):
    """
    Room service handling room business logic.
    
    Orchestrates:
    - Room creation with beds
    - Room search and filtering
    - Occupancy management
    - Room statistics
    """
    
    def __init__(self, session):
        super().__init__(session)
        self.room_repo = RoomRepository(session)
        self.availability_repo = RoomAvailabilityRepository(session)
        self.type_repo = RoomTypeRepository(session)
        self.bed_repo = BedRepository(session)
    
    def create_room_with_beds(
        self,
        room_data: Dict[str, Any],
        num_beds: int,
        bed_configuration: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create room with specified number of beds.
        
        Business Rules:
        1. Validate room data
        2. Create room entity
        3. Create beds based on configuration
        4. Initialize availability tracking
        5. Update room type statistics
        
        Args:
            room_data: Room creation data
            num_beds: Number of beds to create
            bed_configuration: Bed setup configuration
            
        Returns:
            Response with created room and beds
        """
        try:
            # Validate
            if num_beds < 1:
                return self.error_response("Number of beds must be at least 1")
            
            if num_beds > 20:
                return self.error_response("Maximum 20 beds per room allowed")
            
            # Create room
            room = self.room_repo.create_room_with_details(
                room_data,
                commit=False
            )
            
            # Create beds
            beds = []
            bed_config = bed_configuration or {}
            
            for i in range(1, num_beds + 1):
                bed_data = {
                    'room_id': room.id,
                    'bed_number': str(i),
                    'bed_type': bed_config.get('bed_type', 'SINGLE'),
                    'status': 'AVAILABLE',
                    'is_upper_bunk': bed_config.get('is_bunk') and i % 2 == 0,
                    'is_lower_bunk': bed_config.get('is_bunk') and i % 2 == 1,
                }
                
                bed = self.bed_repo.create_bed_with_details(
                    bed_data,
                    condition_data=bed_config.get('condition'),
                    configuration_data=bed_config.get('configuration'),
                    commit=False
                )
                beds.append(bed)
            
            # Update room totals
            room.total_beds = num_beds
            room.available_beds = num_beds
            room.occupied_beds = 0
            
            # Create availability tracking
            self.availability_repo.sync_availability_with_room(
                room.id,
                commit=False
            )
            
            # Update room type statistics if type exists
            if room_data.get('room_type'):
                room_type = self.type_repo.find_by_type(
                    room_data['hostel_id'],
                    room_data['room_type']
                )
                if room_type:
                    self.type_repo.sync_type_availability_from_rooms(
                        room_type.id,
                        commit=False
                    )
            
            # Commit all
            if not self.commit_or_rollback():
                return self.error_response("Failed to save room and beds")
            
            return self.success_response(
                {
                    'room': room,
                    'beds': beds,
                    'total_beds': num_beds
                },
                f"Room {room.room_number} created with {num_beds} beds"
            )
            
        except Exception as e:
            return self.handle_exception(e, "create room with beds")
    
    def search_available_rooms(
        self,
        hostel_id: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Search for available rooms with filters.
        
        Args:
            hostel_id: Hostel ID
            filters: Search filters (room_type, min_beds, is_ac, etc.)
            
        Returns:
            Response with matching rooms
        """
        try:
            filters = filters or {}
            
            rooms = self.room_repo.search_available_rooms(
                hostel_id=hostel_id,
                room_type=filters.get('room_type'),
                min_beds=filters.get('min_beds', 1),
                is_ac=filters.get('is_ac'),
                has_attached_bathroom=filters.get('has_bathroom'),
                max_price=filters.get('max_price'),
                floor_number=filters.get('floor'),
                wing=filters.get('wing')
            )
            
            return self.success_response(
                {
                    'rooms': rooms,
                    'count': len(rooms),
                    'filters_applied': filters
                },
                f"Found {len(rooms)} available rooms"
            )
            
        except Exception as e:
            return self.handle_exception(e, "search rooms")
    
    def get_room_details(
        self,
        room_id: str,
        include_beds: bool = True,
        include_amenities: bool = True,
        include_assignments: bool = False
    ) -> Dict[str, Any]:
        """
        Get comprehensive room details.
        
        Args:
            room_id: Room ID
            include_beds: Include bed details
            include_amenities: Include amenity details
            include_assignments: Include assignment details
            
        Returns:
            Response with room details
        """
        try:
            room = self.room_repo.find_by_id(room_id)
            if not room:
                return self.error_response("Room not found")
            
            details = {
                'room': room,
                'occupancy_rate': float(room.occupancy_rate),
                'revenue_potential': float(room.price_monthly * room.total_beds)
            }
            
            if include_beds:
                beds = self.bed_repo.find_beds_by_room(room_id)
                details['beds'] = beds
                details['bed_statistics'] = self.bed_repo.get_room_bed_statistics(room_id)
            
            if include_amenities:
                from app.repositories.room import RoomAmenityRepository
                amenity_repo = RoomAmenityRepository(self.session)
                details['amenities'] = amenity_repo.find_amenities_by_room(room_id)
            
            if include_assignments:
                from app.repositories.room import BedAssignmentRepository
                assignment_repo = BedAssignmentRepository(self.session)
                details['active_assignments'] = assignment_repo.find_active_assignments(
                    room_id=room_id
                )
            
            # Get availability
            availability = self.availability_repo.get_room_availability(room_id)
            if availability:
                details['availability'] = availability
            
            return self.success_response(details, "Room details retrieved")
            
        except Exception as e:
            return self.handle_exception(e, "get room details")
    
    def update_room_occupancy(
        self,
        room_id: str,
        change: int
    ) -> Dict[str, Any]:
        """
        Update room occupancy (increment or decrement).
        
        Args:
            room_id: Room ID
            change: Change in occupancy (+1 or -1)
            
        Returns:
            Response with updated room
        """
        try:
            room = self.room_repo.find_by_id(room_id)
            if not room:
                return self.error_response("Room not found")
            
            new_occupied = room.occupied_beds + change
            
            if new_occupied < 0:
                return self.error_response("Cannot have negative occupancy")
            
            if new_occupied > room.total_beds:
                return self.error_response("Occupancy exceeds total beds")
            
            room = self.room_repo.update_room_occupancy(
                room_id,
                new_occupied,
                commit=False
            )
            
            # Sync availability
            self.availability_repo.sync_availability_with_room(
                room_id,
                commit=False
            )
            
            if not self.commit_or_rollback():
                return self.error_response("Failed to update occupancy")
            
            return self.success_response(
                {
                    'room': room,
                    'occupancy_rate': float(room.occupancy_rate)
                },
                "Occupancy updated successfully"
            )
            
        except Exception as e:
            return self.handle_exception(e, "update occupancy")
    
    def get_hostel_statistics(
        self,
        hostel_id: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive hostel room statistics.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Response with statistics
        """
        try:
            stats = self.room_repo.get_hostel_room_statistics(hostel_id)
            type_distribution = self.room_repo.get_room_type_distribution(hostel_id)
            floor_occupancy = self.room_repo.get_floor_wise_occupancy(hostel_id)
            
            return self.success_response(
                {
                    'overall_statistics': stats,
                    'type_distribution': type_distribution,
                    'floor_occupancy': floor_occupancy
                },
                "Statistics retrieved successfully"
            )
            
        except Exception as e:
            return self.handle_exception(e, "get statistics")
    
    def find_best_match(
        self,
        hostel_id: str,
        preferences: Dict[str, Any],
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Find best matching rooms based on preferences.
        
        Args:
            hostel_id: Hostel ID
            preferences: User preferences
            limit: Maximum results
            
        Returns:
            Response with best matching rooms
        """
        try:
            rooms = self.room_repo.find_best_match_rooms(
                hostel_id,
                preferences,
                limit
            )
            
            # Calculate match scores
            scored_rooms = []
            for room in rooms:
                score = self._calculate_match_score(room, preferences)
                scored_rooms.append({
                    'room': room,
                    'match_score': score,
                    'match_percentage': min(100, score)
                })
            
            # Sort by score
            scored_rooms.sort(key=lambda x: x['match_score'], reverse=True)
            
            return self.success_response(
                {
                    'matches': scored_rooms,
                    'count': len(scored_rooms)
                },
                f"Found {len(scored_rooms)} matching rooms"
            )
            
        except Exception as e:
            return self.handle_exception(e, "find best match")
    
    def _calculate_match_score(
        self,
        room,
        preferences: Dict[str, Any]
    ) -> float:
        """Calculate match score between room and preferences."""
        score = 50.0  # Base score
        
        # Room type match
        if preferences.get('room_type') and room.room_type == preferences['room_type']:
            score += 20
        
        # AC preference
        if preferences.get('is_ac') is not None:
            if room.is_ac == preferences['is_ac']:
                score += 15
        
        # Bathroom preference
        if preferences.get('has_bathroom') is not None:
            if room.has_attached_bathroom == preferences['has_bathroom']:
                score += 10
        
        # Price preference
        if preferences.get('max_price'):
            if room.price_monthly <= Decimal(str(preferences['max_price'])):
                score += 15
                # Bonus for lower price
                price_ratio = room.price_monthly / Decimal(str(preferences['max_price']))
                score += (1 - float(price_ratio)) * 10
        
        # Bed availability
        if preferences.get('beds_required', 1) <= room.available_beds:
            score += 10
        
        return min(100.0, score)