"""
Document Upload Repository

Document-specific operations with OCR processing, verification workflows,
and expiry tracking.
"""

from datetime import datetime, timedelta, date as Date
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import and_, or_, func, desc, asc, case
from sqlalchemy.orm import Session, joinedload, selectinload

from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.pagination import PaginationManager, PaginatedResult
from app.models.file_management.document_upload import (
    DocumentUpload,
    DocumentType,
    DocumentValidation,
    DocumentOCR,
    DocumentVerification,
    DocumentExpiry,
)
from app.models.file_management.file_upload import FileUpload
from app.models.user.user import User
from app.models.student.student import Student


class DocumentUploadRepository(BaseRepository[DocumentUpload]):
    """
    Repository for document upload operations with OCR, verification,
    and compliance tracking.
    """

    def __init__(self, db_session: Session):
        super().__init__(DocumentUpload, db_session)

    # ============================================================================
    # CORE DOCUMENT OPERATIONS
    # ============================================================================

    async def create_document_upload(
        self,
        file_id: str,
        document_data: Dict[str, Any],
        uploaded_by_user_id: str,
        audit_context: Optional[Dict[str, Any]] = None,
    ) -> DocumentUpload:
        """
        Create document upload with validation and processing setup.

        Args:
            file_id: Associated file upload ID
            document_data: Document metadata
            uploaded_by_user_id: User uploading the document
            audit_context: Audit context

        Returns:
            Created DocumentUpload

        Raises:
            ValidationException: If document data is invalid
        """
        # Validate document type exists
        doc_type = await self.get_document_type(document_data["document_type"])
        if not doc_type:
            raise ValueError(f"Invalid document type: {document_data['document_type']}")

        document = DocumentUpload(
            file_id=file_id,
            document_id=document_data["document_id"],
            document_type=document_data["document_type"],
            document_subtype=document_data.get("document_subtype"),
            description=document_data.get("description"),
            reference_number=document_data.get("reference_number"),
            issue_date=document_data.get("issue_date"),
            expiry_date=document_data.get("expiry_date"),
            issuing_authority=document_data.get("issuing_authority"),
            uploaded_by_user_id=uploaded_by_user_id,
            student_id=document_data.get("student_id"),
            enable_ocr=document_data.get("enable_ocr", True),
            auto_verify=document_data.get("auto_verify", False),
            redact_sensitive_info=document_data.get("redact_sensitive_info", False),
            ocr_status="pending" if document_data.get("enable_ocr") else "skipped",
            verification_status="pending",
            status="pending",
        )

        created_doc = await self.create(document, audit_context)

        # Setup expiry tracking if applicable
        if created_doc.expiry_date:
            await self.create_expiry_tracking(
                created_doc.id,
                created_doc.expiry_date,
                owner_type="student" if created_doc.student_id else "user",
                owner_id=created_doc.student_id or uploaded_by_user_id,
                owner_email=document_data.get("owner_email"),
            )

        return created_doc

    async def find_by_document_id(
        self,
        document_id: str,
        load_relationships: bool = False,
    ) -> Optional[DocumentUpload]:
        """
        Find document by unique document ID.

        Args:
            document_id: Document identifier
            load_relationships: Whether to load relationships

        Returns:
            DocumentUpload if found
        """
        query = self.db_session.query(DocumentUpload).filter(
            DocumentUpload.document_id == document_id
        )

        if load_relationships:
            query = query.options(
                joinedload(DocumentUpload.file),
                joinedload(DocumentUpload.uploaded_by),
                joinedload(DocumentUpload.student),
                selectinload(DocumentUpload.validations),
                joinedload(DocumentUpload.ocr_result),
                selectinload(DocumentUpload.verifications),
                joinedload(DocumentUpload.expiry_tracking),
            )

        return query.first()

    async def find_by_reference_number(
        self,
        reference_number: str,
        document_type: Optional[str] = None,
    ) -> List[DocumentUpload]:
        """
        Find documents by reference number.

        Args:
            reference_number: Document reference number
            document_type: Optional document type filter

        Returns:
            List of matching documents
        """
        query = self.db_session.query(DocumentUpload).filter(
            DocumentUpload.reference_number == reference_number
        )

        if document_type:
            query = query.filter(DocumentUpload.document_type == document_type)

        return query.all()

    async def search_documents(
        self,
        criteria: Dict[str, Any],
        pagination: Optional[Dict[str, Any]] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> PaginatedResult[DocumentUpload]:
        """
        Search documents with flexible criteria.

        Args:
            criteria: Search criteria
            pagination: Pagination parameters
            sort_by: Sort field
            sort_order: Sort order

        Returns:
            Paginated document results

        Criteria:
            - document_type: Filter by document type
            - document_subtype: Filter by subtype
            - uploaded_by_user_id: Filter by uploader
            - student_id: Filter by student
            - verification_status: Filter by verification status
            - ocr_status: Filter by OCR status
            - is_expired: Filter by expiry status
            - verified: Filter by verified flag
            - reference_number: Search by reference number
            - expiring_within_days: Documents expiring within N days
            - issued_after: Documents issued after date
            - issued_before: Documents issued before date
        """
        query = QueryBuilder(DocumentUpload, self.db_session)

        if "document_type" in criteria:
            query = query.where(
                DocumentUpload.document_type == criteria["document_type"]
            )

        if "document_subtype" in criteria:
            query = query.where(
                DocumentUpload.document_subtype == criteria["document_subtype"]
            )

        if "uploaded_by_user_id" in criteria:
            query = query.where(
                DocumentUpload.uploaded_by_user_id == criteria["uploaded_by_user_id"]
            )

        if "student_id" in criteria:
            query = query.where(DocumentUpload.student_id == criteria["student_id"])

        if "verification_status" in criteria:
            query = query.where(
                DocumentUpload.verification_status == criteria["verification_status"]
            )

        if "ocr_status" in criteria:
            query = query.where(DocumentUpload.ocr_status == criteria["ocr_status"])

        if "is_expired" in criteria:
            query = query.where(DocumentUpload.is_expired == criteria["is_expired"])

        if "verified" in criteria:
            query = query.where(DocumentUpload.verified == criteria["verified"])

        if "reference_number" in criteria:
            query = query.where(
                DocumentUpload.reference_number.like(
                    f"%{criteria['reference_number']}%"
                )
            )

        if "expiring_within_days" in criteria:
            expiry_threshold = Date.today() + timedelta(
                days=criteria["expiring_within_days"]
            )
            query = query.where(
                DocumentUpload.expiry_date.isnot(None),
                DocumentUpload.expiry_date <= expiry_threshold,
                DocumentUpload.is_expired == False,
            )

        if "issued_after" in criteria:
            query = query.where(DocumentUpload.issue_date >= criteria["issued_after"])

        if "issued_before" in criteria:
            query = query.where(
                DocumentUpload.issue_date <= criteria["issued_before"]
            )

        # Apply sorting
        sort_field = getattr(DocumentUpload, sort_by, DocumentUpload.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_field))
        else:
            query = query.order_by(asc(sort_field))

        return await PaginationManager.paginate(
            query.build(), pagination or {"page": 1, "page_size": 50}
        )

    async def get_student_documents(
        self,
        student_id: str,
        document_type: Optional[str] = None,
        verified_only: bool = False,
    ) -> List[DocumentUpload]:
        """
        Get all documents for a student.

        Args:
            student_id: Student identifier
            document_type: Optional document type filter
            verified_only: Only return verified documents

        Returns:
            List of student documents
        """
        query = self.db_session.query(DocumentUpload).filter(
            DocumentUpload.student_id == student_id
        )

        if document_type:
            query = query.filter(DocumentUpload.document_type == document_type)

        if verified_only:
            query = query.filter(DocumentUpload.verified == True)

        return query.order_by(desc(DocumentUpload.created_at)).all()

    # ============================================================================
    # DOCUMENT TYPE OPERATIONS
    # ============================================================================

    async def get_document_type(
        self,
        type_name: str,
    ) -> Optional[DocumentType]:
        """
        Get document type configuration.

        Args:
            type_name: Document type name

        Returns:
            DocumentType if found
        """
        return (
            self.db_session.query(DocumentType)
            .filter(
                DocumentType.type_name == type_name,
                DocumentType.is_active == True,
            )
            .first()
        )

    async def get_all_document_types(
        self,
        category: Optional[str] = None,
        is_mandatory: Optional[bool] = None,
        is_active: bool = True,
    ) -> List[DocumentType]:
        """
        Get all document types.

        Args:
            category: Filter by category
            is_mandatory: Filter by mandatory flag
            is_active: Filter by active status

        Returns:
            List of document types
        """
        query = self.db_session.query(DocumentType).filter(
            DocumentType.is_active == is_active
        )

        if category:
            query = query.filter(DocumentType.category == category)

        if is_mandatory is not None:
            query = query.filter(DocumentType.is_mandatory == is_mandatory)

        return query.order_by(
            DocumentType.display_order, DocumentType.type_name
        ).all()

    async def create_document_type(
        self,
        type_data: Dict[str, Any],
        audit_context: Optional[Dict[str, Any]] = None,
    ) -> DocumentType:
        """
        Create new document type configuration.

        Args:
            type_data: Document type configuration
            audit_context: Audit context

        Returns:
            Created DocumentType
        """
        doc_type = DocumentType(
            type_name=type_data["type_name"],
            display_name=type_data["display_name"],
            description=type_data.get("description"),
            category=type_data["category"],
            requires_verification=type_data.get("requires_verification", True),
            requires_expiry_date=type_data.get("requires_expiry_date", False),
            requires_reference_number=type_data.get("requires_reference_number", False),
            accepted_formats=type_data.get("accepted_formats"),
            max_size_bytes=type_data.get("max_size_bytes"),
            min_resolution=type_data.get("min_resolution"),
            enable_ocr_by_default=type_data.get("enable_ocr_by_default", True),
            ocr_fields=type_data.get("ocr_fields", []),
            default_validity_days=type_data.get("default_validity_days"),
            expiry_alert_days=type_data.get("expiry_alert_days", 30),
            is_active=type_data.get("is_active", True),
            is_mandatory=type_data.get("is_mandatory", False),
            display_order=type_data.get("display_order", 0),
            validation_rules=type_data.get("validation_rules", {}),
            metadata_schema=type_data.get("metadata_schema", {}),
        )

        self.db_session.add(doc_type)
        self.db_session.commit()
        return doc_type

    async def validate_document_requirements(
        self,
        document_type: str,
        document_data: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """
        Validate document against type requirements.

        Args:
            document_type: Document type name
            document_data: Document data to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        doc_type = await self.get_document_type(document_type)
        if not doc_type:
            return False, [f"Invalid document type: {document_type}"]

        errors = []

        # Check required fields
        if doc_type.requires_reference_number and not document_data.get(
            "reference_number"
        ):
            errors.append("Reference number is required for this document type")

        if doc_type.requires_expiry_date and not document_data.get("expiry_date"):
            errors.append("Expiry date is required for this document type")

        # Check file format
        if doc_type.accepted_formats and document_data.get("content_type"):
            if document_data["content_type"] not in doc_type.accepted_formats:
                errors.append(
                    f"File format not accepted. Allowed: {', '.join(doc_type.accepted_formats)}"
                )

        # Check file size
        if doc_type.max_size_bytes and document_data.get("size_bytes"):
            if document_data["size_bytes"] > doc_type.max_size_bytes:
                errors.append(
                    f"File size exceeds maximum of {doc_type.max_size_bytes} bytes"
                )

        return len(errors) == 0, errors

    # ============================================================================
    # OCR OPERATIONS
    # ============================================================================

    async def create_ocr_result(
        self,
        document_id: str,
        ocr_data: Dict[str, Any],
    ) -> DocumentOCR:
        """
        Store OCR processing results.

        Args:
            document_id: Document identifier (internal ID)
            ocr_data: OCR results and extracted data

        Returns:
            Created DocumentOCR
        """
        ocr = DocumentOCR(
            document_id=document_id,
            ocr_status=ocr_data["ocr_status"],
            confidence_score=ocr_data.get("confidence_score"),
            full_text=ocr_data.get("full_text"),
            text_length=len(ocr_data.get("full_text", "")),
            extracted_fields=ocr_data.get("extracted_fields", {}),
            extracted_name=ocr_data.get("extracted_name"),
            extracted_id_number=ocr_data.get("extracted_id_number"),
            extracted_dob=ocr_data.get("extracted_dob"),
            extracted_address=ocr_data.get("extracted_address"),
            extracted_issue_date=ocr_data.get("extracted_issue_date"),
            extracted_expiry_date=ocr_data.get("extracted_expiry_date"),
            ocr_engine=ocr_data.get("ocr_engine", "tesseract"),
            ocr_engine_version=ocr_data.get("ocr_engine_version"),
            language_detected=ocr_data.get("language_detected"),
            processing_time_seconds=ocr_data.get("processing_time_seconds"),
            processed_at=datetime.utcnow(),
            total_pages=ocr_data.get("total_pages", 1),
            pages_data=ocr_data.get("pages_data", []),
            error_message=ocr_data.get("error_message"),
        )

        self.db_session.add(ocr)
        self.db_session.commit()

        # Update document OCR status
        document = await self.find_by_id(document_id)
        document.ocr_completed = ocr_data["ocr_status"] == "completed"
        document.ocr_status = ocr_data["ocr_status"]
        if ocr_data.get("full_text"):
            document.extracted_text_preview = ocr_data["full_text"][:500]
        self.db_session.commit()

        return ocr

    async def get_ocr_result(
        self,
        document_id: str,
    ) -> Optional[DocumentOCR]:
        """
        Get OCR result for document.

        Args:
            document_id: Document identifier

        Returns:
            DocumentOCR if exists
        """
        return (
            self.db_session.query(DocumentOCR)
            .filter(DocumentOCR.document_id == document_id)
            .first()
        )

    async def find_documents_pending_ocr(
        self,
        limit: int = 100,
        priority_document_types: Optional[List[str]] = None,
    ) -> List[DocumentUpload]:
        """
        Find documents pending OCR processing.

        Args:
            limit: Maximum results
            priority_document_types: Document types to prioritize

        Returns:
            List of documents needing OCR
        """
        query = self.db_session.query(DocumentUpload).filter(
            DocumentUpload.enable_ocr == True,
            DocumentUpload.ocr_status == "pending",
        )

        if priority_document_types:
            # Priority documents first
            priority_docs = (
                query.filter(DocumentUpload.document_type.in_(priority_document_types))
                .order_by(asc(DocumentUpload.created_at))
                .limit(limit // 2)
                .all()
            )

            # Then other documents
            other_docs = (
                query.filter(
                    DocumentUpload.document_type.notin_(priority_document_types)
                )
                .order_by(asc(DocumentUpload.created_at))
                .limit(limit - len(priority_docs))
                .all()
            )

            return priority_docs + other_docs
        else:
            return query.order_by(asc(DocumentUpload.created_at)).limit(limit).all()

    async def update_ocr_status(
        self,
        document_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> DocumentUpload:
        """
        Update document OCR status.

        Args:
            document_id: Document identifier
            status: OCR status
            error_message: Error message if failed

        Returns:
            Updated DocumentUpload
        """
        document = await self.find_by_id(document_id)
        if not document:
            raise ValueError(f"Document not found: {document_id}")

        document.ocr_status = status
        document.ocr_completed = status == "completed"

        if status == "failed" and error_message:
            # Create OCR result with error
            ocr = DocumentOCR(
                document_id=document_id,
                ocr_status="failed",
                error_message=error_message,
                processed_at=datetime.utcnow(),
            )
            self.db_session.add(ocr)

        self.db_session.commit()
        return document

    # ============================================================================
    # DOCUMENT VALIDATION OPERATIONS
    # ============================================================================

    async def create_validation_result(
        self,
        document_id: str,
        validation_data: Dict[str, Any],
        validated_by_user_id: Optional[str] = None,
    ) -> DocumentValidation:
        """
        Store document validation results.

        Args:
            document_id: Document identifier
            validation_data: Validation results
            validated_by_user_id: User who validated (if manual)

        Returns:
            Created DocumentValidation
        """
        validation = DocumentValidation(
            document_id=document_id,
            validation_type=validation_data["validation_type"],
            is_valid=validation_data["is_valid"],
            validation_score=validation_data.get("validation_score"),
            checks_passed=validation_data.get("checks_passed", []),
            checks_failed=validation_data.get("checks_failed", []),
            warnings=validation_data.get("warnings", []),
            reason=validation_data.get("reason"),
            error_details=validation_data.get("error_details"),
            extracted_metadata=validation_data.get("extracted_metadata", {}),
            detected_type=validation_data.get("detected_type"),
            confidence_level=validation_data.get("confidence_level"),
            validated_at=datetime.utcnow(),
            validated_by_user_id=validated_by_user_id,
            validator_name=validation_data.get("validator_name"),
            validator_version=validation_data.get("validator_version"),
        )

        self.db_session.add(validation)
        self.db_session.commit()
        return validation

    async def get_validation_results(
        self,
        document_id: str,
        validation_type: Optional[str] = None,
    ) -> List[DocumentValidation]:
        """
        Get validation results for document.

        Args:
            document_id: Document identifier
            validation_type: Optional filter by type

        Returns:
            List of validation results
        """
        query = self.db_session.query(DocumentValidation).filter(
            DocumentValidation.document_id == document_id
        )

        if validation_type:
            query = query.filter(DocumentValidation.validation_type == validation_type)

        return query.order_by(desc(DocumentValidation.validated_at)).all()

    # ============================================================================
    # DOCUMENT VERIFICATION OPERATIONS
    # ============================================================================

    async def create_verification(
        self,
        document_id: str,
        verification_data: Dict[str, Any],
        verified_by_user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> DocumentVerification:
        """
        Create document verification record.

        Args:
            document_id: Document identifier
            verification_data: Verification decision and details
            verified_by_user_id: User performing verification
            ip_address: Verifier IP address
            user_agent: Verifier user agent

        Returns:
            Created DocumentVerification
        """
        verification = DocumentVerification(
            document_id=document_id,
            verified_by_user_id=verified_by_user_id,
            verification_status=verification_data["verification_status"],
            verification_type=verification_data.get("verification_type", "manual"),
            verification_notes=verification_data.get("verification_notes"),
            rejection_reason=verification_data.get("rejection_reason"),
            verified_reference_number=verification_data.get("verified_reference_number"),
            verified_issue_date=verification_data.get("verified_issue_date"),
            verified_expiry_date=verification_data.get("verified_expiry_date"),
            verification_checklist=verification_data.get("verification_checklist", {}),
            authenticity_score=verification_data.get("authenticity_score"),
            verified_at=datetime.utcnow(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db_session.add(verification)

        # Update document verification status
        document = await self.find_by_id(document_id)
        document.verification_status = verification_data["verification_status"]
        document.verified = verification_data["verification_status"] == "approved"
        document.verified_by_user_id = verified_by_user_id
        document.verified_at = datetime.utcnow()
        document.verification_notes = verification_data.get("verification_notes")

        if verification_data["verification_status"] == "rejected":
            document.rejection_reason = verification_data.get("rejection_reason")
            document.status = "rejected"
        elif verification_data["verification_status"] == "approved":
            document.status = "verified"

        # Update verified data if provided
        if verification_data.get("verified_reference_number"):
            document.reference_number = verification_data["verified_reference_number"]
        if verification_data.get("verified_issue_date"):
            document.issue_date = verification_data["verified_issue_date"]
        if verification_data.get("verified_expiry_date"):
            document.expiry_date = verification_data["verified_expiry_date"]
            # Update expiry tracking
            if document.expiry_tracking:
                document.expiry_tracking.expiry_date = verification_data[
                    "verified_expiry_date"
                ]
                await self._recalculate_expiry_days(document.expiry_tracking.id)

        self.db_session.commit()
        return verification

    async def get_verification_history(
        self,
        document_id: str,
    ) -> List[DocumentVerification]:
        """
        Get complete verification history for document.

        Args:
            document_id: Document identifier

        Returns:
            List of verifications ordered by date
        """
        return (
            self.db_session.query(DocumentVerification)
            .filter(DocumentVerification.document_id == document_id)
            .order_by(desc(DocumentVerification.verified_at))
            .all()
        )

    async def find_documents_pending_verification(
        self,
        document_type: Optional[str] = None,
        student_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[DocumentUpload]:
        """
        Find documents pending verification.

        Args:
            document_type: Filter by document type
            student_id: Filter by student
            limit: Maximum results

        Returns:
            List of documents pending verification
        """
        query = self.db_session.query(DocumentUpload).filter(
            DocumentUpload.verification_status == "pending"
        )

        if document_type:
            query = query.filter(DocumentUpload.document_type == document_type)

        if student_id:
            query = query.filter(DocumentUpload.student_id == student_id)

        return query.order_by(asc(DocumentUpload.created_at)).limit(limit).all()

    async def get_verification_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        verified_by_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get verification statistics.

        Args:
            start_date: Start date filter
            end_date: End date filter
            verified_by_user_id: Filter by verifier

        Returns:
            Verification statistics
        """
        query = self.db_session.query(
            func.count(DocumentVerification.id).label("total_verifications"),
            func.count(
                case([(DocumentVerification.verification_status == "approved", 1)])
            ).label("approved"),
            func.count(
                case([(DocumentVerification.verification_status == "rejected", 1)])
            ).label("rejected"),
            func.count(
                case([(DocumentVerification.verification_status == "needs_review", 1)])
            ).label("needs_review"),
            func.avg(DocumentVerification.authenticity_score).label(
                "avg_authenticity_score"
            ),
        )

        if start_date:
            query = query.filter(DocumentVerification.verified_at >= start_date)

        if end_date:
            query = query.filter(DocumentVerification.verified_at <= end_date)

        if verified_by_user_id:
            query = query.filter(
                DocumentVerification.verified_by_user_id == verified_by_user_id
            )

        result = query.first()

        return {
            "total_verifications": result.total_verifications or 0,
            "approved": result.approved or 0,
            "rejected": result.rejected or 0,
            "needs_review": result.needs_review or 0,
            "average_authenticity_score": round(
                result.avg_authenticity_score or 0, 2
            ),
        }

    # ============================================================================
    # DOCUMENT EXPIRY OPERATIONS
    # ============================================================================

    async def create_expiry_tracking(
        self,
        document_id: str,
        expiry_date: Date,
        owner_type: str,
        owner_id: str,
        owner_email: Optional[str] = None,
        alert_threshold_days: int = 30,
    ) -> DocumentExpiry:
        """
        Create expiry tracking for document.

        Args:
            document_id: Document identifier
            expiry_date: Document expiry date
            owner_type: Owner type (student, staff, etc.)
            owner_id: Owner identifier
            owner_email: Owner email for notifications
            alert_threshold_days: Days before expiry to alert

        Returns:
            Created DocumentExpiry
        """
        days_until_expiry = (expiry_date - Date.today()).days
        is_expired = days_until_expiry < 0

        # Determine urgency level
        if is_expired:
            urgency_level = "critical"
        elif days_until_expiry <= 7:
            urgency_level = "high"
        elif days_until_expiry <= 30:
            urgency_level = "medium"
        else:
            urgency_level = "low"

        expiry = DocumentExpiry(
            document_id=document_id,
            expiry_date=expiry_date,
            days_until_expiry=days_until_expiry,
            is_expired=is_expired,
            alert_threshold_days=alert_threshold_days,
            owner_type=owner_type,
            owner_id=owner_id,
            owner_email=owner_email,
            urgency_level=urgency_level,
            last_calculated_at=datetime.utcnow(),
        )

        self.db_session.add(expiry)
        self.db_session.commit()
        return expiry

    async def update_expiry_calculations(
        self,
        batch_size: int = 1000,
    ) -> int:
        """
        Update expiry calculations for all tracked documents.

        Args:
            batch_size: Number of records to update per batch

        Returns:
            Number of records updated
        """
        expiries = (
            self.db_session.query(DocumentExpiry)
            .order_by(asc(DocumentExpiry.last_calculated_at))
            .limit(batch_size)
            .all()
        )

        updated_count = 0
        for expiry in expiries:
            await self._recalculate_expiry_days(expiry.id)
            updated_count += 1

        return updated_count

    async def _recalculate_expiry_days(
        self,
        expiry_id: str,
    ) -> DocumentExpiry:
        """
        Recalculate expiry days and urgency for a document.

        Args:
            expiry_id: DocumentExpiry identifier

        Returns:
            Updated DocumentExpiry
        """
        expiry = self.db_session.query(DocumentExpiry).get(expiry_id)
        if not expiry:
            raise ValueError(f"Expiry tracking not found: {expiry_id}")

        days_until_expiry = (expiry.expiry_date - Date.today()).days
        is_expired = days_until_expiry < 0

        # Update urgency level
        if is_expired:
            urgency_level = "critical"
        elif days_until_expiry <= 7:
            urgency_level = "high"
        elif days_until_expiry <= 30:
            urgency_level = "medium"
        else:
            urgency_level = "low"

        expiry.days_until_expiry = days_until_expiry
        expiry.is_expired = is_expired
        expiry.urgency_level = urgency_level
        expiry.last_calculated_at = datetime.utcnow()

        # Update parent document
        document = expiry.document
        document.is_expired = is_expired
        if is_expired:
            document.verification_status = "expired"
            document.status = "expired"

        self.db_session.commit()
        return expiry

    async def find_expiring_documents(
        self,
        days_threshold: int = 30,
        owner_type: Optional[str] = None,
        urgency_level: Optional[str] = None,
        limit: int = 100,
    ) -> List[DocumentExpiry]:
        """
        Find documents expiring within threshold.

        Args:
            days_threshold: Days until expiry threshold
            owner_type: Filter by owner type
            urgency_level: Filter by urgency level
            limit: Maximum results

        Returns:
            List of expiring documents
        """
        query = self.db_session.query(DocumentExpiry).filter(
            DocumentExpiry.is_expired == False,
            DocumentExpiry.days_until_expiry <= days_threshold,
            DocumentExpiry.days_until_expiry >= 0,
        )

        if owner_type:
            query = query.filter(DocumentExpiry.owner_type == owner_type)

        if urgency_level:
            query = query.filter(DocumentExpiry.urgency_level == urgency_level)

        return (
            query.order_by(asc(DocumentExpiry.days_until_expiry)).limit(limit).all()
        )

    async def find_expired_documents(
        self,
        owner_type: Optional[str] = None,
        document_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[DocumentExpiry]:
        """
        Find expired documents.

        Args:
            owner_type: Filter by owner type
            document_type: Filter by document type
            limit: Maximum results

        Returns:
            List of expired documents
        """
        query = (
            self.db_session.query(DocumentExpiry)
            .join(DocumentUpload, DocumentExpiry.document_id == DocumentUpload.id)
            .filter(DocumentExpiry.is_expired == True)
        )

        if owner_type:
            query = query.filter(DocumentExpiry.owner_type == owner_type)

        if document_type:
            query = query.filter(DocumentUpload.document_type == document_type)

        return (
            query.order_by(asc(DocumentExpiry.expiry_date)).limit(limit).all()
        )

    async def send_expiry_alerts(
        self,
        batch_size: int = 100,
    ) -> int:
        """
        Send expiry alerts for documents needing notification.

        Args:
            batch_size: Number of alerts to send

        Returns:
            Number of alerts sent
        """
        # Find documents needing alerts
        expiries = (
            self.db_session.query(DocumentExpiry)
            .filter(
                DocumentExpiry.is_expired == False,
                DocumentExpiry.days_until_expiry <= DocumentExpiry.alert_threshold_days,
                or_(
                    DocumentExpiry.alert_sent == False,
                    DocumentExpiry.last_alert_sent_at.is_(None),
                    DocumentExpiry.last_alert_sent_at
                    < datetime.utcnow()
                    - timedelta(days=DocumentExpiry.alert_frequency_days),
                ),
            )
            .limit(batch_size)
            .all()
        )

        alerts_sent = 0
        for expiry in expiries:
            # TODO: Trigger actual alert notification
            expiry.alert_sent = True
            expiry.last_alert_sent_at = datetime.utcnow()
            expiry.alert_count += 1
            alerts_sent += 1

        self.db_session.commit()
        return alerts_sent

    async def mark_document_renewed(
        self,
        expiry_id: str,
        renewed_document_id: str,
    ) -> DocumentExpiry:
        """
        Mark document as renewed with new document reference.

        Args:
            expiry_id: Original document expiry ID
            renewed_document_id: New document ID

        Returns:
            Updated DocumentExpiry
        """
        expiry = self.db_session.query(DocumentExpiry).get(expiry_id)
        if not expiry:
            raise ValueError(f"Expiry tracking not found: {expiry_id}")

        expiry.renewal_requested = True
        expiry.renewal_requested_at = datetime.utcnow()
        expiry.renewed_document_id = renewed_document_id

        self.db_session.commit()
        return expiry

    # ============================================================================
    # ANALYTICS AND REPORTING
    # ============================================================================

    async def get_document_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        student_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get document upload and verification statistics.

        Args:
            start_date: Start date filter
            end_date: End date filter
            student_id: Filter by student

        Returns:
            Document statistics
        """
        query = self.db_session.query(
            func.count(DocumentUpload.id).label("total_documents"),
            func.count(
                case([(DocumentUpload.verified == True, 1)])
            ).label("verified_documents"),
            func.count(
                case([(DocumentUpload.verification_status == "pending", 1)])
            ).label("pending_verification"),
            func.count(
                case([(DocumentUpload.verification_status == "rejected", 1)])
            ).label("rejected_documents"),
            func.count(
                case([(DocumentUpload.is_expired == True, 1)])
            ).label("expired_documents"),
            func.count(
                case([(DocumentUpload.ocr_completed == True, 1)])
            ).label("ocr_completed"),
        )

        if start_date:
            query = query.filter(DocumentUpload.created_at >= start_date)

        if end_date:
            query = query.filter(DocumentUpload.created_at <= end_date)

        if student_id:
            query = query.filter(DocumentUpload.student_id == student_id)

        result = query.first()

        return {
            "total_documents": result.total_documents or 0,
            "verified_documents": result.verified_documents or 0,
            "pending_verification": result.pending_verification or 0,
            "rejected_documents": result.rejected_documents or 0,
            "expired_documents": result.expired_documents or 0,
            "ocr_completed": result.ocr_completed or 0,
        }

    async def get_document_type_distribution(
        self,
        student_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get distribution of documents by type.

        Args:
            student_id: Filter by student

        Returns:
            List of document type statistics
        """
        query = self.db_session.query(
            DocumentUpload.document_type,
            func.count(DocumentUpload.id).label("count"),
            func.count(
                case([(DocumentUpload.verified == True, 1)])
            ).label("verified_count"),
        ).group_by(DocumentUpload.document_type)

        if student_id:
            query = query.filter(DocumentUpload.student_id == student_id)

        results = query.order_by(desc("count")).all()

        return [
            {
                "document_type": row.document_type,
                "count": row.count,
                "verified_count": row.verified_count,
            }
            for row in results
        ]

    async def get_expiry_summary(
        self,
        owner_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get summary of document expiry status.

        Args:
            owner_type: Filter by owner type

        Returns:
            Expiry summary statistics
        """
        query = self.db_session.query(
            func.count(DocumentExpiry.id).label("total_tracked"),
            func.count(
                case([(DocumentExpiry.is_expired == True, 1)])
            ).label("expired"),
            func.count(
                case([(DocumentExpiry.urgency_level == "critical", 1)])
            ).label("critical"),
            func.count(
                case([(DocumentExpiry.urgency_level == "high", 1)])
            ).label("high_urgency"),
            func.count(
                case([(DocumentExpiry.urgency_level == "medium", 1)])
            ).label("medium_urgency"),
            func.count(
                case([(DocumentExpiry.urgency_level == "low", 1)])
            ).label("low_urgency"),
        )

        if owner_type:
            query = query.filter(DocumentExpiry.owner_type == owner_type)

        result = query.first()

        return {
            "total_tracked": result.total_tracked or 0,
            "expired": result.expired or 0,
            "critical": result.critical or 0,
            "high_urgency": result.high_urgency or 0,
            "medium_urgency": result.medium_urgency or 0,
            "low_urgency": result.low_urgency or 0,
        }

    async def check_student_document_compliance(
        self,
        student_id: str,
    ) -> Dict[str, Any]:
        """
        Check student's document compliance status.

        Args:
            student_id: Student identifier

        Returns:
            Compliance status and missing documents
        """
        # Get all mandatory document types
        mandatory_types = await self.get_all_document_types(is_mandatory=True)

        # Get student's documents
        student_docs = await self.get_student_documents(
            student_id=student_id, verified_only=True
        )

        student_doc_types = {doc.document_type for doc in student_docs}
        mandatory_type_names = {dt.type_name for dt in mandatory_types}

        missing_types = mandatory_type_names - student_doc_types
        expired_docs = [doc for doc in student_docs if doc.is_expired]
        pending_verification = [
            doc for doc in student_docs if doc.verification_status == "pending"
        ]

        is_compliant = (
            len(missing_types) == 0
            and len(expired_docs) == 0
            and len(pending_verification) == 0
        )

        return {
            "is_compliant": is_compliant,
            "total_mandatory_types": len(mandatory_types),
            "total_documents": len(student_docs),
            "verified_documents": len([d for d in student_docs if d.verified]),
            "missing_document_types": list(missing_types),
            "expired_documents": [
                {"document_id": doc.document_id, "document_type": doc.document_type}
                for doc in expired_docs
            ],
            "pending_verification": [
                {"document_id": doc.document_id, "document_type": doc.document_type}
                for doc in pending_verification
            ],
        }