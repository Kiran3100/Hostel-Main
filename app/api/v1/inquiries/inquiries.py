from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.inquiry.inquiry_base import (
    InquiryCreate,
    InquiryUpdate,
)
from app.schemas.inquiry.inquiry_response import (
    InquiryDetail,
    InquiryListItem,
    InquiryResponse,
    InquiryStats,
)
from app.schemas.inquiry.inquiry_filters import (
    InquiryFilterParams,
    InquirySearchRequest,
)
from app.schemas.inquiry.inquiry_status import (
    InquiryStatusUpdate,
    InquiryAssignment,
    BulkInquiryStatusUpdate,
    InquiryConversion,
)
from app.services.inquiry.inquiry_service import InquiryService
from app.services.inquiry.inquiry_assignment_service import InquiryAssignmentService
from app.services.inquiry.inquiry_conversion_service import InquiryConversionService
from app.services.inquiry.inquiry_analytics_service import InquiryAnalyticsService

router = APIRouter(prefix="/inquiries", tags=["inquiries"])


def get_inquiry_service(db: Session = Depends(deps.get_db)) -> InquiryService:
    return InquiryService(db=db)


def get_assignment_service(db: Session = Depends(deps.get_db)) -> InquiryAssignmentService:
    return InquiryAssignmentService(db=db)


def get_conversion_service(db: Session = Depends(deps.get_db)) -> InquiryConversionService:
    return InquiryConversionService(db=db)


def get_analytics_service(db: Session = Depends(deps.get_db)) -> InquiryAnalyticsService:
    return InquiryAnalyticsService(db=db)


# ---------------------------------------------------------------------------
# Core CRUD
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=InquiryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new inquiry",
)
def create_inquiry(
    payload: InquiryCreate,
    # Inquiries can be public (visitor) or admin-created.
    # If public, you might omit current_user dependency or make it optional.
    service: InquiryService = Depends(get_inquiry_service),
) -> Any:
    return service.create(payload)


@router.get(
    "/{inquiry_id}",
    response_model=InquiryDetail,
    summary="Get inquiry details",
)
def get_inquiry(
    inquiry_id: str,
    _admin=Depends(deps.get_admin_user),
    service: InquiryService = Depends(get_inquiry_service),
) -> Any:
    inquiry = service.get_detail(inquiry_id)
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    return inquiry


@router.patch(
    "/{inquiry_id}",
    response_model=InquiryDetail,
    summary="Update inquiry",
)
def update_inquiry(
    inquiry_id: str,
    payload: InquiryUpdate,
    _admin=Depends(deps.get_admin_user),
    service: InquiryService = Depends(get_inquiry_service),
) -> Any:
    return service.update(inquiry_id, payload)


@router.delete(
    "/{inquiry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete inquiry",
)
def delete_inquiry(
    inquiry_id: str,
    _super_admin=Depends(deps.get_super_admin_user),
    service: InquiryService = Depends(get_inquiry_service),
) -> Any:
    service.delete(inquiry_id)
    return None


@router.get(
    "",
    response_model=List[InquiryListItem],
    summary="List inquiries",
)
def list_inquiries(
    filters: InquiryFilterParams = Depends(InquiryFilterParams),
    pagination=Depends(deps.get_pagination_params),
    _admin=Depends(deps.get_admin_user),
    service: InquiryService = Depends(get_inquiry_service),
) -> Any:
    return service.list_with_filters(filters=filters, pagination=pagination)


@router.post(
    "/search",
    response_model=List[InquiryListItem],
    summary="Search inquiries",
)
def search_inquiries(
    payload: InquirySearchRequest,
    pagination=Depends(deps.get_pagination_params),
    _admin=Depends(deps.get_admin_user),
    service: InquiryService = Depends(get_inquiry_service),
) -> Any:
    return service.search(payload, pagination=pagination)


# ---------------------------------------------------------------------------
# Status & Workflow
# ---------------------------------------------------------------------------


@router.post(
    "/{inquiry_id}/status",
    response_model=InquiryDetail,
    summary="Change inquiry status",
)
def change_status(
    inquiry_id: str,
    payload: InquiryStatusUpdate,
    current_user=Depends(deps.get_current_user),
    service: InquiryService = Depends(get_inquiry_service),
) -> Any:
    return service.change_status(
        inquiry_id=inquiry_id, payload=payload, user_id=current_user.id
    )


@router.post(
    "/bulk-status",
    summary="Bulk change status",
)
def bulk_change_status(
    payload: BulkInquiryStatusUpdate,
    current_user=Depends(deps.get_current_user),
    service: InquiryService = Depends(get_inquiry_service),
) -> Any:
    return service.bulk_change_status(payload, user_id=current_user.id)


@router.post(
    "/{inquiry_id}/assign",
    summary="Assign inquiry",
)
def assign_inquiry(
    inquiry_id: str,
    payload: InquiryAssignment,
    current_user=Depends(deps.get_current_user),
    service: InquiryAssignmentService = Depends(get_assignment_service),
) -> Any:
    return service.assign(
        inquiry_id=inquiry_id, payload=payload, assigner_id=current_user.id
    )


@router.post(
    "/{inquiry_id}/convert",
    summary="Convert inquiry to booking",
)
def convert_inquiry(
    inquiry_id: str,
    payload: InquiryConversion,  # Contains booking details if needed
    current_user=Depends(deps.get_current_user),
    service: InquiryConversionService = Depends(get_conversion_service),
) -> Any:
    return service.convert(inquiry_id, payload, converter_id=current_user.id)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


@router.get(
    "/stats",
    response_model=InquiryStats,
    summary="Get inquiry statistics",
)
def get_inquiry_stats(
    hostel_id: str = Query(...),
    service: InquiryAnalyticsService = Depends(get_analytics_service),
) -> Any:
    return service.get_overview(hostel_id=hostel_id)