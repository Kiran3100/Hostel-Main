"""
Student Documents API Endpoints

Provides endpoints for managing student documents, uploads, and verification.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
    UploadFile,
    File,
    status,
    Body,
    Form,
)

from app.core.dependencies import get_current_user
from app.services.student.student_document_service import StudentDocumentService
from app.schemas.student_document import (
    StudentDocument,
    StudentDocumentCreate,
    StudentDocumentUpdate,
    DocumentType,
    DocumentVerificationStatus,
)
from app.schemas.base import User

router = APIRouter(
    prefix="/students",
    tags=["Students - Documents"],
)


def get_document_service() -> StudentDocumentService:
    """
    Dependency injection for StudentDocumentService.
    
    Returns:
        StudentDocumentService: Instance of the document service
        
    Raises:
        NotImplementedError: To be implemented with actual service instantiation
    """
    raise NotImplementedError("StudentDocumentService dependency not configured")


@router.get(
    "/{student_id}/documents",
    response_model=List[StudentDocument],
    status_code=status.HTTP_200_OK,
    summary="List student documents",
    description="Retrieve all documents associated with a student.",
    responses={
        200: {"description": "Documents retrieved successfully"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden - Insufficient permissions"},
        404: {"description": "Student not found"},
    },
)
async def list_documents(
    student_id: UUID = Path(..., description="Unique student identifier"),
    document_type: Optional[DocumentType] = Query(
        None,
        description="Filter by document type",
    ),
    verification_status: Optional[DocumentVerificationStatus] = Query(
        None,
        description="Filter by verification status",
    ),
    doc_service: StudentDocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
) -> List[StudentDocument]:
    """
    List all documents for a specific student with optional filtering.
    
    Args:
        student_id: UUID of the student
        document_type: Optional filter by document type
        verification_status: Optional filter by verification status
        doc_service: Injected document service
        current_user: Authenticated user from dependency
        
    Returns:
        List[StudentDocument]: List of student documents
    """
    result = doc_service.get_student_documents(
        student_id=str(student_id),
        document_type=document_type.value if document_type else None,
        verification_status=verification_status.value if verification_status else None,
    )
    return result.unwrap()


@router.post(
    "/{student_id}/documents",
    response_model=StudentDocument,
    status_code=status.HTTP_201_CREATED,
    summary="Upload student document",
    description="Upload and register a new document for a student.",
    responses={
        201: {"description": "Document uploaded successfully"},
        400: {"description": "Invalid file or data"},
        401: {"description": "Unauthorized"},
        413: {"description": "File too large"},
    },
)
async def upload_document(
    student_id: UUID = Path(..., description="Unique student identifier"),
    file: UploadFile = File(..., description="Document file to upload"),
    document_type: DocumentType = Form(..., description="Type of document"),
    title: str = Form(..., description="Document title"),
    description: Optional[str] = Form(None, description="Document description"),
    doc_service: StudentDocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
) -> StudentDocument:
    """
    Upload and register a new document for a student.
    
    Supports various document types including:
    - ID proof
    - Academic certificates
    - Medical records
    - Income certificates
    - Other documents
    
    Args:
        student_id: UUID of the student
        file: Uploaded file
        document_type: Type of the document
        title: Document title
        description: Optional description
        doc_service: Injected document service
        current_user: Authenticated user from dependency
        
    Returns:
        StudentDocument: Created document record
    """
    result = doc_service.upload_and_register_document(
        student_id=str(student_id),
        file=file,
        document_type=document_type,
        title=title,
        description=description,
        uploaded_by=current_user.id,
    )
    return result.unwrap()


@router.get(
    "/{student_id}/documents/{document_id}",
    response_model=StudentDocument,
    status_code=status.HTTP_200_OK,
    summary="Get document details",
    description="Retrieve detailed information about a specific document.",
)
async def get_document_detail(
    student_id: UUID = Path(..., description="Unique student identifier"),
    document_id: UUID = Path(..., description="Unique document identifier"),
    doc_service: StudentDocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
) -> StudentDocument:
    """
    Get detailed information about a specific document.
    
    Args:
        student_id: UUID of the student
        document_id: UUID of the document
        doc_service: Injected document service
        current_user: Authenticated user from dependency
        
    Returns:
        StudentDocument: Detailed document information
    """
    result = doc_service.get_document_by_id(
        student_id=str(student_id),
        document_id=str(document_id),
    )
    return result.unwrap()


@router.patch(
    "/{student_id}/documents/{document_id}",
    response_model=StudentDocument,
    status_code=status.HTTP_200_OK,
    summary="Update document metadata",
    description="Update document information (title, description, etc.).",
)
async def update_document(
    student_id: UUID = Path(..., description="Unique student identifier"),
    document_id: UUID = Path(..., description="Unique document identifier"),
    payload: StudentDocumentUpdate = Body(..., description="Document update data"),
    doc_service: StudentDocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
) -> StudentDocument:
    """
    Update document metadata.
    
    Args:
        student_id: UUID of the student
        document_id: UUID of the document
        payload: Update data
        doc_service: Injected document service
        current_user: Authenticated user from dependency
        
    Returns:
        StudentDocument: Updated document information
    """
    result = doc_service.update_document(
        document_id=str(document_id),
        data=payload.dict(exclude_unset=True),
    )
    return result.unwrap()


@router.patch(
    "/{student_id}/documents/{document_id}/verify",
    response_model=StudentDocument,
    status_code=status.HTTP_200_OK,
    summary="Verify student document",
    description="Mark a document as verified or rejected (admin/staff only).",
)
async def verify_document(
    student_id: UUID = Path(..., description="Unique student identifier"),
    document_id: UUID = Path(..., description="Unique document identifier"),
    is_verified: bool = Body(..., embed=True, description="Verification status"),
    verification_notes: Optional[str] = Body(
        None,
        embed=True,
        description="Notes regarding verification",
    ),
    doc_service: StudentDocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
) -> StudentDocument:
    """
    Verify or reject a student document.
    
    This endpoint is typically restricted to admin or staff users.
    
    Args:
        student_id: UUID of the student
        document_id: UUID of the document
        is_verified: True to verify, False to reject
        verification_notes: Optional notes about the verification
        doc_service: Injected document service
        current_user: Authenticated user from dependency
        
    Returns:
        StudentDocument: Updated document with verification status
    """
    result = doc_service.verify_document(
        document_id=str(document_id),
        is_verified=is_verified,
        verified_by=current_user.id,
        notes=verification_notes,
    )
    return result.unwrap()


@router.delete(
    "/{student_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document",
    description="Permanently delete a student document.",
    responses={
        204: {"description": "Document deleted successfully"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden - Cannot delete verified documents"},
        404: {"description": "Document not found"},
    },
)
async def delete_document(
    student_id: UUID = Path(..., description="Unique student identifier"),
    document_id: UUID = Path(..., description="Unique document identifier"),
    doc_service: StudentDocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Delete a student document.
    
    Note: Verified documents may have restrictions on deletion.
    
    Args:
        student_id: UUID of the student
        document_id: UUID of the document
        doc_service: Injected document service
        current_user: Authenticated user from dependency
        
    Returns:
        None: 204 No Content on success
    """
    doc_service.delete_document(
        document_id=str(document_id),
        deleted_by=current_user.id,
    ).unwrap()


@router.get(
    "/{student_id}/documents/{document_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download document file",
    description="Download the actual document file.",
)
async def download_document(
    student_id: UUID = Path(..., description="Unique student identifier"),
    document_id: UUID = Path(..., description="Unique document identifier"),
    doc_service: StudentDocumentService = Depends(get_document_service),
    current_user: User = Depends(get_current_user),
):
    """
    Download the document file.
    
    Returns a streaming response with the document file.
    
    Args:
        student_id: UUID of the student
        document_id: UUID of the document
        doc_service: Injected document service
        current_user: Authenticated user from dependency
        
    Returns:
        StreamingResponse: File download response
    """
    result = doc_service.get_document_download_url(
        document_id=str(document_id),
        student_id=str(student_id),
    )
    return result.unwrap()