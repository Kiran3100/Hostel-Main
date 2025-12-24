"""
File Storage Operations Service

Manages storage-level operations including:
- URL generation (download, upload, preview)
- File deletion with storage cleanup
- Copy and move operations
- Storage provider abstraction
"""

from typing import Optional, Dict, Any
from uuid import UUID
import logging

from sqlalchemy.orm import Session

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.file_management.file_upload_repository import FileUploadRepository
from app.models.file_management.file_upload import FileUpload as FileUploadModel
from app.schemas.file.file_response import FileURL

logger = logging.getLogger(__name__)


class FileStorageService(BaseService[FileUploadModel, FileUploadRepository]):
    """
    Storage-level operations with provider abstraction.
    
    Features:
    - Multiple URL types (download, upload, preview)
    - Soft/hard delete capabilities
    - Cross-folder copy/move operations
    - Storage quota management
    """

    def __init__(self, repository: FileUploadRepository, db_session: Session):
        """
        Initialize the file storage service.
        
        Args:
            repository: File upload repository instance
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)
        self._url_cache_ttl = 300  # 5 minutes default cache
        logger.info("FileStorageService initialized")

    def generate_url(
        self,
        file_id: UUID,
        url_type: str = "download",
        expires_in_seconds: int = 900,
        custom_filename: Optional[str] = None,
    ) -> ServiceResult[FileURL]:
        """
        Generate a signed URL for various file operations.
        
        Args:
            file_id: Unique identifier of the file
            url_type: Type of URL (download, upload, preview, inline)
            expires_in_seconds: URL expiration time
            custom_filename: Optional custom filename for download
            
        Returns:
            ServiceResult containing the signed URL
        """
        valid_url_types = {"download", "upload", "preview", "inline", "thumbnail"}
        
        try:
            # Validate URL type
            if url_type not in valid_url_types:
                logger.warning(f"Invalid URL type requested: {url_type}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid URL type. Must be one of: {', '.join(valid_url_types)}",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Validate expiration
            if expires_in_seconds < 60 or expires_in_seconds > 604800:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Expiration must be between 60 and 604800 seconds (1 min to 7 days)",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            logger.info(
                f"Generating {url_type} URL for file ID: {file_id}, "
                f"expires in: {expires_in_seconds}s"
            )
            
            url = self.repository.get_signed_url(
                file_id,
                url_type=url_type,
                expires_in=expires_in_seconds,
                custom_filename=custom_filename
            )
            
            logger.info(f"URL generated successfully for file ID: {file_id}")
            
            return ServiceResult.success(
                url,
                metadata={
                    "url_type": url_type,
                    "expires_in": expires_in_seconds,
                    "custom_filename": custom_filename
                }
            )
            
        except Exception as e:
            logger.error(
                f"Failed to generate {url_type} URL for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, f"generate {url_type} url", file_id)

    def delete_file(
        self,
        file_id: UUID,
        delete_from_storage: bool = True,
        soft_delete: bool = False,
    ) -> ServiceResult[bool]:
        """
        Delete file record and optionally remove from storage.
        
        Args:
            file_id: Unique identifier of the file
            delete_from_storage: Whether to remove from physical storage
            soft_delete: Whether to soft delete (mark as deleted) instead of hard delete
            
        Returns:
            ServiceResult indicating success or failure
        """
        try:
            logger.info(
                f"Deleting file ID: {file_id}, "
                f"from_storage: {delete_from_storage}, soft: {soft_delete}"
            )
            
            # Check if file exists and get info before deletion
            file_info = self.repository.get_file_info(file_id)
            if not file_info:
                logger.warning(f"File not found for deletion: {file_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"File with ID {file_id} not found",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            success = self.repository.delete_file(
                file_id,
                delete_from_storage=delete_from_storage,
                soft_delete=soft_delete
            )
            
            if success:
                self.db.commit()
                delete_type = "soft deleted" if soft_delete else "deleted"
                logger.info(
                    f"File {delete_type} successfully: {file_id}, "
                    f"size: {file_info.size_bytes if hasattr(file_info, 'size_bytes') else 'unknown'}"
                )
                return ServiceResult.success(
                    True,
                    message=f"File {delete_type} successfully"
                )
            else:
                logger.error(f"Failed to delete file: {file_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="File deletion failed",
                        severity=ErrorSeverity.ERROR,
                    )
                )
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting file {file_id}: {str(e)}", exc_info=True)
            return self._handle_exception(e, "delete file", file_id)

    def copy_object(
        self,
        file_id: UUID,
        destination_folder: str,
        new_filename: Optional[str] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Copy a file to a different location in storage.
        
        Args:
            file_id: Source file identifier
            destination_folder: Target folder path
            new_filename: Optional new filename for the copy
            
        Returns:
            ServiceResult containing new file information
        """
        try:
            logger.info(
                f"Copying file ID: {file_id} to folder: {destination_folder}"
            )
            
            # Validate destination folder
            if not destination_folder or not destination_folder.strip():
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Destination folder cannot be empty",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            result = self.repository.copy_object(
                file_id,
                destination_folder,
                new_filename=new_filename
            )
            
            self.db.commit()
            
            logger.info(
                f"File copied successfully from {file_id} to {destination_folder}"
            )
            
            return ServiceResult.success(
                result or {},
                message="File copied successfully",
                metadata={"destination": destination_folder}
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to copy file {file_id}: {str(e)}", exc_info=True)
            return self._handle_exception(e, "copy object", file_id)

    def move_object(
        self,
        file_id: UUID,
        destination_folder: str,
        new_filename: Optional[str] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Move a file to a different location in storage.
        
        Args:
            file_id: Source file identifier
            destination_folder: Target folder path
            new_filename: Optional new filename
            
        Returns:
            ServiceResult containing updated file information
        """
        try:
            logger.info(
                f"Moving file ID: {file_id} to folder: {destination_folder}"
            )
            
            # Validate destination folder
            if not destination_folder or not destination_folder.strip():
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Destination folder cannot be empty",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            result = self.repository.move_object(
                file_id,
                destination_folder,
                new_filename=new_filename
            )
            
            self.db.commit()
            
            logger.info(
                f"File moved successfully from {file_id} to {destination_folder}"
            )
            
            return ServiceResult.success(
                result or {},
                message="File moved successfully",
                metadata={"destination": destination_folder}
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to move file {file_id}: {str(e)}", exc_info=True)
            return self._handle_exception(e, "move object", file_id)

    def get_storage_info(
        self,
        file_id: UUID,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Retrieve storage-specific information about a file.
        
        Args:
            file_id: Unique identifier of the file
            
        Returns:
            ServiceResult containing storage metadata
        """
        try:
            logger.debug(f"Retrieving storage info for file ID: {file_id}")
            
            storage_info = self.repository.get_storage_info(file_id)
            
            if not storage_info:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Storage info not found for file {file_id}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            return ServiceResult.success(storage_info)
            
        except Exception as e:
            logger.error(
                f"Failed to get storage info for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get storage info", file_id)

    def restore_deleted_file(
        self,
        file_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Restore a soft-deleted file.
        
        Args:
            file_id: Unique identifier of the file
            
        Returns:
            ServiceResult indicating success or failure
        """
        try:
            logger.info(f"Restoring deleted file ID: {file_id}")
            
            success = self.repository.restore_file(file_id)
            
            if success:
                self.db.commit()
                logger.info(f"File restored successfully: {file_id}")
                return ServiceResult.success(True, message="File restored successfully")
            else:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="File restoration failed",
                        severity=ErrorSeverity.WARNING,
                    )
                )
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to restore file {file_id}: {str(e)}", exc_info=True)
            return self._handle_exception(e, "restore file", file_id)