from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.announcement import (
    ScheduleRequest,
    ScheduleConfig,
    RecurringAnnouncement,
    ScheduleUpdate,
    ScheduleCancel,
    PublishNow,
    ScheduledAnnouncementItem,
    ScheduledAnnouncementsList,
)
from app.services.announcement.announcement_scheduling_service import AnnouncementSchedulingService

router = APIRouter(prefix="/announcements/scheduling", tags=["announcements:scheduling"])


def get_scheduling_service(db: Session = Depends(deps.get_db)) -> AnnouncementSchedulingService:
    return AnnouncementSchedulingService(db=db)


@router.post(
    "/{announcement_id}",
    response_model=ScheduleConfig,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule announcement for publication",
)
def schedule_announcement(
    announcement_id: str,
    payload: ScheduleRequest,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementSchedulingService = Depends(get_scheduling_service),
) -> Any:
    return service.schedule(
        announcement_id=announcement_id,
        payload=payload,
        actor_id=current_user.id,
    )


@router.post(
    "/{announcement_id}/recurring",
    response_model=ScheduleConfig,
    summary="Create recurring announcement schedule",
)
def create_recurring_schedule(
    announcement_id: str,
    payload: RecurringAnnouncement,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementSchedulingService = Depends(get_scheduling_service),
) -> Any:
    return service.create_recurring(
        announcement_id=announcement_id,
        payload=payload,
        actor_id=current_user.id,
    )


@router.put(
    "/schedule/{schedule_id}",
    response_model=ScheduleConfig,
    summary="Update existing schedule",
)
def update_schedule(
    schedule_id: str,
    payload: ScheduleUpdate,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementSchedulingService = Depends(get_scheduling_service),
) -> Any:
    return service.update_schedule(
        schedule_id=schedule_id,
        payload=payload,
        actor_id=current_user.id,
    )


@router.post(
    "/schedule/{schedule_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel scheduled publication",
)
def cancel_schedule(
    schedule_id: str,
    payload: ScheduleCancel,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementSchedulingService = Depends(get_scheduling_service),
) -> Any:
    service.cancel(
        schedule_id=schedule_id,
        payload=payload,
        actor_id=current_user.id,
    )
    return {"detail": "Schedule cancelled"}


@router.post(
    "/{announcement_id}/publish-now",
    response_model=ScheduleConfig,
    summary="Override schedule and publish now",
)
def publish_now(
    announcement_id: str,
    payload: PublishNow,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementSchedulingService = Depends(get_scheduling_service),
) -> Any:
    return service.publish_now(
        announcement_id=announcement_id,
        payload=payload,
        actor_id=current_user.id,
    )


@router.get(
    "",
    response_model=ScheduledAnnouncementsList,
    summary="List scheduled announcements for hostel",
)
def list_scheduled_announcements(
    hostel_id: Optional[str] = Query(None),
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementSchedulingService = Depends(get_scheduling_service),
) -> Any:
    return service.list_scheduled(
        hostel_id=hostel_id,
        actor_id=current_user.id,
    )