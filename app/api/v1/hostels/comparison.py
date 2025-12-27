from typing import Any, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.hostel.hostel_comparison import (
    HostelComparisonRequest,
    ComparisonResult,
    ComparisonSummary,
)
from app.services.hostel.hostel_comparison_service import HostelComparisonService

router = APIRouter(prefix="/hostels/comparison", tags=["hostels:comparison"])


def get_comparison_service(db: Session = Depends(deps.get_db)) -> HostelComparisonService:
    return HostelComparisonService(db=db)


@router.post(
    "",
    response_model=ComparisonResult,
    summary="Compare multiple hostels",
)
def compare_hostels(
    payload: HostelComparisonRequest,
    service: HostelComparisonService = Depends(get_comparison_service),
) -> Any:
    """
    Compare 2-4 hostels side by side.
    """
    return service.compare(payload.hostel_ids)


@router.get(
    "/pricing",
    summary="Compare pricing across hostels",
)
def compare_pricing(
    hostel_ids: List[str] = Query(..., min_items=2, max_items=4),
    service: HostelComparisonService = Depends(get_comparison_service),
) -> Any:
    return service.compare_pricing(hostel_ids)


@router.get(
    "/recommendations",
    summary="Get hostel recommendations",
)
def get_recommendations(
    # Criteria parameters (e.g. location, budget) could be query params or payload
    city: str = Query(...),
    service: HostelComparisonService = Depends(get_comparison_service),
) -> Any:
    return service.get_recommendations(city=city)