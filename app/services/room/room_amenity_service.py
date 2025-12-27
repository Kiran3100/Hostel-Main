"""
Room Amenity Service

Manages amenities attached to rooms (furniture, appliances, etc.).

Enhancements:
- Added comprehensive error handling
- Improved logging
- Added batch operations
- Enhanced validation
- Support for amenity categories
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.room import RoomAmenityRepository, RoomRepository
from app.models.room.room_amenity import RoomAmenity
from app.schemas.room import RoomAmenityCreate, RoomAmenityUpdate, RoomAmenityResponse
from app.core1.exceptions import ValidationException, BusinessLogicException

logger = logging.getLogger(__name__)


class RoomAmenityService:
    """
    High-level service for room amenities.

    Responsibilities:
    - List amenities in a room with filtering
    - Add/update/remove amenities with validation
    - Batch operations for efficiency
    - Track amenity condition and maintenance
    
    Performance optimizations:
    - Batch processing support
    - Efficient queries with filtering
    - Transaction management
    """

    __slots__ = ('amenity_repo', 'room_repo')

    def __init__(
        self,
        amenity_repo: RoomAmenityRepository,
        room_repo: Optional[RoomRepository] = None,
    ) -> None:
        """
        Initialize the service with amenity repository.

        Args:
            amenity_repo: Repository for room amenity operations
            room_repo: Optional room repository for validation
        """
        self.amenity_repo = amenity_repo
        self.room_repo = room_repo

    def list_amenities_for_room(
        self,
        db: Session,
        room_id: UUID,
        amenity_type: Optional[str] = None,
        condition_filter: Optional[str] = None,
    ) -> List[RoomAmenity]:
        """
        List amenities in a room with optional filtering.

        Args:
            db: Database session
            room_id: UUID of the room
            amenity_type: Optional filter by amenity type
            condition_filter: Optional filter by condition

        Returns:
            List[RoomAmenity]: List of amenities in the room
        """
        try:
            amenities = self.amenity_repo.get_by_room_id(db, room_id)
            
            # Apply filters
            if amenity_type:
                amenities = [a for a in amenities if a.amenity_type == amenity_type]
            
            if condition_filter:
                amenities = [a for a in amenities if a.condition == condition_filter]
            
            logger.debug(f"Retrieved {len(amenities)} amenities for room {room_id}")
            
            return amenities
            
        except Exception as e:
            logger.error(f"Error listing amenities for room {room_id}: {str(e)}")
            raise BusinessLogicException("Failed to list room amenities")

    def add_amenity_to_room(
        self,
        db: Session,
        room_id: UUID,
        amenity_type: str,
        name: str,
        condition: Optional[str] = None,
        quantity: int = 1,
        additional_details: Optional[Dict[str, Any]] = None,
    ) -> RoomAmenity:
        """
        Add a new amenity to a room with validation.

        Args:
            db: Database session
            room_id: UUID of the room
            amenity_type: Type of amenity (e.g., 'furniture', 'appliance')
            name: Name of the amenity
            condition: Optional condition status
            quantity: Number of items (default: 1)
            additional_details: Optional additional details

        Returns:
            RoomAmenity: Created amenity object

        Raises:
            ValidationException: If validation fails
            BusinessLogicException: If creation fails
        """
        try:
            # Validate room exists if room_repo is available
            if self.room_repo:
                room = self.room_repo.get_by_id(db, room_id)
                if not room:
                    raise ValidationException(f"Room {room_id} not found")
            
            # Build amenity data
            amenity_data = {
                "room_id": room_id,
                "amenity_type": amenity_type,
                "name": name,
                "condition": condition or "good",
                "quantity": quantity,
            }
            
            if additional_details:
                amenity_data.update(additional_details)
            
            obj = self.amenity_repo.create(db, data=amenity_data)
            db.commit()
            
            logger.info(f"Added amenity '{name}' to room {room_id}")
            
            return obj
            
        except ValidationException:
            db.rollback()
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error adding amenity: {str(e)}")
            raise BusinessLogicException("Failed to add amenity due to database error")
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error adding amenity: {str(e)}")
            raise BusinessLogicException("Failed to add amenity")

    def add_amenities_batch(
        self,
        db: Session,
        room_id: UUID,
        amenities_data: List[Dict[str, Any]],
    ) -> List[RoomAmenity]:
        """
        Add multiple amenities to a room in a single transaction.

        Args:
            db: Database session
            room_id: UUID of the room
            amenities_data: List of amenity data dictionaries

        Returns:
            List[RoomAmenity]: List of created amenity objects

        Raises:
            BusinessLogicException: If batch creation fails
        """
        try:
            # Validate room exists if room_repo is available
            if self.room_repo:
                room = self.room_repo.get_by_id(db, room_id)
                if not room:
                    raise ValidationException(f"Room {room_id} not found")
            
            created_amenities = []
            
            for amenity_data in amenities_data:
                # Ensure room_id is set
                amenity_data["room_id"] = room_id
                
                # Set defaults
                if "condition" not in amenity_data:
                    amenity_data["condition"] = "good"
                if "quantity" not in amenity_data:
                    amenity_data["quantity"] = 1
                
                obj = self.amenity_repo.create(db, data=amenity_data)
                created_amenities.append(obj)
            
            db.commit()
            
            logger.info(f"Added {len(created_amenities)} amenities to room {room_id}")
            
            return created_amenities
            
        except ValidationException:
            db.rollback()
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error in batch amenity creation: {str(e)}")
            raise BusinessLogicException("Failed to add amenities in batch")
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error in batch amenity creation: {str(e)}")
            raise BusinessLogicException("Failed to add amenities in batch")

    def update_amenity(
        self,
        db: Session,
        amenity_id: UUID,
        name: Optional[str] = None,
        condition: Optional[str] = None,
        quantity: Optional[int] = None,
        additional_updates: Optional[Dict[str, Any]] = None,
    ) -> RoomAmenity:
        """
        Update an existing amenity.

        Args:
            db: Database session
            amenity_id: UUID of the amenity
            name: Optional new name
            condition: Optional new condition
            quantity: Optional new quantity
            additional_updates: Optional additional fields to update

        Returns:
            RoomAmenity: Updated amenity object

        Raises:
            ValidationException: If amenity not found
            BusinessLogicException: If update fails
        """
        try:
            amenity = self.amenity_repo.get_by_id(db, amenity_id)
            if not amenity:
                raise ValidationException(f"Amenity {amenity_id} not found")
            
            # Build update payload
            payload: Dict[str, Any] = {}
            
            if name is not None:
                payload["name"] = name
            if condition is not None:
                payload["condition"] = condition
            if quantity is not None:
                payload["quantity"] = quantity
            
            if additional_updates:
                payload.update(additional_updates)
            
            if not payload:
                logger.warning(f"No updates provided for amenity {amenity_id}")
                return amenity
            
            updated = self.amenity_repo.update(db, amenity, payload)
            db.commit()
            
            logger.info(f"Updated amenity {amenity_id}")
            
            return updated
            
        except ValidationException:
            db.rollback()
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error updating amenity {amenity_id}: {str(e)}")
            raise BusinessLogicException("Failed to update amenity due to database error")
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error updating amenity {amenity_id}: {str(e)}")
            raise BusinessLogicException("Failed to update amenity")

    def remove_amenity(
        self,
        db: Session,
        amenity_id: UUID,
    ) -> None:
        """
        Remove an amenity from a room.

        Args:
            db: Database session
            amenity_id: UUID of the amenity to remove

        Raises:
            BusinessLogicException: If removal fails
        """
        try:
            amenity = self.amenity_repo.get_by_id(db, amenity_id)
            if not amenity:
                logger.warning(f"Attempted to remove non-existent amenity {amenity_id}")
                return
            
            self.amenity_repo.delete(db, amenity)
            db.commit()
            
            logger.info(f"Removed amenity {amenity_id}")
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error removing amenity {amenity_id}: {str(e)}")
            raise BusinessLogicException("Failed to remove amenity due to database error")
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error removing amenity {amenity_id}: {str(e)}")
            raise BusinessLogicException("Failed to remove amenity")

    def get_amenity_summary_for_room(
        self,
        db: Session,
        room_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get summary statistics of amenities in a room.

        Args:
            db: Database session
            room_id: UUID of the room

        Returns:
            Dict containing summary statistics
        """
        try:
            amenities = self.amenity_repo.get_by_room_id(db, room_id)
            
            summary = {
                "total_count": len(amenities),
                "by_type": {},
                "by_condition": {},
                "total_quantity": 0,
            }
            
            for amenity in amenities:
                # Count by type
                amenity_type = amenity.amenity_type or "unknown"
                summary["by_type"][amenity_type] = summary["by_type"].get(amenity_type, 0) + 1
                
                # Count by condition
                condition = amenity.condition or "unknown"
                summary["by_condition"][condition] = summary["by_condition"].get(condition, 0) + 1
                
                # Sum quantities
                if hasattr(amenity, 'quantity') and amenity.quantity:
                    summary["total_quantity"] += amenity.quantity
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating amenity summary for room {room_id}: {str(e)}")
            raise BusinessLogicException("Failed to generate amenity summary")

    def check_amenity_maintenance_needed(
        self,
        db: Session,
        room_id: UUID,
    ) -> List[RoomAmenity]:
        """
        Check which amenities in a room need maintenance.

        Args:
            db: Database session
            room_id: UUID of the room

        Returns:
            List[RoomAmenity]: Amenities needing maintenance
        """
        try:
            amenities = self.amenity_repo.get_by_room_id(db, room_id)
            
            # Define conditions that require maintenance
            maintenance_conditions = {
                "poor",
                "damaged",
                "needs_repair",
                "broken",
            }
            
            needs_maintenance = [
                a for a in amenities
                if a.condition and a.condition.lower() in maintenance_conditions
            ]
            
            logger.info(
                f"Found {len(needs_maintenance)} amenities needing maintenance in room {room_id}"
            )
            
            return needs_maintenance
            
        except Exception as e:
            logger.error(
                f"Error checking amenity maintenance for room {room_id}: {str(e)}"
            )
            raise BusinessLogicException("Failed to check amenity maintenance status")