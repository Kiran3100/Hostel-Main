"""
Student document service.

Document lifecycle management with verification, compliance,
and automated processing.
"""

from datetime import datetime, timedelta
from typing import Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.student.student_document_repository import StudentDocumentRepository
from app.repositories.student.student_repository import StudentRepository
from app.models.student.student_document import StudentDocument
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    BusinessRuleViolationError
)


class StudentDocumentService:
    """
    Student document service for document lifecycle management.
    
    Handles:
        - Document upload and storage
        - Verification workflows
        - Expiry tracking and notifications
        - Document replacement/versioning
        - Compliance monitoring
        - Access control
    """

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.document_repo = StudentDocumentRepository(db)
        self.student_repo = StudentRepository(db)

    # ============================================================================
    # DOCUMENT UPLOAD AND CREATION
    # ============================================================================

    def upload_document(
        self,
        student_id: str,
        document_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentDocument:
        """
        Upload new document for student.
        
        Args:
            student_id: Student UUID
            document_data: Document information
            audit_context: Audit context
            
        Returns:
            Created document instance
            
        Raises:
            NotFoundError: If student not found
            ValidationError: If validation fails
        """
        try:
            # Validate student exists
            student = self.student_repo.find_by_id(student_id)
            if not student:
                raise NotFoundError(f"Student {student_id} not found")
            
            # Validate required fields
            self._validate_document_data(document_data)
            
            document_data['student_id'] = student_id
            
            # Create document
            document = self.document_repo.create(document_data, audit_context)
            
            self.db.commit()
            
            return document
            
        except (NotFoundError, ValidationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def _validate_document_data(self, document_data: dict[str, Any]) -> None:
        """
        Validate document data.
        
        Args:
            document_data: Document information
            
        Raises:
            ValidationError: If validation fails
        """
        required_fields = ['document_type', 'document_name', 'document_url', 'file_name']
        
        for field in required_fields:
            if field not in document_data or not document_data[field]:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate document type
        valid_types = [
            'id_proof',
            'address_proof',
            'photo',
            'institutional_id',
            'company_id',
            'medical_certificate',
            'police_verification',
            'other'
        ]
        
        if document_data['document_type'] not in valid_types:
            raise ValidationError(
                f"Invalid document type: {document_data['document_type']}"
            )

    # ============================================================================
    # DOCUMENT RETRIEVAL
    # ============================================================================

    def get_document_by_id(
        self,
        document_id: str,
        track_access: bool = False,
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentDocument:
        """
        Get document by ID.
        
        Args:
            document_id: Document UUID
            track_access: Track download/access
            audit_context: Audit context
            
        Returns:
            Document instance
            
        Raises:
            NotFoundError: If document not found
        """
        document = self.document_repo.find_by_id(document_id)
        
        if not document:
            raise NotFoundError(f"Document {document_id} not found")
        
        if track_access:
            self.document_repo.track_download(document_id, audit_context)
            self.db.commit()
        
        return document

    def get_student_documents(
        self,
        student_id: str,
        document_type: Optional[str] = None,
        verified_only: bool = False
    ) -> list[StudentDocument]:
        """
        Get documents for a student.
        
        Args:
            student_id: Student UUID
            document_type: Optional document type filter
            verified_only: Return only verified documents
            
        Returns:
            List of documents
        """
        return self.document_repo.find_by_student_id(
            student_id,
            document_type=document_type,
            verified_only=verified_only
        )

    # ============================================================================
    # DOCUMENT VERIFICATION
    # ============================================================================

    def verify_document(
        self,
        document_id: str,
        verified_by: str,
        verification_notes: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentDocument:
        """
        Verify document.
        
        Args:
            document_id: Document UUID
            verified_by: Admin user ID
            verification_notes: Verification notes
            audit_context: Audit context
            
        Returns:
            Updated document instance
            
        Raises:
            NotFoundError: If document not found
        """
        try:
            document = self.document_repo.verify_document(
                document_id,
                verified_by,
                verification_notes,
                audit_context
            )
            
            if not document:
                raise NotFoundError(f"Document {document_id} not found")
            
            self.db.commit()
            
            return document
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def reject_document(
        self,
        document_id: str,
        rejected_by: str,
        rejection_reason: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentDocument:
        """
        Reject document verification.
        
        Args:
            document_id: Document UUID
            rejected_by: Admin user ID
            rejection_reason: Rejection reason
            audit_context: Audit context
            
        Returns:
            Updated document instance
            
        Raises:
            NotFoundError: If document not found
        """
        try:
            if not rejection_reason:
                raise ValidationError("Rejection reason is required")
            
            document = self.document_repo.reject_document(
                document_id,
                rejected_by,
                rejection_reason,
                audit_context
            )
            
            if not document:
                raise NotFoundError(f"Document {document_id} not found")
            
            self.db.commit()
            
            return document
            
        except (NotFoundError, ValidationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def get_pending_verification(
        self,
        document_type: Optional[str] = None,
        hostel_id: Optional[str] = None,
        days_pending: Optional[int] = None,
        offset: int = 0,
        limit: int = 50
    ) -> list[StudentDocument]:
        """
        Get documents pending verification.
        
        Args:
            document_type: Optional document type filter
            hostel_id: Optional hostel filter
            days_pending: Filter by days since upload
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of pending documents
        """
        return self.document_repo.find_pending_verification(
            document_type,
            hostel_id,
            days_pending,
            offset,
            limit
        )

    # ============================================================================
    # DOCUMENT EXPIRY MANAGEMENT
    # ============================================================================

    def get_expiring_documents(
        self,
        days_threshold: int = 30,
        hostel_id: Optional[str] = None
    ) -> list[StudentDocument]:
        """
        Get documents expiring within threshold.
        
        Args:
            days_threshold: Days until expiry
            hostel_id: Optional hostel filter
            
        Returns:
            List of expiring documents
        """
        return self.document_repo.find_expiring_documents(
            days_threshold,
            hostel_id
        )

    def get_expired_documents(
        self,
        hostel_id: Optional[str] = None
    ) -> list[StudentDocument]:
        """
        Get expired documents.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of expired documents
        """
        return self.document_repo.find_expired_documents(hostel_id)

    def mark_expiry_notified(
        self,
        document_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentDocument:
        """
        Mark expiry notification as sent.
        
        Args:
            document_id: Document UUID
            audit_context: Audit context
            
        Returns:
            Updated document instance
        """
        try:
            document = self.document_repo.mark_expiry_notified(
                document_id,
                audit_context
            )
            
            if not document:
                raise NotFoundError(f"Document {document_id} not found")
            
            self.db.commit()
            
            return document
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def process_expired_documents(self) -> int:
        """
        Batch process to mark expired documents.
        
        Returns:
            Number of documents marked as expired
        """
        try:
            count = self.document_repo.process_expired_documents()
            
            self.db.commit()
            
            return count
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    # ============================================================================
    # DOCUMENT REPLACEMENT
    # ============================================================================

    def replace_document(
        self,
        old_document_id: str,
        new_document_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentDocument:
        """
        Replace document with new version.
        
        Args:
            old_document_id: Old document UUID
            new_document_data: New document information
            audit_context: Audit context
            
        Returns:
            New document instance
            
        Raises:
            NotFoundError: If old document not found
            ValidationError: If validation fails
        """
        try:
            # Validate new document data
            self._validate_document_data(new_document_data)
            
            new_document = self.document_repo.replace_document(
                old_document_id,
                new_document_data,
                audit_context
            )
            
            if not new_document:
                raise NotFoundError(f"Document {old_document_id} not found")
            
            self.db.commit()
            
            return new_document
            
        except (NotFoundError, ValidationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def get_document_history(
        self,
        student_id: str,
        document_type: str
    ) -> list[StudentDocument]:
        """
        Get document version history.
        
        Args:
            student_id: Student UUID
            document_type: Document type
            
        Returns:
            List of document versions
        """
        return self.document_repo.get_document_history(student_id, document_type)

    def get_current_version(
        self,
        student_id: str,
        document_type: str
    ) -> Optional[StudentDocument]:
        """
        Get current version of a document.
        
        Args:
            student_id: Student UUID
            document_type: Document type
            
        Returns:
            Current document version or None
        """
        return self.document_repo.get_current_version(student_id, document_type)

    # ============================================================================
    # COMPLIANCE
    # ============================================================================

    def mark_compliance_checked(
        self,
        document_id: str,
        compliance_status: str,
        audit_notes: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentDocument:
        """
        Mark document compliance check.
        
        Args:
            document_id: Document UUID
            compliance_status: Compliance status
            audit_notes: Audit notes
            audit_context: Audit context
            
        Returns:
            Updated document instance
        """
        try:
            document = self.document_repo.mark_compliance_checked(
                document_id,
                compliance_status,
                audit_notes,
                audit_context
            )
            
            if not document:
                raise NotFoundError(f"Document {document_id} not found")
            
            self.db.commit()
            
            return document
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def get_compliance_pending(
        self,
        hostel_id: Optional[str] = None
    ) -> list[StudentDocument]:
        """
        Get documents pending compliance check.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of documents pending compliance
        """
        return self.document_repo.find_compliance_pending(hostel_id)

    def generate_compliance_report(
        self,
        hostel_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> dict[str, Any]:
        """
        Generate compliance report.
        
        Args:
            hostel_id: Optional hostel filter
            start_date: Report start date
            end_date: Report end date
            
        Returns:
            Compliance report data
        """
        return self.document_repo.generate_compliance_report(
            hostel_id,
            start_date,
            end_date
        )

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def get_verification_statistics(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Get verification statistics.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Verification statistics
        """
        return self.document_repo.get_verification_statistics(hostel_id)

    def get_document_type_breakdown(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get document count by type.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Document type breakdown
        """
        return self.document_repo.get_document_type_breakdown(hostel_id)

    def get_average_verification_time(
        self,
        document_type: Optional[str] = None,
        hostel_id: Optional[str] = None
    ) -> Optional[float]:
        """
        Get average verification time in hours.
        
        Args:
            document_type: Optional document type filter
            hostel_id: Optional hostel filter
            
        Returns:
            Average verification time or None
        """
        return self.document_repo.get_average_verification_time(
            document_type,
            hostel_id
        )

    # ============================================================================
    # BULK OPERATIONS
    # ============================================================================

    def bulk_verify_documents(
        self,
        document_ids: list[str],
        verified_by: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> int:
        """
        Bulk verify documents.
        
        Args:
            document_ids: List of document UUIDs
            verified_by: Admin user ID
            audit_context: Audit context
            
        Returns:
            Number of documents verified
        """
        try:
            count = self.document_repo.bulk_verify_documents(
                document_ids,
                verified_by,
                audit_context
            )
            
            self.db.commit()
            
            return count
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    # ============================================================================
    # DELETE OPERATIONS
    # ============================================================================

    def soft_delete_document(
        self,
        document_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> bool:
        """
        Soft delete document.
        
        Args:
            document_id: Document UUID
            audit_context: Audit context
            
        Returns:
            Success status
        """
        try:
            success = self.document_repo.soft_delete(document_id, audit_context)
            
            if not success:
                raise NotFoundError(f"Document {document_id} not found")
            
            self.db.commit()
            
            return success
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")