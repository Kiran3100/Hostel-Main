# app/repositories/workflows/complaint_workflow_repository.py
from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.workflows import ComplaintWorkflow


class ComplaintWorkflowRepository(BaseRepository[ComplaintWorkflow]):
    def __init__(self, session: Session):
        super().__init__(session, ComplaintWorkflow)

    def get_by_complaint_id(self, complaint_id: UUID) -> Optional[ComplaintWorkflow]:
        stmt = self._base_select().where(ComplaintWorkflow.complaint_id == complaint_id)
        return self.session.execute(stmt).scalar_one_or_none()