# service_factory.py

from typing import Type, TypeVar, Dict, Optional, Any
from threading import Lock
import logging
from dependency_injector import containers, providers
from .base_service import BaseService, ServiceConfig, ServiceException

T = TypeVar('T', bound=BaseService)

class ServiceRegistry:
    """Registry for service class mappings"""
    
    def __init__(self):
        self._registry: Dict[str, Type[BaseService]] = {}
        self._lock = Lock()
        self.logger = logging.getLogger(self.__class__.__name__)

    def register(self, service_name: str, service_class: Type[BaseService]) -> None:
        """Register a service class"""
        with self._lock:
            if service_name in self._registry:
                raise ServiceException(f"Service {service_name} already registered")
            self._registry[service_name] = service_class
            self.logger.info(f"Registered service: {service_name}")

    def unregister(self, service_name: str) -> None:
        """Unregister a service class"""
        with self._lock:
            if service_name not in self._registry:
                raise ServiceException(f"Service {service_name} not found")
            del self._registry[service_name]
            self.logger.info(f"Unregistered service: {service_name}")

    def get_service_class(self, service_name: str) -> Type[BaseService]:
        """Get a service class by name"""
        if service_name not in self._registry:
            raise ServiceException(f"Service {service_name} not found")
        return self._registry[service_name]

    def list_services(self) -> Dict[str, Type[BaseService]]:
        """List all registered services"""
        return self._registry.copy()

class DependencyContainer(containers.DeclarativeContainer):
    """Container for dependency injection"""
    
    config = providers.Configuration()
    
    # Core services
    logger = providers.Singleton(
        logging.Logger,
        name="ServiceLogger"
    )
    
    service_registry = providers.Singleton(
        ServiceRegistry
    )

class ServiceLocator:
    """Service locator pattern implementation"""
    
    def __init__(self):
        self._services: Dict[str, BaseService] = {}
        self._lock = Lock()
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_instance(self, service_name: str, instance: BaseService) -> None:
        """Register a service instance"""
        with self._lock:
            if service_name in self._services:
                raise ServiceException(f"Service instance {service_name} already registered")
            self._services[service_name] = instance
            self.logger.info(f"Registered service instance: {service_name}")

    def unregister_instance(self, service_name: str) -> None:
        """Unregister a service instance"""
        with self._lock:
            if service_name not in self._services:
                raise ServiceException(f"Service instance {service_name} not found")
            del self._services[service_name]
            self.logger.info(f"Unregistered service instance: {service_name}")

    def get_instance(self, service_name: str) -> BaseService:
        """Get a service instance by name"""
        if service_name not in self._services:
            raise ServiceException(f"Service instance {service_name} not found")
        return self._services[service_name]

class ServiceLifecycleManager:
    """Manages service lifecycle and dependencies"""
    
    def __init__(self):
        self._active_services: Dict[str, BaseService] = {}
        self._lock = Lock()
        self.logger = logging.getLogger(self.__class__.__name__)

    def start_service(
        self,
        service_name: str,
        service_class: Type[BaseService],
        config: Optional[ServiceConfig] = None,
        **kwargs: Any
    ) -> BaseService:
        """Start and initialize a service"""
        with self._lock:
            if service_name in self._active_services:
                raise ServiceException(f"Service {service_name} already running")
            
            try:
                service_instance = service_class(config=config, **kwargs)
                self._active_services[service_name] = service_instance
                self.logger.info(f"Started service: {service_name}")
                return service_instance
            except Exception as e:
                self.logger.error(f"Failed to start service {service_name}: {str(e)}")
                raise ServiceException(f"Service startup failed: {str(e)}")

    def stop_service(self, service_name: str) -> None:
        """Stop and cleanup a service"""
        with self._lock:
            if service_name not in self._active_services:
                raise ServiceException(f"Service {service_name} not found")
            
            try:
                service = self._active_services[service_name]
                service.cleanup()
                del self._active_services[service_name]
                self.logger.info(f"Stopped service: {service_name}")
            except Exception as e:
                self.logger.error(f"Failed to stop service {service_name}: {str(e)}")
                raise ServiceException(f"Service shutdown failed: {str(e)}")

    def get_active_services(self) -> Dict[str, BaseService]:
        """Get all active services"""
        return self._active_services.copy()

class ServiceFactory:
    """Factory for creating and managing services"""
    
    def __init__(self):
        self.registry = ServiceRegistry()
        self.locator = ServiceLocator()
        self.lifecycle_manager = ServiceLifecycleManager()
        self.container = DependencyContainer()
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_service(
        self,
        service_name: str,
        service_class: Type[T]
    ) -> None:
        """Register a new service class"""
        self.registry.register(service_name, service_class)

    def create_service(
        self,
        service_name: str,
        config: Optional[ServiceConfig] = None,
        **kwargs: Any
    ) -> T:
        """Create and initialize a new service instance"""
        service_class = self.registry.get_service_class(service_name)
        service_instance = self.lifecycle_manager.start_service(
            service_name,
            service_class,
            config,
            **kwargs
        )
        self.locator.register_instance(service_name, service_instance)
        return service_instance

    def get_service(self, service_name: str) -> T:
        """Get an existing service instance"""
        return self.locator.get_instance(service_name)

    def stop_service(self, service_name: str) -> None:
        """Stop and cleanup a service"""
        self.lifecycle_manager.stop_service(service_name)
        self.locator.unregister_instance(service_name)

    def cleanup(self) -> None:
        """Cleanup all services"""
        active_services = self.lifecycle_manager.get_active_services()
        for service_name in active_services:
            self.stop_service(service_name)
        self.logger.info("All services cleaned up")