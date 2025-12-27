from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.hostel.hostel_base import (
    HostelCreate,
    HostelUpdate,
)
from app.schemas.hostel.hostel_response import (
    HostelDetail,
    HostelResponse,
    HostelListItem,
    HostelStats,
)
from app.schemas.hostel.hostel_filter import HostelFilterParams
from app.services.hostel.hostel_service import HostelService

router = APIRouter(prefix="/hostels", tags=["hostels"])


def get_hostel_service(db: Session = Depends(deps.get_db)) -> HostelService:
    return HostelService(db=db)


@router.post(
    "",
    response_model=HostelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new hostel",
)
def create_hostel(
    payload: HostelCreate,
    _super_admin=Depends(deps.get_super_admin_user),
    service: HostelService = Depends(get_hostel_service),
) -> Any:
    return service.create_hostel(payload)


@router.get(
    "/{hostel_id}",
    response_model=HostelDetail,
    summary="Get hostel details",
)
def get_hostel(
    hostel_id: str,
    # This might be public or protected depending on business rules.
    # If public, remove current_user dependency or make optional.
    service: HostelService = Depends(get_hostel_service),
) -> Any:
    hostel = service.get_detail(hostel_id)
    if not hostel:
        raise HTTPException(status_code=404, detail="Hostel not found")
    return hostel


@router.patch(
    "/{hostel_id}",
    response_model=HostelDetail,
    summary="Update hostel details",
)
def update_hostel(
    hostel_id: str,
    payload: HostelUpdate,
    _admin=Depends(deps.get_admin_user),
    service: HostelService = Depends(get_hostel_service),
) -> Any:
    return service.update_hostel(hostel_id, payload)


@router.get(
    "",
    response_model=List[HostelListItem],
    summary="List hostels",
)
def list_hostels(
    filters: HostelFilterParams = Depends(HostelFilterParams),
    pagination=Depends(deps.get_pagination_params),
    service: HostelService = Depends(get_hostel_service),
) -> Any:
    return service.list_hostels(filters=filters, pagination=pagination)


@router.get(
    "/{hostel_id}/stats",
    response_model=HostelStats,
    summary="Get hostel statistics",
)
def get_hostel_stats(
    hostel_id: str,
    _admin=Depends(deps.get_admin_user),
    service: HostelService = Depends(get_hostel_service),
) -> Any:
    return service.get_stats(hostel_id)


@router.post(
    "/{hostel_id}/status",
    response_model=HostelDetail,
    summary="Update hostel status",
)
def set_hostel_status(
    hostel_id: str,
    status_value: str = Query(..., alias="status", description="New status"),
    _super_admin=Depends(deps.get_super_admin_user),
    service: HostelService = Depends(get_hostel_service),
) -> Any:
    return service.set_status(hostel_id, status_value)