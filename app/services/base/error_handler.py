"""
Service-layer error handling utilities.
"""

from typing import Optional, Dict, Any, Type
from traceback import format_exception
import sys

from app.core1.logging import get_logger
from app.services.base.service_result import (
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)


class ErrorHandler:
    """
    Centralized error handling for service layer with:
    - Exception mapping to error codes
    - Contextual logging
    - Error categorization
    - Stack trace capture
    """

    # Exception to ErrorCode mapping
    EXCEPTION_MAP: Dict[Type[Exception], ErrorCode] = {
        ValueError: ErrorCode.VALIDATION_ERROR,
        KeyError: ErrorCode.NOT_FOUND,
        AttributeError: ErrorCode.INVALID_REFERENCE,
        PermissionError: ErrorCode.INSUFFICIENT_PERMISSIONS,
        TimeoutError: ErrorCode.TIMEOUT,
    }

    def __init__(self, logger_name: str = "ServiceErrorHandler"):
        """
        Initialize error handler.
        
        Args:
            logger_name: Name for the logger instance
        """
        self._logger = get_logger(logger_name)

    # -------------------------------------------------------------------------
    # Error Handling
    # -------------------------------------------------------------------------

    def handle(
        self,
        exception: Exception,
        operation: str,
        entity_ref: Optional[Any] = None,
        severity: Optional[ErrorSeverity] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        include_traceback: bool = False,
    ) -> ServiceResult:
        """
        Handle exception and convert to ServiceResult.
        
        Args:
            exception: The exception to handle
            operation: Description of failed operation
            entity_ref: Reference to affected entity
            severity: Error severity (auto-determined if None)
            additional_context: Extra context for debugging
            include_traceback: Whether to include full traceback
            
        Returns:
            ServiceResult with failure status
        """
        # Determine error code and severity
        error_code = self._map_exception(exception)
        if severity is None:
            severity = self._determine_severity(exception, error_code)
        
        # Build error context
        context = {
            "operation": operation,
            "entity_ref": str(entity_ref) if entity_ref is not None else None,
            "exception_type": type(exception).__name__,
            "error_code": error_code.value,
        }
        
        if additional_context:
            context.update(additional_context)
        
        # Capture traceback if requested
        details = {
            "error": str(exception),
            "entity_ref": str(entity_ref) if entity_ref is not None else None,
        }
        
        if include_traceback:
            details["traceback"] = self._capture_traceback()
        
        if additional_context:
            details["context"] = additional_context
        
        # Log with appropriate level
        self._log_error(severity, operation, exception, context)
        
        # Create and return ServiceResult
        return ServiceResult.failure(
            ServiceError(
                code=error_code,
                message=f"Failed to {operation}",
                details=details,
                severity=severity,
            )
        )

    def handle_validation_error(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult:
        """
        Handle validation-specific errors.
        
        Args:
            message: Validation error message
            field: Field that failed validation
            details: Additional validation details
            
        Returns:
            ServiceResult with validation error
        """
        return ServiceResult.failure(
            ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message=message,
                field=field,
                details=details,
                severity=ErrorSeverity.WARNING,
            )
        )

    def handle_not_found(
        self,
        entity_type: str,
        entity_id: Any,
        additional_message: Optional[str] = None,
    ) -> ServiceResult:
        """
        Handle entity not found errors.
        
        Args:
            entity_type: Type of entity not found
            entity_id: ID of missing entity
            additional_message: Additional context message
            
        Returns:
            ServiceResult with not found error
        """
        message = f"{entity_type} with ID {entity_id} not found"
        if additional_message:
            message += f": {additional_message}"
        
        return ServiceResult.failure(
            ServiceError(
                code=ErrorCode.NOT_FOUND,
                message=message,
                details={
                    "entity_type": entity_type,
                    "entity_id": str(entity_id),
                },
                severity=ErrorSeverity.WARNING,
            )
        )

    def handle_permission_denied(
        self,
        operation: str,
        user_id: Optional[Any] = None,
        required_permission: Optional[str] = None,
    ) -> ServiceResult:
        """
        Handle permission denied errors.
        
        Args:
            operation: Operation that was denied
            user_id: ID of user denied access
            required_permission: Permission that was required
            
        Returns:
            ServiceResult with permission error
        """
        message = f"Permission denied for operation: {operation}"
        
        details = {}
        if user_id:
            details["user_id"] = str(user_id)
        if required_permission:
            details["required_permission"] = required_permission
        
        return ServiceResult.failure(
            ServiceError(
                code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                message=message,
                details=details,
                severity=ErrorSeverity.WARNING,
            )
        )

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def _map_exception(self, exception: Exception) -> ErrorCode:
        """
        Map exception type to ErrorCode.
        
        Args:
            exception: Exception to map
            
        Returns:
            Appropriate ErrorCode
        """
        for exc_type, error_code in self.EXCEPTION_MAP.items():
            if isinstance(exception, exc_type):
                return error_code
        
        return ErrorCode.INTERNAL_ERROR

    def _determine_severity(
        self,
        exception: Exception,
        error_code: ErrorCode,
    ) -> ErrorSeverity:
        """
        Determine error severity based on exception and code.
        
        Args:
            exception: The exception
            error_code: Mapped error code
            
        Returns:
            Appropriate ErrorSeverity
        """
        # Validation errors are warnings
        if error_code in [ErrorCode.VALIDATION_ERROR, ErrorCode.MISSING_REQUIRED_FIELD]:
            return ErrorSeverity.WARNING
        
        # Not found errors are warnings
        if error_code == ErrorCode.NOT_FOUND:
            return ErrorSeverity.WARNING
        
        # Permission errors are warnings
        if error_code in [ErrorCode.INSUFFICIENT_PERMISSIONS, ErrorCode.UNAUTHORIZED]:
            return ErrorSeverity.WARNING
        
        # Business rule violations are errors
        if error_code in [ErrorCode.BUSINESS_RULE_VIOLATION, ErrorCode.CONFLICT]:
            return ErrorSeverity.ERROR
        
        # Everything else is critical
        return ErrorSeverity.CRITICAL

    def _log_error(
        self,
        severity: ErrorSeverity,
        operation: str,
        exception: Exception,
        context: Dict[str, Any],
    ) -> None:
        """
        Log error with appropriate level.
        
        Args:
            severity: Error severity
            operation: Operation description
            exception: The exception
            context: Logging context
        """
        log_message = f"Error in {operation}: {exception}"
        
        if severity == ErrorSeverity.CRITICAL:
            self._logger.critical(log_message, exc_info=True, extra=context)
        elif severity == ErrorSeverity.ERROR:
            self._logger.error(log_message, exc_info=True, extra=context)
        elif severity == ErrorSeverity.WARNING:
            self._logger.warning(log_message, extra=context)
        else:  # INFO
            self._logger.info(log_message, extra=context)

    def _capture_traceback(self) -> str:
        """
        Capture current exception traceback.
        
        Returns:
            Formatted traceback string
        """
        exc_type, exc_value, exc_traceback = sys.exc_info()
        if exc_type is None:
            return ""
        
        return "".join(format_exception(exc_type, exc_value, exc_traceback))