"""
Service factory for dependency injection and service instantiation.
"""

from typing import Optional, Dict, Type, TypeVar, Generic
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.repositories.base.repository_factory import RepositoryFactory
from app.services.base.audit_service import AuditService
from app.services.base.authorization_service import AuthorizationService
from app.services.base.notification_dispatcher import NotificationDispatcher
from app.services.base.cache_service import CacheService
from app.services.base.base_service import BaseService
from app.repositories.audit.audit_log_repository import AuditLogRepository
from app.repositories.admin.admin_permissions_repository import AdminPermissionsRepository
from app.repositories.notification.notification_repository import NotificationRepository
from app.repositories.notification.notification_queue_repository import NotificationQueueRepository
from app.config.redis import RedisManager


TService = TypeVar('TService', bound=BaseService)


class ServiceFactory:
    """
    Factory for creating service instances with dependency injection.
    
    Provides:
    - Centralized service creation
    - Dependency management
    - Service caching/reuse
    - Configuration management
    """

    def __init__(
        self,
        db_session: Session,
        redis_manager: Optional[RedisManager] = None,
    ):
        """
        Initialize service factory.
        
        Args:
            db_session: SQLAlchemy database session
            redis_manager: Optional Redis manager for cache services
        """
        self.db = db_session
        self.redis_manager = redis_manager
        self.repo_factory = RepositoryFactory(db_session)
        self._logger = get_logger(self.__class__.__name__)
        
        # Service cache to reuse instances
        self._service_cache: Dict[str, BaseService] = {}

    # -------------------------------------------------------------------------
    # Core Service Getters
    # -------------------------------------------------------------------------

    def audit(self, use_cache: bool = True) -> AuditService:
        """
        Get or create audit service instance.
        
        Args:
            use_cache: Whether to use cached instance
            
        Returns:
            AuditService instance
        """
        cache_key = "audit_service"
        
        if use_cache and cache_key in self._service_cache:
            return self._service_cache[cache_key]
        
        service = AuditService(
            self.repo_factory.get(AuditLogRepository),
            self.db
        )
        
        if use_cache:
            self._service_cache[cache_key] = service
        
        self._logger.debug("Created AuditService instance")
        return service

    def authorization(self, use_cache: bool = True) -> AuthorizationService:
        """
        Get or create authorization service instance.
        
        Args:
            use_cache: Whether to use cached instance
            
        Returns:
            AuthorizationService instance
        """
        cache_key = "authorization_service"
        
        if use_cache and cache_key in self._service_cache:
            return self._service_cache[cache_key]
        
        service = AuthorizationService(
            self.repo_factory.get(AdminPermissionsRepository),
            self.db
        )
        
        if use_cache:
            self._service_cache[cache_key] = service
        
        self._logger.debug("Created AuthorizationService instance")
        return service

    def notification(self, use_cache: bool = True) -> NotificationDispatcher:
        """
        Get or create notification dispatcher instance.
        
        Args:
            use_cache: Whether to use cached instance
            
        Returns:
            NotificationDispatcher instance
        """
        cache_key = "notification_dispatcher"
        
        if use_cache and cache_key in self._service_cache:
            return self._service_cache[cache_key]
        
        notif_repo = self.repo_factory.get(NotificationRepository)
        queue_repo = self.repo_factory.get(NotificationQueueRepository)
        
        service = NotificationDispatcher(notif_repo, queue_repo, self.db)
        
        if use_cache:
            self._service_cache[cache_key] = service
        
        self._logger.debug("Created NotificationDispatcher instance")
        return service

    def cache(
        self,
        namespace: str = "svc",
        default_ttl: int = 300,
        use_cache: bool = True,
    ) -> Optional[CacheService]:
        """
        Get or create cache service instance.
        
        Args:
            namespace: Cache namespace
            default_ttl: Default TTL in seconds
            use_cache: Whether to use cached instance
            
        Returns:
            CacheService instance or None if Redis not available
        """
        if not self.redis_manager:
            self._logger.warning("Redis manager not configured, cache service unavailable")
            return None
        
        cache_key = f"cache_service_{namespace}"
        
        if use_cache and cache_key in self._service_cache:
            return self._service_cache[cache_key]
        
        service = CacheService(
            self.redis_manager,
            namespace=namespace,
            default_ttl=default_ttl
        )
        
        if use_cache:
            self._service_cache[cache_key] = service
        
        self._logger.debug(f"Created CacheService instance (namespace: {namespace})")
        return service

    # -------------------------------------------------------------------------
    # Generic Service Creation
    # -------------------------------------------------------------------------

    def create_service(
        self,
        service_class: Type[TService],
        *args,
        **kwargs
    ) -> TService:
        """
        Create a service instance with provided arguments.
        
        Args:
            service_class: Service class to instantiate
            *args: Positional arguments for service constructor
            **kwargs: Keyword arguments for service constructor
            
        Returns:
            Service instance
        """
        try:
            # Inject db_session if not provided
            if 'db_session' not in kwargs:
                kwargs['db_session'] = self.db
            
            service = service_class(*args, **kwargs)
            
            self._logger.debug(
                f"Created service instance: {service_class.__name__}",
                extra={"service_class": service_class.__name__}
            )
            
            return service
            
        except Exception as e:
            self._logger.error(
                f"Failed to create service {service_class.__name__}: {e}",
                exc_info=True
            )
            raise

    # -------------------------------------------------------------------------
    # Service Management
    # -------------------------------------------------------------------------

    def clear_cache(self) -> None:
        """Clear all cached service instances."""
        count = len(self._service_cache)
        self._service_cache.clear()
        self._logger.info(f"Cleared {count} cached service instances")

    def get_cached_services(self) -> Dict[str, str]:
        """
        Get information about cached services.
        
        Returns:
            Dictionary mapping cache keys to service class names
        """
        return {
            key: service.__class__.__name__
            for key, service in self._service_cache.items()
        }

    def close(self) -> None:
        """
        Clean up factory resources.
        Should be called when factory is no longer needed.
        """
        self.clear_cache()
        self._logger.debug("ServiceFactory closed")


class ServiceFactoryProvider:
    """
    Provider for managing service factory lifecycle.
    Useful for dependency injection in web frameworks.
    """
    
    _instance: Optional[ServiceFactory] = None
    
    @classmethod
    def get_factory(
        cls,
        db_session: Session,
        redis_manager: Optional[RedisManager] = None,
    ) -> ServiceFactory:
        """
        Get or create service factory instance.
        
        Args:
            db_session: Database session
            redis_manager: Optional Redis manager
            
        Returns:
            ServiceFactory instance
        """
        # Note: In production, you might want session-scoped factories
        # This is a simplified implementation
        return ServiceFactory(db_session, redis_manager)
    
    @classmethod
    def close_factory(cls) -> None:
        """Close and clean up factory instance."""
        if cls._instance:
            cls._instance.close()
            cls._instance = None