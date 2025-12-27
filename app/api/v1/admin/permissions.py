from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.admin import (
    AdminPermissions,
    PermissionMatrix,
    RolePermissions,
    PermissionCheck,
)
from app.services.admin.admin_permission_service import AdminPermissionService

router = APIRouter(prefix="/permissions", tags=["admin:permissions"])


def get_permission_service(
    db: Session = Depends(deps.get_db),
) -> AdminPermissionService:
    return AdminPermissionService(db=db)


@router.get(
    "/admins/{admin_id}/hostels/{hostel_id}",
    response_model=AdminPermissions,
    summary="Get admin permissions for a hostel",
)
def get_admin_permissions(
    admin_id: str,
    hostel_id: str,
    _super_admin=Depends(deps.get_super_admin_user),
    service: AdminPermissionService = Depends(get_permission_service),
) -> Any:
    perms = service.get_admin_permissions(admin_id=admin_id, hostel_id=hostel_id)
    if not perms:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permissions not found")
    return perms


@router.put(
    "/admins/{admin_id}/hostels/{hostel_id}",
    response_model=AdminPermissions,
    summary="Update admin permissions for hostel",
)
def update_admin_permissions(
    admin_id: str,
    hostel_id: str,
    payload: AdminPermissions,
    _super_admin=Depends(deps.get_super_admin_user),
    service: AdminPermissionService = Depends(get_permission_service),
) -> Any:
    return service.update_admin_permissions(admin_id=admin_id, hostel_id=hostel_id, payload=payload)


@router.post(
    "/check",
    response_model=PermissionCheck,
    summary="Check if current admin has specific permission",
)
def check_permission(
    payload: PermissionCheck,
    current_admin=Depends(deps.get_admin_user),
    service: AdminPermissionService = Depends(get_permission_service),
) -> Any:
    """
    Wrapper to PermissionCheck logic; service fills `has_permission` and reasoning.
    """
    return service.check_permission(admin_id=current_admin.id, payload=payload)


@router.get(
    "/matrix",
    response_model=PermissionMatrix,
    summary="Get permission matrix for all roles",
)
def get_permission_matrix(
    _super_admin=Depends(deps.get_super_admin_user),
    service: AdminPermissionService = Depends(get_permission_service),
) -> Any:
    return service.get_permission_matrix()


@router.get(
    "/roles/{role_name}",
    response_model=RolePermissions,
    summary="Get permissions for specific role",
)
def get_role_permissions(
    role_name: str,
    _super_admin=Depends(deps.get_super_admin_user),
    service: AdminPermissionService = Depends(get_permission_service),
) -> Any:
    return service.get_role_permissions(role_name=role_name)


@router.put(
    "/roles/{role_name}",
    response_model=RolePermissions,
    summary="Update role permissions",
)
def update_role_permissions(
    role_name: str,
    payload: RolePermissions,
    _super_admin=Depends(deps.get_super_admin_user),
    service: AdminPermissionService = Depends(get_permission_service),
) -> Any:
    return service.update_role_permissions(role_name=role_name, payload=payload)