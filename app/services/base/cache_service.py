"""
Cache service with Redis backend for high-performance data caching.
"""

from typing import Optional, Callable, Any, Dict, List, TypeVar, Generic
import json
import functools
import hashlib
from datetime import timedelta

from app.core1.logging import get_logger
from app.config.redis import RedisManager


T = TypeVar('T')


class CacheService:
    """
    JSON-based cache service with:
    - Namespaced keys
    - TTL support
    - Bulk operations
    - Cache warming
    - Invalidation patterns
    """

    def __init__(
        self,
        redis: RedisManager,
        namespace: str = "svc",
        default_ttl: int = 300,
    ):
        """
        Initialize cache service.
        
        Args:
            redis: Redis manager instance
            namespace: Key namespace prefix
            default_ttl: Default TTL in seconds
        """
        self.redis = redis
        self.namespace = namespace
        self.default_ttl = default_ttl
        self._logger = get_logger(self.__class__.__name__)

    # -------------------------------------------------------------------------
    # Core Cache Operations
    # -------------------------------------------------------------------------

    def _key(self, key: str) -> str:
        """
        Build namespaced cache key.
        
        Args:
            key: Raw key
            
        Returns:
            Namespaced key
        """
        return f"{self.namespace}:{key}"

    def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            default: Default value if not found
            
        Returns:
            Cached value or default
        """
        try:
            raw = self.redis.get(self._key(key))
            if raw is None:
                self._logger.debug(f"Cache miss: {key}")
                return default
            
            self._logger.debug(f"Cache hit: {key}")
            return json.loads(raw)
            
        except json.JSONDecodeError as e:
            self._logger.warning(f"Failed to decode cached value for {key}: {e}")
            return default
        except Exception as e:
            self._logger.error(f"Cache get error for {key}: {e}")
            return default

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl_seconds: Time-to-live in seconds (None for no expiry)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            payload = json.dumps(value, default=str)
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
            
            self.redis.set(self._key(key), payload, ex=ttl)
            
            self._logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
            return True
            
        except (TypeError, ValueError) as e:
            self._logger.error(f"Failed to serialize value for {key}: {e}")
            return False
        except Exception as e:
            self._logger.error(f"Cache set error for {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            result = self.redis.delete(self._key(key))
            self._logger.debug(f"Cache delete: {key}")
            return bool(result)
        except Exception as e:
            self._logger.error(f"Cache delete error for {key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if exists, False otherwise
        """
        try:
            return bool(self.redis.exists(self._key(key)))
        except Exception as e:
            self._logger.error(f"Cache exists error for {key}: {e}")
            return False

    def get_ttl(self, key: str) -> Optional[int]:
        """
        Get remaining TTL for a key.
        
        Args:
            key: Cache key
            
        Returns:
            Remaining TTL in seconds, or None if no expiry/not found
        """
        try:
            ttl = self.redis.ttl(self._key(key))
            return ttl if ttl > 0 else None
        except Exception as e:
            self._logger.error(f"Cache TTL error for {key}: {e}")
            return None

    def extend_ttl(self, key: str, additional_seconds: int) -> bool:
        """
        Extend TTL for an existing key.
        
        Args:
            key: Cache key
            additional_seconds: Seconds to add to TTL
            
        Returns:
            True if successful
        """
        try:
            current_ttl = self.get_ttl(key)
            if current_ttl is None:
                return False
            
            new_ttl = current_ttl + additional_seconds
            return bool(self.redis.expire(self._key(key), new_ttl))
        except Exception as e:
            self._logger.error(f"Cache extend TTL error for {key}: {e}")
            return False

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple values from cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dictionary of key->value for found items
        """
        result = {}
        
        try:
            namespaced_keys = [self._key(k) for k in keys]
            values = self.redis.mget(namespaced_keys)
            
            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        result[key] = json.loads(value)
                    except json.JSONDecodeError:
                        self._logger.warning(f"Failed to decode cached value for {key}")
            
            self._logger.debug(f"Cache get_many: {len(result)}/{len(keys)} hits")
            return result
            
        except Exception as e:
            self._logger.error(f"Cache get_many error: {e}")
            return {}

    def set_many(
        self,
        items: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> int:
        """
        Set multiple values in cache.
        
        Args:
            items: Dictionary of key->value to cache
            ttl_seconds: TTL for all items
            
        Returns:
            Number of successfully cached items
        """
        success_count = 0
        
        for key, value in items.items():
            if self.set(key, value, ttl_seconds):
                success_count += 1
        
        self._logger.debug(f"Cache set_many: {success_count}/{len(items)} successful")
        return success_count

    def delete_many(self, keys: List[str]) -> int:
        """
        Delete multiple keys from cache.
        
        Args:
            keys: List of cache keys to delete
            
        Returns:
            Number of deleted keys
        """
        try:
            if not keys:
                return 0
            
            namespaced_keys = [self._key(k) for k in keys]
            deleted = self.redis.delete(*namespaced_keys)
            
            self._logger.debug(f"Cache delete_many: {deleted}/{len(keys)} deleted")
            return deleted
            
        except Exception as e:
            self._logger.error(f"Cache delete_many error: {e}")
            return 0

    # -------------------------------------------------------------------------
    # Pattern-based Operations
    # -------------------------------------------------------------------------

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.
        
        Args:
            pattern: Key pattern (supports wildcards)
            
        Returns:
            Number of deleted keys
        """
        try:
            full_pattern = self._key(pattern)
            keys = self.redis.keys(full_pattern)
            
            if not keys:
                return 0
            
            deleted = self.redis.delete(*keys)
            self._logger.info(f"Cache pattern delete: {deleted} keys for pattern '{pattern}'")
            return deleted
            
        except Exception as e:
            self._logger.error(f"Cache delete_pattern error: {e}")
            return 0

    def invalidate_namespace(self, sub_namespace: str) -> int:
        """
        Invalidate all keys under a sub-namespace.
        
        Args:
            sub_namespace: Sub-namespace to invalidate
            
        Returns:
            Number of invalidated keys
        """
        pattern = f"{sub_namespace}:*"
        return self.delete_pattern(pattern)

    # -------------------------------------------------------------------------
    # Decorator Support
    # -------------------------------------------------------------------------

    def cached(
        self,
        key_builder: Optional[Callable[..., str]] = None,
        ttl_seconds: Optional[int] = None,
        key_prefix: str = "",
    ) -> Callable:
        """
        Decorator to cache function results.
        
        Args:
            key_builder: Function to build cache key from arguments
            ttl_seconds: Cache TTL
            key_prefix: Prefix for cache key
            
        Returns:
            Decorated function
            
        Example:
            @cache.cached(key_builder=lambda user_id: f"user:{user_id}", ttl_seconds=600)
            def get_user(user_id):
                return fetch_user_from_db(user_id)
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Build cache key
                if key_builder:
                    cache_key = key_builder(*args, **kwargs)
                else:
                    cache_key = self._auto_key(func, args, kwargs)
                
                if key_prefix:
                    cache_key = f"{key_prefix}:{cache_key}"
                
                # Try to get from cache
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    self._logger.debug(f"Cache decorator hit: {cache_key}")
                    return cached_value
                
                # Execute function
                result = func(*args, **kwargs)
                
                # Cache result
                self.set(cache_key, result, ttl_seconds)
                self._logger.debug(f"Cache decorator miss: {cache_key}")
                
                return result
            
            return wrapper
        return decorator

    def _auto_key(
        self,
        func: Callable,
        args: tuple,
        kwargs: Dict[str, Any],
    ) -> str:
        """
        Automatically generate cache key from function signature.
        
        Args:
            func: Function being cached
            args: Positional arguments
            kwargs: Keyword arguments
            
        Returns:
            Generated cache key
        """
        key_parts = [func.__module__, func.__name__]
        
        # Add args
        for arg in args:
            key_parts.append(str(arg))
        
        # Add sorted kwargs
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        
        # Hash if too long
        key = ":".join(key_parts)
        if len(key) > 200:
            key_hash = hashlib.md5(key.encode()).hexdigest()
            return f"{func.__name__}:{key_hash}"
        
        return key

    # -------------------------------------------------------------------------
    # Cache Warming & Management
    # -------------------------------------------------------------------------

    def warm(
        self,
        data_loader: Callable[[], Dict[str, Any]],
        ttl_seconds: Optional[int] = None,
    ) -> int:
        """
        Warm cache with pre-loaded data.
        
        Args:
            data_loader: Function that returns dict of key->value
            ttl_seconds: TTL for warmed data
            
        Returns:
            Number of items cached
        """
        try:
            data = data_loader()
            count = self.set_many(data, ttl_seconds)
            self._logger.info(f"Cache warmed: {count} items")
            return count
        except Exception as e:
            self._logger.error(f"Cache warm error: {e}")
            return 0

    def clear_all(self) -> bool:
        """
        Clear all cached data in this namespace.
        
        Returns:
            True if successful
        """
        try:
            pattern = self._key("*")
            keys = self.redis.keys(pattern)
            
            if keys:
                self.redis.delete(*keys)
                self._logger.warning(f"Cache cleared: {len(keys)} keys in namespace '{self.namespace}'")
            
            return True
        except Exception as e:
            self._logger.error(f"Cache clear_all error: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        try:
            pattern = self._key("*")
            keys = self.redis.keys(pattern)
            
            total_size = 0
            for key in keys:
                try:
                    total_size += len(self.redis.get(key) or b'')
                except:
                    pass
            
            return {
                "namespace": self.namespace,
                "total_keys": len(keys),
                "total_size_bytes": total_size,
                "default_ttl": self.default_ttl,
            }
        except Exception as e:
            self._logger.error(f"Cache stats error: {e}")
            return {}