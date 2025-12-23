"""
File Management Service Layer

Provides comprehensive business logic for:
- File upload lifecycle (single/multipart)
- Storage operations (URLs, delete, copy/move)
- Metadata/ACL/tags/versions/analytics
- Validation and antivirus scanning
- Image processing (variants/optimization/metadata)
- Document processing (OCR/validation/verification/expiry alerts)
- Cleanup of stale/expired artifacts

Version: 2.0.0
"""

from app.services.file_management.file_upload_service import FileUploadService
from app.services.file_management.file_storage_service import FileStorageService
from app.services.file_management.file_metadata_service import FileMetadataService
from app.services.file_management.file_validation_service import FileValidationService
from app.services.file_management.image_processing_service import ImageProcessingService
from app.services.file_management.document_processing_service import DocumentProcessingService
from app.services.file_management.file_cleanup_service import FileCleanupService

__all__ = [
    "FileUploadService",
    "FileStorageService",
    "FileMetadataService",
    "FileValidationService",
    "ImageProcessingService",
    "DocumentProcessingService",
    "FileCleanupService",
]

__version__ = "2.0.0"
__author__ = "Hostel Management System"
__license__ = "MIT"

# Service registry for dependency injection
SERVICE_REGISTRY = {
    "upload": FileUploadService,
    "storage": FileStorageService,
    "metadata": FileMetadataService,
    "validation": FileValidationService,
    "image": ImageProcessingService,
    "document": DocumentProcessingService,
    "cleanup": FileCleanupService,
}


def get_service(service_name: str):
    """
    Factory method to retrieve service class by name.
    
    Args:
        service_name: Name of the service to retrieve
        
    Returns:
        Service class or None if not found
    """
    return SERVICE_REGISTRY.get(service_name)