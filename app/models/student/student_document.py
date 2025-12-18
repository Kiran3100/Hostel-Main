# --- File: C:\Hostel-Main\app\models\student\student_document.py ---
"""
Student document model.

Manages document uploads, verification, and lifecycle for students.
Supports various document types required for admission and compliance.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.student.student import Student
    from app.models.user.user import User


class StudentDocument(BaseModel, TimestampMixin, SoftDeleteMixin):
    """
    Student document model.
    
    Stores all documents uploaded by or for students including
    identification, educational, employment, and other supporting documents.
    
    Document Types:
        - id_proof: Government ID (Aadhaar, Passport, DL, etc.)
        - address_proof: Address verification documents
        - photo: Passport-size photograph
        - institutional_id: College/University ID card
        - company_id: Company/Office ID card
        - medical_certificate: Medical documents
        - police_verification: Police verification (if required)
        - other: Other supporting documents
    
    Document Lifecycle:
        1. Upload → Pending verification
        2. Verification → Approved/Rejected
        3. Expiry tracking (for documents with expiry)
        4. Renewal/replacement
    """

    __tablename__ = "student_documents"

    # Foreign Keys
    student_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to student",
    )

    # Document Metadata
    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Document type/category",
    )
    
    document_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Document display name",
    )
    
    document_url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Document storage URL",
    )
    
    document_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Document number/reference (if applicable)",
    )

    # File Information
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original file name",
    )
    
    file_size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="File size in bytes",
    )
    
    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="MIME type (application/pdf, image/jpeg, etc.)",
    )
    
    file_extension: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="File extension (.pdf, .jpg, etc.)",
    )

    # Upload Information
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Upload timestamp",
    )
    
    uploaded_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="User who uploaded (student or admin)",
    )
    
    upload_source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="web",
        comment="Upload source (web, mobile, admin)",
    )
    
    upload_ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IP address from where uploaded",
    )

    # Verification
    verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Verification status",
    )
    
    verified_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who verified",
    )
    
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Verification timestamp",
    )
    
    verification_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Verification status (pending, approved, rejected)",
    )
    
    verification_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Verification notes/comments",
    )
    
    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for rejection (if rejected)",
    )

    # Document Validity
    issue_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Document issue date",
    )
    
    expiry_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Document expiry date (if applicable)",
    )
    
    is_expired: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether document is expired",
    )
    
    expiry_notified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether expiry notification sent",
    )

    # Document Replacement/Renewal
    replaced_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("student_documents.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID of document that replaced this one",
    )
    
    replaces: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("student_documents.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID of document this replaces",
    )
    
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="Document version number",
    )

    # Additional Metadata
    is_mandatory: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether this is a mandatory document",
    )
    
    is_confidential: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether document contains confidential information",
    )
    
    tags: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Comma-separated tags for categorization",
    )
    
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Document description/notes",
    )
    
    ocr_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Extracted text from OCR (if processed)",
    )
    
    ocr_processed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether OCR processing is done",
    )

    # Access Control
    visible_to_student: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether student can view this document",
    )
    
    downloadable: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether document can be downloaded",
    )
    
    download_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times downloaded",
    )
    
    last_downloaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last download timestamp",
    )

    # Compliance and Audit
    compliance_checked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether compliance check is done",
    )
    
    compliance_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Compliance status",
    )
    
    audit_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Audit notes and compliance remarks",
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="documents",
        lazy="joined",
    )
    
    uploader: Mapped["User"] = relationship(
        "User",
        foreign_keys=[uploaded_by],
        lazy="select",
    )
    
    verifier: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[verified_by],
        lazy="select",
    )
    
    replaced_by_document: Mapped["StudentDocument | None"] = relationship(
        "StudentDocument",
        foreign_keys=[replaced_by],
        remote_side="StudentDocument.id",
        lazy="select",
    )
    
    replaces_document: Mapped["StudentDocument | None"] = relationship(
        "StudentDocument",
        foreign_keys=[replaces],
        remote_side="StudentDocument.id",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<StudentDocument(id={self.id}, student_id={self.student_id}, "
            f"type={self.document_type}, verified={self.verified})>"
        )

    @property
    def is_image(self) -> bool:
        """Check if document is an image."""
        image_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
        return self.mime_type in image_types if self.mime_type else False

    @property
    def is_pdf(self) -> bool:
        """Check if document is a PDF."""
        return self.mime_type == "application/pdf" if self.mime_type else False

    @property
    def file_size_mb(self) -> float | None:
        """Get file size in MB."""
        if self.file_size_bytes:
            return round(self.file_size_bytes / (1024 * 1024), 2)
        return None

    @property
    def days_until_expiry(self) -> int | None:
        """Calculate days until document expiry."""
        if not self.expiry_date:
            return None
        
        delta = self.expiry_date - datetime.utcnow()
        return delta.days

    @property
    def is_expiring_soon(self) -> bool:
        """Check if document is expiring within 30 days."""
        if days := self.days_until_expiry:
            return 0 < days <= 30
        return False

    @property
    def verification_pending(self) -> bool:
        """Check if verification is pending."""
        return self.verification_status == "pending"

    @property
    def is_current_version(self) -> bool:
        """Check if this is the current version (not replaced)."""
        return self.replaced_by is None
