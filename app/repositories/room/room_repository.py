# app/repositories/room/room_repository.py
"""
Room repository with comprehensive room management operations.
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select, and_, or_, func, case
from sqlalchemy.orm import Session, joinedload

from app.models.room import (
    Room,
    RoomSpecification,
    RoomPricingHistory,
    RoomMaintenanceStatus,
    RoomAccessControl,
    RoomOccupancyLimit,
)
from app.models.base.enums import RoomStatus, RoomType
from .base_repository import BaseRepository


class RoomRepository(BaseRepository[Room]):
    """
    Repository for Room entity and related models.
    
    Handles:
    - Room CRUD operations
    - Room specifications
    - Pricing history
    - Maintenance status
    - Access control
    - Occupancy limits
    """

    def __init__(self, session: Session):
        super().__init__(Room, session)

    # ============================================================================
    # ROOM BASIC OPERATIONS
    # ============================================================================

    def create_room_with_details(
        self,
        room_data: Dict[str, Any],
        specification_data: Optional[Dict[str, Any]] = None,
        pricing_data: Optional[Dict[str, Any]] = None,
        commit: bool = True
    ) -> Room:
        """
        Create room with specifications and pricing.
        
        Args:
            room_data: Room data
            specification_data: Room specification data
            pricing_data: Initial pricing data
            commit: Whether to commit transaction
            
        Returns:
            Created room with related data
        """
        try:
            # Create room
            room = self.create(room_data, commit=False)
            
            # Create specification if provided
            if specification_data:
                spec = RoomSpecification(
                    room_id=room.id,
                    **specification_data
                )
                self.session.add(spec)
            
            # Create pricing history if provided
            if pricing_data:
                pricing = RoomPricingHistory(
                    room_id=room.id,
                    is_current=True,
                    effective_from=pricing_data.get('effective_from', date.today()),
                    **pricing_data
                )
                self.session.add(pricing)
            
            # Create default maintenance status
            maintenance = RoomMaintenanceStatus(
                room_id=room.id,
                is_under_maintenance=False,
                total_maintenance_count=0,
                total_maintenance_cost=Decimal('0.00')
            )
            self.session.add(maintenance)
            
            # Create default access control
            access = RoomAccessControl(
                room_id=room.id,
                access_method='KEY',
                master_key_access=True
            )
            self.session.add(access)
            
            # Create occupancy limit
            occupancy = RoomOccupancyLimit(
                room_id=room.id,
                maximum_occupants=room_data.get('total_beds', 1),
                minimum_occupants=1,
                recommended_occupants=room_data.get('total_beds', 1),
                current_occupants=0
            )
            self.session.add(occupancy)
            
            if commit:
                self.session.commit()
                self.session.refresh(room)
            
            return room
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to create room with details: {str(e)}")

    def find_by_room_number(
        self,
        hostel_id: str,
        room_number: str
    ) -> Optional[Room]:
        """
        Find room by hostel and room number.
        
        Args:
            hostel_id: Hostel ID
            room_number: Room number
            
        Returns:
            Room or None if not found
        """
        return self.find_by_criteria({
            'hostel_id': hostel_id,
            'room_number': room_number
        }).first() if self.find_by_criteria({
            'hostel_id': hostel_id,
            'room_number': room_number
        }) else None

    def find_rooms_by_hostel(
        self,
        hostel_id: str,
        include_deleted: bool = False
    ) -> List[Room]:
        """
        Find all rooms in a hostel.
        
        Args:
            hostel_id: Hostel ID
            include_deleted: Whether to include soft-deleted rooms
            
        Returns:
            List of rooms
        """
        return self.find_by_criteria(
            {'hostel_id': hostel_id},
            include_deleted=include_deleted,
            order_by='room_number'
        )

    # ============================================================================
    # ROOM SEARCH AND FILTERING
    # ============================================================================

    def search_available_rooms(
        self,
        hostel_id: str,
        room_type: Optional[RoomType] = None,
        min_beds: Optional[int] = None,
        is_ac: Optional[bool] = None,
        has_attached_bathroom: Optional[bool] = None,
        max_price: Optional[Decimal] = None,
        floor_number: Optional[int] = None,
        wing: Optional[str] = None
    ) -> List[Room]:
        """
        Search available rooms with filters.
        
        Args:
            hostel_id: Hostel ID
            room_type: Room type filter
            min_beds: Minimum available beds
            is_ac: AC filter
            has_attached_bathroom: Bathroom filter
            max_price: Maximum price filter
            floor_number: Floor number filter
            wing: Wing filter
            
        Returns:
            List of matching available rooms
        """
        query = select(Room).where(
            and_(
                Room.hostel_id == hostel_id,
                Room.is_available_for_booking == True,
                Room.is_deleted == False
            )
        )
        
        if room_type:
            query = query.where(Room.room_type == room_type)
        
        if min_beds is not None:
            query = query.where(Room.available_beds >= min_beds)
        
        if is_ac is not None:
            query = query.where(Room.is_ac == is_ac)
        
        if has_attached_bathroom is not None:
            query = query.where(Room.has_attached_bathroom == has_attached_bathroom)
        
        if max_price is not None:
            query = query.where(Room.price_monthly <= max_price)
        
        if floor_number is not None:
            query = query.where(Room.floor_number == floor_number)
        
        if wing:
            query = query.where(Room.wing == wing)
        
        query = query.order_by(Room.price_monthly, Room.room_number)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_rooms_by_status(
        self,
        hostel_id: str,
        status: RoomStatus
    ) -> List[Room]:
        """
        Find rooms by status.
        
        Args:
            hostel_id: Hostel ID
            status: Room status
            
        Returns:
            List of rooms with specified status
        """
        return self.find_by_criteria({
            'hostel_id': hostel_id,
            'status': status
        })

    def find_rooms_under_maintenance(
        self,
        hostel_id: str
    ) -> List[Room]:
        """
        Find rooms currently under maintenance.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            List of rooms under maintenance
        """
        return self.find_by_criteria({
            'hostel_id': hostel_id,
            'is_under_maintenance': True
        })

    # ============================================================================
    # ROOM OCCUPANCY OPERATIONS
    # ============================================================================

    def update_room_occupancy(
        self,
        room_id: str,
        occupied_beds: int,
        commit: bool = True
    ) -> Optional[Room]:
        """
        Update room occupancy.
        
        Args:
            room_id: Room ID
            occupied_beds: Number of occupied beds
            commit: Whether to commit transaction
            
        Returns:
            Updated room
        """
        room = self.find_by_id(room_id)
        if not room:
            return None
        
        room.occupied_beds = occupied_beds
        room.available_beds = max(0, room.total_beds - occupied_beds)
        room.last_occupancy_change = datetime.utcnow()
        
        # Update status based on occupancy
        if room.available_beds == 0:
            room.status = RoomStatus.FULL
        elif room.available_beds > 0 and not room.is_under_maintenance:
            room.status = RoomStatus.AVAILABLE
        
        if commit:
            self.session.commit()
            self.session.refresh(room)
        
        return room

    def get_room_occupancy_rate(self, room_id: str) -> Optional[Decimal]:
        """
        Calculate room occupancy rate.
        
        Args:
            room_id: Room ID
            
        Returns:
            Occupancy rate as percentage or None if room not found
        """
        room = self.find_by_id(room_id)
        if not room:
            return None
        
        return room.occupancy_rate

    def find_fully_occupied_rooms(self, hostel_id: str) -> List[Room]:
        """
        Find fully occupied rooms.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            List of fully occupied rooms
        """
        query = select(Room).where(
            and_(
                Room.hostel_id == hostel_id,
                Room.occupied_beds >= Room.total_beds,
                Room.is_deleted == False
            )
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_vacant_rooms(
        self,
        hostel_id: str,
        min_beds: int = 1
    ) -> List[Room]:
        """
        Find rooms with vacant beds.
        
        Args:
            hostel_id: Hostel ID
            min_beds: Minimum number of vacant beds
            
        Returns:
            List of rooms with vacant beds
        """
        query = select(Room).where(
            and_(
                Room.hostel_id == hostel_id,
                Room.available_beds >= min_beds,
                Room.is_available_for_booking == True,
                Room.is_deleted == False
            )
        ).order_by(Room.available_beds.desc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ============================================================================
    # ROOM PRICING OPERATIONS
    # ============================================================================

    def update_room_pricing(
        self,
        room_id: str,
        new_pricing: Dict[str, Any],
        effective_from: date,
        reason: Optional[str] = None,
        commit: bool = True
    ) -> RoomPricingHistory:
        """
        Update room pricing with history tracking.
        
        Args:
            room_id: Room ID
            new_pricing: New pricing data
            effective_from: Effective date
            reason: Reason for price change
            commit: Whether to commit transaction
            
        Returns:
            New pricing history record
        """
        try:
            room = self.find_by_id(room_id)
            if not room:
                raise ValueError(f"Room {room_id} not found")
            
            # Mark current pricing as historical
            current_pricing = self.session.execute(
                select(RoomPricingHistory).where(
                    and_(
                        RoomPricingHistory.room_id == room_id,
                        RoomPricingHistory.is_current == True
                    )
                )
            ).scalar_one_or_none()
            
            if current_pricing:
                current_pricing.is_current = False
                current_pricing.effective_to = effective_from
            
            # Calculate price change percentage
            price_change_pct = None
            if current_pricing and current_pricing.price_monthly:
                old_price = current_pricing.price_monthly
                new_price = new_pricing.get('price_monthly')
                if new_price and old_price:
                    price_change_pct = ((new_price - old_price) / old_price * 100)
            
            # Create new pricing record
            new_pricing_record = RoomPricingHistory(
                room_id=room_id,
                price_monthly=new_pricing.get('price_monthly'),
                price_quarterly=new_pricing.get('price_quarterly'),
                price_half_yearly=new_pricing.get('price_half_yearly'),
                price_yearly=new_pricing.get('price_yearly'),
                effective_from=effective_from,
                is_current=True,
                change_reason=reason,
                previous_price_monthly=current_pricing.price_monthly if current_pricing else None,
                price_change_percentage=price_change_pct
            )
            self.session.add(new_pricing_record)
            
            # Update room's current pricing
            room.price_monthly = new_pricing.get('price_monthly')
            room.price_quarterly = new_pricing.get('price_quarterly')
            room.price_half_yearly = new_pricing.get('price_half_yearly')
            room.price_yearly = new_pricing.get('price_yearly')
            
            if commit:
                self.session.commit()
                self.session.refresh(new_pricing_record)
            
            return new_pricing_record
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to update room pricing: {str(e)}")

    def get_pricing_history(
        self,
        room_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[RoomPricingHistory]:
        """
        Get room pricing history.
        
        Args:
            room_id: Room ID
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            List of pricing history records
        """
        query = select(RoomPricingHistory).where(
            RoomPricingHistory.room_id == room_id
        )
        
        if start_date:
            query = query.where(RoomPricingHistory.effective_from >= start_date)
        
        if end_date:
            query = query.where(
                or_(
                    RoomPricingHistory.effective_to <= end_date,
                    RoomPricingHistory.effective_to.is_(None)
                )
            )
        
        query = query.order_by(RoomPricingHistory.effective_from.desc())
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ============================================================================
    # ROOM MAINTENANCE OPERATIONS
    # ============================================================================

    def mark_room_under_maintenance(
        self,
        room_id: str,
        maintenance_type: str,
        start_date: date,
        expected_end_date: Optional[date] = None,
        notes: Optional[str] = None,
        commit: bool = True
    ) -> bool:
        """
        Mark room as under maintenance.
        
        Args:
            room_id: Room ID
            maintenance_type: Type of maintenance
            start_date: Maintenance start date
            expected_end_date: Expected completion date
            notes: Maintenance notes
            commit: Whether to commit transaction
            
        Returns:
            True if successful
        """
        try:
            room = self.find_by_id(room_id)
            if not room:
                return False
            
            # Update room
            room.is_under_maintenance = True
            room.maintenance_start_date = start_date
            room.maintenance_end_date = expected_end_date
            room.maintenance_notes = notes
            room.status = RoomStatus.MAINTENANCE
            room.is_available_for_booking = False
            room.last_status_change = datetime.utcnow()
            
            # Update maintenance status
            maintenance_status = self.session.execute(
                select(RoomMaintenanceStatus).where(
                    RoomMaintenanceStatus.room_id == room_id
                )
            ).scalar_one_or_none()
            
            if maintenance_status:
                maintenance_status.is_under_maintenance = True
                maintenance_status.maintenance_type = maintenance_type
                maintenance_status.maintenance_start_date = datetime.utcnow()
                maintenance_status.expected_completion_date = datetime.combine(
                    expected_end_date, datetime.min.time()
                ) if expected_end_date else None
                maintenance_status.maintenance_description = notes
            
            if commit:
                self.session.commit()
            
            return True
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to mark room under maintenance: {str(e)}")

    def complete_room_maintenance(
        self,
        room_id: str,
        actual_cost: Optional[Decimal] = None,
        completion_notes: Optional[str] = None,
        commit: bool = True
    ) -> bool:
        """
        Complete room maintenance.
        
        Args:
            room_id: Room ID
            actual_cost: Actual maintenance cost
            completion_notes: Completion notes
            commit: Whether to commit transaction
            
        Returns:
            True if successful
        """
        try:
            room = self.find_by_id(room_id)
            if not room or not room.is_under_maintenance:
                return False
            
            # Update room
            room.is_under_maintenance = False
            room.last_maintenance_date = date.today()
            room.status = RoomStatus.AVAILABLE if room.available_beds > 0 else RoomStatus.FULL
            room.is_available_for_booking = True
            room.last_status_change = datetime.utcnow()
            
            # Update maintenance status
            maintenance_status = self.session.execute(
                select(RoomMaintenanceStatus).where(
                    RoomMaintenanceStatus.room_id == room_id
                )
            ).scalar_one_or_none()
            
            if maintenance_status:
                maintenance_status.is_under_maintenance = False
                maintenance_status.actual_completion_date = datetime.utcnow()
                maintenance_status.actual_cost = actual_cost or Decimal('0.00')
                maintenance_status.last_maintenance_date = date.today()
                maintenance_status.last_maintenance_type = maintenance_status.maintenance_type
                maintenance_status.total_maintenance_count += 1
                if actual_cost:
                    maintenance_status.total_maintenance_cost += actual_cost
                
                if completion_notes:
                    maintenance_status.maintenance_notes = completion_notes
            
            if commit:
                self.session.commit()
            
            return True
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to complete room maintenance: {str(e)}")

    # ============================================================================
    # ROOM STATISTICS AND ANALYTICS
    # ============================================================================

    def get_hostel_room_statistics(self, hostel_id: str) -> Dict[str, Any]:
        """
        Get comprehensive room statistics for a hostel.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Dictionary with room statistics
        """
        query = select(
            func.count(Room.id).label('total_rooms'),
            func.sum(Room.total_beds).label('total_beds'),
            func.sum(Room.occupied_beds).label('occupied_beds'),
            func.sum(Room.available_beds).label('available_beds'),
            func.sum(
                case((Room.is_under_maintenance == True, 1), else_=0)
            ).label('maintenance_rooms'),
            func.sum(
                case((Room.is_ac == True, 1), else_=0)
            ).label('ac_rooms'),
            func.sum(
                case((Room.has_attached_bathroom == True, 1), else_=0)
            ).label('attached_bathroom_rooms'),
            func.avg(Room.price_monthly).label('avg_price'),
            func.min(Room.price_monthly).label('min_price'),
            func.max(Room.price_monthly).label('max_price')
        ).where(
            and_(
                Room.hostel_id == hostel_id,
                Room.is_deleted == False
            )
        )
        
        result = self.session.execute(query).one()
        
        total_beds = result.total_beds or 0
        occupied_beds = result.occupied_beds or 0
        occupancy_rate = (occupied_beds / total_beds * 100) if total_beds > 0 else 0
        
        return {
            'total_rooms': result.total_rooms or 0,
            'total_beds': total_beds,
            'occupied_beds': occupied_beds,
            'available_beds': result.available_beds or 0,
            'occupancy_rate': round(occupancy_rate, 2),
            'maintenance_rooms': result.maintenance_rooms or 0,
            'ac_rooms': result.ac_rooms or 0,
            'attached_bathroom_rooms': result.attached_bathroom_rooms or 0,
            'avg_price': float(result.avg_price) if result.avg_price else 0,
            'min_price': float(result.min_price) if result.min_price else 0,
            'max_price': float(result.max_price) if result.max_price else 0
        }

    def get_room_type_distribution(self, hostel_id: str) -> Dict[str, int]:
        """
        Get room type distribution.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Dictionary with room type counts
        """
        query = select(
            Room.room_type,
            func.count(Room.id).label('count')
        ).where(
            and_(
                Room.hostel_id == hostel_id,
                Room.is_deleted == False
            )
        ).group_by(Room.room_type)
        
        result = self.session.execute(query)
        
        return {row.room_type: row.count for row in result}

    def get_floor_wise_occupancy(self, hostel_id: str) -> List[Dict[str, Any]]:
        """
        Get floor-wise occupancy statistics.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            List of floor statistics
        """
        query = select(
            Room.floor_number,
            func.count(Room.id).label('total_rooms'),
            func.sum(Room.total_beds).label('total_beds'),
            func.sum(Room.occupied_beds).label('occupied_beds'),
            func.sum(Room.available_beds).label('available_beds')
        ).where(
            and_(
                Room.hostel_id == hostel_id,
                Room.is_deleted == False
            )
        ).group_by(Room.floor_number).order_by(Room.floor_number)
        
        result = self.session.execute(query)
        
        floors = []
        for row in result:
            total_beds = row.total_beds or 0
            occupied_beds = row.occupied_beds or 0
            occupancy_rate = (occupied_beds / total_beds * 100) if total_beds > 0 else 0
            
            floors.append({
                'floor_number': row.floor_number,
                'total_rooms': row.total_rooms,
                'total_beds': total_beds,
                'occupied_beds': occupied_beds,
                'available_beds': row.available_beds or 0,
                'occupancy_rate': round(occupancy_rate, 2)
            })
        
        return floors

    # ============================================================================
    # ROOM AVAILABILITY CHECKS
    # ============================================================================

    def check_room_availability(
        self,
        room_id: str,
        required_beds: int = 1
    ) -> bool:
        """
        Check if room has required bed availability.
        
        Args:
            room_id: Room ID
            required_beds: Number of beds required
            
        Returns:
            True if available, False otherwise
        """
        room = self.find_by_id(room_id)
        if not room:
            return False
        
        return room.can_accommodate(required_beds)

    def find_best_match_rooms(
        self,
        hostel_id: str,
        preferences: Dict[str, Any],
        limit: int = 10
    ) -> List[Room]:
        """
        Find best matching rooms based on preferences.
        
        Args:
            hostel_id: Hostel ID
            preferences: Preference criteria
            limit: Maximum number of results
            
        Returns:
            List of best matching rooms
        """
        # Start with available rooms
        query = select(Room).where(
            and_(
                Room.hostel_id == hostel_id,
                Room.is_available_for_booking == True,
                Room.available_beds >= preferences.get('beds_required', 1),
                Room.is_deleted == False
            )
        )
        
        # Apply preference filters
        if preferences.get('room_type'):
            query = query.where(Room.room_type == preferences['room_type'])
        
        if preferences.get('is_ac') is not None:
            query = query.where(Room.is_ac == preferences['is_ac'])
        
        if preferences.get('has_attached_bathroom') is not None:
            query = query.where(
                Room.has_attached_bathroom == preferences['has_attached_bathroom']
            )
        
        if preferences.get('max_price'):
            query = query.where(Room.price_monthly <= preferences['max_price'])
        
        if preferences.get('floor_number'):
            query = query.where(Room.floor_number == preferences['floor_number'])
        
        # Order by price and availability
        query = query.order_by(
            Room.price_monthly,
            Room.available_beds.desc()
        ).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())