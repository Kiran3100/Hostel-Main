import time
import traceback
import logging
from typing import Dict, Any, Optional, List
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import ValidationError

from app.core.exceptions import (
    BaseHostelException, AuthenticationException, AuthorizationException,
    ValidationException, BusinessLogicException, DatabaseException,
    ExternalServiceException, PaymentException, BookingException
)
from app.services.notification.notification_service import NotificationService
import json

logger = logging.getLogger(__name__)

class GlobalExceptionHandler(BaseHTTPMiddleware):
    """Global exception handling middleware"""
    
    def __init__(self, app, notification_service: Optional[NotificationService] = None):
        super().__init__(app)
        self.notification_service = notification_service
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        
        except BaseHostelException as e:
            # Handle custom application exceptions
            return await self._handle_application_exception(e, request)
        
        except ValidationError as e:
            # Handle Pydantic validation errors
            return await self._handle_validation_error(e, request)
        
        except SQLAlchemyError as e:
            # Handle database exceptions
            return await self._handle_database_error(e, request)
        
        except Exception as e:
            # Handle unexpected exceptions
            return await self._handle_unexpected_exception(e, request)
    
    async def _handle_application_exception(
        self, exception: BaseHostelException, request: Request
    ) -> JSONResponse:
        """Handle custom application exceptions"""
        correlation_id = getattr(request.state, 'correlation_id', None)
        user_id = getattr(request.state, 'user_id', None)
        
        # Log the exception
        logger.warning(
            f"Application exception: {exception.error_code} - {exception.message}",
            extra={
                "exception_data": {
                    "error_code": exception.error_code,
                    "message": exception.message,
                    "details": exception.details,
                    "user_id": user_id,
                    "correlation_id": correlation_id,
                    "path": request.url.path,
                    "method": request.method
                }
            }
        )
        
        # Create error response
        error_response = {
            "error": {
                "code": exception.error_code,
                "message": exception.message,
                "details": exception.details,
                "timestamp": int(time.time())
            }
        }
        
        if correlation_id:
            error_response["correlation_id"] = correlation_id
        
        return JSONResponse(
            status_code=exception.status_code,
            content=error_response
        )
    
    async def _handle_validation_error(
        self, exception: ValidationError, request: Request
    ) -> JSONResponse:
        """Handle Pydantic validation errors"""
        correlation_id = getattr(request.state, 'correlation_id', None)
        
        # Format validation errors
        field_errors = {}
        for error in exception.errors():
            field_path = '.'.join(str(x) for x in error['loc'])
            field_errors[field_path] = {
                "message": error['msg'],
                "type": error['type']
            }
        
        logger.warning(
            f"Validation error: {len(field_errors)} field(s) failed validation",
            extra={
                "validation_errors": field_errors,
                "correlation_id": correlation_id,
                "path": request.url.path,
                "method": request.method
            }
        )
        
        error_response = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {
                    "field_errors": field_errors,
                    "error_count": len(field_errors)
                },
                "timestamp": int(time.time())
            }
        }
        
        if correlation_id:
            error_response["correlation_id"] = correlation_id
        
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_response
        )
    
    async def _handle_database_error(
        self, exception: SQLAlchemyError, request: Request
    ) -> JSONResponse:
        """Handle database exceptions"""
        correlation_id = getattr(request.state, 'correlation_id', None)
        user_id = getattr(request.state, 'user_id', None)
        
        # Determine error type and status code
        if isinstance(exception, IntegrityError):
            error_code = "INTEGRITY_CONSTRAINT_VIOLATION"
            message = "Database integrity constraint violation"
            status_code = status.HTTP_409_CONFLICT
        else:
            error_code = "DATABASE_ERROR"
            message = "Database operation failed"
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        
        # Log the exception with full traceback for debugging
        logger.error(
            f"Database exception: {error_code}",
            extra={
                "exception_data": {
                    "error_code": error_code,
                    "message": message,
                    "exception_type": type(exception).__name__,
                    "user_id": user_id,
                    "correlation_id": correlation_id,
                    "path": request.url.path,
                    "method": request.method
                }
            },
            exc_info=True
        )
        
        # Send critical error notification for 500 errors
        if status_code == 500 and self.notification_service:
            await self._send_critical_error_notification(exception, request)
        
        error_response = {
            "error": {
                "code": error_code,
                "message": message,
                "timestamp": int(time.time())
            }
        }
        
        if correlation_id:
            error_response["correlation_id"] = correlation_id
        
        return JSONResponse(
            status_code=status_code,
            content=error_response
        )
    
    async def _handle_unexpected_exception(
        self, exception: Exception, request: Request
    ) -> JSONResponse:
        """Handle unexpected exceptions"""
        correlation_id = getattr(request.state, 'correlation_id', None)
        user_id = getattr(request.state, 'user_id', None)
        
        # Log the full exception with traceback
        logger.critical(
            f"Unexpected exception: {type(exception).__name__} - {str(exception)}",
            extra={
                "exception_data": {
                    "exception_type": type(exception).__name__,
                    "exception_message": str(exception),
                    "user_id": user_id,
                    "correlation_id": correlation_id,
                    "path": request.url.path,
                    "method": request.method,
                    "traceback": traceback.format_exc()
                }
            },
            exc_info=True
        )
        
        # Send critical error notification
        if self.notification_service:
            await self._send_critical_error_notification(exception, request)
        
        error_response = {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "timestamp": int(time.time())
            }
        }
        
        if correlation_id:
            error_response["correlation_id"] = correlation_id
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response
        )
    
    async def _send_critical_error_notification(
        self, exception: Exception, request: Request
    ):
        """Send notification for critical errors"""
        try:
            await self.notification_service.send_critical_error_alert({
                "exception_type": type(exception).__name__,
                "exception_message": str(exception),
                "path": request.url.path,
                "method": request.method,
                "user_id": getattr(request.state, 'user_id', None),
                "correlation_id": getattr(request.state, 'correlation_id', None),
                "timestamp": time.time()
            })
        except Exception as e:
            # Don't let notification failure affect error response
            logger.error(f"Failed to send critical error notification: {str(e)}")

class ValidationErrorHandler:
    """Validation error formatting handler"""
    
    @staticmethod
    def format_validation_errors(errors: List[Dict]) -> Dict[str, Any]:
        """Format validation errors into a structured response"""
        field_errors = {}
        general_errors = []
        
        for error in errors:
            if 'loc' in error and error['loc']:
                # Field-specific error
                field_path = '.'.join(str(x) for x in error['loc'])
                field_errors[field_path] = {
                    "message": error['msg'],
                    "type": error['type'],
                    "input": error.get('input')
                }
            else:
                # General validation error
                general_errors.append({
                    "message": error['msg'],
                    "type": error['type']
                })
        
        return {
            "field_errors": field_errors,
            "general_errors": general_errors,
            "error_count": len(field_errors) + len(general_errors)
        }

class DatabaseErrorHandler:
    """Database error handling and retry logic"""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 0.1):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def handle_with_retry(self, operation, *args, **kwargs):
        """Execute database operation with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await operation(*args, **kwargs)
            
            except (SQLAlchemyError, Exception) as e:
                last_exception = e
                
                if attempt < self.max_retries and self._is_retryable_error(e):
                    logger.warning(
                        f"Database operation failed (attempt {attempt + 1}), retrying: {str(e)}"
                    )
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                    continue
                else:
                    break
        
        # All retries exhausted
        raise DatabaseException(
            message=f"Database operation failed after {self.max_retries} retries",
            details={"last_error": str(last_exception)}
        )
    
    def _is_retryable_error(self, exception: Exception) -> bool:
        """Determine if an error is retryable"""
        # Connection errors, timeouts, and some transaction conflicts are retryable
        retryable_keywords = [
            'connection',
            'timeout',
            'deadlock',
            'lock wait timeout',
            'connection reset'
        ]
        
        error_message = str(exception).lower()
        return any(keyword in error_message for keyword in retryable_keywords)

class ExternalServiceErrorHandler:
    """External service error handling"""
    
    def __init__(self):
        self.circuit_breakers = {}
    
    async def handle_external_service_error(
        self, service_name: str, exception: Exception, request: Request
    ) -> JSONResponse:
        """Handle external service errors with circuit breaker pattern"""
        correlation_id = getattr(request.state, 'correlation_id', None)
        
        # Update circuit breaker
        self._update_circuit_breaker(service_name, False)
        
        # Log service error
        logger.error(
            f"External service error: {service_name} - {str(exception)}",
            extra={
                "service_error": {
                    "service_name": service_name,
                    "exception_type": type(exception).__name__,
                    "exception_message": str(exception),
                    "correlation_id": correlation_id,
                    "circuit_breaker_state": self._get_circuit_breaker_state(service_name)
                }
            }
        )
        
        # Determine appropriate response based on service criticality
        if service_name in ['payment_gateway', 'authentication_service']:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            message = f"Critical service {service_name} is temporarily unavailable"
        else:
            status_code = status.HTTP_502_BAD_GATEWAY
            message = f"External service {service_name} error"
        
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": "EXTERNAL_SERVICE_ERROR",
                    "message": message,
                    "details": {
                        "service": service_name,
                        "retry_after": 60
                    },
                    "timestamp": int(time.time())
                },
                "correlation_id": correlation_id
            }
        )
    
    def _update_circuit_breaker(self, service_name: str, success: bool):
        """Update circuit breaker state for service"""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = {
                "failure_count": 0,
                "last_failure_time": None,
                "state": "closed"  # closed, open, half-open
            }
        
        breaker = self.circuit_breakers[service_name]
        
        if success:
            breaker["failure_count"] = 0
            breaker["state"] = "closed"
        else:
            breaker["failure_count"] += 1
            breaker["last_failure_time"] = time.time()
            
            # Open circuit breaker after 5 failures
            if breaker["failure_count"] >= 5:
                breaker["state"] = "open"
    
    def _get_circuit_breaker_state(self, service_name: str) -> str:
        """Get current circuit breaker state"""
        if service_name not in self.circuit_breakers:
            return "closed"
        
        breaker = self.circuit_breakers[service_name]
        
        # Check if we should transition from open to half-open
        if (breaker["state"] == "open" and 
            breaker["last_failure_time"] and
            time.time() - breaker["last_failure_time"] > 60):  # 1 minute timeout
            breaker["state"] = "half-open"
        
        return breaker["state"]

class BusinessLogicErrorHandler:
    """Business logic error formatting"""
    
    @staticmethod
    def format_business_logic_error(exception: BusinessLogicException) -> Dict[str, Any]:
        """Format business logic errors with helpful context"""
        return {
            "error": {
                "code": exception.error_code,
                "message": exception.message,
                "details": exception.details,
                "suggestions": BusinessLogicErrorHandler._get_error_suggestions(exception),
                "timestamp": int(time.time())
            }
        }
    
    @staticmethod
    def _get_error_suggestions(exception: BusinessLogicException) -> List[str]:
        """Provide helpful suggestions based on error type"""
        suggestions = []
        
        if "insufficient_balance" in exception.error_code:
            suggestions.append("Please add funds to your account")
            suggestions.append("Contact support for payment assistance")
        
        elif "room_unavailable" in exception.error_code:
            suggestions.append("Try selecting different dates")
            suggestions.append("Check available room types")
            suggestions.append("Join the waitlist for your preferred dates")
        
        elif "permission_denied" in exception.error_code:
            suggestions.append("Contact your administrator for access")
            suggestions.append("Verify you have the correct role assignments")
        
        return suggestions

class SecurityExceptionHandler:
    """Security exception handling"""
    
    def __init__(self):
        self.security_incident_threshold = 5  # incidents per hour
        self.incident_tracking = {}
    
    async def handle_security_exception(
        self, exception: Exception, request: Request
    ) -> JSONResponse:
        """Handle security-related exceptions"""
        ip_address = request.client.host
        user_id = getattr(request.state, 'user_id', None)
        
        # Track security incidents
        self._track_security_incident(ip_address, user_id)
        
        # Log security incident
        logger.warning(
            f"Security exception: {type(exception).__name__} from {ip_address}",
            extra={
                "security_incident": {
                    "exception_type": type(exception).__name__,
                    "exception_message": str(exception),
                    "ip_address": ip_address,
                    "user_id": user_id,
                    "user_agent": request.headers.get('User-Agent'),
                    "path": request.url.path,
                    "method": request.method,
                    "incident_count": self._get_incident_count(ip_address)
                }
            }
        )
        
        # Determine response based on exception type
        if isinstance(exception, AuthenticationException):
            return self._create_auth_error_response(exception, request)
        elif isinstance(exception, AuthorizationException):
            return self._create_authorization_error_response(exception, request)
        else:
            return self._create_generic_security_error_response(exception, request)
    
    def _track_security_incident(self, ip_address: str, user_id: Optional[str]):
        """Track security incidents for rate limiting and blocking"""
        current_time = time.time()
        key = f"{ip_address}:{user_id}" if user_id else ip_address
        
        if key not in self.incident_tracking:
            self.incident_tracking[key] = []
        
        # Clean old incidents (older than 1 hour)
        self.incident_tracking[key] = [
            incident_time for incident_time in self.incident_tracking[key]
            if current_time - incident_time < 3600
        ]
        
        # Add current incident
        self.incident_tracking[key].append(current_time)
    
    def _get_incident_count(self, ip_address: str) -> int:
        """Get security incident count for IP"""
        return len(self.incident_tracking.get(ip_address, []))
    
    def _create_auth_error_response(
        self, exception: AuthenticationException, request: Request
    ) -> JSONResponse:
        """Create authentication error response"""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": {
                    "code": exception.error_code,
                    "message": "Authentication required",
                    "timestamp": int(time.time())
                }
            }
        )
    
    def _create_authorization_error_response(
        self, exception: AuthorizationException, request: Request
    ) -> JSONResponse:
        """Create authorization error response"""
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": {
                    "code": exception.error_code,
                    "message": "Access denied",
                    "timestamp": int(time.time())
                }
            }
        )
    
    def _create_generic_security_error_response(
        self, exception: Exception, request: Request
    ) -> JSONResponse:
        """Create generic security error response"""
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": {
                    "code": "SECURITY_VIOLATION",
                    "message": "Security policy violation",
                    "timestamp": int(time.time())
                }
            }
        )

class ErrorResponseFormatter:
    """Standardized error response formatting"""
    
    @staticmethod
    def format_error_response(
        error_code: str,
        message: str,
        status_code: int = 500,
        details: Optional[Dict] = None,
        correlation_id: Optional[str] = None,
        suggestions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create standardized error response"""
        response = {
            "error": {
                "code": error_code,
                "message": message,
                "timestamp": int(time.time())
            }
        }
        
        if details:
            response["error"]["details"] = details
        
        if suggestions:
            response["error"]["suggestions"] = suggestions
        
        if correlation_id:
            response["correlation_id"] = correlation_id
        
        return response

class ErrorNotificationHandler:
    """Critical error notification handler"""
    
    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service
        self.notification_cooldown = {}  # Prevent spam notifications
        self.cooldown_period = 300  # 5 minutes
    
    async def send_error_notification(self, error_data: Dict[str, Any]):
        """Send notification for critical errors"""
        error_type = error_data.get('exception_type', 'unknown')
        
        # Check cooldown to prevent spam
        if self._is_in_cooldown(error_type):
            return
        
        try:
            await self.notification_service.send_critical_error_notification(error_data)
            self._set_cooldown(error_type)
        except Exception as e:
            logger.error(f"Failed to send error notification: {str(e)}")
    
    def _is_in_cooldown(self, error_type: str) -> bool:
        """Check if error type is in cooldown period"""
        if error_type not in self.notification_cooldown:
            return False
        
        return time.time() - self.notification_cooldown[error_type] < self.cooldown_period
    
    def _set_cooldown(self, error_type: str):
        """Set cooldown for error type"""
        self.notification_cooldown[error_type] = time.time()