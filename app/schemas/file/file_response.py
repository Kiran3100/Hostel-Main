"""
File information and listing schemas.

Provides comprehensive file metadata and listing capabilities
with filtering and pagination support.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Union

from pydantic import Field, HttpUrl, computed_field, field_validator

from app.schemas.common.base import BaseResponseSchema, BaseSchema

__all__ = [
    "FileMetadata",
    "FileInfo",
    "FileURL",
    "FileListResponse",
    "FileStats",
    "FileAccessLog",
]


class FileMetadata(BaseSchema):
    """
    Comprehensive file metadata.
    
    Stores technical and business metadata for files.
    """

    # Technical metadata
    content_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    checksum: Union[str, None] = Field(
        default=None,
        description="File checksum (MD5/SHA256)",
    )

    # Original file information
    original_filename: Union[str, None] = Field(
        default=None,
        max_length=255,
        description="Original uploaded filename",
    )
    extension: Union[str, None] = Field(
        default=None,
        max_length=20,
        description="File extension (without dot)",
    )

    # Dimensions (for images/videos)
    width: Union[int, None] = Field(default=None, ge=1, description="Width in pixels")
    height: Union[int, None] = Field(default=None, ge=1, description="Height in pixels")
    duration_seconds: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Duration for audio/video files",
    )

    # Classification
    category: Union[str, None] = Field(default=None, description="File category")
    tags: List[str] = Field(default_factory=list, description="Searchable tags")

    # Custom metadata
    custom_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Custom key-value metadata",
    )

    # Processing information
    is_processed: bool = Field(
        default=False,
        description="Whether post-upload processing is complete",
    )
    processing_error: Union[str, None] = Field(
        default=None,
        description="Processing error message if failed",
    )

    @computed_field
    @property
    def size_mb(self) -> Decimal:
        """Get file size in megabytes."""
        return Decimal(str(round(self.size_bytes / (1024 * 1024), 2)))

    @computed_field
    @property
    def is_image(self) -> bool:
        """Check if file is an image."""
        return self.content_type.startswith("image/")

    @computed_field
    @property
    def is_video(self) -> bool:
        """Check if file is a video."""
        return self.content_type.startswith("video/")

    @computed_field
    @property
    def is_audio(self) -> bool:
        """Check if file is audio."""
        return self.content_type.startswith("audio/")

    @computed_field
    @property
    def is_document(self) -> bool:
        """Check if file is a document."""
        document_types = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument",
            "application/vnd.ms-excel",
        ]
        return any(self.content_type.startswith(dt) for dt in document_types)


class FileInfo(BaseResponseSchema):
    """
    Complete file information record.
    
    Represents a stored file with all associated metadata.
    """

    file_id: str = Field(..., description="Unique file identifier")
    storage_key: str = Field(..., description="Storage path/key")

    # Ownership
    uploaded_by_user_id: str = Field(..., description="Uploader user ID")
    uploaded_by_name: Union[str, None] = Field(default=None, description="Uploader name")

    hostel_id: Union[str, None] = Field(default=None, description="Associated hostel")
    student_id: Union[str, None] = Field(default=None, description="Associated student")

    # Access control
    is_public: bool = Field(default=False, description="Public access flag")
    is_deleted: bool = Field(default=False, description="Soft delete flag")

    # URLs
    url: HttpUrl = Field(..., description="Primary access URL")
    public_url: Union[HttpUrl, None] = Field(
        default=None,
        description="Public CDN URL (if is_public=True)",
    )
    thumbnail_url: Union[HttpUrl, None] = Field(
        default=None,
        description="Thumbnail URL (for images)",
    )

    # Metadata
    metadata: FileMetadata = Field(..., description="File metadata")

    # Security
    virus_scan_status: str = Field(
        default="pending",
        description="Antivirus scan status",
    )
    virus_scan_timestamp: Union[datetime, None] = Field(
        default=None,
        description="Virus scan completion timestamp",
    )

    # Access tracking
    access_count: int = Field(
        default=0,
        ge=0,
        description="Number of times file was accessed",
    )
    last_accessed_at: Union[datetime, None] = Field(
        default=None,
        description="Last access timestamp",
    )

    # Audit timestamps
    created_at: datetime = Field(..., description="Upload timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    deleted_at: Union[datetime, None] = Field(default=None, description="Deletion timestamp")

    @computed_field
    @property
    def age_days(self) -> int:
        """Get file age in days."""
        now = datetime.now(timezone.utc)
        # Handle timezone-aware comparison
        created = self.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        delta = now - created
        return delta.days

    @computed_field
    @property
    def is_recent(self) -> bool:
        """Check if file was uploaded within last 7 days."""
        return self.age_days <= 7


class FileURL(BaseSchema):
    """
    File access URL with expiration information.
    
    Used for temporary signed URLs.
    """

    url: HttpUrl = Field(..., description="Access URL")
    url_type: str = Field(
        default="signed",
        description="URL type",
    )

    expires_at: Union[datetime, None] = Field(
        default=None,
        description="URL expiration timestamp (for signed URLs)",
    )
    is_permanent: bool = Field(
        default=False,
        description="Whether URL is permanent (public URLs)",
    )

    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if URL has expired."""
        if self.is_permanent or self.expires_at is None:
            return False
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now >= expires

    @computed_field
    @property
    def time_until_expiry_minutes(self) -> Union[int, None]:
        """Get minutes until URL expires."""
        if self.is_permanent or self.expires_at is None:
            return None
        
        now = datetime.now(timezone.utc)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        
        delta = expires - now
        return max(0, int(delta.total_seconds() / 60))


class FileListResponse(BaseSchema):
    """
    Paginated file listing response.
    
    Provides filtered and sorted file listings.
    """

    items: List[FileInfo] = Field(
        default_factory=list,
        description="List of files",
    )

    # Pagination
    total_items: int = Field(..., ge=0, description="Total matching files")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total pages")

    # Summary statistics
    total_size_bytes: int = Field(
        default=0,
        ge=0,
        description="Total size of all files in list",
    )

    @computed_field
    @property
    def has_next(self) -> bool:
        """Check if there are more pages."""
        return self.page < self.total_pages

    @computed_field
    @property
    def has_previous(self) -> bool:
        """Check if there are previous pages."""
        return self.page > 1

    @computed_field
    @property
    def total_size_mb(self) -> Decimal:
        """Get total size in megabytes."""
        return Decimal(str(round(self.total_size_bytes / (1024 * 1024), 2)))


class FileStats(BaseSchema):
    """
    File storage statistics.
    
    Provides aggregate statistics for a user, hostel, or system.
    """

    entity_id: Union[str, None] = Field(
        default=None,
        description="Entity ID (user/hostel) or None for system-wide",
    )
    entity_type: str = Field(
        default="system",
        description="Entity type",
    )

    # Counts
    total_files: int = Field(..., ge=0, description="Total file count")
    public_files: int = Field(..., ge=0, description="Public file count")
    private_files: int = Field(..., ge=0, description="Private file count")

    # By type
    images_count: int = Field(..., ge=0, description="Image file count")
    videos_count: int = Field(..., ge=0, description="Video file count")
    documents_count: int = Field(..., ge=0, description="Document file count")
    other_count: int = Field(..., ge=0, description="Other file count")

    # Storage usage
    total_size_bytes: int = Field(..., ge=0, description="Total storage used (bytes)")
    storage_quota_bytes: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Storage quota (bytes)",
    )

    # Time-based
    files_uploaded_today: int = Field(..., ge=0, description="Files uploaded today")
    files_uploaded_this_week: int = Field(..., ge=0, description="Files uploaded this week")
    files_uploaded_this_month: int = Field(..., ge=0, description="Files uploaded this month")

    @computed_field
    @property
    def total_size_gb(self) -> Decimal:
        """Get total size in gigabytes."""
        return Decimal(str(round(self.total_size_bytes / (1024 ** 3), 2)))

    @computed_field
    @property
    def storage_used_percentage(self) -> Union[Decimal, None]:
        """Get storage usage percentage."""
        if self.storage_quota_bytes is None or self.storage_quota_bytes == 0:
            return None
        
        percentage = (self.total_size_bytes / self.storage_quota_bytes) * 100
        return Decimal(str(round(percentage, 2)))

    @computed_field
    @property
    def is_near_quota(self) -> bool:
        """Check if storage is near quota (>80%)."""
        usage = self.storage_used_percentage
        return usage is not None and usage >= 80


class FileAccessLog(BaseSchema):
    """
    File access audit log entry.
    
    Tracks file access for security and analytics.
    """

    log_id: str = Field(..., description="Log entry identifier")
    file_id: str = Field(..., description="Accessed file ID")
    storage_key: str = Field(..., description="File storage key")

    # Access details
    accessed_by_user_id: Union[str, None] = Field(
        default=None,
        description="User who accessed (None for public access)",
    )
    accessed_by_name: Union[str, None] = Field(default=None, description="User name")

    access_type: str = Field(
        ...,
        description="Type of access",
    )
    access_method: str = Field(
        ...,
        description="Access method",
    )

    # Request metadata
    ip_address: Union[str, None] = Field(default=None, description="Client IP address")
    user_agent: Union[str, None] = Field(default=None, description="Client user agent")
    referrer: Union[str, None] = Field(default=None, description="HTTP referrer")

    # Geo-location
    country: Union[str, None] = Field(default=None, description="Country code")
    city: Union[str, None] = Field(default=None, description="City")

    accessed_at: datetime = Field(..., description="Access timestamp")

    # Response
    success: bool = Field(..., description="Whether access was successful")
    error_message: Union[str, None] = Field(
        default=None,
        description="Error message if access failed",
    )