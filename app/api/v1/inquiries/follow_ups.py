from typing import Any, List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import deps
# Assuming schemas exist in app.schemas.inquiry
from app.schemas.inquiry.inquiry_status import (
    InquiryFollowUp,  # Schema for creating follow-up
    InquiryTimelineEntry,  # Schema for history display
)
from app.services.inquiry.inquiry_follow_up_service import InquiryFollowUpService

router = APIRouter(prefix="/inquiries/follow-ups", tags=["inquiries:follow-ups"])


def get_followup_service(db: Session = Depends(deps.get_db)) -> InquiryFollowUpService:
    return InquiryFollowUpService(db=db)


@router.post(
    "/{inquiry_id}",
    response_model=InquiryTimelineEntry,
    status_code=status.HTTP_201_CREATED,
    summary="Record follow-up interaction",
)
def record_follow_up(
    inquiry_id: str,
    payload: InquiryFollowUp,
    current_user=Depends(deps.get_current_user),
    service: InquiryFollowUpService = Depends(get_followup_service),
) -> Any:
    return service.record(inquiry_id, payload, user_id=current_user.id)


@router.get(
    "/{inquiry_id}/timeline",
    response_model=List[InquiryTimelineEntry],
    summary="Get inquiry timeline",
)
def get_timeline(
    inquiry_id: str,
    current_user=Depends(deps.get_current_user),
    service: InquiryFollowUpService = Depends(get_followup_service),
) -> Any:
    return service.timeline(inquiry_id)


@router.post(
    "/{inquiry_id}/schedule",
    summary="Schedule next follow-up",
)
def schedule_follow_up(
    inquiry_id: str,
    follow_up_date: str = Query(..., description="ISO datetime"),
    notes: str = Query(None),
    current_user=Depends(deps.get_current_user),
    service: InquiryFollowUpService = Depends(get_followup_service),
) -> Any:
    return service.schedule_follow_up(
        inquiry_id, follow_up_date, notes, scheduler_id=current_user.id
    )