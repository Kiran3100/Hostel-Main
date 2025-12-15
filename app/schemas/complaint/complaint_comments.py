"""
Complaint discussion and comments schemas.

Handles internal notes and public comments on complaints
with support for attachments and mentions.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import ConfigDict, Field, HttpUrl, field_validator

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema

__all__ = [
    "CommentCreate",
    "CommentResponse",
    "CommentList",
    "CommentUpdate",
    "CommentDelete",
    "MentionNotification",
]


class CommentCreate(BaseCreateSchema):
    """
    Create comment on complaint.
    
    Supports both public comments and internal notes
    with optional attachments.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(
        ...,
        description="Complaint identifier to comment on",
    )

    comment_text: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Comment text content",
    )

    is_internal: bool = Field(
        default=False,
        description="Internal note (staff only) vs public comment",
    )

    attachments: List[HttpUrl] = Field(
        default_factory=list,
        max_length=5,
        description="Comment attachments (max 5)",
    )

    @field_validator("comment_text")
    @classmethod
    def validate_comment_text(cls, v: str) -> str:
        """Validate comment text quality."""
        v = v.strip()
        if not v:
            raise ValueError("Comment text cannot be empty")
        
        # Ensure meaningful content
        if len(v) < 5:
            raise ValueError("Comment must be at least 5 characters")
        
        return v

    @field_validator("attachments")
    @classmethod
    def validate_attachments_limit(cls, v: List[HttpUrl]) -> List[HttpUrl]:
        """Ensure attachment count doesn't exceed limit."""
        if len(v) > 5:
            raise ValueError("Maximum 5 attachments allowed per comment")
        return v


class CommentResponse(BaseResponseSchema):
    """
    Comment response with author information.
    
    Includes metadata about comment author and timing.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(..., description="Associated complaint ID")

    commented_by: str = Field(..., description="Commenter user ID")
    commented_by_name: str = Field(..., description="Commenter name")
    commented_by_role: str = Field(..., description="Commenter role")

    comment_text: str = Field(..., description="Comment content")
    is_internal: bool = Field(..., description="Internal note flag")

    attachments: List[str] = Field(
        default_factory=list,
        description="Attachment URLs",
    )

    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    is_edited: bool = Field(
        default=False,
        description="Whether comment was edited",
    )


class CommentList(BaseSchema):
    """
    List of comments for a complaint.
    
    Provides summary statistics and comment thread.
    """
    model_config = ConfigDict(from_attributes=True)

    complaint_id: str = Field(..., description="Complaint ID")
    complaint_number: str = Field(..., description="Complaint reference number")

    total_comments: int = Field(..., ge=0, description="Total comment count")
    public_comments: int = Field(..., ge=0, description="Public comment count")
    internal_notes: int = Field(..., ge=0, description="Internal note count")

    comments: List[CommentResponse] = Field(
        default_factory=list,
        description="List of comments (sorted by creation time)",
    )


class CommentUpdate(BaseCreateSchema):
    """
    Update existing comment.
    
    Allows modification of comment text only.
    """
    model_config = ConfigDict(from_attributes=True)

    comment_id: str = Field(
        ...,
        description="Comment identifier to update",
    )
    comment_text: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Updated comment text",
    )

    @field_validator("comment_text")
    @classmethod
    def validate_comment_text(cls, v: str) -> str:
        """Validate comment text quality."""
        v = v.strip()
        if not v:
            raise ValueError("Comment text cannot be empty")
        
        if len(v) < 5:
            raise ValueError("Comment must be at least 5 characters")
        
        return v


class CommentDelete(BaseCreateSchema):
    """
    Delete comment request.
    
    Optional reason for deletion audit trail.
    """
    model_config = ConfigDict(from_attributes=True)

    comment_id: str = Field(
        ...,
        description="Comment identifier to delete",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Deletion reason (optional)",
    )

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: Optional[str]) -> Optional[str]:
        """Normalize deletion reason if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


class MentionNotification(BaseSchema):
    """
    Notification when user is mentioned in comment.
    
    Supports @mention functionality in comments.
    """
    model_config = ConfigDict(from_attributes=True)

    comment_id: str = Field(..., description="Comment ID with mention")
    complaint_id: str = Field(..., description="Associated complaint ID")
    complaint_number: str = Field(..., description="Complaint reference number")

    mentioned_by: str = Field(..., description="User who mentioned")
    mentioned_by_name: str = Field(..., description="Mentioner name")

    comment_excerpt: str = Field(
        ...,
        max_length=200,
        description="Comment excerpt (first 200 chars)",
    )

    comment_url: str = Field(
        ...,
        description="Direct URL to comment",
    )