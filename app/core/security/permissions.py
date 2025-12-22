import time
from typing import Dict, List, Set, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass
from functools import wraps
from sqlalchemy.orm import Session

from app.models.base.enums import UserRole
from app.models.user.user import User
from app.models.admin.admin_permissions import AdminPermission
from app.models.supervisor.supervisor_permissions import SupervisorPermission
from app.core.exceptions import InsufficientPermissionsException, AuthorizationException
from app.services.cache.cache_service import CacheService
import logging

logger = logging.getLogger(__name__)

class PermissionLevel(Enum):
    """Permission levels for granular access control"""
    NONE = 0
    READ = 1
    WRITE = 2
    DELETE = 3
    ADMIN = 4

class ResourceType(Enum):
    """Resource types for permission checking"""
    HOSTEL = "hostel"
    STUDENT = "student"
    ROOM = "room"
    BOOKING = "booking"
    PAYMENT = "payment"
    COMPLAINT = "complaint"
    MAINTENANCE = "maintenance"
    ANNOUNCEMENT = "announcement"
    REVIEW = "review"
    ANALYTICS = "analytics"
    USER = "user"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"

@dataclass
class PermissionContext:
    """Context for permission checking"""
    user_id: str
    user_role: UserRole
    hostel_id: Optional[str] = None
    resource_id: Optional[str] = None
    resource_type: Optional[ResourceType] = None
    additional_context: Optional[Dict[str, Any]] = None

class PermissionChecker:
    """Permission validation utility"""
    
    def __init__(self, cache_service: Optional[CacheService] = None):
        self.cache_service = cache_service
        self.cache_ttl = 300  # 5 minutes
        
        # Define permission hierarchies
        self.role_hierarchy = {
            UserRole.SUPER_ADMIN: 100,
            UserRole.ADMIN: 80,
            UserRole.SUPERVISOR: 60,
            UserRole.STUDENT: 40,
            UserRole.VISITOR: 20
        }
        
        # Default permissions by role
        self.default_permissions = self._init_default_permissions()
    
    async def check_permission(
        self,
        user_id: str,
        permission: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        db: Session = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Check if user has specific permission"""
        try:
            # Check cache first
            cache_key = f"permission:{user_id}:{permission}:{resource_type}:{resource_id}"
            if self.cache_service:
                cached_result = await self.cache_service.get(cache_key)
                if cached_result is not None:
                    return cached_result == "true"
            
            # Get user and check permission
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            
            permission_context = PermissionContext(
                user_id=user_id,
                user_role=user.role,
                hostel_id=context.get('hostel_id') if context else None,
                resource_id=resource_id,
                resource_type=ResourceType(resource_type) if resource_type else None,
                additional_context=context
            )
            
            has_permission = await self._evaluate_permission(
                user, permission, permission_context, db
            )
            
            # Cache result
            if self.cache_service:
                await self.cache_service.set(
                    cache_key, 
                    "true" if has_permission else "false", 
                    self.cache_ttl
                )
            
            return has_permission
            
        except Exception as e:
            logger.error(f"Permission check failed: {str(e)}")
            return False
    
    async def _evaluate_permission(
        self,
        user: User,
        permission: str,
        context: PermissionContext,
        db: Session
    ) -> bool:
        """Evaluate permission based on user role and context"""
        
        # Super admin has all permissions
        if user.role == UserRole.SUPER_ADMIN:
            return True
        
        # Check role-based permissions
        if user.role == UserRole.ADMIN:
            return await self._check_admin_permission(user, permission, context, db)
        elif user.role == UserRole.SUPERVISOR:
            return await self._check_supervisor_permission(user, permission, context, db)
        elif user.role == UserRole.STUDENT:
            return await self._check_student_permission(user, permission, context, db)
        elif user.role == UserRole.VISITOR:
            return await self._check_visitor_permission(user, permission, context, db)
        
        return False
    
    async def _check_admin_permission(
        self,
        user: User,
        permission: str,
        context: PermissionContext,
        db: Session
    ) -> bool:
        """Check admin-specific permissions"""
        # Get admin permissions from database
        admin_perms = db.query(AdminPermission).filter(
            AdminPermission.admin_id == user.id
        ).first()
        
        if not admin_perms:
            # Use default admin permissions
            return permission in self.default_permissions.get(UserRole.ADMIN, set())
        
        # Check specific permission
        return getattr(admin_perms, permission, False)
    
    async def _check_supervisor_permission(
        self,
        user: User,
        permission: str,
        context: PermissionContext,
        db: Session
    ) -> bool:
        """Check supervisor-specific permissions"""
        # Get supervisor permissions
        supervisor_perms = db.query(SupervisorPermission).filter(
            SupervisorPermission.supervisor_id == user.id
        ).first()
        
        if not supervisor_perms:
            return permission in self.default_permissions.get(UserRole.SUPERVISOR, set())
        
        # Check hostel-specific permissions if context provided
        if context.hostel_id:
            # Verify supervisor is assigned to this hostel
            if not await self._check_hostel_assignment(user.id, context.hostel_id, db):
                return False
        
        return getattr(supervisor_perms, permission, False)
    
    async def _check_student_permission(
        self,
        user: User,
        permission: str,
        context: PermissionContext,
        db: Session
    ) -> bool:
        """Check student-specific permissions"""
        # Students have limited permissions
        student_permissions = self.default_permissions.get(UserRole.STUDENT, set())
        
        if permission not in student_permissions:
            return False
        
        # Check resource ownership for certain operations
        if context.resource_type and context.resource_id:
            return await self._check_resource_ownership(user.id, context, db)
        
        return True
    
    async def _check_visitor_permission(
        self,
        user: User,
        permission: str,
        context: PermissionContext,
        db: Session
    ) -> bool:
        """Check visitor-specific permissions"""
        visitor_permissions = self.default_permissions.get(UserRole.VISITOR, set())
        return permission in visitor_permissions
    
    async def _check_hostel_assignment(
        self, user_id: str, hostel_id: str, db: Session
    ) -> bool:
        """Check if user is assigned to specific hostel"""
        # Check supervisor assignment
        from app.models.supervisor.supervisor_assignment import SupervisorAssignment
        
        assignment = db.query(SupervisorAssignment).filter(
            SupervisorAssignment.supervisor_id == user_id,
            SupervisorAssignment.hostel_id == hostel_id,
            SupervisorAssignment.is_active == True
        ).first()
        
        return assignment is not None
    
    async def _check_resource_ownership(
        self, user_id: str, context: PermissionContext, db: Session
    ) -> bool:
        """Check if user owns the resource"""
        if context.resource_type == ResourceType.BOOKING:
            from app.models.booking.booking import Booking
            resource = db.query(Booking).filter(
                Booking.id == context.resource_id,
                Booking.created_by == user_id
            ).first()
            return resource is not None
        
        elif context.resource_type == ResourceType.COMPLAINT:
            from app.models.complaint.complaint import Complaint
            resource = db.query(Complaint).filter(
                Complaint.id == context.resource_id,
                Complaint.raiser_id == user_id
            ).first()
            return resource is not None
        
        # Add more resource ownership checks as needed
        return False
    
    def _init_default_permissions(self) -> Dict[UserRole, Set[str]]:
        """Initialize default permissions for each role"""
        return {
            UserRole.SUPER_ADMIN: {
                # Super admin has all permissions
                "*"
            },
            UserRole.ADMIN: {
                "view_hostels", "create_hostels", "edit_hostels", "delete_hostels",
                "view_students", "create_students", "edit_students", "delete_students",
                "view_rooms", "create_rooms", "edit_rooms", "delete_rooms",
                "view_bookings", "create_bookings", "edit_bookings", "cancel_bookings",
                "view_payments", "process_payments", "refund_payments",
                "view_complaints", "assign_complaints", "resolve_complaints",
                "view_maintenance", "create_maintenance", "assign_maintenance",
                "view_analytics", "view_reports",
                "manage_supervisors", "assign_permissions"
            },
            UserRole.SUPERVISOR: {
                "view_students", "edit_students",
                "view_rooms", "edit_rooms",
                "view_bookings", "edit_bookings",
                "view_complaints", "assign_complaints", "resolve_complaints",
                "view_maintenance", "create_maintenance",
                "view_attendance", "mark_attendance",
                "approve_leaves", "reject_leaves"
            },
            UserRole.STUDENT: {
                "view_profile", "edit_profile",
                "view_bookings", "create_bookings",
                "view_payments", "make_payments",
                "create_complaints", "view_own_complaints",
                "apply_leave", "view_leave_balance",
                "view_attendance", "view_mess_menu"
            },
            UserRole.VISITOR: {
                "view_public_hostels", "search_hostels",
                "create_inquiries", "create_bookings",
                "view_reviews", "create_reviews"
            }
        }

class RolePermissionManager:
    """Role-based permission manager"""
    
    def __init__(self):
        self.role_permissions = {}
        self.permission_cache = {}
    
    def define_role_permissions(self, role: UserRole, permissions: Set[str]):
        """Define permissions for a specific role"""
        self.role_permissions[role] = permissions
        logger.info(f"Role permissions defined for {role}: {len(permissions)} permissions")
    
    def add_permission_to_role(self, role: UserRole, permission: str):
        """Add permission to role"""
        if role not in self.role_permissions:
            self.role_permissions[role] = set()
        
        self.role_permissions[role].add(permission)
        self._invalidate_cache(role)
    
    def remove_permission_from_role(self, role: UserRole, permission: str):
        """Remove permission from role"""
        if role in self.role_permissions:
            self.role_permissions[role].discard(permission)
            self._invalidate_cache(role)
    
    def get_role_permissions(self, role: UserRole) -> Set[str]:
        """Get all permissions for a role"""
        return self.role_permissions.get(role, set())
    
    def check_role_permission(self, role: UserRole, permission: str) -> bool:
        """Check if role has specific permission"""
        role_perms = self.get_role_permissions(role)
        return permission in role_perms or "*" in role_perms
    
    def _invalidate_cache(self, role: UserRole):
        """Invalidate permission cache for role"""
        keys_to_remove = [key for key in self.permission_cache.keys() if key.startswith(f"{role}:")]
        for key in keys_to_remove:
            del self.permission_cache[key]

class ResourcePermissionChecker:
    """Resource-specific permission checker"""
    
    def __init__(self, permission_checker: PermissionChecker):
        self.permission_checker = permission_checker
    
    async def can_access_resource(
        self,
        user_id: str,
        resource_type: ResourceType,
        resource_id: str,
        operation: str,
        db: Session,
        context: Optional[Dict] = None
    ) -> bool:
        """Check if user can access specific resource"""
        
        # Build permission string
        permission = f"{operation}_{resource_type.value}"
        
        # Check base permission first
        has_base_permission = await self.permission_checker.check_permission(
            user_id=user_id,
            permission=permission,
            resource_type=resource_type.value,
            resource_id=resource_id,
            db=db,
            context=context
        )
        
        if not has_base_permission:
            return False
        
        # Check additional resource-specific constraints
        return await self._check_resource_constraints(
            user_id, resource_type, resource_id, operation, db, context
        )
    
    async def _check_resource_constraints(
        self,
        user_id: str,
        resource_type: ResourceType,
        resource_id: str,
        operation: str,
        db: Session,
        context: Optional[Dict]
    ) -> bool:
        """Check additional resource-specific constraints"""
        
        if resource_type == ResourceType.STUDENT:
            return await self._check_student_access(user_id, resource_id, operation, db)
        
        elif resource_type == ResourceType.PAYMENT:
            return await self._check_payment_access(user_id, resource_id, operation, db)
        
        elif resource_type == ResourceType.BOOKING:
            return await self._check_booking_access(user_id, resource_id, operation, db)
        
        # Default: allow if base permission is granted
        return True
    
    async def _check_student_access(
        self, user_id: str, student_id: str, operation: str, db: Session
    ) -> bool:
        """Check student-specific access constraints"""
        user = db.query(User).filter(User.id == user_id).first()
        
        # Students can only access their own data
        if user.role == UserRole.STUDENT:
            from app.models.student.student import Student
            student = db.query(Student).filter(Student.id == student_id).first()
            return student and student.user_id == user_id
        
        # Supervisors can access students in their assigned hostels
        if user.role == UserRole.SUPERVISOR:
            # Implementation would check supervisor's assigned hostels
            pass
        
        return True
    
    async def _check_payment_access(
        self, user_id: str, payment_id: str, operation: str, db: Session
    ) -> bool:
        """Check payment-specific access constraints"""
        from app.models.payment.payment import Payment
        
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            return False
        
        user = db.query(User).filter(User.id == user_id).first()
        
        # Students can only view their own payments
        if user.role == UserRole.STUDENT:
            return operation == "view" and payment.payer_id == user_id
        
        return True
    
    async def _check_booking_access(
        self, user_id: str, booking_id: str, operation: str, db: Session
    ) -> bool:
        """Check booking-specific access constraints"""
        from app.models.booking.booking import Booking
        
        booking = db.query(Booking).filter(Booking.id == booking_id).first()
        if not booking:
            return False
        
        user = db.query(User).filter(User.id == user_id).first()
        
        # Students can access their own bookings
        if user.role == UserRole.STUDENT:
            return booking.created_by == user_id
        
        return True

class PermissionDecorator:
    """Permission checking decorator"""
    
    def __init__(self, permission_checker: PermissionChecker):
        self.permission_checker = permission_checker
    
    def require_permission(
        self,
        permission: str,
        resource_type: Optional[str] = None,
        get_resource_id: Optional[callable] = None
    ):
        """Decorator to require specific permission"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract user context (implementation depends on your auth setup)
                user_id = kwargs.get('current_user_id') or getattr(kwargs.get('current_user'), 'id', None)
                db = kwargs.get('db')
                
                if not user_id or not db:
                    raise AuthorizationException("Authentication required")
                
                # Get resource ID if function provided
                resource_id = None
                if get_resource_id:
                    resource_id = get_resource_id(*args, **kwargs)
                
                # Check permission
                has_permission = await self.permission_checker.check_permission(
                    user_id=user_id,
                    permission=permission,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    db=db
                )
                
                if not has_permission:
                    raise InsufficientPermissionsException(
                        f"Permission '{permission}' required",
                        required_permission=permission
                    )
                
                return await func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    def require_role(self, required_roles: List[UserRole]):
        """Decorator to require specific roles"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                current_user = kwargs.get('current_user')
                
                if not current_user:
                    raise AuthorizationException("Authentication required")
                
                if current_user.role not in required_roles:
                    raise InsufficientPermissionsException(
                        f"Role {current_user.role} not authorized. Required: {required_roles}"
                    )
                
                return await func(*args, **kwargs)
            
            return wrapper
        return decorator

class AdminPermissionChecker:
    """Admin-specific permission checker"""
    
    def __init__(self, permission_checker: PermissionChecker):
        self.permission_checker = permission_checker
    
    async def check_admin_permission(
        self,
        admin_id: str,
        permission: str,
        hostel_id: Optional[str] = None,
        db: Session = None
    ) -> bool:
        """Check admin-specific permissions"""
        return await self.permission_checker.check_permission(
            user_id=admin_id,
            permission=permission,
            resource_type="admin",
            db=db,
            context={"hostel_id": hostel_id}
        )
    
    async def check_multi_hostel_access(
        self,
        admin_id: str,
        hostel_ids: List[str],
        db: Session
    ) -> Dict[str, bool]:
        """Check admin access to multiple hostels"""
        results = {}
        
        for hostel_id in hostel_ids:
            results[hostel_id] = await self.check_admin_permission(
                admin_id, "view_hostels", hostel_id, db
            )
        
        return results

class SupervisorPermissionChecker:
    """Supervisor-specific permission checker"""
    
    def __init__(self, permission_checker: PermissionChecker):
        self.permission_checker = permission_checker
    
    async def check_supervisor_permission(
        self,
        supervisor_id: str,
        permission: str,
        hostel_id: Optional[str] = None,
        db: Session = None
    ) -> bool:
        """Check supervisor-specific permissions"""
        return await self.permission_checker.check_permission(
            user_id=supervisor_id,
            permission=permission,
            resource_type="supervisor",
            db=db,
            context={"hostel_id": hostel_id}
        )

class StudentPermissionChecker:
    """Student-specific permission checker"""
    
    def __init__(self, permission_checker: PermissionChecker):
        self.permission_checker = permission_checker
    
    async def check_student_permission(
        self,
        student_id: str,
        permission: str,
        resource_id: Optional[str] = None,
        db: Session = None
    ) -> bool:
        """Check student-specific permissions"""
        return await self.permission_checker.check_permission(
            user_id=student_id,
            permission=permission,
            resource_type="student",
            resource_id=resource_id,
            db=db
        )

class HostelPermissionChecker:
    """Hostel-specific permission checker"""
    
    def __init__(self, permission_checker: PermissionChecker):
        self.permission_checker = permission_checker
    
    async def check_hostel_permission(
        self,
        user_id: str,
        hostel_id: str,
        permission: str,
        db: Session
    ) -> bool:
        """Check hostel-specific permissions"""
        return await self.permission_checker.check_permission(
            user_id=user_id,
            permission=permission,
            resource_type="hostel",
            resource_id=hostel_id,
            db=db,
            context={"hostel_id": hostel_id}
        )

class CrossHostelPermissionChecker:
    """Cross-hostel permission checker"""
    
    def __init__(self, permission_checker: PermissionChecker):
        self.permission_checker = permission_checker
    
    async def check_cross_hostel_access(
        self,
        user_id: str,
        source_hostel_id: str,
        target_hostel_id: str,
        permission: str,
        db: Session
    ) -> bool:
        """Check if user can access target hostel from source hostel"""
        user = db.query(User).filter(User.id == user_id).first()
        
        # Super admin can access any hostel
        if user.role == UserRole.SUPER_ADMIN:
            return True
        
        # Check if user has access to target hostel
        return await self.permission_checker.check_permission(
            user_id=user_id,
            permission=permission,
            resource_type="hostel",
            resource_id=target_hostel_id,
            db=db,
            context={"hostel_id": target_hostel_id}
        )

class PermissionCache:
    """Permission result caching utility"""
    
    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self.default_ttl = 300  # 5 minutes
    
    async def cache_permission_result(
        self,
        user_id: str,
        permission: str,
        resource_type: Optional[str],
        resource_id: Optional[str],
        result: bool,
        ttl: Optional[int] = None
    ):
        """Cache permission check result"""
        cache_key = self._build_cache_key(user_id, permission, resource_type, resource_id)
        await self.cache_service.set(
            cache_key,
            "true" if result else "false",
            ttl or self.default_ttl
        )
    
    async def get_cached_permission_result(
        self,
        user_id: str,
        permission: str,
        resource_type: Optional[str],
        resource_id: Optional[str]
    ) -> Optional[bool]:
        """Get cached permission result"""
        cache_key = self._build_cache_key(user_id, permission, resource_type, resource_id)
        result = await self.cache_service.get(cache_key)
        
        if result is None:
            return None
        
        return result == "true"
    
    async def invalidate_user_permissions(self, user_id: str):
        """Invalidate all cached permissions for user"""
        pattern = f"permission:{user_id}:*"
        await self.cache_service.delete_pattern(pattern)
    
    def _build_cache_key(
        self,
        user_id: str,
        permission: str,
        resource_type: Optional[str],
        resource_id: Optional[str]
    ) -> str:
        """Build cache key for permission"""
        return f"permission:{user_id}:{permission}:{resource_type or 'none'}:{resource_id or 'none'}"