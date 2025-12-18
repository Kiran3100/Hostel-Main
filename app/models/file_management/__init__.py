"""
File Management Models Package

Comprehensive file upload, management, and processing models
for images, documents, and generic files with metadata,
access control, and analytics.
"""

from app.models.file_management.document_upload import (
    DocumentExpiry,
    DocumentOCR,
    DocumentType,
    DocumentUpload,
    DocumentValidation,
    DocumentVerification,
)
from app.models.file_management.file_metadata import (
    FileAccess,
    FileAccessLog,
    FileAnalytics,
    FileFavorite,
    FileTag,
    FileVersion,
)
from app.models.file_management.file_upload import (
    FileQuota,
    FileUpload,
    FileValidation,
    MultipartUpload,
    MultipartUploadPart,
    UploadProgress,
    UploadSession,
)
from app.models.file_management.image_upload import (
    ImageMetadata,
    ImageOptimization,
    ImageProcessing,
    ImageUpload,
    ImageVariant,
)

__all__ = [
    # File Upload
    "FileUpload",
    "UploadSession",
    "FileValidation",
    "UploadProgress",
    "FileQuota",
    "MultipartUpload",
    "MultipartUploadPart",
    # Image Upload
    "ImageUpload",
    "ImageVariant",
    "ImageProcessing",
    "ImageOptimization",
    "ImageMetadata",
    # Document Upload
    "DocumentUpload",
    "DocumentType",
    "DocumentValidation",
    "DocumentOCR",
    "DocumentVerification",
    "DocumentExpiry",
    # File Metadata
    "FileTag",
    "FileAccess",
    "FileVersion",
    "FileAnalytics",
    "FileAccessLog",
    "FileFavorite",
]