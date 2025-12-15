# api/v1/mess/duplicate.py
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.mess.menu_duplication import (
    DuplicateMenuRequest,
    DuplicateResponse,
    BulkMenuCreate,
    CrossHostelDuplication,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.mess import MessMenuPlanningService

router = APIRouter(prefix="/duplicate")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/",
    response_model=DuplicateResponse,
    summary="Duplicate a single mess menu",
)
async def duplicate_menu(
    payload: DuplicateMenuRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> DuplicateResponse:
    """
    Duplicate a single mess menu (e.g. copy a day's menu to another date).
    """
    service = MessMenuPlanningService(uow)
    try:
        return service.duplicate_menu(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/bulk",
    response_model=DuplicateResponse,
    summary="Bulk create menus across a date range",
)
async def bulk_create_menus(
    payload: BulkMenuCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> DuplicateResponse:
    """
    Bulk create menus over a date range from templates or existing weekly patterns.
    """
    service = MessMenuPlanningService(uow)
    try:
        return service.bulk_create_menus(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/cross-hostel",
    response_model=DuplicateResponse,
    summary="Duplicate menus across hostels",
)
async def cross_hostel_duplication(
    payload: CrossHostelDuplication,
    uow: UnitOfWork = Depends(get_uow),
) -> DuplicateResponse:
    """
    Duplicate menus from one hostel to others according to CrossHostelDuplication config.
    """
    service = MessMenuPlanningService(uow)
    try:
        return service.cross_hostel_duplicate(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)