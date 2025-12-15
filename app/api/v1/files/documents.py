# api/v1/files/documents.py
from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api import deps
from app.core.exceptions import (
    ServiceError,
    NotFoundError,
    ValidationError,
    ConflictError,
)
from app.schemas.file.document_upload import (
    DocumentUploadInitRequest,
    DocumentUploadInitResponse,
    DocumentValidationResult,
    DocumentInfo,
    DocumentList,
)
from app.services.file import DocumentService

router = APIRouter(prefix="/documents")


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
    "/{document_id}/validate",
    response_model=DocumentValidationResult,
    status_code=status.HTTP_200_OK,
    summary="Validate an uploaded document",
)
async def validate_document(
    document_service: Annotated[DocumentService, Depends(deps.get_document_service)],
    document_id: UUID = Path(..., description="Document ID"),
) -> DocumentValidationResult:
    try:
        return document_service.validate_document(document_id=document_id)
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/",
    response_model=DocumentList,
    summary="List documents",
)
async def list_documents(
    document_service: Annotated[DocumentService, Depends(deps.get_document_service)],
    owner_id: Optional[UUID] = Query(
        None,
        description="Optional owner/user ID filter",
    ),
    hostel_id: Optional[UUID] = Query(
        None,
        description="Optional hostel filter",
    ),
    doc_type: Optional[str] = Query(
        None,
        description="Optional document type filter",
    ),
) -> DocumentList:
    try:
        return document_service.list_documents(
            owner_id=owner_id,
            hostel_id=hostel_id,
            doc_type=doc_type,
        )
    except ServiceError as exc:
        raise _map_service_error(exc)


@router.get(
    "/{document_id}",
    response_model=DocumentInfo,
    summary="Get document details",
)
async def get_document(
    document_service: Annotated[DocumentService, Depends(deps.get_document_service)],
    document_id: UUID = Path(..., description="Document ID"),
) -> DocumentInfo:
    try:
        return document_service.get_document(document_id=document_id)
    except ServiceError as exc:
        raise _map_service_error(exc)