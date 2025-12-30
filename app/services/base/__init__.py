"""
Base services module for the Hostel Management System.

This module provides foundational service layer components including:
- Base service classes with common functionality
- Transaction management
- Caching services
- Audit logging
- Authorization and permissions
- Event dispatching
- Notification management
- Validation utilities
- Error handling

All services follow consistent patterns for:
- Result handling via ServiceResult
- Error management and logging
- Transaction safety
- Performance optimization
"""

from app.services.base.service_result import (
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)

from app.services.base.base_service import BaseService

from app.services.base.audit_service import AuditService

from app.services.base.authorization_service import AuthorizationService

from app.services.base.cache_service import CacheService

from app.services.base.error_handler import ErrorHandler

from app.services.base.event_dispatcher import (
    EventDispatcher,
    DispatchedEvent,
    DispatchResult,
    EventDispatcherFactory,
)

from app.services.base.notification_dispatcher import (
    NotificationDispatcher,
    NotificationPriority,
    NotificationChannel,
)

from app.services.base.service_factory import (
    ServiceFactory,
    ServiceFactoryProvider,
)

from app.services.base.transaction_manager import (
    TransactionManager,
    TransactionContext,
    TransactionManagerFactory,
)

from app.services.base.validation_service import (
    ValidationService,
    ValidationRule,
)


__all__ = [
    # Service Result Types
    "ServiceResult",
    "ServiceError",
    "ErrorCode",
    "ErrorSeverity",
    
    # Base Classes
    "BaseService",
    
    # Core Services
    "AuditService",
    "AuthorizationService",
    "CacheService",
    
    # Error Handling
    "ErrorHandler",
    
    # Event Management
    "EventDispatcher",
    "DispatchedEvent",
    "DispatchResult",
    "EventDispatcherFactory",
    
    # Notification Management
    "NotificationDispatcher",
    "NotificationPriority",
    "NotificationChannel",
    
    # Service Factory
    "ServiceFactory",
    "ServiceFactoryProvider",
    
    # Transaction Management
    "TransactionManager",
    "TransactionContext",
    "TransactionManagerFactory",
    
    # Validation
    "ValidationService",
    "ValidationRule",
]


# Module metadata
__version__ = "1.0.0"
__author__ = "Hostel Management System Team"
__description__ = "Base service layer components with consistent patterns and utilities"


# Module-level convenience functions
def create_service_factory(db_session, redis_manager=None):
    """
    Convenience function to create a service factory.
    
    Args:
        db_session: SQLAlchemy database session
        redis_manager: Optional Redis manager for caching
        
    Returns:
        ServiceFactory instance
        
    Example:
        from sqlalchemy.orm import Session
        from app.services.base import create_service_factory
        
        factory = create_service_factory(db_session)
        audit_service = factory.audit()
    """
    return ServiceFactory(db_session, redis_manager)


def create_transaction_manager(db_session):
    """
    Convenience function to create a transaction manager.
    
    Args:
        db_session: SQLAlchemy database session
        
    Returns:
        TransactionManager instance
        
    Example:
        from app.services.base import create_transaction_manager
        
        tx_manager = create_transaction_manager(db_session)
        with tx_manager.start():
            # perform operations
    """
    return TransactionManagerFactory.create(db_session)


def create_error_handler(logger_name=None):
    """
    Convenience function to create an error handler.
    
    Args:
        logger_name: Optional logger name
        
    Returns:
        ErrorHandler instance
        
    Example:
        from app.services.base import create_error_handler
        
        error_handler = create_error_handler("MyService")
        result = error_handler.handle(exception, "operation")
    """
    return ErrorHandler(logger_name or "ServiceErrorHandler")


# Service initialization helpers
class ServiceConfig:
    """
    Configuration container for service initialization.
    
    Provides centralized configuration for service layer components.
    """
    
    # Cache configuration
    CACHE_DEFAULT_TTL = 300  # 5 minutes
    CACHE_NAMESPACE = "svc"
    
    # Transaction configuration
    TRANSACTION_TIMEOUT = 30  # seconds
    TRANSACTION_MAX_RETRIES = 3
    
    # Event dispatcher configuration
    EVENT_MAX_RETRIES = 3
    EVENT_RETRY_DELAY = 0.5  # seconds
    
    # Notification configuration
    NOTIFICATION_DEFAULT_PRIORITY = NotificationPriority.NORMAL
    NOTIFICATION_BATCH_SIZE = 100
    
    # Audit configuration
    AUDIT_RETENTION_DAYS = 90
    AUDIT_BATCH_SIZE = 1000
    
    # Authorization configuration
    PERMISSION_CACHE_TTL = 300  # 5 minutes
    
    @classmethod
    def configure(cls, **kwargs):
        """
        Configure service settings.
        
        Args:
            **kwargs: Configuration key-value pairs
            
        Example:
            ServiceConfig.configure(
                CACHE_DEFAULT_TTL=600,
                NOTIFICATION_BATCH_SIZE=200
            )
        """
        for key, value in kwargs.items():
            if hasattr(cls, key):
                setattr(cls, key, value)
    
    @classmethod
    def get_config(cls):
        """
        Get current configuration as dictionary.
        
        Returns:
            Dictionary of configuration values
        """
        return {
            key: value
            for key, value in cls.__dict__.items()
            if not key.startswith('_') and not callable(value)
        }


# Service registry for dependency injection
class ServiceRegistry:
    """
    Registry for managing service instances and dependencies.
    
    Provides a simple dependency injection container for services.
    """
    
    _instances = {}
    _factories = {}
    
    @classmethod
    def register(cls, service_name, service_instance=None, factory=None):
        """
        Register a service instance or factory.
        
        Args:
            service_name: Unique service identifier
            service_instance: Pre-created service instance
            factory: Factory function to create service
            
        Example:
            ServiceRegistry.register(
                'audit',
                factory=lambda: AuditService(repo, db)
            )
        """
        if service_instance is not None:
            cls._instances[service_name] = service_instance
        elif factory is not None:
            cls._factories[service_name] = factory
        else:
            raise ValueError("Either service_instance or factory must be provided")
    
    @classmethod
    def get(cls, service_name, create_if_missing=True):
        """
        Get a service instance by name.
        
        Args:
            service_name: Service identifier
            create_if_missing: Create from factory if not exists
            
        Returns:
            Service instance or None
            
        Example:
            audit_service = ServiceRegistry.get('audit')
        """
        # Return existing instance if available
        if service_name in cls._instances:
            return cls._instances[service_name]
        
        # Create from factory if available
        if create_if_missing and service_name in cls._factories:
            instance = cls._factories[service_name]()
            cls._instances[service_name] = instance
            return instance
        
        return None
    
    @classmethod
    def clear(cls, service_name=None):
        """
        Clear registered services.
        
        Args:
            service_name: Specific service to clear, or None for all
            
        Example:
            ServiceRegistry.clear('audit')  # Clear specific service
            ServiceRegistry.clear()  # Clear all services
        """
        if service_name:
            cls._instances.pop(service_name, None)
            cls._factories.pop(service_name, None)
        else:
            cls._instances.clear()
            cls._factories.clear()
    
    @classmethod
    def list_services(cls):
        """
        List all registered services.
        
        Returns:
            Dictionary with service names and their status
        """
        return {
            'instances': list(cls._instances.keys()),
            'factories': list(cls._factories.keys()),
        }


# Decorator for service method error handling
def handle_service_errors(operation_name=None):
    """
    Decorator to automatically handle service method errors.
    
    Args:
        operation_name: Description of the operation
        
    Returns:
        Decorated function
        
    Example:
        @handle_service_errors("create user")
        def create_user(self, data):
            # method implementation
    """
    def decorator(func):
        from functools import wraps
        
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            operation = operation_name or func.__name__.replace('_', ' ')
            
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                # Use service's error handler if available
                if hasattr(self, '_handle_exception'):
                    return self._handle_exception(e, operation)
                
                # Fallback to generic error handling
                error_handler = create_error_handler(self.__class__.__name__)
                return error_handler.handle(e, operation)
        
        return wrapper
    return decorator


# Decorator for caching service method results
def cache_result(key_builder=None, ttl=None, namespace=None):
    """
    Decorator to cache service method results.
    
    Args:
        key_builder: Function to build cache key from arguments
        ttl: Cache TTL in seconds
        namespace: Cache namespace
        
    Returns:
        Decorated function
        
    Example:
        @cache_result(
            key_builder=lambda self, user_id: f"user:{user_id}",
            ttl=600
        )
        def get_user(self, user_id):
            # method implementation
    """
    def decorator(func):
        from functools import wraps
        
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Check if service has cache
            cache = getattr(self, '_cache', None)
            if not cache:
                # No cache available, execute function normally
                return func(self, *args, **kwargs)
            
            # Build cache key
            if key_builder:
                cache_key = key_builder(self, *args, **kwargs)
            else:
                # Auto-generate key
                import hashlib
                key_parts = [func.__name__] + [str(arg) for arg in args]
                key_str = ":".join(key_parts)
                cache_key = hashlib.md5(key_str.encode()).hexdigest()
            
            # Try to get from cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = func(self, *args, **kwargs)
            cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


# Module initialization logging
def _log_module_info():
    """Log module initialization information."""
    from app.core.logging import get_logger
    
    logger = get_logger("services.base")
    logger.info(
        f"Base services module initialized (v{__version__})",
        extra={
            "version": __version__,
            "available_services": __all__,
        }
    )


# Initialize module
_log_module_info()


# Cleanup function for graceful shutdown
def cleanup():
    """
    Cleanup function to be called on application shutdown.
    
    Clears all service registries and cached instances.
    """
    ServiceRegistry.clear()
    
    from app.core1.logging import get_logger
    logger = get_logger("services.base")
    logger.info("Base services module cleaned up")