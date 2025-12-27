"""
Booking Search API

Provides advanced search and export capabilities including:
- Multi-criteria booking search
- Export to various formats (CSV, Excel, PDF)
- Saved search filters
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.logging import get_logger
from app.schemas.booking.booking_filters import (
    BookingExportRequest,
    BookingFilterParams,
    BookingSearchRequest,
)
from app.schemas.booking.booking_response import BookingListItem
from app.services.booking.booking_search_service import BookingSearchService

logger = get_logger(__name__)

router = APIRouter(prefix="/bookings/search", tags=["bookings:search"])


def get_search_service(db: Session = Depends(deps.get_db)) -> BookingSearchService:
    """
    Dependency injection for BookingSearchService.
    
    Args:
        db: Database session
        
    Returns:
        BookingSearchService instance
    """
    return BookingSearchService(db=db)


@router.post(
    "",
    response_model=Dict[str, Any],
    summary="Advanced booking search",
    description="Search bookings with multiple filters and sorting options.",
    responses={
        200: {"description": "Search results retrieved successfully"},
        400: {"description": "Invalid search criteria"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
    },
)
async def search_bookings(
    payload: BookingSearchRequest,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    admin=Depends(deps.get_admin_user),
    service: BookingSearchService = Depends(get_search_service),
) -> Dict[str, Any]:
    """
    Advanced search for bookings.
    
    Supports filtering by:
    - Hostel ID
    - Status
    - Date ranges
    - Guest information
    - Room type
    - Payment status
    - And more...
    
    Args:
        payload: Search criteria
        skip: Pagination offset
        limit: Maximum records to return
        admin: Admin user performing search
        service: Search service instance
        
    Returns:
        Search results with pagination metadata
        {
            "items": [...],
            "total": int,
            "skip": int,
            "limit": int,
            "has_more": bool
        }
        
    Raises:
        HTTPException: If search fails
    """
    try:
        logger.debug(
            f"Admin {admin.id} performing advanced search",
            extra={
                "admin_id": admin.id,
                "filters": payload.dict(exclude_unset=True),
                "skip": skip,
                "limit": limit,
            },
        )
        
        pagination = {"skip": skip, "limit": limit}
        results = service.search(payload, pagination)
        
        logger.debug(
            f"Search completed: {results.get('total', 0)} total results, "
            f"returning {len(results.get('items', []))} items"
        )
        
        return results
    except ValueError as e:
        logger.warning(f"Invalid search criteria: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error performing search: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform search",
        )


@router.post(
    "/export",
    summary="Export bookings",
    description="Export booking data in various formats (CSV, Excel, PDF).",
    responses={
        200: {
            "description": "Export file generated successfully",
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
                "text/csv": {},
                "application/pdf": {},
            },
        },
        400: {"description": "Invalid export request"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
    },
)
async def export_bookings(
    payload: BookingExportRequest,
    admin=Depends(deps.get_admin_user),
    service: BookingSearchService = Depends(get_search_service),
) -> Response:
    """
    Export booking data.
    
    Args:
        payload: Export request with filters and format
        admin: Admin user requesting export
        service: Search service instance
        
    Returns:
        File response with appropriate content type
        
    Raises:
        HTTPException: If export fails
    """
    try:
        logger.info(
            f"Admin {admin.id} exporting bookings",
            extra={
                "admin_id": admin.id,
                "format": payload.format,
                "filters": payload.filters.dict(exclude_unset=True) if payload.filters else {},
            },
        )
        
        # Generate export file
        export_result = service.export_bookings(payload)
        
        # Determine content type based on format
        content_types = {
            "csv": "text/csv",
            "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "pdf": "application/pdf",
        }
        
        content_type = content_types.get(
            payload.format.lower(),
            "application/octet-stream",
        )
        
        # Generate filename
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        extensions = {"csv": "csv", "excel": "xlsx", "pdf": "pdf"}
        extension = extensions.get(payload.format.lower(), "bin")
        filename = f"bookings_export_{timestamp}.{extension}"
        
        logger.info(f"Export completed: {filename}")
        
        return Response(
            content=export_result,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except ValueError as e:
        logger.warning(f"Invalid export request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error exporting bookings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export bookings",
        )


@router.get(
    "/quick",
    response_model=List[BookingListItem],
    summary="Quick search bookings",
    description="Quick search by booking ID, guest name, or email.",
    responses={
        200: {"description": "Search results retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
    },
)
async def quick_search(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    admin=Depends(deps.get_admin_user),
    service: BookingSearchService = Depends(get_search_service),
) -> List[BookingListItem]:
    """
    Quick search for bookings.
    
    Searches across:
    - Booking ID
    - Guest name
    - Guest email
    - Guest phone
    
    Args:
        q: Search query string
        limit: Maximum number of results
        admin: Admin user performing search
        service: Search service instance
        
    Returns:
        List of matching bookings
        
    Raises:
        HTTPException: If search fails
    """
    try:
        logger.debug(
            f"Admin {admin.id} performing quick search: '{q}'",
            extra={"admin_id": admin.id, "query": q},
        )
        
        results = service.quick_search(q, limit=limit)
        
        logger.debug(f"Quick search returned {len(results)} results")
        return results
    except Exception as e:
        logger.error(f"Error performing quick search: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform quick search",
        )