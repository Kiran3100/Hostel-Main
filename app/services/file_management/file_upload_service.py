"""
File Upload Lifecycle Service

Handles complete file upload workflows including:
- Single-part upload initialization and completion
- Multipart upload for large files
- Upload state management and verification
- Download URL generation
"""

from typing import Optional, List
from uuid import UUID
import logging

from sqlalchemy.orm import Session

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.file_management.file_upload_repository import FileUploadRepository
from app.models.file_management.file_upload import FileUpload as FileUploadModel
from app.schemas.file.file_upload import (
    FileUploadInitRequest,
    FileUploadInitResponse,
    FileUploadCompleteRequest,
    FileUploadCompleteResponse,
    MultipartUploadInitRequest,
    MultipartUploadPart,
    MultipartUploadCompleteRequest,
)
from app.schemas.file.file_response import FileInfo, FileURL

logger = logging.getLogger(__name__)


class FileUploadService(BaseService[FileUploadModel, FileUploadRepository]):
    """
    Orchestrates file upload flows through the repository layer.
    
    Features:
    - Pre-signed URL generation for direct uploads
    - Multipart upload support for large files
    - Upload verification and integrity checks
    - Automatic cleanup of failed uploads
    """

    def __init__(self, repository: FileUploadRepository, db_session: Session):
        """
        Initialize the file upload service.
        
        Args:
            repository: File upload repository instance
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)
        self._max_single_upload_size = 100 * 1024 * 1024  # 100MB
        logger.info("FileUploadService initialized")

    def init_upload(
        self,
        request: FileUploadInitRequest,
    ) -> ServiceResult[FileUploadInitResponse]:
        """
        Initialize a single-part upload with pre-signed URL.
        
        Args:
            request: Upload initialization request containing file metadata
            
        Returns:
            ServiceResult containing upload initialization response with pre-signed URL
            
        Raises:
            ServiceError: If file size exceeds single upload limit
        """
        try:
            # Validate file size for single-part upload
            if request.size_bytes > self._max_single_upload_size:
                logger.warning(
                    f"File size {request.size_bytes} exceeds single upload limit "
                    f"{self._max_single_upload_size}. Consider multipart upload."
                )
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"File size exceeds {self._max_single_upload_size} bytes. "
                                "Please use multipart upload.",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            logger.info(
                f"Initializing upload for file: {request.filename}, "
                f"size: {request.size_bytes}, type: {request.content_type}"
            )
            
            resp = self.repository.init_upload(request)
            self.db.commit()
            
            logger.info(f"Upload initialized successfully with ID: {resp.file_id}")
            return ServiceResult.success(
                resp,
                message="Upload initialized successfully"
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to initialize upload: {str(e)}", exc_info=True)
            return self._handle_exception(e, "init upload")

    def complete_upload(
        self,
        request: FileUploadCompleteRequest,
    ) -> ServiceResult[FileUploadCompleteResponse]:
        """
        Complete an upload with checksum verification.
        
        Args:
            request: Upload completion request with file ID and verification data
            
        Returns:
            ServiceResult containing completion response with final file info
        """
        try:
            logger.info(f"Completing upload for file ID: {request.file_id}")
            
            resp = self.repository.complete_upload(request)
            self.db.commit()
            
            logger.info(
                f"Upload completed successfully for file ID: {request.file_id}, "
                f"final size: {resp.file_info.size_bytes if resp.file_info else 'unknown'}"
            )
            
            return ServiceResult.success(
                resp,
                message="Upload completed and verified successfully"
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Failed to complete upload for file {request.file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "complete upload", request.file_id)

    def init_multipart(
        self,
        request: MultipartUploadInitRequest,
    ) -> ServiceResult[List[MultipartUploadPart]]:
        """
        Initialize multipart upload and generate signed part URLs.
        
        Args:
            request: Multipart upload initialization request
            
        Returns:
            ServiceResult containing list of upload parts with pre-signed URLs
        """
        try:
            logger.info(
                f"Initializing multipart upload for file: {request.filename}, "
                f"size: {request.size_bytes}, parts: {request.total_parts}"
            )
            
            if request.total_parts < 2:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Multipart upload requires at least 2 parts",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            parts = self.repository.init_multipart(request)
            self.db.commit()
            
            logger.info(
                f"Multipart upload initialized with {len(parts)} parts "
                f"for file ID: {request.file_id if hasattr(request, 'file_id') else 'new'}"
            )
            
            return ServiceResult.success(
                parts,
                message=f"Multipart upload initialized with {len(parts)} parts",
                metadata={"total_parts": len(parts)}
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to initialize multipart upload: {str(e)}", exc_info=True)
            return self._handle_exception(e, "init multipart upload")

    def complete_multipart(
        self,
        request: MultipartUploadCompleteRequest,
    ) -> ServiceResult[FileUploadCompleteResponse]:
        """
        Complete multipart upload by combining all parts.
        
        Args:
            request: Multipart completion request with part ETags
            
        Returns:
            ServiceResult containing final file information
        """
        try:
            logger.info(
                f"Completing multipart upload for file ID: {request.file_id}, "
                f"parts: {len(request.parts) if request.parts else 0}"
            )
            
            resp = self.repository.complete_multipart(request)
            self.db.commit()
            
            logger.info(
                f"Multipart upload completed successfully for file ID: {request.file_id}"
            )
            
            return ServiceResult.success(
                resp,
                message="Multipart upload completed and assembled successfully"
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Failed to complete multipart upload for file {request.file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "complete multipart upload", request.file_id)

    def get_file_info(
        self,
        file_id: UUID,
        include_metadata: bool = False,
    ) -> ServiceResult[FileInfo]:
        """
        Retrieve comprehensive file information.
        
        Args:
            file_id: Unique identifier of the file
            include_metadata: Whether to include extended metadata
            
        Returns:
            ServiceResult containing file information
        """
        try:
            logger.debug(f"Retrieving file info for ID: {file_id}")
            
            info = self.repository.get_file_info(file_id)
            
            if not info:
                logger.warning(f"File not found with ID: {file_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"File with ID {file_id} not found",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            return ServiceResult.success(info)
            
        except Exception as e:
            logger.error(f"Failed to get file info for {file_id}: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get file info", file_id)

    def get_download_url(
        self,
        file_id: UUID,
        expires_in_seconds: int = 900,
        inline: bool = False,
    ) -> ServiceResult[FileURL]:
        """
        Generate a time-limited download URL.
        
        Args:
            file_id: Unique identifier of the file
            expires_in_seconds: URL expiration time (default: 15 minutes)
            inline: Whether to serve inline or as attachment
            
        Returns:
            ServiceResult containing signed download URL
        """
        try:
            logger.info(
                f"Generating download URL for file ID: {file_id}, "
                f"expires in: {expires_in_seconds}s, inline: {inline}"
            )
            
            # Validate expiration time
            if expires_in_seconds < 60 or expires_in_seconds > 604800:  # 1 min to 7 days
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Expiration time must be between 60 and 604800 seconds",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            url_type = "inline" if inline else "download"
            url = self.repository.get_signed_url(
                file_id,
                url_type=url_type,
                expires_in=expires_in_seconds
            )
            
            logger.info(f"Download URL generated successfully for file ID: {file_id}")
            
            return ServiceResult.success(
                url,
                metadata={"expires_in": expires_in_seconds, "type": url_type}
            )
            
        except Exception as e:
            logger.error(
                f"Failed to generate download URL for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get download url", file_id)

    def abort_upload(
        self,
        file_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Abort an in-progress upload and clean up resources.
        
        Args:
            file_id: Unique identifier of the file
            
        Returns:
            ServiceResult indicating success or failure
        """
        try:
            logger.info(f"Aborting upload for file ID: {file_id}")
            
            success = self.repository.abort_upload(file_id)
            
            if success:
                self.db.commit()
                logger.info(f"Upload aborted successfully for file ID: {file_id}")
                return ServiceResult.success(True, message="Upload aborted successfully")
            else:
                logger.warning(f"Failed to abort upload for file ID: {file_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to abort upload",
                        severity=ErrorSeverity.WARNING,
                    )
                )
                
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error aborting upload for file {file_id}: {str(e)}", exc_info=True)
            return self._handle_exception(e, "abort upload", file_id)

    @property
    def max_single_upload_size(self) -> int:
        """Get the maximum file size for single-part uploads."""
        return self._max_single_upload_size

    @max_single_upload_size.setter
    def max_single_upload_size(self, size: int) -> None:
        """Set the maximum file size for single-part uploads."""
        if size < 1024 * 1024:  # Minimum 1MB
            raise ValueError("Maximum upload size must be at least 1MB")
        self._max_single_upload_size = size
        logger.info(f"Max single upload size set to: {size} bytes")