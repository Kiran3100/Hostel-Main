"""
File Management Services Package

Comprehensive services for file upload, storage, processing, validation,
metadata management, and cleanup operations.
"""

from app.services.file_management.file_upload_service import FileUploadService
from app.services.file_management.file_storage_service import (
    FileStorageService,
    StorageProvider,
    S3StorageProvider,
)
from app.services.file_management.file_validation_service import FileValidationService
from app.services.file_management.image_processing_service import ImageProcessingService
from app.services.file_management.document_processing_service import DocumentProcessingService
from app.services.file_management.file_metadata_service import FileMetadataService
from app.services.file_management.file_cleanup_service import FileCleanupService

__all__ = [
    # Core Services
    "FileUploadService",
    "FileStorageService",
    "FileValidationService",
    
    # Processing Services
    "ImageProcessingService",
    "DocumentProcessingService",
    
    # Management Services
    "FileMetadataService",
    "FileCleanupService",
    
    # Storage Providers
    "StorageProvider",
    "S3StorageProvider",
]


# Service factory functions for dependency injection

def create_file_upload_service(db_session, storage_service=None, validation_service=None):
    """
    Create FileUploadService with dependencies.
    
    Args:
        db_session: Database session
        storage_service: Optional storage service (creates default if None)
        validation_service: Optional validation service (creates default if None)
        
    Returns:
        Configured FileUploadService instance
    """
    if storage_service is None:
        storage_service = FileStorageService()
    
    if validation_service is None:
        validation_service = FileValidationService()
    
    return FileUploadService(
        db_session=db_session,
        storage_service=storage_service,
        validation_service=validation_service,
    )


def create_image_processing_service(db_session, storage_service=None):
    """
    Create ImageProcessingService with dependencies.
    
    Args:
        db_session: Database session
        storage_service: Optional storage service
        
    Returns:
        Configured ImageProcessingService instance
    """
    if storage_service is None:
        storage_service = FileStorageService()
    
    return ImageProcessingService(
        db_session=db_session,
        storage_service=storage_service,
    )


def create_document_processing_service(db_session, storage_service=None):
    """
    Create DocumentProcessingService with dependencies.
    
    Args:
        db_session: Database session
        storage_service: Optional storage service
        
    Returns:
        Configured DocumentProcessingService instance
    """
    if storage_service is None:
        storage_service = FileStorageService()
    
    return DocumentProcessingService(
        db_session=db_session,
        storage_service=storage_service,
    )


def create_file_metadata_service(db_session):
    """
    Create FileMetadataService.
    
    Args:
        db_session: Database session
        
    Returns:
        Configured FileMetadataService instance
    """
    return FileMetadataService(db_session=db_session)


def create_file_cleanup_service(db_session, storage_service=None):
    """
    Create FileCleanupService with dependencies.
    
    Args:
        db_session: Database session
        storage_service: Optional storage service
        
    Returns:
        Configured FileCleanupService instance
    """
    if storage_service is None:
        storage_service = FileStorageService()
    
    return FileCleanupService(
        db_session=db_session,
        storage_service=storage_service,
    )


# Service initialization helper
class FileManagementServices:
    """
    Container for all file management services.
    Provides centralized access to all services with shared dependencies.
    """
    
    def __init__(self, db_session):
        """
        Initialize all file management services.
        
        Args:
            db_session: Database session
        """
        self.db_session = db_session
        
        # Initialize shared dependencies
        self.storage_service = FileStorageService()
        self.validation_service = FileValidationService()
        
        # Initialize services
        self.upload = FileUploadService(
            db_session=db_session,
            storage_service=self.storage_service,
            validation_service=self.validation_service,
        )
        
        self.image_processing = ImageProcessingService(
            db_session=db_session,
            storage_service=self.storage_service,
        )
        
        self.document_processing = DocumentProcessingService(
            db_session=db_session,
            storage_service=self.storage_service,
        )
        
        self.metadata = FileMetadataService(
            db_session=db_session,
        )
        
        self.cleanup = FileCleanupService(
            db_session=db_session,
            storage_service=self.storage_service,
        )
    
    def get_all_services(self):
        """
        Get dictionary of all services.
        
        Returns:
            Dictionary mapping service names to service instances
        """
        return {
            "upload": self.upload,
            "image_processing": self.image_processing,
            "document_processing": self.document_processing,
            "metadata": self.metadata,
            "cleanup": self.cleanup,
            "storage": self.storage_service,
            "validation": self.validation_service,
        }


# Usage example helper
def get_file_management_services(db_session):
    """
    Convenience function to get all file management services.
    
    Args:
        db_session: Database session
        
    Returns:
        FileManagementServices instance with all services initialized
        
    Example:
        >>> services = get_file_management_services(db_session)
        >>> file_result = await services.upload.upload_file(...)
        >>> image_result = await services.image_processing.create_image_upload(...)
        >>> cleanup_result = await services.cleanup.run_all_cleanup_tasks()
    """
    return FileManagementServices(db_session)