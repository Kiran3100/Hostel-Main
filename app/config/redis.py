"""
Redis/Cache configuration for the hostel management system.
Provides Redis client management and connection pooling.
"""

from typing import Optional, Any, Dict, Generator, List
import time
import json
import redis
from redis import Redis
from redis.connection import ConnectionPool

from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)

# Create Redis connection pool
redis_pool = ConnectionPool(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    password=settings.REDIS_PASSWORD,
    max_connections=settings.REDIS_POOL_SIZE,
    decode_responses=True  # Auto-decode Redis responses to strings
)

def get_redis_client() -> Generator[Redis, None, None]:
    """Get Redis client with connection pooling"""
    client = Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        # No need to close - connection returns to pool
        pass

class RedisManager:
    """Redis manager for advanced operations"""
    
    def __init__(self, client: Redis = None):
        self.client = client or Redis(connection_pool=redis_pool)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value with optional expiration"""
        try:
            # Serialize complex objects
            if not isinstance(value, (str, int, float, bool)):
                value = json.dumps(value)
                
            return self.client.set(key, value, ex=ttl)
        except Exception as e:
            logger.error(f"Redis set error: {str(e)}")
            return False
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value with deserialization support"""
        try:
            value = self.client.get(key)
            
            if value is None:
                return default
            
            # Try to deserialize JSON
            try:
                return json.loads(value)
            except (TypeError, json.JSONDecodeError):
                return value
                
        except Exception as e:
            logger.error(f"Redis get error: {str(e)}")
            return default
    
    async def delete(self, key: str) -> bool:
        """Delete key"""
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            logger.error(f"Redis delete error: {str(e)}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern"""
        try:
            keys = self.client.keys(pattern)
            if not keys:
                return 0
            
            return self.client.delete(*keys)
        except Exception as e:
            logger.error(f"Redis delete_pattern error: {str(e)}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            return bool(self.client.exists(key))
        except Exception as e:
            logger.error(f"Redis exists error: {str(e)}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment key by amount"""
        try:
            return self.client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Redis increment error: {str(e)}")
            return 0
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set key expiration"""
        try:
            return bool(self.client.expire(key, ttl))
        except Exception as e:
            logger.error(f"Redis expire error: {str(e)}")
            return False
    
    async def publish(self, channel: str, message: Any) -> int:
        """Publish message to channel"""
        try:
            # Serialize complex objects
            if not isinstance(message, (str, int, float, bool)):
                message = json.dumps(message)
                
            return self.client.publish(channel, message)
        except Exception as e:
            logger.error(f"Redis publish error: {str(e)}")
            return 0
    
    def get_pubsub(self) -> redis.client.PubSub:
        """Get PubSub object for subscriptions"""
        return self.client.pubsub()

class RedisHealthCheck:
    """Redis health check utilities"""
    
    @staticmethod
    async def check_redis_connection() -> Dict[str, Any]:
        """Check Redis connection health"""
        client = Redis(connection_pool=redis_pool)
        start_time = time.time()
        
        try:
            # Simple ping-pong check
            pong = client.ping()
            is_connected = pong is True
            error_message = None
        except Exception as e:
            is_connected = False
            error_message = str(e)
        
        response_time = (time.time() - start_time) * 1000  # in milliseconds
        
        return {
            "is_connected": is_connected,
            "response_time_ms": response_time,
            "error": error_message,
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "db": settings.REDIS_DB,
            "pool_size": settings.REDIS_POOL_SIZE
        }

class RateLimiter:
    """Rate limiter using Redis"""
    
    def __init__(self, redis_client: Redis = None):
        self.redis = redis_client or Redis(connection_pool=redis_pool)
    
    async def check_rate_limit(
        self, 
        key: str, 
        limit: int, 
        window_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Check if rate limit is exceeded for key
        Returns dict with is_allowed, remaining, reset_time
        """
        current_time = int(time.time())
        window_key = f"{key}:{current_time // window_seconds}"
        
        # Get current count
        count = self.redis.get(window_key)
        count = int(count) if count else 0
        
        # Check if limit exceeded
        is_allowed = count < limit
        
        # Calculate reset time
        reset_time = (current_time // window_seconds + 1) * window_seconds
        
        # Increment counter if allowed
        if is_allowed:
            self.redis.incr(window_key)
            # Set expiration if key is new
            if count == 0:
                self.redis.expire(window_key, window_seconds * 2)  # 2x window for safety
        
        return {
            "is_allowed": is_allowed,
            "current": count + (1 if is_allowed else 0),
            "remaining": max(0, limit - count - (1 if is_allowed else 0)),
            "limit": limit,
            "reset_at": reset_time,
            "window_seconds": window_seconds
        }

class CacheService:
    """Caching service with multi-level support"""
    
    def __init__(self, redis_client: Redis = None):
        self.redis = redis_client or Redis(connection_pool=redis_pool)
        self.local_cache = {}
        self.local_cache_ttl = {}
    
    async def get(self, key: str, use_local: bool = True) -> Any:
        """Get from cache, checking local first if enabled"""
        if use_local:
            # Check local cache first
            if key in self.local_cache:
                # Check if expired
                if key in self.local_cache_ttl:
                    if self.local_cache_ttl[key] > time.time():
                        return self.local_cache[key]
                    else:
                        # Expired, remove from local cache
                        del self.local_cache[key]
                        del self.local_cache_ttl[key]
                else:
                    # No TTL, return from local cache
                    return self.local_cache[key]
        
        # Get from Redis
        redis_manager = RedisManager(self.redis)
        value = await redis_manager.get(key)
        
        # Update local cache if found
        if value is not None and use_local:
            self.local_cache[key] = value
            
            # Check if TTL exists in Redis
            ttl = self.redis.ttl(key)
            if ttl > 0:
                self.local_cache_ttl[key] = time.time() + ttl
        
        return value
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, use_local: bool = True) -> bool:
        """Set in cache (Redis and local if enabled)"""
        # Set in Redis
        redis_manager = RedisManager(self.redis)
        redis_result = await redis_manager.set(key, value, ttl)
        
        # Update local cache if enabled
        if use_local:
            self.local_cache[key] = value
            if ttl:
                self.local_cache_ttl[key] = time.time() + ttl
        
        return redis_result
    
    async def delete(self, key: str) -> bool:
        """Delete from cache (Redis and local)"""
        # Delete from local cache
        if key in self.local_cache:
            del self.local_cache[key]
        if key in self.local_cache_ttl:
            del self.local_cache_ttl[key]
        
        # Delete from Redis
        redis_manager = RedisManager(self.redis)
        return await redis_manager.delete(key)
    
    async def clear_local_cache(self) -> int:
        """Clear local cache, return count of cleared items"""
        count = len(self.local_cache)
        self.local_cache.clear()
        self.local_cache_ttl.clear()
        return count
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "local_cache_size": len(self.local_cache),
            "local_cache_items": list(self.local_cache.keys()),
            "redis_connected": bool(self.redis.ping()),
            "redis_info": {
                k: v for k, v in self.redis.info().items()
                if k in ["used_memory_human", "connected_clients", "uptime_in_days"]
            }
        }