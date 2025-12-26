"""
Room Maintenance Service

Connects rooms/beds with the maintenance request/approval/completion flows.

Enhancements:
- Added priority-based maintenance scheduling
- Improved tracking and reporting
- Enhanced error handling
- Support for maintenance history
- Better logging and audit trail
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.maintenance import MaintenanceRequestRepository
from app.repositories.room import RoomRepository, BedRepository
from app.schemas.maintenance import (
    MaintenanceRequest as MaintenanceRequestSchema,
    MaintenanceRequestCreate,
)
from app.core.exceptions import ValidationException, BusinessLogicException

logger = logging.getLogger(__name__)


class RoomMaintenanceService:
    """
    High-level service for room/bed maintenance requests.

    Responsibilities:
    - Create and manage maintenance requests for rooms/beds
    - Track maintenance status and history
    - Generate maintenance reports
    - Prioritize and schedule maintenance
    
    Performance optimizations:
    - Batch operations support
    - Efficient query patterns
    - Transaction management
    """

    __slots__ = ('maintenance_request_repo', 'room_repo', 'bed_repo')

    def __init__(
        self,
        maintenance_request_repo: MaintenanceRequestRepository,
        room_repo: RoomRepository,
        bed_repo: Optional[BedRepository] = None,
    ) -> None:
        """
        Initialize the service with required repositories.

        Args:
            maintenance_request_repo: Repository for maintenance requests
            room_repo: Repository for room operations
            bed_repo: Optional repository for bed operations
        """
        self.maintenance_request_repo = maintenance_request_repo
        self.room_repo = room_repo
        self.bed_repo = bed_repo

    def create_maintenance_request_for_room(
        self,
        db: Session,
        room_id: UUID,
        requested_by: UUID,
        title: str,
        description: str,
        category: str,
        priority: str,
        scheduled_date: Optional[date] = None,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> MaintenanceRequestSchema:
        """
        Create a maintenance request for a specific room.

        Args:
            db: Database session
            room_id: UUID of the room
            requested_by: UUID of the user creating the request
            title: Request title
            description: Detailed description
            category: Maintenance category
            priority: Priority level
            scheduled_date: Optional scheduled date
            additional_data: Optional additional data

        Returns:
            MaintenanceRequestSchema: Created maintenance request

        Raises:
            ValidationException: If room not found
            BusinessLogicException: If creation fails
        """
        try:
            # Validate room exists
            room = self.room_repo.get_by_id(db, room_id)
            if not room:
                raise ValidationException(f"Room {room_id} not found")
            
            # Build request data
            request_data = {
                "hostel_id": room.hostel_id,
                "room_id": room_id,
                "title": title,
                "description": description,
                "category": category,
                "priority": priority,
                "requested_by": requested_by,
            }
            
            if scheduled_date:
                request_data["scheduled_date"] = scheduled_date
            
            if additional_data:
                request_data.update(additional_data)
            
            # Create maintenance request
            obj = self.maintenance_request_repo.create(db, data=request_data)
            db.commit()
            
            logger.info(
                f"Created maintenance request {obj.id} for room {room_id} "
                f"with priority {priority}"
            )
            
            return MaintenanceRequestSchema.model_validate(obj)
            
        except ValidationException:
            db.rollback()
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error creating maintenance request: {str(e)}")
            raise BusinessLogicException(
                "Failed to create maintenance request due to database error"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error creating maintenance request: {str(e)}")
            raise BusinessLogicException("Failed to create maintenance request")

    def create_maintenance_request_for_bed(
        self,
        db: Session,
        bed_id: UUID,
        requested_by: UUID,
        title: str,
        description: str,
        category: str,
        priority: str,
        scheduled_date: Optional[date] = None,
    ) -> MaintenanceRequestSchema:
        """
        Create a maintenance request for a specific bed.

        Args:
            db: Database session
            bed_id: UUID of the bed
            requested_by: UUID of the user creating the request
            title: Request title
            description: Detailed description
            category: Maintenance category
            priority: Priority level
            scheduled_date: Optional scheduled date

        Returns:
            MaintenanceRequestSchema: Created maintenance request

        Raises:
            ValidationException: If bed not found or bed_repo not available
            BusinessLogicException: If creation fails
        """
        try:
            if not self.bed_repo:
                raise ValidationException("Bed repository not available")
            
            # Validate bed exists
            bed = self.bed_repo.get_by_id(db, bed_id)
            if not bed:
                raise ValidationException(f"Bed {bed_id} not found")
            
            # Get room to get hostel_id
            room = self.room_repo.get_by_id(db, bed.room_id)
            if not room:
                raise ValidationException(f"Room {bed.room_id} not found")
            
            # Build request data
            request_data = {
                "hostel_id": room.hostel_id,
                "room_id": bed.room_id,
                "bed_id": bed_id,
                "title": title,
                "description": description,
                "category": category,
                "priority": priority,
                "requested_by": requested_by,
            }
            
            if scheduled_date:
                request_data["scheduled_date"] = scheduled_date
            
            # Create maintenance request
            obj = self.maintenance_request_repo.create(db, data=request_data)
            db.commit()
            
            logger.info(
                f"Created maintenance request {obj.id} for bed {bed_id} "
                f"with priority {priority}"
            )
            
            return MaintenanceRequestSchema.model_validate(obj)
            
        except ValidationException:
            db.rollback()
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error creating bed maintenance request: {str(e)}")
            raise BusinessLogicException(
                "Failed to create bed maintenance request due to database error"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error creating bed maintenance request: {str(e)}")
            raise BusinessLogicException("Failed to create bed maintenance request")

    def list_maintenance_requests_for_room(
        self,
        db: Session,
        room_id: UUID,
        status_filter: Optional[str] = None,
        priority_filter: Optional[str] = None,
    ) -> List[MaintenanceRequestSchema]:
        """
        List maintenance requests for a room with optional filtering.

        Args:
            db: Database session
            room_id: UUID of the room
            status_filter: Optional status filter
            priority_filter: Optional priority filter

        Returns:
            List[MaintenanceRequestSchema]: List of maintenance requests
        """
        try:
            objs = self.maintenance_request_repo.get_by_room_id(db, room_id)
            
            # Apply filters
            if status_filter:
                objs = [obj for obj in objs if obj.status == status_filter]
            
            if priority_filter:
                objs = [obj for obj in objs if obj.priority == priority_filter]
            
            logger.debug(
                f"Retrieved {len(objs)} maintenance requests for room {room_id}"
            )
            
            return [MaintenanceRequestSchema.model_validate(o) for o in objs]
            
        except Exception as e:
            logger.error(
                f"Error listing maintenance requests for room {room_id}: {str(e)}"
            )
            raise BusinessLogicException("Failed to list maintenance requests")

    def list_maintenance_requests_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        status_filter: Optional[str] = None,
        priority_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[MaintenanceRequestSchema]:
        """
        List maintenance requests for a hostel with filtering and pagination.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            status_filter: Optional status filter
            priority_filter: Optional priority filter
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List[MaintenanceRequestSchema]: List of maintenance requests
        """
        try:
            objs = self.maintenance_request_repo.get_by_hostel_id(
                db, hostel_id, skip=skip, limit=limit
            )
            
            # Apply filters
            if status_filter:
                objs = [obj for obj in objs if obj.status == status_filter]
            
            if priority_filter:
                objs = [obj for obj in objs if obj.priority == priority_filter]
            
            logger.debug(
                f"Retrieved {len(objs)} maintenance requests for hostel {hostel_id}"
            )
            
            return [MaintenanceRequestSchema.model_validate(o) for o in objs]
            
        except Exception as e:
            logger.error(
                f"Error listing maintenance requests for hostel {hostel_id}: {str(e)}"
            )
            raise BusinessLogicException("Failed to list hostel maintenance requests")

    def get_maintenance_summary_for_room(
        self,
        db: Session,
        room_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get maintenance summary statistics for a room.

        Args:
            db: Database session
            room_id: UUID of the room

        Returns:
            Dict containing summary statistics
        """
        try:
            requests = self.maintenance_request_repo.get_by_room_id(db, room_id)
            
            summary = {
                "room_id": room_id,
                "total_requests": len(requests),
                "by_status": {},
                "by_priority": {},
                "by_category": {},
                "pending_count": 0,
                "in_progress_count": 0,
                "completed_count": 0,
            }
            
            for request in requests:
                # Count by status
                status = request.status or "unknown"
                summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
                
                # Count by priority
                priority = request.priority or "unknown"
                summary["by_priority"][priority] = summary["by_priority"].get(priority, 0) + 1
                
                # Count by category
                category = request.category or "unknown"
                summary["by_category"][category] = summary["by_category"].get(category, 0) + 1
                
                # Special counts
                if status == "pending":
                    summary["pending_count"] += 1
                elif status == "in_progress":
                    summary["in_progress_count"] += 1
                elif status == "completed":
                    summary["completed_count"] += 1
            
            return summary
            
        except Exception as e:
            logger.error(
                f"Error generating maintenance summary for room {room_id}: {str(e)}"
            )
            raise BusinessLogicException("Failed to generate maintenance summary")

    def get_high_priority_maintenance_requests(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> List[MaintenanceRequestSchema]:
        """
        Get all high-priority open maintenance requests for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of the hostel

        Returns:
            List[MaintenanceRequestSchema]: High-priority requests
        """
        try:
            # Get all requests for hostel
            all_requests = self.maintenance_request_repo.get_by_hostel_id(
                db, hostel_id
            )
            
            # Filter for high priority and open status
            high_priority = [
                req for req in all_requests
                if req.priority in {"high", "urgent", "critical"}
                and req.status in {"pending", "in_progress", "approved"}
            ]
            
            # Sort by priority (urgent > high > critical)
            priority_order = {"urgent": 0, "critical": 1, "high": 2}
            high_priority.sort(
                key=lambda x: priority_order.get(x.priority, 99)
            )
            
            logger.info(
                f"Found {len(high_priority)} high-priority maintenance requests "
                f"for hostel {hostel_id}"
            )
            
            return [MaintenanceRequestSchema.model_validate(r) for r in high_priority]
            
        except Exception as e:
            logger.error(
                f"Error getting high-priority maintenance requests: {str(e)}"
            )
            raise BusinessLogicException(
                "Failed to get high-priority maintenance requests"
            )

    def create_bulk_maintenance_requests(
        self,
        db: Session,
        requests_data: List[Dict[str, Any]],
    ) -> List[MaintenanceRequestSchema]:
        """
        Create multiple maintenance requests in a single transaction.

        Args:
            db: Database session
            requests_data: List of request data dictionaries

        Returns:
            List[MaintenanceRequestSchema]: Created maintenance requests

        Raises:
            BusinessLogicException: If bulk creation fails
        """
        try:
            created_requests = []
            
            for request_data in requests_data:
                # Validate room exists
                room_id = request_data.get("room_id")
                if room_id:
                    room = self.room_repo.get_by_id(db, room_id)
                    if not room:
                        raise ValidationException(f"Room {room_id} not found")
                    
                    # Ensure hostel_id is set
                    if "hostel_id" not in request_data:
                        request_data["hostel_id"] = room.hostel_id
                
                obj = self.maintenance_request_repo.create(db, data=request_data)
                created_requests.append(obj)
            
            db.commit()
            
            logger.info(f"Created {len(created_requests)} maintenance requests in bulk")
            
            return [
                MaintenanceRequestSchema.model_validate(r) for r in created_requests
            ]
            
        except ValidationException:
            db.rollback()
            raise
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error in bulk maintenance request creation: {str(e)}")
            raise BusinessLogicException(
                "Failed to create maintenance requests in bulk"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error in bulk maintenance request creation: {str(e)}")
            raise BusinessLogicException(
                "Failed to create maintenance requests in bulk"
            )