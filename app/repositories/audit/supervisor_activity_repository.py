# app/repositories/audit/supervisor_activity_repository.py
from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.audit import SupervisorActivity


class SupervisorActivityRepository(BaseRepository[SupervisorActivity]):
    def __init__(self, session: Session):
        super().__init__(session, SupervisorActivity)

    def list_for_supervisor(
        self,
        supervisor_id: UUID,
        *,
        limit: int = 100,
    ) -> List[SupervisorActivity]:
        stmt = (
            self._base_select()
            .where(SupervisorActivity.supervisor_id == supervisor_id)
            .order_by(SupervisorActivity.created_at.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()