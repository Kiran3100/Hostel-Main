"""
Document Management API Endpoints

Handles document-specific operations:
- Document upload and versioning
- Document verification workflow
- Document listing and filtering
- Document archival
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
    DocumentFilterParams,
    DocumentInfo,
    DocumentList,
    DocumentUploadInitRequest,
    DocumentUploadInitResponse,
    DocumentVerificationRequest,
    DocumentVerificationResponse,
)
from app.services.file_management.document_processing_service import (
    DocumentProcessingService,
)

router = APIRouter(prefix="/documents", tags=["files:documents"])


# ============================================================================
# Dependencies
# ============================================================================


def get_document_service(
    db: Session = Depends(deps.get_db),
) -> DocumentProcessingService:
    """
    Dependency injection for DocumentProcessingService.
    
    Args:
        db: Database session
        
    Returns:
        DocumentProcessingService instance
    """
    return DocumentProcessingService(db=db)


# ============================================================================
# Document Upload Endpoints
# ============================================================================


@router.post(
    "/init",
    response_model=DocumentUploadInitResponse,
    status_code=status.HTTP_200_OK,
    summary="Initialize document upload",
    description="Get a pre-signed URL for document upload with metadata configuration.",
    responses={
        200: {
            "description": "Document upload initialized successfully",
            "content": {
                "application/json": {
                    "example": {
                        "upload_url": "https://storage.example.com/...",
                        "document_id": "uuid-here",
                        "expires_in": 3600,
                        "requires_verification": True,
                    }
                }
            },
        },
        400: {"description": "Invalid document parameters"},
        401: {"description": "Not authenticated"},
    },
)
def init_document_upload(
    payload: DocumentUploadInitRequest,
    current_user=Depends(deps.get_current_user),
    service: DocumentProcessingService = Depends(get_document_service),
) -> DocumentUploadInitResponse:
    """
    Initialize a document upload.
    
    Documents differ from regular files in that they:
    - May require verification/approval workflow
    - Support versioning (multiple versions of same document)
    - Include document-specific metadata (type, category, expiry date)
    - May have access control/permissions
    
    Workflow:
    1. Call this endpoint with document metadata
    2. Upload document to the provided pre-signed URL
    3. Document enters pending state if verification required
    4. Admin/supervisor verifies document via /verify endpoint
    
    Args:
        payload: Document upload request with metadata
        current_user: Authenticated user making the request
        service: Document processing service instance
        
    Returns:
        Upload initialization response with document-specific details
    """
    return service.init_document_upload(payload, user_id=current_user.id)


# ============================================================================
# Document Listing and Retrieval Endpoints
# ============================================================================


@router.get(
    "",
    response_model=DocumentList,
    status_code=status.HTTP_200_OK,
    summary="List documents",
    description="List documents owned by the current user with filtering and pagination.",
    responses={
        200: {
            "description": "List of documents",
            "content": {
                "application/json": {
                    "example": {
                        "total": 50,
                        "page": 1,
                        "page_size": 20,
                        "documents": [
                            {
                                "id": "uuid-1",
                                "name": "passport.pdf",
                                "document_type": "identity",
                                "status": "verified",
                                "uploaded_at": "2024-01-15T10:30:00Z",
                            }
                        ],
                    }
                }
            },
        },
        401: {"description": "Not authenticated"},
    },
)
def list_documents(
    filters: DocumentFilterParams = Depends(),
    current_user=Depends(deps.get_current_user),
    service: DocumentProcessingService = Depends(get_document_service),
) -> DocumentList:
    """
    List documents accessible to the current user.
    
    For regular users, returns only their own documents.
    For admins/supervisors, may return documents they manage or verify.
    
    Supports filtering by:
    - Document type (identity, financial, legal, etc.)
    - Verification status (pending, verified, rejected)
    - Date range (uploaded between dates)
    - Search by filename or tags
    
    Results are paginated for performance.
    
    Args:
        filters: Filter and pagination parameters
        current_user: Authenticated user making the request
        service: Document processing service instance
        
    Returns:
        Paginated list of documents with metadata
    """
    return service.list_documents_for_owner(
        owner_id=current_user.id,
        filters=filters,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentInfo,
    status_code=status.HTTP_200_OK,
    summary="Get document details",
    description="Retrieve detailed information about a specific document.",
    responses={
        200: {
            "description": "Document details",
            "content": {
                "application/json": {
                    "example": {
                        "id": "uuid-here",
                        "name": "passport.pdf",
                        "document_type": "identity",
                        "status": "verified",
                        "file_size": 2048576,
                        "uploaded_at": "2024-01-15T10:30:00Z",
                        "verified_at": "2024-01-15T14:20:00Z",
                        "verified_by": "admin-uuid",
                        "download_url": "https://cdn.example.com/...",
                        "metadata": {
                            "document_number": "AB123456",
                            "expiry_date": "2030-01-15",
                        },
                    }
                }
            },
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized to access this document"},
        404: {"description": "Document not found"},
    },
)
def get_document(
    document_id: str,
    current_user=Depends(deps.get_current_user),
    service: DocumentProcessingService = Depends(get_document_service),
) -> DocumentInfo:
    """
    Get detailed information about a document.
    
    Includes:
    - Basic metadata (name, type, size, dates)
    - Verification status and history
    - Download URL (with access control)
    - Custom metadata fields
    - Version information if applicable
    
    Access control:
    - Users can access their own documents
    - Admins/supervisors can access documents they manage
    - Rejected documents may have restricted access
    
    Args:
        document_id: The unique identifier of the document
        current_user: Authenticated user making the request
        service: Document processing service instance
        
    Returns:
        Detailed document information
        
    Raises:
        HTTPException: If document not found or access denied
    """
    return service.get_document_info(
        document_id=document_id,
        requesting_user_id=current_user.id,
    )


# ============================================================================
# Document Verification Endpoints
# ============================================================================


@router.post(
    "/{document_id}/verify",
    response_model=DocumentVerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify document",
    description="Approve or reject a document (admin/supervisor only).",
    responses={
        200: {
            "description": "Document verification recorded",
            "content": {
                "application/json": {
                    "example": {
                        "document_id": "uuid-here",
                        "status": "verified",
                        "verified_by": "admin-uuid",
                        "verified_at": "2024-01-15T14:20:00Z",
                        "verification_notes": "Document approved",
                    }
                }
            },
        },
        400: {"description": "Invalid verification request"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Document not found"},
    },
)
def verify_document(
    document_id: str,
    payload: DocumentVerificationRequest,
    current_staff=Depends(deps.get_current_user_with_roles),
    service: DocumentProcessingService = Depends(get_document_service),
) -> DocumentVerificationResponse:
    """
    Verify (approve or reject) a document.
    
    Verification workflow:
    1. User uploads document (status: pending)
    2. Admin/supervisor reviews document
    3. Admin approves (verified) or rejects (rejected) with notes
    4. User is notified of verification result
    
    Only users with appropriate roles can verify documents:
    - Admin: Can verify all documents
    - Supervisor: Can verify documents in their domain
    
    Verification decisions are logged with:
    - Verifier identity
    - Timestamp
    - Decision (approved/rejected)
    - Notes/comments explaining the decision
    
    Args:
        document_id: The unique identifier of the document
        payload: Verification request with decision and notes
        current_staff: Authenticated staff member with verification permissions
        service: Document processing service instance
        
    Returns:
        Verification response with updated status
        
    Raises:
        HTTPException: If document not found or insufficient permissions
    """
    return service.verify_document(
        document_id=document_id,
        payload=payload,
        verifier_id=current_staff.id,
    )


@router.get(
    "/{document_id}/verification-history",
    status_code=status.HTTP_200_OK,
    summary="Get document verification history",
    description="Retrieve the complete verification history for a document.",
    responses={
        200: {
            "description": "Verification history",
            "content": {
                "application/json": {
                    "example": {
                        "document_id": "uuid-here",
                        "history": [
                            {
                                "status": "verified",
                                "verified_by": "admin-uuid",
                                "verified_at": "2024-01-15T14:20:00Z",
                                "notes": "Approved",
                            },
                            {
                                "status": "pending",
                                "created_at": "2024-01-15T10:30:00Z",
                            },
                        ],
                    }
                }
            },
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized to view history"},
        404: {"description": "Document not found"},
    },
)
def get_verification_history(
    document_id: str,
    current_user=Depends(deps.get_current_user),
    service: DocumentProcessingService = Depends(get_document_service),
) -> dict[str, Any]:
    """
    Get the verification history for a document.
    
    Shows all verification events in chronological order:
    - Initial upload
    - Verification attempts
    - Status changes
    - Notes from verifiers
    
    Args:
        document_id: The unique identifier of the document
        current_user: Authenticated user making the request
        service: Document processing service instance
        
    Returns:
        Dictionary containing verification history
        
    Raises:
        HTTPException: If document not found or access denied
    """
    return service.get_verification_history(
        document_id=document_id,
        requesting_user_id=current_user.id,
    )


# ============================================================================
# Document Management Endpoints
# ============================================================================


@router.post(
    "/{document_id}/archive",
    status_code=status.HTTP_200_OK,
    summary="Archive document",
    description="Archive a document (soft delete - can be restored later).",
    responses={
        200: {
            "description": "Document archived successfully",
            "content": {
                "application/json": {
                    "example": {"detail": "Document archived"}
                }
            },
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized to archive this document"},
        404: {"description": "Document not found"},
    },
)
def archive_document(
    document_id: str,
    current_user=Depends(deps.get_current_user),
    service: DocumentProcessingService = Depends(get_document_service),
) -> dict[str, str]:
    """
    Archive a document.
    
    Archiving is a soft delete that:
    - Removes document from normal listings
    - Preserves document data for compliance/audit
    - Allows restoration if needed
    - Maintains verification history
    
    Archived documents:
    - Don't appear in default document lists
    - Can be retrieved via archive-specific endpoints
    - Maintain all metadata and relationships
    - Can be permanently deleted later by admins
    
    Args:
        document_id: The unique identifier of the document
        current_user: Authenticated user making the request
        service: Document processing service instance
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If document not found or access denied
    """
    service.archive_document(document_id, user_id=current_user.id)
    return {"detail": "Document archived successfully"}


@router.post(
    "/{document_id}/restore",
    status_code=status.HTTP_200_OK,
    summary="Restore archived document",
    description="Restore a previously archived document.",
    responses={
        200: {
            "description": "Document restored successfully",
            "content": {
                "application/json": {
                    "example": {"detail": "Document restored"}
                }
            },
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized to restore this document"},
        404: {"description": "Archived document not found"},
    },
)
def restore_document(
    document_id: str,
    current_user=Depends(deps.get_current_user),
    service: DocumentProcessingService = Depends(get_document_service),
) -> dict[str, str]:
    """
    Restore an archived document.
    
    Makes the document available again in normal listings and operations.
    
    Args:
        document_id: The unique identifier of the document
        current_user: Authenticated user making the request
        service: Document processing service instance
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If document not found or not archived
    """
    service.restore_document(document_id, user_id=current_user.id)
    return {"detail": "Document restored successfully"}


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete document",
    description="Permanently delete a document and all its data (admin only).",
    responses={
        204: {"description": "Document permanently deleted"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Document not found"},
    },
)
def delete_document_permanently(
    document_id: str,
    current_staff=Depends(deps.get_current_user_with_roles),
    service: DocumentProcessingService = Depends(get_document_service),
) -> None:
    """
    Permanently delete a document.
    
    This is a destructive operation that:
    - Removes all document data from storage
    - Deletes all metadata and history
    - Cannot be undone
    - Requires admin privileges
    
    Use with caution. Consider archiving instead for most cases.
    
    Args:
        document_id: The unique identifier of the document
        current_staff: Authenticated staff member with delete permissions
        service: Document processing service instance
        
    Raises:
        HTTPException: If document not found or insufficient permissions
    """
    service.delete_document_permanently(
        document_id=document_id,
        deleter_id=current_staff.id,
    )