"""
Admin user management service.

Handles admin user lifecycle, profile management, status changes,
hierarchy validation, and security operations.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.admin import AdminUserRepository
from app.repositories.user import UserRepository
from app.models.admin import AdminUser, AdminProfile, AdminSession
from app.models.base.enums import UserRole
from app.schemas.admin.admin_user import (
    AdminUserCreate,
    AdminUserUpdate,
    AdminUserResponse,
    AdminUserDetail,
)
from app.core1.security.password_hasher import PasswordHasher
from app.core1.security.jwt_handler import JWTManager


class AdminUserService(BaseService[AdminUser, AdminUserRepository]):
    """
    Service for admin user management operations.
    
    Responsibilities:
    - Admin user creation and lifecycle management
    - Profile management and updates
    - Status transitions (active/suspended/inactive)
    - Hierarchy validation and supervision
    - Security and session management
    - Admin analytics and search
    """
    
    # Class constants
    ADMIN_ROLES = frozenset([UserRole.ADMIN, UserRole.SUPER_ADMIN])
    
    def __init__(
        self,
        repository: AdminUserRepository,
        user_repository: UserRepository,
        db_session: Session,
    ):
        """
        Initialize admin user service.
        
        Args:
            repository: Admin user repository
            user_repository: Base user repository
            db_session: Database session
        """
        super().__init__(repository, db_session)
        self.user_repository = user_repository
        self.password_hasher = PasswordHasher()
        self.jwt_manager = JWTManager()
    
    # =========================================================================
    # Admin User Creation and Management
    # =========================================================================
    
    def create_admin_user(
        self,
        create_data: AdminUserCreate,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[AdminUserDetail]:
        """
        Create a new admin user with profile.
        
        Validates:
        - Role is admin-level
        - Email uniqueness
        - Supervisor hierarchy (if applicable)
        
        Args:
            create_data: Admin creation data
            created_by: ID of user creating the admin
            
        Returns:
            ServiceResult containing created admin detail or error
        """
        try:
            # Validate admin role
            validation_result = self._validate_admin_role(create_data.role)
            if not validation_result.is_success:
                return validation_result
            
            # Check email uniqueness
            if self.user_repository.find_by_email(create_data.email):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.ALREADY_EXISTS,
                        message="User with this email already exists",
                        field="email",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Validate supervisor hierarchy
            if create_data.supervisor_id:
                hierarchy_check = self._validate_supervisor_hierarchy(
                    create_data.supervisor_id,
                    create_data.role,
                )
                if not hierarchy_check.is_success:
                    return hierarchy_check
            
            # Create base user
            user = self._create_base_user(create_data)
            self.db.flush()
            
            # Create admin user
            admin = self._create_admin_entity(user.id, create_data)
            self.db.flush()
            
            # Create profile if data provided
            if create_data.profile_data:
                self._create_admin_profile(admin.id, create_data.profile_data)
                self.db.flush()
            
            self.db.commit()
            
            # Fetch complete details
            admin_detail = self.repository.get_admin_with_details(admin.id)
            
            self._logger.info(
                "Admin user created successfully",
                extra={
                    "admin_id": str(admin.id),
                    "user_id": str(user.id),
                    "email": create_data.email,
                    "role": create_data.role.value,
                    "created_by": str(created_by) if created_by else None,
                },
            )
            
            return ServiceResult.success(
                admin_detail,
                message="Admin user created successfully",
            )
            
        except IntegrityError as e:
            self.db.rollback()
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.CONSTRAINT_VIOLATION,
                    message="Database constraint violation",
                    details={"error": str(e.orig) if hasattr(e, 'orig') else str(e)},
                    severity=ErrorSeverity.ERROR,
                )
            )
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "create admin user")
    
    def update_admin_user(
        self,
        admin_id: UUID,
        update_data: AdminUserUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[AdminUserDetail]:
        """
        Update admin user information.
        
        Validates:
        - Admin exists
        - No self-supervision
        - Supervisor hierarchy rules
        
        Args:
            admin_id: Admin user ID
            update_data: Update data
            updated_by: ID of user making update
            
        Returns:
            ServiceResult containing updated admin or error
        """
        try:
            # Fetch existing admin
            admin = self.repository.get_by_id(admin_id)
            if not admin:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Admin user not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Validate supervisor changes
            if update_data.supervisor_id is not None:
                supervisor_validation = self._validate_supervisor_change(
                    admin_id,
                    update_data.supervisor_id,
                    admin.user.role,
                )
                if not supervisor_validation.is_success:
                    return supervisor_validation
            
            # Update admin entity
            admin_update_dict = update_data.model_dump(
                exclude_unset=True,
                exclude={'full_name', 'email', 'phone'}
            )
            if admin_update_dict:
                self.repository.update(admin_id, admin_update_dict)
                self.db.flush()
            
            # Update base user if needed
            user_update_dict = self._extract_user_updates(update_data)
            if user_update_dict:
                self.user_repository.update(admin.user_id, user_update_dict)
                self.db.flush()
            
            self.db.commit()
            
            # Fetch updated details
            admin_detail = self.repository.get_admin_with_details(admin_id)
            
            self._logger.info(
                "Admin user updated successfully",
                extra={
                    "admin_id": str(admin_id),
                    "updated_by": str(updated_by) if updated_by else None,
                    "fields_updated": list(admin_update_dict.keys()) + list(user_update_dict.keys()),
                },
            )
            
            return ServiceResult.success(
                admin_detail,
                message="Admin user updated successfully",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update admin user", admin_id)
    
    # =========================================================================
    # Status Management
    # =========================================================================
    
    def activate_admin(
        self,
        admin_id: UUID,
        activated_by: Optional[UUID] = None,
    ) -> ServiceResult[AdminUserDetail]:
        """
        Activate an admin user.
        
        Args:
            admin_id: Admin user ID
            activated_by: ID of user performing activation
            
        Returns:
            ServiceResult containing updated admin or error
        """
        return self._change_admin_status(
            admin_id,
            "active",
            activated_by,
            "Admin activated successfully",
        )
    
    def suspend_admin(
        self,
        admin_id: UUID,
        reason: str,
        suspended_by: Optional[UUID] = None,
    ) -> ServiceResult[AdminUserDetail]:
        """
        Suspend an admin user and revoke all active sessions.
        
        Args:
            admin_id: Admin user ID
            reason: Suspension reason
            suspended_by: ID of user performing suspension
            
        Returns:
            ServiceResult containing updated admin or error
        """
        try:
            # Change status
            result = self._change_admin_status(
                admin_id,
                "suspended",
                suspended_by,
                f"Admin suspended: {reason}",
            )
            
            if result.is_success:
                # Revoke all active sessions
                self.repository.revoke_all_sessions(admin_id)
                self.db.commit()
                
                self._logger.warning(
                    "Admin suspended and sessions revoked",
                    extra={
                        "admin_id": str(admin_id),
                        "reason": reason,
                        "suspended_by": str(suspended_by) if suspended_by else None,
                    },
                )
            
            return result
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "suspend admin", admin_id)
    
    def deactivate_admin(
        self,
        admin_id: UUID,
        deactivated_by: Optional[UUID] = None,
    ) -> ServiceResult[AdminUserDetail]:
        """
        Deactivate an admin user.
        
        Args:
            admin_id: Admin user ID
            deactivated_by: ID of user performing deactivation
            
        Returns:
            ServiceResult containing updated admin or error
        """
        return self._change_admin_status(
            admin_id,
            "inactive",
            deactivated_by,
            "Admin deactivated successfully",
        )
    
    # =========================================================================
    # Profile Management
    # =========================================================================
    
    def update_admin_profile(
        self,
        admin_id: UUID,
        profile_data: Dict[str, Any],
    ) -> ServiceResult[AdminProfile]:
        """
        Update admin profile information.
        
        Args:
            admin_id: Admin user ID
            profile_data: Profile data to update
            
        Returns:
            ServiceResult containing updated profile or error
        """
        try:
            # Verify admin exists
            admin = self.repository.get_by_id(admin_id)
            if not admin:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Admin user not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Get or create profile
            profile = self.repository.get_admin_profile(admin_id)
            
            if profile:
                updated_profile = self.repository.update_profile(
                    profile.id,
                    profile_data,
                )
            else:
                profile_data['admin_user_id'] = admin_id
                updated_profile = self.repository.create_profile(profile_data)
            
            self.db.commit()
            
            self._logger.info(
                "Admin profile updated",
                extra={"admin_id": str(admin_id)},
            )
            
            return ServiceResult.success(
                updated_profile,
                message="Admin profile updated successfully",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update admin profile", admin_id)
    
    def get_admin_profile(
        self,
        admin_id: UUID,
    ) -> ServiceResult[Optional[AdminProfile]]:
        """
        Get admin profile.
        
        Args:
            admin_id: Admin user ID
            
        Returns:
            ServiceResult containing profile or None
        """
        try:
            profile = self.repository.get_admin_profile(admin_id)
            return ServiceResult.success(
                profile,
                message="Profile retrieved successfully" if profile else "No profile found",
            )
        except Exception as e:
            return self._handle_exception(e, "get admin profile", admin_id)
    
    # =========================================================================
    # Hierarchy and Permissions
    # =========================================================================
    
    def get_admin_hierarchy(
        self,
        admin_id: UUID,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get admin's position in organizational hierarchy.
        
        Args:
            admin_id: Admin user ID
            
        Returns:
            ServiceResult containing hierarchy information
        """
        try:
            hierarchy = self.repository.get_admin_hierarchy(admin_id)
            
            return ServiceResult.success(
                hierarchy,
                message="Hierarchy retrieved successfully",
            )
            
        except Exception as e:
            return self._handle_exception(e, "get admin hierarchy", admin_id)
    
    def get_subordinates(
        self,
        admin_id: UUID,
        include_indirect: bool = False,
    ) -> ServiceResult[List[AdminUserResponse]]:
        """
        Get list of admins supervised by this admin.
        
        Args:
            admin_id: Admin user ID
            include_indirect: Include indirect reports
            
        Returns:
            ServiceResult containing list of subordinates
        """
        try:
            subordinates = self.repository.get_subordinates(
                admin_id,
                include_indirect=include_indirect,
            )
            
            return ServiceResult.success(
                subordinates,
                message="Subordinates retrieved successfully",
                metadata={
                    "count": len(subordinates),
                    "include_indirect": include_indirect,
                },
            )
            
        except Exception as e:
            return self._handle_exception(e, "get subordinates", admin_id)
    
    # =========================================================================
    # Search and Analytics
    # =========================================================================
    
    def search_admins(
        self,
        search_query: Optional[str] = None,
        role: Optional[UserRole] = None,
        status: Optional[str] = None,
        department: Optional[str] = None,
        supervisor_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> ServiceResult[List[AdminUserResponse]]:
        """
        Search and filter admin users.
        
        Args:
            search_query: Text search query
            role: Filter by role
            status: Filter by status
            department: Filter by department
            supervisor_id: Filter by supervisor
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            ServiceResult containing matching admins
        """
        try:
            admins = self.repository.search_admins(
                search_query=search_query,
                role=role,
                status=status,
                department=department,
                supervisor_id=supervisor_id,
                skip=skip,
                limit=limit,
            )
            
            return ServiceResult.success(
                admins,
                message="Search completed successfully",
                metadata={
                    "count": len(admins),
                    "skip": skip,
                    "limit": limit,
                    "has_more": len(admins) == limit,
                },
            )
            
        except Exception as e:
            return self._handle_exception(e, "search admins")
    
    def get_admin_statistics(self) -> ServiceResult[Dict[str, Any]]:
        """
        Get overall admin user statistics.
        
        Returns:
            ServiceResult containing statistics
        """
        try:
            stats = self.repository.get_admin_statistics()
            
            return ServiceResult.success(
                stats,
                message="Statistics retrieved successfully",
            )
            
        except Exception as e:
            return self._handle_exception(e, "get admin statistics")
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _validate_admin_role(self, role: UserRole) -> ServiceResult[None]:
        """Validate that role is admin-level."""
        if role not in self.ADMIN_ROLES:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid admin role: {role.value}. Must be ADMIN or SUPER_ADMIN.",
                    field="role",
                    severity=ErrorSeverity.WARNING,
                )
            )
        return ServiceResult.success(None)
    
    def _create_base_user(self, create_data: AdminUserCreate):
        """Create base user entity."""
        user_data = {
            "email": create_data.email,
            "phone": create_data.phone,
            "full_name": create_data.full_name,
            "role": create_data.role,
            "password_hash": self.password_hasher.hash(create_data.password),
            "is_active": True,
        }
        return self.user_repository.create(user_data)
    
    def _create_admin_entity(self, user_id: UUID, create_data: AdminUserCreate) -> AdminUser:
        """Create admin entity."""
        admin_data = {
            "user_id": user_id,
            "employee_id": create_data.employee_id,
            "department": create_data.department,
            "designation": create_data.designation,
            "supervisor_id": create_data.supervisor_id,
            "can_manage_multiple_hostels": create_data.can_manage_multiple_hostels,
            "status": "active",
        }
        return self.repository.create(admin_data)
    
    def _create_admin_profile(self, admin_id: UUID, profile_data: Dict[str, Any]) -> AdminProfile:
        """Create admin profile."""
        profile_data['admin_user_id'] = admin_id
        return self.repository.create_profile(profile_data)
    
    def _validate_supervisor_change(
        self,
        admin_id: UUID,
        supervisor_id: UUID,
        admin_role: UserRole,
    ) -> ServiceResult[None]:
        """Validate supervisor change."""
        # Prevent self-supervision
        if supervisor_id == admin_id:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Admin cannot supervise themselves",
                    field="supervisor_id",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        # Validate hierarchy
        return self._validate_supervisor_hierarchy(supervisor_id, admin_role)
    
    def _validate_supervisor_hierarchy(
        self,
        supervisor_id: UUID,
        admin_role: UserRole,
    ) -> ServiceResult[None]:
        """
        Validate supervisor hierarchy rules.
        
        Rules:
        - Super Admin can supervise anyone
        - Admin can supervise other Admins but not Super Admins
        """
        try:
            supervisor = self.repository.get_by_id(supervisor_id)
            if not supervisor:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Supervisor not found",
                        field="supervisor_id",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Super admin can supervise anyone
            if supervisor.user.role == UserRole.SUPER_ADMIN:
                return ServiceResult.success(None)
            
            # Admin cannot supervise super admin
            if supervisor.user.role == UserRole.ADMIN and admin_role == UserRole.SUPER_ADMIN:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.BUSINESS_RULE_VIOLATION,
                        message="Admin cannot supervise Super Admin",
                        field="supervisor_id",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            return ServiceResult.success(None)
            
        except Exception as e:
            return self._handle_exception(e, "validate supervisor hierarchy")
    
    def _extract_user_updates(self, update_data: AdminUserUpdate) -> Dict[str, Any]:
        """Extract user-level fields from update data."""
        user_update = {}
        
        if update_data.full_name is not None:
            user_update['full_name'] = update_data.full_name
        if update_data.email is not None:
            user_update['email'] = update_data.email
        if update_data.phone is not None:
            user_update['phone'] = update_data.phone
        
        return user_update
    
    def _change_admin_status(
        self,
        admin_id: UUID,
        new_status: str,
        changed_by: Optional[UUID],
        success_message: str,
    ) -> ServiceResult[AdminUserDetail]:
        """
        Internal method to change admin status.
        
        Args:
            admin_id: Admin user ID
            new_status: New status value (active/suspended/inactive)
            changed_by: ID of user making change
            success_message: Success message for logging
            
        Returns:
            ServiceResult containing updated admin or error
        """
        try:
            admin = self.repository.get_by_id(admin_id)
            if not admin:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Admin user not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Update admin status
            self.repository.update(admin_id, {"status": new_status})
            
            # Update base user active status
            is_active = (new_status == "active")
            self.user_repository.update(admin.user_id, {"is_active": is_active})
            
            self.db.commit()
            
            # Fetch updated details
            admin_detail = self.repository.get_admin_with_details(admin_id)
            
            self._logger.info(
                f"Admin status changed to {new_status}",
                extra={
                    "admin_id": str(admin_id),
                    "old_status": admin.status,
                    "new_status": new_status,
                    "changed_by": str(changed_by) if changed_by else None,
                },
            )
            
            return ServiceResult.success(admin_detail, message=success_message)
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(
                e,
                f"change admin status to {new_status}",
                admin_id,
            )