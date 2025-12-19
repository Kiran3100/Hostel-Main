# --- File: student_document_repository.py ---

"""
Student document repository.

Document lifecycle management with verification, compliance,
and automated processing.
"""

from datetime import datetime, timedelta
from typing import Any, Optional
from sqlalchemy import and_, or_, func, case
from sqlalchemy.orm import Session, joinedload

from app.models.student.student_document import StudentDocument
from app.models.student.student import Student


class StudentDocumentRepository:
    """
    Student document repository for comprehensive document management.
    
    Handles:
        - Complete document lifecycle management
        - Automated verification workflows
        - Compliance monitoring and alerts
        - Document renewal tracking
        - Pattern analysis for fraud detection
        - Secure storage and access control
        - Regulatory compliance reporting
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ============================================================================
    # CORE CRUD OPERATIONS
    # ============================================================================

    def create(
        self,
        document_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentDocument:
        """
        Create student document with audit logging.
        
        Args:
            document_data: Document information
            audit_context: Audit context (user_id, ip_address, etc.)
            
        Returns:
            Created document instance
        """
        if audit_context:
            document_data['uploaded_by'] = audit_context.get('user_id')
            document_data['upload_ip_address'] = audit_context.get('ip_address')
        
        document_data['uploaded_at'] = datetime.utcnow()
        document_data['verification_status'] = 'pending'

        document = StudentDocument(**document_data)
        self.db.add(document)
        self.db.flush()
        
        return document

    def find_by_id(
        self,
        document_id: str,
        include_deleted: bool = False,
        eager_load: bool = False
    ) -> Optional[StudentDocument]:
        """
        Find document by ID with optional eager loading.
        
        Args:
            document_id: Document UUID
            include_deleted: Include soft-deleted records
            eager_load: Load related entities
            
        Returns:
            Document instance or None
        """
        query = self.db.query(StudentDocument)
        
        if eager_load:
            query = query.options(
                joinedload(StudentDocument.student),
                joinedload(StudentDocument.uploader),
                joinedload(StudentDocument.verifier)
            )
        
        query = query.filter(StudentDocument.id == document_id)
        
        if not include_deleted:
            query = query.filter(StudentDocument.deleted_at.is_(None))
        
        return query.first()

    def find_by_student_id(
        self,
        student_id: str,
        document_type: Optional[str] = None,
        include_deleted: bool = False,
        verified_only: bool = False
    ) -> list[StudentDocument]:
        """
        Find documents for a student.
        
        Args:
            student_id: Student UUID
            document_type: Filter by document type
            include_deleted: Include soft-deleted records
            verified_only: Return only verified documents
            
        Returns:
            List of documents
        """
        query = self.db.query(StudentDocument).filter(
            StudentDocument.student_id == student_id
        )
        
        if document_type:
            query = query.filter(StudentDocument.document_type == document_type)
        
        if not include_deleted:
            query = query.filter(StudentDocument.deleted_at.is_(None))
        
        if verified_only:
            query = query.filter(StudentDocument.verified == True)
        
        return query.order_by(StudentDocument.uploaded_at.desc()).all()

    def update(
        self,
        document_id: str,
        update_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentDocument]:
        """
        Update document with audit logging.
        
        Args:
            document_id: Document UUID
            update_data: Fields to update
            audit_context: Audit context
            
        Returns:
            Updated document instance or None
        """
        document = self.find_by_id(document_id)
        if not document:
            return None
        
        for key, value in update_data.items():
            if hasattr(document, key):
                setattr(document, key, value)
        
        self.db.flush()
        return document

    def soft_delete(
        self,
        document_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> bool:
        """
        Soft delete document with audit logging.
        
        Args:
            document_id: Document UUID
            audit_context: Audit context
            
        Returns:
            Success status
        """
        document = self.find_by_id(document_id)
        if not document:
            return False
        
        document.deleted_at = datetime.utcnow()
        if audit_context:
            document.deleted_by = audit_context.get('user_id')
        
        self.db.flush()
        return True

    # ============================================================================
    # DOCUMENT VERIFICATION
    # ============================================================================

    def verify_document(
        self,
        document_id: str,
        verified_by: str,
        verification_notes: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentDocument]:
        """
        Mark document as verified.
        
        Args:
            document_id: Document UUID
            verified_by: Admin user ID who verified
            verification_notes: Verification notes
            audit_context: Audit context
            
        Returns:
            Updated document instance or None
        """
        update_data = {
            'verified': True,
            'verified_by': verified_by,
            'verified_at': datetime.utcnow(),
            'verification_status': 'approved',
            'verification_notes': verification_notes
        }
        
        return self.update(document_id, update_data, audit_context)

    def reject_document(
        self,
        document_id: str,
        rejected_by: str,
        rejection_reason: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentDocument]:
        """
        Reject document verification.
        
        Args:
            document_id: Document UUID
            rejected_by: Admin user ID who rejected
            rejection_reason: Reason for rejection
            audit_context: Audit context
            
        Returns:
            Updated document instance or None
        """
        update_data = {
            'verified': False,
            'verified_by': rejected_by,
            'verified_at': datetime.utcnow(),
            'verification_status': 'rejected',
            'rejection_reason': rejection_reason
        }
        
        return self.update(document_id, update_data, audit_context)

    def find_pending_verification(
        self,
        document_type: Optional[str] = None,
        hostel_id: Optional[str] = None,
        days_pending: Optional[int] = None,
        offset: int = 0,
        limit: int = 50
    ) -> list[StudentDocument]:
        """
        Find documents pending verification.
        
        Args:
            document_type: Filter by document type
            hostel_id: Filter by hostel
            days_pending: Filter by days since upload
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of pending documents
        """
        query = self.db.query(StudentDocument).filter(
            and_(
                StudentDocument.verification_status == 'pending',
                StudentDocument.deleted_at.is_(None)
            )
        )
        
        if document_type:
            query = query.filter(StudentDocument.document_type == document_type)
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        if days_pending:
            cutoff_date = datetime.utcnow() - timedelta(days=days_pending)
            query = query.filter(StudentDocument.uploaded_at <= cutoff_date)
        
        return query.order_by(
            StudentDocument.uploaded_at.asc()
        ).offset(offset).limit(limit).all()

    def find_rejected_documents(
        self,
        student_id: Optional[str] = None,
        hostel_id: Optional[str] = None,
        offset: int = 0,
        limit: int = 50
    ) -> list[StudentDocument]:
        """
        Find rejected documents.
        
        Args:
            student_id: Filter by student
            hostel_id: Filter by hostel
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of rejected documents
        """
        query = self.db.query(StudentDocument).filter(
            and_(
                StudentDocument.verification_status == 'rejected',
                StudentDocument.deleted_at.is_(None)
            )
        )
        
        if student_id:
            query = query.filter(StudentDocument.student_id == student_id)
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.offset(offset).limit(limit).all()

    # ============================================================================
    # DOCUMENT EXPIRY MANAGEMENT
    # ============================================================================

    def find_expiring_documents(
        self,
        days_threshold: int = 30,
        hostel_id: Optional[str] = None
    ) -> list[StudentDocument]:
        """
        Find documents expiring within threshold.
        
        Args:
            days_threshold: Days until expiry
            hostel_id: Optional hostel filter
            
        Returns:
            List of expiring documents
        """
        threshold_date = datetime.utcnow() + timedelta(days=days_threshold)
        
        query = self.db.query(StudentDocument).filter(
            and_(
                StudentDocument.expiry_date.isnot(None),
                StudentDocument.expiry_date <= threshold_date,
                StudentDocument.expiry_date >= datetime.utcnow(),
                StudentDocument.is_expired == False,
                StudentDocument.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.order_by(StudentDocument.expiry_date.asc()).all()

    def find_expired_documents(
        self,
        hostel_id: Optional[str] = None,
        notified_only: bool = False
    ) -> list[StudentDocument]:
        """
        Find expired documents.
        
        Args:
            hostel_id: Optional hostel filter
            notified_only: Return only notified documents
            
        Returns:
            List of expired documents
        """
        query = self.db.query(StudentDocument).filter(
            and_(
                StudentDocument.expiry_date.isnot(None),
                StudentDocument.expiry_date < datetime.utcnow(),
                StudentDocument.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        if notified_only:
            query = query.filter(StudentDocument.expiry_notified == True)
        
        return query.all()

    def mark_as_expired(
        self,
        document_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentDocument]:
        """
        Mark document as expired.
        
        Args:
            document_id: Document UUID
            audit_context: Audit context
            
        Returns:
            Updated document instance or None
        """
        update_data = {'is_expired': True}
        return self.update(document_id, update_data, audit_context)

    def mark_expiry_notified(
        self,
        document_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentDocument]:
        """
        Mark expiry notification as sent.
        
        Args:
            document_id: Document UUID
            audit_context: Audit context
            
        Returns:
            Updated document instance or None
        """
        update_data = {'expiry_notified': True}
        return self.update(document_id, update_data, audit_context)

    def process_expired_documents(self) -> int:
        """
        Batch process to mark expired documents.
        
        Returns:
            Number of documents marked as expired
        """
        updated = self.db.query(StudentDocument).filter(
            and_(
                StudentDocument.expiry_date.isnot(None),
                StudentDocument.expiry_date < datetime.utcnow(),
                StudentDocument.is_expired == False,
                StudentDocument.deleted_at.is_(None)
            )
        ).update(
            {'is_expired': True},
            synchronize_session=False
        )
        
        self.db.flush()
        return updated

    # ============================================================================
    # DOCUMENT REPLACEMENT/VERSIONING
    # ============================================================================

    def replace_document(
        self,
        old_document_id: str,
        new_document_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentDocument]:
        """
        Replace document with new version.
        
        Args:
            old_document_id: Old document UUID
            new_document_data: New document information
            audit_context: Audit context
            
        Returns:
            New document instance or None
        """
        old_document = self.find_by_id(old_document_id)
        if not old_document:
            return None
        
        # Set version for new document
        new_document_data['version'] = old_document.version + 1
        new_document_data['replaces'] = old_document_id
        new_document_data['student_id'] = old_document.student_id
        new_document_data['document_type'] = old_document.document_type
        
        # Create new document
        new_document = self.create(new_document_data, audit_context)
        
        # Update old document
        self.update(
            old_document_id,
            {'replaced_by': new_document.id},
            audit_context
        )
        
        return new_document

    def get_document_history(
        self,
        student_id: str,
        document_type: str
    ) -> list[StudentDocument]:
        """
        Get complete version history for a document type.
        
        Args:
            student_id: Student UUID
            document_type: Document type
            
        Returns:
            List of documents ordered by version
        """
        return self.db.query(StudentDocument).filter(
            and_(
                StudentDocument.student_id == student_id,
                StudentDocument.document_type == document_type,
                StudentDocument.deleted_at.is_(None)
            )
        ).order_by(StudentDocument.version.desc()).all()

    def get_current_version(
        self,
        student_id: str,
        document_type: str
    ) -> Optional[StudentDocument]:
        """
        Get current (latest) version of a document.
        
        Args:
            student_id: Student UUID
            document_type: Document type
            
        Returns:
            Current document version or None
        """
        return self.db.query(StudentDocument).filter(
            and_(
                StudentDocument.student_id == student_id,
                StudentDocument.document_type == document_type,
                StudentDocument.replaced_by.is_(None),
                StudentDocument.deleted_at.is_(None)
            )
        ).first()

    # ============================================================================
    # DOCUMENT STATISTICS
    # ============================================================================

    def get_verification_statistics(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Get document verification statistics.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary with verification statistics
        """
        query = self.db.query(StudentDocument).filter(
            StudentDocument.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        total = query.count()
        
        pending = query.filter(
            StudentDocument.verification_status == 'pending'
        ).count()
        
        approved = query.filter(
            StudentDocument.verification_status == 'approved'
        ).count()
        
        rejected = query.filter(
            StudentDocument.verification_status == 'rejected'
        ).count()
        
        verified = query.filter(StudentDocument.verified == True).count()
        
        return {
            'total_documents': total,
            'pending_verification': pending,
            'approved': approved,
            'rejected': rejected,
            'verified': verified,
            'verification_rate': round((verified / total * 100), 2) if total > 0 else 0
        }

    def get_document_type_breakdown(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get count of documents by type.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary mapping document types to counts
        """
        query = self.db.query(
            StudentDocument.document_type,
            func.count(StudentDocument.id).label('count')
        ).filter(StudentDocument.deleted_at.is_(None))
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        query = query.group_by(StudentDocument.document_type)
        
        results = query.all()
        
        return {doc_type: count for doc_type, count in results}

    def get_average_verification_time(
        self,
        document_type: Optional[str] = None,
        hostel_id: Optional[str] = None
    ) -> Optional[float]:
        """
        Calculate average time to verify documents (in hours).
        
        Args:
            document_type: Optional document type filter
            hostel_id: Optional hostel filter
            
        Returns:
            Average verification time in hours or None
        """
        query = self.db.query(StudentDocument).filter(
            and_(
                StudentDocument.verified_at.isnot(None),
                StudentDocument.deleted_at.is_(None)
            )
        )
        
        if document_type:
            query = query.filter(StudentDocument.document_type == document_type)
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        documents = query.all()
        
        if not documents:
            return None
        
        total_hours = sum(
            (doc.verified_at - doc.uploaded_at).total_seconds() / 3600
            for doc in documents
        )
        
        return round(total_hours / len(documents), 2)

    # ============================================================================
    # DOCUMENT ACCESS TRACKING
    # ============================================================================

    def track_download(
        self,
        document_id: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentDocument]:
        """
        Track document download.
        
        Args:
            document_id: Document UUID
            audit_context: Audit context
            
        Returns:
            Updated document instance or None
        """
        document = self.find_by_id(document_id)
        if not document:
            return None
        
        document.download_count += 1
        document.last_downloaded_at = datetime.utcnow()
        
        self.db.flush()
        return document

    def get_most_downloaded_documents(
        self,
        hostel_id: Optional[str] = None,
        limit: int = 10
    ) -> list[StudentDocument]:
        """
        Get most frequently downloaded documents.
        
        Args:
            hostel_id: Optional hostel filter
            limit: Number of documents to return
            
        Returns:
            List of most downloaded documents
        """
        query = self.db.query(StudentDocument).filter(
            StudentDocument.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.order_by(
            StudentDocument.download_count.desc()
        ).limit(limit).all()

    # ============================================================================
    # COMPLIANCE AND AUDIT
    # ============================================================================

    def mark_compliance_checked(
        self,
        document_id: str,
        compliance_status: str,
        audit_notes: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentDocument]:
        """
        Mark document compliance check.
        
        Args:
            document_id: Document UUID
            compliance_status: Compliance status
            audit_notes: Audit notes
            audit_context: Audit context
            
        Returns:
            Updated document instance or None
        """
        update_data = {
            'compliance_checked': True,
            'compliance_status': compliance_status,
            'audit_notes': audit_notes
        }
        
        return self.update(document_id, update_data, audit_context)

    def find_compliance_pending(
        self,
        hostel_id: Optional[str] = None
    ) -> list[StudentDocument]:
        """
        Find documents pending compliance check.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of documents pending compliance
        """
        query = self.db.query(StudentDocument).filter(
            and_(
                StudentDocument.verified == True,
                StudentDocument.compliance_checked == False,
                StudentDocument.deleted_at.is_(None)
            )
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

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
        query = self.db.query(StudentDocument).filter(
            StudentDocument.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        if start_date:
            query = query.filter(StudentDocument.uploaded_at >= start_date)
        
        if end_date:
            query = query.filter(StudentDocument.uploaded_at <= end_date)
        
        total = query.count()
        
        verified = query.filter(StudentDocument.verified == True).count()
        
        compliance_checked = query.filter(
            StudentDocument.compliance_checked == True
        ).count()
        
        compliant = query.filter(
            StudentDocument.compliance_status == 'compliant'
        ).count()
        
        expired = query.filter(StudentDocument.is_expired == True).count()
        
        return {
            'total_documents': total,
            'verified_documents': verified,
            'compliance_checked': compliance_checked,
            'compliant_documents': compliant,
            'expired_documents': expired,
            'verification_rate': round((verified / total * 100), 2) if total > 0 else 0,
            'compliance_rate': round((compliant / compliance_checked * 100), 2) if compliance_checked > 0 else 0
        }

    # ============================================================================
    # SEARCH AND FILTERING
    # ============================================================================

    def search_documents(
        self,
        search_term: str,
        document_type: Optional[str] = None,
        hostel_id: Optional[str] = None,
        verification_status: Optional[str] = None,
        offset: int = 0,
        limit: int = 50
    ) -> list[StudentDocument]:
        """
        Search documents by multiple criteria.
        
        Args:
            search_term: Search term (name, number)
            document_type: Filter by document type
            hostel_id: Filter by hostel
            verification_status: Filter by verification status
            offset: Pagination offset
            limit: Page size
            
        Returns:
            List of matching documents
        """
        query = self.db.query(StudentDocument).filter(
            and_(
                or_(
                    StudentDocument.document_name.ilike(f"%{search_term}%"),
                    StudentDocument.document_number.ilike(f"%{search_term}%"),
                    StudentDocument.file_name.ilike(f"%{search_term}%")
                ),
                StudentDocument.deleted_at.is_(None)
            )
        )
        
        if document_type:
            query = query.filter(StudentDocument.document_type == document_type)
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        if verification_status:
            query = query.filter(
                StudentDocument.verification_status == verification_status
            )
        
        return query.offset(offset).limit(limit).all()

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
            verified_by: Admin user ID who verified
            audit_context: Audit context
            
        Returns:
            Number of documents verified
        """
        updated = self.db.query(StudentDocument).filter(
            and_(
                StudentDocument.id.in_(document_ids),
                StudentDocument.deleted_at.is_(None)
            )
        ).update(
            {
                'verified': True,
                'verified_by': verified_by,
                'verified_at': datetime.utcnow(),
                'verification_status': 'approved'
            },
            synchronize_session=False
        )
        
        self.db.flush()
        return updated

    def bulk_mark_expired(
        self,
        document_ids: list[str],
        audit_context: Optional[dict[str, Any]] = None
    ) -> int:
        """
        Bulk mark documents as expired.
        
        Args:
            document_ids: List of document UUIDs
            audit_context: Audit context
            
        Returns:
            Number of documents marked as expired
        """
        updated = self.db.query(StudentDocument).filter(
            and_(
                StudentDocument.id.in_(document_ids),
                StudentDocument.deleted_at.is_(None)
            )
        ).update(
            {'is_expired': True},
            synchronize_session=False
        )
        
        self.db.flush()
        return updated

    # ============================================================================
    # VALIDATION
    # ============================================================================

    def count_by_student_and_type(
        self,
        student_id: str,
        document_type: str,
        exclude_id: Optional[str] = None
    ) -> int:
        """
        Count documents of a type for a student.
        
        Args:
            student_id: Student UUID
            document_type: Document type
            exclude_id: Document UUID to exclude
            
        Returns:
            Count of documents
        """
        query = self.db.query(func.count(StudentDocument.id)).filter(
            and_(
                StudentDocument.student_id == student_id,
                StudentDocument.document_type == document_type,
                StudentDocument.deleted_at.is_(None)
            )
        )
        
        if exclude_id:
            query = query.filter(StudentDocument.id != exclude_id)
        
        return query.scalar()