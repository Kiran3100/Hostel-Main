"""
Student document schemas for API compatibility and document management.

Provides schemas for document upload, verification, and management operations.
Maps to existing DocumentInfo and DocumentUploadRequest schemas while providing
API-specific interfaces.
"""

from datetime import datetime
from typing import Union, List
from enum import Enum

from pydantic import Field, field_validator, model_validator, ConfigDict, HttpUrl

from app.schemas.common.base import (
    BaseSchema,
    BaseCreateSchema,
    BaseUpdateSchema,
    BaseResponseSchema,
)

__all__ = [
    "DocumentType",
    "DocumentVerificationStatus", 
    "StudentDocument",
    "StudentDocumentCreate",
    "StudentDocumentUpdate",
    "DocumentVerificationRequest",
    "DocumentListResponse",
]


class DocumentType(str, Enum):
    """
    Document types for student documents.
    
    Defines the categories of documents that can be uploaded for students.
    """
    
    ID_PROOF = "id_proof"
    ADDRESS_PROOF = "address_proof"
    PHOTO = "photo"
    INSTITUTIONAL_ID = "institutional_id"
    COMPANY_ID = "company_id"
    ACADEMIC_CERTIFICATE = "academic_certificate"
    MEDICAL_RECORD = "medical_record"
    INCOME_CERTIFICATE = "income_certificate"
    BIRTH_CERTIFICATE = "birth_certificate"
    PASSPORT = "passport"
    VISA = "visa"
    OTHER = "other"


class DocumentVerificationStatus(str, Enum):
    """
    Document verification status enumeration.
    
    Tracks the verification state of uploaded documents.
    """
    
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"
    UNDER_REVIEW = "under_review"


class StudentDocument(BaseResponseSchema):
    """
    Student document response schema.
    
    Represents a document associated with a student including metadata
    and verification status. Maps to existing DocumentInfo schema.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=True,
    )

    id: str = Field(..., description="Document ID")
    student_id: str = Field(..., description="Student ID")
    student_name: Union[str, None] = Field(
        default=None,
        description="Student name for reference",
    )

    # Document details
    document_type: DocumentType = Field(..., description="Document type/category")
    document_name: str = Field(..., description="Document display name")
    document_url: HttpUrl = Field(..., description="Document storage URL")
    
    # File metadata
    file_size_bytes: Union[int, None] = Field(
        default=None,
        ge=0,
        description="File size in bytes",
    )
    mime_type: Union[str, None] = Field(
        default=None,
        description="MIME type of the document",
        examples=["application/pdf", "image/jpeg", "image/png"],
    )
    file_extension: Union[str, None] = Field(
        default=None,
        description="File extension",
    )

    # Upload information
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    uploaded_by: str = Field(..., description="User ID who uploaded")
    uploaded_by_name: Union[str, None] = Field(
        default=None,
        description="Name of uploader",
    )

    # Verification details
    verified: bool = Field(
        default=False,
        description="Whether document is verified",
    )
    verification_status: DocumentVerificationStatus = Field(
        default=DocumentVerificationStatus.PENDING,
        description="Detailed verification status",
    )
    verified_by: Union[str, None] = Field(
        default=None,
        description="Admin who verified",
    )
    verified_by_name: Union[str, None] = Field(
        default=None,
        description="Name of verifier",
    )
    verified_at: Union[datetime, None] = Field(
        default=None,
        description="Verification timestamp",
    )
    verification_notes: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Verification notes or rejection reason",
    )

    # Expiry information
    expiry_date: Union[datetime, None] = Field(
        default=None,
        description="Document expiry date (for ID documents)",
    )
    is_expired: bool = Field(
        default=False,
        description="Whether document has expired",
    )

    # Additional metadata
    tags: List[str] = Field(
        default_factory=list,
        description="Document tags for categorization",
    )
    description: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Additional document description",
    )
    is_required: bool = Field(
        default=False,
        description="Whether this document type is required",
    )

    @property
    def file_size_readable(self) -> Union[str, None]:
        """Get human-readable file size."""
        if not self.file_size_bytes:
            return None
        
        if self.file_size_bytes < 1024:
            return f"{self.file_size_bytes} B"
        elif self.file_size_bytes < 1024 * 1024:
            return f"{self.file_size_bytes / 1024:.1f} KB"
        else:
            return f"{self.file_size_bytes / (1024 * 1024):.1f} MB"


class StudentDocumentCreate(BaseCreateSchema):
    """
    Create student document request.
    
    Used after file upload to register document in the system.
    Maps to existing DocumentUploadRequest schema.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    student_id: str = Field(..., description="Student ID")
    document_type: DocumentType = Field(..., description="Document type/category")
    document_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Document display name",
    )
    document_url: HttpUrl = Field(
        ...,
        description="Document URL after upload to storage",
    )
    
    # File metadata
    file_size_bytes: Union[int, None] = Field(
        default=None,
        ge=0,
        le=10485760,  # 10MB limit
        description="File size in bytes (max 10MB)",
    )
    mime_type: Union[str, None] = Field(
        default=None,
        description="MIME type of uploaded file",
    )
    
    # Optional metadata
    description: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Document description",
    )
    expiry_date: Union[datetime, None] = Field(
        default=None,
        description="Document expiry date (for ID documents)",
    )
    tags: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Document tags (max 10)",
    )
    
    # Upload context
    notes: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Upload notes",
    )

    @field_validator("document_name")
    @classmethod
    def validate_document_name(cls, v: str) -> str:
        """Validate and normalize document name."""
        v = v.strip()
        if not v:
            raise ValueError("Document name cannot be empty")
        return " ".join(v.split())

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate MIME type is allowed."""
        if v is not None:
            allowed_types = [
                "application/pdf",
                "image/jpeg",
                "image/jpg", 
                "image/png",
                "image/webp",
                "image/gif",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ]
            if v.lower() not in allowed_types:
                raise ValueError(
                    f"MIME type must be one of: {', '.join(allowed_types)}"
                )
        return v

    @field_validator("expiry_date")
    @classmethod
    def validate_expiry_date(cls, v: Union[datetime, None]) -> Union[datetime, None]:
        """Validate expiry date is in the future."""
        if v is not None:
            if v < datetime.now():
                raise ValueError("Document expiry date cannot be in the past")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate and normalize tags."""
        if not v:
            return v
        
        # Normalize tags
        normalized = []
        for tag in v:
            tag = tag.strip().lower()
            if tag and len(tag) <= 50:  # Max tag length
                normalized.append(tag)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_tags = []
        for tag in normalized:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)
                
        return unique_tags


class StudentDocumentUpdate(BaseUpdateSchema):
    """
    Update student document metadata.
    
    Allows updating document information without re-uploading the file.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    document_name: Union[str, None] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated document name",
    )
    description: Union[str, None] = Field(
        default=None,
        max_length=1000,
        description="Updated description",
    )
    tags: Union[List[str], None] = Field(
        default=None,
        max_length=10,
        description="Updated tags",
    )
    expiry_date: Union[datetime, None] = Field(
        default=None,
        description="Updated expiry date",
    )
    notes: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Additional notes",
    )

    # Apply same validators as create schema
    @field_validator("document_name")
    @classmethod
    def validate_document_name(cls, v: Union[str, None]) -> Union[str, None]:
        if v is not None:
            return StudentDocumentCreate.validate_document_name(v)
        return v

    @field_validator("expiry_date")
    @classmethod
    def validate_expiry_date(cls, v: Union[datetime, None]) -> Union[datetime, None]:
        return StudentDocumentCreate.validate_expiry_date(v)

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Union[List[str], None]) -> Union[List[str], None]:
        if v is not None:
            return StudentDocumentCreate.validate_tags(v)
        return v


class DocumentVerificationRequest(BaseCreateSchema):
    """
    Document verification request.
    
    Used by admins to verify or reject uploaded documents.
    Maps to existing DocumentVerificationRequest schema.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    document_id: str = Field(..., description="Document ID to verify")
    verification_status: DocumentVerificationStatus = Field(
        ...,
        description="Verification decision",
    )
    verification_notes: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Verification notes or rejection reason",
    )
    
    # For rejected documents
    rejection_reason: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Detailed rejection reason",
    )
    
    # For verification issues
    requires_resubmission: bool = Field(
        default=False,
        description="Whether document needs to be resubmitted",
    )

    @model_validator(mode="after")
    def validate_rejection_reason(self) -> "DocumentVerificationRequest":
        """Require rejection reason for rejected documents."""
        if (
            self.verification_status == DocumentVerificationStatus.REJECTED
            and not self.rejection_reason
        ):
            raise ValueError(
                "Rejection reason is required when rejecting a document"
            )
        return self


class DocumentListResponse(BaseSchema):
    """
    Response for document listing.
    
    Provides document list with summary information.
    """

    student_id: str = Field(..., description="Student ID")
    student_name: str = Field(..., description="Student name")
    
    documents: List[StudentDocument] = Field(
        default_factory=list,
        description="List of documents",
    )
    
    # Summary statistics
    total_documents: int = Field(
        default=0,
        ge=0,
        description="Total number of documents",
    )
    verified_documents: int = Field(
        default=0,
        ge=0,
        description="Number of verified documents",
    )
    pending_verification: int = Field(
        default=0,
        ge=0,
        description="Documents pending verification",
    )
    rejected_documents: int = Field(
        default=0,
        ge=0,
        description="Number of rejected documents",
    )
    expired_documents: int = Field(
        default=0,
        ge=0,
        description="Number of expired documents",
    )
    
    # Required documents check
    required_documents_uploaded: bool = Field(
        default=False,
        description="Whether all required documents are uploaded",
    )
    missing_required_documents: List[DocumentType] = Field(
        default_factory=list,
        description="List of missing required document types",
    )

    @property
    def verification_completion_rate(self) -> float:
        """Calculate verification completion percentage."""
        if self.total_documents == 0:
            return 0.0
        return (self.verified_documents / self.total_documents) * 100

    @property
    def has_pending_verifications(self) -> bool:
        """Check if there are pending verifications."""
        return self.pending_verification > 0

    @property
    def has_rejected_documents(self) -> bool:
        """Check if there are rejected documents."""
        return self.rejected_documents > 0