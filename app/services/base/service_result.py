"""
Service result patterns for standardized response handling.
"""

from typing import TypeVar, Generic, Optional, Any, Dict, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


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
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation."""
        return {
            "code": self.code.value,
            "message": self.message,
            "severity": self.severity.value,
            "details": self.details,
            "field": self.field,
            "timestamp": self.timestamp.isoformat(),
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