"""
File filtering and search schemas.

Provides comprehensive filtering, searching, and sorting
capabilities for file queries.
"""

from datetime import date as Date, datetime
from typing import List, Union

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseFilterSchema

__all__ = [
    "FileFilterParams",
    "FileSearchRequest",
    "FileSortOptions",
    "DocumentFilterParams",
    "ImageFilterParams",
]


class FileFilterParams(BaseFilterSchema):
    """
    Comprehensive file filter parameters.
    
    Supports filtering by multiple dimensions for flexible queries.
    """

    # Text search
    search: Union[str, None] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Search in filename, tags, description",
    )

    # Ownership filters
    uploaded_by_user_id: Union[str, None] = Field(
        default=None,
        description="Filter by uploader",
    )
    hostel_id: Union[str, None] = Field(
        default=None,
        description="Filter by hostel",
    )
    student_id: Union[str, None] = Field(
        default=None,
        description="Filter by student",
    )

    # File type filters
    content_type: Union[str, None] = Field(
        default=None,
        description="Filter by MIME type",
    )
    content_type_prefix: Union[str, None] = Field(
        default=None,
        description="Filter by MIME type prefix (e.g., 'image/')",
    )
    category: Union[str, None] = Field(
        default=None,
        description="Filter by file category",
    )
    categories: Union[List[str], None] = Field(
        default=None,
        max_length=20,
        description="Filter by multiple categories",
    )

    # Tags
    tags: Union[List[str], None] = Field(
        default=None,
        max_length=10,
        description="Filter by tags (AND logic)",
    )
    any_tags: Union[List[str], None] = Field(
        default=None,
        max_length=10,
        description="Filter by tags (OR logic)",
    )

    # Size filters
    min_size_bytes: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Minimum file size",
    )
    max_size_bytes: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Maximum file size",
    )

    # Date filters
    uploaded_after: Union[datetime, None] = Field(
        default=None,
        description="Uploaded after this timestamp",
    )
    uploaded_before: Union[datetime, None] = Field(
        default=None,
        description="Uploaded before this timestamp",
    )

    # Access filters
    is_public: Union[bool, None] = Field(
        default=None,
        description="Filter by public/private status",
    )
    is_deleted: Union[bool, None] = Field(
        default=None,
        description="Include deleted files",
    )

    # Security filters
    virus_scan_status: Union[str, None] = Field(
        default=None,
        pattern=r"^(pending|clean|infected|error|skipped)$",
        description="Filter by virus scan status",
    )

    @field_validator("search")
    @classmethod
    def validate_search(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize search query."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v

    @model_validator(mode="after")
    def validate_size_range(self) -> "FileFilterParams":
        """Validate size range is logical."""
        if self.max_size_bytes is not None and self.min_size_bytes is not None:
            if self.max_size_bytes < self.min_size_bytes:
                raise ValueError(
                    "max_size_bytes must be >= min_size_bytes"
                )
        return self

    @model_validator(mode="after")
    def validate_date_range(self) -> "FileFilterParams":
        """Validate Date range is logical."""
        if self.uploaded_before is not None and self.uploaded_after is not None:
            if self.uploaded_before < self.uploaded_after:
                raise ValueError(
                    "uploaded_before must be >= uploaded_after"
                )
        return self


class FileSearchRequest(BaseFilterSchema):
    """
    Full-text file search request.
    
    Supports advanced search with field selection and filters.
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query string",
    )

    # Search scope
    search_in_filename: bool = Field(
        default=True,
        description="Search in filenames",
    )
    search_in_tags: bool = Field(
        default=True,
        description="Search in tags",
    )
    search_in_metadata: bool = Field(
        default=True,
        description="Search in metadata",
    )
    search_in_ocr_text: bool = Field(
        default=False,
        description="Search in OCR extracted text",
    )

    # Optional filters
    hostel_id: Union[str, None] = Field(
        default=None,
        description="Limit to specific hostel",
    )
    content_type_prefix: Union[str, None] = Field(
        default=None,
        description="Limit to specific file type",
    )

    # Pagination
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Results per page",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Normalize search query."""
        v = v.strip()
        if not v:
            raise ValueError("Search query cannot be empty")
        return v


class FileSortOptions(BaseFilterSchema):
    """
    File sorting options.
    
    Defines available sort fields and order.
    """

    sort_by: str = Field(
        default="created_at",
        pattern=r"^(created_at|updated_at|filename|size_bytes|access_count)$",
        description="Field to sort by",
    )
    sort_order: str = Field(
        default="desc",
        pattern=r"^(asc|desc)$",
        description="Sort order",
    )

    @field_validator("sort_by", "sort_order")
    @classmethod
    def normalize_sort_params(cls, v: str) -> str:
        """Normalize sort parameters."""
        return v.lower().strip()


class DocumentFilterParams(BaseFilterSchema):
    """
    Document-specific filter parameters.
    
    Extends base file filters with document-specific fields.
    """

    # Document type filters
    document_type: Union[str, None] = Field(
        default=None,
        description="Filter by document type",
    )
    document_types: Union[List[str], None] = Field(
        default=None,
        max_length=20,
        description="Filter by multiple document types",
    )
    document_subtype: Union[str, None] = Field(
        default=None,
        description="Filter by document subtype",
    )

    # Verification status
    verified: Union[bool, None] = Field(
        default=None,
        description="Filter by verification status",
    )
    verification_status: Union[str, None] = Field(
        default=None,
        pattern=r"^(pending|verified|rejected)$",
        description="Filter by specific verification status",
    )

    # Expiry filters
    is_expired: Union[bool, None] = Field(
        default=None,
        description="Filter expired documents",
    )
    expiring_within_days: Union[int, None] = Field(
        default=None,
        ge=1,
        le=365,
        description="Filter documents expiring within N days",
    )
    expiry_date_from: Union[Date, None] = Field(
        default=None,
        description="Expiry Date range start",
    )
    expiry_date_to: Union[Date, None] = Field(
        default=None,
        description="Expiry Date range end",
    )

    # OCR filters
    ocr_completed: Union[bool, None] = Field(
        default=None,
        description="Filter by OCR completion status",
    )

    # Student/Hostel filters
    student_id: Union[str, None] = Field(default=None)
    hostel_id: Union[str, None] = Field(default=None)


class ImageFilterParams(BaseFilterSchema):
    """
    Image-specific filter parameters.
    
    Extends base file filters with image-specific fields.
    """

    # Image usage filters
    usage: Union[str, None] = Field(
        default=None,
        pattern=r"^(hostel_cover|hostel_gallery|room_photo|avatar|"
        r"profile_photo|document_scan|complaint_attachment|"
        r"announcement_image|other)$",
        description="Filter by image usage",
    )

    # Dimension filters
    min_width: Union[int, None] = Field(
        default=None,
        ge=1,
        description="Minimum width in pixels",
    )
    max_width: Union[int, None] = Field(
        default=None,
        ge=1,
        description="Maximum width in pixels",
    )
    min_height: Union[int, None] = Field(
        default=None,
        ge=1,
        description="Minimum height in pixels",
    )
    max_height: Union[int, None] = Field(
        default=None,
        ge=1,
        description="Maximum height in pixels",
    )

    # Orientation filter
    orientation: Union[str, None] = Field(
        default=None,
        pattern=r"^(landscape|portrait|square)$",
        description="Filter by image orientation",
    )

    # Processing filters
    has_variants: Union[bool, None] = Field(
        default=None,
        description="Filter images with generated variants",
    )
    is_optimized: Union[bool, None] = Field(
        default=None,
        description="Filter optimized images",
    )

    # Format filters
    format: Union[str, None] = Field(
        default=None,
        pattern=r"^(jpeg|png|gif|webp|svg|bmp|tiff)$",
        description="Filter by image format",
    )

    # Hostel filters
    hostel_id: Union[str, None] = Field(default=None)

    @model_validator(mode="after")
    def validate_dimension_ranges(self) -> "ImageFilterParams":
        """Validate dimension ranges."""
        if self.max_width is not None and self.min_width is not None:
            if self.max_width < self.min_width:
                raise ValueError("max_width must be >= min_width")
        
        if self.max_height is not None and self.min_height is not None:
            if self.max_height < self.min_height:
                raise ValueError("max_height must be >= min_height")
        
        return self