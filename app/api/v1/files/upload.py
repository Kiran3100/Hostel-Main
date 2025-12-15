from typing import Annotated, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api import deps
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.file.file_upload import (
    FileUploadInitRequest,
    FileUploadInitResponse,
    FileUploadCompleteRequest,
)
from app.schemas.file.file_response import (
    FileInfo,
    FileListResponse,
    FileURL,
)
from app.services.file import FileService

router = APIRouter(prefix="/upload")


def _map_service_error(exc: ServiceError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    if isinstance(exc, ConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


@router.post(
    "/init",
    response_model=FileUploadInitResponse,
    status_code=status.HTTP_200_OK,
    summary="Initialize a generic file upload",
)
async def init_file_upload(
    payload: FileUploadInitRequest,
    file_service: Annotated[FileService, Depends(deps.get_file_service)],
) -> FileUploadInitResponse:
    """
    Initialize a generic file upload (e.g. S3 presigned URL or similar).

    The service returns upload target information and any metadata needed
    by the client to perform the actual upload.
    """
    try:
        return file_service.init_upload(payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.post(
    "/complete",
    response_model=FileInfo,
    status_code=status.HTTP_201_CREATED,
    summary="Mark an upload as completed",
)
async def complete_file_upload(
    payload: FileUploadCompleteRequest,
    file_service: Annotated[FileService, Depends(deps.get_file_service)],
) -> FileInfo:
    """
    Notify the backend that the file has finished uploading.

    The service persists file metadata and returns a FileInfo record.
    """
    try:
        return file_service.complete_upload(payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


# Get file metadata
@router.get(
    "/{file_id}",
    response_model=FileInfo,
    summary="Get file metadata",
)
async def get_file(
    file_service: Annotated[FileService, Depends(deps.get_file_service)],
    file_id: UUID = Path(..., description="File ID"),
) -> FileInfo:
    try:
        return file_service.get_file(file_id=file_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


# List files
@router.get(
    "/",
    response_model=FileListResponse,
    summary="List files",
)
async def list_files(
    file_service: Annotated[FileService, Depends(deps.get_file_service)],
    owner_id: Union[UUID, None] = Query(
        None,
        description="Optional owner/user ID filter",
    ),
    folder: Union[str, None] = Query(
        None,
        description="Optional logical folder/path filter",
    ),
    tag: Union[str, None] = Query(
        None,
        description="Optional tag filter",
    ),
) -> FileListResponse:
    try:
        return file_service.list_files(
            owner_id=owner_id,
            folder=folder,
            tag=tag,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


# Get file URL
@router.get(
    "/{file_id}/url",
    response_model=FileURL,
    summary="Get a file URL",
)
async def get_file_url(
    file_service: Annotated[FileService, Depends(deps.get_file_service)],
    file_id: UUID = Path(..., description="File ID"),
) -> FileURL:
    try:
        return file_service.get_file_url(file_id=file_id)
    except ServiceError as exc:
        raise _map_service_error(exc)