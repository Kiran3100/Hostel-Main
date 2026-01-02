"""
Document Upload Models

Document-specific upload and validation with OCR processing
and verification support.
"""

from datetime import date as Date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date as DateType,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.file_management.file_upload import FileUpload
    from app.models.user.user import User
    from app.models.student.student import Student

__all__ = [
    "DocumentUpload",
    "DocumentType",
    "DocumentValidation",
    "DocumentOCR",
    "DocumentVerification",
    "DocumentExpiry",
]


class DocumentUpload(UUIDMixin, TimestampModel, BaseModel):  # ✅ FIXED ORDER
    """
    Document-specific upload and validation.
    
    Handles various document types with classification,
    verification, and expiry tracking.
    """

    __tablename__ = "document_uploads"

    # File reference
    file_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("file_uploads.file_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Associated file upload",
    )

    # Document identification
    document_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique document identifier",
    )

    # Document classification
    document_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Document type: id_proof, address_proof, educational_certificate, etc.",
    )
    document_subtype: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Specific subtype (e.g., 'aadhaar', 'passport' for id_proof)",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Document description or notes",
    )

    # Document details
    reference_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Document reference/ID number",
    )
    issue_date: Mapped[Optional[Date]] = mapped_column(
        DateType,
        nullable=True,
        comment="Document issue date",
    )
    expiry_date: Mapped[Optional[Date]] = mapped_column(
        DateType,
        nullable=True,
        index=True,
        comment="Document expiry date (if applicable)",
    )
    issuing_authority: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Issuing authority/organization",
    )

    # Ownership
    uploaded_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who uploaded document",
    )
    student_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Associated student (if applicable)",
    )

    # Processing options
    enable_ocr: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether OCR is enabled",
    )
    auto_verify: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Attempt automatic verification",
    )
    redact_sensitive_info: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Redact sensitive information (PII)",
    )

    # OCR status
    ocr_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether OCR was performed",
    )
    ocr_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        comment="OCR status: pending, processing, completed, failed, skipped",
    )
    extracted_text_preview: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Preview of extracted text (first 500 chars)",
    )

    # Verification status
    verification_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        index=True,
        comment="Verification status: pending, verified, rejected, expired",
    )
    verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether document has been verified",
    )
    verified_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who verified the document",
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Verification timestamp",
    )
    verification_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Verification notes or comments",
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for rejection (if rejected)",
    )

    # Document status
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        index=True,
        comment="Overall document status",
    )
    is_expired: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether document has expired",
    )

    # Thumbnail for preview
    thumbnail_url: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        comment="Thumbnail URL for document preview",
    )

    # Relationships
    file: Mapped["FileUpload"] = relationship(
        "FileUpload",
        back_populates="document_upload",
    )
    uploaded_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[uploaded_by_user_id],
        back_populates="uploaded_documents",
    )
    verified_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[verified_by_user_id],
    )
    student: Mapped[Optional["Student"]] = relationship(
        "Student",
        foreign_keys=[student_id],
        back_populates="documents",
    )

    # Back-references
    validations: Mapped[List["DocumentValidation"]] = relationship(
        "DocumentValidation",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    ocr_result: Mapped[Optional["DocumentOCR"]] = relationship(
        "DocumentOCR",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
    )
    verifications: Mapped[List["DocumentVerification"]] = relationship(
        "DocumentVerification",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentVerification.verified_at.desc()",
    )
    expiry_tracking: Mapped[Optional["DocumentExpiry"]] = relationship(
        "DocumentExpiry",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_document_upload_type_status", "document_type", "status"),
        Index("idx_document_upload_student_type", "student_id", "document_type"),
        Index("idx_document_upload_verification", "verification_status", "verified"),
        Index("idx_document_upload_expiry", "expiry_date", "is_expired"),
        Index("idx_document_upload_reference", "reference_number"),
    )

    def __repr__(self) -> str:
        return f"<DocumentUpload(document_id={self.document_id}, type={self.document_type})>"


class DocumentType(UUIDMixin, TimestampModel, BaseModel):  # ✅ FIXED ORDER
    """
    Document type definitions and requirements.
    
    Configures validation rules, required fields, and
    processing options for different document types.
    """

    __tablename__ = "document_types"

    # Type identification
    type_name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="Document type name",
    )
    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Display name for UI",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Type description",
    )

    # Category
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Document category: identity, address, education, financial, etc.",
    )

    # Requirements
    requires_verification: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether verification is required",
    )
    requires_expiry_date: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether expiry date is required",
    )
    requires_reference_number: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether reference number is required",
    )

    # Validation rules
    accepted_formats: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Accepted file formats (MIME types)",
    )
    max_size_bytes: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Maximum file size allowed",
    )
    min_resolution: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Minimum resolution requirements (width, height)",
    )

    # OCR configuration
    enable_ocr_by_default: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether to enable OCR by default",
    )
    ocr_fields: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Fields to extract via OCR",
    )

    # Expiry settings
    default_validity_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Default validity period in days",
    )
    expiry_alert_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Days before expiry to send alert",
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether type is active",
    )
    is_mandatory: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether this document is mandatory",
    )

    # Display order
    display_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Display order in UI",
    )

    # Configuration
    validation_rules: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional validation rules",
    )
    metadata_schema: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Expected metadata schema",
    )

    __table_args__ = (
        Index("idx_document_type_category_active", "category", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<DocumentType(name={self.type_name}, category={self.category})>"


class DocumentValidation(UUIDMixin, TimestampModel, BaseModel):  # ✅ FIXED ORDER
    """
    Document validation results and checks.
    
    Stores detailed validation results including automated
    checks and manual review findings.
    """

    __tablename__ = "document_validations"

    # Document reference
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_uploads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Validated document",
    )

    # Validation details
    validation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Validation type: format, content, authenticity, etc.",
    )
    is_valid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        index=True,
        comment="Overall validation result",
    )
    validation_score: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Validation confidence score (0-100)",
    )

    # Checks performed
    checks_passed: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of passed validation checks",
    )
    checks_failed: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of failed validation checks",
    )
    warnings: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Validation warnings",
    )

    # Failure details
    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Primary reason if invalid",
    )
    error_details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed error information",
    )

    # Extracted information
    extracted_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Metadata extracted during validation",
    )
    detected_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Auto-detected document type",
    )
    confidence_level: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Detection confidence: low, medium, high",
    )

    # Validation execution
    validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Validation timestamp",
    )
    validated_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who performed validation (if manual)",
    )

    # Validator information
    validator_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Name of validator (automated/manual)",
    )
    validator_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Validator version",
    )

    # Relationships
    document: Mapped["DocumentUpload"] = relationship(
        "DocumentUpload",
        back_populates="validations",
    )
    validated_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[validated_by_user_id],
    )

    __table_args__ = (
        Index("idx_document_validation_doc_type", "document_id", "validation_type"),
        Index("idx_document_validation_valid", "is_valid", "validation_type"),
    )

    def __repr__(self) -> str:
        return f"<DocumentValidation(document_id={self.document_id}, valid={self.is_valid})>"


class DocumentOCR(UUIDMixin, TimestampModel, BaseModel):  # ✅ FIXED ORDER
    """
    OCR (Optical Character Recognition) result.
    
    Contains extracted text and structured data from documents
    with confidence scoring and field extraction.
    """

    __tablename__ = "document_ocr"

    # Document reference
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_uploads.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="OCR processed document",
    )

    # OCR status
    ocr_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="OCR status: pending, processing, completed, failed",
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Overall OCR confidence score (0-100)",
    )

    # Extracted content
    full_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Complete extracted text",
    )
    text_length: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Length of extracted text",
    )

    # Structured data extraction
    extracted_fields: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Structured fields extracted from document",
    )

    # For ID documents
    extracted_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Extracted name",
    )
    extracted_id_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Extracted ID/document number",
    )
    extracted_dob: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Extracted date of birth",
    )
    extracted_address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Extracted address",
    )
    extracted_issue_date: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Extracted issue date",
    )
    extracted_expiry_date: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Extracted expiry date",
    )

    # OCR processing details
    ocr_engine: Mapped[str] = mapped_column(
        String(100),
        default="tesseract",
        nullable=False,
        comment="OCR engine used",
    )
    ocr_engine_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="OCR engine version",
    )
    language_detected: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Detected text language",
    )

    # Processing metrics
    processing_time_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="OCR processing time",
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="OCR completion timestamp",
    )

    # Pages (for multi-page documents)
    total_pages: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
        comment="Total pages processed",
    )
    pages_data: Mapped[Optional[List[dict]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Per-page OCR results",
    )

    # Error information
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if OCR failed",
    )

    # Relationships
    document: Mapped["DocumentUpload"] = relationship(
        "DocumentUpload",
        back_populates="ocr_result",
    )

    __table_args__ = (
        Index("idx_document_ocr_status", "ocr_status"),
        Index("idx_document_ocr_id_number", "extracted_id_number"),
    )

    def __repr__(self) -> str:
        return f"<DocumentOCR(document_id={self.document_id}, status={self.ocr_status})>"


class DocumentVerification(UUIDMixin, TimestampModel, BaseModel):  # ✅ FIXED ORDER
    """
    Document verification history.
    
    Tracks all verification attempts and decisions with
    audit trail and approval workflow.
    """

    __tablename__ = "document_verifications"

    # Document reference
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_uploads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Verified document",
    )

    # Verifier information
    verified_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who performed verification",
    )

    # Verification decision
    verification_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Verification decision: approved, rejected, needs_review",
    )
    verification_type: Mapped[str] = mapped_column(
        String(50),
        default="manual",
        nullable=False,
        comment="Verification type: manual, automated, hybrid",
    )

    # Notes and reasons
    verification_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Verification notes or comments",
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for rejection (if rejected)",
    )

    # Extracted/corrected information
    verified_reference_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Verified/corrected reference number",
    )
    verified_issue_date: Mapped[Optional[Date]] = mapped_column(
        DateType,
        nullable=True,
        comment="Verified/corrected issue date",
    )
    verified_expiry_date: Mapped[Optional[Date]] = mapped_column(
        DateType,
        nullable=True,
        comment="Verified/corrected expiry date",
    )

    # Verification metadata
    verification_checklist: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Verification checklist and results",
    )
    authenticity_score: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Authenticity score (0-100)",
    )

    # Timestamps
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Verification timestamp",
    )

    # IP and device tracking
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address of verifier",
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="User agent of verifier",
    )

    # Relationships
    document: Mapped["DocumentUpload"] = relationship(
        "DocumentUpload",
        back_populates="verifications",
    )
    verified_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[verified_by_user_id],
    )

    __table_args__ = (
        Index("idx_document_verification_doc_status", "document_id", "verification_status"),
        Index("idx_document_verification_user", "verified_by_user_id", "verified_at"),
    )

    def __repr__(self) -> str:
        return f"<DocumentVerification(document_id={self.document_id}, status={self.verification_status})>"


class DocumentExpiry(UUIDMixin, TimestampModel, BaseModel):  # ✅ FIXED ORDER
    """
    Document expiry tracking and alerting.
    
    Monitors document expiration dates and manages
    automated notification workflow.
    """

    __tablename__ = "document_expiries"

    # Document reference
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_uploads.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Document being tracked",
    )

    # Expiry details
    expiry_date: Mapped[Date] = mapped_column(
        DateType,
        nullable=False,
        index=True,
        comment="Document expiry date",
    )
    days_until_expiry: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Days until expiry (negative if expired)",
    )
    is_expired: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether document is expired",
    )

    # Alert configuration
    alert_threshold_days: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
        comment="Days before expiry to start alerts",
    )
    alert_frequency_days: Mapped[int] = mapped_column(
        Integer,
        default=7,
        nullable=False,
        comment="Frequency of reminder alerts",
    )

    # Alert status
    alert_sent: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether expiry alert was sent",
    )
    last_alert_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last alert timestamp",
    )
    alert_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of alerts sent",
    )

    # Renewal tracking
    renewal_requested: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether renewal was requested",
    )
    renewal_requested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Renewal request timestamp",
    )
    renewed_document_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("document_uploads.id", ondelete="SET NULL"),
        nullable=True,
        comment="New document after renewal",
    )

    # Owner information (denormalized for efficient queries)
    owner_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Owner type: student, staff, etc.",
    )
    owner_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        comment="Owner identifier",
    )
    owner_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Owner email for notifications",
    )

    # Urgency level
    urgency_level: Mapped[str] = mapped_column(
        String(20),
        default="low",
        nullable=False,
        index=True,
        comment="Urgency: low, medium, high, critical",
    )

    # Last calculation
    last_calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Last days calculation timestamp",
    )

    # Relationships
    document: Mapped["DocumentUpload"] = relationship(
        "DocumentUpload",
        foreign_keys=[document_id],
        back_populates="expiry_tracking",
    )
    renewed_document: Mapped[Optional["DocumentUpload"]] = relationship(
        "DocumentUpload",
        foreign_keys=[renewed_document_id],
    )

    __table_args__ = (
        Index("idx_document_expiry_date_expired", "expiry_date", "is_expired"),
        Index("idx_document_expiry_days_urgency", "days_until_expiry", "urgency_level"),
        Index("idx_document_expiry_owner", "owner_type", "owner_id"),
    )

    def __repr__(self) -> str:
        return f"<DocumentExpiry(document_id={self.document_id}, days={self.days_until_expiry}, expired={self.is_expired})>"