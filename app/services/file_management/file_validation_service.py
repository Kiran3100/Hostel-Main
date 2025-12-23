"""
File Validation and Security Service

Provides:
- Pre-upload validation (filename, type, size)
- MIME type verification
- File extension whitelisting/blacklisting
- Antivirus scanning integration
- Content inspection
"""

from typing import Optional, Dict, Any, List, Set
from uuid import UUID
import logging
import re

from sqlalchemy.orm import Session

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.file_management.file_upload_repository import FileUploadRepository
from app.models.file_management.file_upload import FileUpload as FileUploadModel
from app.schemas.file.file_upload import FileUploadInitRequest
from app.schemas.file.file_response import FileInfo
from app.utils.validators import FileValidator

logger = logging.getLogger(__name__)


class FileValidationService(BaseService[FileUploadModel, FileUploadRepository]):
    """
    Comprehensive file validation and security scanning.
    
    Features:
    - Multi-layer validation (filename, type, size, content)
    - Malware detection via antivirus integration
    - Configurable security policies
    - Quarantine management for suspicious files
    """

    # Dangerous file extensions
    DANGEROUS_EXTENSIONS: Set[str] = {
        'exe', 'bat', 'cmd', 'com', 'pif', 'scr', 'vbs', 'js',
        'jar', 'app', 'deb', 'rpm', 'sh', 'ps1', 'msi', 'dll'
    }

    # Safe filename pattern
    SAFE_FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9._\-\s()]+$')

    def __init__(
        self,
        repository: FileUploadRepository,
        db_session: Session,
        enable_antivirus: bool = True
    ):
        """
        Initialize the file validation service.
        
        Args:
            repository: File upload repository instance
            db_session: SQLAlchemy database session
            enable_antivirus: Whether to enable antivirus scanning
        """
        super().__init__(repository, db_session)
        self.validator = FileValidator()
        self.enable_antivirus = enable_antivirus
        self._max_file_size = 500 * 1024 * 1024  # 500MB default
        self._allowed_extensions: Optional[Set[str]] = None
        self._blocked_extensions: Set[str] = self.DANGEROUS_EXTENSIONS.copy()
        logger.info(
            f"FileValidationService initialized, antivirus: {enable_antivirus}"
        )

    def preflight_validate(
        self,
        request: FileUploadInitRequest,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Comprehensive pre-upload validation.
        
        Args:
            request: Upload initialization request
            
        Returns:
            ServiceResult with validation results
        """
        try:
            validation_results = {
                "filename_valid": False,
                "extension_valid": False,
                "content_type_valid": False,
                "size_valid": False,
                "overall_valid": False,
                "warnings": [],
                "errors": []
            }

            logger.info(
                f"Running preflight validation for file: {request.filename}, "
                f"size: {request.size_bytes}, type: {request.content_type}"
            )

            # 1. Validate filename
            filename_result = self._validate_filename(request.filename)
            validation_results["filename_valid"] = filename_result.success
            if not filename_result.success:
                validation_results["errors"].append(filename_result.error.message)

            # 2. Validate file extension
            extension_result = self._validate_extension(request.filename)
            validation_results["extension_valid"] = extension_result.success
            if not extension_result.success:
                validation_results["errors"].append(extension_result.error.message)

            # 3. Validate content type
            content_type_result = self._validate_content_type(request.content_type)
            validation_results["content_type_valid"] = content_type_result.success
            if not content_type_result.success:
                validation_results["errors"].append(content_type_result.error.message)

            # 4. Validate file size
            size_result = self._validate_size(request.size_bytes)
            validation_results["size_valid"] = size_result.success
            if not size_result.success:
                validation_results["errors"].append(size_result.error.message)

            # 5. Additional warnings
            if request.size_bytes > 100 * 1024 * 1024:  # > 100MB
                validation_results["warnings"].append(
                    "Large file detected. Consider using multipart upload."
                )

            # Overall validation
            validation_results["overall_valid"] = all([
                validation_results["filename_valid"],
                validation_results["extension_valid"],
                validation_results["content_type_valid"],
                validation_results["size_valid"]
            ])

            if validation_results["overall_valid"]:
                logger.info(f"Preflight validation passed for: {request.filename}")
                return ServiceResult.success(
                    validation_results,
                    message="Validation passed"
                )
            else:
                logger.warning(
                    f"Preflight validation failed for: {request.filename}, "
                    f"errors: {validation_results['errors']}"
                )
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="; ".join(validation_results["errors"]),
                        severity=ErrorSeverity.WARNING,
                        details=validation_results
                    )
                )

        except Exception as e:
            logger.error(f"Preflight validation error: {str(e)}", exc_info=True)
            return self._handle_exception(e, "preflight validate file")

    def _validate_filename(self, filename: str) -> ServiceResult[bool]:
        """
        Validate filename for safety and format.
        
        Args:
            filename: Name of the file
            
        Returns:
            ServiceResult indicating validity
        """
        try:
            if not filename or not filename.strip():
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Filename cannot be empty",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Check length
            if len(filename) > 255:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Filename too long (max 255 characters)",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Check for path traversal attempts
            if '..' in filename or '/' in filename or '\\' in filename:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Invalid characters in filename (path traversal detected)",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            # Check for safe characters
            if not self.SAFE_FILENAME_PATTERN.match(filename):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Filename contains invalid characters",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Additional validator check
            if not self.validator.validate_filename(filename):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Filename failed security validation",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            return ServiceResult.success(True)

        except Exception as e:
            logger.error(f"Filename validation error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Filename validation failed: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                )
            )

    def _validate_extension(self, filename: str) -> ServiceResult[bool]:
        """
        Validate file extension against whitelist/blacklist.
        
        Args:
            filename: Name of the file
            
        Returns:
            ServiceResult indicating validity
        """
        try:
            # Extract extension
            if '.' not in filename:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="File must have an extension",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            extension = filename.rsplit('.', 1)[-1].lower()

            # Check blacklist first (higher priority)
            if extension in self._blocked_extensions:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"File type '.{extension}' is not allowed (security risk)",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            # Check whitelist if configured
            if self._allowed_extensions is not None:
                if extension not in self._allowed_extensions:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"File type '.{extension}' is not in allowed list",
                            severity=ErrorSeverity.WARNING,
                        )
                    )

            return ServiceResult.success(True)

        except Exception as e:
            logger.error(f"Extension validation error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Extension validation failed: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                )
            )

    def _validate_content_type(self, content_type: str) -> ServiceResult[bool]:
        """
        Validate MIME type.
        
        Args:
            content_type: MIME type of the file
            
        Returns:
            ServiceResult indicating validity
        """
        try:
            if not content_type or not content_type.strip():
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Content type cannot be empty",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Use validator
            if not self.validator.validate_content_type(content_type):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Unsupported content type: {content_type}",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            return ServiceResult.success(True)

        except Exception as e:
            logger.error(f"Content type validation error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Content type validation failed: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                )
            )

    def _validate_size(self, size_bytes: int) -> ServiceResult[bool]:
        """
        Validate file size.
        
        Args:
            size_bytes: File size in bytes
            
        Returns:
            ServiceResult indicating validity
        """
        try:
            if size_bytes <= 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="File size must be greater than 0",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            if size_bytes > self._max_file_size:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"File size exceeds maximum allowed ({self._max_file_size} bytes)",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Use validator
            if not self.validator.validate_size(size_bytes):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="File size validation failed",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            return ServiceResult.success(True)

        except Exception as e:
            logger.error(f"Size validation error: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Size validation failed: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                )
            )

    def run_antivirus_scan(
        self,
        file_id: UUID,
        force: bool = False,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Trigger antivirus scanning via repository/provider.
        
        Args:
            file_id: Unique identifier of the file
            force: Force rescan even if already scanned
            
        Returns:
            ServiceResult containing scan results
        """
        try:
            if not self.enable_antivirus:
                logger.warning("Antivirus scanning is disabled")
                return ServiceResult.success(
                    {"status": "skipped", "reason": "antivirus_disabled"},
                    message="Antivirus scanning is disabled"
                )

            logger.info(f"Running antivirus scan for file ID: {file_id}")

            result = self.repository.scan_file(file_id, force=force)

            if result:
                self.db.commit()

                scan_status = result.get("status", "unknown")
                threats_found = result.get("threats_found", 0)

                if scan_status == "clean":
                    logger.info(f"File {file_id} passed antivirus scan")
                    return ServiceResult.success(
                        result,
                        message="File is clean"
                    )
                elif scan_status == "infected":
                    logger.error(
                        f"File {file_id} is infected! Threats: {threats_found}"
                    )
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.SECURITY_ERROR,
                            message=f"File is infected with {threats_found} threat(s)",
                            severity=ErrorSeverity.CRITICAL,
                            details=result
                        )
                    )
                else:
                    logger.warning(f"Scan completed with status: {scan_status}")
                    return ServiceResult.success(result, message=f"Scan status: {scan_status}")
            else:
                logger.error("Antivirus scan returned no result")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Antivirus scan failed",
                        severity=ErrorSeverity.ERROR,
                    )
                )

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Antivirus scan error for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "run antivirus scan", file_id)

    def quarantine_file(
        self,
        file_id: UUID,
        reason: str,
        quarantined_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Quarantine a suspicious or infected file.
        
        Args:
            file_id: Unique identifier of the file
            reason: Reason for quarantine
            quarantined_by: User ID who initiated quarantine
            
        Returns:
            ServiceResult indicating success or failure
        """
        try:
            logger.warning(f"Quarantining file {file_id}, reason: {reason}")

            success = self.repository.quarantine_file(
                file_id,
                reason=reason,
                quarantined_by=quarantined_by
            )

            if success:
                self.db.commit()
                logger.info(f"File {file_id} quarantined successfully")
                return ServiceResult.success(True, message="File quarantined successfully")
            else:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to quarantine file",
                        severity=ErrorSeverity.ERROR,
                    )
                )

        except Exception as e:
            self.db.rollback()
            logger.error(f"Quarantine failed for file {file_id}: {str(e)}", exc_info=True)
            return self._handle_exception(e, "quarantine file", file_id)

    def release_from_quarantine(
        self,
        file_id: UUID,
        released_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Release a file from quarantine.
        
        Args:
            file_id: Unique identifier of the file
            released_by: User ID who released the file
            
        Returns:
            ServiceResult indicating success or failure
        """
        try:
            logger.info(f"Releasing file {file_id} from quarantine")

            success = self.repository.release_from_quarantine(
                file_id,
                released_by=released_by
            )

            if success:
                self.db.commit()
                logger.info(f"File {file_id} released from quarantine")
                return ServiceResult.success(True, message="File released from quarantine")
            else:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to release file from quarantine",
                        severity=ErrorSeverity.ERROR,
                    )
                )

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Release from quarantine failed for file {file_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "release from quarantine", file_id)

    def configure_allowed_extensions(self, extensions: List[str]) -> None:
        """
        Configure whitelist of allowed file extensions.
        
        Args:
            extensions: List of allowed extensions (without dots)
        """
        self._allowed_extensions = {ext.lower().strip('.') for ext in extensions}
        logger.info(f"Allowed extensions configured: {self._allowed_extensions}")

    def configure_blocked_extensions(self, extensions: List[str]) -> None:
        """
        Configure blacklist of blocked file extensions.
        
        Args:
            extensions: List of blocked extensions (without dots)
        """
        self._blocked_extensions = {ext.lower().strip('.') for ext in extensions}
        logger.info(f"Blocked extensions configured: {self._blocked_extensions}")

    def add_blocked_extension(self, extension: str) -> None:
        """Add a single extension to the blocklist."""
        self._blocked_extensions.add(extension.lower().strip('.'))
        logger.info(f"Added blocked extension: {extension}")

    def remove_blocked_extension(self, extension: str) -> None:
        """Remove an extension from the blocklist."""
        self._blocked_extensions.discard(extension.lower().strip('.'))
        logger.info(f"Removed blocked extension: {extension}")

    @property
    def max_file_size(self) -> int:
        """Get the maximum allowed file size."""
        return self._max_file_size

    @max_file_size.setter
    def max_file_size(self, size: int) -> None:
        """Set the maximum allowed file size."""
        if size < 1024:  # Minimum 1KB
            raise ValueError("Maximum file size must be at least 1KB")
        self._max_file_size = size
        logger.info(f"Max file size set to: {size} bytes")