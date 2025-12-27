from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.admin import (
    HostelContext,
    HostelSwitchRequest,
    ActiveHostelResponse,
    ContextHistory,
    HostelSelectorResponse,
    RecentHostels,
    FavoriteHostels,
    UpdateFavoriteRequest,
)
from app.services.admin.hostel_context_service import HostelContextService
from app.services.admin.hostel_selector_service import HostelSelectorService

router = APIRouter(prefix="/context", tags=["admin:context"])


def get_context_service(
    db: Session = Depends(deps.get_db),
) -> HostelContextService:
    return HostelContextService(db=db)


def get_selector_service(
    db: Session = Depends(deps.get_db),
) -> HostelSelectorService:
    return HostelSelectorService(db=db)


@router.get(
    "/active",
    response_model=HostelContext,
    summary="Get active hostel context",
)
def get_active_context(
    current_admin=Depends(deps.get_admin_user),
    service: HostelContextService = Depends(get_context_service),
) -> Any:
    return service.get_active_context(admin_id=current_admin.id)


@router.post(
    "/switch",
    response_model=ActiveHostelResponse,
    status_code=status.HTTP_200_OK,
    summary="Switch active hostel context",
)
def switch_hostel_context(
    payload: HostelSwitchRequest,
    current_admin=Depends(deps.get_admin_user),
    service: HostelContextService = Depends(get_context_service),
) -> Any:
    return service.switch_hostel(admin_id=current_admin.id, payload=payload)


@router.get(
    "/history",
    response_model=ContextHistory,
    summary="Get context switch history",
)
def get_context_history(
    current_admin=Depends(deps.get_admin_user),
    service: HostelContextService = Depends(get_context_service),
) -> Any:
    return service.get_context_history(admin_id=current_admin.id)


@router.get(
    "/selector",
    response_model=HostelSelectorResponse,
    summary="Get hostel selector data",
)
def get_hostel_selector(
    current_admin=Depends(deps.get_admin_user),
    service: HostelSelectorService = Depends(get_selector_service),
) -> Any:
    return service.get_selector(admin_id=current_admin.id)


@router.get(
    "/selector/recent",
    response_model=RecentHostels,
    summary="Get recent hostels for admin",
)
def get_recent_hostels(
    current_admin=Depends(deps.get_admin_user),
    service: HostelSelectorService = Depends(get_selector_service),
) -> Any:
    return service.get_recent_hostels(admin_id=current_admin.id)


@router.get(
    "/selector/favorites",
    response_model=FavoriteHostels,
    summary="Get favorite hostels for admin",
)
def get_favorite_hostels(
    current_admin=Depends(deps.get_admin_user),
    service: HostelSelectorService = Depends(get_selector_service),
) -> Any:
    return service.get_favorite_hostels(admin_id=current_admin.id)


@router.post(
    "/selector/favorites",
    response_model=FavoriteHostels,
    summary="Update favorites (add/remove)",
)
def update_favorite_hostels(
    payload: UpdateFavoriteRequest,
    current_admin=Depends(deps.get_admin_user),
    service: HostelSelectorService = Depends(get_selector_service),
) -> Any:
    return service.update_favorite(admin_id=current_admin.id, payload=payload)