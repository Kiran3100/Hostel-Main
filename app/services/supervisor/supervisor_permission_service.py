"""
Supervisor Permission Service

Manages supervisor permissions and permission checks.
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.supervisor import SupervisorPermissionsRepository
from app.schemas.supervisor import (
    SupervisorPermissions,
    PermissionUpdate,
    PermissionCheckRequest,
    PermissionCheckResponse,
)
from app.core.exceptions import ValidationException


class SupervisorPermissionService:
    """
    High-level service for supervisor permissions.

    Responsibilities:
    - Get/update supervisor permissions
    - Apply permission templates
    - Check if a supervisor has a given permission in a context
    """

    def __init__(
        self,
        permissions_repo: SupervisorPermissionsRepository,
    ) -> None:
        self.permissions_repo = permissions_repo

    # -------------------------------------------------------------------------
    # Get/Set
    # -------------------------------------------------------------------------

    def get_permissions(
        self,
        db: Session,
        supervisor_id: UUID,
    ) -> SupervisorPermissions:
        """
        Retrieve supervisor's permissions.
        """
        obj = self.permissions_repo.get_by_supervisor_id(db, supervisor_id)
        if not obj:
            raise ValidationException("Permissions not configured for supervisor")
        return SupervisorPermissions.model_validate(obj)

    def update_permissions(
        self,
        db: Session,
        supervisor_id: UUID,
        update: PermissionUpdate,
    ) -> SupervisorPermissions:
        """
        Partially update supervisor's permissions.
        """
        existing = self.permissions_repo.get_by_supervisor_id(db, supervisor_id)
        if not existing:
            raise ValidationException("Permissions not configured for supervisor")

        obj = self.permissions_repo.update_permissions(
            db=db,
            supervisor_id=supervisor_id,
            permission_data=update.permissions,
            reason=update.reason,
        )
        return SupervisorPermissions.model_validate(obj)

    # -------------------------------------------------------------------------
    # Templates
    # -------------------------------------------------------------------------

    def apply_permission_template(
        self,
        db: Session,
        supervisor_id: UUID,
        template_name: str,
        override_existing: bool = False,
    ) -> SupervisorPermissions:
        """
        Apply a named permission template to a single supervisor.
        """
        obj = self.permissions_repo.apply_template_to_supervisor(
            db=db,
            supervisor_id=supervisor_id,
            template_name=template_name,
            override_existing=override_existing,
        )
        return SupervisorPermissions.model_validate(obj)

    def bulk_apply_permission_template(
        self,
        db: Session,
        supervisor_ids: List[UUID],
        template_name: str,
        override_existing: bool = False,
    ) -> int:
        """
        Apply a named template to multiple supervisors.

        Returns the number of supervisors updated.
        """
        count = self.permissions_repo.bulk_apply_template(
            db=db,
            supervisor_ids=supervisor_ids,
            template_name=template_name,
            override_existing=override_existing,
        )
        return count

    # -------------------------------------------------------------------------
    # Permission checks
    # -------------------------------------------------------------------------

    def check_permission(
        self,
        db: Session,
        supervisor_id: UUID,
        request: PermissionCheckRequest,
    ) -> PermissionCheckResponse:
        """
        Check if a supervisor has a given permission in a context (amount, days, etc.).
        """
        has_permission, reason, threshold = self.permissions_repo.check_permission(
            db=db,
            supervisor_id=supervisor_id,
            permission_key=request.permission_key,
            context=request.context or {},
        )

        return PermissionCheckResponse(
            supervisor_id=supervisor_id,
            permission_key=request.permission_key,
            has_permission=has_permission,
            reason=reason,
            threshold=threshold,
        )