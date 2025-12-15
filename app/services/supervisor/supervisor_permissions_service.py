# app/services/supervisor/supervisor_permissions_service.py
from __future__ import annotations

from decimal import Decimal
from typing import Callable, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import SupervisorRepository
from app.schemas.supervisor import (
    SupervisorPermissions,
    PermissionUpdate,
    PermissionCheckRequest,
    PermissionCheckResponse,
)
from app.services.common import UnitOfWork, errors


class SupervisorPermissionsService:
    """
    Supervisor permission management:

    - Get/set permissions (stored on core_supervisor.permissions JSON)
    - Evaluate a simple permission check, including threshold-based checks
      (e.g., maintenance_approval_threshold).
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_supervisor_repo(self, uow: UnitOfWork) -> SupervisorRepository:
        return uow.get_repo(SupervisorRepository)

    # Internal helpers
    def _load_permissions(self, sup) -> SupervisorPermissions:
        """
        Merge stored JSON permissions onto SupervisorPermissions defaults.
        """
        stored = sup.permissions or {}
        base = SupervisorPermissions()
        data = base.model_dump()
        data.update(stored)
        return SupervisorPermissions.model_validate(data)

    # Public API
    def get_permissions(self, supervisor_id: UUID) -> SupervisorPermissions:
        with UnitOfWork(self._session_factory) as uow:
            sup_repo = self._get_supervisor_repo(uow)
            sup = sup_repo.get(supervisor_id)
            if sup is None:
                raise errors.NotFoundError(f"Supervisor {supervisor_id} not found")
            return self._load_permissions(sup)

    def update_permissions(
        self,
        supervisor_id: UUID,
        data: PermissionUpdate,
    ) -> SupervisorPermissions:
        with UnitOfWork(self._session_factory) as uow:
            sup_repo = self._get_supervisor_repo(uow)
            sup = sup_repo.get(supervisor_id)
            if sup is None:
                raise errors.NotFoundError(f"Supervisor {supervisor_id} not found")

            current = sup.permissions or {}
            current.update(data.permissions)
            sup.permissions = current  # type: ignore[attr-defined]
            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

            return self._load_permissions(sup)

    def check_permission(self, req: PermissionCheckRequest) -> PermissionCheckResponse:
        perms = self.get_permissions(req.supervisor_id)
        data = perms.model_dump()

        key = req.permission_key
        ctx = req.context or {}
        has_perm = False
        requires_approval = False
        threshold_exceeded = False
        threshold_value: Decimal | None = None
        actual_value: Decimal | None = None
        message = ""

        if key not in data and key != "maintenance_approval_threshold":
            return PermissionCheckResponse(
                supervisor_id=req.supervisor_id,
                permission_key=key,
                has_permission=False,
                requires_approval=False,
                threshold_exceeded=False,
                message="Unknown permission key",
                threshold_value=None,
                actual_value=None,
            )

        if key == "maintenance_approval_threshold":
            # Threshold-based check
            threshold_value = Decimal(str(data.get("maintenance_approval_threshold", "0")))
            amount = ctx.get("amount")
            if amount is not None:
                actual_value = Decimal(str(amount))
                threshold_exceeded = actual_value > threshold_value
                has_perm = True
                requires_approval = threshold_exceeded
                message = (
                    "Amount exceeds supervisor approval threshold; admin approval required."
                    if threshold_exceeded
                    else "Within supervisor approval threshold."
                )
            else:
                has_perm = True
                message = "Threshold value retrieved."
        else:
            val = data.get(key)
            if isinstance(val, bool):
                has_perm = val
                message = "Permission granted." if val else "Permission denied."
            else:
                has_perm = bool(val)

        return PermissionCheckResponse(
            supervisor_id=req.supervisor_id,
            permission_key=key,
            has_permission=has_perm,
            requires_approval=requires_approval,
            threshold_exceeded=threshold_exceeded,
            message=message,
            threshold_value=threshold_value,
            actual_value=actual_value,
        )