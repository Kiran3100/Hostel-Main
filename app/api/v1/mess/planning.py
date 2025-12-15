# api/v1/mess/planning.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.mess.menu_planning import (
    MenuPlanRequest,
    WeeklyPlan,
    MonthlyPlan,
    MenuTemplate,
    MenuSuggestion,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.mess import MessMenuPlanningService

router = APIRouter(prefix="/planning")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/plan",
    response_model=WeeklyPlan | MonthlyPlan,
    summary="Generate a mess menu plan",
)
async def generate_menu_plan(
    payload: MenuPlanRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> WeeklyPlan | MonthlyPlan:
    """
    Generate a weekly or monthly mess menu plan based on the provided request,
    templates, and patterns.
    """
    service = MessMenuPlanningService(uow)
    try:
        return service.generate_plan(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/templates",
    response_model=list[MenuTemplate],
    summary="List saved menu templates",
)
async def list_menu_templates(
    uow: UnitOfWork = Depends(get_uow),
) -> list[MenuTemplate]:
    """
    List available mess menu templates that can be used for planning/duplication.
    """
    service = MessMenuPlanningService(uow)
    try:
        return service.list_templates()
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/suggestions",
    response_model=list[MenuSuggestion],
    summary="Get menu suggestions",
)
async def get_menu_suggestions(
    uow: UnitOfWork = Depends(get_uow),
) -> list[MenuSuggestion]:
    """
    Get suggested menu combinations or special menus (e.g. for special days).
    """
    service = MessMenuPlanningService(uow)
    try:
        return service.get_suggestions()
    except ServiceError as exc:
        raise _map_service_error(exc)