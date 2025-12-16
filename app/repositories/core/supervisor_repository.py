# app/repositories/core/supervisor_repository.py
from typing import List, Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.core import Supervisor
from app.schemas.common.enums import SupervisorStatus


class SupervisorRepository(BaseRepository[Supervisor]):
    def __init__(self, session: Session):
        super().__init__(session, Supervisor)

    def list_for_hostel(
        self,
        hostel_id: UUID,
        *,
        status: Union[SupervisorStatus, None] = None,
    ) -> List[Supervisor]:
        stmt = self._base_select().where(Supervisor.hostel_id == hostel_id)
        if status is not None:
            stmt = stmt.where(Supervisor.status == status)
        return self.session.execute(stmt).scalars().all()