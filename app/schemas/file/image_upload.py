"""
Image-specific upload schemas with advanced processing.

Handles image uploads with variant generation, optimization,
and format conversion capabilities.
"""

from typing import List, Union

from pydantic import Field, HttpUrl, field_validator, model_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema
from app.schemas.file.file_upload import FileUploadInitResponse

__all__ = [
    "ImageUploadInitRequest",
    "ImageUploadInitResponse",
    "ImageVariant",
    "ImageProcessingResult",
    "ImageProcessingOptions",
    "ImageMetadata",
]


class ImageUploadInitRequest(BaseCreateSchema):
    """
    Initialize image upload with processing options.
    
    Supports various image types and automatic processing.
    """

    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(
        ...,
        pattern=r"^image\/(jpeg|jpg|png|gif|webp|svg\+xml|bmp|tiff)$",
        description="Image MIME type (jpeg, png, gif, webp, svg, bmp, tiff)",
    )
    size_bytes: int = Field(
        ...,
        ge=1,
        le=20 * 1024 * 1024,
        description="Image size (max 20 MB)",
    )

    uploaded_by_user_id: str = Field(...)
    hostel_id: Union[str, None] = Field(default=None)
    student_id: Union[str, None] = Field(default=None)

    # Image context
    usage: str = Field(
        ...,
        pattern=r"^(hostel_cover|hostel_gallery|room_photo|avatar|profile_photo|"
        r"document_scan|complaint_attachment|announcement_image|other)$",
        description="Intended usage of the image",
    )

    # Processing options
    generate_variants: bool = Field(
        default=True,
        description="Generate resized variants (thumbnail, medium, large)",
    )
    auto_optimize: bool = Field(
        default=True,
        description="Optimize image (compression, format conversion)",
    )
    convert_to_webp: bool = Field(
        default=False,
        description="Convert to WebP format for better compression",
    )

    # Quality settings
    quality: int = Field(
        default=85,
        ge=1,
        le=100,
        description="Image quality for compression (1-100)",
    )

    # Watermark
    add_watermark: bool = Field(
        default=False,
        description="Add watermark to image",
    )

    @field_validator("filename")
    @classmethod
    def validate_image_filename(cls, v: str) -> str:
        """Validate image filename has valid extension."""
        v = v.strip()
        if not v:
            raise ValueError("Filename cannot be empty")
        
        valid_extensions = [
            ".jpg", ".jpeg", ".png", ".gif",
            ".webp", ".svg", ".bmp", ".tiff"
        ]
        
        if not any(v.lower().endswith(ext) for ext in valid_extensions):
            raise ValueError(
                f"Invalid image extension. Allowed: {', '.join(valid_extensions)}"
            )
        
        return v

    @model_validator(mode="after")
    def validate_svg_restrictions(self) -> "ImageUploadInitRequest":
        """Apply special restrictions for SVG files."""
        if self.content_type == "image/svg+xml":
            # SVG files shouldn't generate variants
            if self.generate_variants:
                raise ValueError(
                    "Variant generation not supported for SVG files"
                )
            
            # No optimization for SVG
            if self.auto_optimize:
                raise ValueError(
                    "Auto-optimization not supported for SVG files"
                )
        
        return self


class ImageVariant(BaseSchema):
    """
    Generated image variant information.
    
    Represents a resized/optimized version of the original image.
    """

    variant_name: str = Field(
        ...,
        description="Variant identifier",
    )
    url: HttpUrl = Field(..., description="Variant URL")

    # Dimensions
    width: int = Field(..., ge=1, description="Width in pixels")
    height: int = Field(..., ge=1, description="Height in pixels")

    # File information
    size_bytes: int = Field(..., ge=0, description="Variant file size")
    format: str = Field(..., description="Image format")

    # Processing
    is_optimized: bool = Field(
        default=False,
        description="Whether variant was optimized",
    )
    quality: Union[int, None] = Field(
        default=None,
        ge=1,
        le=100,
        description="Quality setting used",
    )

    @computed_field
    @property
    def aspect_ratio(self) -> str:
        """Get aspect ratio as string."""
        from math import gcd
        divisor = gcd(self.width, self.height)
        return f"{self.width // divisor}:{self.height // divisor}"

    @computed_field
    @property
    def megapixels(self) -> float:
        """Get image size in megapixels."""
        return round((self.width * self.height) / 1_000_000, 2)


class ImageUploadInitResponse(FileUploadInitResponse):
    """
    Image-specific upload initialization response.
    
    Extends base upload response with image processing information.
    """

    # Variant planning
    variants_planned: List[str] = Field(
        default_factory=lambda: ["thumbnail", "medium", "large"],
        description="Variants that will be generated after upload",
    )

    # Processing flags
    will_optimize: bool = Field(
        default=True,
        description="Whether image will be optimized",
    )
    will_convert_format: bool = Field(
        default=False,
        description="Whether format conversion will occur",
    )
    target_format: Union[str, None] = Field(
        default=None,
        description="Target format if converting",
    )


class ImageProcessingResult(BaseSchema):
    """
    Result of post-upload image processing.
    
    Provides information about all generated variants.
    """

    file_id: str = Field(..., description="File identifier")
    storage_key: str = Field(..., description="Original storage key")

    # Original image
    original_url: HttpUrl = Field(..., description="Original image URL")
    original_width: int = Field(..., ge=1, description="Original width")
    original_height: int = Field(..., ge=1, description="Original height")
    original_size_bytes: int = Field(..., ge=0, description="Original file size")

    # Generated variants
    variants: List[ImageVariant] = Field(
        default_factory=list,
        description="List of generated variants",
    )

    # Processing details
    processing_status: str = Field(
        default="completed",
        description="Processing status",
    )
    processing_time_seconds: Union[float, None] = Field(
        default=None,
        ge=0,
        description="Time taken to process",
    )
    processing_error: Union[str, None] = Field(
        default=None,
        description="Error message if processing failed",
    )

    # Optimization results
    was_optimized: bool = Field(
        default=False,
        description="Whether optimization was applied",
    )
    size_reduction_percentage: Union[float, None] = Field(
        default=None,
        ge=0,
        le=100,
        description="Percentage of size reduction from optimization",
    )

    @computed_field
    @property
    def total_variants(self) -> int:
        """Get total number of variants generated."""
        return len(self.variants)

    @computed_field
    @property
    def total_storage_bytes(self) -> int:
        """Get total storage used by all variants."""
        return self.original_size_bytes + sum(
            v.size_bytes for v in self.variants
        )


class ImageProcessingOptions(BaseSchema):
    """
    Advanced image processing configuration.
    
    Defines processing rules and variant specifications.
    """

    # Variant sizes
    thumbnail_max_size: int = Field(
        default=150,
        ge=50,
        le=500,
        description="Maximum dimension for thumbnail (pixels)",
    )
    small_max_size: int = Field(
        default=320,
        ge=200,
        le=640,
        description="Maximum dimension for small variant",
    )
    medium_max_size: int = Field(
        default=640,
        ge=400,
        le=1024,
        description="Maximum dimension for medium variant",
    )
    large_max_size: int = Field(
        default=1280,
        ge=800,
        le=2048,
        description="Maximum dimension for large variant",
    )

    # Quality settings
    thumbnail_quality: int = Field(default=70, ge=50, le=100)
    small_quality: int = Field(default=75, ge=50, le=100)
    medium_quality: int = Field(default=80, ge=50, le=100)
    large_quality: int = Field(default=85, ge=50, le=100)

    # Format preferences
    preferred_format: str = Field(
        default="original",
        pattern=r"^(original|jpeg|png|webp)$",
        description="Preferred output format",
    )

    # Processing flags
    preserve_exif: bool = Field(
        default=False,
        description="Preserve EXIF metadata",
    )
    strip_metadata: bool = Field(
        default=True,
        description="Strip all metadata for privacy",
    )
    auto_orient: bool = Field(
        default=True,
        description="Auto-rotate based on EXIF orientation",
    )

    # Watermark
    watermark_enabled: bool = Field(default=False)
    watermark_text: Union[str, None] = Field(default=None, max_length=50)
    watermark_position: str = Field(
        default="bottom-right",
        pattern=r"^(top-left|top-right|bottom-left|bottom-right|center)$",
    )
    watermark_opacity: int = Field(default=50, ge=0, le=100)


class ImageMetadata(BaseSchema):
    """
    Extended image metadata.
    
    Stores comprehensive image information including EXIF data.
    """

    # Basic properties
    width: int = Field(..., ge=1, description="Width in pixels")
    height: int = Field(..., ge=1, description="Height in pixels")
    format: str = Field(..., description="Image format")
    mode: Union[str, None] = Field(
        default=None,
        description="Color mode (RGB, RGBA, L, etc.)",
    )

    # Color information
    has_alpha: bool = Field(
        default=False,
        description="Whether image has alpha channel",
    )
    color_space: Union[str, None] = Field(
        default=None,
        description="Color space (sRGB, Adobe RGB, etc.)",
    )

    # EXIF data (if preserved)
    camera_make: Union[str, None] = Field(default=None, description="Camera manufacturer")
    camera_model: Union[str, None] = Field(default=None, description="Camera model")
    date_taken: Union[str, None] = Field(default=None, description="Date photo was taken")
    gps_latitude: Union[float, None] = Field(default=None, description="GPS latitude")
    gps_longitude: Union[float, None] = Field(default=None, description="GPS longitude")

    @computed_field
    @property
    def aspect_ratio(self) -> str:
        """Get aspect ratio."""
        from math import gcd
        divisor = gcd(self.width, self.height)
        return f"{self.width // divisor}:{self.height // divisor}"

    @computed_field
    @property
    def megapixels(self) -> float:
        """Get megapixels."""
        return round((self.width * self.height) / 1_000_000, 2)

    @computed_field
    @property
    def orientation(self) -> str:
        """Get image orientation."""
        if self.width > self.height:
            return "landscape"
        elif self.height > self.width:
            return "portrait"
        else:
            return "square"