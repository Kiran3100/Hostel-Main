from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.announcement import (
    TargetingConfig,
    AudienceSelection,
    TargetingSummary,
    BulkTargeting,
    TargetingPreview,
)
from app.services.announcement.announcement_targeting_service import AnnouncementTargetingService

router = APIRouter(prefix="/announcements/targeting", tags=["announcements:targeting"])


def get_targeting_service(db: Session = Depends(deps.get_db)) -> AnnouncementTargetingService:
    return AnnouncementTargetingService(db=db)


@router.post(
    "/{announcement_id}/apply",
    response_model=TargetingSummary,
    summary="Apply targeting configuration to announcement",
)
def apply_targeting(
    announcement_id: str,
    payload: AudienceSelection,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementTargetingService = Depends(get_targeting_service),
) -> Any:
    """
    Apply comprehensive audience selection rules to an announcement.
    """
    return service.apply_targeting(
        announcement_id=announcement_id,
        payload=payload,
        actor_id=current_user.id,
    )


@router.post(
    "/{announcement_id}/preview",
    response_model=TargetingPreview,
    summary="Preview targeting results",
)
def preview_targeting(
    announcement_id: str,
    payload: AudienceSelection,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementTargetingService = Depends(get_targeting_service),
) -> Any:
    return service.preview_targeting(
        announcement_id=announcement_id,
        payload=payload,
        actor_id=current_user.id,
    )


@router.get(
    "/{announcement_id}/summary",
    response_model=TargetingSummary,
    summary="Get targeting summary",
)
def get_targeting_summary(
    announcement_id: str,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementTargetingService = Depends(get_targeting_service),
) -> Any:
    return service.compute_summary(
        announcement_id=announcement_id,
        actor_id=current_user.id,
    )


@router.delete(
    "/{announcement_id}",
    status_code=status.HTTP_200_OK,
    summary="Clear all targeting for announcement",
)
def clear_targeting(
    announcement_id: str,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementTargetingService = Depends(get_targeting_service),
) -> Any:
    service.clear_targeting(
        announcement_id=announcement_id,
        actor_id=current_user.id,
    )
    return {"detail": "Targeting cleared"}


@router.post(
    "/bulk",
    response_model=TargetingSummary,
    summary="Apply bulk targeting rules",
)
def apply_bulk_targeting(
    payload: BulkTargeting,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementTargetingService = Depends(get_targeting_service),
) -> Any:
    return service.apply_bulk_targeting(
        payload=payload,
        actor_id=current_user.id,
    )