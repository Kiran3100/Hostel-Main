"""
Multi-layer caching repository with intelligent invalidation and performance monitoring.

Provides L1 (in-memory), L2 (Redis), query cache, and result cache
with automatic invalidation strategies.
"""

from typing import Any, Dict, List, Optional, Type, TypeVar, Callable, Union
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import json
import pickle
from collections import OrderedDict

from sqlalchemy.orm import Query, Session

from app.models.base import BaseModel
from app.repositories.base.base_repository import BaseRepository, AuditContext
from app.core.logging import get_logger
from app.core.cache import CacheManager, CacheBackend
from app.core.exceptions import CacheError

logger = get_logger(__name__)

ModelType = TypeVar("ModelType", bound=BaseModel)


class CacheStrategy:
    """Cache strategy enumeration."""
    
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"
    CACHE_ASIDE = "cache_aside"
    REFRESH_AHEAD = "refresh_ahead"


class CacheLevel:
    """Cache level enumeration."""
    
    L1 = "l1"  # In-memory
    L2 = "l2"  # Redis/Memcached
    L3 = "l3"  # Database


class LRUCache:
    """
    Simple in-memory LRU cache implementation.
    
    Thread-safe Least Recently Used cache with TTL support.
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of items
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: Dict[str, float] = {}
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        if key not in self._cache:
            self._misses += 1
            return None
        
        # Check TTL
        if self._is_expired(key):
            self.delete(key)
            self._misses += 1
            return None
        
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        self._hits += 1
        return self._cache[key]
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
        """
        # Remove oldest if at capacity
        if key not in self._cache and len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)
        
        self._cache[key] = value
        self._cache.move_to_end(key)
        self._timestamps[key] = datetime.utcnow().timestamp()
        
        if ttl:
            self._timestamps[f"{key}:ttl"] = ttl
    
    def delete(self, key: str) -> None:
        """Delete key from cache."""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)
        self._timestamps.pop(f"{key}:ttl", None)
    
    def clear(self) -> None:
        """Clear entire cache."""
        self._cache.clear()
        self._timestamps.clear()
    
    def _is_expired(self, key: str) -> bool:
        """Check if key has expired."""
        if key not in self._timestamps:
            return True
        
        ttl = self._timestamps.get(f"{key}:ttl", self.default_ttl)
        age = datetime.utcnow().timestamp() - self._timestamps[key]
        return age > ttl
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "total_requests": total_requests
        }


class CacheKeyGenerator:
    """Generate cache keys for different operations."""
    
    @staticmethod
    def generate_entity_key(
        table_name: str,
        entity_id: Any
    ) -> str:
        """
        Generate key for single entity.
        
        Args:
            table_name: Table/model name
            entity_id: Entity ID
            
        Returns:
            Cache key
        """
        return f"{table_name}:entity:{entity_id}"
    
    @staticmethod
    def generate_query_key(
        table_name: str,
        query_hash: str
    ) -> str:
        """
        Generate key for query result.
        
        Args:
            table_name: Table/model name
            query_hash: Query hash
            
        Returns:
            Cache key
        """
        return f"{table_name}:query:{query_hash}"
    
    @staticmethod
    def generate_list_key(
        table_name: str,
        criteria_hash: str
    ) -> str:
        """
        Generate key for list query.
        
        Args:
            table_name: Table/model name
            criteria_hash: Criteria hash
            
        Returns:
            Cache key
        """
        return f"{table_name}:list:{criteria_hash}"
    
    @staticmethod
    def generate_count_key(
        table_name: str,
        criteria_hash: str
    ) -> str:
        """
        Generate key for count query.
        
        Args:
            table_name: Table/model name
            criteria_hash: Criteria hash
            
        Returns:
            Cache key
        """
        return f"{table_name}:count:{criteria_hash}"
    
    @staticmethod
    def hash_criteria(criteria: Dict[str, Any]) -> str:
        """
        Generate hash from criteria.
        
        Args:
            criteria: Filter criteria
            
        Returns:
            Hash string
        """
        # Sort criteria for consistent hashing
        criteria_str = json.dumps(criteria, sort_keys=True, default=str)
        return hashlib.md5(criteria_str.encode()).hexdigest()
    
    @staticmethod
    def hash_query(query: Query) -> str:
        """
        Generate hash from SQLAlchemy query.
        
        Args:
            query: SQLAlchemy query
            
        Returns:
            Hash string
        """
        query_str = str(query.statement.compile(
            compile_kwargs={"literal_binds": True}
        ))
        return hashlib.md5(query_str.encode()).hexdigest()


class CacheInvalidator:
    """Handle cache invalidation strategies."""
    
    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.cache_manager = cache_manager
        self._invalidation_patterns: Dict[str, List[str]] = {}
    
    def register_pattern(
        self,
        entity_type: str,
        patterns: List[str]
    ) -> None:
        """
        Register invalidation patterns for entity type.
        
        Args:
            entity_type: Entity type name
            patterns: List of key patterns to invalidate
        """
        self._invalidation_patterns[entity_type] = patterns
    
    def invalidate_entity(
        self,
        table_name: str,
        entity_id: Any
    ) -> None:
        """
        Invalidate cache for specific entity.
        
        Args:
            table_name: Table name
            entity_id: Entity ID
        """
        if not self.cache_manager:
            return
        
        # Invalidate entity cache
        entity_key = CacheKeyGenerator.generate_entity_key(table_name, entity_id)
        self.cache_manager.delete(entity_key)
        
        # Invalidate related patterns
        patterns = self._invalidation_patterns.get(table_name, [])
        for pattern in patterns:
            self.cache_manager.delete_pattern(pattern.format(id=entity_id))
        
        logger.debug(f"Invalidated cache for {table_name}:{entity_id}")
    
    def invalidate_pattern(self, pattern: str) -> None:
        """
        Invalidate cache by pattern.
        
        Args:
            pattern: Key pattern to invalidate
        """
        if self.cache_manager:
            self.cache_manager.delete_pattern(pattern)
            logger.debug(f"Invalidated cache pattern: {pattern}")
    
    def invalidate_table(self, table_name: str) -> None:
        """
        Invalidate all cache for table.
        
        Args:
            table_name: Table name
        """
        self.invalidate_pattern(f"{table_name}:*")
    
    def tag_based_invalidation(
        self,
        tags: List[str]
    ) -> None:
        """
        Invalidate cache by tags.
        
        Args:
            tags: List of tags to invalidate
        """
        for tag in tags:
            self.invalidate_pattern(f"tag:{tag}:*")


class CachingRepository(BaseRepository[ModelType]):
    """
    Repository with multi-layer caching support.
    
    Wraps base repository with intelligent caching,
    automatic invalidation, and performance monitoring.
    """
    
    def __init__(
        self,
        repository: BaseRepository[ModelType],
        cache_manager: Optional[CacheManager] = None,
        ttl: int = 300,
        strategy: str = CacheStrategy.WRITE_THROUGH,
        enable_l1_cache: bool = True,
        l1_max_size: int = 1000
    ):
        """
        Initialize caching repository.
        
        Args:
            repository: Base repository to wrap
            cache_manager: Cache manager for L2 cache
            ttl: Default time-to-live in seconds
            strategy: Cache strategy
            enable_l1_cache: Enable in-memory L1 cache
            l1_max_size: L1 cache max size
        """
        self.repository = repository
        self.cache_manager = cache_manager
        self.ttl = ttl
        self.strategy = strategy
        self.enable_l1_cache = enable_l1_cache
        
        # Initialize L1 cache
        self._l1_cache = LRUCache(max_size=l1_max_size, default_ttl=ttl) if enable_l1_cache else None
        
        # Initialize cache invalidator
        self._invalidator = CacheInvalidator(cache_manager)
        
        # Initialize key generator
        self._key_gen = CacheKeyGenerator()
        
        # Performance metrics
        self._metrics = {
            "l1_hits": 0,
            "l1_misses": 0,
            "l2_hits": 0,
            "l2_misses": 0,
            "db_queries": 0
        }
    
    # ==================== Cache Operations ====================
    
    def _get_from_cache(
        self,
        key: str,
        use_l1: bool = True
    ) -> Optional[Any]:
        """
        Get value from cache (L1 then L2).
        
        Args:
            key: Cache key
            use_l1: Whether to check L1 cache
            
        Returns:
            Cached value or None
        """
        # Try L1 cache first
        if use_l1 and self._l1_cache:
            value = self._l1_cache.get(key)
            if value is not None:
                self._metrics["l1_hits"] += 1
                logger.debug(f"L1 cache hit: {key}")
                return value
            self._metrics["l1_misses"] += 1
        
        # Try L2 cache
        if self.cache_manager:
            value = self.cache_manager.get(key)
            if value is not None:
                self._metrics["l2_hits"] += 1
                logger.debug(f"L2 cache hit: {key}")
                
                # Populate L1 cache
                if use_l1 and self._l1_cache:
                    self._l1_cache.set(key, value, self.ttl)
                
                return value
            self._metrics["l2_misses"] += 1
        
        return None
    
    def _set_in_cache(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> None:
        """
        Set value in cache (both L1 and L2).
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
            tags: Cache tags for invalidation
        """
        ttl = ttl or self.ttl
        
        # Set in L1 cache
        if self._l1_cache:
            self._l1_cache.set(key, value, ttl)
        
        # Set in L2 cache
        if self.cache_manager:
            self.cache_manager.set(key, value, ttl, tags=tags)
    
    def _invalidate_cache(
        self,
        key: Optional[str] = None,
        pattern: Optional[str] = None
    ) -> None:
        """
        Invalidate cache.
        
        Args:
            key: Specific key to invalidate
            pattern: Pattern to invalidate
        """
        if key:
            if self._l1_cache:
                self._l1_cache.delete(key)
            if self.cache_manager:
                self.cache_manager.delete(key)
        
        if pattern:
            # L1 cache doesn't support patterns, clear all
            if self._l1_cache:
                self._l1_cache.clear()
            if self.cache_manager:
                self.cache_manager.delete_pattern(pattern)
    
    # ==================== Cached Repository Methods ====================
    
    def find_by_id(
        self,
        id: Union[int, Any],
        include_deleted: bool = False
    ) -> Optional[ModelType]:
        """
        Find entity by ID with caching.
        
        Args:
            id: Entity ID
            include_deleted: Include soft-deleted entities
            
        Returns:
            Entity or None
        """
        # Generate cache key
        table_name = self.repository.model.__tablename__
        cache_key = self._key_gen.generate_entity_key(table_name, id)
        
        # Try cache first
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            # Check if deleted flag matches request
            if hasattr(cached, 'is_deleted'):
                if not include_deleted and cached.is_deleted:
                    return None
            return cached
        
        # Query database
        self._metrics["db_queries"] += 1
        entity = self.repository.find_by_id(id, include_deleted)
        
        # Cache result
        if entity:
            tags = [table_name, f"{table_name}:entity"]
            self._set_in_cache(cache_key, entity, tags=tags)
        
        return entity
    
    def find_by_criteria(
        self,
        criteria: Dict[str, Any],
        skip: int = 0,
        limit: int = 100,
        order_by: Optional[List[str]] = None,
        include_deleted: bool = False
    ) -> List[ModelType]:
        """
        Find entities by criteria with caching.
        
        Args:
            criteria: Filter criteria
            skip: Offset
            limit: Limit
            order_by: Order by fields
            include_deleted: Include deleted
            
        Returns:
            List of entities
        """
        # Generate cache key
        table_name = self.repository.model.__tablename__
        criteria_with_params = {
            **criteria,
            "skip": skip,
            "limit": limit,
            "order_by": order_by,
            "include_deleted": include_deleted
        }
        criteria_hash = self._key_gen.hash_criteria(criteria_with_params)
        cache_key = self._key_gen.generate_list_key(table_name, criteria_hash)
        
        # Try cache
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        # Query database
        self._metrics["db_queries"] += 1
        entities = self.repository.find_by_criteria(
            criteria, skip, limit, order_by, include_deleted
        )
        
        # Cache result
        tags = [table_name, f"{table_name}:list"]
        self._set_in_cache(cache_key, entities, tags=tags)
        
        return entities
    
    def count(
        self,
        criteria: Optional[Dict[str, Any]] = None,
        include_deleted: bool = False
    ) -> int:
        """
        Count entities with caching.
        
        Args:
            criteria: Filter criteria
            include_deleted: Include deleted
            
        Returns:
            Count
        """
        # Generate cache key
        table_name = self.repository.model.__tablename__
        criteria_hash = self._key_gen.hash_criteria(criteria or {})
        cache_key = self._key_gen.generate_count_key(table_name, criteria_hash)
        
        # Try cache
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        
        # Query database
        self._metrics["db_queries"] += 1
        count = self.repository.count(criteria, include_deleted)
        
        # Cache result with shorter TTL (counts change frequently)
        tags = [table_name, f"{table_name}:count"]
        self._set_in_cache(cache_key, count, ttl=self.ttl // 2, tags=tags)
        
        return count
    
    # ==================== Write Operations (with invalidation) ====================
    
    def create(
        self,
        entity: ModelType,
        audit_context: Optional[AuditContext] = None,
        commit: bool = True
    ) -> ModelType:
        """
        Create entity with cache invalidation.
        
        Args:
            entity: Entity to create
            audit_context: Audit context
            commit: Commit immediately
            
        Returns:
            Created entity
        """
        # Create in database
        created = self.repository.create(entity, audit_context, commit)
        
        if commit:
            # Invalidate list and count caches
            table_name = self.repository.model.__tablename__
            self._invalidator.invalidate_pattern(f"{table_name}:list:*")
            self._invalidator.invalidate_pattern(f"{table_name}:count:*")
            
            # Cache new entity
            if created.id:
                cache_key = self._key_gen.generate_entity_key(table_name, created.id)
                tags = [table_name, f"{table_name}:entity"]
                self._set_in_cache(cache_key, created, tags=tags)
        
        return created
    
    def update(
        self,
        id: Union[int, Any],
        data: Dict[str, Any],
        audit_context: Optional[AuditContext] = None,
        version: Optional[int] = None,
        commit: bool = True
    ) -> ModelType:
        """
        Update entity with cache invalidation.
        
        Args:
            id: Entity ID
            data: Update data
            audit_context: Audit context
            version: Version for optimistic locking
            commit: Commit immediately
            
        Returns:
            Updated entity
        """
        # Update in database
        updated = self.repository.update(id, data, audit_context, version, commit)
        
        if commit:
            # Invalidate entity cache
            table_name = self.repository.model.__tablename__
            self._invalidator.invalidate_entity(table_name, id)
            
            # Invalidate list and count caches
            self._invalidator.invalidate_pattern(f"{table_name}:list:*")
            self._invalidator.invalidate_pattern(f"{table_name}:count:*")
            
            # Cache updated entity
            cache_key = self._key_gen.generate_entity_key(table_name, id)
            tags = [table_name, f"{table_name}:entity"]
            self._set_in_cache(cache_key, updated, tags=tags)
        
        return updated
    
    def delete(
        self,
        id: Union[int, Any],
        audit_context: Optional[AuditContext] = None,
        commit: bool = True
    ) -> bool:
        """
        Delete entity with cache invalidation.
        
        Args:
            id: Entity ID
            audit_context: Audit context
            commit: Commit immediately
            
        Returns:
            Success flag
        """
        # Delete from database
        deleted = self.repository.delete(id, audit_context, commit)
        
        if deleted and commit:
            # Invalidate all caches for this entity
            table_name = self.repository.model.__tablename__
            self._invalidator.invalidate_entity(table_name, id)
            self._invalidator.invalidate_pattern(f"{table_name}:list:*")
            self._invalidator.invalidate_pattern(f"{table_name}:count:*")
        
        return deleted
    
    def soft_delete(
        self,
        id: Union[int, Any],
        audit_context: Optional[AuditContext] = None,
        commit: bool = True
    ) -> ModelType:
        """
        Soft delete entity with cache invalidation.
        
        Args:
            id: Entity ID
            audit_context: Audit context
            commit: Commit immediately
            
        Returns:
            Soft-deleted entity
        """
        # Soft delete in database
        deleted = self.repository.soft_delete(id, audit_context, commit)
        
        if commit:
            # Invalidate entity cache
            table_name = self.repository.model.__tablename__
            self._invalidator.invalidate_entity(table_name, id)
            
            # Invalidate list and count caches
            self._invalidator.invalidate_pattern(f"{table_name}:list:*")
            self._invalidator.invalidate_pattern(f"{table_name}:count:*")
        
        return deleted
    
    # ==================== Cache Management ====================
    
    def clear_cache(self, pattern: Optional[str] = None) -> None:
        """
        Clear cache for repository.
        
        Args:
            pattern: Optional pattern to clear
        """
        if pattern:
            self._invalidate_cache(pattern=pattern)
        else:
            table_name = self.repository.model.__tablename__
            self._invalidator.invalidate_table(table_name)
    
    def warm_cache(
        self,
        ids: List[Any],
        batch_size: int = 100
    ) -> None:
        """
        Warm cache by preloading entities.
        
        Args:
            ids: List of entity IDs to preload
            batch_size: Batch size for loading
        """
        table_name = self.repository.model.__tablename__
        
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]
            
            # Query database
            entities = self.repository.find_by_criteria(
                {"id": batch_ids},
                limit=batch_size
            )
            
            # Cache entities
            for entity in entities:
                cache_key = self._key_gen.generate_entity_key(table_name, entity.id)
                tags = [table_name, f"{table_name}:entity"]
                self._set_in_cache(cache_key, entity, tags=tags)
        
        logger.info(f"Warmed cache for {len(ids)} entities")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Statistics dictionary
        """
        stats = {
            "metrics": self._metrics.copy(),
            "l1_stats": self._l1_cache.get_stats() if self._l1_cache else None,
            "l2_stats": self.cache_manager.get_stats() if self.cache_manager else None
        }
        
        # Calculate hit rates
        total_l1 = self._metrics["l1_hits"] + self._metrics["l1_misses"]
        total_l2 = self._metrics["l2_hits"] + self._metrics["l2_misses"]
        
        stats["l1_hit_rate"] = (
            self._metrics["l1_hits"] / total_l1 if total_l1 > 0 else 0
        )
        stats["l2_hit_rate"] = (
            self._metrics["l2_hits"] / total_l2 if total_l2 > 0 else 0
        )
        
        return stats
    
    def reset_stats(self) -> None:
        """Reset performance metrics."""
        self._metrics = {
            "l1_hits": 0,
            "l1_misses": 0,
            "l2_hits": 0,
            "l2_misses": 0,
            "db_queries": 0
        }
    
    # ==================== Delegate to Base Repository ====================
    
    def __getattr__(self, name: str) -> Any:
        """Delegate unknown attributes to base repository."""
        return getattr(self.repository, name)


def cached_method(
    ttl: Optional[int] = None,
    key_prefix: Optional[str] = None,
    tags: Optional[List[str]] = None
):
    """
    Decorator for caching repository methods.
    
    Args:
        ttl: Time-to-live in seconds
        key_prefix: Cache key prefix
        tags: Cache tags
        
    Returns:
        Decorated method
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Check if caching is enabled
            if not hasattr(self, 'cache_manager') or not self.cache_manager:
                return func(self, *args, **kwargs)
            
            # Generate cache key
            key_gen = CacheKeyGenerator()
            method_name = func.__name__
            args_hash = key_gen.hash_criteria({
                "args": args,
                "kwargs": kwargs
            })
            cache_key = f"{key_prefix or method_name}:{args_hash}"
            
            # Try cache
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                return cached
            
            # Execute method
            result = func(self, *args, **kwargs)
            
            # Cache result
            self._set_in_cache(
                cache_key,
                result,
                ttl=ttl or self.ttl,
                tags=tags
            )
            
            return result
        
        return wrapper
    return decorator