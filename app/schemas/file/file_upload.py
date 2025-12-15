"""
Generic file upload schemas with comprehensive validation.

Handles file upload initialization, completion, and validation
for various storage backends (S3, GCS, Azure Blob, etc.).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field, HttpUrl, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema

__all__ = [
    "FileUploadInitRequest",
    "FileUploadInitResponse",
    "FileUploadCompleteRequest",
    "FileUploadCompleteResponse",
    "MultipartUploadInitRequest",
    "MultipartUploadPart",
    "MultipartUploadCompleteRequest",
]


class FileUploadInitRequest(BaseCreateSchema):
    """
    Request to initialize a file upload.
    
    Generates pre-signed URLs or prepares upload session
    for direct-to-storage uploads.
    """

    filename: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Original filename with extension",
    )
    content_type: str = Field(
        ...,
        max_length=255,
        description="MIME type (e.g., 'image/jpeg', 'application/pdf')",
    )
    size_bytes: int = Field(
        ...,
        ge=1,
        le=100 * 1024 * 1024,  # 100 MB default max
        description="File size in bytes (max 100MB)",
    )

    # Logical organization
    folder: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Logical folder path (e.g., 'hostels/123/documents')",
    )

    # Ownership context
    uploaded_by_user_id: str = Field(
        ...,
        description="User ID initiating the upload",
    )
    hostel_id: Optional[str] = Field(
        default=None,
        description="Associated hostel ID (if applicable)",
    )
    student_id: Optional[str] = Field(
        default=None,
        description="Associated student ID (if applicable)",
    )

    # Classification
    category: Optional[str] = Field(
        default=None,
        max_length=50,
        description="File category for organization",
    )
    tags: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Searchable tags (max 20)",
    )

    # Access control
    is_public: bool = Field(
        default=False,
        description="Whether file should be publicly accessible",
    )

    # Advanced options
    enable_virus_scan: bool = Field(
        default=True,
        description="Enable antivirus scanning on upload",
    )
    auto_optimize: bool = Field(
        default=False,
        description="Auto-optimize file (compression, format conversion)",
    )

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """
        Validate and sanitize filename.
        
        Prevents path traversal and dangerous characters.
        """
        v = v.strip()
        if not v:
            raise ValueError("Filename cannot be empty")
        
        # Block dangerous characters
        dangerous_chars = ["<", ">", ":", '"', "|", "?", "*", "/", "\\"]
        if any(char in v for char in dangerous_chars):
            raise ValueError(
                f"Filename contains invalid characters: {dangerous_chars}"
            )
        
        # Block path traversal attempts
        if ".." in v or v.startswith("."):
            raise ValueError("Filename cannot contain '..' or start with '.'")
        
        # Validate extension exists
        if "." not in v:
            raise ValueError("Filename must include an extension")
        
        return v

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        """Validate MIME type format."""
        v = v.lower().strip()
        
        # Basic MIME type validation
        if "/" not in v:
            raise ValueError("Invalid MIME type format (must contain '/')")
        
        parts = v.split("/")
        if len(parts) != 2:
            raise ValueError("Invalid MIME type format")
        
        # Validate main type
        valid_main_types = [
            "image", "video", "audio", "application",
            "text", "multipart", "message",
        ]
        if parts[0] not in valid_main_types:
            raise ValueError(f"Unsupported MIME type category: {parts[0]}")
        
        return v

    @field_validator("folder")
    @classmethod
    def validate_folder(cls, v: Optional[str]) -> Optional[str]:
        """Validate folder path."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            
            # Normalize path separators
            v = v.replace("\\", "/")
            
            # Remove leading/trailing slashes
            v = v.strip("/")
            
            # Block path traversal
            if ".." in v:
                raise ValueError("Folder path cannot contain '..'")
            
            # Block absolute paths
            if v.startswith("/"):
                raise ValueError("Folder path cannot be absolute")
        
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate and normalize tags."""
        if len(v) > 20:
            raise ValueError("Maximum 20 tags allowed")
        
        # Normalize and validate each tag
        normalized_tags = []
        for tag in v:
            tag = tag.strip().lower()
            if tag:
                if len(tag) > 50:
                    raise ValueError("Tag length cannot exceed 50 characters")
                if " " in tag:
                    raise ValueError("Tags cannot contain spaces")
                normalized_tags.append(tag)
        
        # Remove duplicates while preserving order
        seen: set[str] = set()
        unique_tags: List[str] = []
        for tag in normalized_tags:
            if tag not in seen:
                seen.add(tag)
                unique_tags.append(tag)
        
        return unique_tags

    @model_validator(mode="after")
    def validate_size_for_type(self) -> "FileUploadInitRequest":
        """
        Validate file size is appropriate for content type.
        
        Different file types have different reasonable size limits.
        """
        size_limits = {
            "image/": 20 * 1024 * 1024,      # 20 MB for images
            "video/": 100 * 1024 * 1024,     # 100 MB for videos
            "audio/": 50 * 1024 * 1024,      # 50 MB for audio
            "application/pdf": 25 * 1024 * 1024,  # 25 MB for PDFs
            "text/": 10 * 1024 * 1024,       # 10 MB for text
        }
        
        for prefix, limit in size_limits.items():
            if self.content_type.startswith(prefix):
                if self.size_bytes > limit:
                    raise ValueError(
                        f"File size ({self.size_bytes / (1024*1024):.2f} MB) "
                        f"exceeds limit for {prefix} files "
                        f"({limit / (1024*1024):.0f} MB)"
                    )
                break
        
        return self


class FileUploadInitResponse(BaseResponseSchema):
    """
    Response for file upload initialization.
    
    Provides pre-signed URL and upload instructions.
    """

    upload_id: str = Field(
        ...,
        description="Unique upload session identifier",
    )
    storage_key: str = Field(
        ...,
        description="Storage path/key for the file",
    )

    # Direct upload information
    upload_url: Optional[HttpUrl] = Field(
        default=None,
        description="Pre-signed URL for direct upload to storage",
    )
    upload_method: str = Field(
        default="PUT",
        pattern=r"^(PUT|POST)$",
        description="HTTP method for upload (PUT or POST)",
    )
    upload_headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Required headers for upload request",
    )

    # File information
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(..., description="Expected file size")

    # Access information
    is_public: bool = Field(..., description="Public access flag")
    public_url: Optional[HttpUrl] = Field(
        default=None,
        description="Public URL (if is_public=True)",
    )

    # Upload constraints
    expires_at: datetime = Field(
        ...,
        description="Upload URL expiration timestamp",
    )
    max_file_size: int = Field(
        ...,
        description="Maximum allowed file size for this upload",
    )

    # Processing hints
    will_scan_virus: bool = Field(
        default=True,
        description="Whether file will be scanned for viruses",
    )
    will_optimize: bool = Field(
        default=False,
        description="Whether file will be auto-optimized",
    )


class FileUploadCompleteRequest(BaseCreateSchema):
    """
    Notify backend that upload is complete.
    
    Triggers post-upload processing and validation.
    """

    upload_id: str = Field(
        ...,
        description="Upload session ID from init response",
    )
    storage_key: str = Field(
        ...,
        description="Storage key from init response",
    )

    uploaded_by_user_id: str = Field(
        ...,
        description="User who completed the upload",
    )

    # Verification
    checksum: Optional[str] = Field(
        default=None,
        max_length=128,
        description="File checksum (MD5/SHA256) for integrity verification",
    )
    etag: Optional[str] = Field(
        default=None,
        max_length=128,
        description="ETag from storage provider",
    )

    # Optional metadata
    actual_size_bytes: Optional[int] = Field(
        default=None,
        ge=1,
        description="Actual uploaded file size (for verification)",
    )

    @field_validator("checksum", "etag")
    @classmethod
    def validate_hash(cls, v: Optional[str]) -> Optional[str]:
        """Validate checksum/etag format."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
            # Basic hex validation
            if not all(c in "0123456789abcdefABCDEF" for c in v):
                raise ValueError("Checksum must be hexadecimal")
        return v


class FileUploadCompleteResponse(BaseSchema):
    """
    Response after successful upload completion.
    
    Provides file access information and processing status.
    """

    file_id: str = Field(..., description="Unique file identifier")
    storage_key: str = Field(..., description="Storage path/key")

    # Access URLs
    url: HttpUrl = Field(..., description="File access URL")
    public_url: Optional[HttpUrl] = Field(
        default=None,
        description="Public CDN URL (if applicable)",
    )

    # File metadata
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(..., description="Actual file size")

    # Processing status
    processing_status: str = Field(
        default="completed",
        description="Post-upload processing status",
    )
    virus_scan_status: str = Field(
        default="pending",
        description="Virus scan status",
    )

    uploaded_at: datetime = Field(..., description="Upload completion timestamp")

    message: str = Field(
        default="File uploaded successfully",
        description="Success message",
    )


class MultipartUploadInitRequest(BaseCreateSchema):
    """
    Initialize multipart upload for large files.
    
    Enables chunked uploads for files over a certain size threshold.
    """

    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., max_length=255)
    total_size_bytes: int = Field(
        ...,
        ge=5 * 1024 * 1024,  # Minimum 5 MB for multipart
        le=5 * 1024 * 1024 * 1024,  # Maximum 5 GB
        description="Total file size (5 MB - 5 GB)",
    )

    # Chunk configuration
    part_size_bytes: int = Field(
        default=5 * 1024 * 1024,
        ge=5 * 1024 * 1024,
        le=100 * 1024 * 1024,
        description="Size of each part (5 MB - 100 MB)",
    )

    uploaded_by_user_id: str = Field(...)
    hostel_id: Optional[str] = Field(default=None)

    category: Optional[str] = Field(default=None, max_length=50)
    is_public: bool = Field(default=False)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename (same as regular upload)."""
        v = v.strip()
        if not v:
            raise ValueError("Filename cannot be empty")
        
        dangerous_chars = ["<", ">", ":", '"', "|", "?", "*", "/", "\\"]
        if any(char in v for char in dangerous_chars):
            raise ValueError("Filename contains invalid characters")
        
        if ".." in v or v.startswith("."):
            raise ValueError("Invalid filename pattern")
        
        return v


class MultipartUploadPart(BaseSchema):
    """
    Pre-signed URL for a single multipart upload part.
    
    Each part can be uploaded independently.
    """

    part_number: int = Field(
        ...,
        ge=1,
        le=10000,
        description="Part number (1-10000)",
    )
    upload_url: HttpUrl = Field(..., description="Pre-signed URL for this part")
    size_bytes: int = Field(..., ge=1, description="Expected size for this part")

    expires_at: datetime = Field(..., description="URL expiration timestamp")


class MultipartUploadCompleteRequest(BaseCreateSchema):
    """
    Complete multipart upload after all parts uploaded.
    
    Combines all parts into final file.
    """

    upload_id: str = Field(..., description="Multipart upload session ID")
    storage_key: str = Field(..., description="Storage key")

    uploaded_by_user_id: str = Field(...)

    # Part verification
    parts: List[Dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="List of uploaded parts with ETags",
    )

    @field_validator("parts")
    @classmethod
    def validate_parts(cls, v: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate parts list contains required fields."""
        for i, part in enumerate(v, 1):
            if "part_number" not in part or "etag" not in part:
                raise ValueError(
                    f"Part {i} missing required fields (part_number, etag)"
                )
            
            try:
                part_num = int(part["part_number"])
                if part_num < 1:
                    raise ValueError(f"Invalid part_number: {part_num}")
            except (ValueError, TypeError):
                raise ValueError(f"Invalid part_number in part {i}")
        
        return v