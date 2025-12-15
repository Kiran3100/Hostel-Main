# app/repositories/associations/supervisor_hostel_repository.py
from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.associations import SupervisorHostel
from app.models.core import Supervisor, Hostel


class SupervisorHostelRepository(BaseRepository[SupervisorHostel]):
    def __init__(self, session: Session):
        super().__init__(session, SupervisorHostel)

    def get_hostels_for_supervisor(self, supervisor_id: UUID) -> List[Hostel]:
        stmt = (
            select(Hostel)
            .join(SupervisorHostel, SupervisorHostel.hostel_id == Hostel.id)
            .where(
                SupervisorHostel.supervisor_id == supervisor_id,
                SupervisorHostel.is_active.is_(True),
            )
        )
        return self.session.execute(stmt).scalars().all()

    def get_supervisors_for_hostel(self, hostel_id: UUID) -> List[Supervisor]:
        stmt = (
            select(Supervisor)
            .join(SupervisorHostel, SupervisorHostel.supervisor_id == Supervisor.id)
            .where(
                SupervisorHostel.hostel_id == hostel_id,
                SupervisorHostel.is_active.is_(True),
            )
        )
        return self.session.execute(stmt).scalars().all()