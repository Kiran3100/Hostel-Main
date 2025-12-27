from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.announcement import (
    ReadReceipt,
    ReadReceiptResponse,
    AcknowledgmentRequest,
    AcknowledgmentResponse,
    AcknowledgmentTracking,
    EngagementMetrics,
    EngagementTrend,
    StudentEngagement,
    AnnouncementAnalytics,
)
from app.services.announcement.announcement_tracking_service import AnnouncementTrackingService

router = APIRouter(prefix="/announcements/tracking", tags=["announcements:tracking"])


def get_tracking_service(db: Session = Depends(deps.get_db)) -> AnnouncementTrackingService:
    return AnnouncementTrackingService(db=db)


# ---------------------------------------------------------------------------
# Student-facing endpoints: read receipts & acknowledgments
# ---------------------------------------------------------------------------


@router.post(
    "/{announcement_id}/read-receipts",
    response_model=ReadReceiptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit read receipt",
)
def submit_read_receipt(
    announcement_id: str,
    payload: ReadReceipt,
    current_student=Depends(deps.get_student_user),
    service: AnnouncementTrackingService = Depends(get_tracking_service),
) -> Any:
    """
    Called from student-facing UI when a student views/reads an announcement.
    """
    return service.submit_read_receipt(
        announcement_id=announcement_id,
        payload=payload,
        student_id=current_student.id,
    )


@router.post(
    "/{announcement_id}/acknowledgments",
    response_model=AcknowledgmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Acknowledge announcement",
)
def acknowledge_announcement(
    announcement_id: str,
    payload: AcknowledgmentRequest,
    current_student=Depends(deps.get_student_user),
    service: AnnouncementTrackingService = Depends(get_tracking_service),
) -> Any:
    """
    Student acknowledges important announcement (e.g. policy, safety).
    """
    return service.acknowledge(
        announcement_id=announcement_id,
        payload=payload,
        student_id=current_student.id,
    )


# ---------------------------------------------------------------------------
# Staff-facing endpoints: tracking & analytics
# ---------------------------------------------------------------------------


@router.get(
    "/{announcement_id}/acknowledgments",
    response_model=AcknowledgmentTracking,
    summary="Get acknowledgment tracking for announcement",
)
def get_acknowledgment_tracking(
    announcement_id: str,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementTrackingService = Depends(get_tracking_service),
) -> Any:
    return service.get_acknowledgment_tracking(
        announcement_id=announcement_id,
        actor_id=current_user.id,
    )


@router.get(
    "/{announcement_id}/engagement",
    response_model=EngagementMetrics,
    summary="Get engagement metrics for announcement",
)
def get_engagement_metrics(
    announcement_id: str,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementTrackingService = Depends(get_tracking_service),
) -> Any:
    return service.compute_engagement(
        announcement_id=announcement_id,
        actor_id=current_user.id,
    )


@router.get(
    "/{announcement_id}/engagement/trend",
    response_model=EngagementTrend,
    summary="Get engagement trend over time",
)
def get_engagement_trend(
    announcement_id: str,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementTrackingService = Depends(get_tracking_service),
) -> Any:
    return service.get_engagement_trend(
        announcement_id=announcement_id,
        actor_id=current_user.id,
    )


@router.get(
    "/students/{student_id}/engagement",
    response_model=StudentEngagement,
    summary="Get engagement profile for student",
)
def get_student_engagement(
    student_id: str,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementTrackingService = Depends(get_tracking_service),
) -> Any:
    return service.get_student_engagement(
        student_id=student_id,
        actor_id=current_user.id,
    )


@router.get(
    "/analytics",
    response_model=AnnouncementAnalytics,
    summary="Get announcement analytics dashboard",
)
def get_announcement_analytics(
    hostel_id: Optional[str] = Query(None),
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementTrackingService = Depends(get_tracking_service),
) -> Any:
    """
    System-wide or per-hostel announcement analytics dashboard
    (read rates, acknowledgments, device breakdowns, etc.).
    """
    return service.get_analytics(
        hostel_id=hostel_id,
        actor_id=current_user.id,
    )