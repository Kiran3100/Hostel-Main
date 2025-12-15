"""
Document-specific upload schemas with validation and verification.

Handles document uploads including ID proofs, agreements, invoices,
and other official documents with OCR and verification support.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from typing import Dict, List, Optional

from pydantic import Field, HttpUrl, field_validator, model_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema
from app.schemas.common.enums import IDProofType
from app.schemas.file.file_upload import FileUploadInitResponse

__all__ = [
    "DocumentUploadInitRequest",
    "DocumentUploadInitResponse",
    "DocumentValidationResult",
    "DocumentInfo",
    "DocumentList",
    "DocumentVerificationRequest",
    "DocumentVerificationResponse",
    "DocumentOCRResult",
    "DocumentExpiryAlert",
]


class DocumentUploadInitRequest(BaseCreateSchema):
    """
    Initialize document upload with classification.
    
    Supports various document types with appropriate validation
    and processing rules.
    """

    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(
        ...,
        pattern=r"^(application\/pdf|image\/(jpeg|jpg|png|tiff|bmp))$",
        description="Allowed: PDF or image formats for documents",
    )
    size_bytes: int = Field(
        ...,
        ge=1,
        le=25 * 1024 * 1024,
        description="Document size (max 25 MB)",
    )

    uploaded_by_user_id: str = Field(...)
    student_id: Optional[str] = Field(
        default=None,
        description="Student ID if document belongs to student",
    )
    hostel_id: Optional[str] = Field(
        default=None,
        description="Hostel ID if document is hostel-related",
    )

    # Document classification
    document_type: str = Field(
        ...,
        pattern=r"^(id_proof|address_proof|income_proof|educational_certificate|"
        r"medical_certificate|agreement|invoice|receipt|noc|"
        r"parent_consent|police_verification|other)$",
        description="Type of document being uploaded",
    )
    document_subtype: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Specific subtype (e.g., 'aadhaar', 'passport' for id_proof)",
    )

    # Metadata
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Document description or notes",
    )
    reference_number: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Document reference/ID number",
    )

    # Dates
    issue_date: Optional[Date] = Field(
        default=None,
        description="Document issue Date",
    )
    expiry_date: Optional[Date] = Field(
        default=None,
        description="Document expiry Date (if applicable)",
    )

    # Processing options
    enable_ocr: bool = Field(
        default=True,
        description="Enable OCR text extraction",
    )
    auto_verify: bool = Field(
        default=False,
        description="Attempt automatic verification if possible",
    )
    redact_sensitive_info: bool = Field(
        default=False,
        description="Redact sensitive information (PII)",
    )

    @field_validator("filename")
    @classmethod
    def validate_document_filename(cls, v: str) -> str:
        """Validate document filename."""
        v = v.strip()
        if not v:
            raise ValueError("Filename cannot be empty")
        
        valid_extensions = [".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".bmp"]
        if not any(v.lower().endswith(ext) for ext in valid_extensions):
            raise ValueError(
                f"Invalid extension. Allowed: {', '.join(valid_extensions)}"
            )
        
        return v

    @field_validator("reference_number")
    @classmethod
    def validate_reference_number(cls, v: Optional[str]) -> Optional[str]:
        """Normalize reference number."""
        if v is not None:
            v = v.strip().upper()
            if not v:
                return None
        return v

    @field_validator("expiry_date")
    @classmethod
    def validate_expiry_date(cls, v: Optional[Date]) -> Optional[Date]:
        """Validate expiry Date is in the future."""
        if v is not None and v < Date.today():
            raise ValueError(
                "Document expiry Date cannot be in the past"
            )
        return v

    @model_validator(mode="after")
    def validate_dates_consistency(self) -> "DocumentUploadInitRequest":
        """Validate issue and expiry dates are consistent."""
        if self.issue_date and self.expiry_date:
            if self.expiry_date <= self.issue_date:
                raise ValueError(
                    "Expiry Date must be after issue Date"
                )
        
        return self


class DocumentUploadInitResponse(FileUploadInitResponse):
    """
    Document-specific upload initialization response.
    
    Extends base response with document processing information.
    """

    document_type: str = Field(..., description="Document type")
    
    # Processing flags
    will_perform_ocr: bool = Field(
        default=False,
        description="Whether OCR will be performed",
    )
    will_auto_verify: bool = Field(
        default=False,
        description="Whether automatic verification will be attempted",
    )
    
    # Expected processing time
    estimated_processing_time_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        description="Estimated time for document processing",
    )


class DocumentValidationResult(BaseSchema):
    """
    Backend document validation result.
    
    Validates document format, size, content, and basic checks.
    """

    storage_key: str = Field(..., description="Document storage key")
    file_id: str = Field(..., description="File identifier")

    # Validation status
    is_valid: bool = Field(..., description="Overall validation status")
    validation_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Validation confidence score (0-100)",
    )

    # Validation checks
    checks_passed: List[str] = Field(
        default_factory=list,
        description="List of passed validation checks",
    )
    checks_failed: List[str] = Field(
        default_factory=list,
        description="List of failed validation checks",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Validation warnings",
    )

    # Failure details
    reason: Optional[str] = Field(
        default=None,
        description="Primary reason if invalid",
    )
    error_details: Optional[str] = Field(
        default=None,
        description="Detailed error information",
    )

    # Extracted metadata (non-PII summary)
    extracted_metadata: Optional[Dict[str, str]] = Field(
        default=None,
        description="Extracted document metadata",
    )
    detected_type: Optional[str] = Field(
        default=None,
        description="Auto-detected document type",
    )
    confidence_level: Optional[str] = Field(
        default=None,
        description="Detection confidence",
    )

    validated_at: datetime = Field(
        ...,
        description="Validation timestamp",
    )


class DocumentInfo(BaseResponseSchema):
    """
    Comprehensive document information.
    
    Used for displaying document details to users and admins.
    """

    document_id: str = Field(..., description="Document identifier")
    file_id: str = Field(..., description="Associated file ID")
    storage_key: str = Field(..., description="Storage key")

    # URLs
    url: HttpUrl = Field(..., description="Document access URL")
    thumbnail_url: Optional[HttpUrl] = Field(
        default=None,
        description="Thumbnail URL for preview",
    )

    # Classification
    document_type: str = Field(..., description="Document type")
    document_subtype: Optional[str] = Field(default=None, description="Document subtype")
    description: Optional[str] = Field(default=None, description="Description")

    # Ownership
    uploaded_by_user_id: str = Field(..., description="Uploader user ID")
    uploaded_by_name: Optional[str] = Field(default=None, description="Uploader name")
    student_id: Optional[str] = Field(default=None, description="Associated student")
    hostel_id: Optional[str] = Field(default=None, description="Associated hostel")

    # Document details
    reference_number: Optional[str] = Field(default=None, description="Reference number")
    issue_date: Optional[Date] = Field(default=None, description="Issue Date")
    expiry_date: Optional[Date] = Field(default=None, description="Expiry Date")

    # File metadata
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(..., ge=0, description="File size")

    # Verification status
    verified: bool = Field(
        default=False,
        description="Whether document has been verified",
    )
    verified_by: Optional[str] = Field(
        default=None,
        description="User ID who verified",
    )
    verified_by_name: Optional[str] = Field(
        default=None,
        description="Verifier name",
    )
    verified_at: Optional[datetime] = Field(
        default=None,
        description="Verification timestamp",
    )
    verification_notes: Optional[str] = Field(
        default=None,
        description="Verification notes",
    )

    # Status
    status: str = Field(
        default="pending",
        description="Document status",
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Reason for rejection if rejected",
    )

    # OCR results
    ocr_completed: bool = Field(
        default=False,
        description="Whether OCR was performed",
    )
    extracted_text: Optional[str] = Field(
        default=None,
        description="OCR extracted text (truncated for display)",
    )

    # Timestamps
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if document has expired."""
        if self.expiry_date is None:
            return False
        return self.expiry_date < Date.today()

    @computed_field
    @property
    def days_until_expiry(self) -> Optional[int]:
        """Get days until expiry."""
        if self.expiry_date is None:
            return None
        delta = self.expiry_date - Date.today()
        return delta.days

    @computed_field
    @property
    def is_expiring_soon(self) -> bool:
        """Check if document expires within 30 days."""
        days = self.days_until_expiry
        return days is not None and 0 <= days <= 30


class DocumentList(BaseSchema):
    """
    List of documents for a student/hostel/user.
    
    Provides organized document listing with filtering.
    """

    owner_type: str = Field(
        ...,
        pattern=r"^(student|hostel|user|system)$",
        description="Owner entity type",
    )
    owner_id: str = Field(..., description="Owner identifier")

    documents: List[DocumentInfo] = Field(
        default_factory=list,
        description="List of documents",
    )

    # Summary
    total_documents: int = Field(..., ge=0, description="Total document count")
    verified_count: int = Field(..., ge=0, description="Verified documents")
    pending_count: int = Field(..., ge=0, description="Pending verification")
    expired_count: int = Field(..., ge=0, description="Expired documents")
    expiring_soon_count: int = Field(
        ...,
        ge=0,
        description="Documents expiring within 30 days",
    )

    # By type breakdown
    by_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Document count by type",
    )

    @computed_field
    @property
    def verification_rate(self) -> float:
        """Get verification rate percentage."""
        if self.total_documents == 0:
            return 0.0
        return round((self.verified_count / self.total_documents) * 100, 2)


class DocumentVerificationRequest(BaseCreateSchema):
    """
    Request to verify a document.
    
    Used by admins/supervisors to verify uploaded documents.
    """

    document_id: str = Field(..., description="Document identifier to verify")
    
    verified_by_user_id: str = Field(
        ...,
        description="User performing verification",
    )

    # Verification decision
    verification_status: str = Field(
        ...,
        pattern=r"^(approved|rejected)$",
        description="Verification decision",
    )

    # Notes
    verification_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Verification notes or comments",
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason for rejection (required if rejected)",
    )

    # Extracted information (manual correction)
    extracted_reference_number: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Manually extracted reference number",
    )
    extracted_issue_date: Optional[Date] = Field(
        default=None,
        description="Manually extracted issue Date",
    )
    extracted_expiry_date: Optional[Date] = Field(
        default=None,
        description="Manually extracted expiry Date",
    )

    @model_validator(mode="after")
    def validate_rejection_reason(self) -> "DocumentVerificationRequest":
        """Ensure rejection reason is provided when rejecting."""
        if self.verification_status == "rejected" and not self.rejection_reason:
            raise ValueError(
                "Rejection reason is required when rejecting a document"
            )
        return self


class DocumentVerificationResponse(BaseSchema):
    """
    Response after document verification.
    
    Confirms verification action and provides updated status.
    """

    document_id: str = Field(..., description="Document identifier")
    file_id: str = Field(..., description="Associated file ID")

    verification_status: str = Field(..., description="Verification status")
    verified_by: str = Field(..., description="Verifier user ID")
    verified_by_name: str = Field(..., description="Verifier name")
    verified_at: datetime = Field(..., description="Verification timestamp")

    message: str = Field(
        ...,
        description="Confirmation message",
    )


class DocumentOCRResult(BaseSchema):
    """
    OCR (Optical Character Recognition) result.
    
    Contains extracted text and structured data from document.
    """

    document_id: str = Field(..., description="Document identifier")
    file_id: str = Field(..., description="File identifier")

    # OCR status
    ocr_status: str = Field(
        ...,
        description="OCR processing status",
    )
    confidence_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Overall OCR confidence score (0-100)",
    )

    # Extracted content
    full_text: str = Field(
        default="",
        description="Complete extracted text",
    )
    text_length: int = Field(
        ...,
        ge=0,
        description="Length of extracted text",
    )

    # Structured data extraction
    extracted_fields: Dict[str, str] = Field(
        default_factory=dict,
        description="Structured fields extracted from document",
    )

    # For ID documents
    extracted_name: Optional[str] = Field(default=None, description="Extracted name")
    extracted_id_number: Optional[str] = Field(default=None, description="Extracted ID number")
    extracted_dob: Optional[str] = Field(default=None, description="Extracted Date of birth")
    extracted_address: Optional[str] = Field(default=None, description="Extracted address")

    # Processing metadata
    ocr_engine: str = Field(
        default="tesseract",
        description="OCR engine used",
    )
    processing_time_seconds: Optional[float] = Field(
        default=None,
        ge=0,
        description="OCR processing time",
    )
    processed_at: datetime = Field(..., description="OCR completion timestamp")

    # Error information
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if OCR failed",
    )


class DocumentExpiryAlert(BaseSchema):
    """
    Document expiry alert/notification.
    
    Used to notify users about expiring or expired documents.
    """

    document_id: str = Field(..., description="Document identifier")
    document_type: str = Field(..., description="Document type")
    reference_number: Optional[str] = Field(default=None, description="Document reference")

    owner_id: str = Field(..., description="Document owner ID")
    owner_type: str = Field(..., description="Owner type (student/hostel)")
    owner_name: str = Field(..., description="Owner name")

    # Expiry information
    expiry_date: Date = Field(..., description="Document expiry Date")
    days_until_expiry: int = Field(
        ...,
        description="Days until expiry (negative if already expired)",
    )

    # Alert details
    alert_type: str = Field(
        ...,
        description="Alert type",
    )
    severity: str = Field(
        ...,
        description="Alert severity",
    )

    # Notification
    notification_sent: bool = Field(
        default=False,
        description="Whether notification was sent",
    )
    notification_sent_at: Optional[datetime] = Field(
        default=None,
        description="Notification timestamp",
    )

    created_at: datetime = Field(..., description="Alert creation timestamp")

    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if document is already expired."""
        return self.days_until_expiry < 0

    @computed_field
    @property
    def urgency_level(self) -> str:
        """Determine urgency level based on days until expiry."""
        if self.days_until_expiry < 0:
            return "critical"
        elif self.days_until_expiry <= 7:
            return "high"
        elif self.days_until_expiry <= 30:
            return "medium"
        else:
            return "low"