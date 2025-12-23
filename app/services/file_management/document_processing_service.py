"""
Document Processing Service

Manages:
- Document upload initialization
- OCR (Optical Character Recognition)
- Document validation and verification
- Expiry date monitoring and alerts
- Document archival and compliance
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, datetime, timedelta
import logging

from sqlalchemy.orm import Session

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.file_management.document_upload_repository import DocumentUploadRepository
from app.models.file_management.document_upload import DocumentUpload as DocumentUploadModel
from app.schemas.file.document_upload import (
    DocumentUploadInitRequest,
    DocumentUploadInitResponse,
    DocumentValidationResult,
    DocumentInfo,
    DocumentVerificationRequest,
    DocumentVerificationResponse,
    DocumentOCRResult,
    DocumentExpiryAlert,
    DocumentList,
)

logger = logging.getLogger(__name__)


class DocumentProcessingService(BaseService[DocumentUploadModel, DocumentUploadRepository]):
    """
    Comprehensive document management and processing.
    
    Features:
    - Document upload with type validation
    - OCR for text extraction
    - Multi-level document verification
    - Expiry tracking and automated alerts
    - Archival and retention policies
    """

    # Supported document types
    SUPPORTED_DOCUMENT_TYPES = {
        'id_card', 'passport', 'driving_license', 'birth_certificate',
        'academic_transcript', 'degree_certificate', 'medical_certificate',
        'police_clearance', 'financial_statement', 'contract', 'invoice',
        'receipt', 'other'
    }

    def __init__(
        self,
        repository: DocumentUploadRepository,
        db_session: Session,
        auto_ocr: bool = True
    ):
        """
        Initialize the document processing service.
        
        Args:
            repository: Document upload repository instance
            db_session: SQLAlchemy database session
            auto_ocr: Whether to automatically run OCR on document upload
        """
        super().__init__(repository, db_session)
        self.auto_ocr = auto_ocr
        self._expiry_warning_days = 30  # Default warning period
        logger.info(
            f"DocumentProcessingService initialized, auto_ocr: {auto_ocr}"
        )

    def init_document_upload(
        self,
        request: DocumentUploadInitRequest,
    ) -> ServiceResult[DocumentUploadInitResponse]:
        """
        Initialize a document upload with metadata.
        
        Args:
            request: Document upload initialization request
            
        Returns:
            ServiceResult containing upload initialization response
        """
        try:
            logger.info(
                f"Initializing document upload: {request.filename}, "
                f"type: {request.document_type}, owner: {request.owner_user_id}"
            )

            # Validate document type
            if hasattr(request, 'document_type') and request.document_type:
                if request.document_type not in self.SUPPORTED_DOCUMENT_TYPES:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"Unsupported document type: {request.document_type}",
                            severity=ErrorSeverity.WARNING,
                        )
                    )

            # Validate expiry date if provided
            if hasattr(request, 'expiry_date') and request.expiry_date:
                if request.expiry_date < date.today():
                    logger.warning(
                        f"Document expiry date is in the past: {request.expiry_date}"
                    )

            response = self.repository.init_document_upload(request)
            self.db.commit()

            logger.info(
                f"Document upload initialized successfully with ID: {response.document_id}"
            )

            # Trigger auto-OCR if enabled and document is uploaded
            if self.auto_ocr and response.status == "completed":
                logger.info(f"Triggering auto-OCR for document {response.document_id}")
                self.run_ocr(response.document_id)

            return ServiceResult.success(
                response,
                message="Document upload initialized successfully"
            )

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Failed to initialize document upload: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "init document upload")

    def validate_document(
        self,
        document_id: UUID,
        validation_rules: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[DocumentValidationResult]:
        """
        Validate document against business rules.
        
        Args:
            document_id: Unique identifier of the document
            validation_rules: Optional custom validation rules
            
        Returns:
            ServiceResult containing validation results
        """
        try:
            logger.info(f"Validating document with ID: {document_id}")

            result = self.repository.validate_document(
                document_id,
                validation_rules=validation_rules
            )
            self.db.commit()

            if result.is_valid:
                logger.info(
                    f"Document {document_id} validated successfully, "
                    f"warnings: {len(result.warnings) if result.warnings else 0}"
                )
                return ServiceResult.success(
                    result,
                    message="Document validated successfully"
                )
            else:
                logger.warning(
                    f"Document {document_id} validation failed, "
                    f"errors: {len(result.errors) if result.errors else 0}"
                )
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Document validation failed",
                        severity=ErrorSeverity.WARNING,
                        details={"result": result}
                    )
                )

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Document validation error for {document_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "validate document", document_id)

    def run_ocr(
        self,
        document_id: UUID,
        language: str = "eng",
        extract_fields: Optional[List[str]] = None,
    ) -> ServiceResult[DocumentOCRResult]:
        """
        Run OCR on a document to extract text.
        
        Args:
            document_id: Unique identifier of the document
            language: OCR language code (default: English)
            extract_fields: Specific fields to extract (e.g., name, date, ID number)
            
        Returns:
            ServiceResult containing OCR results
        """
        try:
            logger.info(
                f"Running OCR on document {document_id}, language: {language}"
            )

            result = self.repository.run_ocr(
                document_id,
                language=language,
                extract_fields=extract_fields
            )
            self.db.commit()

            if result.status == "completed":
                logger.info(
                    f"OCR completed successfully for document {document_id}, "
                    f"confidence: {result.confidence}%, "
                    f"text length: {len(result.extracted_text) if result.extracted_text else 0}"
                )
                return ServiceResult.success(
                    result,
                    message="OCR completed successfully",
                    metadata={"confidence": result.confidence}
                )
            elif result.status == "failed":
                logger.error(
                    f"OCR failed for document {document_id}: {result.error_message}"
                )
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.PROCESSING_ERROR,
                        message=result.error_message or "OCR processing failed",
                        severity=ErrorSeverity.ERROR,
                        details={"result": result}
                    )
                )
            else:
                logger.info(f"OCR status for document {document_id}: {result.status}")
                return ServiceResult.success(result, message=f"OCR status: {result.status}")

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"OCR error for document {document_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "run document ocr", document_id)

    def verify_document(
        self,
        request: DocumentVerificationRequest,
        verified_by: Optional[UUID] = None,
    ) -> ServiceResult[DocumentVerificationResponse]:
        """
        Verify document authenticity and accuracy.
        
        Args:
            request: Document verification request
            verified_by: User ID who performed verification
            
        Returns:
            ServiceResult containing verification response
        """
        try:
            logger.info(
                f"Verifying document {request.document_id}, "
                f"status: {request.verification_status}"
            )

            # Validate verification status
            valid_statuses = {'pending', 'verified', 'rejected', 'requires_resubmission'}
            if request.verification_status not in valid_statuses:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid verification status. Must be one of: {', '.join(valid_statuses)}",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            response = self.repository.verify_document(request, verified_by=verified_by)
            self.db.commit()

            logger.info(
                f"Document verification saved for {request.document_id}, "
                f"status: {request.verification_status}"
            )

            return ServiceResult.success(
                response,
                message=f"Document {request.verification_status} successfully"
            )

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Document verification error for {request.document_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "verify document", request.document_id)

    def get_document_info(
        self,
        document_id: UUID,
        include_ocr: bool = False,
        include_verification: bool = False,
    ) -> ServiceResult[DocumentInfo]:
        """
        Retrieve comprehensive document information.
        
        Args:
            document_id: Unique identifier of the document
            include_ocr: Whether to include OCR results
            include_verification: Whether to include verification history
            
        Returns:
            ServiceResult containing document information
        """
        try:
            logger.debug(f"Retrieving document info for ID: {document_id}")

            info = self.repository.get_document_info(
                document_id,
                include_ocr=include_ocr,
                include_verification=include_verification
            )

            if not info:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Document with ID {document_id} not found",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            return ServiceResult.success(
                info,
                metadata={
                    "include_ocr": include_ocr,
                    "include_verification": include_verification
                }
            )

        except Exception as e:
            logger.error(
                f"Failed to get document info for {document_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get document info", document_id)

    def list_documents_for_owner(
        self,
        owner_user_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        document_type: Optional[str] = None,
        verification_status: Optional[str] = None,
        expiring_within_days: Optional[int] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> ServiceResult[DocumentList]:
        """
        List documents with advanced filtering.
        
        Args:
            owner_user_id: Filter by document owner
            student_id: Filter by student
            hostel_id: Filter by hostel
            document_type: Filter by document type
            verification_status: Filter by verification status
            expiring_within_days: Filter documents expiring within specified days
            page: Page number
            page_size: Number of items per page
            
        Returns:
            ServiceResult containing paginated document list
        """
        try:
            logger.info(
                f"Listing documents - owner: {owner_user_id}, student: {student_id}, "
                f"hostel: {hostel_id}, type: {document_type}, page: {page}"
            )

            listing = self.repository.list_documents(
                owner_user_id=owner_user_id,
                student_id=student_id,
                hostel_id=hostel_id,
                document_type=document_type,
                verification_status=verification_status,
                expiring_within_days=expiring_within_days,
                page=page,
                page_size=page_size
            )

            total_count = listing.total if hasattr(listing, 'total') else len(listing.items)

            logger.info(f"Retrieved {len(listing.items)} documents (total: {total_count})")

            return ServiceResult.success(
                listing,
                metadata={
                    "count": total_count,
                    "page": page,
                    "page_size": page_size
                }
            )

        except Exception as e:
            logger.error(f"Failed to list documents: {str(e)}", exc_info=True)
            return self._handle_exception(e, "list documents")

    def queue_expiry_alerts(
        self,
        within_days: int = 30,
    ) -> ServiceResult[int]:
        """
        Queue alerts for documents expiring soon.
        
        Args:
            within_days: Number of days ahead to check for expiry
            
        Returns:
            ServiceResult with count of queued alerts
        """
        try:
            if within_days < 1:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="within_days must be at least 1",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            logger.info(f"Queueing expiry alerts for documents expiring within {within_days} days")

            count = self.repository.queue_expiry_alerts(within_days=within_days)
            self.db.commit()

            logger.info(f"Queued {count} expiry alerts")

            return ServiceResult.success(
                count or 0,
                message=f"Queued {count or 0} expiry alerts"
            )

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to queue expiry alerts: {str(e)}", exc_info=True)
            return self._handle_exception(e, "queue expiry alerts")

    def get_expiring_documents(
        self,
        within_days: int = 30,
        owner_user_id: Optional[UUID] = None,
    ) -> ServiceResult[List[DocumentInfo]]:
        """
        Get list of documents expiring within specified days.
        
        Args:
            within_days: Number of days to look ahead
            owner_user_id: Optional filter by owner
            
        Returns:
            ServiceResult containing list of expiring documents
        """
        try:
            logger.info(f"Retrieving documents expiring within {within_days} days")

            documents = self.repository.get_expiring_documents(
                within_days=within_days,
                owner_user_id=owner_user_id
            )

            logger.info(f"Found {len(documents)} expiring documents")

            return ServiceResult.success(
                documents,
                metadata={
                    "count": len(documents),
                    "within_days": within_days
                }
            )

        except Exception as e:
            logger.error(f"Failed to get expiring documents: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get expiring documents")

    def archive_document(
        self,
        document_id: UUID,
        archive_reason: Optional[str] = None,
        archived_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Archive a document (soft delete with metadata).
        
        Args:
            document_id: Unique identifier of the document
            archive_reason: Reason for archival
            archived_by: User ID who archived the document
            
        Returns:
            ServiceResult indicating success or failure
        """
        try:
            logger.info(f"Archiving document {document_id}, reason: {archive_reason}")

            success = self.repository.archive_document(
                document_id,
                archive_reason=archive_reason,
                archived_by=archived_by
            )

            if success:
                self.db.commit()
                logger.info(f"Document {document_id} archived successfully")
                return ServiceResult.success(True, message="Document archived successfully")
            else:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to archive document",
                        severity=ErrorSeverity.ERROR,
                    )
                )

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Failed to archive document {document_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "archive document", document_id)

    def restore_archived_document(
        self,
        document_id: UUID,
        restored_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Restore an archived document.
        
        Args:
            document_id: Unique identifier of the document
            restored_by: User ID who restored the document
            
        Returns:
            ServiceResult indicating success or failure
        """
        try:
            logger.info(f"Restoring archived document {document_id}")

            success = self.repository.restore_archived_document(
                document_id,
                restored_by=restored_by
            )

            if success:
                self.db.commit()
                logger.info(f"Document {document_id} restored successfully")
                return ServiceResult.success(True, message="Document restored successfully")
            else:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to restore document",
                        severity=ErrorSeverity.WARNING,
                    )
                )

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Failed to restore document {document_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "restore archived document", document_id)

    @property
    def expiry_warning_days(self) -> int:
        """Get the default expiry warning period in days."""
        return self._expiry_warning_days

    @expiry_warning_days.setter
    def expiry_warning_days(self, days: int) -> None:
        """Set the default expiry warning period."""
        if days < 1:
            raise ValueError("Expiry warning days must be at least 1")
        self._expiry_warning_days = days
        logger.info(f"Expiry warning days set to: {days}")