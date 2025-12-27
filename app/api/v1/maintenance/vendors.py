from typing import Any, List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.maintenance.maintenance_vendor import (
    MaintenanceVendor,
    VendorPerformanceReview,
)
from app.services.maintenance.maintenance_vendor_service import MaintenanceVendorService

router = APIRouter(prefix="/vendors", tags=["maintenance:vendors"])


def get_vendor_service(db: Session = Depends(deps.get_db)) -> MaintenanceVendorService:
    return MaintenanceVendorService(db=db)


@router.post(
    "",
    response_model=MaintenanceVendor,
    status_code=status.HTTP_201_CREATED,
    summary="Create vendor",
)
def create_vendor(
    payload: Any,  # CreateVendor schema
    _admin=Depends(deps.get_admin_user),
    service: MaintenanceVendorService = Depends(get_vendor_service),
) -> Any:
    return service.create_vendor(payload, creator_id=_admin.id)


@router.get(
    "",
    response_model=List[MaintenanceVendor],
    summary="List vendors",
)
def list_vendors(
    hostel_id: str = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: MaintenanceVendorService = Depends(get_vendor_service),
) -> Any:
    return service.list_vendors_for_hostel(hostel_id)


@router.post(
    "/{vendor_id}/review",
    response_model=VendorPerformanceReview,
    summary="Submit vendor performance review",
)
def review_vendor(
    vendor_id: str,
    payload: Any,  # Review schema
    _admin=Depends(deps.get_admin_user),
    service: MaintenanceVendorService = Depends(get_vendor_service),
) -> Any:
    return service.create_performance_review(vendor_id, payload, reviewer_id=_admin.id)