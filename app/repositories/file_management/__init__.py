"""
File Management Repositories Package

Comprehensive repositories for file upload, image processing,
document management, metadata, and aggregated analytics.
"""

from app.repositories.file_management.file_upload_repository import (
    FileUploadRepository,
    QuotaExceededException,
)
from app.repositories.file_management.image_upload_repository import (
    ImageUploadRepository,
)
from app.repositories.file_management.document_upload_repository import (
    DocumentUploadRepository,
)
from app.repositories.file_management.file_metadata_repository import (
    FileMetadataRepository,
)
from app.repositories.file_management.file_aggregate_repository import (
    FileAggregateRepository,
)

__all__ = [
    # File Upload
    "FileUploadRepository",
    "QuotaExceededException",
    # Image Upload
    "ImageUploadRepository",
    # Document Upload
    "DocumentUploadRepository",
    # File Metadata
    "FileMetadataRepository",
    # Aggregates
    "FileAggregateRepository",
]