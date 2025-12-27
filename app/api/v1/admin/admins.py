from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.services.admin.admin_user_service import AdminUserService
from app.services.admin.admin_role_service import AdminRoleService
from app.schemas.user.user_response import UserDetail, UserListItem, UserStats

router = APIRouter(prefix="/admins", tags=["admin:admins"])


def get_admin_user_service(db: Session = Depends(deps.get_db)) -> AdminUserService:
    """
    Helper dependency to build an AdminUserService.

    Adjust the constructor wiring to match your real implementation
    (e.g. via a ServiceFactory or explicit repositories).
    """
    return AdminUserService(db=db)


def get_admin_role_service(db: Session = Depends(deps.get_db)) -> AdminRoleService:
    return AdminRoleService(db=db)


# ---- Admin users --------------------------------------------------------------


@router.get(
    "",
    response_model=List[UserListItem],
    summary="List admin users",
)
def list_admins(
    q: Optional[str] = Query(None, description="Search term (name/email/employee ID)"),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(deps.get_db),
    _super_admin=Depends(deps.get_super_admin_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> Any:
    """
    Search/filter admin users.

    Uses AdminUserService.search_admins() under the hood.
    """
    return service.search_admins(query=q, is_active=is_active, db=db)


@router.get(
    "/{admin_id}",
    response_model=UserDetail,
    summary="Get admin details",
)
def get_admin_detail(
    admin_id: str,
    db: Session = Depends(deps.get_db),
    _admin=Depends(deps.get_admin_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> Any:
    admin = service.get_admin_by_id(admin_id, db=db)
    if not admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")
    return admin


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create admin user",
)
def create_admin(
    payload: Dict[str, Any],  # TODO: replace with concrete AdminCreate schema
    db: Session = Depends(deps.get_db),
    _super_admin=Depends(deps.get_super_admin_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> Any:
    """
    Create a new admin user.

    This should map to AdminUserService.create_admin_user().
    Replace `Dict[str, Any]` with your concrete Pydantic schema (e.g. AdminCreate).
    """
    return service.create_admin_user(payload, db=db)


@router.patch(
    "/{admin_id}",
    summary="Update admin user",
)
def update_admin(
    admin_id: str,
    payload: Dict[str, Any],  # TODO: replace with AdminUpdate schema
    db: Session = Depends(deps.get_db),
    _super_admin=Depends(deps.get_super_admin_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> Any:
    return service.update_admin_user(admin_id, payload, db=db)


@router.post(
    "/{admin_id}/activate",
    status_code=status.HTTP_200_OK,
    summary="Activate admin account",
)
def activate_admin(
    admin_id: str,
    db: Session = Depends(deps.get_db),
    _super_admin=Depends(deps.get_super_admin_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> Any:
    return service.activate_admin(admin_id, db=db)


@router.post(
    "/{admin_id}/suspend",
    status_code=status.HTTP_200_OK,
    summary="Suspend admin account",
)
def suspend_admin(
    admin_id: str,
    reason: Optional[str] = Query(None),
    db: Session = Depends(deps.get_db),
    _super_admin=Depends(deps.get_super_admin_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> Any:
    return service.suspend_admin(admin_id, reason=reason, db=db)


# ---- Roles & hierarchy --------------------------------------------------------


@router.get(
    "/hierarchy",
    response_model=Dict[str, Any],
    summary="Get admin hierarchy tree",
)
def get_admin_hierarchy(
    db: Session = Depends(deps.get_db),
    _super_admin=Depends(deps.get_super_admin_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> Any:
    """
    Return organizational hierarchy for admins (reporting structure).
    """
    return service.get_admin_hierarchy(db=db)


@router.get(
    "/stats",
    response_model=UserStats,
    summary="Get admin user statistics",
)
def get_admin_stats(
    db: Session = Depends(deps.get_db),
    _super_admin=Depends(deps.get_super_admin_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> Any:
    """
    Reuse UserStats to expose high-level statistics for admins as users.
    """
    return service.get_admin_statistics(db=db)