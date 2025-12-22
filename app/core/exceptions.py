from typing import Optional, Dict, Any
from fastapi import status

class BaseHostelException(Exception):
    """Base exception for hostel management system"""
    
    def __init__(
        self,
        message: str = "An error occurred",
        error_code: str = "HOSTEL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details
            }
        }

class AuthenticationException(BaseHostelException):
    """Authentication related exceptions"""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message=message,
            error_code="AUTH_ERROR",
            status_code=status.HTTP_401_UNAUTHORIZED,
            **kwargs
        )

class AuthorizationException(BaseHostelException):
    """Authorization and permission exceptions"""
    
    def __init__(self, message: str = "Access denied", **kwargs):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=status.HTTP_403_FORBIDDEN,
            **kwargs
        )

class ValidationException(BaseHostelException):
    """Data validation exceptions"""
    
    def __init__(self, message: str = "Validation failed", field_errors: Optional[Dict] = None, **kwargs):
        details = kwargs.get('details', {})
        if field_errors:
            details['field_errors'] = field_errors
        
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
            **kwargs
        )

class BusinessLogicException(BaseHostelException):
    """Business rule violation exceptions"""
    
    def __init__(self, message: str = "Business rule violation", **kwargs):
        super().__init__(
            message=message,
            error_code="BUSINESS_LOGIC_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            **kwargs
        )

class DatabaseException(BaseHostelException):
    """Database operation exceptions"""
    
    def __init__(self, message: str = "Database operation failed", **kwargs):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            **kwargs
        )

class ExternalServiceException(BaseHostelException):
    """External service integration exceptions"""
    
    def __init__(self, message: str = "External service error", service_name: str = None, **kwargs):
        details = kwargs.get('details', {})
        if service_name:
            details['service'] = service_name
        
        super().__init__(
            message=message,
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
            **kwargs
        )

class PaymentException(BaseHostelException):
    """Payment processing exceptions"""
    
    def __init__(self, message: str = "Payment processing failed", transaction_id: str = None, **kwargs):
        details = kwargs.get('details', {})
        if transaction_id:
            details['transaction_id'] = transaction_id
        
        super().__init__(
            message=message,
            error_code="PAYMENT_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
            **kwargs
        )

class BookingException(BaseHostelException):
    """Booking related exceptions"""
    
    def __init__(self, message: str = "Booking operation failed", booking_id: str = None, **kwargs):
        details = kwargs.get('details', {})
        if booking_id:
            details['booking_id'] = booking_id
        
        super().__init__(
            message=message,
            error_code="BOOKING_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
            **kwargs
        )

class RoomUnavailableException(BookingException):
    """Room unavailability exceptions"""
    
    def __init__(self, message: str = "Room not available", room_id: str = None, dates: Dict = None, **kwargs):
        details = kwargs.get('details', {})
        if room_id:
            details['room_id'] = room_id
        if dates:
            details['requested_dates'] = dates
        
        super().__init__(
            message=message,
            error_code="ROOM_UNAVAILABLE",
            details=details,
            **kwargs
        )

class InsufficientPermissionsException(AuthorizationException):
    """Insufficient permissions exceptions"""
    
    def __init__(self, message: str = "Insufficient permissions", required_permission: str = None, **kwargs):
        details = kwargs.get('details', {})
        if required_permission:
            details['required_permission'] = required_permission
        
        super().__init__(
            message=message,
            error_code="INSUFFICIENT_PERMISSIONS",
            details=details,
            **kwargs
        )

class TokenExpiredException(AuthenticationException):
    """Expired token exceptions"""
    
    def __init__(self, message: str = "Token has expired", **kwargs):
        super().__init__(
            message=message,
            error_code="TOKEN_EXPIRED",
            **kwargs
        )

class InvalidCredentialsException(AuthenticationException):
    """Invalid credentials exceptions"""
    
    def __init__(self, message: str = "Invalid credentials", **kwargs):
        super().__init__(
            message=message,
            error_code="INVALID_CREDENTIALS",
            **kwargs
        )

class TenantNotFoundException(BaseHostelException):
    """Tenant not found exceptions"""
    
    def __init__(self, message: str = "Tenant not found", tenant_id: str = None, **kwargs):
        details = kwargs.get('details', {})
        if tenant_id:
            details['tenant_id'] = tenant_id
        
        super().__init__(
            message=message,
            error_code="TENANT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
            **kwargs
        )

class HostelNotFoundException(BaseHostelException):
    """Hostel not found exceptions"""
    
    def __init__(self, message: str = "Hostel not found", hostel_id: str = None, **kwargs):
        details = kwargs.get('details', {})
        if hostel_id:
            details['hostel_id'] = hostel_id
        
        super().__init__(
            message=message,
            error_code="HOSTEL_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
            **kwargs
        )

class StudentNotFoundException(BaseHostelException):
    """Student not found exceptions"""
    
    def __init__(self, message: str = "Student not found", student_id: str = None, **kwargs):
        details = kwargs.get('details', {})
        if student_id:
            details['student_id'] = student_id
        
        super().__init__(
            message=message,
            error_code="STUDENT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
            **kwargs
        )

class DuplicateResourceException(BaseHostelException):
    """Duplicate resource exceptions"""
    
    def __init__(self, message: str = "Resource already exists", resource_type: str = None, **kwargs):
        details = kwargs.get('details', {})
        if resource_type:
            details['resource_type'] = resource_type
        
        super().__init__(
            message=message,
            error_code="DUPLICATE_RESOURCE",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
            **kwargs
        )

class FileUploadException(BaseHostelException):
    """File upload related exceptions"""
    
    def __init__(self, message: str = "File upload failed", file_name: str = None, **kwargs):
        details = kwargs.get('details', {})
        if file_name:
            details['file_name'] = file_name
        
        super().__init__(
            message=message,
            error_code="FILE_UPLOAD_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
            **kwargs
        )

class NotificationException(BaseHostelException):
    """Notification service exceptions"""
    
    def __init__(self, message: str = "Notification failed", channel: str = None, **kwargs):
        details = kwargs.get('details', {})
        if channel:
            details['channel'] = channel
        
        super().__init__(
            message=message,
            error_code="NOTIFICATION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
            **kwargs
        )

class MaintenanceException(BaseHostelException):
    """Maintenance operation exceptions"""
    
    def __init__(self, message: str = "Maintenance operation failed", request_id: str = None, **kwargs):
        details = kwargs.get('details', {})
        if request_id:
            details['request_id'] = request_id
        
        super().__init__(
            message=message,
            error_code="MAINTENANCE_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
            **kwargs
        )

class ComplaintException(BaseHostelException):
    """Complaint handling exceptions"""
    
    def __init__(self, message: str = "Complaint operation failed", complaint_id: str = None, **kwargs):
        details = kwargs.get('details', {})
        if complaint_id:
            details['complaint_id'] = complaint_id
        
        super().__init__(
            message=message,
            error_code="COMPLAINT_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
            **kwargs
        )

# Exception mappings for FastAPI exception handlers
EXCEPTION_STATUS_CODES = {
    AuthenticationException: status.HTTP_401_UNAUTHORIZED,
    AuthorizationException: status.HTTP_403_FORBIDDEN,
    ValidationException: status.HTTP_422_UNPROCESSABLE_ENTITY,
    BusinessLogicException: status.HTTP_400_BAD_REQUEST,
    DatabaseException: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ExternalServiceException: status.HTTP_503_SERVICE_UNAVAILABLE,
    PaymentException: status.HTTP_400_BAD_REQUEST,
    BookingException: status.HTTP_400_BAD_REQUEST,
    RoomUnavailableException: status.HTTP_400_BAD_REQUEST,
    InsufficientPermissionsException: status.HTTP_403_FORBIDDEN,
    TokenExpiredException: status.HTTP_401_UNAUTHORIZED,
    InvalidCredentialsException: status.HTTP_401_UNAUTHORIZED,
    TenantNotFoundException: status.HTTP_404_NOT_FOUND,
    HostelNotFoundException: status.HTTP_404_NOT_FOUND,
    StudentNotFoundException: status.HTTP_404_NOT_FOUND,
    DuplicateResourceException: status.HTTP_409_CONFLICT,
    FileUploadException: status.HTTP_400_BAD_REQUEST,
    NotificationException: status.HTTP_500_INTERNAL_SERVER_ERROR,
    MaintenanceException: status.HTTP_400_BAD_REQUEST,
    ComplaintException: status.HTTP_400_BAD_REQUEST,
}