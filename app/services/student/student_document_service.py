# app/services/student/student_document_service.py
"""
Student Document Service

Manages student documents: upload registration, listing, verification, and expiry.
"""

from __future__ import annotations

from typing import List
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.student import StudentDocumentRepository
from app.schemas.student import (
    StudentDocuments,
    DocumentInfo,
    DocumentUploadRequest,
    DocumentVerificationRequest,
    StudentDocumentInfo,
)
from app.core.exceptions import ValidationException


class StudentDocumentService:
    """
    High-level service for student documents.

    Responsibilities:
    - Register uploaded documents for a student
    - List documents
    - Verify/reject documents
    - Build document-centric views
    """

    def __init__(
        self,
        document_repo: StudentDocumentRepository,
    ) -> None:
        self.document_repo = document_repo

    # -------------------------------------------------------------------------
    # Listing / views
    # -------------------------------------------------------------------------

    def get_student_documents(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentDocuments:
        """
        Return full document set + counts for a student.
        """
        docs = self.document_repo.get_by_student_id(db, student_id)
        items = [DocumentInfo.model_validate(d) for d in docs]

        total = len(items)
        verified = sum(1 for i in items if i.is_verified)
        expired = sum(1 for i in items if i.is_expired)

        return StudentDocuments(
            student_id=student_id,
            documents=items,
            total_documents=total,
            verified_documents=verified,
            expired_documents=expired,
        )

    def get_document_info(
        self,
        db: Session,
        document_id: UUID,
    ) -> DocumentInfo:
        doc = self.document_repo.get_by_id(db, document_id)
        if not doc:
            raise ValidationException("Document not found")
        return DocumentInfo.model_validate(doc)

    def get_document_summary_for_student(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentDocumentInfo:
        """
        Student-centric summary (as used in StudentDetail).
        """
        summary = self.document_repo.get_document_summary(db, student_id)
        return StudentDocumentInfo.model_validate(summary)

    # -------------------------------------------------------------------------
    # Upload registration
    # -------------------------------------------------------------------------

    def register_uploaded_document(
        self,
        db: Session,
        request: DocumentUploadRequest,
    ) -> DocumentInfo:
        """
        Register a document after file upload has completed.

        File storage is handled elsewhere; this step only associates it with a student.
        """
        payload = request.model_dump(exclude_none=True)
        payload["uploaded_at"] = datetime.utcnow()

        obj = self.document_repo.create(db, payload)
        return DocumentInfo.model_validate(obj)

    # -------------------------------------------------------------------------
    # Verification
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
        """
        doc = self.document_repo.get_by_id(db, document_id)
        if not doc:
            raise ValidationException("Document not found")

        updated = self.document_repo.verify_document(
            db=db,
            document=doc,
            verified=request.verified,
            verifier_id=verified_by,
            notes=request.notes,
            reject_reason=request.reject_reason,
            corrected_data=request.corrected_fields or {},
        )
        return DocumentInfo.model_validate(updated)