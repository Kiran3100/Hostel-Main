# app/api/v1/supervisors/permissions.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Any

from app.core import get_session
from app.services import UnitOfWork
from app.services.supervisor import SupervisorPermissionsService
from app.schemas.supervisor.supervisor_permissions import (
    SupervisorPermissions,
    PermissionUpdate,
    PermissionCheckRequest,
    PermissionCheckResponse,
    BulkPermissionUpdate,
    ApplyPermissionTemplate,
)
from . import CurrentUser, get_current_user, get_current_supervisor

router = APIRouter(tags=["Supervisors - Permissions"])


def _get_service(session: Session) -> SupervisorPermissionsService:
    uow = UnitOfWork(session)
    return SupervisorPermissionsService(uow)


@router.get("/me", response_model=SupervisorPermissions)
def get_my_permissions(
    current_user: CurrentUser = Depends(get_current_supervisor),
    session: Session = Depends(get_session),
) -> SupervisorPermissions:
    """
    Get permissions for the authenticated supervisor.

    Expected service method:
        get_permissions_for_user(user_id: UUID) -> SupervisorPermissions
    """
    service = _get_service(session)
    return service.get_permissions_for_user(user_id=current_user.id)


@router.get("/{supervisor_id}", response_model=SupervisorPermissions)
def get_permissions_for_supervisor(
    supervisor_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupervisorPermissions:
    """
    Get permissions for a specific supervisor.

    Expected service method:
        get_permissions(supervisor_id: UUID) -> SupervisorPermissions
    """
    service = _get_service(session)
    return service.get_permissions(supervisor_id=supervisor_id)


@router.patch("/{supervisor_id}", response_model=SupervisorPermissions)
def update_permission(
    supervisor_id: UUID,
    payload: PermissionUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupervisorPermissions:
    """
    Update a single permission for a supervisor.

    Expected service method:
        update_permission(supervisor_id: UUID, data: PermissionUpdate) -> SupervisorPermissions
    """
    service = _get_service(session)
    return service.update_permission(
        supervisor_id=supervisor_id,
        data=payload,
    )


@router.patch("/{supervisor_id}/bulk", response_model=SupervisorPermissions)
def bulk_update_permissions(
    supervisor_id: UUID,
    payload: BulkPermissionUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupervisorPermissions:
    """
    Bulk update multiple permissions for a supervisor.

    Expected service method:
        bulk_update_permissions(supervisor_id: UUID, data: BulkPermissionUpdate) -> SupervisorPermissions
    """
    service = _get_service(session)
    return service.bulk_update_permissions(
        supervisor_id=supervisor_id,
        data=payload,
    )


@router.post("/{supervisor_id}/template", response_model=SupervisorPermissions)
def apply_permission_template(
    supervisor_id: UUID,
    payload: ApplyPermissionTemplate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupervisorPermissions:
    """
    Apply a predefined permission template to a supervisor.

    Expected service method:
        apply_template(supervisor_id: UUID, data: ApplyPermissionTemplate) -> SupervisorPermissions
    """
    service = _get_service(session)
    return service.apply_template(
        supervisor_id=supervisor_id,
        data=payload,
    )


@router.post("/{supervisor_id}/check", response_model=PermissionCheckResponse)
def check_permission_for_supervisor(
    supervisor_id: UUID,
    payload: PermissionCheckRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> PermissionCheckResponse:
    """
    Check if a supervisor has a specific permission / within limits.

    Expected service method:
        check_permission(supervisor_id: UUID, data: PermissionCheckRequest) -> PermissionCheckResponse
    """
    service = _get_service(session)
    return service.check_permission(
        supervisor_id=supervisor_id,
        data=payload,
    )


@router.post("/me/check", response_model=PermissionCheckResponse)
def check_my_permission(
    payload: PermissionCheckRequest,
    current_user: CurrentUser = Depends(get_current_supervisor),
    session: Session = Depends(get_session),
) -> PermissionCheckResponse:
    """
    Check a permission for the authenticated supervisor.

    Convenience wrapper around the generic check endpoint.
    """
    service = _get_service(session)
    return service.check_permission_for_user(
        user_id=current_user.id,
        data=payload,
    )