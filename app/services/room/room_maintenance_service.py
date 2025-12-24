"""
Room Maintenance Service

Connects rooms/beds with the maintenance request/approval/completion flows.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceRequestRepository
from app.repositories.room import RoomRepository
from app.schemas.maintenance import MaintenanceRequest as MaintenanceRequestSchema
from app.core.exceptions import ValidationException


class RoomMaintenanceService:
    """
    High-level service that creates maintenance requests for rooms/beds.

    Responsibilities:
    - Create maintenance requests for rooms/beds
    - List maintenance requests by room
    """

    def __init__(
        self,
        maintenance_request_repo: MaintenanceRequestRepository,
        room_repo: RoomRepository,
    ) -> None:
        self.maintenance_request_repo = maintenance_request_repo
        self.room_repo = room_repo

    def create_maintenance_request_for_room(
        self,
        db: Session,
        room_id: UUID,
        requested_by: UUID,
        title: str,
        description: str,
        category: str,
        priority: str,
    ) -> MaintenanceRequestSchema:
        """
        Create a maintenance request for a specific room.
        """
        room = self.room_repo.get_by_id(db, room_id)
        if not room:
            raise ValidationException("Room not found")

        obj = self.maintenance_request_repo.create(
            db,
            data={
                "hostel_id": room.hostel_id,
                "room_id": room_id,
                "title": title,
                "description": description,
                "category": category,
                "priority": priority,
                "requested_by": requested_by,
            },
        )
        return MaintenanceRequestSchema.model_validate(obj)

    def list_maintenance_requests_for_room(
        self,
        db: Session,
        room_id: UUID,
    ) -> List[MaintenanceRequestSchema]:
        objs = self.maintenance_request_repo.get_by_room_id(db, room_id)
        return [MaintenanceRequestSchema.model_validate(o) for o in objs]