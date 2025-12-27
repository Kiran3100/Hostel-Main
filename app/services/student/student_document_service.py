# app/services/student/student_document_service.py
"""
Student Document Service

Manages student documents including upload, verification, expiry tracking,
and document lifecycle management.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.student import StudentDocumentRepository
from app.schemas.student import (
    StudentDocuments,
    DocumentInfo,
    DocumentUploadRequest,
    DocumentVerificationRequest,
    StudentDocumentInfo,
)
from app.core1.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)

logger = logging.getLogger(__name__)


class StudentDocumentService:
    """
    High-level service for student document management.

    Responsibilities:
    - Register uploaded documents
    - List and filter documents
    - Verify/reject documents
    - Track document expiry
    - Generate document summaries
    - Handle document lifecycle

    Document types supported:
    - Identity documents (ID, passport, etc.)
    - Educational documents (certificates, transcripts)
    - Medical documents
    - Guardian documents
    - Hostel-specific documents
    """

    def __init__(
        self,
        document_repo: StudentDocumentRepository,
    ) -> None:
        """
        Initialize service with document repository.

        Args:
            document_repo: Repository for document operations
        """
        self.document_repo = document_repo

    # -------------------------------------------------------------------------
    # Document Listing and Views
    # -------------------------------------------------------------------------

    def get_student_documents(
        self,
        db: Session,
        student_id: UUID,
        document_type: Optional[str] = None,
        verified_only: bool = False,
        include_expired: bool = True,
    ) -> StudentDocuments:
        """
        Retrieve comprehensive document set for a student.

        Args:
            db: Database session
            student_id: UUID of student
            document_type: Filter by document type
            verified_only: Only include verified documents
            include_expired: Include expired documents

        Returns:
            StudentDocuments: Complete document set with metadata
        """
        try:
            docs = self.document_repo.get_by_student_id(
                db,
                student_id,
                document_type=document_type,
                verified_only=verified_only,
            )
            
            items = [DocumentInfo.model_validate(d) for d in docs]
            
            # Filter expired if needed
            if not include_expired:
                items = [i for i in items if not i.is_expired]

            # Calculate statistics
            total = len(items)
            verified = sum(1 for i in items if i.is_verified)
            expired = sum(1 for i in items if i.is_expired)
            pending = sum(1 for i in items if not i.is_verified and not i.is_rejected)

            return StudentDocuments(
                student_id=student_id,
                documents=items,
                total_documents=total,
                verified_documents=verified,
                expired_documents=expired,
                pending_documents=pending,
            )

        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving documents for {student_id}: {str(e)}"
            )
            raise BusinessLogicException(
                f"Failed to retrieve documents: {str(e)}"
            ) from e

    def get_document_info(
        self,
        db: Session,
        document_id: UUID,
    ) -> DocumentInfo:
        """
        Retrieve single document information.

        Args:
            db: Database session
            document_id: UUID of document

        Returns:
            DocumentInfo: Document details

        Raises:
            NotFoundException: If document not found
        """
        doc = self.document_repo.get_by_id(db, document_id)
        
        if not doc:
            raise NotFoundException(f"Document not found: {document_id}")
        
        return DocumentInfo.model_validate(doc)

    def get_document_summary_for_student(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentDocumentInfo:
        """
        Get student-centric document summary.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            StudentDocumentInfo: Summary of student documents
        """
        try:
            summary = self.document_repo.get_document_summary(db, student_id)
            return StudentDocumentInfo.model_validate(summary)

        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving document summary for {student_id}: {str(e)}"
            )
            raise BusinessLogicException(
                f"Failed to retrieve document summary: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Document Upload and Registration
    # -------------------------------------------------------------------------

    def register_uploaded_document(
        self,
        db: Session,
        request: DocumentUploadRequest,
        uploaded_by: Optional[UUID] = None,
    ) -> DocumentInfo:
        """
        Register a document after file upload completion.

        Note: File storage is handled separately; this only creates the database record.

        Args:
            db: Database session
            request: Document upload request data
            uploaded_by: UUID of user who uploaded (if different from student)

        Returns:
            DocumentInfo: Registered document

        Raises:
            ValidationException: If validation fails
        """
        # Validate file path exists
        if not request.file_path:
            raise ValidationException("File path is required")

        # Validate document type
        self._validate_document_type(request.document_type)

        try:
            payload = request.model_dump(exclude_none=True)
            payload["uploaded_at"] = datetime.utcnow()
            
            if uploaded_by:
                payload["uploaded_by"] = uploaded_by

            # Set initial verification status
            payload.setdefault("is_verified", False)
            payload.setdefault("is_rejected", False)

            obj = self.document_repo.create(db, payload)
            
            logger.info(
                f"Document registered: {obj.id} for student: {request.student_id}, "
                f"type: {request.document_type}"
            )
            
            return DocumentInfo.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(f"Database error registering document: {str(e)}")
            raise BusinessLogicException(
                f"Failed to register document: {str(e)}"
            ) from e

    def update_document(
        self,
        db: Session,
        document_id: UUID,
        updates: Dict[str, Any],
    ) -> DocumentInfo:
        """
        Update document metadata.

        Args:
            db: Database session
            document_id: UUID of document
            updates: Fields to update

        Returns:
            DocumentInfo: Updated document

        Raises:
            NotFoundException: If document not found
        """
        doc = self.document_repo.get_by_id(db, document_id)
        
        if not doc:
            raise NotFoundException(f"Document not found: {document_id}")

        try:
            obj = self.document_repo.update(db, doc, updates)
            
            logger.info(
                f"Document updated: {document_id}, "
                f"fields: {list(updates.keys())}"
            )
            
            return DocumentInfo.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(f"Database error updating document: {str(e)}")
            raise BusinessLogicException(
                f"Failed to update document: {str(e)}"
            ) from e

    def delete_document(
        self,
        db: Session,
        document_id: UUID,
        soft_delete: bool = True,
    ) -> None:
        """
        Delete a document record.

        Args:
            db: Database session
            document_id: UUID of document
            soft_delete: If True, marks as deleted; if False, permanently removes

        Raises:
            NotFoundException: If document not found
        """
        doc = self.document_repo.get_by_id(db, document_id)
        
        if not doc:
            raise NotFoundException(f"Document not found: {document_id}")

        try:
            if soft_delete:
                self.document_repo.soft_delete(db, doc)
                action = "soft-deleted"
            else:
                self.document_repo.delete(db, doc)
                action = "permanently deleted"

            logger.info(f"Document {action}: {document_id}")

        except SQLAlchemyError as e:
            logger.error(f"Database error deleting document: {str(e)}")
            raise BusinessLogicException(
                f"Failed to delete document: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Document Verification
    # -------------------------------------------------------------------------

    def verify_document(
        self,
        db: Session,
        document_id: UUID,
        request: DocumentVerificationRequest,
        verified_by: UUID,
    ) -> DocumentInfo:
        """
        Verify or reject a document.

        Args:
            db: Database session
            document_id: UUID of document
            request: Verification request data
            verified_by: UUID of verifier

        Returns:
            DocumentInfo: Updated document

        Raises:
            NotFoundException: If document not found
            ValidationException: If document already verified/rejected
        """
        doc = self.document_repo.get_by_id(db, document_id)
        
        if not doc:
            raise NotFoundException(f"Document not found: {document_id}")

        # Check if already processed
        if doc.is_verified and request.verified:
            raise ValidationException("Document is already verified")
        if doc.is_rejected and not request.verified:
            raise ValidationException("Document is already rejected")

        try:
            updated = self.document_repo.verify_document(
                db=db,
                document=doc,
                verified=request.verified,
                verifier_id=verified_by,
                notes=request.notes,
                reject_reason=request.reject_reason,
                corrected_data=request.corrected_fields or {},
            )
            
            status = "verified" if request.verified else "rejected"
            logger.info(
                f"Document {status}: {document_id} by verifier: {verified_by}"
            )
            
            return DocumentInfo.model_validate(updated)

        except SQLAlchemyError as e:
            logger.error(f"Database error verifying document: {str(e)}")
            raise BusinessLogicException(
                f"Failed to verify document: {str(e)}"
            ) from e

    def bulk_verify_documents(
        self,
        db: Session,
        document_ids: List[UUID],
        verified: bool,
        verified_by: UUID,
        notes: Optional[str] = None,
    ) -> int:
        """
        Bulk verify or reject multiple documents.

        Args:
            db: Database session
            document_ids: List of document UUIDs
            verified: True to verify, False to reject
            verified_by: UUID of verifier
            notes: Optional notes for all documents

        Returns:
            Number of documents processed
        """
        if not document_ids:
            return 0

        try:
            count = self.document_repo.bulk_verify(
                db,
                document_ids=document_ids,
                verified=verified,
                verifier_id=verified_by,
                notes=notes,
            )
            
            status = "verified" if verified else "rejected"
            logger.info(
                f"Bulk {status}: {count} documents by verifier: {verified_by}"
            )
            
            return count

        except SQLAlchemyError as e:
            logger.error(f"Database error in bulk verify: {str(e)}")
            raise BusinessLogicException(
                f"Failed to bulk verify documents: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Document Expiry Management
    # -------------------------------------------------------------------------

    def get_expiring_documents(
        self,
        db: Session,
        hostel_id: UUID,
        days_before: int = 30,
    ) -> List[DocumentInfo]:
        """
        Get documents expiring within specified days.

        Args:
            db: Database session
            hostel_id: UUID of hostel
            days_before: Number of days to look ahead

        Returns:
            List of expiring documents
        """
        try:
            docs = self.document_repo.get_expiring_documents(
                db,
                hostel_id=hostel_id,
                days_before=days_before,
            )
            
            return [DocumentInfo.model_validate(d) for d in docs]

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving expiring documents: {str(e)}")
            raise BusinessLogicException(
                f"Failed to retrieve expiring documents: {str(e)}"
            ) from e

    def get_expired_documents(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> List[DocumentInfo]:
        """
        Get all expired documents for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of hostel

        Returns:
            List of expired documents
        """
        try:
            docs = self.document_repo.get_expired_documents(db, hostel_id)
            return [DocumentInfo.model_validate(d) for d in docs]

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving expired documents: {str(e)}")
            raise BusinessLogicException(
                f"Failed to retrieve expired documents: {str(e)}"
            ) from e

    def extend_document_expiry(
        self,
        db: Session,
        document_id: UUID,
        new_expiry_date: date,
        extended_by: UUID,
        reason: Optional[str] = None,
    ) -> DocumentInfo:
        """
        Extend document expiry date.

        Args:
            db: Database session
            document_id: UUID of document
            new_expiry_date: New expiry date
            extended_by: UUID of user extending
            reason: Reason for extension

        Returns:
            DocumentInfo: Updated document

        Raises:
            NotFoundException: If document not found
            ValidationException: If new date is invalid
        """
        doc = self.document_repo.get_by_id(db, document_id)
        
        if not doc:
            raise NotFoundException(f"Document not found: {document_id}")

        # Validate new expiry date
        if new_expiry_date <= date.today():
            raise ValidationException("New expiry date must be in the future")

        try:
            updates = {
                "expiry_date": new_expiry_date,
                "expiry_extended_by": extended_by,
                "expiry_extension_reason": reason,
                "expiry_extended_at": datetime.utcnow(),
            }
            
            updated = self.document_repo.update(db, doc, updates)
            
            logger.info(
                f"Document expiry extended: {document_id} to {new_expiry_date} "
                f"by {extended_by}"
            )
            
            return DocumentInfo.model_validate(updated)

        except SQLAlchemyError as e:
            logger.error(f"Database error extending document expiry: {str(e)}")
            raise BusinessLogicException(
                f"Failed to extend document expiry: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Document Statistics
    # -------------------------------------------------------------------------

    def get_document_statistics(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get comprehensive document statistics for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of hostel

        Returns:
            Dictionary with various statistics
        """
        try:
            stats = self.document_repo.get_document_statistics(db, hostel_id)
            return stats

        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving document statistics: {str(e)}")
            raise BusinessLogicException(
                f"Failed to retrieve document statistics: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_document_type(self, document_type: str) -> None:
        """
        Validate document type against allowed types.

        Args:
            document_type: Type of document

        Raises:
            ValidationException: If type is invalid
        """
        allowed_types = [
            "id_card",
            "passport",
            "birth_certificate",
            "academic_certificate",
            "transcript",
            "medical_report",
            "guardian_id",
            "hostel_agreement",
            "other",
        ]

        if document_type not in allowed_types:
            raise ValidationException(
                f"Invalid document type: {document_type}. "
                f"Allowed types: {', '.join(allowed_types)}"
            )