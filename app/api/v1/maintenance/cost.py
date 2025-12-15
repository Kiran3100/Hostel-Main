from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import ServiceError, NotFoundError, ValidationError, ConflictError
from app.schemas.maintenance.maintenance_cost import (
    CostTracking,
    CategoryBudget,
    ExpenseReport,
    CostAnalysis,
)
from app.services.common.unit_of_work import UnitOfWork
from app.services.maintenance import MaintenanceCostService

router = APIRouter(prefix="/cost")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/{maintenance_id}/tracking",
    response_model=CostTracking,
    summary="Get cost tracking for a maintenance request",
)
async def get_cost_tracking(
    maintenance_id: UUID = Path(..., description="Maintenance request ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> CostTracking:
    """
    Return detailed cost tracking for a single maintenance request.
    """
    service = MaintenanceCostService(uow)
    try:
        return service.get_cost_tracking(maintenance_id=maintenance_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/hostels/{hostel_id}/budget",
    response_model=List[CategoryBudget],
    summary="Get maintenance budget allocation per category for a hostel",
)
async def get_hostel_budget(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> List[CategoryBudget]:
    """
    Get configured budget allocations per maintenance category for a hostel.
    """
    service = MaintenanceCostService(uow)
    try:
        return service.get_budget_allocations(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/hostels/{hostel_id}/expenses",
    response_model=ExpenseReport,
    summary="Get maintenance expense report for a hostel",
)
async def get_hostel_expense_report(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    year: int = Query(..., ge=2000, description="Year for the report"),
    month: int = Query(..., ge=1, le=12, description="Month for the report"),
    uow: UnitOfWork = Depends(get_uow),
) -> ExpenseReport:
    """
    Get an expense report for maintenance costs for a given hostel and month.
    """
    service = MaintenanceCostService(uow)
    try:
        return service.get_expense_report(
            hostel_id=hostel_id,
            year=year,
            month=month,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/hostels/{hostel_id}/analysis",
    response_model=CostAnalysis,
    summary="Get high-level cost analysis for a hostel",
)
async def get_hostel_cost_analysis(
    hostel_id: UUID = Path(..., description="Hostel ID"),
    uow: UnitOfWork = Depends(get_uow),
) -> CostAnalysis:
    """
    High-level cost analysis for maintenance at a hostel (trends, ratios, etc.).
    """
    service = MaintenanceCostService(uow)
    try:
        return service.get_cost_analysis(hostel_id=hostel_id)
    except ServiceError as exc:
        raise _map_service_error(exc)