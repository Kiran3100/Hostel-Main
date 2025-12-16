# app/repositories/workflows/maintenance_workflow_repository.py
from typing import Union
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.workflows import MaintenanceWorkflow


class MaintenanceWorkflowRepository(BaseRepository[MaintenanceWorkflow]):
    def __init__(self, session: Session):
        super().__init__(session, MaintenanceWorkflow)

    def get_by_maintenance_id(self, maintenance_id: UUID) -> Union[MaintenanceWorkflow, None]:
        stmt = self._base_select().where(MaintenanceWorkflow.maintenance_id == maintenance_id)
        return self.session.execute(stmt).scalar_one_or_none()