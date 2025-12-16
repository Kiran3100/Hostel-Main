# app/repositories/audit/audit_log_repository.py
from datetime import datetime
from typing import List, Union
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.repositories.base import BaseRepository
from app.models.audit import AuditLog
from app.schemas.common.enums import AuditActionCategory, UserRole


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, session: Session):
        super().__init__(session, AuditLog)

    def list_for_entity(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        limit: int = 100,
    ) -> List[AuditLog]:
        stmt = (
            self._base_select()
            .where(
                and_(
                    AuditLog.entity_type == entity_type,
                    AuditLog.entity_id == entity_id,
                )
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def list_for_user(
        self,
        *,
        user_id: UUID,
        user_role: Union[UserRole, None] = None,
        limit: int = 100,
    ) -> List[AuditLog]:
        stmt = self._base_select().where(AuditLog.user_id == user_id)
        if user_role is not None:
            stmt = stmt.where(AuditLog.user_role == user_role)
        stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)
        return self.session.execute(stmt).scalars().all()

    def list_for_hostel(
        self,
        *,
        hostel_id: UUID,
        category: Union[AuditActionCategory, None] = None,
        limit: int = 200,
    ) -> List[AuditLog]:
        stmt = self._base_select().where(AuditLog.hostel_id == hostel_id)
        if category is not None:
            stmt = stmt.where(AuditLog.action_category == category)
        stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit)
        return self.session.execute(stmt).scalars().all()