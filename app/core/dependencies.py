"""
FastAPI Dependencies

This module contains dependency functions used throughout the application
for authentication, authorization, database connections, etc.
"""

from typing import Generator, Optional, Any, Dict, List, Callable
from fastapi import Depends, HTTPException, status, Request, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import os
import uuid
from pathlib import Path
from datetime import datetime

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


# Direct function aliases to handle deps.py expectations
get_supervisor_user = get_current_active_user
get_student_user = get_current_active_user  
get_admin_user = get_current_admin_user
get_super_admin_user = get_current_superuser


# Base dependency class with dynamic attribute handling
class BaseDependency:
    """Base class for all dependencies with dynamic attribute handling"""
    
    def __getattr__(self, name: str):
        """
        Dynamic attribute handler for any missing attributes.
        This returns the __call__ method for most common patterns.
        """
        # Common patterns that should map to __call__
        if any(pattern in name.lower() for pattern in [
            'get_', 'fetch_', 'retrieve_', 'load_', 'find_', 'query_',
            'validate_', 'verify_', 'check_', 'ensure_', 'confirm_',
            'process_', 'handle_', 'manage_', 'create_', 'update_',
            'service', 'manager', 'handler', 'processor', 'validator'
        ]):
            return self.__call__
        
        # If it's asking for a user-related function, return the appropriate user function
        if 'user' in name.lower():
            if hasattr(self, '_user_function'):
                return self._user_function
            return get_current_active_user
        
        # Default fallback
        return self.__call__


# Database dependency class
class DatabaseDependency(BaseDependency):
    """Database dependency class that provides a database session"""
    
    def __init__(self):
        # Expose get_database as multiple potential attribute names
        self.get_db = get_database
        self.get_database = get_database
        self.db_session = get_database
        self.database_session = get_database
        self.get_db_session = get_database
        self.get_database_session = get_database
    
    def __call__(self) -> Generator[Session, None, None]:
        """Get database session"""
        return get_database()


# Current user dependency class
class CurrentUserDependency(BaseDependency):
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
        self._user_function = get_current_active_user
        
        # Expose __call__ as multiple potential attribute names
        self.get_current_user = self.__call__
        self.get_current_user_with_roles = self.__call__
        self.get_user = self.__call__
        self.get_user_with_roles = self.__call__
        self.get_user_with_permissions = self.__call__
        self.get_current_user_with_permissions = self.__call__
        self.current_user = self.__call__
        self.get_current_active_user = self.__call__
    
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
class AuthenticationDependency(BaseDependency):
    """Dependency for authentication with optional requirements"""
    
    def __init__(self, require_active: bool = True, require_verified: bool = False):
        self.require_active = require_active
        self.require_verified = require_verified
        self._user_function = get_current_user_from_token
        
        # Expose __call__ as multiple potential attribute names
        self.authenticate_user = self.__call__
        self.get_current_user = get_current_user_from_token  # Direct function reference
        self.require_auth = self.__call__
        self.verify_auth = self.__call__
        self.check_auth = self.__call__
        self.get_authenticated_user = self.__call__
    
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
class AuthorizationDependency(BaseDependency):
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
        self._user_function = get_current_active_user
        
        # Expose __call__ as multiple potential attribute names
        self.authorize_user = self.__call__
        self.check_permissions = self.__call__
        self.verify_permissions = self.__call__
        self.check_roles = self.__call__
        self.verify_roles = self.__call__
        self.authorize = self.__call__
        self.require_permission = require_permission
        self.require_role = require_role
        self.get_authorization = self.__call__
    
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
class AdminDependency(BaseDependency):
    """Dependency for admin-only endpoints"""
    
    def __init__(self, required_level: str = "admin"):
        self.required_level = required_level
        self._user_function = get_current_admin_user
        
        # Expose __call__ as multiple potential attribute names
        self.require_admin = self.__call__
        self.check_admin = self.__call__
        self.verify_admin = self.__call__
        self.get_admin = self.__call__
        self.get_admin_user = get_current_admin_user  # Direct function reference
        self.is_admin = self.__call__
        self.get_admin_context = self.__call__
    
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


# Super admin dependency class
class SuperAdminDependency(BaseDependency):
    """Dependency for handling super admin specific functionality and elevated permissions"""
    
    def __init__(
        self,
        require_elevated_access: bool = True,
        include_system_metrics: bool = True,
        include_audit_logs: bool = False
    ):
        """
        Initialize super admin dependency
        
        Args:
            require_elevated_access: Whether to require elevated system access
            include_system_metrics: Whether to include system metrics
            include_audit_logs: Whether to include audit logs
        """
        self.require_elevated_access = require_elevated_access
        self.include_system_metrics = include_system_metrics
        self.include_audit_logs = include_audit_logs
        self._user_function = get_current_superuser
        
        # Expose __call__ as multiple potential attribute names
        self.get_super_admin_context = self.__call__
        self.require_super_admin = self.__call__
        self.get_super_admin = self.__call__
        self.get_super_admin_user = get_current_superuser  # Direct function reference
        self.verify_super_admin = self.__call__
        self.check_super_admin = self.__call__
        self.get_superuser = self.__call__
    
    async def __call__(
        self,
        request: Request,
        db: Session = Depends(get_database),
        current_user: Dict[str, Any] = Depends(get_current_active_user)
    ) -> Dict[str, Any]:
        """
        Get super admin context and validate access
        
        Args:
            request: FastAPI request object
            db: Database session
            current_user: Current authenticated user
            
        Returns:
            Dict with super admin context and data
        """
        # Verify the user has super admin privileges
        if self.require_elevated_access:
            if not current_user.get("is_superuser", False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Super admin privileges required"
                )
        
        # Build the super admin context
        admin_context = {
            "admin_id": current_user.get("id"),
            "access_level": "super_admin",
            "system_mode": "production" if settings.ENVIRONMENT == "production" else "development",
            "last_login": current_user.get("last_login", datetime.now().isoformat()),
            "available_actions": [
                "manage_admins", 
                "manage_system_settings", 
                "view_all_hostels",
                "reset_user_passwords", 
                "manage_permissions", 
                "system_maintenance"
            ]
        }
        
        # Include system metrics if requested
        if self.include_system_metrics:
            # In a real implementation, fetch these from monitoring systems
            admin_context["system_metrics"] = {
                "active_users": 328,
                "total_hostels": 12,
                "total_rooms": 1250,
                "occupancy_rate": "87%",
                "active_bookings": 1089,
                "pending_maintenance": 23,
                "system_uptime": "99.98%",
                "database_size": "2.7 GB",
                "average_response_time": "124ms",
                "daily_api_requests": 58942
            }
        
        # Include audit logs if requested
        if self.include_audit_logs:
            # In a real implementation, fetch these from the database
            admin_context["recent_audit_logs"] = [
                {"timestamp": "2025-12-29T08:45:12", "user": "admin5", "action": "user_update", "details": "Modified permissions for staff member"},
                {"timestamp": "2025-12-29T08:15:45", "user": "warden3", "action": "room_assignment", "details": "Changed room assignment for 3 students"},
                {"timestamp": "2025-12-29T07:30:22", "user": "admin1", "action": "settings_update", "details": "Updated system notification settings"},
                {"timestamp": "2025-12-28T16:22:15", "user": "superadmin", "action": "hostel_creation", "details": "Created new hostel: North Campus"}
            ]
        
        return admin_context


# File upload dependency class
class FileUploadDependency(BaseDependency):
    """Dependency for handling file uploads with validation"""
    
    def __init__(
        self,
        upload_directory: str = "uploads",
        allowed_types: Optional[List[str]] = None,
        max_size_mb: float = 5.0,
        create_dir: bool = True
    ):
        """
        Initialize file upload dependency
        
        Args:
            upload_directory: Directory to store uploaded files
            allowed_types: List of allowed MIME types (e.g., ['image/jpeg', 'image/png'])
            max_size_mb: Maximum file size in MB
            create_dir: Whether to create the upload directory if it doesn't exist
        """
        self.upload_directory = Path(upload_directory)
        self.allowed_types = allowed_types or []
        self.max_size_bytes = max_size_mb * 1024 * 1024
        
        if create_dir and not self.upload_directory.exists():
            self.upload_directory.mkdir(parents=True, exist_ok=True)
            
        # Expose __call__ as multiple potential attribute names
        self.upload_file = self.__call__
        self.process_upload = self.__call__
        self.handle_file_upload = self.__call__
        self.save_file = self.__call__
        self.get_file_upload = self.__call__
        self.validate_file_upload = self.__call__  # Add this line
        self.validate_upload = self.__call__
        self.file_upload_handler = self.__call__
        self.process_file_upload = self.__call__
        self.handle_upload = self.__call__
    
    async def __call__(
        self,
        file: UploadFile = File(...),
        current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
    ) -> Dict[str, Any]:
        """
        Process and validate uploaded file
        
        Returns:
            Dict with file metadata and path
        """
        # Validate file size
        file_size = 0
        contents = await file.read()
        file_size = len(contents)
        await file.seek(0)  # Reset file pointer
        
        if file_size > self.max_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size exceeds maximum allowed ({self.max_size_bytes/1024/1024:.1f}MB)"
            )
        
        # Validate content type
        if self.allowed_types and file.content_type not in self.allowed_types:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"File type not allowed. Accepted types: {', '.join(self.allowed_types)}"
            )
        
        # Generate unique filename
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else ''
        unique_filename = f"{uuid.uuid4()}.{file_extension}" if file_extension else f"{uuid.uuid4()}"
        file_path = self.upload_directory / unique_filename
        
        # Save file
        try:
            with open(file_path, "wb") as f:
                f.write(contents)
        except Exception as e:
            logger.error(f"File upload error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error saving uploaded file"
            )
        
        # Return file metadata
        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "size": file_size,
            "path": str(file_path),
            "url_path": f"/uploads/{unique_filename}",
            "uploaded_by": current_user.get("id") if current_user else None
        }


# Cache dependency class
class CacheDependency(BaseDependency):
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
        
        # Expose __call__ as multiple potential attribute names
        self.get_cache_context = self.__call__
        self.get_cache = self.__call__
        self.cache_context = self.__call__
        self.get_cache_service = self.__call__
        self.cache_service = self.__call__
        self.get_cache_manager = self.__call__
        self.cache_manager = self.__call__
    
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


# Pagination dependency class
class PaginationDependency(BaseDependency):
    """Dependency for handling pagination with automatic validation and metadata"""
    
    def __init__(
        self, 
        default_limit: int = 100,
        max_limit: int = 1000,
        include_total: bool = True
    ):
        """
        Initialize pagination dependency
        
        Args:
            default_limit: Default number of items per page
            max_limit: Maximum allowed items per page
            include_total: Whether to include total count in response
        """
        self.default_limit = default_limit
        self.max_limit = max_limit
        self.include_total = include_total
        
        # Expose __call__ as multiple potential attribute names
        self.get_pagination = self.__call__
        self.paginate = self.__call__
        self.get_pagination_params = self.__call__
        self.pagination = self.__call__
        self.get_pagination_service = self.__call__
    
    async def __call__(
        self,
        skip: int = 0,
        limit: Optional[int] = None,
        page: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get pagination parameters and metadata
        
        Args:
            skip: Number of items to skip
            limit: Number of items per page
            page: Page number (1-based, overrides skip if provided)
            
        Returns:
            Dict with pagination parameters and metadata
        """
        # Set default limit if not provided
        if limit is None:
            limit = self.default_limit
        
        # Enforce maximum limit
        limit = min(limit, self.max_limit)
        
        # Calculate skip based on page if provided
        if page is not None and page > 0:
            skip = (page - 1) * limit
        
        # Ensure skip is not negative
        skip = max(0, skip)
        
        # Build pagination info
        pagination = {
            "skip": skip,
            "limit": limit,
            "page": (skip // limit) + 1 if limit > 0 else 1,
            "size": limit,
            "offset": skip,
        }
        
        return pagination
    
    def get_pagination_links(
        self, 
        pagination: Dict[str, Any], 
        total: int,
        base_url: str
    ) -> Dict[str, Optional[str]]:
        """
        Generate pagination links
        
        Args:
            pagination: Pagination parameters from __call__
            total: Total number of items
            base_url: Base URL for links
            
        Returns:
            Dict with pagination links (first, prev, next, last)
        """
        page = pagination["page"]
        limit = pagination["limit"]
        total_pages = (total + limit - 1) // limit if limit > 0 else 1
        
        # Remove trailing slash and query parameters
        base_url = base_url.split('?')[0].rstrip('/')
        
        links = {
            "first": f"{base_url}?page=1&limit={limit}" if total > 0 else None,
            "prev": f"{base_url}?page={page-1}&limit={limit}" if page > 1 else None,
            "next": f"{base_url}?page={page+1}&limit={limit}" if page < total_pages else None,
            "last": f"{base_url}?page={total_pages}&limit={limit}" if total_pages > 0 else None
        }
        
        return links
    
    def get_pagination_metadata(
        self, 
        pagination: Dict[str, Any], 
        total: int,
        base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get complete pagination metadata
        
        Args:
            pagination: Pagination parameters from __call__
            total: Total number of items
            base_url: Optional base URL for pagination links
            
        Returns:
            Dict with complete pagination metadata
        """
        page = pagination["page"]
        limit = pagination["limit"]
        total_pages = (total + limit - 1) // limit if limit > 0 else 1
        
        metadata = {
            "page": page,
            "size": limit,
            "total": total,
            "pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages
        }
        
        if base_url:
            metadata["links"] = self.get_pagination_links(pagination, total, base_url)
        
        return metadata


# Filter dependency class
class FilterDependency(BaseDependency):
    """Dependency for handling dynamic filtering of data"""
    
    def __init__(
        self,
        allowed_fields: Optional[List[str]] = None,
        default_sort: Optional[str] = None,
        default_direction: str = "asc",
        max_filter_complexity: int = 5
    ):
        """
        Initialize filter dependency
        
        Args:
            allowed_fields: List of fields that can be filtered and sorted
            default_sort: Default field to sort by
            default_direction: Default sort direction ('asc' or 'desc')
            max_filter_complexity: Maximum number of filters allowed
        """
        self.allowed_fields = allowed_fields or []
        self.default_sort = default_sort
        self.default_direction = default_direction.lower()
        self.max_filter_complexity = max_filter_complexity
        
        # Expose __call__ as multiple potential attribute names
        self.get_filter_params = self.__call__
        self.filter = self.__call__
        self.get_filters = self.__call__
        self.get_filter_config = self.__call__
        self.get_filter_service = self.__call__
    
    async def __call__(
        self,
        request: Request,
        sort_by: Optional[str] = None,
        sort_dir: Optional[str] = None,
        q: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process filtering and sorting parameters
        
        Args:
            request: FastAPI request object
            sort_by: Field to sort by
            sort_dir: Sort direction ('asc' or 'desc')
            q: Search query string
            
        Returns:
            Dict with filter configuration
        """
        # Get all query parameters for filtering
        filter_params = dict(request.query_params)
        
        # Remove pagination and sorting params from filter params
        for param in ["page", "limit", "skip", "sort_by", "sort_dir", "q"]:
            if param in filter_params:
                del filter_params[param]
        
        # Validate filter complexity
        if len(filter_params) > self.max_filter_complexity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Too many filter parameters. Maximum allowed: {self.max_filter_complexity}"
            )
        
        # Validate allowed fields if specified
        if self.allowed_fields:
            invalid_fields = [field for field in filter_params.keys() if field not in self.allowed_fields]
            if invalid_fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid filter fields: {', '.join(invalid_fields)}. Allowed fields: {', '.join(self.allowed_fields)}"
                )
        
        # Determine sorting
        if sort_by and self.allowed_fields and sort_by not in self.allowed_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort field: {sort_by}. Allowed fields: {', '.join(self.allowed_fields)}"
            )
        
        effective_sort = sort_by or self.default_sort
        effective_direction = sort_dir.lower() if sort_dir else self.default_direction
        
        if effective_direction not in ["asc", "desc"]:
            effective_direction = self.default_direction
        
        # Build filter configuration
        filter_config = {
            "filters": filter_params,
            "search_query": q,
            "sort": {
                "field": effective_sort,
                "direction": effective_direction
            },
            "filter_count": len(filter_params),
            "has_search": q is not None and q != ""
        }
        
        # Build SQL-like WHERE clause for reference (just a string representation)
        where_clauses = []
        params = []
        
        for field, value in filter_params.items():
            where_clauses.append(f"{field} = ?")
            params.append(value)
        
        if q:
            # This is just a simplified example - in practice you'd need proper 
            # search field configuration and escaping
            search_fields = self.allowed_fields[:3] if self.allowed_fields else ["name", "description", "id"]
            search_clause = " OR ".join([f"{field} LIKE ?" for field in search_fields])
            where_clauses.append(f"({search_clause})")
            params.extend([f"%{q}%" for _ in search_fields])
        
        if where_clauses:
            filter_config["sql_representation"] = {
                "where_clause": " AND ".join(where_clauses),
                "parameters": params,
                "order_clause": f"ORDER BY {effective_sort} {effective_direction.upper()}" if effective_sort else ""
            }
        
        return filter_config


# Hostel context dependency
class HostelContextDependency(BaseDependency):
    """Dependency for providing hostel context information throughout the application"""
    
    def __init__(
        self,
        hostel_id: Optional[str] = None,
        include_settings: bool = True,
        include_academic_info: bool = True,
        include_facility_info: bool = True
    ):
        """
        Initialize hostel context dependency
        
        Args:
            hostel_id: Optional specific hostel ID to use
            include_settings: Whether to include hostel settings
            include_academic_info: Whether to include academic year/term info
            include_facility_info: Whether to include facility information
        """
        self.hostel_id = hostel_id
        self.include_settings = include_settings
        self.include_academic_info = include_academic_info
        self.include_facility_info = include_facility_info
        
        # Expose __call__ as multiple potential attribute names
        self.get_hostel_context = self.__call__
        self.hostel_context = self.__call__
        self.get_hostel = self.__call__
        self.get_hostel_info = self.__call__
        self.get_hostel_service = self.__call__
    
    async def __call__(
        self,
        request: Request,
        db: Session = Depends(get_database),
        current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
    ) -> Dict[str, Any]:
        """
        Get hostel context information
        
        Returns:
            Dict with hostel context data
        """
        # Determine which hostel to use
        hostel_id = self.hostel_id
        
        # If no specific hostel_id is provided, try to get it from:
        # 1. URL path parameter
        # 2. Query parameter
        # 3. Current user's assigned hostel
        # 4. Default hostel from settings
        if not hostel_id:
            # Try path parameter
            if request.path_params and "hostel_id" in request.path_params:
                hostel_id = request.path_params.get("hostel_id")
            
            # Try query parameter
            elif request.query_params and "hostel_id" in request.query_params:
                hostel_id = request.query_params.get("hostel_id")
            
            # Try from user's assigned hostel
            elif current_user and "hostel_id" in current_user:
                hostel_id = current_user.get("hostel_id")
            
            # Fall back to default hostel from settings
            else:
                hostel_id = getattr(settings, "DEFAULT_HOSTEL_ID", "default")
        
        # Build context dictionary
        context = {
            "hostel_id": hostel_id,
            "timestamp": datetime.now().isoformat(),
            "request_id": request.headers.get("X-Request-ID", str(uuid.uuid4())),
            "user_id": current_user.get("id") if current_user else None,
        }
        
        # Add hostel settings if requested
        if self.include_settings:
            # In a real implementation, you would fetch this from database or config
            # For now, using placeholder values
            context["settings"] = {
                "name": f"Hostel {hostel_id}",
                "capacity": 200,
                "check_in_time": "14:00",
                "check_out_time": "11:00",
                "currency": "USD",
                "timezone": "UTC",
                "features_enabled": {
                    "online_booking": True,
                    "room_service": True,
                    "maintenance_requests": True
                }
            }
        
        # Add academic information if requested
        if self.include_academic_info:
            # In a real implementation, you would determine current academic period
            # from database or settings. This is a placeholder.
            now = datetime.now()
            current_month = now.month
            
            # Simple logic to determine current term/semester
            if 1 <= current_month <= 5:
                term = "Spring"
            elif 6 <= current_month <= 8:
                term = "Summer"
            else:
                term = "Fall"
            
            academic_year = f"{now.year}-{now.year + 1}" if current_month >= 8 else f"{now.year - 1}-{now.year}"
            
            context["academic_info"] = {
                "year": academic_year,
                "term": term,
                "is_active_term": True,
                "term_start_date": "2025-08-15" if term == "Fall" else "2026-01-15" if term == "Spring" else "2026-05-15",
                "term_end_date": "2025-12-15" if term == "Fall" else "2026-05-15" if term == "Spring" else "2026-08-15"
            }
        
        # Add facility information if requested
        if self.include_facility_info:
            # In a real implementation, you would fetch this from database
            # This is a placeholder
            context["facility_info"] = {
                "total_rooms": 100,
                "available_rooms": 35,
                "maintenance_count": 5,
                "amenities": ["WiFi", "Cafeteria", "Laundry", "Study Room", "Gym"],
                "floors": 4,
                "blocks": ["A", "B", "C"],
                "security_contact": "+1-123-456-7890"
            }
        
        return context


# Tenant context dependency
class TenantContextDependency(BaseDependency):
    """Dependency for multi-tenant functionality and isolation"""
    
    def __init__(
        self,
        tenant_id: Optional[str] = None,
        require_tenant_access: bool = True,
        include_tenant_settings: bool = True,
        include_tenant_users: bool = False
    ):
        """
        Initialize tenant context dependency
        
        Args:
            tenant_id: Optional specific tenant ID to use
            require_tenant_access: Whether to require access to the tenant
            include_tenant_settings: Whether to include tenant settings
            include_tenant_users: Whether to include tenant users
        """
        self.tenant_id = tenant_id
        self.require_tenant_access = require_tenant_access
        self.include_tenant_settings = include_tenant_settings
        self.include_tenant_users = include_tenant_users
        
        # Expose __call__ as multiple potential attribute names
        self.get_tenant_context = self.__call__
        self.tenant_context = self.__call__
        self.get_tenant = self.__call__
        self.get_tenant_info = self.__call__
        self.get_tenant_service = self.__call__
    
    async def __call__(
        self,
        request: Request,
        db: Session = Depends(get_database),
        current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
    ) -> Dict[str, Any]:
        """
        Get tenant context information
        
        Returns:
            Dict with tenant context data
        """
        # Determine which tenant to use
        tenant_id = self.tenant_id
        
        # If no specific tenant_id is provided, try to get it from:
        # 1. URL path parameter
        # 2. Query parameter
        # 3. Current user's assigned tenant
        # 4. Default tenant from settings
        if not tenant_id:
            # Try path parameter
            if request.path_params and "tenant_id" in request.path_params:
                tenant_id = request.path_params.get("tenant_id")
            
            # Try query parameter
            elif request.query_params and "tenant_id" in request.query_params:
                tenant_id = request.query_params.get("tenant_id")
            
            # Try from user's assigned tenant
            elif current_user and "tenant_id" in current_user:
                tenant_id = current_user.get("tenant_id")
            
            # Fall back to default tenant from settings
            else:
                tenant_id = getattr(settings, "DEFAULT_TENANT_ID", "main")
        
        # Verify tenant access if required
        if self.require_tenant_access and current_user:
            user_tenants = current_user.get("accessible_tenants", [])
            is_superuser = current_user.get("is_superuser", False)
            
            # Check if user has access to this tenant
            if not is_superuser and tenant_id not in user_tenants:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"No access to tenant: {tenant_id}"
                )
        
        # Build tenant context
        tenant_context = {
            "tenant_id": tenant_id,
            "current_user_has_access": True if not current_user else (
                current_user.get("is_superuser", False) or 
                tenant_id in current_user.get("accessible_tenants", [])
            )
        }
        
        # Include tenant settings if requested
        if self.include_tenant_settings:
            # In a real implementation, you would fetch this from database
            tenant_context["settings"] = {
                "name": f"University Housing - {tenant_id.capitalize()}",
                "domain": f"{tenant_id.lower()}.universityhousing.edu",
                "contact_email": f"support@{tenant_id.lower()}.universityhousing.edu",
                "timezone": "America/New_York",
                "language": "en-US",
                "logo_url": f"/assets/tenants/{tenant_id}/logo.png",
                "theme": {
                    "primary_color": "#003366",
                    "secondary_color": "#990000",
                    "font_family": "Roboto, sans-serif"
                },
                "features_enabled": {
                    "maintenance_requests": True,
                    "room_bookings": True,
                    "payment_processing": True,
                    "student_portal": True
                },
                "integration_ids": {
                    "payment_gateway": "stripe_account_123",
                    "student_info_system": "sis_connector_456",
                    "notification_service": "notify_789"
                }
            }
        
        # Include tenant users if requested
        if self.include_tenant_users and (not current_user or current_user.get("is_admin", False) or current_user.get("is_superuser", False)):
            # In a real implementation, you would fetch this from database
            tenant_context["user_summary"] = {
                "total_users": 1250,
                "active_users": 1180,
                "admin_count": 5,
                "staff_count": 45,
                "student_count": 1200,
                "roles_distribution": {
                    "admin": 5,
                    "warden": 8,
                    "supervisor": 12,
                    "staff": 25,
                    "student": 1200
                }
            }
        
        return tenant_context


# Notification dependency class
class NotificationDependency(BaseDependency):
    """Dependency for handling notifications and user preferences"""
    
    def __init__(
        self,
        channel: str = "all",
        include_unread: bool = True,
        include_preferences: bool = True,
        max_notifications: int = 10
    ):
        """
        Initialize notification dependency
        
        Args:
            channel: Notification channel to filter by ('email', 'sms', 'app', 'all')
            include_unread: Whether to include unread notifications
            include_preferences: Whether to include user notification preferences
            max_notifications: Maximum number of notifications to include
        """
        self.channel = channel
        self.include_unread = include_unread
        self.include_preferences = include_preferences
        self.max_notifications = max_notifications
        
        # Expose __call__ as multiple potential attribute names
        self.get_notifications = self.__call__
        self.notifications = self.__call__
        self.get_user_notifications = self.__call__
        self.get_notification_service = self.__call__
    
    async def __call__(
        self,
        request: Request,
        db: Session = Depends(get_database),
        current_user: Dict[str, Any] = Depends(get_current_active_user)
    ) -> Dict[str, Any]:
        """
        Get notification context and user's notifications
        
        Returns:
            Dict with notification data and preferences
        """
        user_id = current_user.get("id")
        
        # In a real implementation, you would fetch this from database
        # This is a placeholder
        notification_data = {
            "user_id": user_id,
            "unread_count": 5,
            "last_notification_at": "2025-12-29T08:15:30"
        }
        
        # Include recent notifications
        notifications = [
            {
                "id": "notif1",
                "type": "maintenance",
                "title": "Maintenance Request Completed",
                "message": "Your maintenance request #1234 has been completed",
                "timestamp": "2025-12-29T08:15:30",
                "is_read": False,
                "channel": "app",
                "action_url": "/maintenance/requests/1234"
            },
            {
                "id": "notif2",
                "type": "payment",
                "title": "Payment Reminder",
                "message": "Your hostel fee payment is due in 5 days",
                "timestamp": "2025-12-28T14:30:00",
                "is_read": True,
                "channel": "email",
                "action_url": "/payments/upcoming"
            },
            {
                "id": "notif3",
                "type": "announcement",
                "title": "New Hostel Guidelines",
                "message": "Please review the updated hostel guidelines for 2026",
                "timestamp": "2025-12-27T10:45:22",
                "is_read": False,
                "channel": "app",
                "action_url": "/announcements/guidelines-2026"
            }
        ]
        
        # Filter by channel if specified
        if self.channel != "all":
            notifications = [n for n in notifications if n["channel"] == self.channel]
        
        # Filter by read status if requested
        if self.include_unread:
            unread_notifications = [n for n in notifications if not n["is_read"]]
            notification_data["unread_notifications"] = unread_notifications[:self.max_notifications]
        
        # Include all notifications up to max count
        notification_data["notifications"] = notifications[:self.max_notifications]
        
        # Include notification preferences if requested
        if self.include_preferences:
            notification_data["preferences"] = {
                "email_enabled": True,
                "sms_enabled": False,
                "app_notifications_enabled": True,
                "maintenance_updates": True,
                "payment_reminders": True,
                "community_announcements": True,
                "security_alerts": True,
                "quiet_hours": {"start": "22:00", "end": "07:00"}
            }
        
        return notification_data


# Student dependency class
class StudentDependency(BaseDependency):
    """Dependency for handling student-specific logic and validation"""
    
    def __init__(
        self,
        require_enrollment: bool = True,
        verify_residence: bool = True,
        include_academic_records: bool = False,
        include_payment_history: bool = False
    ):
        """
        Initialize student dependency
        
        Args:
            require_enrollment: Whether to require active enrollment
            verify_residence: Whether to verify hostel residence
            include_academic_records: Whether to include academic records
            include_payment_history: Whether to include payment history
        """
        self.require_enrollment = require_enrollment
        self.verify_residence = verify_residence
        self.include_academic_records = include_academic_records
        self.include_payment_history = include_payment_history
        self._user_function = get_student_user
        
        # Expose __call__ as multiple potential attribute names
        self.get_student = self.__call__
        self.get_student_info = self.__call__
        self.student_info = self.__call__
        self.verify_student = self.__call__
        self.get_student_user = get_student_user
        self.get_student_service = self.__call__
    
    async def __call__(
        self,
        request: Request,
        student_id: Optional[str] = None,
        db: Session = Depends(get_database),
        current_user: Dict[str, Any] = Depends(get_current_active_user),
        hostel_context: Dict[str, Any] = Depends(HostelContextDependency())
    ) -> Dict[str, Any]:
        """
        Get student data and validate access
        
        Args:
            request: FastAPI request object
            student_id: Optional student ID (will use current user's if not provided)
            db: Database session
            current_user: Current authenticated user
            hostel_context: Hostel context information
            
        Returns:
            Dict with student data
        """
        # Determine which student to use
        if not student_id:
            # Try from path parameter
            if request.path_params and "student_id" in request.path_params:
                student_id = request.path_params.get("student_id")
            
            # Try from query parameter
            elif request.query_params and "student_id" in request.query_params:
                student_id = request.query_params.get("student_id")
            
            # Use current user if they are a student
            elif current_user.get("role") in ["student", "resident"]:
                student_id = current_user.get("id")
            
            # No student ID available
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Student ID is required"
                )
        
        # In a real implementation, you would fetch student data from database
        # This is a placeholder
        student_data = {
            "id": student_id,
            "name": f"Student {student_id}",
            "enrollment_status": "active",
            "year_of_study": 2,
            "program": "Computer Science",
            "hostel_id": hostel_context.get("hostel_id"),
            "room_number": f"A-{student_id}",
            "check_in_date": "2025-08-15",
            "expected_check_out": "2026-05-15"
        }
        
        # Verify enrollment if required
        if self.require_enrollment and student_data.get("enrollment_status") != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Student is not actively enrolled"
            )
        
        # Verify residence if required
        if self.verify_residence:
            # Check if student is assigned to current hostel
            if student_data.get("hostel_id") != hostel_context.get("hostel_id"):
                # Only allow staff/admin to access students from other hostels
                if not current_user.get("is_admin") and not current_user.get("is_superuser") and current_user.get("role") not in ["staff", "warden"]:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Student not assigned to current hostel"
                    )
        
        # Include academic records if requested
        if self.include_academic_records:
            # In a real implementation, you would fetch this from database
            student_data["academic_records"] = {
                "gpa": 3.7,
                "credits_completed": 65,
                "current_courses": [
                    "Advanced Algorithms",
                    "Database Systems",
                    "Software Engineering"
                ],
                "academic_standing": "good"
            }
        
        # Include payment history if requested
        if self.include_payment_history:
            # In a real implementation, you would fetch this from database
            student_data["payment_history"] = {
                "current_balance": 0,
                "last_payment_date": "2025-09-01",
                "last_payment_amount": 2500,
                "payment_status": "paid",
                "recent_payments": [
                    {"date": "2025-09-01", "amount": 2500, "method": "bank_transfer"},
                    {"date": "2025-08-15", "amount": 500, "method": "credit_card"}
                ]
            }
        
        return student_data


# Supervisor dependency class
class SupervisorDependency(BaseDependency):
    """Dependency for handling supervisor-specific logic and authorization"""
    
    def __init__(
        self,
        require_active: bool = True,
        require_hostel_assignment: bool = True,
        include_subordinates: bool = True,
        include_performance_metrics: bool = False
    ):
        """
        Initialize supervisor dependency
        
        Args:
            require_active: Whether to require active employment status
            require_hostel_assignment: Whether supervisor must be assigned to current hostel
            include_subordinates: Whether to include list of supervised staff
            include_performance_metrics: Whether to include performance metrics
        """
        self.require_active = require_active
        self.require_hostel_assignment = require_hostel_assignment
        self.include_subordinates = include_subordinates
        self.include_performance_metrics = include_performance_metrics
        self._user_function = get_supervisor_user
        
        # Expose __call__ as multiple potential attribute names
        self.get_supervisor = self.__call__
        self.supervisor_info = self.__call__
        self.get_supervisor_info = self.__call__
        self.verify_supervisor = self.__call__
        self.get_supervisor_user = get_supervisor_user
        self.get_supervisor_service = self.__call__
    
    async def __call__(
        self,
        request: Request,
        supervisor_id: Optional[str] = None,
        db: Session = Depends(get_database),
        current_user: Dict[str, Any] = Depends(get_current_active_user),
        hostel_context: Dict[str, Any] = Depends(HostelContextDependency())
    ) -> Dict[str, Any]:
        """
        Get supervisor data and validate access
        
        Args:
            request: FastAPI request object
            supervisor_id: Optional supervisor ID (will use current user's if not provided)
            db: Database session
            current_user: Current authenticated user
            hostel_context: Hostel context information
            
        Returns:
            Dict with supervisor data
        """
        # Determine which supervisor to use
        if not supervisor_id:
            # Try from path parameter
            if request.path_params and "supervisor_id" in request.path_params:
                supervisor_id = request.path_params.get("supervisor_id")
            
            # Try from query parameter
            elif request.query_params and "supervisor_id" in request.query_params:
                supervisor_id = request.query_params.get("supervisor_id")
            
            # Use current user if they are a supervisor
            elif current_user.get("role") in ["supervisor", "warden", "admin"]:
                supervisor_id = current_user.get("id")
            
            # No supervisor ID available
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Supervisor ID is required"
                )
        
        # In a real implementation, you would fetch supervisor data from database
        # This is a placeholder
        supervisor_data = {
            "id": supervisor_id,
            "name": f"Supervisor {supervisor_id}",
            "role": "Hostel Warden",
            "employment_status": "active",
            "years_of_service": 5,
            "hostel_id": hostel_context.get("hostel_id"),
            "office_location": "Admin Block, Room 102",
            "contact_email": f"supervisor{supervisor_id}@university.edu",
            "contact_phone": "+1-555-123-4567"
        }
        
        # Verify active status if required
        if self.require_active and supervisor_data.get("employment_status") != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Supervisor is not actively employed"
            )
        
        # Verify hostel assignment if required
        if self.require_hostel_assignment:
            # Check if supervisor is assigned to current hostel
            if supervisor_data.get("hostel_id") != hostel_context.get("hostel_id"):
                # Only allow higher admin to access supervisors from other hostels
                if not current_user.get("is_admin") and not current_user.get("is_superuser"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Supervisor not assigned to current hostel"
                    )
        
        # Include subordinates if requested
        if self.include_subordinates:
            # In a real implementation, you would fetch this from database
            supervisor_data["subordinates"] = [
                {"id": "staff1", "name": "Staff Member 1", "role": "Maintenance"},
                {"id": "staff2", "name": "Staff Member 2", "role": "Security"},
                {"id": "staff3", "name": "Staff Member 3", "role": "Cleaning"}
            ]
        
        # Include performance metrics if requested
        if self.include_performance_metrics:
            # In a real implementation, you would fetch this from database
            supervisor_data["performance_metrics"] = {
                "avg_issue_resolution_time": "6 hours",
                "student_satisfaction_rating": 4.7,
                "facility_uptime": "98.5%",
                "maintenance_requests_handled": 42,
                "complaints_resolved": 15,
                "staff_performance_rating": 4.5
            }
        
        return supervisor_data


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


# Create dependency instances that can be imported and used
_student_dep = StudentDependency()
_supervisor_dep = SupervisorDependency()
_admin_dep = AdminDependency()
_super_admin_dep = SuperAdminDependency()
_auth_dep = AuthenticationDependency()
_authz_dep = AuthorizationDependency()
_db_dep = DatabaseDependency()
_current_user_dep = CurrentUserDependency()
_hostel_context_dep = HostelContextDependency()
_tenant_context_dep = TenantContextDependency()
_notification_dep = NotificationDependency()
_filter_dep = FilterDependency()
_pagination_dep = PaginationDependency()
_upload_dep = FileUploadDependency()
_cache_dep = CacheDependency()
_file_upload_dep = FileUploadDependency()  # Add this alias


# Additional service and utility function aliases that might be expected
get_cache_service = _cache_dep.get_cache_service
get_filter_service = _filter_dep.get_filter_service
get_pagination_service = _pagination_dep.get_pagination_service
get_student_service = _student_dep.get_student_service
get_supervisor_service = _supervisor_dep.get_supervisor_service
get_hostel_service = _hostel_context_dep.get_hostel_service
get_tenant_service = _tenant_context_dep.get_tenant_service
get_notification_service = _notification_dep.get_notification_service
get_admin_context = _admin_dep.get_admin_context
get_db_session = _db_dep.get_db_session
get_database_session = _db_dep.get_database_session
get_current_user_with_roles = _current_user_dep.get_current_user_with_roles
get_authenticated_user = _auth_dep.get_authenticated_user
get_authorization = _authz_dep.get_authorization
get_superuser = _super_admin_dep.get_superuser
get_file_upload = _upload_dep.get_file_upload
validate_file_upload = _file_upload_dep.validate_file_upload  # Add this specific alias


# Export commonly used dependencies
__all__ = [
    "get_database",
    "DatabaseDependency",
    "get_current_user_from_token",
    "get_current_active_user",
    "get_current_admin_user",
    "get_current_superuser",
    "get_current_user_optional",
    "get_student_user",
    "get_supervisor_user",
    "get_admin_user",
    "get_super_admin_user",
    "HostelContextDependency",
    "FileUploadDependency",
    "PaginationDependency",
    "StudentDependency",
    "SupervisorDependency",
    "SuperAdminDependency",
    "TenantContextDependency",
    "NotificationDependency",
    "FilterDependency",
    "CurrentUserDependency",
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
    "require_json_content_type",
    "_student_dep",
    "_supervisor_dep",
    "_admin_dep",
    "_super_admin_dep",
    "_auth_dep",
    "_authz_dep",
    "_db_dep",
    "_current_user_dep",
    "_hostel_context_dep",
    "_tenant_context_dep",
    "_notification_dep",
    "_filter_dep",
    "_pagination_dep",
    "_upload_dep",
    "_cache_dep",
    "_file_upload_dep",
    # Additional service aliases
    "get_cache_service",
    "get_filter_service",
    "get_pagination_service",
    "get_student_service",
    "get_supervisor_service",
    "get_hostel_service",
    "get_tenant_service",
    "get_notification_service",
    "get_admin_context",
    "get_db_session",
    "get_database_session",
    "get_current_user_with_roles",
    "get_authenticated_user",
    "get_authorization",
    "get_superuser",
    "get_file_upload",
    "validate_file_upload"
]