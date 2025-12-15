# api/v1/files/images.py
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.api import deps
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.file.image_upload import (
    ImageUploadInitRequest,
    ImageUploadInitResponse,
    ImageProcessingResult,
)
from app.schemas.file.file_response import FileInfo
from app.services.file import ImageService

router = APIRouter(prefix="/images")


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
    response_model=ImageUploadInitResponse,
    status_code=status.HTTP_200_OK,
    summary="Initialize an image upload",
)
async def init_image_upload(
    payload: ImageUploadInitRequest,
    image_service: Annotated[ImageService, Depends(deps.get_image_service)],
) -> ImageUploadInitResponse:
    """
    Initialize an image upload, specifying constraints and usage context.

    Service typically returns upload targets and planned variants.
    """
    try:
        return image_service.init_upload(payload)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{image_id}",
    response_model=FileInfo,
    summary="Get image file metadata",
)
async def get_image_info(
    image_service: Annotated[ImageService, Depends(deps.get_image_service)],
    image_id: UUID = Path(..., description="Image file ID"),
) -> FileInfo:
    try:
        return image_service.get_image(image_id=image_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{image_id}/processing",
    response_model=ImageProcessingResult,
    summary="Get image processing/variants information",
)
async def get_image_processing_result(
    image_service: Annotated[ImageService, Depends(deps.get_image_service)],
    image_id: UUID = Path(..., description="Image file ID"),
) -> ImageProcessingResult:
    try:
        return image_service.get_processing_result(image_id=image_id)
    except ServiceError as exc:
        raise _map_service_error(exc)
        raise _map_service_error(exc)