"""
Image Upload Models

Image-specific upload handling with variant generation,
processing queue, and optimization.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import UUIDMixin

if TYPE_CHECKING:
    from app.models.file_management.file_upload import FileUpload

__all__ = [
    "ImageUpload",
    "ImageVariant",
    "ImageProcessing",
    "ImageOptimization",
    "ImageMetadata",
]


class ImageUpload(UUIDMixin, TimestampModel, BaseModel):
    """
    Image-specific upload handling.
    
    Extends file upload with image-specific properties,
    processing configuration, and variant management.
    """

    __tablename__ = "image_uploads"

    # File reference
    file_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("file_uploads.file_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Associated file upload",
    )

    # Image context
    usage: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Image usage: hostel_cover, hostel_gallery, room_photo, avatar, etc.",
    )

    # Original image properties
    original_width: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Original image width in pixels",
    )
    original_height: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Original image height in pixels",
    )
    original_format: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Original image format (JPEG, PNG, etc.)",
    )
    original_mode: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Color mode (RGB, RGBA, L, etc.)",
    )

    # Color information
    has_alpha: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether image has alpha channel",
    )
    color_space: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Color space (sRGB, Adobe RGB, etc.)",
    )
    dominant_colors: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Dominant colors in image (hex codes)",
    )

    # Processing configuration
    generate_variants: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether to generate resized variants",
    )
    auto_optimize: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether to optimize image",
    )
    convert_to_webp: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether to convert to WebP format",
    )
    quality: Mapped[int] = mapped_column(
        Integer,
        default=85,
        nullable=False,
        comment="Image quality for compression (1-100)",
    )

    # Watermark
    add_watermark: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether to add watermark",
    )
    watermark_applied: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether watermark was applied",
    )

    # Processing status
    variants_generated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Whether variants have been generated",
    )
    optimization_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether optimization is complete",
    )

    # Size reduction
    original_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Original file size",
    )
    optimized_size_bytes: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Optimized file size",
    )
    size_reduction_percentage: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Percentage of size reduction",
    )

    # Processing timing
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Processing start time",
    )
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Processing completion time",
    )
    processing_duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Total processing time",
    )

    # Error tracking
    processing_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Processing error message",
    )

    # Relationships
    file: Mapped["FileUpload"] = relationship(
        "FileUpload",
        back_populates="image_upload",
    )
    variants: Mapped[List["ImageVariant"]] = relationship(
        "ImageVariant",
        back_populates="image",
        cascade="all, delete-orphan",
        order_by="ImageVariant.variant_name",
    )
    processing: Mapped[Optional["ImageProcessing"]] = relationship(
        "ImageProcessing",
        back_populates="image",
        uselist=False,
        cascade="all, delete-orphan",
    )
    optimization: Mapped[Optional["ImageOptimization"]] = relationship(
        "ImageOptimization",
        back_populates="image",
        uselist=False,
        cascade="all, delete-orphan",
    )
    # CHANGED: Renamed from 'metadata' to 'image_metadata'
    image_metadata: Mapped[Optional["ImageMetadata"]] = relationship(
        "ImageMetadata",
        back_populates="image",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_image_upload_usage_variants", "usage", "variants_generated"),
        Index("idx_image_upload_file", "file_id"),
    )

    def __repr__(self) -> str:
        return f"<ImageUpload(file_id={self.file_id}, usage={self.usage}, {self.original_width}x{self.original_height})>"


class ImageVariant(UUIDMixin, TimestampModel, BaseModel):
    """
    Generated image variant information.
    
    Represents a resized/optimized version of the original image
    for different use cases (thumbnail, medium, large, etc.).
    """

    __tablename__ = "image_variants"

    # Image reference
    image_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("image_uploads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent image upload",
    )

    # Variant identification
    variant_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Variant identifier: thumbnail, small, medium, large, webp, etc.",
    )
    storage_key: Mapped[str] = mapped_column(
        String(500),
        unique=True,
        nullable=False,
        comment="Storage path/key for variant",
    )

    # Variant properties
    width: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Variant width in pixels",
    )
    height: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Variant height in pixels",
    )
    format: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Image format",
    )
    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Variant file size",
    )

    # Access URLs
    url: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Variant access URL",
    )
    public_url: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        comment="Public CDN URL",
    )

    # Processing details
    is_optimized: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether variant was optimized",
    )
    quality: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Quality setting used",
    )

    # Generation timing
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Variant generation timestamp",
    )
    generation_duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Generation time in milliseconds",
    )

    # Relationships
    image: Mapped["ImageUpload"] = relationship(
        "ImageUpload",
        back_populates="variants",
    )

    __table_args__ = (
        Index("idx_image_variant_image_name", "image_id", "variant_name"),
    )

    def __repr__(self) -> str:
        return f"<ImageVariant(variant={self.variant_name}, {self.width}x{self.height})>"


class ImageProcessing(UUIDMixin, TimestampModel, BaseModel):
    """
    Image processing queue and status tracking.
    
    Manages the image processing workflow including
    resizing, optimization, and variant generation.
    """

    __tablename__ = "image_processing"

    # Image reference
    image_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("image_uploads.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Image being processed",
    )

    # Processing status
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        index=True,
        comment="Status: pending, queued, processing, completed, failed",
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
        comment="Processing priority (1-10, higher = more urgent)",
    )

    # Processing steps
    current_step: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Current processing step",
    )
    completed_steps: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of completed processing steps",
    )
    pending_steps: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of pending processing steps",
    )

    # Queue management
    queued_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Time added to processing queue",
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Processing start time",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Processing completion time",
    )

    # Worker information
    worker_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="ID of worker processing the image",
    )
    worker_hostname: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Hostname of processing worker",
    )

    # Progress tracking
    progress_percentage: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
        comment="Processing progress (0-100)",
    )

    # Retry management
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of retry attempts",
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
        comment="Maximum retry attempts allowed",
    )
    last_retry_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last retry attempt timestamp",
    )

    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if processing failed",
    )
    error_details: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Detailed error information",
    )

    # Processing configuration
    processing_config: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Processing configuration and options",
    )

    # Relationships
    image: Mapped["ImageUpload"] = relationship(
        "ImageUpload",
        back_populates="processing",
    )

    __table_args__ = (
        Index("idx_image_processing_status_priority", "status", "priority"),
        Index("idx_image_processing_queued", "queued_at"),
    )

    def __repr__(self) -> str:
        return f"<ImageProcessing(image_id={self.image_id}, status={self.status}, progress={self.progress_percentage}%)>"


class ImageOptimization(UUIDMixin, TimestampModel, BaseModel):
    """
    Image optimization settings and results.
    
    Tracks optimization parameters and results including
    compression, format conversion, and size reduction.
    """

    __tablename__ = "image_optimizations"

    # Image reference
    image_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("image_uploads.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Optimized image",
    )

    # Optimization settings
    optimization_level: Mapped[str] = mapped_column(
        String(20),
        default="medium",
        nullable=False,
        comment="Optimization level: low, medium, high, maximum",
    )
    target_format: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Target format for conversion",
    )
    target_quality: Mapped[int] = mapped_column(
        Integer,
        default=85,
        nullable=False,
        comment="Target quality (1-100)",
    )

    # Compression settings
    compression_algorithm: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Compression algorithm used",
    )
    compression_level: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Compression level",
    )

    # Metadata handling
    strip_metadata: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether to strip metadata",
    )
    preserve_exif: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether to preserve EXIF data",
    )
    auto_orient: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Auto-rotate based on EXIF orientation",
    )

    # Optimization results
    original_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Original file size",
    )
    optimized_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Optimized file size",
    )
    bytes_saved: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="Bytes saved by optimization",
    )
    reduction_percentage: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Percentage reduction in file size",
    )

    # Quality metrics
    visual_quality_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Visual quality score (0-100)",
    )
    ssim_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="SSIM (Structural Similarity Index) score",
    )

    # Optimization timing
    optimization_duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Optimization duration in milliseconds",
    )
    optimized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Optimization timestamp",
    )

    # Tool information
    optimization_tool: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Tool/library used for optimization",
    )
    tool_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Tool version",
    )

    # Relationships
    image: Mapped["ImageUpload"] = relationship(
        "ImageUpload",
        back_populates="optimization",
    )

    def __repr__(self) -> str:
        return f"<ImageOptimization(image_id={self.image_id}, reduction={self.reduction_percentage:.1f}%)>"


class ImageMetadata(UUIDMixin, TimestampModel, BaseModel):
    """
    Extended image metadata including EXIF data.
    
    Stores comprehensive image information including camera data,
    location, and technical properties.
    """

    __tablename__ = "image_metadata"

    # Image reference
    image_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("image_uploads.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Image",
    )

    # EXIF data
    camera_make: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Camera manufacturer",
    )
    camera_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Camera model",
    )
    lens_model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Lens model",
    )

    # Camera settings
    iso: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="ISO setting",
    )
    aperture: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Aperture (f-stop)",
    )
    shutter_speed: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Shutter speed",
    )
    focal_length: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Focal length",
    )
    flash: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="Whether flash was used",
    )

    # Date/time information
    date_taken: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date photo was taken",
    )
    date_modified: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date photo was modified",
    )

    # GPS data
    gps_latitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="GPS latitude",
    )
    gps_longitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="GPS longitude",
    )
    gps_altitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="GPS altitude in meters",
    )
    location_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Named location",
    )

    # Image properties
    orientation: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="EXIF orientation value",
    )
    resolution_x: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Horizontal resolution (DPI)",
    )
    resolution_y: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Vertical resolution (DPI)",
    )
    bit_depth: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Bit depth per channel",
    )

    # Software information
    software: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Software used to create/edit image",
    )
    copyright: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Copyright information",
    )
    artist: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Artist/photographer name",
    )

    # Additional metadata
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Image description",
    )
    keywords: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Image keywords/tags",
    )

    # Raw EXIF data
    raw_exif: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Complete raw EXIF data",
    )

    # Extraction details
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Metadata extraction timestamp",
    )
    extraction_tool: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Tool used for extraction",
    )

    # Relationships
    image: Mapped["ImageUpload"] = relationship(
        "ImageUpload",
        back_populates="image_metadata",  # CHANGED: Updated to match new relationship name
    )

    __table_args__ = (
        Index("idx_image_metadata_gps", "gps_latitude", "gps_longitude"),
        Index("idx_image_metadata_date_taken", "date_taken"),
    )

    def __repr__(self) -> str:
        return f"<ImageMetadata(image_id={self.image_id}, camera={self.camera_make} {self.camera_model})>"