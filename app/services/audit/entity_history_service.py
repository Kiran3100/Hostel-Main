# app/services/audit/entity_history_service.py
from __future__ import annotations

from typing import Callable, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.audit import AuditLogRepository
from app.schemas.audit.audit_reports import (
    EntityChangeHistory,
    EntityChangeRecord,
)
from app.services.common import UnitOfWork
from app.repositories.core import UserRepository


class EntityHistoryService:
    """
    Thin wrapper around AuditLogRepository focused on per-entity history.

    - Get complete change history for one entity instance.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_audit_repo(self, uow: UnitOfWork) -> AuditLogRepository:
        return uow.get_repo(AuditLogRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def get_history(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
    ) -> EntityChangeHistory:
        with UnitOfWork(self._session_factory) as uow:
            audit_repo = self._get_audit_repo(uow)
            user_repo = self._get_user_repo(uow)

            logs = audit_repo.list_for_entity(
                entity_type=entity_type,
                entity_id=entity_id,
            )

            records: List[EntityChangeRecord] = []
            for l in logs:
                user_name = None
                if l.user_id:
                    u = user_repo.get(l.user_id)
                    user_name = u.full_name if u else None

                records.append(
                    EntityChangeRecord(
                        log_id=l.id,
                        action_type=l.action_type,
                        description=l.description,
                        old_values=l.old_values,
                        new_values=l.new_values,
                        changed_by=l.user_id,
                        changed_by_name=user_name,
                        changed_at=l.created_at,
                    )
                )

        records.sort(key=lambda r: r.changed_at)
        return EntityChangeHistory(
            entity_type=entity_type,
            entity_id=entity_id,
            changes=records,
        )