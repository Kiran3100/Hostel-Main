# app/services/admin/admin_override_service.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.audit import AdminOverrideRepository
from app.repositories.core import HostelRepository, SupervisorRepository, UserRepository
from app.schemas.admin import (
    AdminOverrideRequest,
    OverrideLog,
)
from app.schemas.audit import (
    AdminOverrideCreate,
    AdminOverrideLogResponse,
    AdminOverrideDetail,
)
from app.services.common import UnitOfWork, errors


class AdminOverrideService:
    """
    Record and read admin overrides of supervisor decisions.

    - Persist an override into audit_admin_override table
    - Provide admin-facing log entries
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_repo(self, uow: UnitOfWork) -> AdminOverrideRepository:
        return uow.get_repo(AdminOverrideRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_supervisor_repo(self, uow: UnitOfWork) -> SupervisorRepository:
        return uow.get_repo(SupervisorRepository)

    def _get_user_repo(self, uow: UnitOfWork) -> UserRepository:
        return uow.get_repo(UserRepository)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Create override
    # ------------------------------------------------------------------ #
    def record_override(
        self,
        *,
        admin_id: UUID,
        request: AdminOverrideRequest,
    ) -> OverrideLog:
        """
        Create an override record.

        NOTE:
        - This service only records metadata; caller is responsible for
          actually applying override effect to the target entity.
        """
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            supervisor_repo = self._get_supervisor_repo(uow)
            user_repo = self._get_user_repo(uow)

            hostel = hostel_repo.get(request.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {request.hostel_id} not found")

            sup_user_name: Optional[str] = None
            if request.supervisor_id:
                sup = supervisor_repo.get(request.supervisor_id)
                if sup and getattr(sup, "user", None):
                    sup_user_name = sup.user.full_name

            admin_user = user_repo.get(admin_id)
            admin_name = admin_user.full_name if admin_user else ""

            payload = AdminOverrideCreate(
                admin_id=admin_id,
                supervisor_id=request.supervisor_id,
                hostel_id=request.hostel_id,
                override_type=request.override_type,
                entity_type=request.entity_type,
                entity_id=request.entity_id,
                reason=request.reason,
                original_action=request.original_action,
                override_action=request.override_action,
            )
            record = repo.create(payload.model_dump())  # type: ignore[arg-type]
            uow.commit()

            return OverrideLog(
                id=record.id,
                created_at=record.created_at,
                updated_at=record.created_at,
                admin_id=admin_id,
                admin_name=admin_name,
                supervisor_id=request.supervisor_id,
                supervisor_name=sup_user_name,
                hostel_id=request.hostel_id,
                hostel_name=hostel.name,
                override_type=request.override_type,
                entity_type=request.entity_type,
                entity_id=request.entity_id,
                reason=request.reason,
                original_action=request.original_action,
                override_action=request.override_action,
            )

    # ------------------------------------------------------------------ #
    # Read logs
    # ------------------------------------------------------------------ #
    def list_overrides_for_entity(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
    ) -> List[AdminOverrideLogResponse]:
        """Low-level audit style listing for a specific entity."""
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            records = repo.list_for_entity(entity_type=entity_type, entity_id=entity_id)

            results: List[AdminOverrideLogResponse] = []
            for r in records:
                results.append(
                    AdminOverrideLogResponse(
                        id=r.id,
                        created_at=r.created_at,
                        updated_at=r.created_at,
                        admin_id=r.admin_id,
                        admin_name=None,
                        supervisor_id=r.supervisor_id,
                        supervisor_name=None,
                        hostel_id=r.hostel_id,
                        hostel_name=None,
                        override_type=r.override_type,
                        entity_type=r.entity_type,
                        entity_id=r.entity_id,
                        reason=r.reason,
                    )
                )
            return results

    def get_override_detail(self, override_id: UUID) -> AdminOverrideDetail:
        """Fetch a single override record with full details."""
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)
            supervisor_repo = self._get_supervisor_repo(uow)
            user_repo = self._get_user_repo(uow)

            r = repo.get(override_id)
            if r is None:
                raise errors.NotFoundError(f"AdminOverride {override_id} not found")

            admin_user = user_repo.get(r.admin_id)
            admin_name = admin_user.full_name if admin_user else None

            sup_user_name = None
            if r.supervisor_id:
                sup = supervisor_repo.get(r.supervisor_id)
                if sup and getattr(sup, "user", None):
                    sup_user_name = sup.user.full_name

            hostel = hostel_repo.get(r.hostel_id)

            return AdminOverrideDetail(
                id=r.id,
                created_at=r.created_at,
                updated_at=r.created_at,
                admin_id=r.admin_id,
                admin_name=admin_name,
                supervisor_id=r.supervisor_id,
                supervisor_name=sup_user_name,
                hostel_id=r.hostel_id,
                hostel_name=hostel.name if hostel else None,
                override_type=r.override_type,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                reason=r.reason,
                original_action=r.original_action,
                override_action=r.override_action,
            )