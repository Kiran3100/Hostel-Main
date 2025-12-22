import time
import json
import hashlib
from typing import Dict, Optional, Callable
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.cache.cache_service import CacheService
from app.models.base.enums import UserRole
import logging

logger = logging.getLogger(__name__)

class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """Global API rate limiting middleware"""
    
    def __init__(
        self, 
        app, 
        cache_service: CacheService,
        requests_per_minute: int = 1000,
        window_size: int = 60
    ):
        super().__init__(app)
        self.cache_service = cache_service
        self.requests_per_minute = requests_per_minute
        self.window_size = window_size
    
    async def dispatch(self, request: Request, call_next):
        # Global rate limiting key
        current_minute = int(time.time() // self.window_size)
        cache_key = f"global_rate_limit:{current_minute}"
        
        # Get current request count
        current_count = await self.cache_service.get(cache_key)
        if current_count is None:
            current_count = 0
        else:
            current_count = int(current_count)
        
        # Check if limit exceeded
        if current_count >= self.requests_per_minute:
            logger.warning(f"Global rate limit exceeded: {current_count}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Global rate limit exceeded",
                headers={
                    "Retry-After": str(self.window_size),
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(current_minute + 1)
                }
            )
        
        # Increment counter
        await self.cache_service.set(
            cache_key, 
            current_count + 1, 
            self.window_size
        )
        
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, self.requests_per_minute - current_count - 1)
        )
        response.headers["X-RateLimit-Reset"] = str(current_minute + 1)
        
        return response

class UserSpecificRateLimitMiddleware(BaseHTTPMiddleware):
    """User-specific rate limiting middleware"""
    
    def __init__(
        self, 
        app, 
        cache_service: CacheService,
        default_limit: int = 100,
        window_size: int = 60
    ):
        super().__init__(app)
        self.cache_service = cache_service
        self.window_size = window_size
        
        # Role-based rate limits
        self.role_limits = {
            UserRole.SUPER_ADMIN: 1000,
            UserRole.ADMIN: 500,
            UserRole.SUPERVISOR: 300,
            UserRole.STUDENT: 100,
            UserRole.VISITOR: 50,
            'anonymous': 20
        }
        self.default_limit = default_limit
    
    async def dispatch(self, request: Request, call_next):
        user_id = getattr(request.state, 'user_id', None)
        user_role = getattr(request.state, 'user_role', None)
        
        # Determine rate limit based on user role
        if user_role:
            rate_limit = self.role_limits.get(user_role, self.default_limit)
            identifier = f"user:{user_id}"
        else:
            # Anonymous user - use IP address
            rate_limit = self.role_limits['anonymous']
            identifier = f"ip:{request.client.host}"
        
        # Check rate limit
        await self._check_rate_limit(
            identifier, rate_limit, request
        )
        
        response = await call_next(request)
        return response
    
    async def _check_rate_limit(
        self, identifier: str, limit: int, request: Request
    ):
        """Check rate limit for specific identifier"""
        current_minute = int(time.time() // self.window_size)
        cache_key = f"user_rate_limit:{identifier}:{current_minute}"
        
        # Get current request count
        current_count = await self.cache_service.get(cache_key)
        if current_count is None:
            current_count = 0
        else:
            current_count = int(current_count)
        
        # Check if limit exceeded
        if current_count >= limit:
            logger.warning(f"User rate limit exceeded for {identifier}: {current_count}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {identifier}",
                headers={
                    "Retry-After": str(self.window_size),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(current_minute + 1)
                }
            )
        
        # Increment counter
        await self.cache_service.set(
            cache_key, 
            current_count + 1, 
            self.window_size
        )

class EndpointRateLimitMiddleware(BaseHTTPMiddleware):
    """Endpoint-specific rate limiting middleware"""
    
    def __init__(self, app, cache_service: CacheService):
        super().__init__(app)
        self.cache_service = cache_service
        
        # Endpoint-specific limits (requests per minute)
        self.endpoint_limits = {
            "POST:/auth/login": 10,
            "POST:/auth/register": 5,
            "POST:/auth/password/reset": 3,
            "POST:/payments": 30,
            "POST:/bookings": 20,
            "POST:/files/upload": 50,
            "GET:/analytics": 100,
            "POST:/notifications": 200,
        }
    
    async def dispatch(self, request: Request, call_next):
        endpoint_key = f"{request.method}:{request.url.path}"
        
        # Check if endpoint has specific rate limit
        rate_limit = None
        for pattern, limit in self.endpoint_limits.items():
            if endpoint_key.startswith(pattern):
                rate_limit = limit
                break
        
        if rate_limit:
            user_id = getattr(request.state, 'user_id', None) or request.client.host
            cache_key = f"endpoint_rate_limit:{endpoint_key}:{user_id}:{int(time.time() // 60)}"
            
            current_count = await self.cache_service.get(cache_key)
            if current_count is None:
                current_count = 0
            else:
                current_count = int(current_count)
            
            if current_count >= rate_limit:
                logger.warning(f"Endpoint rate limit exceeded: {endpoint_key} for {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded for {endpoint_key}",
                    headers={"Retry-After": "60"}
                )
            
            await self.cache_service.set(cache_key, current_count + 1, 60)
        
        response = await call_next(request)
        return response

class IPBasedRateLimitMiddleware(BaseHTTPMiddleware):
    """IP-based rate limiting middleware"""
    
    def __init__(
        self, 
        app, 
        cache_service: CacheService,
        requests_per_minute: int = 60,
        burst_limit: int = 10
    ):
        super().__init__(app)
        self.cache_service = cache_service
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
    
    async def dispatch(self, request: Request, call_next):
        ip_address = self._get_client_ip(request)
        
        # Implement sliding window rate limiting
        await self._check_sliding_window_limit(ip_address)
        
        # Implement burst protection
        await self._check_burst_limit(ip_address)
        
        response = await call_next(request)
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Get real client IP considering proxies"""
        # Check for forwarded IP headers
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.client.host
    
    async def _check_sliding_window_limit(self, ip_address: str):
        """Check sliding window rate limit"""
        current_time = time.time()
        window_start = current_time - 60  # 1 minute window
        
        # Get recent requests for this IP
        cache_key = f"ip_requests:{ip_address}"
        requests_data = await self.cache_service.get(cache_key)
        
        if requests_data:
            requests = json.loads(requests_data)
            # Filter requests within the window
            recent_requests = [req for req in requests if req > window_start]
        else:
            recent_requests = []
        
        # Check if limit exceeded
        if len(recent_requests) >= self.requests_per_minute:
            logger.warning(f"IP rate limit exceeded for {ip_address}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={"Retry-After": "60"}
            )
        
        # Add current request and store
        recent_requests.append(current_time)
        await self.cache_service.set(
            cache_key, 
            json.dumps(recent_requests), 
            120  # Keep for 2 minutes
        )
    
    async def _check_burst_limit(self, ip_address: str):
        """Check burst protection (requests in last 10 seconds)"""
        current_time = time.time()
        burst_window_start = current_time - 10  # 10 second window
        
        cache_key = f"ip_burst:{ip_address}"
        burst_requests_data = await self.cache_service.get(cache_key)
        
        if burst_requests_data:
            burst_requests = json.loads(burst_requests_data)
            recent_burst = [req for req in burst_requests if req > burst_window_start]
        else:
            recent_burst = []
        
        if len(recent_burst) >= self.burst_limit:
            logger.warning(f"Burst limit exceeded for {ip_address}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Burst limit exceeded",
                headers={"Retry-After": "10"}
            )
        
        recent_burst.append(current_time)
        await self.cache_service.set(
            cache_key, 
            json.dumps(recent_burst), 
            20  # Keep for 20 seconds
        )

class APIQuotaMiddleware(BaseHTTPMiddleware):
    """API quota management middleware"""
    
    def __init__(self, app, cache_service: CacheService):
        super().__init__(app)
        self.cache_service = cache_service
        
        # Subscription-based quotas (per month)
        self.subscription_quotas = {
            'basic': 10000,
            'standard': 50000,
            'premium': 200000,
            'enterprise': 1000000
        }
    
    async def dispatch(self, request: Request, call_next):
        user_id = getattr(request.state, 'user_id', None)
        
        if user_id:
            # Check user's subscription quota
            await self._check_monthly_quota(user_id)
        
        response = await call_next(request)
        
        if user_id:
            # Increment quota usage
            await self._increment_quota_usage(user_id)
        
        return response
    
    async def _check_monthly_quota(self, user_id: str):
        """Check monthly API quota for user"""
        current_month = time.strftime('%Y-%m')
        cache_key = f"api_quota:{user_id}:{current_month}"
        
        # Get user's subscription plan
        subscription_plan = await self._get_user_subscription_plan(user_id)
        quota_limit = self.subscription_quotas.get(subscription_plan, 1000)
        
        # Get current usage
        current_usage = await self.cache_service.get(cache_key)
        if current_usage is None:
            current_usage = 0
        else:
            current_usage = int(current_usage)
        
        if current_usage >= quota_limit:
            logger.warning(f"API quota exceeded for user {user_id}: {current_usage}/{quota_limit}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="API quota exceeded",
                headers={
                    "X-Quota-Limit": str(quota_limit),
                    "X-Quota-Used": str(current_usage),
                    "X-Quota-Remaining": "0"
                }
            )
    
    async def _increment_quota_usage(self, user_id: str):
        """Increment user's monthly quota usage"""
        current_month = time.strftime('%Y-%m')
        cache_key = f"api_quota:{user_id}:{current_month}"
        
        current_usage = await self.cache_service.get(cache_key)
        if current_usage is None:
            current_usage = 0
        else:
            current_usage = int(current_usage)
        
        # Calculate TTL until end of month
        next_month = time.strptime(f"{current_month}-01", '%Y-%m-%d')
        ttl = int(time.mktime(next_month)) + 32 * 24 * 3600 - int(time.time())
        
        await self.cache_service.set(cache_key, current_usage + 1, ttl)
    
    async def _get_user_subscription_plan(self, user_id: str) -> str:
        """Get user's subscription plan"""
        # This would typically query the database
        # For now, return a default
        return 'basic'

class RateLimitExceptionMiddleware(BaseHTTPMiddleware):
    """Rate limit exception handling middleware"""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        
        except HTTPException as e:
            if e.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                # Log rate limit violation
                logger.warning(
                    f"Rate limit exceeded: {request.client.host} -> "
                    f"{request.method} {request.url.path}"
                )
                
                # Add standard rate limit headers if not present
                if "Retry-After" not in e.headers:
                    e.headers["Retry-After"] = "60"
                
                # Custom rate limit response
                return Response(
                    content=json.dumps({
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": e.detail,
                            "retry_after": e.headers.get("Retry-After"),
                            "timestamp": int(time.time())
                        }
                    }),
                    status_code=e.status_code,
                    headers=e.headers,
                    media_type="application/json"
                )
            
            raise e