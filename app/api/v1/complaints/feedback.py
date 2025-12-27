from typing import Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.complaint import (
    FeedbackRequest,
    FeedbackResponse,
    FeedbackSummary,
    FeedbackAnalysis,
)
from app.services.complaint.complaint_feedback_service import ComplaintFeedbackService

router = APIRouter(prefix="/complaints/feedback", tags=["complaints:feedback"])


def get_feedback_service(
    db: Session = Depends(deps.get_db),
) -> ComplaintFeedbackService:
    return ComplaintFeedbackService(db=db)


@router.post(
    "/{complaint_id}",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback for complaint",
)
def submit_feedback(
    complaint_id: str,
    payload: FeedbackRequest,
    current_user=Depends(deps.get_current_user),
    service: ComplaintFeedbackService = Depends(get_feedback_service),
) -> Any:
    return service.submit(
        complaint_id=complaint_id, payload=payload, user_id=current_user.id
    )


@router.get(
    "/summary",
    response_model=FeedbackSummary,
    summary="Get feedback summary",
)
def get_feedback_summary(
    hostel_id: str = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: ComplaintFeedbackService = Depends(get_feedback_service),
) -> Any:
    return service.summary(hostel_id=hostel_id)


@router.get(
    "/analysis",
    response_model=FeedbackAnalysis,
    summary="Get detailed feedback analysis",
)
def get_feedback_analysis(
    hostel_id: str = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: ComplaintFeedbackService = Depends(get_feedback_service),
) -> Any:
    return service.analysis(hostel_id=hostel_id)