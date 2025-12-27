"""
Caching System

Comprehensive caching utilities with Redis backend support,
cache decorators, and intelligent cache invalidation strategies.
"""

import json
import asyncio
import hashlib
import pickle
from typing import Any, Dict, List, Optional, Union, Callable
from functools import wraps
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from .config import settings
from .exceptions import CacheError
from .logging import get_logger

logger = get_logger(__name__)


class CacheBackend:
    """Abstract cache backend interface"""
    
    async def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        raise NotImplementedError
    
    async def delete(self, key: str) -> bool:
        raise NotImplementedError
    
    async def exists(self, key: str) -> bool:
        raise NotImplementedError
    
    async def clear(self, pattern: str = "*") -> int:
        raise NotImplementedError
    
    async def close(self):
        pass


class RedisBackend(CacheBackend):
    """Redis cache backend implementation"""
    
    def __init__(self):
        self.pool: Optional[ConnectionPool] = None
        self.redis: Optional[redis.Redis] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize Redis connection"""
        if self._initialized:
            return
        
        try:
            self.pool = ConnectionPool.from_url(
                settings.redis.redis_url,
                max_connections=settings.redis.REDIS_MAX_CONNECTIONS,
                retry_on_timeout=settings.redis.REDIS_RETRY_ON_TIMEOUT,
                socket_connect_timeout=settings.redis.REDIS_SOCKET_CONNECT_TIMEOUT,
                socket_timeout=settings.redis.REDIS_SOCKET_TIMEOUT,
                decode_responses=True
            )
            
            self.redis = redis.Redis(connection_pool=self.pool)
            
            # Test connection
            await self.redis.ping()
            self._initialized = True
            
            logger.info("Redis cache backend initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis backend: {str(e)}")
            raise CacheError(f"Cache initialization failed: {str(e)}")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self._initialized:
            await self.initialize()
        
        try:
            value = await self.redis.get(key)
            if value is None:
                return None
            
            # Try to deserialize JSON first, then pickle
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                try:
                    return pickle.loads(value.encode() if isinstance(value, str) else value)
                except (pickle.UnpicklingError, TypeError):
                    return value
                    
        except Exception as e:
            logger.error(f"Cache get failed for key '{key}': {str(e)}")
            return None
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set value in cache"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Serialize value
            if isinstance(value, (dict, list, tuple)):
                serialized_value = json.dumps(value, default=str)
            elif isinstance(value, (str, int, float, bool)):
                serialized_value = json.dumps(value)
            else:
                serialized_value = pickle.dumps(value)
            
            # Set with expiration
            if expire:
                await self.redis.setex(key, expire, serialized_value)
            else:
                await self.redis.set(key, serialized_value)
            
            return True
            
        except Exception as e:
            logger.error(f"Cache set failed for key '{key}': {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self._initialized:
            await self.initialize()
        
        try:
            result = await self.redis.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Cache delete failed for key '{key}': {str(e)}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self._initialized:
            await self.initialize()
        
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists check failed for key '{key}': {str(e)}")
            return False
    
    async def clear(self, pattern: str = "*") -> int:
        """Clear cache keys matching pattern"""
        if not self._initialized:
            await self.initialize()
        
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache clear failed for pattern '{pattern}': {str(e)}")
            return 0
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment numeric value in cache"""
        if not self._initialized:
            await self.initialize()
        
        try:
            return await self.redis.incr(key, amount)
        except Exception as e:
            logger.error(f"Cache increment failed for key '{key}': {str(e)}")
            raise CacheError(f"Cache increment failed: {str(e)}")
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration time for key"""
        if not self._initialized:
            await self.initialize()
        
        try:
            return await self.redis.expire(key, seconds)
        except Exception as e:
            logger.error(f"Cache expire failed for key '{key}': {str(e)}")
            return False
    
    async def ttl(self, key: str) -> int:
        """Get time to live for key"""
        if not self._initialized:
            await self.initialize()
        
        try:
            return await self.redis.ttl(key)
        except Exception as e:
            logger.error(f"Cache TTL check failed for key '{key}': {str(e)}")
            return -1
    
    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
        if self.pool:
            await self.pool.disconnect()


class InMemoryBackend(CacheBackend):
    """In-memory cache backend for development/testing"""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            
            # Check expiration
            if entry.get("expires") and datetime.utcnow() > entry["expires"]:
                del self._cache[key]
                return None
            
            return entry["value"]
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        async with self._lock:
            expires = None
            if expire:
                expires = datetime.utcnow() + timedelta(seconds=expire)
            
            self._cache[key] = {
                "value": value,
                "expires": expires
            }
            return True
    
    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None
    
    async def clear(self, pattern: str = "*") -> int:
        async with self._lock:
            if pattern == "*":
                count = len(self._cache)
                self._cache.clear()
                return count
            
            # Simple pattern matching (only supports * wildcard)
            import fnmatch
            matching_keys = [
                key for key in self._cache.keys() 
                if fnmatch.fnmatch(key, pattern)
            ]
            
            for key in matching_keys:
                del self._cache[key]
            
            return len(matching_keys)


class CacheManager:
    """Main cache manager with multiple backend support"""
    
    def __init__(self):
        self.backend: Optional[CacheBackend] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize cache backend"""
        if self._initialized:
            return
        
        try:
            if settings.cache.CACHE_BACKEND == "redis":
                self.backend = RedisBackend()
                await self.backend.initialize()
            else:
                self.backend = InMemoryBackend()
            
            self._initialized = True
            logger.info(f"Cache manager initialized with {settings.cache.CACHE_BACKEND} backend")
            
        except Exception as e:
            logger.error(f"Cache manager initialization failed: {str(e)}")
            # Fallback to in-memory cache
            self.backend = InMemoryBackend()
            self._initialized = True
            logger.warning("Falling back to in-memory cache backend")
    
    def _generate_key(self, *parts: str) -> str:
        """Generate cache key from parts"""
        key = ":".join(str(part) for part in parts if part)
        return f"{settings.cache.CACHE_KEY_PREFIX}{key}"
    
    async def get(self, *key_parts: str) -> Optional[Any]:
        """Get value from cache"""
        if not self._initialized:
            await self.initialize()
        
        key = self._generate_key(*key_parts)
        return await self.backend.get(key)
    
    async def set(
        self,
        *key_parts: str,
        value: Any,
        expire: Optional[int] = None
    ) -> bool:
        """Set value in cache"""
        if not self._initialized:
            await self.initialize()
        
        key = self._generate_key(*key_parts)
        expire_time = expire or settings.cache.CACHE_DEFAULT_TIMEOUT
        return await self.backend.set(key, value, expire_time)
    
    async def delete(self, *key_parts: str) -> bool:
        """Delete key from cache"""
        if not self._initialized:
            await self.initialize()
        
        key = self._generate_key(*key_parts)
        return await self.backend.delete(key)
    
    async def exists(self, *key_parts: str) -> bool:
        """Check if key exists"""
        if not self._initialized:
            await self.initialize()
        
        key = self._generate_key(*key_parts)
        return await self.backend.exists(key)
    
    async def clear(self, pattern: str = "*") -> int:
        """Clear cache with pattern"""
        if not self._initialized:
            await self.initialize()
        
        full_pattern = f"{settings.cache.CACHE_KEY_PREFIX}{pattern}"
        return await self.backend.clear(full_pattern)
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache keys matching pattern"""
        return await self.clear(pattern)
    
    async def close(self):
        """Close cache backend"""
        if self.backend:
            await self.backend.close()


# Global cache manager instance
cache_manager = CacheManager()


def cache_key_from_args(*args, **kwargs) -> str:
    """Generate cache key from function arguments"""
    # Create a hash of the arguments
    key_data = {
        "args": args,
        "kwargs": {k: v for k, v in kwargs.items() if not k.startswith('_')}
    }
    
    key_string = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(key_string.encode()).hexdigest()


def cache_result(
    expire_time: Optional[int] = None,
    key_prefix: Optional[str] = None,
    skip_cache: Optional[Callable] = None
):
    """
    Decorator to cache function results.
    
    Args:
        expire_time: Cache expiration time in seconds
        key_prefix: Custom key prefix
        skip_cache: Function to determine if caching should be skipped
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Skip cache if condition is met
            if skip_cache and skip_cache(*args, **kwargs):
                return await func(*args, **kwargs)
            
            # Generate cache key
            func_name = f"{func.__module__}.{func.__name__}"
            if key_prefix:
                func_name = f"{key_prefix}:{func_name}"
            
            arg_hash = cache_key_from_args(*args, **kwargs)
            cache_key = f"func:{func_name}:{arg_hash}"
            
            # Try to get from cache
            try:
                cached_result = await cache_manager.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"Cache hit for key: {cache_key}")
                    return cached_result
            except Exception as e:
                logger.warning(f"Cache get failed: {str(e)}")
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            try:
                cache_expire = expire_time or settings.cache.CACHE_DEFAULT_TIMEOUT
                await cache_manager.set(cache_key, value=result, expire=cache_expire)
                logger.debug(f"Cached result for key: {cache_key}")
            except Exception as e:
                logger.warning(f"Cache set failed: {str(e)}")
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, we'll need to handle differently
            # This is a simplified version
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


async def invalidate_cache(*key_parts: str) -> bool:
    """Convenience function to invalidate cache"""
    try:
        return await cache_manager.delete(*key_parts)
    except Exception as e:
        logger.error(f"Cache invalidation failed: {str(e)}")
        return False


async def clear_cache_pattern(pattern: str) -> int:
    """Convenience function to clear cache pattern"""
    try:
        return await cache_manager.clear(pattern)
    except Exception as e:
        logger.error(f"Cache pattern clear failed: {str(e)}")
        return 0


class CacheStats:
    """Cache statistics tracking"""
    
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.errors = 0
    
    def record_hit(self):
        self.hits += 1
    
    def record_miss(self):
        self.misses += 1
    
    def record_set(self):
        self.sets += 1
    
    def record_delete(self):
        self.deletes += 1
    
    def record_error(self):
        self.errors += 1
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "errors": self.errors,
            "hit_rate": self.hit_rate,
            "total_operations": self.hits + self.misses + self.sets + self.deletes
        }


# Global cache stats
cache_stats = CacheStats()


@asynccontextmanager
async def cache_context():
    """Context manager for cache operations"""
    try:
        await cache_manager.initialize()
        yield cache_manager
    finally:
        await cache_manager.close()


# Export main functions and classes
__all__ = [
    "CacheBackend",
    "RedisBackend", 
    "InMemoryBackend",
    "CacheManager",
    "CacheStats",
    "cache_manager",
    "cache_stats",
    "cache_result",
    "invalidate_cache",
    "clear_cache_pattern",
    "cache_context",
    "CacheError"
]