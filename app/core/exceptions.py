"""
Custom Exceptions for the Hostel Management Application

This module defines custom exception classes used throughout the application
for better error handling and debugging.
"""

from typing import Any, Dict, List, Optional
from enum import Enum


class ErrorCode(str, Enum):
    """Standard error codes for the application"""
    # General errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    OPERATION_FAILED = "OPERATION_FAILED"
    MAINTENANCE_MODE = "MAINTENANCE_MODE"
    API_DEPRECATED = "API_DEPRECATED"
    
    # Authentication & Authorization
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    
    # Validation errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_FORMAT = "INVALID_FORMAT"
    CONSTRAINT_VIOLATION = "CONSTRAINT_VIOLATION"
    
    # Database errors
    DATABASE_ERROR = "DATABASE_ERROR"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    DUPLICATE_ENTRY = "DUPLICATE_ENTRY"
    FOREIGN_KEY_VIOLATION = "FOREIGN_KEY_VIOLATION"
    
    # Business logic errors
    BOOKING_CONFLICT = "BOOKING_CONFLICT"
    ROOM_UNAVAILABLE = "ROOM_UNAVAILABLE"
    INSUFFICIENT_CAPACITY = "INSUFFICIENT_CAPACITY"
    INVALID_DATE_RANGE = "INVALID_DATE_RANGE"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    GUEST_ALREADY_CHECKED_IN = "GUEST_ALREADY_CHECKED_IN"
    GUEST_NOT_CHECKED_IN = "GUEST_NOT_CHECKED_IN"
    
    # User/Staff specific errors
    USER_NOT_FOUND = "USER_NOT_FOUND"
    ADMIN_NOT_FOUND = "ADMIN_NOT_FOUND"
    STUDENT_NOT_FOUND = "STUDENT_NOT_FOUND"
    SUPERVISOR_NOT_FOUND = "SUPERVISOR_NOT_FOUND"
    HOSTEL_NOT_FOUND = "HOSTEL_NOT_FOUND"
    ROOM_NOT_FOUND = "ROOM_NOT_FOUND"
    
    # External service errors
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    PAYMENT_GATEWAY_ERROR = "PAYMENT_GATEWAY_ERROR"
    EMAIL_SERVICE_ERROR = "EMAIL_SERVICE_ERROR"
    SMS_SERVICE_ERROR = "SMS_SERVICE_ERROR"
    
    # Cache and performance errors
    CACHE_ERROR = "CACHE_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    
    # Configuration errors
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    MISSING_CONFIGURATION = "MISSING_CONFIGURATION"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"


class BaseAppException(Exception):
    """
    Base exception class for all application exceptions.
    
    Provides consistent error handling across the application with
    structured error information.
    """
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary format"""
        return {
            "error": {
                "message": self.message,
                "code": self.error_code.value,
                "details": self.details,
                "type": self.__class__.__name__
            }
        }
    
    def __str__(self) -> str:
        return f"{self.error_code.value}: {self.message}"
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message='{self.message}', error_code='{self.error_code.value}')"


# ========================================
# General Application Exceptions
# ========================================

class OperationError(BaseAppException):
    """Exception raised when an operation fails"""
    
    def __init__(
        self,
        message: str = "Operation failed",
        error_code: ErrorCode = ErrorCode.OPERATION_FAILED,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        super().__init__(message, error_code, details, status_code)


class ValidationError(BaseAppException):
    """Exception raised when data validation fails"""
    
    def __init__(
        self,
        message: str = "Validation failed",
        field_errors: Optional[Dict[str, List[str]]] = None,
        error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
        status_code: int = 422
    ):
        details = {"field_errors": field_errors} if field_errors else {}
        super().__init__(message, error_code, details, status_code)


class ResourceNotFoundError(BaseAppException):
    """Exception raised when a requested resource is not found"""
    
    def __init__(
        self,
        resource_type: str = "Resource",
        resource_id: Optional[str] = None,
        message: Optional[str] = None
    ):
        if not message:
            message = f"{resource_type} not found"
            if resource_id:
                message += f" (ID: {resource_id})"
        
        details = {
            "resource_type": resource_type,
            "resource_id": resource_id
        }
        super().__init__(message, ErrorCode.RESOURCE_NOT_FOUND, details, 404)


class AdminAPIException(BaseAppException):
    """Exception raised for admin API specific errors"""
    
    def __init__(
        self,
        message: str = "Admin API operation failed",
        error_code: ErrorCode = ErrorCode.OPERATION_FAILED,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        super().__init__(message, error_code, details, status_code)


class MaintenanceMode(BaseAppException):
    """Exception raised when the system is in maintenance mode"""
    
    def __init__(
        self,
        message: str = "System is currently under maintenance",
        maintenance_until: Optional[str] = None,
        error_code: ErrorCode = ErrorCode.MAINTENANCE_MODE,
        status_code: int = 503
    ):
        details = {"maintenance_until": maintenance_until} if maintenance_until else {}
        super().__init__(message, error_code, details, status_code)


class APIDeprecated(BaseAppException):
    """Exception raised when an API endpoint is deprecated"""
    
    def __init__(
        self,
        message: str = "This API endpoint is deprecated",
        deprecated_since: Optional[str] = None,
        alternative_endpoint: Optional[str] = None,
        removal_date: Optional[str] = None,
        error_code: ErrorCode = ErrorCode.API_DEPRECATED,
        status_code: int = 410
    ):
        details = {
            "deprecated_since": deprecated_since,
            "alternative_endpoint": alternative_endpoint,
            "removal_date": removal_date
        }
        super().__init__(message, error_code, details, status_code)


# ========================================
# Resource Not Found Exceptions
# ========================================

class UserNotFoundError(ResourceNotFoundError):
    """Exception raised when a user is not found"""
    
    def __init__(
        self,
        user_id: Optional[str] = None,
        message: Optional[str] = None
    ):
        if not message:
            message = "User not found"
            if user_id:
                message += f" (ID: {user_id})"
        super().__init__("User", user_id, message)
        self.error_code = ErrorCode.USER_NOT_FOUND


class AdminNotFoundError(ResourceNotFoundError):
    """Exception raised when an admin is not found"""
    
    def __init__(
        self,
        admin_id: Optional[str] = None,
        message: Optional[str] = None
    ):
        if not message:
            message = "Admin not found"
            if admin_id:
                message += f" (ID: {admin_id})"
        super().__init__("Admin", admin_id, message)
        self.error_code = ErrorCode.ADMIN_NOT_FOUND


class StudentNotFoundError(ResourceNotFoundError):
    """Exception raised when a student is not found"""
    
    def __init__(
        self,
        student_id: Optional[str] = None,
        message: Optional[str] = None
    ):
        if not message:
            message = "Student not found"
            if student_id:
                message += f" (ID: {student_id})"
        super().__init__("Student", student_id, message)
        self.error_code = ErrorCode.STUDENT_NOT_FOUND


class SupervisorNotFoundError(ResourceNotFoundError):
    """Exception raised when a supervisor is not found"""
    
    def __init__(
        self,
        supervisor_id: Optional[str] = None,
        message: Optional[str] = None
    ):
        if not message:
            message = "Supervisor not found"
            if supervisor_id:
                message += f" (ID: {supervisor_id})"
        super().__init__("Supervisor", supervisor_id, message)
        self.error_code = ErrorCode.SUPERVISOR_NOT_FOUND


class HostelNotFoundError(ResourceNotFoundError):
    """Exception raised when a hostel is not found"""
    
    def __init__(
        self,
        hostel_id: Optional[str] = None,
        message: Optional[str] = None
    ):
        if not message:
            message = "Hostel not found"
            if hostel_id:
                message += f" (ID: {hostel_id})"
        super().__init__("Hostel", hostel_id, message)
        self.error_code = ErrorCode.HOSTEL_NOT_FOUND


class RoomNotFoundError(ResourceNotFoundError):
    """Exception raised when a room is not found"""
    
    def __init__(
        self,
        room_id: Optional[str] = None,
        message: Optional[str] = None
    ):
        if not message:
            message = "Room not found"
            if room_id:
                message += f" (ID: {room_id})"
        super().__init__("Room", room_id, message)
        self.error_code = ErrorCode.ROOM_NOT_FOUND


# ========================================
# Authentication & Authorization Exceptions
# ========================================

class AuthenticationError(BaseAppException):
    """Exception raised when authentication fails"""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        error_code: ErrorCode = ErrorCode.AUTHENTICATION_FAILED,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, error_code, details, 401)


class AuthorizationError(BaseAppException):
    """Exception raised when authorization fails"""
    
    def __init__(
        self,
        message: str = "Access denied",
        required_permission: Optional[str] = None,
        error_code: ErrorCode = ErrorCode.AUTHORIZATION_FAILED
    ):
        details = {"required_permission": required_permission} if required_permission else {}
        super().__init__(message, error_code, details, 403)


class TokenError(AuthenticationError):
    """Exception raised for token-related authentication errors"""
    
    def __init__(
        self,
        message: str = "Invalid token",
        error_code: ErrorCode = ErrorCode.TOKEN_INVALID,
        token_type: str = "access_token"
    ):
        details = {"token_type": token_type}
        super().__init__(message, error_code, details)


class TokenExpiredError(TokenError):
    """Exception raised when a token has expired"""
    
    def __init__(
        self,
        message: str = "Token has expired",
        token_type: str = "access_token"
    ):
        super().__init__(message, ErrorCode.TOKEN_EXPIRED, token_type)


class InvalidTokenError(TokenError):
    """Exception raised when token is invalid"""
    
    def __init__(
        self,
        message: str = "Invalid token",
        token_type: str = "access_token",
        reason: Optional[str] = None
    ):
        details = {"reason": reason} if reason else {}
        super().__init__(message, ErrorCode.TOKEN_INVALID, token_type)
        self.details.update(details)


class PermissionError(AuthorizationError):
    """Exception raised when user lacks required permissions"""
    
    def __init__(
        self,
        message: str = "Permission denied",
        required_permission: Optional[str] = None,
        user_permissions: Optional[List[str]] = None
    ):
        details = {
            "required_permission": required_permission,
            "user_permissions": user_permissions
        }
        super().__init__(message, required_permission, ErrorCode.AUTHORIZATION_FAILED)
        self.details.update(details)


# ========================================
# Database Exceptions
# ========================================

class DatabaseError(BaseAppException):
    """Exception raised when database operations fail"""
    
    def __init__(
        self,
        message: str = "Database operation failed",
        operation: Optional[str] = None,
        table: Optional[str] = None,
        error_code: ErrorCode = ErrorCode.DATABASE_ERROR,
        status_code: int = 500
    ):
        details = {
            "operation": operation,
            "table": table
        }
        super().__init__(message, error_code, details, status_code)


class DatabaseConnectionError(DatabaseError):
    """Exception raised when database connection fails"""
    
    def __init__(
        self,
        message: str = "Database connection failed",
        database: Optional[str] = None
    ):
        details = {"database": database} if database else {}
        super().__init__(message, error_code=ErrorCode.CONNECTION_ERROR, status_code=503)


class DuplicateEntryError(DatabaseError):
    """Exception raised when trying to create a duplicate entry"""
    
    def __init__(
        self,
        message: str = "Duplicate entry",
        field: Optional[str] = None,
        value: Optional[str] = None,
        table: Optional[str] = None
    ):
        details = {
            "field": field,
            "value": value,
            "table": table
        }
        super().__init__(message, table=table, error_code=ErrorCode.DUPLICATE_ENTRY, status_code=409)


class ForeignKeyViolationError(DatabaseError):
    """Exception raised when foreign key constraint is violated"""
    
    def __init__(
        self,
        message: str = "Foreign key constraint violation",
        foreign_key: Optional[str] = None,
        referenced_table: Optional[str] = None
    ):
        details = {
            "foreign_key": foreign_key,
            "referenced_table": referenced_table
        }
        super().__init__(message, error_code=ErrorCode.FOREIGN_KEY_VIOLATION, status_code=409)


# ========================================
# Business Logic Exceptions
# ========================================

class BookingError(BaseAppException):
    """Base class for booking-related exceptions"""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        booking_id: Optional[str] = None,
        room_id: Optional[str] = None,
        status_code: int = 400
    ):
        details = {
            "booking_id": booking_id,
            "room_id": room_id
        }
        super().__init__(message, error_code, details, status_code)


class BookingConflictError(BookingError):
    """Exception raised when booking conflicts with existing bookings"""
    
    def __init__(
        self,
        message: str = "Booking conflict detected",
        room_id: Optional[str] = None,
        conflicting_booking_id: Optional[str] = None
    ):
        details = {
            "room_id": room_id,
            "conflicting_booking_id": conflicting_booking_id
        }
        super().__init__(
            message,
            ErrorCode.BOOKING_CONFLICT,
            room_id=room_id,
            status_code=409
        )
        self.details.update(details)


class RoomUnavailableError(BookingError):
    """Exception raised when room is not available for booking"""
    
    def __init__(
        self,
        message: str = "Room is not available",
        room_id: Optional[str] = None,
        reason: Optional[str] = None
    ):
        details = {"reason": reason} if reason else {}
        super().__init__(
            message,
            ErrorCode.ROOM_UNAVAILABLE,
            room_id=room_id,
            status_code=409
        )
        self.details.update(details)


class InsufficientCapacityError(BaseAppException):
    """Exception raised when there's insufficient capacity"""
    
    def __init__(
        self,
        message: str = "Insufficient capacity",
        requested: Optional[int] = None,
        available: Optional[int] = None
    ):
        details = {
            "requested": requested,
            "available": available
        }
        super().__init__(message, ErrorCode.INSUFFICIENT_CAPACITY, details, 409)


class InvalidDateRangeError(BaseAppException):
    """Exception raised when date range is invalid"""
    
    def __init__(
        self,
        message: str = "Invalid date range",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ):
        details = {
            "start_date": start_date,
            "end_date": end_date
        }
        super().__init__(message, ErrorCode.INVALID_DATE_RANGE, details, 422)


class GuestError(BaseAppException):
    """Base class for guest-related exceptions"""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        guest_id: Optional[str] = None,
        status_code: int = 400
    ):
        details = {"guest_id": guest_id} if guest_id else {}
        super().__init__(message, error_code, details, status_code)


class GuestAlreadyCheckedInError(GuestError):
    """Exception raised when guest is already checked in"""
    
    def __init__(
        self,
        message: str = "Guest is already checked in",
        guest_id: Optional[str] = None
    ):
        super().__init__(message, ErrorCode.GUEST_ALREADY_CHECKED_IN, guest_id, 409)


class GuestNotCheckedInError(GuestError):
    """Exception raised when guest is not checked in"""
    
    def __init__(
        self,
        message: str = "Guest is not checked in",
        guest_id: Optional[str] = None
    ):
        super().__init__(message, ErrorCode.GUEST_NOT_CHECKED_IN, guest_id, 409)


# ========================================
# Payment Exceptions
# ========================================

class PaymentError(BaseAppException):
    """Exception raised when payment operations fail"""
    
    def __init__(
        self,
        message: str = "Payment failed",
        payment_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
        amount: Optional[float] = None,
        error_code: ErrorCode = ErrorCode.PAYMENT_FAILED
    ):
        details = {
            "payment_id": payment_id,
            "transaction_id": transaction_id,
            "amount": amount
        }
        super().__init__(message, error_code, details, 402)


class PaymentGatewayError(PaymentError):
    """Exception raised when payment gateway operations fail"""
    
    def __init__(
        self,
        message: str = "Payment gateway error",
        gateway_name: Optional[str] = None,
        gateway_error_code: Optional[str] = None,
        **kwargs
    ):
        details = {
            "gateway_name": gateway_name,
            "gateway_error_code": gateway_error_code
        }
        super().__init__(message, error_code=ErrorCode.PAYMENT_GATEWAY_ERROR, **kwargs)
        self.details.update(details)


# ========================================
# External Service Exceptions
# ========================================

class ExternalServiceError(BaseAppException):
    """Exception raised when external service calls fail"""
    
    def __init__(
        self,
        message: str = "External service error",
        service_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        status_code: int = 503
    ):
        details = {
            "service_name": service_name,
            "endpoint": endpoint
        }
        super().__init__(message, ErrorCode.EXTERNAL_SERVICE_ERROR, details, status_code)


class EmailServiceError(ExternalServiceError):
    """Exception raised when email service operations fail"""
    
    def __init__(
        self,
        message: str = "Email service error",
        recipient: Optional[str] = None,
        **kwargs
    ):
        details = {"recipient": recipient} if recipient else {}
        super().__init__(message, error_code=ErrorCode.EMAIL_SERVICE_ERROR, **kwargs)
        self.details.update(details)


class SMSServiceError(ExternalServiceError):
    """Exception raised when SMS service operations fail"""
    
    def __init__(
        self,
        message: str = "SMS service error",
        phone_number: Optional[str] = None,
        **kwargs
    ):
        details = {"phone_number": phone_number} if phone_number else {}
        super().__init__(message, error_code=ErrorCode.SMS_SERVICE_ERROR, **kwargs)
        self.details.update(details)


# ========================================
# Cache and Performance Exceptions
# ========================================

class CacheError(BaseAppException):
    """Exception raised when cache operations fail"""
    
    def __init__(
        self,
        message: str = "Cache operation failed",
        operation: Optional[str] = None,
        key: Optional[str] = None
    ):
        details = {
            "operation": operation,
            "key": key
        }
        super().__init__(message, ErrorCode.CACHE_ERROR, details, 503)


class TimeoutError(BaseAppException):
    """Exception raised when operations timeout"""
    
    def __init__(
        self,
        message: str = "Operation timed out",
        timeout_seconds: Optional[float] = None,
        operation: Optional[str] = None
    ):
        details = {
            "timeout_seconds": timeout_seconds,
            "operation": operation
        }
        super().__init__(message, ErrorCode.TIMEOUT_ERROR, details, 504)


class RateLimitExceededError(BaseAppException):
    """Exception raised when rate limit is exceeded"""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        reset_time: Optional[int] = None,
        identifier: Optional[str] = None
    ):
        details = {
            "limit": limit,
            "reset_time": reset_time,
            "identifier": identifier
        }
        super().__init__(message, ErrorCode.RATE_LIMIT_EXCEEDED, details, 429)


# Backward compatibility alias for rate limiting
RateLimitExceeded = RateLimitExceededError


# ========================================
# Configuration Exceptions
# ========================================

class ConfigurationError(BaseAppException):
    """Exception raised when configuration is invalid"""
    
    def __init__(
        self,
        message: str = "Configuration error",
        config_key: Optional[str] = None,
        config_value: Optional[Any] = None,
        error_code: ErrorCode = ErrorCode.CONFIGURATION_ERROR
    ):
        details = {
            "config_key": config_key,
            "config_value": str(config_value) if config_value is not None else None
        }
        super().__init__(message, error_code, details, 500)


class MissingConfigurationError(ConfigurationError):
    """Exception raised when required configuration is missing"""
    
    def __init__(
        self,
        message: str = "Missing required configuration",
        config_key: Optional[str] = None
    ):
        super().__init__(
            message,
            config_key=config_key,
            error_code=ErrorCode.MISSING_CONFIGURATION
        )


class InvalidConfigurationError(ConfigurationError):
    """Exception raised when configuration value is invalid"""
    
    def __init__(
        self,
        message: str = "Invalid configuration value",
        config_key: Optional[str] = None,
        config_value: Optional[Any] = None,
        expected_type: Optional[str] = None
    ):
        details = {"expected_type": expected_type} if expected_type else {}
        super().__init__(
            message,
            config_key=config_key,
            config_value=config_value,
            error_code=ErrorCode.INVALID_CONFIGURATION
        )
        self.details.update(details)


# ========================================
# Utility Functions
# ========================================

def handle_database_exception(exc: Exception) -> BaseAppException:
    """Convert database exceptions to application exceptions"""
    error_message = str(exc)
    
    if "duplicate" in error_message.lower() or "unique constraint" in error_message.lower():
        return DuplicateEntryError(f"Duplicate entry: {error_message}")
    elif "foreign key" in error_message.lower():
        return ForeignKeyViolationError(f"Foreign key violation: {error_message}")
    elif "connection" in error_message.lower():
        return DatabaseConnectionError(f"Database connection error: {error_message}")
    else:
        return DatabaseError(f"Database error: {error_message}")


def create_validation_error(field_errors: Dict[str, List[str]]) -> ValidationError:
    """Create a validation error with field-specific errors"""
    total_errors = sum(len(errors) for errors in field_errors.values())
    message = f"Validation failed with {total_errors} error(s)"
    return ValidationError(message, field_errors)


# Export all exception classes
__all__ = [
    # Enums
    'ErrorCode',
    
    # Base exceptions
    'BaseAppException',
    
    # General exceptions
    'OperationError',
    'ValidationError',
    'ResourceNotFoundError',
    'AdminAPIException',
    'MaintenanceMode',
    'APIDeprecated',
    
    # Resource Not Found exceptions
    'UserNotFoundError',
    'AdminNotFoundError',  # Added this
    'StudentNotFoundError',
    'SupervisorNotFoundError',
    'HostelNotFoundError',
    'RoomNotFoundError',
    
    # Auth exceptions
    'AuthenticationError',
    'AuthorizationError',
    'TokenError',
    'TokenExpiredError',
    'InvalidTokenError',
    'PermissionError',
    
    # Database exceptions
    'DatabaseError',
    'DatabaseConnectionError',
    'DuplicateEntryError',
    'ForeignKeyViolationError',
    
    # Business logic exceptions
    'BookingError',
    'BookingConflictError',
    'RoomUnavailableError',
    'InsufficientCapacityError',
    'InvalidDateRangeError',
    'GuestError',
    'GuestAlreadyCheckedInError',
    'GuestNotCheckedInError',
    
    # Payment exceptions
    'PaymentError',
    'PaymentGatewayError',
    
    # External service exceptions
    'ExternalServiceError',
    'EmailServiceError',
    'SMSServiceError',
    
    # Cache and performance exceptions
    'CacheError',
    'TimeoutError',
    'RateLimitExceededError',
    'RateLimitExceeded',  # Backward compatibility alias
    
    # Configuration exceptions
    'ConfigurationError',
    'MissingConfigurationError',
    'InvalidConfigurationError',
    
    # Utility functions
    'handle_database_exception',
    'create_validation_error'
]