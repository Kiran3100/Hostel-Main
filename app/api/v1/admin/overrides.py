from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.admin import (
    AdminOverrideRequest,
    OverrideLog,
    OverrideReason,
    OverrideSummary,
    SupervisorOverrideStats,
)
from app.services.admin.admin_override_service import AdminOverrideService

router = APIRouter(prefix="/overrides", tags=["admin:overrides"])


def get_override_service(
    db: Session = Depends(deps.get_db),
) -> AdminOverrideService:
    return AdminOverrideService(db=db)


@router.post(
    "",
    response_model=OverrideLog,
    status_code=status.HTTP_201_CREATED,
    summary="Create admin override",
)
def create_override(
    payload: AdminOverrideRequest,
    _admin=Depends(deps.get_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> Any:
    return service.create_override(payload)


@router.get(
    "/{override_id}",
    response_model=OverrideLog,
    summary="Get override details",
)
def get_override_detail(
    override_id: str,
    _admin=Depends(deps.get_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> Any:
    override = service.get_override_by_id(override_id)
    if not override:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Override not found")
    return override


@router.post(
    "/{override_id}/approve",
    response_model=OverrideLog,
    summary="Approve override",
)
def approve_override(
    override_id: str,
    _super_admin=Depends(deps.get_super_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> Any:
    return service.approve_override(override_id)


@router.post(
    "/{override_id}/reject",
    response_model=OverrideLog,
    summary="Reject override",
)
def reject_override(
    override_id: str,
    reason: str = Query(..., min_length=5),
    _super_admin=Depends(deps.get_super_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> Any:
    return service.reject_override(override_id, reason=reason)


@router.get(
    "/pending",
    response_model=List[OverrideLog],
    summary="List pending overrides",
)
def list_pending_overrides(
    _super_admin=Depends(deps.get_super_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> Any:
    return service.get_pending_overrides()


@router.get(
    "/summary",
    response_model=OverrideSummary,
    summary="Get override summary for period",
)
def get_override_summary(
    hostel_id: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    _admin=Depends(deps.get_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> Any:
    return service.get_override_summary(hostel_id=hostel_id, days=days)


@router.get(
    "/supervisors/{supervisor_id}/stats",
    response_model=SupervisorOverrideStats,
    summary="Get supervisor override statistics",
)
def get_supervisor_override_stats(
    supervisor_id: str,
    _admin=Depends(deps.get_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> Any:
    return service.get_supervisor_override_stats(supervisor_id=supervisor_id)


@router.get(
    "/reasons",
    response_model=List[OverrideReason],
    summary="List standard override reasons",
)
def list_override_reasons(
    _admin=Depends(deps.get_admin_user),
    service: AdminOverrideService = Depends(get_override_service),
) -> Any:
    return service.get_standard_reasons()