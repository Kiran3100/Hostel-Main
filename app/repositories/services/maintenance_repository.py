# app/repositories/services/maintenance_repository.py
from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.services import Maintenance
from app.schemas.common.enums import MaintenanceStatus, MaintenanceCategory, Priority


class MaintenanceRepository(BaseRepository[Maintenance]):
    def __init__(self, session: Session):
        super().__init__(session, Maintenance)

    def list_open_for_hostel(
        self,
        hostel_id: UUID,
        *,
        category: Optional[MaintenanceCategory] = None,
        priority: Optional[Priority] = None,
    ) -> List[Maintenance]:
        stmt = self._base_select().where(
            Maintenance.hostel_id == hostel_id,
            Maintenance.status.in_(
                [
                    MaintenanceStatus.OPEN,
                    MaintenanceStatus.IN_PROGRESS,
                    MaintenanceStatus.PENDING_APPROVAL,
                ]
            ),
        )
        if category is not None:
            stmt = stmt.where(Maintenance.category == category)
        if priority is not None:
            stmt = stmt.where(Maintenance.priority == priority)
        return self.session.execute(stmt).scalars().all()

    def list_for_room(self, room_id: UUID) -> List[Maintenance]:
        stmt = (
            self._base_select()
            .where(Maintenance.room_id == room_id)
            .order_by(Maintenance.created_at.desc())
        )
        return self.session.execute(stmt).scalars().all()