"""
Custom Exception Classes

Comprehensive exception hierarchy for the hostel management system
with detailed error handling and proper HTTP status codes.
"""

from typing import Any, Dict, Optional, List
from fastapi import HTTPException, status


class BaseHostelException(Exception):
    """Base exception class for all hostel management exceptions"""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)


class AdminAPIException(HTTPException):
    """Base exception for Admin API specific errors"""
    
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code or self.__class__.__name__


# ============================================================================
# Authentication and Authorization Exceptions
# ============================================================================

class AuthenticationError(AdminAPIException):
    """Authentication failed"""
    
    def __init__(self, detail: str = "Authentication failed", **kwargs):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
            **kwargs
        )


class AuthorizationError(AdminAPIException):
    """Authorization failed"""
    
    def __init__(self, detail: str = "Insufficient permissions", **kwargs):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            **kwargs
        )


class InvalidTokenError(AuthenticationError):
    """Invalid or expired token"""
    
    def __init__(self, detail: str = "Invalid or expired token", **kwargs):
        super().__init__(detail=detail, **kwargs)


class TokenExpiredError(AuthenticationError):
    """Token has expired"""
    
    def __init__(self, detail: str = "Token has expired", **kwargs):
        super().__init__(detail=detail, **kwargs)


class PermissionError(AuthorizationError):
    """Permission denied for specific operation"""
    
    def __init__(
        self,
        detail: str = "Permission denied",
        required_permission: Optional[str] = None,
        **kwargs
    ):
        self.required_permission = required_permission
        super().__init__(detail=detail, **kwargs)


# ============================================================================
# Validation Exceptions
# ============================================================================

class ValidationError(AdminAPIException):
    """Data validation failed"""
    
    def __init__(
        self,
        detail: str = "Validation failed",
        field_errors: Optional[Dict[str, List[str]]] = None,
        **kwargs
    ):
        self.field_errors = field_errors or {}
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            **kwargs
        )


class BusinessRuleViolationError(ValidationError):
    """Business rule validation failed"""
    
    def __init__(
        self,
        detail: str = "Business rule violation",
        violated_rules: Optional[List[str]] = None,
        **kwargs
    ):
        self.violated_rules = violated_rules or []
        super().__init__(detail=detail, **kwargs)


class DuplicateRecordError(AdminAPIException):
    """Duplicate record found"""
    
    def __init__(
        self,
        detail: str = "Duplicate record found",
        conflicting_fields: Optional[List[str]] = None,
        **kwargs
    ):
        self.conflicting_fields = conflicting_fields or []
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            **kwargs
        )


class InvalidInputError(ValidationError):
    """Invalid input data"""
    
    def __init__(self, detail: str = "Invalid input data", **kwargs):
        super().__init__(detail=detail, **kwargs)


# ============================================================================
# Resource Exceptions
# ============================================================================

class ResourceNotFoundError(AdminAPIException):
    """Resource not found"""
    
    def __init__(
        self,
        detail: str = "Resource not found",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs
    ):
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            **kwargs
        )


class AdminNotFoundError(ResourceNotFoundError):
    """Admin user not found"""
    
    def __init__(self, admin_id: str, **kwargs):
        super().__init__(
            detail=f"Admin user with ID '{admin_id}' not found",
            resource_type="admin",
            resource_id=admin_id,
            **kwargs
        )


class HostelNotFoundError(ResourceNotFoundError):
    """Hostel not found"""
    
    def __init__(self, hostel_id: str, **kwargs):
        super().__init__(
            detail=f"Hostel with ID '{hostel_id}' not found",
            resource_type="hostel",
            resource_id=hostel_id,
            **kwargs
        )


class AssignmentNotFoundError(ResourceNotFoundError):
    """Assignment not found"""
    
    def __init__(self, assignment_id: str, **kwargs):
        super().__init__(
            detail=f"Assignment with ID '{assignment_id}' not found",
            resource_type="assignment",
            resource_id=assignment_id,
            **kwargs
        )


class OverrideNotFoundError(ResourceNotFoundError):
    """Override not found"""
    
    def __init__(self, override_id: str, **kwargs):
        super().__init__(
            detail=f"Override with ID '{override_id}' not found",
            resource_type="override",
            resource_id=override_id,
            **kwargs
        )


class PermissionNotFoundError(ResourceNotFoundError):
    """Permission not found"""
    
    def __init__(self, permission_id: str, **kwargs):
        super().__init__(
            detail=f"Permission with ID '{permission_id}' not found",
            resource_type="permission",
            resource_id=permission_id,
            **kwargs
        )


# ============================================================================
# Operation Exceptions
# ============================================================================

class OperationError(AdminAPIException):
    """Generic operation failed"""
    
    def __init__(
        self,
        detail: str = "Operation failed",
        operation: Optional[str] = None,
        **kwargs
    ):
        self.operation = operation
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            **kwargs
        )


class ConcurrencyError(AdminAPIException):
    """Concurrent modification detected"""
    
    def __init__(self, detail: str = "Concurrent modification detected", **kwargs):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            **kwargs
        )


class StateTransitionError(AdminAPIException):
    """Invalid state transition"""
    
    def __init__(
        self,
        detail: str = "Invalid state transition",
        current_state: Optional[str] = None,
        target_state: Optional[str] = None,
        **kwargs
    ):
        self.current_state = current_state
        self.target_state = target_state
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            **kwargs
        )


class DuplicateAssignmentError(DuplicateRecordError):
    """Duplicate assignment found"""
    
    def __init__(self, admin_id: str, hostel_id: str, **kwargs):
        super().__init__(
            detail=f"Assignment already exists for admin '{admin_id}' and hostel '{hostel_id}'",
            **kwargs
        )


class InvalidOverrideError(ValidationError):
    """Invalid override request"""
    
    def __init__(self, detail: str = "Invalid override request", **kwargs):
        super().__init__(detail=detail, **kwargs)


class InvalidPermissionError(ValidationError):
    """Invalid permission configuration"""
    
    def __init__(self, detail: str = "Invalid permission configuration", **kwargs):
        super().__init__(detail=detail, **kwargs)


class ContextSwitchError(OperationError):
    """Context switch operation failed"""
    
    def __init__(self, detail: str = "Context switch failed", **kwargs):
        super().__init__(
            detail=detail,
            operation="context_switch",
            **kwargs
        )


# ============================================================================
# System and Infrastructure Exceptions
# ============================================================================

class DatabaseError(OperationError):
    """Database operation failed"""
    
    def __init__(self, detail: str = "Database operation failed", **kwargs):
        super().__init__(
            detail=detail,
            operation="database",
            **kwargs
        )


class CacheError(OperationError):
    """Cache operation failed"""
    
    def __init__(self, detail: str = "Cache operation failed", **kwargs):
        super().__init__(
            detail=detail,
            operation="cache",
            **kwargs
        )


class ExternalServiceError(OperationError):
    """External service operation failed"""
    
    def __init__(
        self,
        detail: str = "External service operation failed",
        service_name: Optional[str] = None,
        **kwargs
    ):
        self.service_name = service_name
        super().__init__(
            detail=detail,
            operation="external_service",
            **kwargs
        )


class ConfigurationError(BaseHostelException):
    """Configuration error"""
    
    def __init__(self, detail: str = "Configuration error", **kwargs):
        super().__init__(message=detail, **kwargs)


# ============================================================================
# Rate Limiting and Traffic Control
# ============================================================================

class RateLimitExceeded(AdminAPIException):
    """Rate limit exceeded"""
    
    def __init__(
        self,
        detail: str = "Rate limit exceeded",
        retry_after: int = 60,
        limit: Optional[int] = None,
        **kwargs
    ):
        self.retry_after = retry_after
        self.limit = limit
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(retry_after)},
            **kwargs
        )


class MaintenanceMode(AdminAPIException):
    """Service in maintenance mode"""
    
    def __init__(
        self,
        detail: str = "Service temporarily unavailable",
        maintenance_window: Optional[str] = None,
        estimated_completion: Optional[str] = None,
        **kwargs
    ):
        self.maintenance_window = maintenance_window
        self.estimated_completion = estimated_completion
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
            headers={"Retry-After": "3600"},  # 1 hour default
            **kwargs
        )


class APIDeprecated(AdminAPIException):
    """API endpoint deprecated"""
    
    def __init__(
        self,
        detail: str = "API endpoint deprecated",
        deprecation_date: Optional[str] = None,
        removal_date: Optional[str] = None,
        migration_guide: Optional[str] = None,
        **kwargs
    ):
        self.deprecation_date = deprecation_date
        self.removal_date = removal_date
        self.migration_guide = migration_guide
        super().__init__(
            status_code=status.HTTP_410_GONE,
            detail=detail,
            **kwargs
        )


# ============================================================================
# Background Task Exceptions
# ============================================================================

class TaskExecutionError(OperationError):
    """Background task execution failed"""
    
    def __init__(
        self,
        detail: str = "Task execution failed",
        task_id: Optional[str] = None,
        **kwargs
    ):
        self.task_id = task_id
        super().__init__(
            detail=detail,
            operation="background_task",
            **kwargs
        )


class TaskTimeoutError(TaskExecutionError):
    """Background task timed out"""
    
    def __init__(
        self,
        detail: str = "Task execution timed out",
        timeout_seconds: Optional[int] = None,
        **kwargs
    ):
        self.timeout_seconds = timeout_seconds
        super().__init__(detail=detail, **kwargs)


class TaskRetryExhaustedError(TaskExecutionError):
    """Background task retry attempts exhausted"""
    
    def __init__(
        self,
        detail: str = "Task retry attempts exhausted",
        max_retries: Optional[int] = None,
        **kwargs
    ):
        self.max_retries = max_retries
        super().__init__(detail=detail, **kwargs)


# ============================================================================
# Notification Exceptions
# ============================================================================

class NotificationError(OperationError):
    """Notification delivery failed"""
    
    def __init__(
        self,
        detail: str = "Notification delivery failed",
        notification_type: Optional[str] = None,
        recipient: Optional[str] = None,
        **kwargs
    ):
        self.notification_type = notification_type
        self.recipient = recipient
        super().__init__(
            detail=detail,
            operation="notification",
            **kwargs
        )


class EmailDeliveryError(NotificationError):
    """Email delivery failed"""
    
    def __init__(
        self,
        detail: str = "Email delivery failed",
        recipient_email: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            detail=detail,
            notification_type="email",
            recipient=recipient_email,
            **kwargs
        )


class SMSDeliveryError(NotificationError):
    """SMS delivery failed"""
    
    def __init__(
        self,
        detail: str = "SMS delivery failed",
        recipient_phone: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            detail=detail,
            notification_type="sms",
            recipient=recipient_phone,
            **kwargs
        )


# ============================================================================
# Exception Utilities
# ============================================================================

def create_exception_response(
    exception: BaseHostelException,
    include_details: bool = False
) -> Dict[str, Any]:
    """Create standardized exception response"""
    response = {
        "error": True,
        "error_code": exception.error_code,
        "message": str(exception),
        "timestamp": time.time()
    }
    
    if include_details and hasattr(exception, 'details'):
        response["details"] = exception.details
    
    return response


def handle_database_exception(e: Exception) -> DatabaseError:
    """Convert database exceptions to standardized format"""
    if "duplicate key value" in str(e).lower():
        return DuplicateRecordError("Record already exists")
    elif "foreign key constraint" in str(e).lower():
        return ValidationError("Invalid reference to related record")
    elif "not null constraint" in str(e).lower():
        return ValidationError("Required field cannot be empty")
    else:
        return DatabaseError(f"Database operation failed: {str(e)}")


def handle_validation_exception(errors: List[Dict[str, Any]]) -> ValidationError:
    """Convert validation errors to standardized format"""
    field_errors = {}
    
    for error in errors:
        field = ".".join(str(loc) for loc in error.get("loc", []))
        message = error.get("msg", "Invalid value")
        
        if field not in field_errors:
            field_errors[field] = []
        field_errors[field].append(message)
    
    return ValidationError(
        detail="Validation failed",
        field_errors=field_errors
    )


# Export all exceptions for easy importing
__all__ = [
    # Base exceptions
    "BaseHostelException",
    "AdminAPIException",
    
    # Authentication/Authorization
    "AuthenticationError",
    "AuthorizationError", 
    "InvalidTokenError",
    "TokenExpiredError",
    "PermissionError",
    
    # Validation
    "ValidationError",
    "BusinessRuleViolationError",
    "DuplicateRecordError",
    "InvalidInputError",
    
    # Resources
    "ResourceNotFoundError",
    "AdminNotFoundError",
    "HostelNotFoundError",
    "AssignmentNotFoundError",
    "OverrideNotFoundError",
    "PermissionNotFoundError",
    
    # Operations
    "OperationError",
    "ConcurrencyError",
    "StateTransitionError",
    "DuplicateAssignmentError",
    "InvalidOverrideError",
    "InvalidPermissionError",
    "ContextSwitchError",
    
    # System
    "DatabaseError",
    "CacheError",
    "ExternalServiceError",
    "ConfigurationError",
    
    # Traffic Control
    "RateLimitExceeded",
    "MaintenanceMode",
    "APIDeprecated",
    
    # Background Tasks
    "TaskExecutionError",
    "TaskTimeoutError",
    "TaskRetryExhaustedError",
    
    # Notifications
    "NotificationError",
    "EmailDeliveryError",
    "SMSDeliveryError",
    
    # Utilities
    "create_exception_response",
    "handle_database_exception",
    "handle_validation_exception"
]