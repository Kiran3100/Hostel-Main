from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.file_management import (
    DocumentUploadInitRequest,
    DocumentUploadInitResponse,
    DocumentInfo,
    DocumentList,
    DocumentVerificationRequest,
    DocumentVerificationResponse,
    DocumentFilterParams,
)
from app.services.file_management.document_processing_service import (
    DocumentProcessingService,
)

router = APIRouter(prefix="/documents", tags=["files:documents"])


def get_document_service(
    db: Session = Depends(deps.get_db),
) -> DocumentProcessingService:
    return DocumentProcessingService(db=db)


@router.post(
    "/init",
    response_model=DocumentUploadInitResponse,
    summary="Initialize document upload",
)
def init_document_upload(
    payload: DocumentUploadInitRequest,
    current_user=Depends(deps.get_current_user),
    service: DocumentProcessingService = Depends(get_document_service),
) -> Any:
    return service.init_document_upload(payload, user_id=current_user.id)


@router.get(
    "",
    response_model=DocumentList,
    summary="List documents",
)
def list_documents(
    filters: DocumentFilterParams = Depends(DocumentFilterParams),
    current_user=Depends(deps.get_current_user),
    service: DocumentProcessingService = Depends(get_document_service),
) -> Any:
    """
    List documents owned by the current user (or managed users if admin).
    """
    return service.list_documents_for_owner(
        owner_id=current_user.id, filters=filters
    )


@router.get(
    "/{document_id}",
    response_model=DocumentInfo,
    summary="Get document details",
)
def get_document(
    document_id: str,
    current_user=Depends(deps.get_current_user),
    service: DocumentProcessingService = Depends(get_document_service),
) -> Any:
    return service.get_document_info(document_id)


@router.post(
    "/{document_id}/verify",
    response_model=DocumentVerificationResponse,
    summary="Verify document (admin/supervisor)",
)
def verify_document(
    document_id: str,
    payload: DocumentVerificationRequest,
    _staff=Depends(deps.get_current_user_with_roles),  # Ensure staff role
    service: DocumentProcessingService = Depends(get_document_service),
) -> Any:
    return service.verify_document(
        document_id=document_id, payload=payload, verifier_id=_staff.id
    )


@router.post(
    "/{document_id}/archive",
    status_code=status.HTTP_200_OK,
    summary="Archive document",
)
def archive_document(
    document_id: str,
    current_user=Depends(deps.get_current_user),
    service: DocumentProcessingService = Depends(get_document_service),
) -> Any:
    service.archive_document(document_id, user_id=current_user.id)
    return {"detail": "Document archived"}