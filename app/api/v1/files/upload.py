from typing import Any

from fastapi import APIRouter, Depends, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.file_management import (
    FileUploadInitRequest,
    FileUploadInitResponse,
    FileUploadCompleteRequest,
    FileUploadCompleteResponse,
    MultipartUploadInitRequest,
    MultipartUploadPart,
    MultipartUploadCompleteRequest,
    FileInfo,
)
from app.services.file_management.file_upload_service import FileUploadService

router = APIRouter(prefix="/upload", tags=["files:upload"])


def get_upload_service(db: Session = Depends(deps.get_db)) -> FileUploadService:
    return FileUploadService(db=db)


@router.post(
    "/init",
    response_model=FileUploadInitResponse,
    summary="Initialize file upload (pre-signed URL)",
)
def init_upload(
    payload: FileUploadInitRequest,
    current_user=Depends(deps.get_current_user),
    service: FileUploadService = Depends(get_upload_service),
) -> Any:
    """
    Get a pre-signed URL to upload a file directly to storage.
    """
    return service.init_upload(payload, user_id=current_user.id)


@router.post(
    "/complete",
    response_model=FileUploadCompleteResponse,
    summary="Complete file upload",
)
def complete_upload(
    payload: FileUploadCompleteRequest,
    current_user=Depends(deps.get_current_user),
    service: FileUploadService = Depends(get_upload_service),
) -> Any:
    """
    Notify backend that upload is finished so it can verify and finalize.
    """
    return service.complete_upload(payload, user_id=current_user.id)


# ---------------------------------------------------------------------------
# Direct upload (if supporting direct POST to backend instead of pre-signed)
# ---------------------------------------------------------------------------


@router.post(
    "/direct",
    response_model=FileInfo,
    status_code=status.HTTP_201_CREATED,
    summary="Direct file upload to server",
)
async def direct_upload(
    file: UploadFile = File(...),
    # Optional metadata if needed, e.g. folder, tags
    folder: str = Form("uploads"), 
    current_user=Depends(deps.get_current_user),
    service: FileUploadService = Depends(get_upload_service),
    # Use validate_file_upload dependency if you want size/type checks here
    _validation=Depends(deps.validate_file_upload),
) -> Any:
    """
    Upload file directly to the backend server (streamed to storage).
    """
    # Service should handle reading the stream and pushing to storage
    return await service.handle_direct_upload(
        file=file, folder=folder, user_id=current_user.id
    )


# ---------------------------------------------------------------------------
# Multipart / Chunked Uploads
# ---------------------------------------------------------------------------


@router.post(
    "/multipart/init",
    response_model=MultipartUploadPart,  # or a list of parts / upload ID
    summary="Initialize multipart upload",
)
def init_multipart_upload(
    payload: MultipartUploadInitRequest,
    current_user=Depends(deps.get_current_user),
    service: FileUploadService = Depends(get_upload_service),
) -> Any:
    return service.init_multipart(payload, user_id=current_user.id)


@router.post(
    "/multipart/complete",
    response_model=FileUploadCompleteResponse,
    summary="Complete multipart upload",
)
def complete_multipart_upload(
    payload: MultipartUploadCompleteRequest,
    current_user=Depends(deps.get_current_user),
    service: FileUploadService = Depends(get_upload_service),
) -> Any:
    return service.complete_multipart(payload, user_id=current_user.id)