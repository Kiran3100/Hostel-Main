# app/api/v1/admin/permissions.py

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api.deps import get_uow
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.admin.admin_permissions import (
    PermissionMatrix,
    RolePermissions,
    PermissionCheck,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.admin import PermissionMatrixService

router = APIRouter(prefix="/permissions")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/matrix",
    response_model=PermissionMatrix,
    summary="Get global role→permissions matrix",
)
async def get_permission_matrix(
    uow: UnitOfWork = Depends(get_uow),
) -> PermissionMatrix:
    """
    Fetch the current role→permissions matrix.

    Backed by PermissionMatrixService.
    """
    service = PermissionMatrixService(uow)
    try:
        return service.get_matrix()
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.put(
    "/matrix",
    response_model=PermissionMatrix,
    summary="Update global role→permissions matrix",
)
async def update_permission_matrix(
    payload: PermissionMatrix,
    uow: UnitOfWork = Depends(get_uow),
) -> PermissionMatrix:
    """
    Replace the stored permission matrix.

    Should typically be restricted to super admins.
    """
    service = PermissionMatrixService(uow)
    try:
        return service.update_matrix(matrix=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/roles/{role_name}",
    response_model=RolePermissions,
    summary="Get permissions for a specific role",
)
async def get_role_permissions(
    role_name: str = Path(..., description="Role name (e.g. HOSTEL_ADMIN)"),
    uow: UnitOfWork = Depends(get_uow),
) -> RolePermissions:
    """
    Fetch the permissions assigned to a specific role.
    """
    service = PermissionMatrixService(uow)
    try:
        return service.get_role_permissions(role_name=role_name)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/check",
    response_model=PermissionCheck,
    summary="Check if a principal has a permission in a hostel",
)
async def check_permission(
    payload: PermissionCheck,
    uow: UnitOfWork = Depends(get_uow),
) -> PermissionCheck:
    """
    Check a single permission for a principal in the context of a hostel.

    Uses PermissionMatrixService.check_permission which bridges into RBACService.
    """
    service = PermissionMatrixService(uow)
    try:
        return service.check_permission(check=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)