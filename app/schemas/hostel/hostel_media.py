"""
Hostel media schemas for images, videos, and documents management.
"""

from datetime import datetime
from enum import Enum
from typing import Union, List
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.schemas.common.base import (
    BaseCreateSchema,
    BaseUpdateSchema, 
    BaseResponseSchema
)

__all__ = [
    "MediaType",
    "MediaAdd",
    "MediaUpdate", 
    "MediaResponse",
]


class MediaType(str, Enum):
    """Media type enumeration."""
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"


class MediaAdd(BaseCreateSchema):
    """Add media to hostel schema."""
    model_config = ConfigDict(from_attributes=True)
    
    hostel_id: UUID = Field(..., description="Hostel ID")
    media_type: MediaType = Field(..., description="Type of media")
    title: Union[str, None] = Field(
        default=None,
        max_length=200,
        description="Media title/caption"
    )
    description: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Media description"
    )
    file_name: str = Field(..., description="Original file name")
    content_type: str = Field(..., description="MIME content type")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    is_primary: bool = Field(
        default=False,
        description="Set as primary/featured image"
    )
    display_order: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Display order position"
    )

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str, info) -> str:
        """Validate content type matches media type."""
        media_type = info.data.get("media_type")
        
        valid_types = {
            MediaType.IMAGE: ["image/jpeg", "image/png", "image/webp", "image/gif"],
            MediaType.VIDEO: ["video/mp4", "video/webm", "video/avi"],
            MediaType.DOCUMENT: ["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
        }
        
        if media_type and v not in valid_types.get(media_type, []):
            raise ValueError(f"Invalid content type {v} for media type {media_type}")
        
        return v


class MediaUpdate(BaseUpdateSchema):
    """Update media metadata schema."""
    model_config = ConfigDict(from_attributes=True)
    
    title: Union[str, None] = Field(
        default=None,
        max_length=200,
        description="Media title/caption"
    )
    description: Union[str, None] = Field(
        default=None,
        max_length=500,
        description="Media description"
    )
    is_primary: Union[bool, None] = Field(
        default=None,
        description="Set as primary/featured image"
    )
    display_order: Union[int, None] = Field(
        default=None,
        ge=0,
        description="Display order position"
    )
    is_active: Union[bool, None] = Field(
        default=None,
        description="Active status"
    )


class MediaResponse(BaseResponseSchema):
    """Media response schema."""
    model_config = ConfigDict(from_attributes=True)
    
    hostel_id: UUID = Field(..., description="Hostel ID")
    media_type: MediaType = Field(..., description="Type of media")
    title: Union[str, None] = Field(default=None, description="Media title")
    description: Union[str, None] = Field(default=None, description="Media description")
    file_name: str = Field(..., description="Original file name")
    file_url: str = Field(..., description="Public URL to access the media")
    thumbnail_url: Union[str, None] = Field(
        default=None,
        description="Thumbnail URL for images/videos"
    )
    content_type: str = Field(..., description="MIME content type")
    file_size: int = Field(..., description="File size in bytes")
    file_size_formatted: str = Field(..., description="Human readable file size")
    is_primary: bool = Field(..., description="Is primary/featured media")
    display_order: int = Field(..., description="Display order position")
    is_active: bool = Field(..., description="Active status")
    
    # Metadata
    width: Union[int, None] = Field(default=None, description="Image/video width")
    height: Union[int, None] = Field(default=None, description="Image/video height")
    duration: Union[float, None] = Field(default=None, description="Video duration in seconds")
    
    # Upload info
    uploaded_by: Union[UUID, None] = Field(default=None, description="User who uploaded")
    upload_source: Union[str, None] = Field(default=None, description="Upload source")