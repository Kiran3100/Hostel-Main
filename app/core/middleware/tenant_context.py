import time
import json
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from app.core.exceptions import TenantNotFoundException, HostelNotFoundException
from app.models.user.user import User
from app.models.hostel.hostel import Hostel
from app.models.admin.hostel_context import HostelContext
from app.models.base.enums import UserRole
from app.config.database import get_db_session
from app.services.cache.cache_service import CacheService
import logging

logger = logging.getLogger(__name__)

class TenantContextMiddleware(BaseHTTPMiddleware):
    """Multi-tenant context resolution middleware"""
    
    def __init__(self, app, cache_service: CacheService):
        super().__init__(app)
        self.cache_service = cache_service
        self.cache_ttl = 300  # 5 minutes
    
    async def dispatch(self, request: Request, call_next):
        # Extract tenant information from various sources
        tenant_id = self._extract_tenant_id(request)
        user_id = getattr(request.state, 'user_id', None)
        
        if tenant_id or user_id:
            db = next(get_db_session())
            try:
                tenant_context = await self._resolve_tenant_context(
                    tenant_id, user_id, db
                )
                
                if tenant_context:
                    request.state.tenant_context = tenant_context
                    request.state.tenant_id = tenant_context['tenant_id']
                    
                    # Log tenant context switch
                    if user_id:
                        logger.info(f"Tenant context set for user {user_id}: {tenant_id}")
                
            finally:
                db.close()
        
        response = await call_next(request)
        return response
    
    def _extract_tenant_id(self, request: Request) -> Optional[str]:
        """Extract tenant ID from request headers, subdomain, or path"""
        # Method 1: Header-based tenant identification
        tenant_id = request.headers.get('X-Tenant-ID')
        if tenant_id:
            return tenant_id
        
        # Method 2: Subdomain-based tenant identification
        host = request.headers.get('Host', '')
        if '.' in host:
            subdomain = host.split('.')[0]
            if subdomain not in ['www', 'api', 'admin']:
                return subdomain
        
        # Method 3: Path-based tenant identification
        path_parts = request.url.path.strip('/').split('/')
        if len(path_parts) > 1 and path_parts[0] == 'tenant':
            return path_parts[1]
        
        return None
    
    async def _resolve_tenant_context(
        self, tenant_id: Optional[str], user_id: Optional[str], db: Session
    ) -> Optional[Dict[str, Any]]:
        """Resolve complete tenant context"""
        context = {}
        
        # If tenant_id is provided directly
        if tenant_id:
            context['tenant_id'] = tenant_id
            context['source'] = 'explicit'
        
        # If user_id is available, get tenant from user
        elif user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user and hasattr(user, 'tenant_id'):
                context['tenant_id'] = user.tenant_id
                context['source'] = 'user'
        
        # Validate tenant exists and user has access
        if context.get('tenant_id'):
            if await self._validate_tenant_access(context['tenant_id'], user_id, db):
                # Add additional context information
                context.update({
                    'user_id': user_id,
                    'timestamp': time.time(),
                    'permissions': await self._get_tenant_permissions(user_id, context['tenant_id'], db)
                })
                return context
        
        return None
    
    async def _validate_tenant_access(
        self, tenant_id: str, user_id: Optional[str], db: Session
    ) -> bool:
        """Validate user has access to tenant"""
        # Super admin has access to all tenants
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.role == UserRole.SUPER_ADMIN:
                return True
            
            # Check if user belongs to this tenant
            if hasattr(user, 'tenant_id') and user.tenant_id == tenant_id:
                return True
        
        # For public endpoints, allow without user
        return user_id is None
    
    async def _get_tenant_permissions(
        self, user_id: Optional[str], tenant_id: str, db: Session
    ) -> Dict[str, Any]:
        """Get user permissions within tenant context"""
        if not user_id:
            return {}
        
        # Cache key for user tenant permissions
        cache_key = f"tenant_permissions:{user_id}:{tenant_id}"
        
        # Try cache first
        cached = await self.cache_service.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Compute permissions
        permissions = {}
        
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            if user.role == UserRole.ADMIN:
                # Get admin-specific tenant permissions
                from app.models.admin.admin_permissions import AdminPermission
                admin_perms = db.query(AdminPermission).filter(
                    AdminPermission.admin_id == user.id
                ).first()
                if admin_perms:
                    permissions = admin_perms.to_dict()
            
            elif user.role == UserRole.SUPERVISOR:
                # Get supervisor-specific tenant permissions
                from app.models.supervisor.supervisor_permissions import SupervisorPermission
                supervisor_perms = db.query(SupervisorPermission).filter(
                    SupervisorPermission.supervisor_id == user.id
                ).first()
                if supervisor_perms:
                    permissions = supervisor_perms.to_dict()
        
        # Cache permissions
        await self.cache_service.set(cache_key, json.dumps(permissions), self.cache_ttl)
        
        return permissions

class HostelContextMiddleware(BaseHTTPMiddleware):
    """Hostel context switching middleware"""
    
    def __init__(self, app, cache_service: CacheService):
        super().__init__(app)
        self.cache_service = cache_service
    
    async def dispatch(self, request: Request, call_next):
        user_id = getattr(request.state, 'user_id', None)
        hostel_id = request.headers.get('X-Hostel-ID')
        
        if user_id:
            db = next(get_db_session())
            try:
                # Get or set active hostel context
                if hostel_id:
                    # User is switching context
                    await self._set_hostel_context(user_id, hostel_id, db)
                else:
                    # Get current active context
                    hostel_id = await self._get_active_hostel_context(user_id, db)
                
                if hostel_id:
                    request.state.hostel_id = hostel_id
                    request.state.hostel_context = await self._get_hostel_context_data(
                        hostel_id, db
                    )
                    
            finally:
                db.close()
        
        response = await call_next(request)
        return response
    
    async def _set_hostel_context(
        self, user_id: str, hostel_id: str, db: Session
    ):
        """Set active hostel context for user"""
        # Validate hostel exists and user has access
        hostel = db.query(Hostel).filter(
            Hostel.id == hostel_id,
            Hostel.is_deleted == False
        ).first()
        
        if not hostel:
            raise HostelNotFoundException(hostel_id=hostel_id)
        
        # Update or create hostel context
        context = db.query(HostelContext).filter(
            HostelContext.user_id == user_id
        ).first()
        
        if context:
            context.active_hostel_id = hostel_id
            context.last_switched_at = time.time()
        else:
            context = HostelContext(
                user_id=user_id,
                active_hostel_id=hostel_id,
                last_switched_at=time.time()
            )
            db.add(context)
        
        db.commit()
        
        # Log context switch
        logger.info(f"Hostel context switched for user {user_id}: {hostel_id}")
    
    async def _get_active_hostel_context(
        self, user_id: str, db: Session
    ) -> Optional[str]:
        """Get user's current active hostel context"""
        context = db.query(HostelContext).filter(
            HostelContext.user_id == user_id
        ).first()
        
        return context.active_hostel_id if context else None
    
    async def _get_hostel_context_data(
        self, hostel_id: str, db: Session
    ) -> Dict[str, Any]:
        """Get hostel context data"""
        cache_key = f"hostel_context:{hostel_id}"
        
        # Try cache first
        cached = await self.cache_service.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Get hostel data
        hostel = db.query(Hostel).filter(Hostel.id == hostel_id).first()
        if hostel:
            context_data = {
                'hostel_id': hostel.id,
                'hostel_name': hostel.name,
                'hostel_type': hostel.type,
                'total_capacity': hostel.total_capacity,
                'status': hostel.status,
                'settings': hostel.settings if hasattr(hostel, 'settings') else {}
            }
            
            # Cache for 5 minutes
            await self.cache_service.set(cache_key, json.dumps(context_data), 300)
            
            return context_data
        
        return {}

class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """Tenant data isolation middleware"""
    
    async def dispatch(self, request: Request, call_next):
        tenant_id = getattr(request.state, 'tenant_id', None)
        
        if tenant_id:
            # Add tenant filter to all database queries
            request.state.tenant_filter = {'tenant_id': tenant_id}
            
            # Log tenant-isolated operation
            logger.debug(f"Tenant isolation active: {tenant_id}")
        
        response = await call_next(request)
        return response

class CrossTenantAccessMiddleware(BaseHTTPMiddleware):
    """Cross-tenant access validation middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        # Define which roles can access cross-tenant data
        self.cross_tenant_roles = {UserRole.SUPER_ADMIN}
    
    async def dispatch(self, request: Request, call_next):
        user_role = getattr(request.state, 'user_role', None)
        requested_tenant = request.headers.get('X-Requested-Tenant-ID')
        current_tenant = getattr(request.state, 'tenant_id', None)
        
        # Check if cross-tenant access is being attempted
        if (requested_tenant and current_tenant and 
            requested_tenant != current_tenant):
            
            if user_role not in self.cross_tenant_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cross-tenant access not allowed"
                )
            
            # Log cross-tenant access
            user_id = getattr(request.state, 'user_id', None)
            logger.warning(
                f"Cross-tenant access: User {user_id} accessing tenant "
                f"{requested_tenant} from tenant {current_tenant}"
            )
            
            # Override tenant context for this request
            request.state.tenant_id = requested_tenant
            request.state.cross_tenant_access = True
        
        response = await call_next(request)
        return response

class ContextSwitchTrackingMiddleware(BaseHTTPMiddleware):
    """Context switch audit tracking middleware"""
    
    async def dispatch(self, request: Request, call_next):
        user_id = getattr(request.state, 'user_id', None)
        old_hostel_id = getattr(request.state, 'previous_hostel_id', None)
        new_hostel_id = getattr(request.state, 'hostel_id', None)
        
        if user_id and old_hostel_id and new_hostel_id and old_hostel_id != new_hostel_id:
            # Record context switch in audit log
            db = next(get_db_session())
            try:
                from app.models.audit.audit_log import AuditLog
                
                audit_entry = AuditLog(
                    user_id=user_id,
                    action='hostel_context_switch',
                    entity_type='hostel_context',
                    entity_id=new_hostel_id,
                    old_values={'hostel_id': old_hostel_id},
                    new_values={'hostel_id': new_hostel_id},
                    ip_address=request.client.host,
                    user_agent=request.headers.get('User-Agent', ''),
                    timestamp=time.time()
                )
                
                db.add(audit_entry)
                db.commit()
                
            finally:
                db.close()
        
        response = await call_next(request)
        return response