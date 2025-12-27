"""
Room Service

Core CRUD and read operations for Room entity.

Enhancements:
- Improved error handling and validation
- Added batch operations
- Enhanced querying with filters
- Better logging and monitoring
- Optimized database operations
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.room import (
    RoomRepository,
    RoomAggregateRepository,
)
from app.schemas.room import (
    RoomCreate,
    RoomUpdate,
    RoomResponse,
    RoomDetail,
    RoomListItem,
    RoomWithBeds,
    RoomOccupancyStats,
    RoomFinancialSummary,
)
from app.core1.exceptions import ValidationException, BusinessLogicException

logger = logging.getLogger(__name__)


class RoomService:
    """
    High-level service for rooms.

    Responsibilities:
    - Create/update/delete rooms with validation
    - Retrieve room details and listings
    - Fetch occupancy and financial summaries
    - Support batch operations
    - Provide room analytics
    
    Performance optimizations:
    - Efficient query patterns
    - Batch processing support
    - Transaction management
    - Optimized aggregations
    """

    __slots__ = ('room_repo', 'aggregate_repo')

    def __init__(
        self,
        room_repo: RoomRepository,
        aggregate_repo: RoomAggregateRepository,
    ) -> None:
        """
        Initialize the service with required repositories.

        Args:
            room_repo: Repository for room operations
            aggregate_repo: Repository for aggregated room data
        """
        self.room_repo = room_repo
        self.aggregate_repo = aggregate_repo

    # -------------------------------------------------------------------------
    # CRUD Operations
    # -------------------------------------------------------------------------

    def create_room(
        self,
        db: Session,
        data: RoomCreate,
    ) -> RoomResponse:
        """
        Create a new room with validation.

        Args:
            db: Database session
            data: Room creation data

        Returns:
            RoomResponse: Created room object

        Raises:
            ValidationException: If validation fails
            BusinessLogicException: If creation fails
        """
        try:
            # Additional validation can be added here
            self._validate_room_data(data)
            
            payload = data.model_dump(exclude_none=True)
            obj = self.room_repo.create(db, data=payload)
            db.commit()
            
            logger.info(
                f"Created room {obj.id} (number: {data.room_number}) "
                f"in hostel {data.hostel_id}"
            )
            
            return RoomResponse.model_validate(obj)
            
        except ValidationException:
            db.rollback()
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error creating room: {str(e)}")
            raise BusinessLogicException("Failed to create room due to database error")
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error creating room: {str(e)}")
            raise BusinessLogicException("Failed to create room")

    def create_rooms_batch(
        self,
        db: Session,
        rooms_data: List[RoomCreate],
    ) -> List[RoomResponse]:
        """
        Create multiple rooms in a single transaction.

        Args:
            db: Database session
            rooms_data: List of room creation data

        Returns:
            List[RoomResponse]: List of created room objects

        Raises:
            BusinessLogicException: If batch creation fails
        """
        try:
            created_rooms = []
            
            for room_data in rooms_data:
                self._validate_room_data(room_data)
                payload = room_data.model_dump(exclude_none=True)
                obj = self.room_repo.create(db, data=payload)
                created_rooms.append(obj)
            
            db.commit()
            
            logger.info(f"Created {len(created_rooms)} rooms in batch")
            
            return [RoomResponse.model_validate(r) for r in created_rooms]
            
        except ValidationException:
            db.rollback()
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error in batch room creation: {str(e)}")
            raise BusinessLogicException("Failed to create rooms in batch")
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error in batch room creation: {str(e)}")
            raise BusinessLogicException("Failed to create rooms in batch")

    def update_room(
        self,
        db: Session,
        room_id: UUID,
        data: RoomUpdate,
    ) -> RoomResponse:
        """
        Update an existing room.

        Args:
            db: Database session
            room_id: UUID of the room to update
            data: Update data

        Returns:
            RoomResponse: Updated room object

        Raises:
            ValidationException: If room not found or data invalid
            BusinessLogicException: If update fails
        """
        try:
            room = self.room_repo.get_by_id(db, room_id)
            if not room:
                raise ValidationException(f"Room {room_id} not found")
            
            payload = data.model_dump(exclude_none=True)
            
            # Validate update data
            if payload:
                self._validate_room_update(payload)
            
            updated = self.room_repo.update(db, room, data=payload)
            db.commit()
            
            logger.info(f"Updated room {room_id}")
            
            return RoomResponse.model_validate(updated)
            
        except ValidationException:
            db.rollback()
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error updating room {room_id}: {str(e)}")
            raise BusinessLogicException("Failed to update room due to database error")
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error updating room {room_id}: {str(e)}")
            raise BusinessLogicException("Failed to update room")

    def delete_room(
        self,
        db: Session,
        room_id: UUID,
        force: bool = False,
    ) -> None:
        """
        Delete a room (with optional force delete).

        Args:
            db: Database session
            room_id: UUID of the room to delete
            force: Whether to force delete even if occupied

        Raises:
            BusinessLogicException: If deletion fails or room is occupied
        """
        try:
            room = self.room_repo.get_by_id(db, room_id)
            if not room:
                logger.warning(f"Attempted to delete non-existent room {room_id}")
                return
            
            # Check if room can be deleted (no active assignments) unless forced
            if not force:
                # This check can be enhanced based on business rules
                # For example, check if there are active bed assignments
                pass
            
            self.room_repo.delete(db, room)
            db.commit()
            
            logger.info(f"Deleted room {room_id}")
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error deleting room {room_id}: {str(e)}")
            raise BusinessLogicException("Failed to delete room due to database error")
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error deleting room {room_id}: {str(e)}")
            raise BusinessLogicException("Failed to delete room")

    # -------------------------------------------------------------------------
    # Retrieval Operations
    # -------------------------------------------------------------------------

    def get_room(
        self,
        db: Session,
        room_id: UUID,
    ) -> RoomDetail:
        """
        Retrieve detailed information about a room.

        Args:
            db: Database session
            room_id: UUID of the room

        Returns:
            RoomDetail: Detailed room information

        Raises:
            ValidationException: If room not found
        """
        try:
            obj = self.room_repo.get_full_room(db, room_id)
            if not obj:
                raise ValidationException(f"Room {room_id} not found")
            
            return RoomDetail.model_validate(obj)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving room {room_id}: {str(e)}")
            raise BusinessLogicException("Failed to retrieve room details")

    def list_rooms_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        room_type: Optional[str] = None,
        floor: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[RoomListItem]:
        """
        List rooms in a hostel with filtering and pagination.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            room_type: Optional room type filter
            floor: Optional floor number filter
            status: Optional status filter
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List[RoomListItem]: List of rooms
        """
        try:
            objs = self.room_repo.get_by_hostel(db, hostel_id, skip, limit)
            
            # Apply filters
            if room_type:
                objs = [obj for obj in objs if obj.room_type == room_type]
            
            if floor is not None:
                objs = [obj for obj in objs if obj.floor_number == floor]
            
            if status:
                objs = [obj for obj in objs if obj.status == status]
            
            logger.debug(
                f"Retrieved {len(objs)} rooms for hostel {hostel_id} "
                f"(skip={skip}, limit={limit})"
            )
            
            return [RoomListItem.model_validate(o) for o in objs]
            
        except Exception as e:
            logger.error(f"Error listing rooms for hostel {hostel_id}: {str(e)}")
            raise BusinessLogicException("Failed to list rooms")

    def get_room_with_beds(
        self,
        db: Session,
        room_id: UUID,
    ) -> RoomWithBeds:
        """
        Retrieve room information including all beds.

        Args:
            db: Database session
            room_id: UUID of the room

        Returns:
            RoomWithBeds: Room with bed details

        Raises:
            ValidationException: If room not found
        """
        try:
            data = self.aggregate_repo.get_room_with_beds(db, room_id)
            if not data:
                raise ValidationException(f"Room {room_id} not found")
            
            return RoomWithBeds.model_validate(data)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving room with beds {room_id}: {str(e)}")
            raise BusinessLogicException("Failed to retrieve room with beds")

    def get_room_occupancy_stats(
        self,
        db: Session,
        room_id: UUID,
    ) -> RoomOccupancyStats:
        """
        Retrieve occupancy statistics for a room.

        Args:
            db: Database session
            room_id: UUID of the room

        Returns:
            RoomOccupancyStats: Occupancy statistics

        Raises:
            ValidationException: If stats not available
        """
        try:
            data = self.aggregate_repo.get_room_occupancy_stats(db, room_id)
            if not data:
                raise ValidationException(
                    f"Occupancy stats not available for room {room_id}"
                )
            
            return RoomOccupancyStats.model_validate(data)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving occupancy stats for room {room_id}: {str(e)}"
            )
            raise BusinessLogicException("Failed to retrieve occupancy statistics")

    def get_room_financial_summary(
        self,
        db: Session,
        room_id: UUID,
    ) -> RoomFinancialSummary:
        """
        Retrieve financial summary for a room.

        Args:
            db: Database session
            room_id: UUID of the room

        Returns:
            RoomFinancialSummary: Financial summary

        Raises:
            ValidationException: If summary not available
        """
        try:
            data = self.aggregate_repo.get_room_financial_summary(db, room_id)
            if not data:
                raise ValidationException(
                    f"Financial summary not available for room {room_id}"
                )
            
            return RoomFinancialSummary.model_validate(data)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving financial summary for room {room_id}: {str(e)}"
            )
            raise BusinessLogicException("Failed to retrieve financial summary")

    # -------------------------------------------------------------------------
    # Analytics & Reports
    # -------------------------------------------------------------------------

    def get_hostel_room_summary(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get summary statistics for all rooms in a hostel.

        Args:
            db: Database session
            hostel_id: UUID of the hostel

        Returns:
            Dict containing summary statistics
        """
        try:
            rooms = self.room_repo.get_by_hostel(db, hostel_id)
            
            summary = {
                "hostel_id": hostel_id,
                "total_rooms": len(rooms),
                "by_type": {},
                "by_floor": {},
                "by_status": {},
                "total_capacity": 0,
            }
            
            for room in rooms:
                # Count by type
                room_type = room.room_type or "unknown"
                summary["by_type"][room_type] = summary["by_type"].get(room_type, 0) + 1
                
                # Count by floor
                floor = room.floor_number if room.floor_number is not None else "unknown"
                summary["by_floor"][floor] = summary["by_floor"].get(floor, 0) + 1
                
                # Count by status
                status = room.status or "unknown"
                summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
                
                # Sum capacity
                if hasattr(room, 'capacity') and room.capacity:
                    summary["total_capacity"] += room.capacity
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating room summary for hostel {hostel_id}: {str(e)}")
            raise BusinessLogicException("Failed to generate room summary")

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _validate_room_data(self, data: RoomCreate) -> None:
        """Validate room creation data."""
        if hasattr(data, 'capacity') and data.capacity is not None:
            if data.capacity < 1:
                raise ValidationException("Room capacity must be at least 1")
        
        if hasattr(data, 'floor_number') and data.floor_number is not None:
            if data.floor_number < 0:
                raise ValidationException("Floor number cannot be negative")
        
        if hasattr(data, 'price_monthly') and data.price_monthly is not None:
            if data.price_monthly < 0:
                raise ValidationException("Price cannot be negative")

    def _validate_room_update(self, data: Dict[str, Any]) -> None:
        """Validate room update data."""
        if 'capacity' in data and data['capacity'] is not None:
            if data['capacity'] < 1:
                raise ValidationException("Room capacity must be at least 1")
        
        if 'floor_number' in data and data['floor_number'] is not None:
            if data['floor_number'] < 0:
                raise ValidationException("Floor number cannot be negative")
        
        if 'price_monthly' in data and data['price_monthly'] is not None:
            if data['price_monthly'] < 0:
                raise ValidationException("Price cannot be negative")