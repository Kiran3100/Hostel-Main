from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.fee_structure import (
    FeeCalculation,
    FeeProjection,
    FeeQuoteRequest,  # Assuming a request schema for quote calculation
)
from app.services.fee_structure.fee_calculation_service import FeeCalculationService
from app.services.fee_structure.fee_projection_service import FeeProjectionService

router = APIRouter(prefix="/fee-structures/calculate", tags=["fee-structures:calculate"])


def get_calculation_service(db: Session = Depends(deps.get_db)) -> FeeCalculationService:
    return FeeCalculationService(db=db)


def get_projection_service(db: Session = Depends(deps.get_db)) -> FeeProjectionService:
    return FeeProjectionService(db=db)


@router.post(
    "/quote",
    response_model=FeeCalculation,
    summary="Calculate fee quote (without saving)",
)
def calculate_quote(
    payload: FeeQuoteRequest,
    # This might be public or require authentication depending on use case
    service: FeeCalculationService = Depends(get_calculation_service),
) -> Any:
    """
    Calculate fees based on room type, dates, and optional discount code.
    """
    return service.calculate_quote(payload)


@router.get(
    "/booking/{booking_id}",
    response_model=FeeCalculation,
    summary="Get fee calculation for a booking",
)
def get_booking_fees(
    booking_id: str,
    current_user=Depends(deps.get_current_user),
    service: FeeCalculationService = Depends(get_calculation_service),
) -> Any:
    return service.get_calculations_for_booking(booking_id)


@router.get(
    "/projections",
    response_model=FeeProjection,
    summary="Get revenue projections",
)
def get_fee_projections(
    hostel_id: str = Query(...),
    months: int = Query(12, ge=1, le=60),
    _admin=Depends(deps.get_admin_user),
    service: FeeProjectionService = Depends(get_projection_service),
) -> Any:
    return service.project_for_hostel(hostel_id=hostel_id, months=months)