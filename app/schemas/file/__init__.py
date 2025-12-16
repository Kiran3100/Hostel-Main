"""
File management schemas package.

Comprehensive file upload, management, and processing schemas
for images, documents, and generic files.

Example:
    from app.schemas.file import FileUploadInitRequest, DocumentInfo
"""

from app.schemas.file.document_upload import (
    DocumentExpiryAlert,
    DocumentInfo,
    DocumentList,
    DocumentOCRResult,
    DocumentUploadInitRequest,
    DocumentUploadInitResponse,
    DocumentValidationResult,
    DocumentVerificationRequest,
    DocumentVerificationResponse,
)
from app.schemas.file.file_filters import (
    DocumentFilterParams,
    FileFilterParams,
    FileSearchRequest,
    FileSortOptions,
    ImageFilterParams,
)
from app.schemas.file.file_response import (
    FileAccessLog,
    FileInfo,
    FileListResponse,
    FileMetadata,
    FileStats,
    FileURL,
)
from app.schemas.file.file_upload import (
    FileUploadCompleteRequest,
    FileUploadCompleteResponse,
    FileUploadInitRequest,
    FileUploadInitResponse,
    MultipartUploadCompleteRequest,
    MultipartUploadInitRequest,
    MultipartUploadPart,
)
from app.schemas.file.image_upload import (
    ImageMetadata,
    ImageProcessingOptions,
    ImageProcessingResult,
    ImageUploadInitRequest,
    ImageUploadInitResponse,
    ImageVariant,
)

__all__ = [
    # Generic file upload
    "FileUploadInitRequest",
    "FileUploadInitResponse",
    "FileUploadCompleteRequest",
    "FileUploadCompleteResponse",
    "MultipartUploadInitRequest",
    "MultipartUploadPart",
    "MultipartUploadCompleteRequest",
    # File response/info
    "FileInfo",
    "FileMetadata",
    "FileURL",
    "FileListResponse",
    "FileStats",
    "FileAccessLog",
    # File filters
    "FileFilterParams",
    "FileSearchRequest",
    "FileSortOptions",
    "DocumentFilterParams",
    "ImageFilterParams",
    # Image upload
    "ImageUploadInitRequest",
    "ImageUploadInitResponse",
    "ImageVariant",
    "ImageProcessingResult",
    "ImageProcessingOptions",
    "ImageMetadata",
    # Document upload
    "DocumentUploadInitRequest",
    "DocumentUploadInitResponse",
    "DocumentValidationResult",
    "DocumentInfo",
    "DocumentList",
    "DocumentVerificationRequest",
    "DocumentVerificationResponse",
    "DocumentOCRResult",
    "DocumentExpiryAlert",
]