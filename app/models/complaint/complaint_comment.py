"""
Complaint comment and discussion model.

Handles internal notes and public comments on complaints with support
for attachments, mentions, and edit tracking.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel
from app.models.base.mixins import SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.complaint.complaint import Complaint
    from app.models.user.user import User

__all__ = ["ComplaintComment"]


class ComplaintComment(BaseModel, TimestampMixin, SoftDeleteMixin):
    """
    Complaint comment and discussion thread.
    
    Supports both public comments and internal notes with rich content,
    attachments, mentions, and edit history.
    
    Attributes:
        complaint_id: Associated complaint identifier
        commented_by: User ID who created the comment
        
        comment_text: Comment content
        is_internal: Internal note flag (staff only vs public)
        
        attachments: URLs of attached files/images
        mentioned_users: List of mentioned user IDs (@mentions)
        
        is_edited: Flag indicating if comment was edited
        edited_at: Last edit timestamp
        edit_count: Number of times comment was edited
        
        parent_comment_id: Parent comment ID for threaded discussions
        thread_depth: Depth in comment thread
        
        metadata: Additional comment metadata
    """

    __tablename__ = "complaint_comments"
    __table_args__ = (
        # Indexes
        Index("ix_complaint_comments_complaint_id", "complaint_id"),
        Index("ix_complaint_comments_commented_by", "commented_by"),
        Index("ix_complaint_comments_created_at", "created_at"),
        Index("ix_complaint_comments_internal", "complaint_id", "is_internal"),
        Index("ix_complaint_comments_parent", "parent_comment_id"),
        
        # Check constraints
        CheckConstraint(
            "edit_count >= 0",
            name="check_edit_count_positive",
        ),
        CheckConstraint(
            "thread_depth >= 0",
            name="check_thread_depth_positive",
        ),
        CheckConstraint(
            "edited_at IS NULL OR edited_at >= created_at",
            name="check_edited_after_created",
        ),
        
        {"comment": "Complaint comments and internal notes"},
    )

    # Foreign Keys
    complaint_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Associated complaint identifier",
    )
    
    commented_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="User ID who created the comment",
    )

    # Comment Content
    comment_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Comment content",
    )
    
    is_internal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Internal note flag (staff only vs public)",
    )

    # Media and Mentions
    attachments: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        server_default=text("'{}'::varchar[]"),
        comment="URLs of attached files/images",
    )
    
    mentioned_users: Mapped[List[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
        server_default=text("'{}'::varchar[]"),
        comment="List of mentioned user IDs (@mentions)",
    )

    # Edit Tracking
    is_edited: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Flag indicating if comment was edited",
    )
    
    edited_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Last edit timestamp",
    )
    
    edit_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times comment was edited",
    )

    # Threading Support
    parent_comment_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("complaint_comments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Parent comment ID for threaded discussions",
    )
    
    thread_depth: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Depth in comment thread",
    )

    # Metadata
    metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
        comment="Additional comment metadata",
    )

    # Relationships
    complaint: Mapped["Complaint"] = relationship(
        "Complaint",
        back_populates="comments",
        lazy="joined",
    )
    
    commenter: Mapped["User"] = relationship(
        "User",
        foreign_keys=[commented_by],
        lazy="joined",
    )
    
    # Self-referential for threading
    parent_comment: Mapped[Optional["ComplaintComment"]] = relationship(
        "ComplaintComment",
        foreign_keys=[parent_comment_id],
        remote_side="ComplaintComment.id",
        back_populates="replies",
        lazy="selectin",
    )
    
    replies: Mapped[List["ComplaintComment"]] = relationship(
        "ComplaintComment",
        back_populates="parent_comment",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation of ComplaintComment."""
        return (
            f"<ComplaintComment(id={self.id}, "
            f"complaint_id={self.complaint_id}, "
            f"is_internal={self.is_internal}, "
            f"is_edited={self.is_edited})>"
        )

    def mark_edited(self) -> None:
        """Mark comment as edited and update edit tracking."""
        self.is_edited = True
        self.edited_at = datetime.now(timezone.utc)
        self.edit_count += 1