"""
Rate Limiting System

Comprehensive rate limiting with Redis backend support,
multiple algorithms, and flexible configuration.
"""

import time
import asyncio
import hashlib
from typing import Any, Dict, List, Optional, Union, Callable
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass

import redis.asyncio as redis
from fastapi import Request, HTTPException, status

from .config import settings
from .exceptions import RateLimitExceeded
from .logging import get_logger
from .cache import cache_manager

logger = get_logger(__name__)


class RateLimitAlgorithm(str, Enum):
    """Rate limiting algorithms"""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"


class RateLimitScope(str, Enum):
    """Rate limit scope"""
    GLOBAL = "global"
    IP = "ip"
    USER = "user"
    ENDPOINT = "endpoint"
    API_KEY = "api_key"


@dataclass
class RateLimit:
    """Rate limit configuration"""
    key: str
    limit: int
    period: int  # seconds
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW
    scope: RateLimitScope = RateLimitScope.IP
    burst_size: Optional[int] = None
    description: Optional[str] = None


@dataclass
class RateLimitResult:
    """Rate limit check result"""
    allowed: bool
    limit: int
    remaining: int
    reset_time: datetime
    retry_after: int
    total_hits: int
    key: str


class TokenBucketLimiter:
    """Token bucket rate limiting algorithm"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def check_limit(self, key: str, limit: int, period: int, burst_size: Optional[int] = None) -> RateLimitResult:
        """Check rate limit using token bucket algorithm"""
        bucket_key = f"rate_limit:bucket:{key}"
        now = time.time()
        
        # Use burst_size if provided, otherwise use limit
        bucket_size = burst_size or limit
        refill_rate = limit / period  # tokens per second
        
        async with self.redis.pipeline() as pipe:
            try:
                pipe.multi()
                
                # Get current bucket state
                bucket_data = await self.redis.hmget(bucket_key, "tokens", "last_refill")
                
                current_tokens = float(bucket_data[0] or bucket_size)
                last_refill = float(bucket_data[1] or now)
                
                # Calculate tokens to add based on time passed
                time_passed = now - last_refill
                tokens_to_add = time_passed * refill_rate
                
                # Update token count (don't exceed bucket size)
                new_tokens = min(bucket_size, current_tokens + tokens_to_add)
                
                if new_tokens >= 1:
                    # Allow request and consume token
                    remaining_tokens = new_tokens - 1
                    
                    await pipe.hmset(bucket_key, {
                        "tokens": remaining_tokens,
                        "last_refill": now
                    })
                    await pipe.expire(bucket_key, period * 2)  # Keep data longer than period
                    await pipe.execute()
                    
                    return RateLimitResult(
                        allowed=True,
                        limit=limit,
                        remaining=int(remaining_tokens),
                        reset_time=datetime.fromtimestamp(now + (bucket_size - remaining_tokens) / refill_rate),
                        retry_after=0,
                        total_hits=bucket_size - int(remaining_tokens),
                        key=key
                    )
                else:
                    # Rate limit exceeded
                    retry_after = int((1 - new_tokens) / refill_rate)
                    
                    return RateLimitResult(
                        allowed=False,
                        limit=limit,
                        remaining=0,
                        reset_time=datetime.fromtimestamp(now + retry_after),
                        retry_after=retry_after,
                        total_hits=bucket_size,
                        key=key
                    )
                    
            except Exception as e:
                logger.error(f"Token bucket rate limit check failed: {str(e)}")
                # Fail open on errors
                return RateLimitResult(
                    allowed=True,
                    limit=limit,
                    remaining=limit,
                    reset_time=datetime.fromtimestamp(now + period),
                    retry_after=0,
                    total_hits=0,
                    key=key
                )


class SlidingWindowLimiter:
    """Sliding window rate limiting algorithm"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def check_limit(self, key: str, limit: int, period: int) -> RateLimitResult:
        """Check rate limit using sliding window algorithm"""
        window_key = f"rate_limit:sliding:{key}"
        now = time.time()
        window_start = now - period
        
        try:
            async with self.redis.pipeline() as pipe:
                # Remove old entries
                await pipe.zremrangebyscore(window_key, 0, window_start)
                
                # Count current entries
                current_count = await pipe.zcard(window_key)
                
                if current_count < limit:
                    # Allow request
                    await pipe.zadd(window_key, {str(now): now})
                    await pipe.expire(window_key, period)
                    await pipe.execute()
                    
                    return RateLimitResult(
                        allowed=True,
                        limit=limit,
                        remaining=limit - current_count - 1,
                        reset_time=datetime.fromtimestamp(now + period),
                        retry_after=0,
                        total_hits=current_count + 1,
                        key=key
                    )
                else:
                    # Rate limit exceeded
                    # Get oldest entry to determine reset time
                    oldest_entries = await pipe.zrange(window_key, 0, 0, withscores=True)
                    
                    if oldest_entries:
                        oldest_time = oldest_entries[0][1]
                        retry_after = int(oldest_time + period - now)
                    else:
                        retry_after = period
                    
                    return RateLimitResult(
                        allowed=False,
                        limit=limit,
                        remaining=0,
                        reset_time=datetime.fromtimestamp(now + retry_after),
                        retry_after=retry_after,
                        total_hits=current_count,
                        key=key
                    )
                    
        except Exception as e:
            logger.error(f"Sliding window rate limit check failed: {str(e)}")
            # Fail open on errors
            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=limit,
                reset_time=datetime.fromtimestamp(now + period),
                retry_after=0,
                total_hits=0,
                key=key
            )


class FixedWindowLimiter:
    """Fixed window rate limiting algorithm"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def check_limit(self, key: str, limit: int, period: int) -> RateLimitResult:
        """Check rate limit using fixed window algorithm"""
        now = time.time()
        window = int(now // period)
        window_key = f"rate_limit:fixed:{key}:{window}"
        
        try:
            # Get current count and increment
            current_count = await self.redis.incr(window_key)
            
            if current_count == 1:
                # First request in window, set expiration
                await self.redis.expire(window_key, period)
            
            if current_count <= limit:
                # Allow request
                next_window_start = (window + 1) * period
                
                return RateLimitResult(
                    allowed=True,
                    limit=limit,
                    remaining=limit - current_count,
                    reset_time=datetime.fromtimestamp(next_window_start),
                    retry_after=0,
                    total_hits=current_count,
                    key=key
                )
            else:
                # Rate limit exceeded
                next_window_start = (window + 1) * period
                retry_after = int(next_window_start - now)
                
                return RateLimitResult(
                    allowed=False,
                    limit=limit,
                    remaining=0,
                    reset_time=datetime.fromtimestamp(next_window_start),
                    retry_after=retry_after,
                    total_hits=current_count,
                    key=key
                )
                
        except Exception as e:
            logger.error(f"Fixed window rate limit check failed: {str(e)}")
            # Fail open on errors
            return RateLimitResult(
                allowed=True,
                limit=limit,
                remaining=limit,
                reset_time=datetime.fromtimestamp(now + period),
                retry_after=0,
                total_hits=0,
                key=key
            )


class RateLimiter:
    """Main rate limiting system"""
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.limiters = {}
        self.rate_limits: Dict[str, RateLimit] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize rate limiter"""
        if self._initialized:
            return
        
        try:
            # Initialize Redis connection
            self.redis_client = redis.Redis.from_url(
                settings.redis.redis_url,
                decode_responses=True
            )
            await self.redis_client.ping()
            
            # Initialize algorithm implementations
            self.limiters = {
                RateLimitAlgorithm.TOKEN_BUCKET: TokenBucketLimiter(self.redis_client),
                RateLimitAlgorithm.SLIDING_WINDOW: SlidingWindowLimiter(self.redis_client),
                RateLimitAlgorithm.FIXED_WINDOW: FixedWindowLimiter(self.redis_client),
            }
            
            # Set up default rate limits
            self._setup_default_limits()
            
            self._initialized = True
            logger.info("Rate limiter initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize rate limiter: {str(e)}")
            # Continue without rate limiting in case of Redis failure
            self._initialized = False
    
    def _setup_default_limits(self):
        """Set up default rate limits"""
        # Global API rate limit
        self.add_rate_limit(
            "global_api",
            RateLimit(
                key="global",
                limit=settings.api.DEFAULT_RATE_LIMIT,
                period=60,  # per minute
                algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
                scope=RateLimitScope.GLOBAL,
                description="Global API rate limit"
            )
        )
        
        # Admin API rate limit
        self.add_rate_limit(
            "admin_api",
            RateLimit(
                key="admin",
                limit=settings.api.ADMIN_API_RATE_LIMIT,
                period=60,
                algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
                scope=RateLimitScope.USER,
                burst_size=settings.api.ADMIN_API_BURST_SIZE,
                description="Admin API rate limit"
            )
        )
        
        # Login attempt rate limit
        self.add_rate_limit(
            "login_attempts",
            RateLimit(
                key="login",
                limit=5,
                period=300,  # 5 minutes
                algorithm=RateLimitAlgorithm.FIXED_WINDOW,
                scope=RateLimitScope.IP,
                description="Login attempt rate limit"
            )
        )
    
    def add_rate_limit(self, name: str, rate_limit: RateLimit):
        """Add a rate limit configuration"""
        self.rate_limits[name] = rate_limit
        logger.info(f"Added rate limit: {name} - {rate_limit.limit}/{rate_limit.period}s")
    
    async def check_rate_limit(
        self,
        limit_name: str,
        identifier: str,
        increment: bool = True
    ) -> RateLimitResult:
        """Check rate limit for given identifier"""
        if not self._initialized:
            await self.initialize()
        
        if not self._initialized or limit_name not in self.rate_limits:
            # Return permissive result if rate limiter not available
            return RateLimitResult(
                allowed=True,
                limit=1000,
                remaining=999,
                reset_time=datetime.utcnow() + timedelta(minutes=1),
                retry_after=0,
                total_hits=1,
                key=identifier
            )
        
        rate_limit = self.rate_limits[limit_name]
        
        # Generate rate limit key
        rate_key = self._generate_key(rate_limit, identifier)
        
        try:
            # Get appropriate limiter
            limiter = self.limiters.get(rate_limit.algorithm)
            if not limiter:
                raise ValueError(f"Unsupported algorithm: {rate_limit.algorithm}")
            
            # Check rate limit based on algorithm
            if rate_limit.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
                result = await limiter.check_limit(
                    rate_key,
                    rate_limit.limit,
                    rate_limit.period,
                    rate_limit.burst_size
                )
            else:
                result = await limiter.check_limit(
                    rate_key,
                    rate_limit.limit,
                    rate_limit.period
                )
            
            # Log rate limit violations
            if not result.allowed:
                logger.warning(f"Rate limit exceeded for {limit_name}: {identifier}")
            
            return result
            
        except Exception as e:
            logger.error(f"Rate limit check failed for {limit_name}: {str(e)}")
            # Fail open on errors
            return RateLimitResult(
                allowed=True,
                limit=rate_limit.limit,
                remaining=rate_limit.limit,
                reset_time=datetime.utcnow() + timedelta(seconds=rate_limit.period),
                retry_after=0,
                total_hits=0,
                key=rate_key
            )
    
    def _generate_key(self, rate_limit: RateLimit, identifier: str) -> str:
        """Generate rate limit key"""
        key_parts = [rate_limit.key, rate_limit.scope.value]
        
        if rate_limit.scope == RateLimitScope.GLOBAL:
            key_parts.append("all")
        else:
            # Hash identifier for privacy
            hashed_id = hashlib.md5(identifier.encode()).hexdigest()
            key_parts.append(hashed_id)
        
        return ":".join(key_parts)
    
    async def reset_rate_limit(self, limit_name: str, identifier: str) -> bool:
        """Reset rate limit for specific identifier"""
        if not self._initialized or limit_name not in self.rate_limits:
            return False
        
        rate_limit = self.rate_limits[limit_name]
        rate_key = self._generate_key(rate_limit, identifier)
        
        try:
            # Delete all keys related to this rate limit
            pattern = f"rate_limit:*:{rate_key}"
            keys = await self.redis_client.keys(pattern)
            
            if keys:
                await self.redis_client.delete(*keys)
                logger.info(f"Reset rate limit {limit_name} for {identifier}")
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset rate limit: {str(e)}")
            return False
    
    async def get_rate_limit_stats(self, limit_name: str) -> Dict[str, Any]:
        """Get statistics for a rate limit"""
        if not self._initialized or limit_name not in self.rate_limits:
            return {}
        
        try:
            rate_limit = self.rate_limits[limit_name]
            pattern = f"rate_limit:*:{rate_limit.key}:*"
            keys = await self.redis_client.keys(pattern)
            
            stats = {
                "limit_name": limit_name,
                "active_limiters": len(keys),
                "algorithm": rate_limit.algorithm.value,
                "limit": rate_limit.limit,
                "period": rate_limit.period,
                "scope": rate_limit.scope.value
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get rate limit stats: {str(e)}")
            return {}
    
    async def close(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()


# Global rate limiter instance
rate_limiter = RateLimiter()


def extract_identifier(request: Request, scope: RateLimitScope) -> str:
    """Extract identifier from request based on scope"""
    if scope == RateLimitScope.IP:
        # Get client IP (consider X-Forwarded-For for proxy setups)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    elif scope == RateLimitScope.USER:
        # Extract user ID from request (you'll need to implement based on your auth system)
        # This is a placeholder - implement based on your authentication
        return request.headers.get("X-User-ID", "anonymous")
    
    elif scope == RateLimitScope.API_KEY:
        # Extract API key
        return request.headers.get("X-API-Key", "no-key")
    
    elif scope == RateLimitScope.ENDPOINT:
        # Use endpoint path
        return request.url.path
    
    else:  # GLOBAL
        return "global"


def rate_limit_middleware(
    requests_per_minute: int = 60,
    burst_size: Optional[int] = None,
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW,
    scope: RateLimitScope = RateLimitScope.IP,
    skip_paths: Optional[List[str]] = None
):
    """Rate limiting middleware factory"""
    skip_paths = skip_paths or ["/health", "/metrics"]
    
    async def middleware(request: Request, call_next):
        # Skip rate limiting for certain paths
        if any(request.url.path.startswith(path) for path in skip_paths):
            return await call_next(request)
        
        if not settings.api.ENABLE_RATE_LIMITING:
            return await call_next(request)
        
        # Extract identifier
        identifier = extract_identifier(request, scope)
        
        # Create dynamic rate limit for this middleware
        limit_name = f"middleware_{algorithm.value}_{scope.value}"
        if limit_name not in rate_limiter.rate_limits:
            rate_limiter.add_rate_limit(
                limit_name,
                RateLimit(
                    key="middleware",
                    limit=requests_per_minute,
                    period=60,
                    algorithm=algorithm,
                    scope=scope,
                    burst_size=burst_size
                )
            )
        
        # Check rate limit
        result = await rate_limiter.check_rate_limit(limit_name, identifier)
        
        if not result.allowed:
            raise RateLimitExceeded(
                detail=f"Rate limit exceeded: {requests_per_minute} requests per minute",
                retry_after=result.retry_after,
                limit=result.limit
            )
        
        # Add rate limit headers to response
        response = await call_next(request)
        
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(int(result.reset_time.timestamp()))
        
        return response
    
    return middleware


def rate_limit(
    limit_name: str,
    requests_per_period: Optional[int] = None,
    period_seconds: Optional[int] = None,
    scope: RateLimitScope = RateLimitScope.USER
):
    """Rate limiting decorator for endpoint functions"""
    def decorator(func):
        async def wrapper(request: Request, *args, **kwargs):
            # Extract identifier
            identifier = extract_identifier(request, scope)
            
            # Use provided limits or get from existing configuration
            if requests_per_period and period_seconds:
                # Create temporary rate limit
                temp_limit_name = f"decorator_{limit_name}"
                rate_limiter.add_rate_limit(
                    temp_limit_name,
                    RateLimit(
                        key=limit_name,
                        limit=requests_per_period,
                        period=period_seconds,
                        scope=scope
                    )
                )
                check_name = temp_limit_name
            else:
                check_name = limit_name
            
            # Check rate limit
            result = await rate_limiter.check_rate_limit(check_name, identifier)
            
            if not result.allowed:
                raise RateLimitExceeded(
                    detail=f"Rate limit exceeded for {limit_name}",
                    retry_after=result.retry_after,
                    limit=result.limit
                )
            
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator


# Export main functions and classes
__all__ = [
    'RateLimitAlgorithm',
    'RateLimitScope', 
    'RateLimit',
    'RateLimitResult',
    'RateLimiter',
    'rate_limiter',
    'rate_limit_middleware',
    'rate_limit',
    'extract_identifier'
]