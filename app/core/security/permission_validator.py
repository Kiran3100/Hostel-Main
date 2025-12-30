"""
Permission validation utilities.

Provides permission checking and validation for admin operations.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Set, Callable
from enum import Enum
from fastapi import HTTPException, status
from functools import wraps

logger = logging.getLogger(__name__)


class PermissionLevel(str, Enum):
    """Permission level enumeration"""
    NONE = "none"
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class PermissionValidator:
    """
    Validate permissions for admin operations.
    
    Handles permission checking with support for:
    - Role-based permissions
    - Resource-based permissions
    - Hierarchical permissions
    - Context-aware validation
    """
    
    def __init__(self):
        """Initialize permission validator."""
        self._permission_cache: Dict[str, Any] = {}
        logger.info("PermissionValidator initialized")
    
    def validate_permission(
        self,
        user_permissions: List[str],
        required_permission: str,
        resource: Optional[str] = None,
        action: Optional[str] = None,
    ) -> bool:
        """
        Validate if user has required permission.
        
        Args:
            user_permissions: List of user's permissions
            required_permission: Required permission string
            resource: Optional resource identifier
            action: Optional action identifier
            
        Returns:
            True if user has permission, False otherwise
        """
        try:
            # Check for wildcard permission
            if "*" in user_permissions or "admin:*" in user_permissions:
                return True
            
            # Check exact permission match
            if required_permission in user_permissions:
                return True
            
            # Check resource-based permission
            if resource and action:
                resource_permission = f"{resource}:{action}"
                if resource_permission in user_permissions:
                    return True
                
                # Check wildcard for resource
                if f"{resource}:*" in user_permissions:
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error validating permission: {e}")
            return False
    
    def validate_role_permissions(
        self,
        user_roles: List[str],
        required_roles: List[str],
        require_all: bool = False,
    ) -> bool:
        """
        Validate if user has required roles.
        
        Args:
            user_roles: List of user's roles
            required_roles: List of required roles
            require_all: If True, user must have all roles; if False, any role matches
            
        Returns:
            True if user has required role(s), False otherwise
        """
        try:
            user_roles_set = set(user_roles)
            required_roles_set = set(required_roles)
            
            if require_all:
                return required_roles_set.issubset(user_roles_set)
            else:
                return bool(required_roles_set.intersection(user_roles_set))
                
        except Exception as e:
            logger.error(f"Error validating role permissions: {e}")
            return False
    
    def has_permission(
        self,
        user_data: Dict[str, Any],
        permission: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Check if user has specific permission with context.
        
        Args:
            user_data: User data dictionary with permissions and roles
            permission: Permission to check
            context: Optional context for permission check
            
        Returns:
            True if user has permission, False otherwise
        """
        try:
            # Extract permissions from user data
            user_permissions = user_data.get("permissions", [])
            user_roles = user_data.get("roles", [])
            
            # Check if user is super admin
            if user_data.get("is_superuser", False):
                return True
            
            # Check direct permission
            if permission in user_permissions:
                return True
            
            # Check wildcard permissions
            if "*" in user_permissions:
                return True
            
            # Check role-based permissions
            admin_roles = {"admin", "super_admin", "superuser"}
            if any(role in admin_roles for role in user_roles):
                return True
            
            # Context-aware permission check
            if context:
                return self._check_contextual_permission(
                    user_data, permission, context
                )
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return False
    
    def _check_contextual_permission(
        self,
        user_data: Dict[str, Any],
        permission: str,
        context: Dict[str, Any],
    ) -> bool:
        """
        Check permission with context (hostel, department, etc.).
        
        Args:
            user_data: User data dictionary
            permission: Permission to check
            context: Context for permission check
            
        Returns:
            True if user has contextual permission, False otherwise
        """
        try:
            # Check hostel-scoped permissions
            hostel_id = context.get("hostel_id")
            if hostel_id:
                user_hostel_id = user_data.get("hostel_id")
                if user_hostel_id != hostel_id:
                    # Check if user has access to multiple hostels
                    accessible_hostels = user_data.get("accessible_tenants", [])
                    if hostel_id not in accessible_hostels:
                        return False
            
            # Check resource-specific permissions
            resource_id = context.get("resource_id")
            if resource_id:
                # Add resource-specific validation logic here
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking contextual permission: {e}")
            return False
    
    def get_effective_permissions(
        self,
        user_data: Dict[str, Any],
        include_inherited: bool = True,
    ) -> Set[str]:
        """
        Get all effective permissions for user.
        
        Args:
            user_data: User data dictionary
            include_inherited: Include role-inherited permissions
            
        Returns:
            Set of effective permissions
        """
        try:
            permissions = set(user_data.get("permissions", []))
            
            # Add superuser wildcard
            if user_data.get("is_superuser", False):
                permissions.add("*")
            
            # Add admin wildcard
            if user_data.get("is_admin", False):
                permissions.add("admin:*")
            
            # Add role-based permissions if requested
            if include_inherited:
                user_roles = user_data.get("roles", [])
                for role in user_roles:
                    role_permissions = self._get_role_permissions(role)
                    permissions.update(role_permissions)
            
            return permissions
            
        except Exception as e:
            logger.error(f"Error getting effective permissions: {e}")
            return set()
    
    def _get_role_permissions(self, role: str) -> Set[str]:
        """
        Get permissions associated with a role.
        
        Args:
            role: Role name
            
        Returns:
            Set of permissions for the role
        """
        # Define role-based permissions
        role_permissions_map = {
            "super_admin": {"*"},
            "superuser": {"*"},
            "admin": {
                "admin:*",
                "users:read",
                "users:write",
                "rooms:read",
                "rooms:write",
                "bookings:read",
                "bookings:write",
                "announcement:create",
                "announcement:publish",
                "announcement:unpublish",
                "announcement:archive",
                "announcement:unarchive",
                "announcement:export",
                "announcement:bulk_delete",
                "announcement:analytics",
            },
            "warden": {
                "rooms:read",
                "rooms:write",
                "students:read",
                "students:write",
                "bookings:read",
                "reports:read",
                "announcement:create",
                "announcement:publish",
                "announcement:unpublish",
            },
            "supervisor": {
                "rooms:read",
                "students:read",
                "bookings:read",
                "reports:read",
                "announcement:create",
            },
            "student": {
                "profile:read",
                "profile:write",
                "maintenance:create",
            },
        }
        
        return role_permissions_map.get(role, set())
    
    def validate_bulk_permissions(
        self,
        user_data: Dict[str, Any],
        permissions: List[str],
        require_all: bool = True,
    ) -> Dict[str, bool]:
        """
        Validate multiple permissions at once.
        
        Args:
            user_data: User data dictionary
            permissions: List of permissions to check
            require_all: If True, all permissions must be valid
            
        Returns:
            Dictionary mapping permission to validation result
        """
        results = {}
        
        for permission in permissions:
            results[permission] = self.has_permission(user_data, permission)
        
        return results
    
    def clear_cache(self):
        """Clear the permission cache."""
        self._permission_cache.clear()
        logger.debug("Permission cache cleared")


def require_permissions(required_permissions: List[str]):
    """
    Decorator to require specific permissions for endpoint access.
    
    Args:
        required_permissions: List of required permission strings
        
    Usage:
        @require_permissions(["announcement:create"])
        async def create_announcement(...):
            pass
    """
    def decorator(func: Callable):
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get current_user from kwargs (should be injected by FastAPI)
            current_user = kwargs.get('current_user')
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            # Initialize permission validator
            validator = PermissionValidator()
            
            # Check if user has all required permissions
            for permission in required_permissions:
                if not validator.has_permission(current_user, permission):
                    logger.warning(
                        f"Permission denied for user {current_user.get('id', 'unknown')}: {permission}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied. Required: {permission}"
                    )
            
            # User has all required permissions, execute the function
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            validator = PermissionValidator()
            
            for permission in required_permissions:
                if not validator.has_permission(current_user, permission):
                    logger.warning(
                        f"Permission denied for user {current_user.get('id', 'unknown')}: {permission}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied. Required: {permission}"
                    )
            
            return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator