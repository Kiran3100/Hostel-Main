"""
File Upload Models

Core file metadata and storage tracking with comprehensive
upload session management and validation.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user.user import User
    from app.models.hostel.hostel import Hostel
    from app.models.student.student import Student

__all__ = [
    "FileUpload",
    "UploadSession",
    "FileValidation",
    "UploadProgress",
    "FileQuota",
    "MultipartUpload",
    "MultipartUploadPart",
]


class FileUpload(UUIDMixin, SoftDeleteMixin, TimestampModel, BaseModel):
    """
    Core file metadata and storage tracking.
    
    Stores comprehensive file information including storage location,
    metadata, access control, and processing status.
    """

    __tablename__ = "file_uploads"

    # Primary identification
    file_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique file identifier (UUID)",
    )
    storage_key: Mapped[str] = mapped_column(
        String(500),
        unique=True,
        nullable=False,
        index=True,
        comment="Storage path/key in cloud storage",
    )

    # File metadata
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original filename with extension",
    )
    content_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="MIME type (e.g., image/jpeg, application/pdf)",
    )
    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="File size in bytes",
    )
    extension: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="File extension without dot",
    )
    checksum: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        index=True,
        comment="File checksum (MD5/SHA256) for integrity",
    )
    etag: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="ETag from storage provider",
    )

    # Ownership and context
    uploaded_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who uploaded the file",
    )
    hostel_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Associated hostel (if applicable)",
    )
    student_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Associated student (if applicable)",
    )

    # Logical organization
    folder: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        index=True,
        comment="Logical folder path for organization",
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="File category for classification",
    )
    tags: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Searchable tags",
    )

    # Access control
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether file is publicly accessible",
    )
    public_url: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        comment="Public CDN URL (if is_public=True)",
    )

    # URLs and access
    url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Primary access URL",
    )
    signed_url_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Signed URL expiration (if applicable)",
    )

    # Processing status
    is_processed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether post-upload processing is complete",
    )
    processing_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        index=True,
        comment="Processing status: pending, processing, completed, failed",
    )
    processing_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Processing error message if failed",
    )
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Processing start timestamp",
    )
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Processing completion timestamp",
    )

    # Security
    virus_scan_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        index=True,
        comment="Virus scan status: pending, clean, infected, error, skipped",
    )
    virus_scan_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Virus scan completion timestamp",
    )
    virus_scan_result: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Detailed virus scan result",
    )

    # Access tracking
    access_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of times file was accessed",
    )
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last access timestamp",
    )
    last_accessed_by_user_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who last accessed the file",
    )

    # Custom metadata - RENAMED from 'metadata' to avoid SQLAlchemy reserved name
    file_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Custom metadata key-value pairs",
    )

    # Relationships
    uploaded_by: Mapped["User"] = relationship(
        "User",
        foreign_keys=[uploaded_by_user_id],
        back_populates="uploaded_files",
    )
    hostel: Mapped[Optional["Hostel"]] = relationship(
        "Hostel",
        foreign_keys=[hostel_id],
        back_populates="files",
    )
    student: Mapped[Optional["Student"]] = relationship(
        "Student",
        foreign_keys=[student_id],
        back_populates="files",
    )
    last_accessed_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[last_accessed_by_user_id],
    )

    # Back-references
    upload_session: Mapped[Optional["UploadSession"]] = relationship(
        "UploadSession",
        back_populates="file",
        uselist=False,
    )
    validations: Mapped[List["FileValidation"]] = relationship(
        "FileValidation",
        back_populates="file",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_file_upload_category_status", "category", "processing_status"),
        Index("idx_file_upload_hostel_category", "hostel_id", "category"),
        Index("idx_file_upload_student_category", "student_id", "category"),
        Index("idx_file_upload_uploader_created", "uploaded_by_user_id", "created_at"),
        Index("idx_file_upload_content_type", "content_type"),
        Index("idx_file_upload_virus_scan", "virus_scan_status"),
    )

    def __repr__(self) -> str:
        return f"<FileUpload(file_id={self.file_id}, filename={self.filename})>"


class UploadSession(UUIDMixin, TimestampModel, BaseModel):
    """
    Multi-part upload session management.
    
    Tracks upload sessions including direct uploads and multipart uploads
    with progress monitoring and expiration handling.
    """

    __tablename__ = "upload_sessions"

    # Session identification
    upload_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique upload session identifier",
    )
    session_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Session type: direct, multipart",
    )

    # File reference
    file_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("file_uploads.file_id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
        comment="Associated file after completion",
    )
    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Target storage key",
    )

    # Upload details
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original filename",
    )
    content_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="MIME type",
    )
    expected_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Expected file size",
    )
    actual_size_bytes: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Actual uploaded size",
    )

    # User context
    uploaded_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User initiating upload",
    )

    # Session status
    status: Mapped[str] = mapped_column(
        String(50),
        default="initialized",
        nullable=False,
        index=True,
        comment="Status: initialized, uploading, completed, failed, expired",
    )
    upload_url: Mapped[Optional[str]] = mapped_column(
        String(2000),
        nullable=True,
        comment="Pre-signed upload URL",
    )
    upload_method: Mapped[str] = mapped_column(
        String(10),
        default="PUT",
        nullable=False,
        comment="HTTP method for upload (PUT, POST)",
    )
    upload_headers: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Required headers for upload request",
    )

    # Expiration
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Session expiration timestamp",
    )

    # Completion tracking
    upload_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Upload start timestamp",
    )
    upload_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Upload completion timestamp",
    )

    # Verification
    checksum: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="Expected/actual checksum",
    )
    etag: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="ETag from storage provider",
    )

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if upload failed",
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of retry attempts",
    )

    # Metadata - RENAMED from 'session_metadata' to avoid confusion
    session_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional session metadata",
    )

    # Relationships
    uploaded_by: Mapped["User"] = relationship(
        "User",
        back_populates="upload_sessions",
    )
    file: Mapped[Optional["FileUpload"]] = relationship(
        "FileUpload",
        back_populates="upload_session",
    )
    progress: Mapped[Optional["UploadProgress"]] = relationship(
        "UploadProgress",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )
    multipart_upload: Mapped[Optional["MultipartUpload"]] = relationship(
        "MultipartUpload",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_upload_session_status_expires", "status", "expires_at"),
        Index("idx_upload_session_user_status", "uploaded_by_user_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<UploadSession(upload_id={self.upload_id}, status={self.status})>"


class FileValidation(UUIDMixin, TimestampModel, BaseModel):
    """
    File validation results and checks.
    
    Stores validation results for uploaded files including
    format checks, size validation, and content analysis.
    """

    __tablename__ = "file_validations"

    # File reference
    file_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("file_uploads.file_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Validated file",
    )

    # Validation details
    validation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of validation performed",
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

    # Validation checks
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

    # Extracted metadata
    extracted_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Metadata extracted during validation",
    )
    detected_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Auto-detected file/document type",
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
    validation_duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Validation duration in milliseconds",
    )

    # Validator information
    validator_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Name of validator used",
    )
    validator_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Validator version",
    )

    # Relationships
    file: Mapped["FileUpload"] = relationship(
        "FileUpload",
        back_populates="validations",
    )

    __table_args__ = (
        Index("idx_file_validation_file_type", "file_id", "validation_type"),
        Index("idx_file_validation_valid_type", "is_valid", "validation_type"),
    )

    def __repr__(self) -> str:
        return f"<FileValidation(file_id={self.file_id}, type={self.validation_type}, valid={self.is_valid})>"


class UploadProgress(UUIDMixin, TimestampModel, BaseModel):
    """
    Upload progress tracking for large files.
    
    Monitors real-time upload progress with byte tracking
    and speed calculation.
    """

    __tablename__ = "upload_progress"

    # Session reference
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("upload_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="Upload session being tracked",
    )

    # Progress metrics
    bytes_uploaded: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="Bytes uploaded so far",
    )
    total_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Total bytes to upload",
    )
    progress_percentage: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Upload progress percentage",
    )

    # Speed tracking
    upload_speed_bps: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Current upload speed (bytes per second)",
    )
    average_speed_bps: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Average upload speed",
    )
    estimated_time_remaining_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Estimated seconds until completion",
    )

    # Chunk tracking
    chunks_uploaded: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of chunks uploaded",
    )
    total_chunks: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Total number of chunks",
    )

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Upload start time",
    )
    last_update_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Last progress update",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Upload completion time",
    )

    # Status
    is_paused: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether upload is paused",
    )
    is_stalled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether upload appears stalled",
    )

    # Relationships
    session: Mapped["UploadSession"] = relationship(
        "UploadSession",
        back_populates="progress",
    )

    def __repr__(self) -> str:
        return f"<UploadProgress(session_id={self.session_id}, progress={self.progress_percentage}%)>"


class FileQuota(UUIDMixin, TimestampModel, BaseModel):
    """
    Storage quota management per tenant/user.
    
    Tracks storage usage against allocated quotas with
    enforcement and alerting.
    """

    __tablename__ = "file_quotas"

    # Owner identification
    owner_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Owner type: user, hostel, tenant, system",
    )
    owner_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        comment="Owner identifier",
    )

    # Quota limits
    quota_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Total allocated storage in bytes",
    )
    used_bytes: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="Currently used storage in bytes",
    )
    reserved_bytes: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="Reserved storage (pending uploads)",
    )

    # File count limits
    max_files: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum number of files allowed",
    )
    current_file_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Current number of files",
    )

    # Per-file limits
    max_file_size_bytes: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Maximum size per file",
    )

    # Usage tracking
    last_usage_update_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last usage calculation timestamp",
    )

    # Alerts
    alert_threshold_percentage: Mapped[int] = mapped_column(
        Integer,
        default=80,
        nullable=False,
        comment="Usage percentage to trigger alert",
    )
    alert_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last alert sent timestamp",
    )

    # Enforcement
    is_enforced: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether quota is actively enforced",
    )
    is_exceeded: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether quota is currently exceeded",
    )

    # Metadata
    quota_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional quota configuration",
    )

    __table_args__ = (
        UniqueConstraint("owner_type", "owner_id", name="uq_file_quota_owner"),
        Index("idx_file_quota_exceeded", "is_exceeded", "is_enforced"),
    )

    def __repr__(self) -> str:
        usage_pct = (self.used_bytes / self.quota_bytes * 100) if self.quota_bytes > 0 else 0
        return f"<FileQuota(owner={self.owner_type}:{self.owner_id}, usage={usage_pct:.1f}%)>"


class MultipartUpload(UUIDMixin, TimestampModel, BaseModel):
    """
    Multipart upload management for large files.
    
    Handles chunked uploads with part tracking and assembly.
    """

    __tablename__ = "multipart_uploads"

    # Session reference
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("upload_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="Upload session",
    )

    # Multipart details
    multipart_upload_id: Mapped[str] = mapped_column(
        String(200),
        unique=True,
        nullable=False,
        comment="Storage provider multipart upload ID",
    )
    total_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Total file size",
    )
    part_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Size of each part",
    )
    total_parts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Total number of parts",
    )

    # Progress
    uploaded_parts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of successfully uploaded parts",
    )
    uploaded_bytes: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        comment="Total bytes uploaded",
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        default="in_progress",
        nullable=False,
        index=True,
        comment="Status: in_progress, assembling, completed, failed, aborted",
    )

    # Assembly
    assembly_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Part assembly start time",
    )
    assembly_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Part assembly completion time",
    )

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if upload failed",
    )

    # Relationships
    session: Mapped["UploadSession"] = relationship(
        "UploadSession",
        back_populates="multipart_upload",
    )
    parts: Mapped[List["MultipartUploadPart"]] = relationship(
        "MultipartUploadPart",
        back_populates="multipart_upload",
        cascade="all, delete-orphan",
        order_by="MultipartUploadPart.part_number",
    )

    __table_args__ = (
        Index("idx_multipart_upload_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<MultipartUpload(id={self.multipart_upload_id}, parts={self.uploaded_parts}/{self.total_parts})>"


class MultipartUploadPart(UUIDMixin, TimestampModel, BaseModel):
    """
    Individual part in multipart upload.
    
    Tracks each chunk with pre-signed URL and upload status.
    """

    __tablename__ = "multipart_upload_parts"

    # Multipart reference
    multipart_upload_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("multipart_uploads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent multipart upload",
    )

    # Part details
    part_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Part number (1-based)",
    )
    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Size of this part",
    )

    # Upload URL
    upload_url: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
        comment="Pre-signed URL for this part",
    )
    url_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="URL expiration timestamp",
    )

    # Upload status
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        index=True,
        comment="Status: pending, uploading, completed, failed",
    )
    uploaded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Part upload completion time",
    )

    # Verification
    etag: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="ETag from storage provider",
    )
    checksum: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="Part checksum",
    )

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of upload attempts",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if upload failed",
    )

    # Relationships
    multipart_upload: Mapped["MultipartUpload"] = relationship(
        "MultipartUpload",
        back_populates="parts",
    )

    __table_args__ = (
        UniqueConstraint(
            "multipart_upload_id",
            "part_number",
            name="uq_multipart_part_number",
        ),
        Index("idx_multipart_part_status", "multipart_upload_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<MultipartUploadPart(part={self.part_number}, status={self.status})>"