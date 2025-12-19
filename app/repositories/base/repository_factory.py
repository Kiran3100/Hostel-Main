"""
Repository factory for centralized instantiation and dependency injection.

Provides singleton pattern, configuration management, and
lifecycle control for repositories.
"""

from typing import Any, Dict, Optional, Type, TypeVar, Generic
from functools import lru_cache
import importlib

from sqlalchemy.orm import Session

from app.models.base import BaseModel
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.caching_repository import CachingRepository
from app.core.config import settings
from app.core.logging import get_logger
from app.core.cache import CacheManager

logger = get_logger(__name__)

ModelType = TypeVar("ModelType", bound=BaseModel)
RepositoryType = TypeVar("RepositoryType", bound=BaseRepository)


class RepositoryRegistry:
    """Registry for repository classes."""
    
    _repositories: Dict[str, Type[BaseRepository]] = {}
    
    @classmethod
    def register(cls, name: str, repository_class: Type[BaseRepository]) -> None:
        """
        Register repository class.
        
        Args:
            name: Repository name
            repository_class: Repository class
        """
        cls._repositories[name] = repository_class
        logger.debug(f"Registered repository: {name}")
    
    @classmethod
    def get(cls, name: str) -> Optional[Type[BaseRepository]]:
        """
        Get repository class by name.
        
        Args:
            name: Repository name
            
        Returns:
            Repository class or None
        """
        return cls._repositories.get(name)
    
    @classmethod
    def list_all(cls) -> Dict[str, Type[BaseRepository]]:
        """
        Get all registered repositories.
        
        Returns:
            Dictionary of repository classes
        """
        return cls._repositories.copy()


class RepositoryFactory:
    """
    Factory for creating and managing repository instances.
    
    Provides centralized instantiation with dependency injection,
    caching, and lifecycle management.
    """
    
    def __init__(
        self,
        db: Session,
        cache_manager: Optional[CacheManager] = None,
        enable_caching: bool = True,
        enable_performance_profiling: bool = False
    ):
        """
        Initialize repository factory.
        
        Args:
            db: Database session
            cache_manager: Cache manager instance
            enable_caching: Whether to enable caching
            enable_performance_profiling: Whether to enable profiling
        """
        self.db = db
        self.cache_manager = cache_manager
        self.enable_caching = enable_caching
        self.enable_performance_profiling = enable_performance_profiling
        self._instances: Dict[str, BaseRepository] = {}
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load repository configuration.
        
        Returns:
            Configuration dictionary
        """
        return {
            "default_page_size": getattr(settings, "DEFAULT_PAGE_SIZE", 50),
            "max_page_size": getattr(settings, "MAX_PAGE_SIZE", 1000),
            "cache_ttl": getattr(settings, "CACHE_TTL", 300),
            "enable_query_logging": getattr(settings, "ENABLE_QUERY_LOGGING", False),
        }
    
    def create(
        self,
        repository_class: Type[RepositoryType],
        model: Type[ModelType],
        singleton: bool = True,
        **kwargs
    ) -> RepositoryType:
        """
        Create repository instance.
        
        Args:
            repository_class: Repository class to instantiate
            model: Model class
            singleton: Whether to use singleton pattern
            **kwargs: Additional arguments for repository
            
        Returns:
            Repository instance
        """
        # Generate instance key
        key = f"{repository_class.__name__}:{model.__name__}"
        
        # Return existing instance if singleton
        if singleton and key in self._instances:
            return self._instances[key]
        
        # Create base repository
        repository = repository_class(model=model, db=self.db, **kwargs)
        
        # Wrap with caching if enabled
        if self.enable_caching and self.cache_manager:
            repository = CachingRepository(
                repository=repository,
                cache_manager=self.cache_manager,
                ttl=self._config["cache_ttl"]
            )
        
        # Store instance if singleton
        if singleton:
            self._instances[key] = repository
        
        logger.debug(f"Created repository: {key}")
        return repository
    
    def create_by_name(
        self,
        name: str,
        model: Type[ModelType],
        singleton: bool = True,
        **kwargs
    ) -> BaseRepository:
        """
        Create repository by registered name.
        
        Args:
            name: Repository name
            model: Model class
            singleton: Whether to use singleton pattern
            **kwargs: Additional arguments
            
        Returns:
            Repository instance
            
        Raises:
            ValueError: If repository not found
        """
        repository_class = RepositoryRegistry.get(name)
        if not repository_class:
            raise ValueError(f"Repository not found: {name}")
        
        return self.create(repository_class, model, singleton, **kwargs)
    
    def create_base(
        self,
        model: Type[ModelType],
        singleton: bool = True
    ) -> BaseRepository[ModelType]:
        """
        Create base repository for model.
        
        Args:
            model: Model class
            singleton: Whether to use singleton pattern
            
        Returns:
            Base repository instance
        """
        return self.create(BaseRepository, model, singleton)
    
    def get_or_create(
        self,
        repository_class: Type[RepositoryType],
        model: Type[ModelType],
        **kwargs
    ) -> RepositoryType:
        """
        Get existing or create new repository instance.
        
        Args:
            repository_class: Repository class
            model: Model class
            **kwargs: Additional arguments
            
        Returns:
            Repository instance
        """
        return self.create(repository_class, model, singleton=True, **kwargs)
    
    def clear_cache(self, repository_name: Optional[str] = None) -> None:
        """
        Clear repository caches.
        
        Args:
            repository_name: Specific repository to clear, or all if None
        """
        if repository_name:
            if repository_name in self._instances:
                repo = self._instances[repository_name]
                if hasattr(repo, 'clear_cache'):
                    repo.clear_cache()
        else:
            for repo in self._instances.values():
                if hasattr(repo, 'clear_cache'):
                    repo.clear_cache()
        
        logger.info(f"Cleared cache for: {repository_name or 'all repositories'}")
    
    def reset(self) -> None:
        """Reset factory and clear all instances."""
        self._instances.clear()
        logger.info("Repository factory reset")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get factory statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_instances": len(self._instances),
            "repositories": list(self._instances.keys()),
            "caching_enabled": self.enable_caching,
            "profiling_enabled": self.enable_performance_profiling,
        }
    
    def auto_discover_repositories(self, package: str = "app.repositories") -> None:
        """
        Auto-discover and register repositories from package.
        
        Args:
            package: Package to scan for repositories
        """
        try:
            module = importlib.import_module(package)
            # Scan for repository classes and register them
            # Implementation depends on project structure
            logger.info(f"Auto-discovered repositories from: {package}")
        except ImportError as e:
            logger.error(f"Failed to auto-discover repositories: {e}")


class RepositoryDecorator:
    """Base decorator for repository enhancements."""
    
    def __init__(self, repository: BaseRepository):
        self.repository = repository
        self._wrap_methods()
    
    def _wrap_methods(self) -> None:
        """Wrap repository methods with decorator logic."""
        # Get all public methods from repository
        for attr_name in dir(self.repository):
            if not attr_name.startswith('_'):
                attr = getattr(self.repository, attr_name)
                if callable(attr):
                    wrapped = self._wrap_method(attr)
                    setattr(self, attr_name, wrapped)
    
    def _wrap_method(self, method):
        """Wrap single method."""
        def wrapper(*args, **kwargs):
            return self._before_call(method, *args, **kwargs)
        return wrapper
    
    def _before_call(self, method, *args, **kwargs):
        """Hook before method call."""
        return method(*args, **kwargs)
    
    def __getattr__(self, name):
        """Delegate attribute access to repository."""
        return getattr(self.repository, name)


class PerformanceProfilingDecorator(RepositoryDecorator):
    """Decorator for repository performance profiling."""
    
    def __init__(self, repository: BaseRepository):
        super().__init__(repository)
        self._call_stats: Dict[str, Dict[str, Any]] = {}
    
    def _before_call(self, method, *args, **kwargs):
        """Profile method execution."""
        import time
        
        method_name = method.__name__
        start_time = time.time()
        
        try:
            result = method(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Update statistics
            if method_name not in self._call_stats:
                self._call_stats[method_name] = {
                    "count": 0,
                    "total_time": 0,
                    "min_time": float('inf'),
                    "max_time": 0,
                }
            
            stats = self._call_stats[method_name]
            stats["count"] += 1
            stats["total_time"] += execution_time
            stats["min_time"] = min(stats["min_time"], execution_time)
            stats["max_time"] = max(stats["max_time"], execution_time)
            
            logger.debug(
                f"{method_name} executed in {execution_time:.4f}s"
            )
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"{method_name} failed after {execution_time:.4f}s: {e}"
            )
            raise
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get profiling statistics."""
        stats = {}
        for method_name, data in self._call_stats.items():
            stats[method_name] = {
                "calls": data["count"],
                "total_time": round(data["total_time"], 4),
                "avg_time": round(data["total_time"] / data["count"], 4),
                "min_time": round(data["min_time"], 4),
                "max_time": round(data["max_time"], 4),
            }
        return stats


class TransactionDecorator(RepositoryDecorator):
    """Decorator for automatic transaction management."""
    
    def __init__(
        self,
        repository: BaseRepository,
        auto_commit: bool = True
    ):
        self.auto_commit = auto_commit
        super().__init__(repository)
    
    def _before_call(self, method, *args, **kwargs):
        """Wrap method in transaction."""
        # Only wrap mutating operations
        mutating_methods = [
            'create', 'update', 'delete', 'soft_delete',
            'create_many', 'update_many'
        ]
        
        if method.__name__ in mutating_methods:
            with self.repository.transaction():
                return method(*args, **kwargs)
        
        return method(*args, **kwargs)


# Global factory instance
_global_factory: Optional[RepositoryFactory] = None


def get_repository_factory(db: Session) -> RepositoryFactory:
    """
    Get global repository factory instance.
    
    Args:
        db: Database session
        
    Returns:
        Repository factory instance
    """
    global _global_factory
    if _global_factory is None:
        _global_factory = RepositoryFactory(db=db)
    return _global_factory


def reset_factory() -> None:
    """Reset global factory instance."""
    global _global_factory
    if _global_factory:
        _global_factory.reset()
    _global_factory = None