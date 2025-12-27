"""
Hostel Media Management API Endpoints
Handles upload, retrieval, and deletion of hostel media (images, videos, documents)
"""
from typing import Any, List
from enum import Enum

from fastapi import (
    APIRouter,
    Depends,
    status,
    Query,
    Path,
    HTTPException,
    UploadFile,
    File,
)
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.hostel.hostel_media import (
    MediaAdd,
    MediaResponse,
    MediaUpdate,
    MediaType,
)
from app.services.hostel.hostel_media_service import HostelMediaService
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/hostels/media", tags=["hostels:media"])


def get_media_service(db: Session = Depends(deps.get_db)) -> HostelMediaService:
    """
    Dependency to get hostel media service instance
    
    Args:
        db: Database session
        
    Returns:
        HostelMediaService instance
    """
    return HostelMediaService(db=db)


@router.post(
    "",
    response_model=MediaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add media to hostel",
    description="Upload media files (images, videos, documents) for a hostel",
    responses={
        201: {"description": "Media uploaded successfully"},
        400: {"description": "Invalid file or parameters"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        413: {"description": "File too large"},
    },
)
async def add_media(
    hostel_id: str = Query(
        ...,
        description="ID of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    file: UploadFile = File(..., description="Media file to upload"),
    media_type: MediaType = Query(
        ...,
        description="Type of media being uploaded"
    ),
    title: str | None = Query(
        None,
        description="Title/caption for the media",
        max_length=200
    ),
    description: str | None = Query(
        None,
        description="Description of the media",
        max_length=500
    ),
    is_primary: bool = Query(
        False,
        description="Set as primary/featured image"
    ),
    display_order: int | None = Query(
        None,
        description="Display order position",
        ge=0
    ),
    admin=Depends(deps.get_admin_user),
    service: HostelMediaService = Depends(get_media_service),
) -> MediaResponse:
    """
    Upload media file for a hostel.
    
    Supported file types:
    - Images: JPG, PNG, WebP (max 10MB)
    - Videos: MP4, WebM (max 100MB)
    - Documents: PDF (max 5MB)
    
    Args:
        hostel_id: The hostel identifier
        file: The file to upload
        media_type: Type of media
        title: Optional title
        description: Optional description
        is_primary: Set as featured image
        display_order: Display position
        admin: Current admin user
        service: Media service instance
        
    Returns:
        Uploaded media details
        
    Raises:
        HTTPException: If upload fails or file invalid
    """
    try:
        logger.info(
            f"Admin {admin.id} uploading {media_type} media for hostel {hostel_id}"
        )
        
        # Validate file size
        file_size = 0
        chunk_size = 1024 * 1024  # 1MB chunks
        max_size = {
            MediaType.IMAGE: 10 * 1024 * 1024,  # 10MB
            MediaType.VIDEO: 100 * 1024 * 1024,  # 100MB
            MediaType.DOCUMENT: 5 * 1024 * 1024,  # 5MB
        }
        
        # Read file in chunks to calculate size
        contents = await file.read()
        file_size = len(contents)
        
        if file_size > max_size.get(media_type, 10 * 1024 * 1024):
            raise ValueError(
                f"File size exceeds maximum allowed for {media_type}"
            )
        
        # Reset file position
        await file.seek(0)
        
        payload = MediaAdd(
            hostel_id=hostel_id,
            media_type=media_type,
            title=title,
            description=description,
            is_primary=is_primary,
            display_order=display_order,
            file_size=file_size,
            file_name=file.filename,
            content_type=file.content_type,
        )
        
        media = await service.add_media(
            payload=payload,
            file_content=contents
        )
        
        logger.info(f"Media {media.id} uploaded successfully")
        return media
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error uploading media: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload media"
        )


@router.get(
    "",
    response_model=List[MediaResponse],
    summary="List hostel media",
    description="Retrieve all media for a specific hostel",
    responses={
        200: {"description": "Media list retrieved successfully"},
        404: {"description": "Hostel not found"},
    },
)
def list_media(
    hostel_id: str = Query(
        ...,
        description="ID of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    media_type: MediaType | None = Query(
        None,
        description="Filter by media type"
    ),
    include_archived: bool = Query(
        False,
        description="Include archived media"
    ),
    service: HostelMediaService = Depends(get_media_service),
) -> List[MediaResponse]:
    """
    List all media for a hostel.
    
    Args:
        hostel_id: The hostel identifier
        media_type: Optional type filter
        include_archived: Whether to include archived media
        service: Media service instance
        
    Returns:
        List of media items
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        media_list = service.list_media(
            hostel_id=hostel_id,
            media_type=media_type,
            include_archived=include_archived
        )
        
        logger.info(f"Retrieved {len(media_list)} media items for hostel {hostel_id}")
        return media_list
        
    except Exception as e:
        logger.error(f"Error listing media: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve media"
        )


@router.get(
    "/{media_id}",
    response_model=MediaResponse,
    summary="Get media details",
    description="Retrieve detailed information about a specific media item",
    responses={
        200: {"description": "Media details retrieved successfully"},
        404: {"description": "Media not found"},
    },
)
def get_media(
    media_id: str = Path(
        ...,
        description="ID of the media item",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    service: HostelMediaService = Depends(get_media_service),
) -> MediaResponse:
    """
    Get media item details.
    
    Args:
        media_id: The media identifier
        service: Media service instance
        
    Returns:
        Media details
        
    Raises:
        HTTPException: If media not found
    """
    media = service.get_media(media_id)
    
    if not media:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media not found"
        )
    
    return media


@router.patch(
    "/{media_id}",
    response_model=MediaResponse,
    summary="Update media details",
    description="Update metadata for a media item",
    responses={
        200: {"description": "Media updated successfully"},
        400: {"description": "Invalid update data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Media not found"},
    },
)
def update_media(
    media_id: str = Path(
        ...,
        description="ID of the media item",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    payload: MediaUpdate = ...,
    admin=Depends(deps.get_admin_user),
    service: HostelMediaService = Depends(get_media_service),
) -> MediaResponse:
    """
    Update media metadata.
    
    Args:
        media_id: The media identifier
        payload: Updated media data
        admin: Current admin user
        service: Media service instance
        
    Returns:
        Updated media details
    """
    try:
        logger.info(f"Admin {admin.id} updating media {media_id}")
        
        updated_media = service.update_media(media_id, payload)
        
        if not updated_media:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media not found"
            )
        
        logger.info(f"Media {media_id} updated successfully")
        return updated_media
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating media: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update media"
        )


@router.delete(
    "/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete media",
    description="Delete a media item from a hostel",
    responses={
        204: {"description": "Media deleted successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Media not found"},
    },
)
def delete_media(
    media_id: str = Path(
        ...,
        description="ID of the media item to delete",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    permanent: bool = Query(
        False,
        description="Permanently delete (default is soft delete)"
    ),
    admin=Depends(deps.get_admin_user),
    service: HostelMediaService = Depends(get_media_service),
) -> None:
    """
    Delete a media item.
    
    Args:
        media_id: The media identifier
        permanent: Whether to permanently delete
        admin: Current admin user
        service: Media service instance
        
    Raises:
        HTTPException: If media not found or deletion fails
    """
    try:
        logger.info(
            f"Admin {admin.id} deleting media {media_id} "
            f"(permanent={permanent})"
        )
        
        success = service.delete_media(media_id, permanent=permanent)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media not found"
            )
        
        logger.info(f"Media {media_id} deleted successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting media: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete media"
        )


@router.post(
    "/{media_id}/reorder",
    response_model=MediaResponse,
    summary="Reorder media",
    description="Update the display order of a media item",
    responses={
        200: {"description": "Media reordered successfully"},
        400: {"description": "Invalid order position"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Media not found"},
    },
)
def reorder_media(
    media_id: str = Path(
        ...,
        description="ID of the media item",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    new_order: int = Query(
        ...,
        description="New display order position",
        ge=0
    ),
    admin=Depends(deps.get_admin_user),
    service: HostelMediaService = Depends(get_media_service),
) -> MediaResponse:
    """
    Update media display order.
    
    Args:
        media_id: The media identifier
        new_order: New position in display order
        admin: Current admin user
        service: Media service instance
        
    Returns:
        Updated media details
    """
    try:
        logger.info(f"Admin {admin.id} reordering media {media_id} to {new_order}")
        
        updated_media = service.reorder_media(media_id, new_order)
        
        if not updated_media:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media not found"
            )
        
        logger.info(f"Media {media_id} reordered successfully")
        return updated_media
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error reordering media: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reorder media"
        )