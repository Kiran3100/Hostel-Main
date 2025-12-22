# base_service.py

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging
import uuid

T = TypeVar('T')

@dataclass
class ServiceConfig:
    """Configuration settings for services"""
    tenant_id: str
    environment: str
    debug_mode: bool
    timeout_seconds: int
    retry_attempts: int
    cache_enabled: bool
    metrics_enabled: bool
    log_level: str
    service_version: str
    
    @classmethod
    def create_default(cls) -> 'ServiceConfig':
        return cls(
            tenant_id="default",
            environment="development",
            debug_mode=True,
            timeout_seconds=30,
            retry_attempts=3,
            cache_enabled=True,
            metrics_enabled=True,
            log_level="INFO",
            service_version="1.0.0"
        )

@dataclass
class ServiceContext:
    """Execution context for service operations"""
    request_id: str
    user_id: Optional[str]
    tenant_id: str
    correlation_id: str
    timestamp: datetime
    trace_id: str
    source: str
    metadata: Dict[str, Any]

    @classmethod
    def create(cls, user_id: Optional[str] = None, tenant_id: str = "default") -> 'ServiceContext':
        return cls(
            request_id=str(uuid.uuid4()),
            user_id=user_id,
            tenant_id=tenant_id,
            correlation_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            trace_id=str(uuid.uuid4()),
            source="system",
            metadata={}
        )

@dataclass
class ServiceResponse(Generic[T]):
    """Standard response wrapper for service operations"""
    success: bool
    data: Optional[T]
    error: Optional[str]
    message: Optional[str]
    code: str
    timestamp: datetime
    trace_id: str
    metadata: Dict[str, Any]

    @classmethod
    def success_response(cls, data: T, message: str = "Operation successful") -> 'ServiceResponse[T]':
        return cls(
            success=True,
            data=data,
            error=None,
            message=message,
            code="SUCCESS",
            timestamp=datetime.utcnow(),
            trace_id=str(uuid.uuid4()),
            metadata={}
        )

    @classmethod
    def error_response(cls, error: str, code: str = "ERROR") -> 'ServiceResponse[T]':
        return cls(
            success=False,
            data=None,
            error=error,
            message=None,
            code=code,
            timestamp=datetime.utcnow(),
            trace_id=str(uuid.uuid4()),
            metadata={}
        )

class ServiceException(Exception):
    """Base exception for service layer errors"""
    def __init__(
        self, 
        message: str,
        code: str = "SERVICE_ERROR",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.cause = cause
        self.timestamp = datetime.utcnow()
        self.trace_id = str(uuid.uuid4())

class BaseService(ABC):
    """Abstract base class for all services"""
    
    def __init__(
        self,
        config: Optional[ServiceConfig] = None,
        logger: Optional[logging.Logger] = None
    ):
        self.config = config or ServiceConfig.create_default()
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.initialize_service()

    def initialize_service(self) -> None:
        """Initialize service resources and connections"""
        self.logger.info(f"Initializing service {self.__class__.__name__}")
        try:
            self._setup_monitoring()
            self._setup_connections()
            self._validate_configuration()
            self._register_event_handlers()
        except Exception as e:
            self.logger.error(f"Service initialization failed: {str(e)}")
            raise ServiceException("Service initialization failed", cause=e)

    @abstractmethod
    def _setup_monitoring(self) -> None:
        """Setup monitoring and metrics collection"""
        pass

    @abstractmethod
    def _setup_connections(self) -> None:
        """Setup required connections and resources"""
        pass

    @abstractmethod
    def _validate_configuration(self) -> None:
        """Validate service configuration"""
        pass

    @abstractmethod
    def _register_event_handlers(self) -> None:
        """Register event handlers for the service"""
        pass

    def execute_with_context(
        self,
        context: ServiceContext,
        operation: callable,
        *args,
        **kwargs
    ) -> ServiceResponse:
        """Execute an operation within a service context"""
        self.logger.debug(f"Executing operation with context {context.request_id}")
        try:
            self._before_execution(context)
            result = operation(*args, **kwargs)
            self._after_execution(context)
            return ServiceResponse.success_response(result)
        except ServiceException as se:
            self._handle_service_exception(se, context)
            return ServiceResponse.error_response(str(se), se.code)
        except Exception as e:
            self._handle_unexpected_exception(e, context)
            return ServiceResponse.error_response(str(e))

    def _before_execution(self, context: ServiceContext) -> None:
        """Pre-execution hooks"""
        pass

    def _after_execution(self, context: ServiceContext) -> None:
        """Post-execution hooks"""
        pass

    def _handle_service_exception(
        self,
        exception: ServiceException,
        context: ServiceContext
    ) -> None:
        """Handle known service exceptions"""
        self.logger.error(
            f"Service exception in {context.request_id}: {str(exception)}",
            extra={
                "trace_id": context.trace_id,
                "error_code": exception.code,
                "details": exception.details
            }
        )

    def _handle_unexpected_exception(
        self,
        exception: Exception,
        context: ServiceContext
    ) -> None:
        """Handle unexpected exceptions"""
        self.logger.error(
            f"Unexpected error in {context.request_id}: {str(exception)}",
            extra={"trace_id": context.trace_id},
            exc_info=True
        )

    def cleanup(self) -> None:
        """Cleanup service resources"""
        self.logger.info(f"Cleaning up service {self.__class__.__name__}")