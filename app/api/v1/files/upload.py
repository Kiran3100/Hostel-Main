"""
File Upload API Endpoints

Handles various upload strategies:
- Pre-signed URL uploads (recommended for large files)
- Direct server uploads
- Multipart/chunked uploads for very large files
"""

from typing import Any, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.file_management import (
    FileInfo,
    FileUploadCompleteRequest,
    FileUploadCompleteResponse,
    FileUploadInitRequest,
    FileUploadInitResponse,
    MultipartUploadCompleteRequest,
    MultipartUploadInitRequest,
    MultipartUploadPart,
)
from app.services.file_management.file_upload_service import FileUploadService

# Constants
MAX_DIRECT_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB
ALLOWED_FOLDERS = {"uploads", "documents", "images", "temp"}

router = APIRouter(prefix="/upload", tags=["files:upload"])


# ============================================================================
# Dependencies
# ============================================================================


def get_upload_service(db: Session = Depends(deps.get_db)) -> FileUploadService:
    """
    Dependency injection for FileUploadService.
    
    Args:
        db: Database session
        
    Returns:
        FileUploadService instance
    """
    return FileUploadService(db=db)


def validate_folder(folder: str) -> str:
    """
    Validate folder name against allowed values.
    
    Args:
        folder: Folder path to validate
        
    Returns:
        Validated folder name
        
    Raises:
        HTTPException: If folder is not allowed
    """
    if folder not in ALLOWED_FOLDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Folder must be one of: {', '.join(ALLOWED_FOLDERS)}",
        )
    return folder


# ============================================================================
# Pre-signed URL Upload Endpoints
# ============================================================================


@router.post(
    "/init",
    response_model=FileUploadInitResponse,
    status_code=status.HTTP_200_OK,
    summary="Initialize file upload",
    description="Get a pre-signed URL to upload a file directly to storage. "
                "Recommended for files larger than 10MB for better performance.",
    responses={
        200: {
            "description": "Pre-signed URL generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "upload_url": "https://storage.example.com/...",
                        "file_id": "uuid-here",
                        "expires_in": 3600,
                    }
                }
            },
        },
        400: {"description": "Invalid request parameters"},
        401: {"description": "Not authenticated"},
    },
)
def init_upload(
    payload: FileUploadInitRequest,
    current_user=Depends(deps.get_current_user),
    service: FileUploadService = Depends(get_upload_service),
) -> FileUploadInitResponse:
    """
    Initialize a file upload and receive a pre-signed URL.
    
    The client should:
    1. Call this endpoint to get an upload URL
    2. Upload the file directly to the URL using PUT/POST
    3. Call /complete to finalize the upload
    
    Args:
        payload: Upload initialization request with file metadata
        current_user: Authenticated user making the request
        service: File upload service instance
        
    Returns:
        Upload initialization response with pre-signed URL
    """
    return service.init_upload(payload, user_id=current_user.id)


@router.post(
    "/complete",
    response_model=FileUploadCompleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete file upload",
    description="Notify backend that upload is finished so it can verify and finalize the file.",
    responses={
        200: {"description": "Upload completed and verified successfully"},
        400: {"description": "Upload verification failed"},
        401: {"description": "Not authenticated"},
        404: {"description": "Upload session not found"},
    },
)
def complete_upload(
    payload: FileUploadCompleteRequest,
    current_user=Depends(deps.get_current_user),
    service: FileUploadService = Depends(get_upload_service),
) -> FileUploadCompleteResponse:
    """
    Complete and verify a file upload.
    
    This endpoint should be called after the file has been uploaded to the
    pre-signed URL. The backend will verify the upload and update the database.
    
    Args:
        payload: Upload completion request with file ID and checksum
        current_user: Authenticated user making the request
        service: File upload service instance
        
    Returns:
        Upload completion response with file information
    """
    return service.complete_upload(payload, user_id=current_user.id)


# ============================================================================
# Direct Upload Endpoint
# ============================================================================


@router.post(
    "/direct",
    response_model=FileInfo,
    status_code=status.HTTP_201_CREATED,
    summary="Direct file upload to server",
    description=f"Upload file directly to the backend server (max {MAX_DIRECT_UPLOAD_SIZE // (1024 * 1024)}MB). "
                "For larger files, use the pre-signed URL method via /init.",
    responses={
        201: {"description": "File uploaded successfully"},
        400: {"description": "Invalid file or parameters"},
        401: {"description": "Not authenticated"},
        413: {"description": "File too large"},
    },
)
async def direct_upload(
    file: UploadFile = File(..., description="File to upload"),
    folder: str = Form(
        default="uploads",
        description="Destination folder for the file",
    ),
    current_user=Depends(deps.get_current_user),
    service: FileUploadService = Depends(get_upload_service),
    _validation=Depends(deps.validate_file_upload),
) -> FileInfo:
    """
    Upload file directly to the backend server.
    
    The file is streamed to storage without being fully loaded into memory.
    Recommended for files smaller than 100MB. For larger files, use the
    pre-signed URL upload method.
    
    Args:
        file: The file to upload
        folder: Destination folder (must be one of the allowed folders)
        current_user: Authenticated user making the request
        service: File upload service instance
        _validation: File validation dependency (size, type checks)
        
    Returns:
        FileInfo object with upload details
        
    Raises:
        HTTPException: If file is too large or folder is invalid
    """
    # Validate folder
    folder = validate_folder(folder)
    
    # Additional size check for direct uploads
    if file.size and file.size > MAX_DIRECT_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large for direct upload. "
                   f"Maximum size: {MAX_DIRECT_UPLOAD_SIZE // (1024 * 1024)}MB. "
                   f"Use pre-signed URL upload for larger files.",
        )
    
    return await service.handle_direct_upload(
        file=file,
        folder=folder,
        user_id=current_user.id,
    )


# ============================================================================
# Multipart Upload Endpoints
# ============================================================================


@router.post(
    "/multipart/init",
    response_model=MultipartUploadPart,
    status_code=status.HTTP_200_OK,
    summary="Initialize multipart upload",
    description="Start a multipart upload session for very large files (>100MB). "
                "The file will be uploaded in chunks.",
    responses={
        200: {"description": "Multipart upload initialized successfully"},
        400: {"description": "Invalid request parameters"},
        401: {"description": "Not authenticated"},
    },
)
def init_multipart_upload(
    payload: MultipartUploadInitRequest,
    current_user=Depends(deps.get_current_user),
    service: FileUploadService = Depends(get_upload_service),
) -> MultipartUploadPart:
    """
    Initialize a multipart upload session.
    
    For very large files, multipart upload allows:
    - Uploading files in smaller chunks
    - Resuming failed uploads
    - Parallel chunk uploads for faster transfer
    
    The client should:
    1. Call this endpoint to get upload session ID and part URLs
    2. Upload each part to its respective URL
    3. Call /multipart/complete with all part ETags
    
    Args:
        payload: Multipart upload initialization request
        current_user: Authenticated user making the request
        service: File upload service instance
        
    Returns:
        Multipart upload session details with part URLs
    """
    return service.init_multipart(payload, user_id=current_user.id)


@router.post(
    "/multipart/complete",
    response_model=FileUploadCompleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete multipart upload",
    description="Finalize a multipart upload by combining all uploaded parts.",
    responses={
        200: {"description": "Multipart upload completed successfully"},
        400: {"description": "Invalid parts or upload session"},
        401: {"description": "Not authenticated"},
        404: {"description": "Upload session not found"},
    },
)
def complete_multipart_upload(
    payload: MultipartUploadCompleteRequest,
    current_user=Depends(deps.get_current_user),
    service: FileUploadService = Depends(get_upload_service),
) -> FileUploadCompleteResponse:
    """
    Complete a multipart upload session.
    
    This endpoint combines all uploaded parts into a single file and
    verifies the integrity of the upload.
    
    Args:
        payload: Completion request with upload ID and part ETags
        current_user: Authenticated user making the request
        service: File upload service instance
        
    Returns:
        Upload completion response with final file information
    """
    return service.complete_multipart(payload, user_id=current_user.id)


# ============================================================================
# Additional Helper Endpoints
# ============================================================================


@router.delete(
    "/multipart/{upload_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Abort multipart upload",
    description="Cancel an in-progress multipart upload and clean up partial data.",
    responses={
        204: {"description": "Upload aborted successfully"},
        401: {"description": "Not authenticated"},
        404: {"description": "Upload session not found"},
    },
)
def abort_multipart_upload(
    upload_id: str,
    current_user=Depends(deps.get_current_user),
    service: FileUploadService = Depends(get_upload_service),
) -> None:
    """
    Abort an in-progress multipart upload.
    
    This cleans up any partially uploaded data and cancels the upload session.
    
    Args:
        upload_id: The multipart upload session ID
        current_user: Authenticated user making the request
        service: File upload service instance
    """
    service.abort_multipart(upload_id, user_id=current_user.id)