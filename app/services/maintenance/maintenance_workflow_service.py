# app/services/maintenance/maintenance_workflow_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.workflows import MaintenanceWorkflowRepository
from app.services.common import UnitOfWork, errors


class MaintenanceWorkflowService:
    """
    Lightweight wrapper over wf_maintenance table.

    Tracks a single workflow row per maintenance with the current_status.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_repo(self, uow: UnitOfWork) -> MaintenanceWorkflowRepository:
        return uow.get_repo(MaintenanceWorkflowRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def ensure_workflow(self, maintenance_id: UUID, initial_status: str) -> None:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            wf = repo.get_by_maintenance_id(maintenance_id)
            if wf is None:
                payload = {
                    "maintenance_id": maintenance_id,
                    "current_status": initial_status,
                    "last_updated_at": self._now(),
                }
                repo.create(payload)  # type: ignore[arg-type]
                uow.commit()

    def set_status(self, maintenance_id: UUID, status: str) -> None:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            wf = repo.get_by_maintenance_id(maintenance_id)
            if wf is None:
                payload = {
                    "maintenance_id": maintenance_id,
                    "current_status": status,
                    "last_updated_at": self._now(),
                }
                repo.create(payload)  # type: ignore[arg-type]
            else:
                wf.current_status = status  # type: ignore[attr-defined]
                wf.last_updated_at = self._now()  # type: ignore[attr-defined]

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()