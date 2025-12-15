# app/repositories/workflows/approval_workflow_repository.py
from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.workflows import ApprovalWorkflow


class ApprovalWorkflowRepository(BaseRepository[ApprovalWorkflow]):
    def __init__(self, session: Session):
        super().__init__(session, ApprovalWorkflow)

    def get_for_entity(self, entity_type: str, entity_id: UUID) -> Optional[ApprovalWorkflow]:
        stmt = self._base_select().where(
            ApprovalWorkflow.entity_type == entity_type,
            ApprovalWorkflow.entity_id == entity_id,
        )
        return self.session.execute(stmt).scalar_one_or_none()