from functools import wraps
from typing import Optional, Generator, Annotated
from fastapi import Depends, HTTPException, status, Request, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from redis import Redis

from app.config.database import get_db_session
from app.config.redis import get_redis_client
from app.core.security.jwt_handler import JWTManager
from app.core.security.permissions import PermissionChecker
from app.models.user.user import User
from app.models.admin.admin_user import AdminUser
from app.models.supervisor.supervisor import Supervisor
from app.models.student.student import Student
from app.models.base.enums import UserRole
from app.schemas.common.pagination import PaginationParams
from app.services.cache.cache_service import CacheService
from app.services.notification.notification_service import NotificationService

# Security scheme
security = HTTPBearer()

class DatabaseDependency:
    """Database session dependency provider"""
    
    @staticmethod
    def get_db() -> Generator[Session, None, None]:
        """Get database session with automatic cleanup"""
        db = next(get_db_session())
        try:
            yield db
        finally:
            db.close()

class AuthenticationDependency:
    """Current authenticated user dependency"""
    
    def __init__(self, jwt_manager: JWTManager):
        self.jwt_manager = jwt_manager
    
    async def get_current_user(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(DatabaseDependency.get_db)
    ) -> User:
        """Extract and validate current user from JWT token"""
        try:
            # Validate JWT token
            payload = self.jwt_manager.decode_token(credentials.credentials)
            user_id = payload.get("sub")
            
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials"
                )
            
            # Get user from database
            user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )
            
            # Check if user is active
            if user.status != "ACTIVE":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User account is inactive"
                )
            
            return user
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )

class AuthorizationDependency:
    """Permission-based authorization dependency"""
    
    def __init__(self, permission_checker: PermissionChecker):
        self.permission_checker = permission_checker
    
    def require_permission(self, permission: str, resource_type: Optional[str] = None):
        """Decorator for requiring specific permissions"""
        def decorator(func):
            @wraps(func)
            async def wrapper(
                current_user: User = Depends(AuthenticationDependency.get_current_user),
                db: Session = Depends(DatabaseDependency.get_db),
                *args, **kwargs
            ):
                has_permission = await self.permission_checker.check_permission(
                    user=current_user,
                    permission=permission,
                    resource_type=resource_type,
                    db=db
                )
                
                if not has_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Insufficient permissions: {permission}"
                    )
                
                return await func(current_user=current_user, db=db, *args, **kwargs)
            return wrapper
        return decorator

class TenantContextDependency:
    """Multi-tenant context dependency"""
    
    async def get_tenant_context(
        self,
        request: Request,
        current_user: User = Depends(AuthenticationDependency.get_current_user)
    ) -> dict:
        """Extract tenant context from request and user"""
        tenant_id = getattr(current_user, 'tenant_id', None)
        hostel_id = request.headers.get('X-Hostel-ID')
        
        return {
            "tenant_id": tenant_id,
            "hostel_id": hostel_id,
            "user_id": current_user.id,
            "user_role": current_user.role
        }

class CurrentUserDependency:
    """Current user with roles dependency"""
    
    def __init__(self, auth_dependency: AuthenticationDependency):
        self.auth_dependency = auth_dependency
    
    async def get_current_user_with_roles(
        self,
        current_user: User = Depends(AuthenticationDependency.get_current_user),
        db: Session = Depends(DatabaseDependency.get_db)
    ) -> User:
        """Get current user with loaded role relationships"""
        # Load role-specific data based on user type
        if current_user.role == UserRole.ADMIN:
            admin = db.query(AdminUser).filter(AdminUser.user_id == current_user.id).first()
            current_user.admin_profile = admin
        elif current_user.role == UserRole.SUPERVISOR:
            supervisor = db.query(Supervisor).filter(Supervisor.user_id == current_user.id).first()
            current_user.supervisor_profile = supervisor
        elif current_user.role == UserRole.STUDENT:
            student = db.query(Student).filter(Student.user_id == current_user.id).first()
            current_user.student_profile = student
        
        return current_user

class SuperAdminDependency:
    """Super admin only dependency"""
    
    async def get_super_admin_user(
        self,
        current_user: User = Depends(CurrentUserDependency.get_current_user_with_roles)
    ) -> User:
        """Ensure current user is super admin"""
        if current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super admin access required"
            )
        return current_user

class AdminDependency:
    """Admin level access dependency"""
    
    async def get_admin_user(
        self,
        current_user: User = Depends(CurrentUserDependency.get_current_user_with_roles)
    ) -> User:
        """Ensure current user has admin access"""
        if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        return current_user

class SupervisorDependency:
    """Supervisor level access dependency"""
    
    async def get_supervisor_user(
        self,
        current_user: User = Depends(CurrentUserDependency.get_current_user_with_roles)
    ) -> User:
        """Ensure current user has supervisor access"""
        if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.SUPERVISOR]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Supervisor access required"
            )
        return current_user

class StudentDependency:
    """Student access dependency"""
    
    async def get_student_user(
        self,
        current_user: User = Depends(CurrentUserDependency.get_current_user_with_roles)
    ) -> User:
        """Ensure current user is a student"""
        if current_user.role != UserRole.STUDENT:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Student access required"
            )
        return current_user

class HostelContextDependency:
    """Current hostel context dependency"""
    
    async def get_hostel_context(
        self,
        request: Request,
        current_user: User = Depends(AuthenticationDependency.get_current_user),
        db: Session = Depends(DatabaseDependency.get_db)
    ) -> dict:
        """Get current hostel context with validation"""
        hostel_id = request.headers.get('X-Hostel-ID')
        
        if not hostel_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hostel context required"
            )
        
        # Validate user has access to this hostel
        # Implementation would check admin assignments, supervisor assignments, etc.
        
        return {
            "hostel_id": hostel_id,
            "user_id": current_user.id,
            "user_role": current_user.role
        }

class PaginationDependency:
    """Pagination parameters dependency"""
    
    @staticmethod
    def get_pagination_params(
        page: int = Query(1, ge=1, description="Page number"),
        size: int = Query(20, ge=1, le=100, description="Page size"),
    ) -> PaginationParams:
        """Extract pagination parameters"""
        return PaginationParams(
            page=page,
            size=size,
            skip=(page - 1) * size
        )

class FilterDependency:
    """Query filtering dependency"""
    
    @staticmethod
    def get_filter_params(request: Request) -> dict:
        """Extract filter parameters from request"""
        return dict(request.query_params)

class CacheDependency:
    """Cache service dependency"""
    
    @staticmethod
    def get_cache_service(
        redis_client: Redis = Depends(get_redis_client)
    ) -> CacheService:
        """Get cache service instance"""
        return CacheService(redis_client)

class NotificationDependency:
    """Notification service dependency"""
    
    @staticmethod
    def get_notification_service(
        db: Session = Depends(DatabaseDependency.get_db),
        cache: CacheService = Depends(CacheDependency.get_cache_service)
    ) -> NotificationService:
        """Get notification service instance"""
        return NotificationService(db, cache)

class FileUploadDependency:
    """File upload validation dependency"""
    
    @staticmethod
    def validate_file_upload(
        max_size: int = 10 * 1024 * 1024,  # 10MB default
        allowed_types: list = None
    ):
        """File upload validation decorator"""
        if allowed_types is None:
            allowed_types = ['image/jpeg', 'image/png', 'application/pdf']
        
        def validator(file):
            if file.size > max_size:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File size exceeds {max_size} bytes"
                )
            
            if file.content_type not in allowed_types:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail=f"File type {file.content_type} not allowed"
                )
            
            return file
        
        return validator

# Dependency instances
database_dependency = DatabaseDependency()
jwt_manager = JWTManager()
permission_checker = PermissionChecker()
auth_dependency = AuthenticationDependency(jwt_manager)
authorization_dependency = AuthorizationDependency(permission_checker)
tenant_context_dependency = TenantContextDependency()
current_user_dependency = CurrentUserDependency(auth_dependency)
super_admin_dependency = SuperAdminDependency()
admin_dependency = AdminDependency()
supervisor_dependency = SupervisorDependency()
student_dependency = StudentDependency()
hostel_context_dependency = HostelContextDependency()
pagination_dependency = PaginationDependency()
filter_dependency = FilterDependency()
cache_dependency = CacheDependency()
notification_dependency = NotificationDependency()
file_upload_dependency = FileUploadDependency()

# Common dependency combinations
get_db = database_dependency.get_db
get_current_user = auth_dependency.get_current_user
get_current_user_with_roles = current_user_dependency.get_current_user_with_roles
get_super_admin = super_admin_dependency.get_super_admin_user
get_admin = admin_dependency.get_admin_user
get_supervisor = supervisor_dependency.get_supervisor_user
get_student = student_dependency.get_student_user
get_pagination = pagination_dependency.get_pagination_params
get_cache = cache_dependency.get_cache_service
get_notification_service = notification_dependency.get_notification_service