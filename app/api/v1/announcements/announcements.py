from datetime import date
from typing import Any

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.announcement import (
    AnnouncementCreate,
    AnnouncementUpdate,
    AnnouncementPublish,
    AnnouncementUnpublish,
    AnnouncementResponse,
    AnnouncementDetail,
    AnnouncementList,
    AnnouncementFilterParams,
    SearchRequest,
    AnnouncementExportRequest,
    BulkDeleteRequest,
    AnnouncementStatsRequest,
    AnnouncementSummary,
)
from app.services.announcement.announcement_service import AnnouncementService

router = APIRouter(prefix="/announcements", tags=["announcements"])


def get_announcement_service(db: Session = Depends(deps.get_db)) -> AnnouncementService:
    return AnnouncementService(db=db)


# ---------------------------------------------------------------------------
# CRUD & Listing
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=AnnouncementDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create announcement",
)
def create_announcement(
    payload: AnnouncementCreate,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementService = Depends(get_announcement_service),
) -> Any:
    """
    Create a new announcement (draft or ready-to-approve).
    """
    return service.create_announcement(payload, actor_id=current_user.id)


@router.put(
    "/{announcement_id}",
    response_model=AnnouncementDetail,
    summary="Update announcement",
)
def update_announcement(
    announcement_id: str,
    payload: AnnouncementUpdate,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementService = Depends(get_announcement_service),
) -> Any:
    """
    Update existing announcement content/settings.
    """
    return service.update_announcement(
        announcement_id=announcement_id,
        payload=payload,
        actor_id=current_user.id,
    )


@router.get(
    "/{announcement_id}",
    response_model=AnnouncementDetail,
    summary="Get announcement detail",
)
def get_announcement_detail(
    announcement_id: str,
    current_user=Depends(deps.get_current_user),
    service: AnnouncementService = Depends(get_announcement_service),
) -> Any:
    """
    Detailed announcement view including metadata, targeting, delivery, and engagement.
    """
    return service.get_detail(
        announcement_id=announcement_id,
        actor_id=current_user.id,
    )


@router.get(
    "",
    response_model=AnnouncementList,
    summary="List announcements",
)
def list_announcements(
    hostel_id: str = Query(..., description="Hostel ID"),
    filters: AnnouncementFilterParams = Depends(AnnouncementFilterParams),
    pagination=Depends(deps.get_pagination_params),
    current_user=Depends(deps.get_current_user),
    service: AnnouncementService = Depends(get_announcement_service),
) -> Any:
    """
    List announcements for a hostel with rich filtering, sorting, and pagination.
    """
    return service.list_for_hostel(
        hostel_id=hostel_id,
        filters=filters,
        pagination=pagination,
        actor_id=current_user.id,
    )


# ---------------------------------------------------------------------------
# Lifecycle: publish/unpublish/archive
# ---------------------------------------------------------------------------


@router.post(
    "/{announcement_id}/publish",
    response_model=AnnouncementDetail,
    summary="Publish announcement",
)
def publish_announcement(
    announcement_id: str,
    payload: AnnouncementPublish = Body(
        default_factory=AnnouncementPublish,
        description="Publish options (immediate vs scheduled)",
    ),
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementService = Depends(get_announcement_service),
) -> Any:
    """
    Publish a draft announcement (immediate or scheduled by time).
    """
    return service.publish(
        announcement_id=announcement_id,
        payload=payload,
        actor_id=current_user.id,
    )


@router.post(
    "/{announcement_id}/unpublish",
    response_model=AnnouncementDetail,
    summary="Unpublish announcement",
)
def unpublish_announcement(
    announcement_id: str,
    payload: AnnouncementUnpublish,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementService = Depends(get_announcement_service),
) -> Any:
    """
    Unpublish a currently published announcement, with a recorded reason.
    """
    return service.unpublish(
        announcement_id=announcement_id,
        payload=payload,
        actor_id=current_user.id,
    )


@router.post(
    "/{announcement_id}/archive",
    status_code=status.HTTP_200_OK,
    summary="Archive announcement",
)
def archive_announcement(
    announcement_id: str,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementService = Depends(get_announcement_service),
) -> Any:
    """
    Archive an announcement (remove from active views, keep for history).
    """
    service.archive(announcement_id=announcement_id, actor_id=current_user.id)
    return {"detail": "Announcement archived"}


@router.post(
    "/{announcement_id}/unarchive",
    status_code=status.HTTP_200_OK,
    summary="Unarchive announcement",
)
def unarchive_announcement(
    announcement_id: str,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementService = Depends(get_announcement_service),
) -> Any:
    """
    Restore an archived announcement to draft/published state.
    """
    service.unarchive(announcement_id=announcement_id, actor_id=current_user.id)
    return {"detail": "Announcement unarchived"}


# ---------------------------------------------------------------------------
# Search, export, bulk delete, stats
# ---------------------------------------------------------------------------


@router.post(
    "/search",
    response_model=AnnouncementList,
    summary="Full-text search announcements",
)
def search_announcements(
    payload: SearchRequest,
    current_user=Depends(deps.get_current_user),
    service: AnnouncementService = Depends(get_announcement_service),
) -> Any:
    return service.search(
        payload=payload,
        actor_id=current_user.id,
    )


@router.post(
    "/export",
    summary="Export announcements",
)
def export_announcements(
    payload: AnnouncementExportRequest,
    current_user=Depends(deps.get_admin_user),
    service: AnnouncementService = Depends(get_announcement_service),
) -> Any:
    """
    Export announcements to PDF/Excel/CSV/JSON.

    Return type should be your export-specific schema (e.g. with download URL).
    """
    return service.export_announcements(
        payload=payload,
        actor_id=current_user.id,
    )


@router.post(
    "/bulk-delete",
    status_code=status.HTTP_200_OK,
    summary="Bulk delete announcements",
)
def bulk_delete_announcements(
    payload: BulkDeleteRequest,
    current_user=Depends(deps.get_admin_user),
    service: AnnouncementService = Depends(get_announcement_service),
) -> Any:
    service.bulk_delete(payload=payload, actor_id=current_user.id)
    return {"detail": "Bulk delete completed"}


@router.post(
    "/stats",
    response_model=AnnouncementSummary,
    summary="Get announcement statistics",
)
def get_announcement_stats(
    payload: AnnouncementStatsRequest,
    current_user=Depends(deps.get_admin_user),
    service: AnnouncementService = Depends(get_announcement_service),
) -> Any:
    return service.get_stats(
        payload=payload,
        actor_id=current_user.id,
    )