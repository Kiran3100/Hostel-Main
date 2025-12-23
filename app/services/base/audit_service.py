"""
Audit logging service.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.services.base.base_service import BaseService
from app.services.base.service_result import ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.audit.audit_log_repository import AuditLogRepository
from app.models.audit.audit_log import AuditLog


class AuditService(BaseService[AuditLog, AuditLogRepository]):
    """
    Convenience wrapper around AuditLogRepository with service-level helpers.
    """

    def __init__(self, repository: AuditLogRepository, db_session: Session):
        super().__init__(repository, db_session)

    def log_action(
        self,
        actor_user_id: UUID,
        action: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        category: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        status: str = "success",
    ) -> ServiceResult[AuditLog]:
        try:
            record = self.repository.create({
                "actor_user_id": actor_user_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "category": category,
                "context": context or {},
                "status": status,
                "timestamp": datetime.utcnow(),
            })
            self.db.commit()
            return ServiceResult.success(record, message="Audit logged")
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "log audit", entity_id or actor_user_id)

    def log_change(
        self,
        actor_user_id: UUID,
        entity_type: str,
        entity_id: str,
        changes: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[AuditLog]:
        try:
            record = self.repository.create({
                "actor_user_id": actor_user_id,
                "action": "update",
                "entity_type": entity_type,
                "entity_id": entity_id,
                "category": "change",
                "context": {
                    "changes": changes,
                    **(context or {}),
                },
                "status": "success",
                "timestamp": datetime.utcnow(),
            })
            self.db.commit()
            return ServiceResult.success(record, message="Change logged")
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "log change", entity_id)

    def get_actor_activity(
        self,
        actor_user_id: UUID,
        days: int = 7,
        limit: int = 100,
    ) -> ServiceResult[List[AuditLog]]:
        try:
            since = datetime.utcnow() - timedelta(days=days)
            items = self.repository.get_user_activity(actor_user_id, since, limit=limit)
            return ServiceResult.success(items, metadata={"count": len(items)})
        except Exception as e:
            return self._handle_exception(e, "get actor activity", actor_user_id)

    def get_entity_history(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 100,
    ) -> ServiceResult[List[AuditLog]]:
        try:
            items = self.repository.get_entity_history(entity_type, entity_id, limit=limit)
            return ServiceResult.success(items, metadata={"count": len(items)})
        except Exception as e:
            return self._handle_exception(e, "get entity history", entity_id)