# api/v1/mess/menu.py
from __future__ import annotations

from datetime import date as Date

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.mess.mess_menu_base import MessMenuCreate, MessMenuUpdate
from app.schemas.mess.mess_menu_response import (
    MenuResponse,
    MenuDetail,
    WeeklyMenu,
    MonthlyMenu,
    TodayMenu,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.mess import MessMenuService

router = APIRouter(prefix="/menu")


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
    response_model=MenuDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a mess menu entry",
)
async def create_mess_menu(
    payload: MessMenuCreate,
    uow: UnitOfWork = Depends(get_uow),
) -> MenuDetail:
    """
    Create a daily mess menu for a hostel.
    """
    service = MessMenuService(uow)
    try:
        return service.create_menu(data=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{menu_id}",
    response_model=MenuDetail,
    summary="Get mess menu details",
)
async def get_mess_menu(
    menu_id: UUID = Path(..., description="Mess menu ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> MenuDetail:
    """
    Retrieve full details for a specific mess menu entry.
    """
    service = MessMenuService(uow)
    try:
        return service.get_menu(menu_id=menu_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.patch(
    "/{menu_id}",
    response_model=MenuDetail,
    summary="Update a mess menu",
)
async def update_mess_menu(
    menu_id: UUID = Path(..., description="Mess menu ID"),
    payload: MessMenuUpdate = ...,
    uow: UnitOfWork = Depends(get_uow),
) -> MenuDetail:
    """
    Partially update a mess menu (items, times, flags, etc.).
    """
    service = MessMenuService(uow)
    try:
        return service.update_menu(
            menu_id=menu_id,
            data=payload,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/hostels/{hostel_id}/today",
    response_model=TodayMenu,
    summary="Get today's mess menu for a hostel",
)
async def get_today_menu(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> TodayMenu:
    """
    Return today's mess menu for a hostel in a simplified format.
    """
    service = MessMenuService(uow)
    try:
        return service.get_today_menu(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/hostels/{hostel_id}/Date",
    response_model=MenuDetail,
    summary="Get mess menu for a specific Date",
)
async def get_menu_for_date(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    menu_date: Date = Query(..., description="Menu Date (YYYY-MM-DD)"),
    uow: UnitOfWork = Depends(get_uow),
) -> MenuDetail:
    """
    Get the mess menu for a hostel on a given Date.
    """
    service = MessMenuService(uow)
    try:
        return service.get_menu_for_date(
            hostel_id=hostel_id,
            menu_date=menu_date,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/hostels/{hostel_id}/week",
    response_model=WeeklyMenu,
    summary="Get weekly mess menu for a hostel",
)
async def get_weekly_menu(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    start_date: Date = Query(..., description="Week start Date (inclusive)"),
    end_date: Date = Query(..., description="Week end Date (inclusive)"),
    uow: UnitOfWork = Depends(get_uow),
) -> WeeklyMenu:
    """
    Return a weekly menu view for a hostel between the given dates.
    """
    service = MessMenuService(uow)
    try:
        return service.get_weekly_menu(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/hostels/{hostel_id}/month",
    response_model=MonthlyMenu,
    summary="Get monthly mess menu for a hostel",
)
async def get_monthly_menu(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    year: int = Query(..., ge=2000, description="Year (e.g. 2025)"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    uow: UnitOfWork = Depends(get_uow),
) -> MonthlyMenu:
    """
    Return a monthly menu calendar for a hostel.
    """
    service = MessMenuService(uow)
    try:
        return service.get_monthly_menu(
            hostel_id=hostel_id,
            year=year,
            month=month,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)