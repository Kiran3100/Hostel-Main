"""
Enhanced announcements core API with improved performance and maintainability.
"""
from datetime import date
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, status, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api import deps
from app.core.logging import get_logger, log_endpoint_call
from app.core.security import require_permissions
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
from .deps import get_announcement_service

logger = get_logger(__name__)
router = APIRouter(
    prefix="/announcements", 
    tags=["announcements"],
    responses={
        404: {"description": "Announcement not found"},
        403: {"description": "Insufficient permissions"},
        500: {"description": "Internal server error"}
    }
)


# ---------------------------------------------------------------------------
# CRUD & Listing Operations
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=AnnouncementDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create announcement",
    description="""
    Create a new announcement in draft or ready-to-approve state.
    
    **Required permissions:** announcement:create
    **Supported content types:** text, markdown, html
    **File attachments:** Supported via file_urls field
    """,
    response_description="Created announcement with full details"
)
@log_endpoint_call
async def create_announcement(
    payload: AnnouncementCreate,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementService = Depends(get_announcement_service),
) -> AnnouncementDetail:
    """
    Create a new announcement with comprehensive validation and audit logging.
    """
    try:
        logger.info(
            f"Creating announcement",
            extra={
                "actor_id": current_user.id,
                "hostel_id": getattr(payload, 'hostel_id', None),
                "announcement_type": getattr(payload, 'type', None)
            }
        )
        
        result = await service.create_announcement(payload, actor_id=current_user.id)
        
        logger.info(
            f"Successfully created announcement",
            extra={"announcement_id": result.id, "actor_id": current_user.id}
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid announcement data: {str(e)}", extra={"actor_id": current_user.id})
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create announcement: {str(e)}", extra={"actor_id": current_user.id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Creation failed")


@router.put(
    "/{announcement_id}",
    response_model=AnnouncementDetail,
    summary="Update announcement",
    description="""
    Update existing announcement content, settings, or metadata.
    
    **Note:** Published announcements have limited update capabilities.
    **Permissions:** Requires ownership or admin access.
    """,
    responses={
        400: {"description": "Invalid update for announcement state"},
        404: {"description": "Announcement not found"},
        403: {"description": "No permission to update this announcement"}
    }
)
@log_endpoint_call
async def update_announcement(
    announcement_id: UUID,
    payload: AnnouncementUpdate,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementService = Depends(get_announcement_service),
) -> AnnouncementDetail:
    """
    Update existing announcement with state validation and audit trail.
    """
    try:
        logger.info(
            f"Updating announcement {announcement_id}",
            extra={"actor_id": current_user.id, "announcement_id": str(announcement_id)}
        )
        
        result = await service.update_announcement(
            announcement_id=str(announcement_id),
            payload=payload,
            actor_id=current_user.id,
        )
        
        logger.info(
            f"Successfully updated announcement {announcement_id}",
            extra={"actor_id": current_user.id, "announcement_id": str(announcement_id)}
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid update data for announcement {announcement_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except PermissionError as e:
        logger.warning(f"Permission denied for announcement {announcement_id} update", extra={"actor_id": current_user.id})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    except Exception as e:
        logger.error(f"Failed to update announcement {announcement_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Update failed")


@router.get(
    "/{announcement_id}",
    response_model=AnnouncementDetail,
    summary="Get announcement detail",
    description="""
    Retrieve comprehensive announcement details including:
    - Content and metadata
    - Targeting configuration 
    - Delivery status
    - Engagement metrics (if accessible)
    
    **Auto-tracking:** This endpoint automatically records a view event for analytics.
    """,
    response_description="Detailed announcement view with metadata and metrics"
)
@log_endpoint_call
async def get_announcement_detail(
    announcement_id: UUID,
    include_metrics: bool = Query(False, description="Include engagement metrics in response"),
    current_user=Depends(deps.get_current_user),
    service: AnnouncementService = Depends(get_announcement_service),
) -> AnnouncementDetail:
    """
    Get detailed announcement view with optional metrics inclusion.
    """
    try:
        result = await service.get_detail(
            announcement_id=str(announcement_id),
            actor_id=current_user.id,
            include_metrics=include_metrics,
        )
        
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Announcement not found")
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve announcement {announcement_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Retrieval failed")


@router.get(
    "",
    response_model=AnnouncementList,
    summary="List announcements",
    description="""
    List announcements for a hostel with advanced filtering, sorting, and pagination.
    
    **Supported filters:**
    - Status (draft, published, archived)
    - Type (general, urgent, maintenance, etc.)
    - Date ranges
    - Author/creator
    - Target audience
    
    **Sorting options:**
    - Created date (default)
    - Published date
    - Priority level
    - Title alphabetical
    """,
    response_description="Paginated list of announcements with metadata"
)
@log_endpoint_call
async def list_announcements(
    hostel_id: UUID = Query(..., description="Hostel ID to list announcements for"),
    filters: AnnouncementFilterParams = Depends(AnnouncementFilterParams),
    pagination=Depends(deps.get_pagination_params),
    current_user=Depends(deps.get_current_user),
    service: AnnouncementService = Depends(get_announcement_service),
) -> AnnouncementList:
    """
    List announcements with comprehensive filtering and pagination.
    """
    try:
        logger.debug(
            f"Listing announcements for hostel {hostel_id}",
            extra={
                "actor_id": current_user.id,
                "hostel_id": str(hostel_id),
                "filters": filters.model_dump() if filters else {},
                "pagination": pagination.model_dump() if pagination else {}
            }
        )
        
        result = await service.list_for_hostel(
            hostel_id=str(hostel_id),
            filters=filters,
            pagination=pagination,
            actor_id=current_user.id,
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to list announcements for hostel {hostel_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Listing failed")


# ---------------------------------------------------------------------------
# Lifecycle Management: publish/unpublish/archive
# ---------------------------------------------------------------------------

@router.post(
    "/{announcement_id}/publish",
    response_model=AnnouncementDetail,
    summary="Publish announcement",
    description="""
    Publish a draft announcement for immediate or scheduled delivery.
    
    **Publishing modes:**
    - Immediate: Publish right away
    - Scheduled: Publish at specific date/time
    - Conditional: Publish when conditions are met
    
    **Prerequisites:**
    - Announcement must be in draft or approved state
    - All required fields must be completed
    - Target audience must be configured
    """,
    responses={
        400: {"description": "Announcement not ready for publishing"},
        409: {"description": "Announcement already published"}
    }
)
@require_permissions(["announcement:publish"])
@log_endpoint_call
async def publish_announcement(
    announcement_id: UUID,
    payload: AnnouncementPublish = Body(
        default_factory=AnnouncementPublish,
        description="Publishing configuration (immediate vs scheduled)"
    ),
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementService = Depends(get_announcement_service),
) -> AnnouncementDetail:
    """
    Publish announcement with comprehensive pre-flight checks and audit logging.
    """
    try:
        logger.info(
            f"Publishing announcement {announcement_id}",
            extra={
                "actor_id": current_user.id,
                "announcement_id": str(announcement_id),
                "publish_mode": getattr(payload, 'mode', 'immediate')
            }
        )
        
        result = await service.publish(
            announcement_id=str(announcement_id),
            payload=payload,
            actor_id=current_user.id,
        )
        
        logger.info(
            f"Successfully published announcement {announcement_id}",
            extra={"actor_id": current_user.id, "announcement_id": str(announcement_id)}
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid publish request for announcement {announcement_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to publish announcement {announcement_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Publishing failed")


@router.post(
    "/{announcement_id}/unpublish",
    response_model=AnnouncementDetail,
    summary="Unpublish announcement",
    description="""
    Unpublish a currently published announcement with reason tracking.
    
    **Common reasons:**
    - Content error/correction needed
    - Emergency retraction
    - Superseded by newer announcement
    - Policy change
    
    **Effects:**
    - Removes from student-facing views
    - Maintains audit trail
    - Can be republished after corrections
    """,
    responses={
        400: {"description": "Cannot unpublish announcement in current state"}
    }
)
@require_permissions(["announcement:unpublish"])
@log_endpoint_call
async def unpublish_announcement(
    announcement_id: UUID,
    payload: AnnouncementUnpublish,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementService = Depends(get_announcement_service),
) -> AnnouncementDetail:
    """
    Unpublish announcement with mandatory reason and audit trail.
    """
    try:
        logger.warning(
            f"Unpublishing announcement {announcement_id}",
            extra={
                "actor_id": current_user.id,
                "announcement_id": str(announcement_id),
                "reason": getattr(payload, 'reason', 'Not specified')
            }
        )
        
        result = await service.unpublish(
            announcement_id=str(announcement_id),
            payload=payload,
            actor_id=current_user.id,
        )
        
        logger.warning(
            f"Successfully unpublished announcement {announcement_id}",
            extra={"actor_id": current_user.id, "announcement_id": str(announcement_id)}
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid unpublish request for announcement {announcement_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to unpublish announcement {announcement_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unpublish failed")


@router.post(
    "/{announcement_id}/archive",
    status_code=status.HTTP_200_OK,
    summary="Archive announcement",
    description="""
    Archive an announcement to remove from active views while preserving history.
    
    **Effects:**
    - Removes from active announcement lists
    - Maintains full audit trail and data
    - Can be unarchived if needed
    - Preserves all engagement metrics
    
    **Use cases:**
    - End-of-semester cleanup
    - Outdated information removal
    - Space management
    """,
    responses={
        200: {"description": "Announcement successfully archived"}
    }
)
@require_permissions(["announcement:archive"])
@log_endpoint_call
async def archive_announcement(
    announcement_id: UUID,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementService = Depends(get_announcement_service),
) -> Dict[str, str]:
    """
    Archive announcement with comprehensive state validation.
    """
    try:
        logger.info(
            f"Archiving announcement {announcement_id}",
            extra={"actor_id": current_user.id, "announcement_id": str(announcement_id)}
        )
        
        await service.archive(announcement_id=str(announcement_id), actor_id=current_user.id)
        
        logger.info(
            f"Successfully archived announcement {announcement_id}",
            extra={"actor_id": current_user.id, "announcement_id": str(announcement_id)}
        )
        
        return {"detail": "Announcement archived successfully"}
        
    except ValueError as e:
        logger.warning(f"Invalid archive request for announcement {announcement_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to archive announcement {announcement_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Archive failed")


@router.post(
    "/{announcement_id}/unarchive",
    status_code=status.HTTP_200_OK,
    summary="Unarchive announcement",
    description="""
    Restore an archived announcement to active state.
    
    **Restored to:** Original state (draft/published) before archiving
    **Validation:** Ensures content compliance with current policies
    **Audit:** Full restoration event logged
    """,
    responses={
        200: {"description": "Announcement successfully unarchived"}
    }
)
@require_permissions(["announcement:unarchive"])
@log_endpoint_call
async def unarchive_announcement(
    announcement_id: UUID,
    current_user=Depends(deps.get_current_user_with_roles),
    service: AnnouncementService = Depends(get_announcement_service),
) -> Dict[str, str]:
    """
    Unarchive announcement with state restoration and validation.
    """
    try:
        logger.info(
            f"Unarchiving announcement {announcement_id}",
            extra={"actor_id": current_user.id, "announcement_id": str(announcement_id)}
        )
        
        await service.unarchive(announcement_id=str(announcement_id), actor_id=current_user.id)
        
        logger.info(
            f"Successfully unarchived announcement {announcement_id}",
            extra={"actor_id": current_user.id, "announcement_id": str(announcement_id)}
        )
        
        return {"detail": "Announcement unarchived successfully"}
        
    except ValueError as e:
        logger.warning(f"Invalid unarchive request for announcement {announcement_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to unarchive announcement {announcement_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unarchive failed")


# ---------------------------------------------------------------------------
# Advanced Operations: search, export, bulk operations, analytics
# ---------------------------------------------------------------------------

@router.post(
    "/search",
    response_model=AnnouncementList,
    summary="Full-text search announcements",
    description="""
    Perform advanced full-text search across announcements with ranking and filtering.
    
    **Search capabilities:**
    - Title and content full-text search
    - Tag-based filtering
    - Author/creator search
    - Date range constraints
    - Priority-based ranking
    
    **Performance:** Results are cached for common queries
    """,
    response_description="Ranked search results with relevance scoring"
)
@log_endpoint_call
async def search_announcements(
    payload: SearchRequest,
    current_user=Depends(deps.get_current_user),
    service: AnnouncementService = Depends(get_announcement_service),
) -> AnnouncementList:
    """
    Advanced search with full-text capabilities and relevance ranking.
    """
    try:
        logger.debug(
            f"Searching announcements",
            extra={
                "actor_id": current_user.id,
                "query": getattr(payload, 'query', ''),
                "filters": getattr(payload, 'filters', {})
            }
        )
        
        result = await service.search(
            payload=payload,
            actor_id=current_user.id,
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Search failed: {str(e)}", extra={"actor_id": current_user.id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Search failed")


@router.post(
    "/export",
    summary="Export announcements",
    description="""
    Export announcements in various formats for reporting and archival.
    
    **Supported formats:**
    - PDF: Formatted reports with engagement data
    - Excel: Detailed spreadsheets with metrics
    - CSV: Raw data for analysis
    - JSON: Complete data export
    
    **Export includes:**
    - Announcement content and metadata
    - Engagement metrics (if permission allows)
    - Audit trail information
    - Target audience details
    """,
    responses={
        200: {"description": "Export job initiated, download link provided"},
        202: {"description": "Export job queued for processing"}
    }
)
@require_permissions(["announcement:export"])
@log_endpoint_call
async def export_announcements(
    payload: AnnouncementExportRequest,
    current_user=Depends(deps.get_admin_user),
    service: AnnouncementService = Depends(get_announcement_service),
) -> Dict[str, Any]:
    """
    Initiate announcement export with format validation and job tracking.
    """
    try:
        logger.info(
            f"Initiating announcement export",
            extra={
                "actor_id": current_user.id,
                "format": getattr(payload, 'format', 'unknown'),
                "filter_count": len(getattr(payload, 'filters', []))
            }
        )
        
        result = await service.export_announcements(
            payload=payload,
            actor_id=current_user.id,
        )
        
        logger.info(
            f"Export job initiated",
            extra={"actor_id": current_user.id, "job_id": result.get("job_id")}
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Invalid export request: {str(e)}", extra={"actor_id": current_user.id})
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error(f"Export initiation failed: {str(e)}", extra={"actor_id": current_user.id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Export failed")


@router.post(
    "/bulk-delete",
    status_code=status.HTTP_200_OK,
    summary="Bulk delete announcements",
    description="""
    Delete multiple announcements in a single operation with safety checks.
    
    **Safety features:**
    - Dry-run mode available
    - Published announcement protection
    - Cascade deletion handling
    - Comprehensive audit logging
    
    **Limitations:**
    - Maximum 100 announcements per request
    - Requires admin privileges
    - Cannot delete announcements with active schedules
    """,
    responses={
        200: {"description": "Bulk deletion completed successfully"},
        207: {"description": "Partial success with detailed results"}
    }
)
@require_permissions(["announcement:bulk_delete"])
@log_endpoint_call
async def bulk_delete_announcements(
    payload: BulkDeleteRequest,
    current_user=Depends(deps.get_admin_user),
    service: AnnouncementService = Depends(get_announcement_service),
) -> Dict[str, Any]:
    """
    Bulk delete with comprehensive safety checks and detailed result reporting.
    """
    try:
        logger.warning(
            f"Initiating bulk delete",
            extra={
                "actor_id": current_user.id,
                "target_count": len(getattr(payload, 'announcement_ids', [])),
                "dry_run": getattr(payload, 'dry_run', False)
            }
        )
        
        result = await service.bulk_delete(payload=payload, actor_id=current_user.id)
        
        logger.warning(
            f"Bulk delete completed",
            extra={
                "actor_id": current_user.id,
                "deleted_count": result.get("deleted_count", 0),
                "failed_count": result.get("failed_count", 0)
            }
        )
        
        if result.get("failed_count", 0) > 0:
            return JSONResponse(
                status_code=status.HTTP_207_MULTI_STATUS,
                content=result
            )
        
        return {"detail": "Bulk delete completed successfully", **result}
        
    except ValueError as e:
        logger.warning(f"Invalid bulk delete request: {str(e)}", extra={"actor_id": current_user.id})
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error(f"Bulk delete failed: {str(e)}", extra={"actor_id": current_user.id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Bulk delete failed")


@router.post(
    "/stats",
    response_model=AnnouncementSummary,
    summary="Get announcement statistics",
    description="""
    Generate comprehensive announcement statistics and analytics.
    
    **Statistics include:**
    - Publication trends over time
    - Engagement rate analysis
    - Popular content categories
    - Author performance metrics
    - Target audience effectiveness
    
    **Time ranges supported:**
    - Last 7 days, 30 days, 90 days
    - Custom date ranges
    - Year-over-year comparisons
    """,
    response_description="Comprehensive statistics and trends"
)
@require_permissions(["announcement:analytics"])
@log_endpoint_call
async def get_announcement_stats(
    payload: AnnouncementStatsRequest,
    current_user=Depends(deps.get_admin_user),
    service: AnnouncementService = Depends(get_announcement_service),
) -> AnnouncementSummary:
    """
    Generate comprehensive announcement statistics with caching.
    """
    try:
        logger.debug(
            f"Generating announcement statistics",
            extra={
                "actor_id": current_user.id,
                "time_range": getattr(payload, 'time_range', 'unknown'),
                "hostel_id": getattr(payload, 'hostel_id', None)
            }
        )
        
        result = await service.get_stats(
            payload=payload,
            actor_id=current_user.id,
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Statistics generation failed: {str(e)}", extra={"actor_id": current_user.id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Statistics generation failed")