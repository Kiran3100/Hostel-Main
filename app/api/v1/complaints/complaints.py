from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintUpdate,
    ComplaintResponse,
    ComplaintDetail,
    ComplaintListItem,
    ComplaintFilterParams,
    ComplaintSearchRequest,
    ComplaintStatusUpdate,
    ComplaintSummary,
)
from app.services.complaint.complaint_service import ComplaintService

router = APIRouter(prefix="/complaints", tags=["complaints"])


def get_complaint_service(db: Session = Depends(deps.get_db)) -> ComplaintService:
    return ComplaintService(db=db)


@router.post(
    "",
    response_model=ComplaintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new complaint",
)
def create_complaint(
    payload: ComplaintCreate,
    current_user=Depends(deps.get_current_user),
    service: ComplaintService = Depends(get_complaint_service),
) -> Any:
    return service.create(payload, creator_id=current_user.id)


@router.get(
    "/{complaint_id}",
    response_model=ComplaintDetail,
    summary="Get complaint details",
)
def get_complaint(
    complaint_id: str,
    current_user=Depends(deps.get_current_user),
    service: ComplaintService = Depends(get_complaint_service),
) -> Any:
    complaint = service.get_detail(complaint_id, user_id=current_user.id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found"
        )
    return complaint


@router.patch(
    "/{complaint_id}",
    response_model=ComplaintDetail,
    summary="Update complaint details",
)
def update_complaint(
    complaint_id: str,
    payload: ComplaintUpdate,
    current_user=Depends(deps.get_current_user),
    service: ComplaintService = Depends(get_complaint_service),
) -> Any:
    return service.update(
        complaint_id=complaint_id, payload=payload, user_id=current_user.id
    )


@router.post(
    "/{complaint_id}/status",
    response_model=ComplaintDetail,
    summary="Change complaint status",
)
def change_complaint_status(
    complaint_id: str,
    payload: ComplaintStatusUpdate,
    current_user=Depends(deps.get_current_user),
    service: ComplaintService = Depends(get_complaint_service),
) -> Any:
    return service.change_status(
        complaint_id=complaint_id, payload=payload, user_id=current_user.id
    )


@router.get(
    "",
    response_model=List[ComplaintListItem],
    summary="List complaints",
)
def list_complaints(
    filters: ComplaintFilterParams = Depends(ComplaintFilterParams),
    pagination=Depends(deps.get_pagination_params),
    current_user=Depends(deps.get_current_user),
    service: ComplaintService = Depends(get_complaint_service),
) -> Any:
    return service.list_with_filters(
        filters=filters, pagination=pagination, user_id=current_user.id
    )


@router.post(
    "/search",
    response_model=List[ComplaintListItem],
    summary="Search complaints",
)
def search_complaints(
    payload: ComplaintSearchRequest,
    pagination=Depends(deps.get_pagination_params),
    current_user=Depends(deps.get_current_user),
    service: ComplaintService = Depends(get_complaint_service),
) -> Any:
    return service.search(
        payload=payload, pagination=pagination, user_id=current_user.id
    )


@router.get(
    "/summary/stats",
    response_model=ComplaintSummary,
    summary="Get complaint summary statistics",
)
def get_complaint_summary(
    hostel_id: str = Query(..., description="Hostel ID"),
    current_user=Depends(deps.get_current_user),
    service: ComplaintService = Depends(get_complaint_service),
) -> Any:
    return service.get_summary(hostel_id=hostel_id)