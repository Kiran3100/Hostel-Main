# cache_service.py

from typing import Dict, Any, Optional, Union, List, Set, TypeVar, Generic
from datetime import datetime, timedelta
import json
import asyncio
import logging
from enum import Enum
import hashlib
from dataclasses import dataclass
import pickle
from functools import wraps

T = TypeVar('T')

class CacheStrategy(Enum):
    WRITE_THROUGH = "WRITE_THROUGH"
    WRITE_BEHIND = "WRITE_BEHIND"
    WRITE_AROUND = "WRITE_AROUND"
    READ_THROUGH = "READ_THROUGH"
    CACHE_ASIDE = "CACHE_ASIDE"

@dataclass
class CacheConfig:
    """Cache configuration settings"""
    strategy: CacheStrategy
    ttl_seconds: int
    max_size: int
    eviction_policy: str
    namespace: str
    serializer: str = "json"
    compression: bool = False
    distributed: bool = False
    sync_interval: int = 300  # seconds

@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with metadata"""
    key: str
    value: T
    created_at: datetime
    expires_at: datetime
    last_accessed: datetime
    access_count: int
    version: int
    metadata: Dict[str, Any]

    def is_expired(self) -> bool:
        """Check if entry is expired"""
        return datetime.utcnow() > self.expires_at

    def update_access(self) -> None:
        """Update access statistics"""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1

class CacheManager:
    """Manages cache operations and lifecycle"""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self._cache: Dict[str, CacheEntry] = {}
        self._write_queue: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        self.logger = logging.getLogger(self.__class__.__name__)

    def _generate_key(self, key: str) -> str:
        """Generate namespaced cache key"""
        return f"{self.config.namespace}:{key}"

    def _serialize(self, value: Any) -> str:
        """Serialize value for storage"""
        if self.config.serializer == "json":
            return json.dumps(value)
        elif self.config.serializer == "pickle":
            return pickle.dumps(value)
        else:
            raise ValueError(f"Unsupported serializer: {self.config.serializer}")

    def _deserialize(self, value: str) -> Any:
        """Deserialize stored value"""
        if self.config.serializer == "json":
            return json.loads(value)
        elif self.config.serializer == "pickle":
            return pickle.loads(value)
        else:
            raise ValueError(f"Unsupported serializer: {self.config.serializer}")

    async def get(
        self,
        key: str,
        default: Optional[T] = None
    ) -> Optional[T]:
        """Get value from cache"""
        cache_key = self._generate_key(key)
        
        async with self._lock:
            entry = self._cache.get(cache_key)
            
            if not entry:
                return default
            
            if entry.is_expired():
                await self.delete(key)
                return default
            
            entry.update_access()
            return entry.value

    async def set(
        self,
        key: str,
        value: T,
        ttl: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Set value in cache"""
        cache_key = self._generate_key(key)
        ttl = ttl or self.config.ttl_seconds
        
        entry = CacheEntry(
            key=cache_key,
            value=value,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=ttl),
            last_accessed=datetime.utcnow(),
            access_count=0,
            version=1,
            metadata=metadata or {}
        )
        
        async with self._lock:
            self._cache[cache_key] = entry
            
            if self.config.strategy == CacheStrategy.WRITE_BEHIND:
                await self._write_queue.put(('set', cache_key, value))

    async def delete(self, key: str) -> None:
        """Delete value from cache"""
        cache_key = self._generate_key(key)
        
        async with self._lock:
            self._cache.pop(cache_key, None)
            
            if self.config.strategy == CacheStrategy.WRITE_BEHIND:
                await self._write_queue.put(('delete', cache_key, None))

    async def clear(self) -> None:
        """Clear all cache entries"""
        async with self._lock:
            self._cache.clear()

    async def get_many(
        self,
        keys: List[str]
    ) -> Dict[str, Optional[T]]:
        """Get multiple values from cache"""
        return {
            key: await self.get(key)
            for key in keys
        }

    async def set_many(
        self,
        items: Dict[str, T],
        ttl: Optional[int] = None
    ) -> None:
        """Set multiple values in cache"""
        for key, value in items.items():
            await self.set(key, value, ttl)

    async def delete_many(self, keys: List[str]) -> None:
        """Delete multiple values from cache"""
        for key in keys:
            await self.delete(key)

class CacheInvalidator:
    """Handles cache invalidation strategies"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        self._invalidation_patterns: Dict[str, Set[str]] = {}

    def add_invalidation_pattern(
        self,
        pattern: str,
        related_keys: Set[str]
    ) -> None:
        """Add invalidation pattern"""
        self._invalidation_patterns[pattern] = related_keys
        self.logger.info(f"Added invalidation pattern: {pattern}")

    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate keys matching pattern"""
        related_keys = self._invalidation_patterns.get(pattern, set())
        await self.cache_manager.delete_many(list(related_keys))
        self.logger.info(f"Invalidated pattern: {pattern}")

    async def invalidate_key(self, key: str) -> None:
        """Invalidate specific key"""
        await self.cache_manager.delete(key)
        self.logger.info(f"Invalidated key: {key}")

    async def invalidate_prefix(self, prefix: str) -> None:
        """Invalidate all keys with prefix"""
        keys_to_delete = [
            key for key in self.cache_manager._cache.keys()
            if key.startswith(prefix)
        ]
        await self.cache_manager.delete_many(keys_to_delete)
        self.logger.info(f"Invalidated prefix: {prefix}")

class CacheWarmer:
    """Handles cache warming and preloading"""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        self._warm_up_functions: Dict[str, callable] = {}

    def register_warm_up(
        self,
        key_pattern: str,
        warm_up_func: callable
    ) -> None:
        """Register warm-up function"""
        self._warm_up_functions[key_pattern] = warm_up_func
        self.logger.info(f"Registered warm-up for: {key_pattern}")

    async def warm_up(self, key_pattern: str) -> None:
        """Execute warm-up for pattern"""
        warm_up_func = self._warm_up_functions.get(key_pattern)
        if not warm_up_func:
            self.logger.warning(f"No warm-up function for: {key_pattern}")
            return

        try:
            data = await warm_up_func()
            if isinstance(data, dict):
                await self.cache_manager.set_many(data)
            else:
                await self.cache_manager.set(key_pattern, data)
            self.logger.info(f"Warmed up cache for: {key_pattern}")
        except Exception as e:
            self.logger.error(f"Warm-up failed for {key_pattern}: {str(e)}")

    async def warm_up_all(self) -> None:
        """Execute all warm-up functions"""
        for pattern in self._warm_up_functions:
            await self.warm_up(pattern)

class CacheMetrics:
    """Tracks cache performance metrics"""
    
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.total_requests = 0
        self.evictions = 0
        self.size = 0
        self.logger = logging.getLogger(self.__class__.__name__)

    def record_hit(self) -> None:
        """Record cache hit"""
        self.hits += 1
        self.total_requests += 1

    def record_miss(self) -> None:
        """Record cache miss"""
        self.misses += 1
        self.total_requests += 1

    def record_eviction(self) -> None:
        """Record cache eviction"""
        self.evictions += 1

    def update_size(self, size: int) -> None:
        """Update cache size"""
        self.size = size

    def get_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics"""
        return {
            'hits': self.hits,
            'misses': self.misses,
            'total_requests': self.total_requests,
            'hit_rate': self.get_hit_rate(),
            'evictions': self.evictions,
            'size': self.size
        }

class CacheService:
    """Main cache service interface"""
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig(
            strategy=CacheStrategy.WRITE_THROUGH,
            ttl_seconds=3600,
            max_size=1000,
            eviction_policy="LRU",
            namespace="default"
        )
        self.manager = CacheManager(self.config)
        self.invalidator = CacheInvalidator(self.manager)
        self.warmer = CacheWarmer(self.manager)
        self.metrics = CacheMetrics()
        self.logger = logging.getLogger(self.__class__.__name__)

    async def get(
        self,
        key: str,
        default: Optional[T] = None
    ) -> Optional[T]:
        """Get value from cache"""
        try:
            value = await self.manager.get(key, default)
            if value is not None:
                self.metrics.record_hit()
            else:
                self.metrics.record_miss()
            return value
        except Exception as e:
            self.logger.error(f"Cache get error: {str(e)}")
            return default

    async def set(
        self,
        key: str,
        value: T,
        ttl: Optional[int] = None
    ) -> None:
        """Set value in cache"""
        try:
            await self.manager.set(key, value, ttl)
            self.metrics.update_size(len(self.manager._cache))
        except Exception as e:
            self.logger.error(f"Cache set error: {str(e)}")

    async def delete(self, key: str) -> None:
        """Delete value from cache"""
        try:
            await self.manager.delete(key)
            self.metrics.update_size(len(self.manager._cache))
        except Exception as e:
            self.logger.error(f"Cache delete error: {str(e)}")

    async def clear(self) -> None:
        """Clear all cache entries"""
        try:
            await self.manager.clear()
            self.metrics.update_size(0)
        except Exception as e:
            self.logger.error(f"Cache clear error: {str(e)}")

    def cached(
        self,
        key_prefix: str,
        ttl: Optional[int] = None
    ):
        """Decorator for caching function results"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                key_parts = [key_prefix]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)
                
                # Try to get from cache
                cached_value = await self.get(cache_key)
                if cached_value is not None:
                    return cached_value
                
                # Execute function and cache result
                result = await func(*args, **kwargs)
                await self.set(cache_key, result, ttl)
                return result
            return wrapper
        return decorator

    async def warm_up(self) -> None:
        """Warm up cache"""
        await self.warmer.warm_up_all()

    def get_metrics(self) -> Dict[str, Any]:
        """Get cache metrics"""
        return self.metrics.get_metrics()

    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate by pattern"""
        await self.invalidator.invalidate_pattern(pattern)

    async def health_check(self) -> bool:
        """Check cache health"""
        try:
            test_key = "__health_check__"
            test_value = "ok"
            await self.set(test_key, test_value)
            value = await self.get(test_key)
            await self.delete(test_key)
            return value == test_value
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return False