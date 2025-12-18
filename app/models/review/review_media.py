# --- File: C:\Hostel-Main\app\models\review\review_media.py ---
"""
Review media models for photo and video attachments.

Implements media management with processing and moderation.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Index,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import relationship, validates

from app.models.base import BaseModel, TimestampMixin, SoftDeleteMixin

__all__ = [
    "ReviewMedia",
    "ReviewMediaProcessing",
]


class ReviewMedia(BaseModel, TimestampMixin, SoftDeleteMixin):
    """
    Media attachments for reviews (photos, videos).
    
    Manages media uploads with processing and moderation.
    """
    
    __tablename__ = "review_media"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    review_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Media type and storage
    media_type = Column(String(20), nullable=False)
    # Types: photo, video
    
    original_filename = Column(String(255), nullable=True)
    file_size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    
    # Storage URLs
    original_url = Column(String(500), nullable=False)
    thumbnail_url = Column(String(500), nullable=True)
    processed_url = Column(String(500), nullable=True)
    
    # Image-specific properties
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    
    # Video-specific properties
    duration_seconds = Column(Numeric(precision=10, scale=2), nullable=True)
    
    # Media metadata
    exif_data = Column(JSONB, nullable=True)
    caption = Column(Text, nullable=True)
    alt_text = Column(String(255), nullable=True)
    
    # Display order
    display_order = Column(Integer, default=0, nullable=False)
    
    # Processing status
    is_processed = Column(Boolean, default=False, nullable=False)
    processing_status = Column(String(50), default='pending', nullable=False)
    # Status: pending, processing, completed, failed
    
    processing_error = Column(Text, nullable=True)
    
    # Moderation
    is_approved = Column(Boolean, default=False, nullable=False, index=True)
    moderation_status = Column(String(50), default='pending', nullable=False)
    # Status: pending, approved, rejected, flagged
    
    moderated_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    moderated_at = Column(DateTime(timezone=True), nullable=True)
    moderation_notes = Column(Text, nullable=True)
    
    # AI content analysis
    has_inappropriate_content = Column(Boolean, default=False, nullable=False)
    content_safety_score = Column(Numeric(precision=4, scale=3), nullable=True)
    detected_labels = Column(ARRAY(String), default=list, server_default='{}')
    
    # Visibility
    is_visible = Column(Boolean, default=True, nullable=False)
    
    # Usage tracking
    view_count = Column(Integer, default=0, nullable=False)
    
    # Upload metadata
    uploaded_by = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    upload_ip_address = Column(String(45), nullable=True)
    
    # Additional metadata
    metadata = Column(JSONB, nullable=True)
    
    # Relationships
    review = relationship("Review", back_populates="media")
    processing_log = relationship(
        "ReviewMediaProcessing",
        back_populates="media",
        uselist=False,
        cascade="all, delete-orphan",
    )
    
    __table_args__ = (
        CheckConstraint(
            "file_size_bytes > 0",
            name="check_file_size_positive",
        ),
        CheckConstraint(
            "width IS NULL OR width > 0",
            name="check_width_positive",
        ),
        CheckConstraint(
            "height IS NULL OR height > 0",
            name="check_height_positive",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds > 0",
            name="check_duration_positive",
        ),
        CheckConstraint(
            "view_count >= 0",
            name="check_view_count_positive",
        ),
        CheckConstraint(
            "content_safety_score IS NULL OR (content_safety_score >= 0 AND content_safety_score <= 1)",
            name="check_safety_score_range",
        ),
        Index("idx_review_order", "review_id", "display_order"),
        Index("idx_moderation_status", "moderation_status", "created_at"),
        Index("idx_processing_status", "processing_status", "created_at"),
    )
    
    @validates("media_type")
    def validate_media_type(self, key, value):
        """Validate media type."""
        valid_types = {'photo', 'video', 'image'}
        if value.lower() not in valid_types:
            raise ValueError(f"Invalid media type: {value}")
        # Normalize 'image' to 'photo'
        return 'photo' if value.lower() == 'image' else value.lower()
    
    @validates("processing_status")
    def validate_processing_status(self, key, value):
        """Validate processing status."""
        valid_statuses = {'pending', 'processing', 'completed', 'failed'}
        if value.lower() not in valid_statuses:
            raise ValueError(f"Invalid processing status: {value}")
        return value.lower()
    
    @validates("moderation_status")
    def validate_moderation_status(self, key, value):
        """Validate moderation status."""
        valid_statuses = {'pending', 'approved', 'rejected', 'flagged'}
        if value.lower() not in valid_statuses:
            raise ValueError(f"Invalid moderation status: {value}")
        return value.lower()
    
    def mark_as_processed(self, processed_url: str = None):
        """Mark media as processed."""
        self.is_processed = True
        self.processing_status = 'completed'
        if processed_url:
            self.processed_url = processed_url
    
    def mark_processing_failed(self, error: str):
        """Mark processing as failed."""
        self.processing_status = 'failed'
        self.processing_error = error
    
    def approve(self, admin_id: UUID, notes: str = None):
        """Approve media."""
        self.is_approved = True
        self.moderation_status = 'approved'
        self.moderated_by = admin_id
        self.moderated_at = datetime.utcnow()
        self.moderation_notes = notes
        self.is_visible = True
    
    def reject(self, admin_id: UUID, notes: str):
        """Reject media."""
        self.is_approved = False
        self.moderation_status = 'rejected'
        self.moderated_by = admin_id
        self.moderated_at = datetime.utcnow()
        self.moderation_notes = notes
        self.is_visible = False
    
    def flag(self, admin_id: UUID, notes: str):
        """Flag media for review."""
        self.moderation_status = 'flagged'
        self.moderated_by = admin_id
        self.moderated_at = datetime.utcnow()
        self.moderation_notes = notes
    
    def increment_view(self):
        """Increment view count."""
        self.view_count += 1
    
    def __repr__(self):
        return (
            f"<ReviewMedia(id={self.id}, review_id={self.review_id}, "
            f"type={self.media_type}, status={self.moderation_status})>"
        )


class ReviewMediaProcessing(BaseModel, TimestampMixin):
    """
    Media processing tracking and logs.
    
    Tracks processing steps and performance.
    """
    
    __tablename__ = "review_media_processing"
    
    id = Column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    media_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("review_media.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    
    # Processing steps
    steps_completed = Column(ARRAY(String), default=list, server_default='{}')
    current_step = Column(String(100), nullable=True)
    
    # Processing times (in milliseconds)
    upload_time_ms = Column(Integer, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    total_time_ms = Column(Integer, nullable=True)
    
    # Processing details
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Variants generated (for images)
    variants_generated = Column(JSONB, nullable=True)
    # Format: {"thumbnail": "url", "medium": "url", "large": "url"}
    
    # Compression and optimization
    original_size_bytes = Column(Integer, nullable=True)
    compressed_size_bytes = Column(Integer, nullable=True)
    compression_ratio = Column(Numeric(precision=5, scale=2), nullable=True)
    
    # AI analysis results
    ai_analysis_completed = Column(Boolean, default=False, nullable=False)
    ai_labels = Column(ARRAY(String), default=list, server_default='{}')
    ai_confidence_scores = Column(JSONB, nullable=True)
    
    # Content safety analysis
    safety_analysis_completed = Column(Boolean, default=False, nullable=False)
    safety_flags = Column(ARRAY(String), default=list, server_default='{}')
    
    # Error tracking
    errors_encountered = Column(ARRAY(String), default=list, server_default='{}')
    retry_count = Column(Integer, default=0, nullable=False)
    
    # Processing metadata
    processor_version = Column(String(50), nullable=True)
    metadata = Column(JSONB, nullable=True)
    
    # Relationships
    media = relationship("ReviewMedia", back_populates="processing_log")
    
    __table_args__ = (
        CheckConstraint(
            "upload_time_ms IS NULL OR upload_time_ms >= 0",
            name="check_upload_time_positive",
        ),
        CheckConstraint(
            "processing_time_ms IS NULL OR processing_time_ms >= 0",
            name="check_processing_time_positive",
        ),
        CheckConstraint(
            "retry_count >= 0",
            name="check_retry_count_positive",
        ),
        Index("idx_processing_completed", "ai_analysis_completed", "safety_analysis_completed"),
    )
    
    def add_step(self, step_name: str):
        """Add completed processing step."""
        if self.steps_completed is None:
            self.steps_completed = []
        if step_name not in self.steps_completed:
            self.steps_completed.append(step_name)
        self.current_step = step_name
    
    def add_error(self, error: str):
        """Add error to error list."""
        if self.errors_encountered is None:
            self.errors_encountered = []
        self.errors_encountered.append(error)
    
    def calculate_compression_ratio(self):
        """Calculate compression ratio."""
        if self.original_size_bytes and self.compressed_size_bytes:
            ratio = (
                (self.original_size_bytes - self.compressed_size_bytes) /
                self.original_size_bytes * 100
            )
            self.compression_ratio = Decimal(str(round(ratio, 2)))
    
    def mark_started(self):
        """Mark processing as started."""
        self.started_at = datetime.utcnow()
    
    def mark_completed(self):
        """Mark processing as completed."""
        self.completed_at = datetime.utcnow()
        if self.started_at:
            delta = self.completed_at - self.started_at
            self.total_time_ms = int(delta.total_seconds() * 1000)
    
    def increment_retry(self):
        """Increment retry count."""
        self.retry_count += 1
    
    def __repr__(self):
        return (
            f"<ReviewMediaProcessing(media_id={self.media_id}, "
            f"steps={len(self.steps_completed or [])}, errors={len(self.errors_encountered or [])})>"
        )