import time
import json
from typing import Dict, Set, Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from app.core.security.permissions import PermissionChecker
from app.core.exceptions import AuthorizationException, InsufficientPermissionsException
from app.models.user.user import User
from app.models.admin.admin_permissions import AdminPermission
from app.models.supervisor.supervisor_permissions import SupervisorPermission
from app.models.base.enums import UserRole
from app.config.database import get_db_session
from app.services.cache.cache_service import CacheService
import logging

logger = logging.getLogger(__name__)

class RoleBasedAuthorizationMiddleware(BaseHTTPMiddleware):
    """Role-based access control middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        # Define role-based route access
        self.role_permissions = {
            "/admin": [UserRole.SUPER_ADMIN, UserRole.ADMIN],
            "/supervisor": [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.SUPERVISOR],
            "/student": [UserRole.STUDENT],
            "/analytics": [UserRole.SUPER_ADMIN, UserRole.ADMIN],
            "/maintenance": [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.SUPERVISOR],
            "/complaints": [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.SUPERVISOR],
            "/payments": [UserRole.SUPER_ADMIN, UserRole.ADMIN],
            "/subscriptions": [UserRole.SUPER_ADMIN],
        }
    
    async def dispatch(self, request: Request, call_next):
        user_id = getattr(request.state, 'user_id', None)
        
        if user_id:
            # Get user role
            db = next(get_db_session())
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    # Check role-based access
                    path = request.url.path
                    for route_prefix, allowed_roles in self.role_permissions.items():
                        if path.startswith(route_prefix):
                            if user.role not in allowed_roles:
                                raise HTTPException(
                                    status_code=status.HTTP_403_FORBIDDEN,
                                    detail=f"Role {user.role} not allowed for {route_prefix}"
                                )
                            break
                    
                    request.state.user_role = user.role
                    
            finally:
                db.close()
        
        response = await call_next(request)
        return response

class PermissionCheckMiddleware(BaseHTTPMiddleware):
    """Granular permission checking middleware"""
    
    def __init__(self, app, permission_checker: PermissionChecker):
        super().__init__(app)
        self.permission_checker = permission_checker
        # Define endpoint permissions
        self.endpoint_permissions = {
            "GET:/hostels": "view_hostels",
            "POST:/hostels": "create_hostels",
            "PUT:/hostels": "edit_hostels",
            "DELETE:/hostels": "delete_hostels",
            "GET:/students": "view_students",
            "POST:/students": "create_students",
            "PUT:/students": "edit_students",
            "GET:/payments": "view_payments",
            "POST:/payments": "process_payments",
            "GET:/analytics": "view_analytics",
            "GET:/maintenance": "view_maintenance",
            "POST:/maintenance": "create_maintenance",
        }
    
    async def dispatch(self, request: Request, call_next):
        user_id = getattr(request.state, 'user_id', None)
        user_role = getattr(request.state, 'user_role', None)
        
        if user_id and user_role:
            # Create permission key
            permission_key = f"{request.method}:{request.url.path}"
            
            # Check if specific permission is required
            required_permission = None
            for endpoint, permission in self.endpoint_permissions.items():
                if permission_key.startswith(endpoint):
                    required_permission = permission
                    break
            
            if required_permission:
                db = next(get_db_session())
                try:
                    has_permission = await self.permission_checker.check_permission(
                        user_id=user_id,
                        permission=required_permission,
                        resource_type=self._extract_resource_type(request.url.path),
                        db=db
                    )
                    
                    if not has_permission:
                        raise InsufficientPermissionsException(
                            f"Permission '{required_permission}' required",
                            required_permission=required_permission
                        )
                        
                finally:
                    db.close()
        
        response = await call_next(request)
        return response
    
    def _extract_resource_type(self, path: str) -> Optional[str]:
        """Extract resource type from URL path"""
        parts = path.strip('/').split('/')
        if parts:
            return parts[0]
        return None

class HostelAccessMiddleware(BaseHTTPMiddleware):
    """Hostel-specific access control middleware"""
    
    async def dispatch(self, request: Request, call_next):
        user_id = getattr(request.state, 'user_id', None)
        hostel_id = request.headers.get('X-Hostel-ID')
        
        if user_id and hostel_id:
            # Check if user has access to this hostel
            db = next(get_db_session())
            try:
                user = db.query(User).filter(User.id == user_id).first()
                
                if user:
                    has_access = await self._check_hostel_access(
                        user, hostel_id, db
                    )
                    
                    if not has_access:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Access denied to hostel {hostel_id}"
                        )
                    
                    request.state.hostel_id = hostel_id
                    
            finally:
                db.close()
        
        response = await call_next(request)
        return response
    
    async def _check_hostel_access(
        self, user: User, hostel_id: str, db: Session
    ) -> bool:
        """Check if user has access to specific hostel"""
        if user.role == UserRole.SUPER_ADMIN:
            return True
        
        if user.role == UserRole.ADMIN:
            # Check admin hostel assignments
            from app.models.admin.admin_hostel_assignment import AdminHostelAssignment
            assignment = db.query(AdminHostelAssignment).filter(
                AdminHostelAssignment.admin_id == user.id,
                AdminHostelAssignment.hostel_id == hostel_id,
                AdminHostelAssignment.is_active == True
            ).first()
            return assignment is not None
        
        if user.role == UserRole.SUPERVISOR:
            # Check supervisor hostel assignments
            from app.models.supervisor.supervisor_assignment import SupervisorAssignment
            assignment = db.query(SupervisorAssignment).filter(
                SupervisorAssignment.supervisor_id == user.id,
                SupervisorAssignment.hostel_id == hostel_id,
                SupervisorAssignment.is_active == True
            ).first()
            return assignment is not None
        
        if user.role == UserRole.STUDENT:
            # Check if student belongs to this hostel
            from app.models.student.student import Student
            student = db.query(Student).filter(
                Student.user_id == user.id,
                Student.hostel_id == hostel_id
            ).first()
            return student is not None
        
        return False

class ResourceOwnershipMiddleware(BaseHTTPMiddleware):
    """Resource ownership validation middleware"""
    
    async def dispatch(self, request: Request, call_next):
        user_id = getattr(request.state, 'user_id', None)
        user_role = getattr(request.state, 'user_role', None)
        
        if user_id and user_role and request.method in ['GET', 'PUT', 'DELETE']:
            # Extract resource ID from path
            resource_id = self._extract_resource_id(request.url.path)
            
            if resource_id:
                # Check ownership for non-admin users
                if user_role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
                    db = next(get_db_session())
                    try:
                        owns_resource = await self._check_resource_ownership(
                            user_id, resource_id, request.url.path, db
                        )
                        
                        if not owns_resource:
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="Access denied to resource"
                            )
                            
                    finally:
                        db.close()
        
        response = await call_next(request)
        return response
    
    def _extract_resource_id(self, path: str) -> Optional[str]:
        """Extract resource ID from URL path"""
        # Simple extraction - assumes /{resource}/{id} pattern
        parts = path.strip('/').split('/')
        if len(parts) >= 2:
            try:
                # Check if it's a UUID or integer ID
                return parts[1] if parts[1] else None
            except:
                pass
        return None
    
    async def _check_resource_ownership(
        self, user_id: str, resource_id: str, path: str, db: Session
    ) -> bool:
        """Check if user owns the resource"""
        # Implementation depends on specific resource types
        if "/students/" in path:
            from app.models.student.student import Student
            student = db.query(Student).filter(
                Student.id == resource_id,
                Student.user_id == user_id
            ).first()
            return student is not None
        
        if "/bookings/" in path:
            from app.models.booking.booking import Booking
            booking = db.query(Booking).filter(
                Booking.id == resource_id,
                Booking.created_by == user_id
            ).first()
            return booking is not None
        
        if "/complaints/" in path:
            from app.models.complaint.complaint import Complaint
            complaint = db.query(Complaint).filter(
                Complaint.id == resource_id,
                Complaint.raiser_id == user_id
            ).first()
            return complaint is not None
        
        return True  # Default to allow if no specific check

class SuperAdminOverrideMiddleware(BaseHTTPMiddleware):
    """Super admin override capability middleware"""
    
    async def dispatch(self, request: Request, call_next):
        user_role = getattr(request.state, 'user_role', None)
        
        # Super admins can override any authorization
        if user_role == UserRole.SUPER_ADMIN:
            request.state.admin_override = True
        
        response = await call_next(request)
        return response

class PermissionCacheMiddleware(BaseHTTPMiddleware):
    """Permission result caching middleware"""
    
    def __init__(self, app, cache_service: CacheService, cache_ttl: int = 300):
        super().__init__(app)
        self.cache_service = cache_service
        self.cache_ttl = cache_ttl
    
    async def dispatch(self, request: Request, call_next):
        user_id = getattr(request.state, 'user_id', None)
        
        if user_id:
            # Create cache key for user permissions
            cache_key = f"permissions:{user_id}"
            
            # Try to get cached permissions
            cached_permissions = await self.cache_service.get(cache_key)
            
            if cached_permissions:
                request.state.cached_permissions = json.loads(cached_permissions)
            else:
                # Will be populated by permission checks
                request.state.permission_cache_key = cache_key
        
        response = await call_next(request)
        
        # Cache permissions after request processing
        if hasattr(request.state, 'computed_permissions'):
            cache_key = getattr(request.state, 'permission_cache_key')
            if cache_key:
                await self.cache_service.set(
                    cache_key,
                    json.dumps(request.state.computed_permissions),
                    self.cache_ttl
                )
        
        return response