"""
FastAPI Dependencies

This module contains dependency functions used throughout the application
for authentication, authorization, database connections, etc.
"""

from typing import Generator, Optional, Any, Dict, List
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from .config import settings
from .database import get_db
from .security import verify_token, get_current_user
from .exceptions import (
    AuthenticationError,
    AuthorizationError,
    TokenError,
    TokenExpiredError,
    RateLimitExceeded
)
from .logging import get_logger

logger = get_logger(__name__)

# Security scheme
security = HTTPBearer()


# Database dependency
def get_database() -> Generator[Session, None, None]:
    """
    Database dependency to get database session
    """
    try:
        db = next(get_db())
        yield db
    finally:
        db.close()


# Authentication dependencies
async def get_current_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_database)
) -> Optional[Dict[str, Any]]:
    """
    Get current user from JWT token
    """
    try:
        token = credentials.credentials
        user = await get_current_user(token, db)
        if not user:
            raise AuthenticationError("Invalid token")
        return user
    except JWTError:
        raise AuthenticationError("Invalid token")
    except TokenExpiredError:
        raise AuthenticationError("Token has expired")
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise AuthenticationError("Authentication failed")


async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user_from_token)
) -> Dict[str, Any]:
    """
    Get current active user (must be active)
    """
    if not current_user.get("is_active", True):
        raise AuthenticationError("Inactive user")
    return current_user


async def get_current_admin_user(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get current admin user (must be admin)
    """
    if not current_user.get("is_admin", False) and not current_user.get("is_superuser", False):
        raise AuthorizationError("Admin access required")
    return current_user


async def get_current_superuser(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """
    Get current superuser (must be superuser)
    """
    if not current_user.get("is_superuser", False):
        raise AuthorizationError("Superuser access required")
    return current_user


# Optional authentication (for endpoints that can work with or without auth)
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_database)
) -> Optional[Dict[str, Any]]:
    """
    Get current user optionally (doesn't raise error if not authenticated)
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        user = await get_current_user(token, db)
        return user
    except Exception:
        return None


# Current user dependency class
class CurrentUserDependency:
    """Dependency for getting current user with flexible options"""
    
    def __init__(
        self, 
        optional: bool = False,
        require_active: bool = True,
        require_verified: bool = False
    ):
        self.optional = optional
        self.require_active = require_active
        self.require_verified = require_verified
    
    async def __call__(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        db: Session = Depends(get_database)
    ) -> Optional[Dict[str, Any]]:
        """Get current user with specified requirements"""
        if not credentials:
            if self.optional:
                return None
            else:
                raise AuthenticationError("Authentication required")
        
        try:
            token = credentials.credentials
            user = await get_current_user(token, db)
            
            if not user:
                if self.optional:
                    return None
                else:
                    raise AuthenticationError("Invalid token")
            
            # Check if user is active
            if self.require_active and not user.get("is_active", True):
                raise AuthenticationError("Account is not active")
            
            # Check if user is verified
            if self.require_verified and not user.get("is_verified", True):
                raise AuthenticationError("Account is not verified")
            
            return user
            
        except (JWTError, TokenExpiredError, AuthenticationError):
            if self.optional:
                return None
            else:
                raise
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            if self.optional:
                return None
            else:
                raise AuthenticationError("Authentication failed")


# Authentication dependency class
class AuthenticationDependency:
    """Dependency for authentication with optional requirements"""
    
    def __init__(self, require_active: bool = True, require_verified: bool = False):
        self.require_active = require_active
        self.require_verified = require_verified
    
    async def __call__(
        self, 
        current_user: Dict[str, Any] = Depends(get_current_user_from_token)
    ) -> Dict[str, Any]:
        """Check authentication requirements"""
        if self.require_active and not current_user.get("is_active", True):
            raise AuthenticationError("Account is not active")
        
        if self.require_verified and not current_user.get("is_verified", True):
            raise AuthenticationError("Account is not verified")
        
        return current_user


# Authorization dependency class
class AuthorizationDependency:
    """Dependency for authorization with flexible permission checking"""
    
    def __init__(
        self, 
        required_permissions: Optional[List[str]] = None,
        required_roles: Optional[List[str]] = None,
        require_all_permissions: bool = True,
        require_all_roles: bool = False
    ):
        self.required_permissions = required_permissions or []
        self.required_roles = required_roles or []
        self.require_all_permissions = require_all_permissions
        self.require_all_roles = require_all_roles
    
    async def __call__(
        self, 
        current_user: Dict[str, Any] = Depends(get_current_active_user)
    ) -> Dict[str, Any]:
        """Check authorization requirements"""
        # Superusers bypass all checks
        if current_user.get("is_superuser", False):
            return current_user
        
        user_permissions = current_user.get("permissions", [])
        user_roles = current_user.get("roles", [])
        
        # Check permissions
        if self.required_permissions:
            if self.require_all_permissions:
                # User must have ALL required permissions
                missing_permissions = [p for p in self.required_permissions if p not in user_permissions]
                if missing_permissions:
                    raise AuthorizationError(
                        f"Missing required permissions: {', '.join(missing_permissions)}",
                        required_permission=missing_permissions[0]
                    )
            else:
                # User must have AT LEAST ONE required permission
                if not any(p in user_permissions for p in self.required_permissions):
                    raise AuthorizationError(
                        f"At least one of these permissions required: {', '.join(self.required_permissions)}",
                        required_permission=self.required_permissions[0]
                    )
        
        # Check roles
        if self.required_roles:
            if self.require_all_roles:
                # User must have ALL required roles
                missing_roles = [r for r in self.required_roles if r not in user_roles]
                if missing_roles:
                    raise AuthorizationError(f"Missing required roles: {', '.join(missing_roles)}")
            else:
                # User must have AT LEAST ONE required role
                if not any(r in user_roles for r in self.required_roles):
                    raise AuthorizationError(f"At least one of these roles required: {', '.join(self.required_roles)}")
        
        return current_user


# Admin dependency class
class AdminDependency:
    """Dependency for admin-only endpoints"""
    
    def __init__(self, required_level: str = "admin"):
        self.required_level = required_level
    
    async def __call__(
        self, 
        current_user: Dict[str, Any] = Depends(get_current_active_user)
    ) -> Dict[str, Any]:
        """Check if user has admin privileges"""
        if not current_user.get("is_admin", False) and not current_user.get("is_superuser", False):
            raise AuthorizationError("Admin access required")
        
        # Additional admin level checks if needed
        if self.required_level == "super_admin" and not current_user.get("is_superuser", False):
            raise AuthorizationError("Super admin access required")
        
        return current_user


# Cache dependency class
class CacheDependency:
    """Dependency for cache management and control"""
    
    def __init__(
        self, 
        cache_key_prefix: Optional[str] = None,
        ttl: Optional[int] = None,
        bypass_cache: bool = False
    ):
        self.cache_key_prefix = cache_key_prefix
        self.ttl = ttl
        self.bypass_cache = bypass_cache
    
    async def __call__(
        self,
        request: Request,
        current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
    ) -> Dict[str, Any]:
        """Setup cache context for the request"""
        cache_context = {
            "cache_key_prefix": self.cache_key_prefix,
            "ttl": self.ttl,
            "bypass_cache": self.bypass_cache,
            "user_id": current_user.get("id") if current_user else None,
            "endpoint": str(request.url.path),
            "method": request.method
        }
        
        return cache_context


# Role-based access dependencies
def require_role(role: str):
    """
    Create a dependency that requires a specific role
    """
    async def role_dependency(
        current_user: Dict[str, Any] = Depends(get_current_active_user)
    ) -> Dict[str, Any]:
        user_roles = current_user.get("roles", [])
        if role not in user_roles and not current_user.get("is_superuser", False):
            raise AuthorizationError(f"Role '{role}' required", required_permission=role)
        return current_user
    
    return role_dependency


def require_permission(permission: str):
    """
    Create a dependency that requires a specific permission
    """
    async def permission_dependency(
        current_user: Dict[str, Any] = Depends(get_current_active_user)
    ) -> Dict[str, Any]:
        user_permissions = current_user.get("permissions", [])
        if permission not in user_permissions and not current_user.get("is_superuser", False):
            raise AuthorizationError(f"Permission '{permission}' required", required_permission=permission)
        return current_user
    
    return permission_dependency


# Rate limiting dependency
async def check_rate_limit(request: Request) -> None:
    """
    Check rate limiting for the current request
    """
    # This is a placeholder - you would implement actual rate limiting logic
    # using Redis or another store to track request counts
    client_ip = request.client.host
    
    # Placeholder rate limiting check
    # In a real implementation, you would:
    # 1. Get the current count from Redis for this IP
    # 2. Check if it exceeds the limit
    # 3. Increment the count
    # 4. Set expiration if it's the first request in the window
    
    # For now, just log the request
    logger.debug(f"Rate limit check for IP: {client_ip}")
    
    # Example of how you might raise a rate limit error:
    # if request_count > rate_limit:
    #     raise RateLimitExceeded("Rate limit exceeded", limit=rate_limit, reset_time=reset_time)


# Pagination dependencies
class PaginationParams:
    """Pagination parameters"""
    
    def __init__(
        self,
        skip: int = 0,
        limit: int = 100,
        max_limit: int = 1000
    ):
        self.skip = skip
        self.limit = min(limit, max_limit)


def get_pagination_params(
    skip: int = 0,
    limit: int = 100
) -> PaginationParams:
    """
    Get pagination parameters with validation
    """
    return PaginationParams(skip=skip, limit=limit)


# Search and filter dependencies
def get_search_params(
    q: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "asc"
) -> Dict[str, Any]:
    """
    Get search and filter parameters
    """
    return {
        "search_query": q,
        "sort_by": sort_by,
        "sort_order": sort_order.lower() if sort_order else "asc"
    }


# Common header dependencies
def get_request_id(request: Request) -> str:
    """
    Get or generate request ID for tracing
    """
    return request.headers.get("X-Request-ID", "unknown")


def get_user_agent(request: Request) -> str:
    """
    Get user agent from request headers
    """
    return request.headers.get("User-Agent", "unknown")


def get_client_ip(request: Request) -> str:
    """
    Get client IP address, considering proxy headers
    """
    # Check for forwarded IP first (from load balancers/proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Get the first IP if there are multiple
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fallback to direct client IP
    return request.client.host if request.client else "unknown"


# API versioning dependencies
def get_api_version(request: Request) -> str:
    """
    Get API version from headers or path
    """
    # Check header first
    version = request.headers.get("X-API-Version")
    if version:
        return version
    
    # Try to extract from path
    path_parts = request.url.path.split("/")
    for part in path_parts:
        if part.startswith("v") and part[1:].isdigit():
            return part
    
    return "v1"  # default version


# Content type dependencies
def require_json_content_type(request: Request) -> None:
    """
    Ensure request has JSON content type
    """
    content_type = request.headers.get("Content-Type", "")
    if not content_type.startswith("application/json"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Content-Type must be application/json"
        )


# Export commonly used dependencies
__all__ = [
    "get_database",
    "get_current_user_from_token",
    "get_current_active_user",
    "get_current_admin_user",
    "get_current_superuser",
    "get_current_user_optional",
    "CurrentUserDependency",  # Added this
    "AuthenticationDependency",
    "AuthorizationDependency",
    "AdminDependency",
    "CacheDependency",
    "require_role",
    "require_permission",
    "check_rate_limit",
    "PaginationParams",
    "get_pagination_params",
    "get_search_params",
    "get_request_id",
    "get_user_agent",
    "get_client_ip",
    "get_api_version",
    "require_json_content_type"
]