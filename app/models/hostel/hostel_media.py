# --- File: C:\Hostel-Main\app\models\hostel\hostel_media.py ---
"""
Hostel media model for managing images, videos, and virtual tours.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel


class HostelMedia(TimestampModel, UUIDMixin):
    """
    Hostel media management for images, videos, and virtual tours.
    
    Manages all media content associated with a hostel including
    images, videos, virtual tours with categorization and ordering.
    """

    __tablename__ = "hostel_media"

    # Foreign Keys
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to hostel",
    )

    # Media Information
    media_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="Media type (image, video, virtual_tour, document)",
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Media category (exterior, interior, room, facility, etc.)",
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Media title/caption",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed description",
    )

    # File Information
    file_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Primary file URL",
    )
    thumbnail_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Thumbnail URL for images/videos",
    )
    file_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="File size in bytes",
    )
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="MIME type of the file",
    )

    # Image-specific fields
    width: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Image/video width in pixels",
    )
    height: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Image/video height in pixels",
    )
    alt_text: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
        comment="Alt text for accessibility",
    )

    # Video-specific fields
    duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Video duration in seconds",
    )
    video_provider: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Video hosting provider (youtube, vimeo, self-hosted)",
    )
    embed_code: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Video embed code",
    )

    # Display and Ordering
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Display order priority",
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Featured media status",
    )
    is_cover: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Use as cover/primary image",
    )

    # Status and Moderation
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Active/visible status",
    )
    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Moderation approval status",
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Approval timestamp",
    )
    approved_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Admin who approved",
    )

    # SEO
    seo_keywords: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="SEO keywords for image search",
    )

    # Metadata (JSONB for flexible data)
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional metadata (EXIF, GPS, etc.)",
    )

    # Analytics
    view_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of views",
    )
    click_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of clicks",
    )

    # Upload Information
    uploaded_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="User who uploaded the media",
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
        comment="Upload timestamp",
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="media_items",
    )

    # Table Arguments
    __table_args__ = (
        # Indexes
        Index("idx_media_hostel_type", "hostel_id", "media_type"),
        Index("idx_media_hostel_category", "hostel_id", "category"),
        Index("idx_media_featured", "is_featured", "is_active"),
        Index("idx_media_cover", "is_cover", "hostel_id"),
        Index("idx_media_display_order", "hostel_id", "display_order"),
        
        # Check constraints
        CheckConstraint(
            "media_type IN ('image', 'video', 'virtual_tour', 'document')",
            name="check_media_type_valid",
        ),
        CheckConstraint(
            "file_size IS NULL OR file_size >= 0",
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
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="check_duration_positive",
        ),
        CheckConstraint(
            "display_order >= 0",
            name="check_display_order_positive",
        ),
        CheckConstraint(
            "view_count >= 0",
            name="check_view_count_positive",
        ),
        CheckConstraint(
            "click_count >= 0",
            name="check_click_count_positive",
        ),
        
        {"comment": "Hostel media content management"},
    )

    def __repr__(self) -> str:
        return (
            f"<HostelMedia(id={self.id}, hostel_id={self.hostel_id}, "
            f"type='{self.media_type}', category='{self.category}')>"
        )

    @property
    def is_image(self) -> bool:
        """Check if media is an image."""
        return self.media_type == "image"

    @property
    def is_video(self) -> bool:
        """Check if media is a video."""
        return self.media_type == "video"

    @property
    def aspect_ratio(self) -> Optional[float]:
        """Calculate aspect ratio if width and height are available."""
        if self.width and self.height and self.height > 0:
            return self.width / self.height
        return None

    def increment_views(self) -> None:
        """Increment view count."""
        self.view_count += 1

    def increment_clicks(self) -> None:
        """Increment click count."""
        self.click_count += 1


class MediaCategory(TimestampModel, UUIDMixin):
    """
    Media category master for standardization.
    
    Defines standard media categories with properties.
    """

    __tablename__ = "media_categories"

    # Category Information
    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        comment="Category name",
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Display name",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Category description",
    )

    # Properties
    applicable_media_types: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        comment="List of applicable media types",
    )
    max_items: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum items allowed in this category",
    )
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Requires moderation approval",
    )

    # Display
    icon_name: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Icon identifier",
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Display order",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Active status",
    )

    # Table Arguments
    __table_args__ = (
        Index("idx_media_category_active", "is_active"),
        CheckConstraint(
            "max_items IS NULL OR max_items > 0",
            name="check_max_items_positive",
        ),
        CheckConstraint(
            "display_order >= 0",
            name="check_media_cat_display_order_positive",
        ),
        {"comment": "Media category master data"},
    )

    def __repr__(self) -> str:
        return f"<MediaCategory(id={self.id}, name='{self.name}')>"