"""
Service result patterns for standardized response handling.
"""

from typing import TypeVar, Generic, Optional, Any, Dict, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone


class ErrorCode(str, Enum):
    """Standard error codes for service operations."""
    
    # General errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    
    # Business logic errors
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    INVALID_STATE = "INVALID_STATE"
    CONFLICT = "CONFLICT"
    
    # Security errors
    UNAUTHORIZED = "UNAUTHORIZED"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    
    # Data errors
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FORMAT = "INVALID_FORMAT"
    INVALID_REFERENCE = "INVALID_REFERENCE"
    
    # External service errors
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"


class ErrorSeverity(str, Enum):
    """Error severity levels."""
    
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class ServiceError:
    """Represents a service operation error with context."""
    
    code: ErrorCode
    message: str
    severity: ErrorSeverity = ErrorSeverity.ERROR
    details: Optional[Dict[str, Any]] = None
    field: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation."""
        return {
            "code": self.code.value,
            "message": self.message,
            "severity": self.severity.value,
            "details": self.details,
            "field": self.field,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


TData = TypeVar("TData")


@dataclass
class ServiceResult(Generic[TData]):
    """
    Standardized service operation result with success/failure pattern.
    
    Attributes:
        is_success: Operation success indicator
        data: Result data (if successful)
        error: Error information (if failed)
        message: Human-readable status message
        metadata: Additional context information
    """
    
    is_success: bool
    data: Optional[TData] = None
    error: Optional[ServiceError] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @classmethod
    def success(
        cls,
        data: Optional[TData] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ServiceResult[TData]":
        """Create a successful result."""
        return cls(
            is_success=True,
            data=data,
            message=message,
            metadata=metadata or {},
        )
    
    @classmethod
    def failure(
        cls,
        error: ServiceError,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ServiceResult[TData]":
        """Create a failed result."""
        return cls(
            is_success=False,
            error=error,
            message=error.message,
            metadata=metadata or {},
        )
    
    @classmethod
    def from_exception(
        cls,
        exception: Exception,
        operation: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
    ) -> "ServiceResult[TData]":
        """Create a failed result from an exception."""
        return cls.failure(
            ServiceError(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to {operation}: {str(exception)}",
                severity=severity,
                details={"exception_type": type(exception).__name__},
            )
        )
    
    @classmethod
    def validation_failure(
        cls,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> "ServiceResult[TData]":
        """Create a validation failure result."""
        return cls.failure(
            ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message=message,
                field=field,
                details=details,
            )
        )
    
    @classmethod
    def not_found(
        cls,
        resource_type: str,
        resource_id: Optional[str] = None,
    ) -> "ServiceResult[TData]":
        """Create a not found failure result."""
        message = f"{resource_type} not found"
        if resource_id:
            message += f" (ID: {resource_id})"
        
        return cls.failure(
            ServiceError(
                code=ErrorCode.NOT_FOUND,
                message=message,
                details={"resource_type": resource_type, "resource_id": resource_id},
            )
        )
    
    @classmethod
    def unauthorized(
        cls,
        action: Optional[str] = None,
        resource: Optional[str] = None,
    ) -> "ServiceResult[TData]":
        """Create an unauthorized failure result."""
        message = "Unauthorized access"
        if action:
            message += f" to {action}"
        if resource:
            message += f" on {resource}"
        
        return cls.failure(
            ServiceError(
                code=ErrorCode.UNAUTHORIZED,
                message=message,
                details={"action": action, "resource": resource},
            )
        )
    
    @classmethod
    def conflict(
        cls,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> "ServiceResult[TData]":
        """Create a conflict failure result."""
        return cls.failure(
            ServiceError(
                code=ErrorCode.CONFLICT,
                message=message,
                details=details,
            )
        )
    
    def unwrap(self) -> TData:
        """
        Unwrap the result data or raise exception if failed.
        
        Raises:
            ValueError: If the result is not successful
        """
        if not self.is_success:
            raise ValueError(f"Cannot unwrap failed result: {self.error.message if self.error else 'Unknown error'}")
        return self.data
    
    def unwrap_or(self, default: TData) -> TData:
        """Unwrap the result data or return default if failed."""
        return self.data if self.is_success else default
    
    def unwrap_or_none(self) -> Optional[TData]:
        """Unwrap the result data or return None if failed."""
        return self.data if self.is_success else None
    
    def map(self, func) -> "ServiceResult":
        """Map the result data through a function if successful."""
        if self.is_success and self.data is not None:
            try:
                new_data = func(self.data)
                return ServiceResult.success(data=new_data, message=self.message, metadata=self.metadata)
            except Exception as e:
                return ServiceResult.from_exception(e, "map operation")
        return self
    
    def flat_map(self, func) -> "ServiceResult":
        """Flat map the result data through a function that returns ServiceResult."""
        if self.is_success:
            try:
                return func(self.data)
            except Exception as e:
                return ServiceResult.from_exception(e, "flat_map operation")
        return self
    
    def add_metadata(self, key: str, value: Any) -> "ServiceResult[TData]":
        """Add metadata to the result."""
        if self.metadata is None:
            self.metadata = {}
        self.metadata[key] = value
        return self
    
    def with_message(self, message: str) -> "ServiceResult[TData]":
        """Set a custom message for the result."""
        self.message = message
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary representation."""
        result = {
            "is_success": self.is_success,
            "message": self.message,
            "metadata": self.metadata,
        }
        
        if self.is_success:
            result["data"] = self.data
        else:
            result["error"] = self.error.to_dict() if self.error else None
        
        return result
    
    def __bool__(self) -> bool:
        """Allow boolean evaluation of the result."""
        return self.is_success
    
    def __repr__(self) -> str:
        """String representation of the result."""
        status = "Success" if self.is_success else "Failure"
        if self.message:
            return f"ServiceResult({status}: {self.message})"
        return f"ServiceResult({status})"


# Convenience type aliases for common result types
BoolResult = ServiceResult[bool]
StringResult = ServiceResult[str]
IntResult = ServiceResult[int]
DictResult = ServiceResult[Dict[str, Any]]
ListResult = ServiceResult[List[Any]]


# Utility functions for creating common results
def success(
    data: Optional[TData] = None,
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ServiceResult[TData]:
    """Create a successful service result."""
    return ServiceResult.success(data=data, message=message, metadata=metadata)


def failure(
    error_code: ErrorCode,
    message: str,
    field: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
) -> ServiceResult[None]:
    """Create a failed service result."""
    error = ServiceError(
        code=error_code,
        message=message,
        field=field,
        details=details,
        severity=severity,
    )
    return ServiceResult.failure(error)


def validation_error(
    message: str,
    field: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> ServiceResult[None]:
    """Create a validation error result."""
    return ServiceResult.validation_failure(message=message, field=field, details=details)


def not_found_error(
    resource_type: str,
    resource_id: Optional[str] = None,
) -> ServiceResult[None]:
    """Create a not found error result."""
    return ServiceResult.not_found(resource_type=resource_type, resource_id=resource_id)


def unauthorized_error(
    action: Optional[str] = None,
    resource: Optional[str] = None,
) -> ServiceResult[None]:
    """Create an unauthorized error result."""
    return ServiceResult.unauthorized(action=action, resource=resource)


def conflict_error(
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> ServiceResult[None]:
    """Create a conflict error result."""
    return ServiceResult.conflict(message=message, details=details)


# Export all public classes and functions
__all__ = [
    # Enums
    "ErrorCode",
    "ErrorSeverity",
    
    # Classes
    "ServiceError",
    "ServiceResult",
    
    # Type aliases
    "BoolResult",
    "StringResult", 
    "IntResult",
    "DictResult",
    "ListResult",
    
    # Utility functions
    "success",
    "failure",
    "validation_error",
    "not_found_error",
    "unauthorized_error",
    "conflict_error",
]