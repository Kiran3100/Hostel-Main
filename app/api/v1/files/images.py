"""
Image Processing API Endpoints

Handles image-specific operations:
- Image upload with processing options
- Automatic resizing and optimization
- Variant generation (thumbnails, different sizes)
"""

from typing import Any, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.file_management import (
    ImageProcessingResult,
    ImageUploadInitRequest,
    ImageUploadInitResponse,
    ImageVariant,
)
from app.services.file_management.image_processing_service import ImageProcessingService

router = APIRouter(prefix="/images", tags=["files:images"])


# ============================================================================
# Dependencies
# ============================================================================


def get_image_service(db: Session = Depends(deps.get_db)) -> ImageProcessingService:
    """
    Dependency injection for ImageProcessingService.
    
    Args:
        db: Database session
        
    Returns:
        ImageProcessingService instance
    """
    return ImageProcessingService(db=db)


# ============================================================================
# Image Upload Endpoints
# ============================================================================


@router.post(
    "/init",
    response_model=ImageUploadInitResponse,
    status_code=status.HTTP_200_OK,
    summary="Initialize image upload with processing options",
    description="Get a pre-signed URL for image upload and configure automatic processing options.",
    responses={
        200: {
            "description": "Image upload initialized successfully",
            "content": {
                "application/json": {
                    "example": {
                        "upload_url": "https://storage.example.com/...",
                        "file_id": "uuid-here",
                        "processing_options": {
                            "auto_optimize": True,
                            "generate_thumbnails": True,
                            "max_dimension": 2048,
                        },
                    }
                }
            },
        },
        400: {"description": "Invalid image parameters"},
        401: {"description": "Not authenticated"},
    },
)
def init_image_upload(
    payload: ImageUploadInitRequest,
    current_user=Depends(deps.get_current_user),
    service: ImageProcessingService = Depends(get_image_service),
) -> ImageUploadInitResponse:
    """
    Initialize an image upload with processing configuration.
    
    This endpoint is similar to the general file upload initialization but
    includes image-specific processing options:
    - Automatic optimization (compression, format conversion)
    - Thumbnail generation
    - Multiple size variants
    - Metadata extraction (dimensions, EXIF data)
    
    Workflow:
    1. Call this endpoint with desired processing options
    2. Upload the image to the provided pre-signed URL
    3. Backend automatically processes the image
    4. Use /process endpoint to manually trigger processing if needed
    
    Args:
        payload: Image upload request with processing options
        current_user: Authenticated user making the request
        service: Image processing service instance
        
    Returns:
        Upload initialization response with image-specific details
    """
    return service.init_image_upload(payload, user_id=current_user.id)


# ============================================================================
# Image Processing Endpoints
# ============================================================================


@router.post(
    "/{file_id}/process",
    response_model=ImageProcessingResult,
    status_code=status.HTTP_200_OK,
    summary="Trigger image processing",
    description="Manually trigger image processing (resize, optimize, generate variants). "
                "Usually automatic after upload, but can be re-run if needed.",
    responses={
        200: {
            "description": "Image processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "file_id": "uuid-here",
                        "status": "completed",
                        "variants_generated": 3,
                        "original_size": 5242880,
                        "optimized_size": 1048576,
                        "compression_ratio": 0.2,
                    }
                }
            },
        },
        400: {"description": "Processing failed or invalid file type"},
        401: {"description": "Not authenticated"},
        404: {"description": "Image not found"},
    },
)
def process_image(
    file_id: str,
    reprocess: bool = Query(
        default=False,
        description="Force reprocessing even if already processed",
    ),
    current_user=Depends(deps.get_current_user),
    service: ImageProcessingService = Depends(get_image_service),
) -> ImageProcessingResult:
    """
    Process an uploaded image.
    
    Processing includes:
    - Image optimization (compression, format conversion)
    - Resizing to maximum dimensions
    - Thumbnail generation
    - Variant creation for responsive images
    - Metadata extraction
    
    Processing is usually triggered automatically after upload, but this
    endpoint allows manual triggering in cases like:
    - Initial processing failed
    - Different processing options needed
    - Re-optimizing with updated algorithms
    
    Args:
        file_id: The unique identifier of the image file
        reprocess: Whether to force reprocessing even if already done
        current_user: Authenticated user making the request
        service: Image processing service instance
        
    Returns:
        Processing result with generated variants and statistics
        
    Raises:
        HTTPException: If file is not found or not an image
    """
    return service.process_image(
        file_id=file_id,
        user_id=current_user.id,
        force_reprocess=reprocess,
    )


@router.get(
    "/{file_id}/variants",
    response_model=List[ImageVariant],
    status_code=status.HTTP_200_OK,
    summary="List image variants",
    description="Get all generated variants (thumbnails, different sizes) for an image.",
    responses={
        200: {
            "description": "List of image variants",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "variant_type": "thumbnail",
                            "url": "https://cdn.example.com/thumb.jpg",
                            "width": 150,
                            "height": 150,
                            "size": 10240,
                        },
                        {
                            "variant_type": "medium",
                            "url": "https://cdn.example.com/medium.jpg",
                            "width": 800,
                            "height": 600,
                            "size": 102400,
                        },
                    ]
                }
            },
        },
        401: {"description": "Not authenticated"},
        404: {"description": "Image not found"},
    },
)
def list_image_variants(
    file_id: str,
    variant_type: Optional[str] = Query(
        default=None,
        description="Filter by variant type (thumbnail, small, medium, large, original)",
    ),
    current_user=Depends(deps.get_current_user),
    service: ImageProcessingService = Depends(get_image_service),
) -> List[ImageVariant]:
    """
    List all generated variants for an image.
    
    Variants are different sizes/formats of the same image, typically:
    - thumbnail: Small preview (e.g., 150x150)
    - small: Mobile-friendly size (e.g., 480px wide)
    - medium: Tablet-friendly size (e.g., 800px wide)
    - large: Desktop size (e.g., 1920px wide)
    - original: Unmodified uploaded image
    
    Each variant includes:
    - Direct URL for accessing the image
    - Dimensions (width, height)
    - File size in bytes
    - Format (JPEG, PNG, WebP, etc.)
    
    Args:
        file_id: The unique identifier of the image file
        variant_type: Optional filter for specific variant type
        current_user: Authenticated user making the request
        service: Image processing service instance
        
    Returns:
        List of image variants with URLs and metadata
        
    Raises:
        HTTPException: If image is not found
    """
    return service.list_variants(
        file_id=file_id,
        variant_type=variant_type,
    )


# ============================================================================
# Image Metadata Endpoints
# ============================================================================


@router.get(
    "/{file_id}/metadata",
    status_code=status.HTTP_200_OK,
    summary="Get image metadata",
    description="Retrieve detailed metadata about an image (dimensions, EXIF, color profile, etc.).",
    responses={
        200: {
            "description": "Image metadata",
            "content": {
                "application/json": {
                    "example": {
                        "width": 1920,
                        "height": 1080,
                        "format": "JPEG",
                        "color_mode": "RGB",
                        "has_alpha": False,
                        "exif": {
                            "camera_make": "Canon",
                            "camera_model": "EOS R5",
                            "datetime_original": "2024-01-15T10:30:00Z",
                        },
                    }
                }
            },
        },
        401: {"description": "Not authenticated"},
        404: {"description": "Image not found"},
    },
)
def get_image_metadata(
    file_id: str,
    current_user=Depends(deps.get_current_user),
    service: ImageProcessingService = Depends(get_image_service),
) -> dict[str, Any]:
    """
    Get detailed metadata for an image.
    
    Metadata includes:
    - Basic info: dimensions, format, file size
    - Color information: color mode, bit depth, has transparency
    - EXIF data: camera info, GPS, timestamps (if available)
    - Processing history: optimization applied, variants generated
    
    Args:
        file_id: The unique identifier of the image file
        current_user: Authenticated user making the request
        service: Image processing service instance
        
    Returns:
        Dictionary containing image metadata
        
    Raises:
        HTTPException: If image is not found
    """
    return service.get_image_metadata(file_id)


@router.delete(
    "/{file_id}/variants/{variant_type}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete specific image variant",
    description="Delete a specific variant of an image (e.g., regenerate thumbnail).",
    responses={
        204: {"description": "Variant deleted successfully"},
        401: {"description": "Not authenticated"},
        404: {"description": "Image or variant not found"},
    },
)
def delete_image_variant(
    file_id: str,
    variant_type: str,
    current_user=Depends(deps.get_current_user),
    service: ImageProcessingService = Depends(get_image_service),
) -> None:
    """
    Delete a specific variant of an image.
    
    Useful when you want to regenerate a specific size or fix issues
    with a particular variant without affecting other sizes.
    
    Args:
        file_id: The unique identifier of the image file
        variant_type: Type of variant to delete (thumbnail, small, medium, large)
        current_user: Authenticated user making the request
        service: Image processing service instance
        
    Raises:
        HTTPException: If image or variant is not found
    """
    service.delete_variant(
        file_id=file_id,
        variant_type=variant_type,
        user_id=current_user.id,
    )