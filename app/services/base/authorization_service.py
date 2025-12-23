"""
Authorization (permission) service for role-based access control.
"""

from typing import Optional, Dict, Any, List, Set
from uuid import UUID
from functools import lru_cache

from sqlalchemy.orm import Session

from app.services.base.base_service import BaseService
from app.services.base.service_result import ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.admin.admin_permissions_repository import AdminPermissionsRepository
from app.schemas.admin.admin_permissions import PermissionCheckResponse


class AuthorizationService(BaseService[object, AdminPermissionsRepository]):
    """
    Provides comprehensive permission checking with:
    - Role-based permissions
    - Resource-based permissions
    - Context-aware authorization
    - Permission caching for performance
    """

    def __init__(
        self,
        repository: AdminPermissionsRepository,
        db_session: Session,
        cache_ttl: int = 300,  # 5 minutes default cache
    ):
        """
        Initialize authorization service.
        
        Args:
            repository: Admin permissions repository
            db_session: SQLAlchemy database session
            cache_ttl: Cache time-to-live in seconds
        """
        super().__init__(repository, db_session)
        self.cache_ttl = cache_ttl

    # -------------------------------------------------------------------------
    # Permission Checking
    # -------------------------------------------------------------------------

    def has_permission(
        self,
        admin_id: UUID,
        permission_key: str,
        hostel_id: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[PermissionCheckResponse]:
        """
        Check if admin has a specific permission.
        
        Args:
            admin_id: UUID of the admin user
            permission_key: Permission identifier to check
            hostel_id: Optional hostel context for scoped permissions
            context: Additional context for contextual authorization
            
        Returns:
            ServiceResult containing permission check response
        """
        try:
            # Attempt to get cached result
            cache_key = self._build_cache_key(admin_id, permission_key, hostel_id)
            
            # Get permissions from repository
            perms = self.repository.get_admin_permissions(admin_id, hostel_id)
            
            if not perms:
                return ServiceResult.success(
                    PermissionCheckResponse(
                        has_permission=False,
                        reason="No permissions found for admin",
                        admin_id=admin_id,
                        permission_key=permission_key,
                    ),
                )
            
            # Check base permission
            has_perm = bool(getattr(perms, permission_key, False))
            
            # Apply contextual checks if provided
            if has_perm and context:
                has_perm = self._apply_contextual_checks(
                    admin_id,
                    permission_key,
                    context,
                    perms,
                )
            
            response = PermissionCheckResponse(
                has_permission=has_perm,
                reason="Permission granted" if has_perm else "Permission denied",
                admin_id=admin_id,
                permission_key=permission_key,
                hostel_id=hostel_id,
            )
            
            self._logger.debug(
                f"Permission check: {permission_key} for admin {admin_id} = {has_perm}",
                extra={
                    "admin_id": str(admin_id),
                    "permission": permission_key,
                    "granted": has_perm,
                    "hostel_id": str(hostel_id) if hostel_id else None,
                }
            )
            
            return ServiceResult.success(response)
            
        except Exception as e:
            return self._handle_exception(
                e,
                "check permission",
                admin_id,
                severity=ErrorSeverity.ERROR,
            )

    def has_any_permission(
        self,
        admin_id: UUID,
        permission_keys: List[str],
        hostel_id: Optional[UUID] = None,
    ) -> ServiceResult[PermissionCheckResponse]:
        """
        Check if admin has ANY of the specified permissions.
        
        Args:
            admin_id: UUID of the admin user
            permission_keys: List of permission identifiers
            hostel_id: Optional hostel context
            
        Returns:
            ServiceResult with permission check response
        """
        try:
            perms = self.repository.get_admin_permissions(admin_id, hostel_id)
            
            if not perms:
                return ServiceResult.success(
                    PermissionCheckResponse(
                        has_permission=False,
                        reason="No permissions found",
                        admin_id=admin_id,
                    )
                )
            
            granted_perms = []
            for perm_key in permission_keys:
                if bool(getattr(perms, perm_key, False)):
                    granted_perms.append(perm_key)
            
            has_any = len(granted_perms) > 0
            
            return ServiceResult.success(
                PermissionCheckResponse(
                    has_permission=has_any,
                    reason=f"Granted permissions: {granted_perms}" if has_any else "No matching permissions",
                    admin_id=admin_id,
                    granted_permissions=granted_perms,
                )
            )
            
        except Exception as e:
            return self._handle_exception(e, "check any permission", admin_id)

    def has_all_permissions(
        self,
        admin_id: UUID,
        permission_keys: List[str],
        hostel_id: Optional[UUID] = None,
    ) -> ServiceResult[PermissionCheckResponse]:
        """
        Check if admin has ALL of the specified permissions.
        
        Args:
            admin_id: UUID of the admin user
            permission_keys: List of permission identifiers
            hostel_id: Optional hostel context
            
        Returns:
            ServiceResult with permission check response
        """
        try:
            perms = self.repository.get_admin_permissions(admin_id, hostel_id)
            
            if not perms:
                return ServiceResult.success(
                    PermissionCheckResponse(
                        has_permission=False,
                        reason="No permissions found",
                        admin_id=admin_id,
                    )
                )
            
            missing_perms = []
            for perm_key in permission_keys:
                if not bool(getattr(perms, perm_key, False)):
                    missing_perms.append(perm_key)
            
            has_all = len(missing_perms) == 0
            
            return ServiceResult.success(
                PermissionCheckResponse(
                    has_permission=has_all,
                    reason="All permissions granted" if has_all else f"Missing: {missing_perms}",
                    admin_id=admin_id,
                    missing_permissions=missing_perms,
                )
            )
            
        except Exception as e:
            return self._handle_exception(e, "check all permissions", admin_id)

    def require_permission(
        self,
        admin_id: UUID,
        permission_key: str,
        hostel_id: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[bool]:
        """
        Enforce permission requirement - returns failure if not granted.
        
        Args:
            admin_id: UUID of the admin user
            permission_key: Required permission identifier
            hostel_id: Optional hostel context
            context: Additional authorization context
            
        Returns:
            ServiceResult success if granted, failure otherwise
        """
        check = self.has_permission(admin_id, permission_key, hostel_id, context)
        
        if not check.is_success:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.INTERNAL_ERROR,
                    message="Failed to check permissions",
                    severity=ErrorSeverity.ERROR,
                )
            )
        
        if not (check.data and check.data.has_permission):
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                    message=f"Permission '{permission_key}' is required",
                    details={
                        "admin_id": str(admin_id),
                        "permission": permission_key,
                        "reason": check.data.reason if check.data else "Unknown",
                    },
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(True, message="Permission verified")

    def require_any_permission(
        self,
        admin_id: UUID,
        permission_keys: List[str],
        hostel_id: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Require at least one of the specified permissions.
        
        Args:
            admin_id: UUID of the admin user
            permission_keys: List of acceptable permissions
            hostel_id: Optional hostel context
            
        Returns:
            ServiceResult success if any permission granted, failure otherwise
        """
        check = self.has_any_permission(admin_id, permission_keys, hostel_id)
        
        if not check.is_success or not (check.data and check.data.has_permission):
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                    message=f"At least one of these permissions required: {permission_keys}",
                    details={"admin_id": str(admin_id)},
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(True)

    # -------------------------------------------------------------------------
    # Permission Management
    # -------------------------------------------------------------------------

    def get_admin_permissions(
        self,
        admin_id: UUID,
        hostel_id: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, bool]]:
        """
        Get all permissions for an admin.
        
        Args:
            admin_id: UUID of the admin user
            hostel_id: Optional hostel context
            
        Returns:
            ServiceResult containing permission dictionary
        """
        try:
            perms = self.repository.get_admin_permissions(admin_id, hostel_id)
            
            if not perms:
                return ServiceResult.success({}, message="No permissions found")
            
            # Convert to dictionary
            perm_dict = {
                key: bool(getattr(perms, key, False))
                for key in dir(perms)
                if not key.startswith('_') and not callable(getattr(perms, key))
            }
            
            return ServiceResult.success(
                perm_dict,
                metadata={
                    "admin_id": str(admin_id),
                    "hostel_id": str(hostel_id) if hostel_id else None,
                    "total_permissions": len(perm_dict),
                }
            )
            
        except Exception as e:
            return self._handle_exception(e, "get admin permissions", admin_id)

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def _apply_contextual_checks(
        self,
        admin_id: UUID,
        permission_key: str,
        context: Dict[str, Any],
        permissions: Any,
    ) -> bool:
        """
        Apply contextual authorization rules.
        Override in subclasses for custom logic.
        
        Args:
            admin_id: Admin user ID
            permission_key: Permission being checked
            context: Authorization context
            permissions: Permission object
            
        Returns:
            True if contextual checks pass
        """
        # Example contextual checks:
        # - Time-based restrictions
        # - Resource ownership
        # - Hierarchical permissions
        
        # Default implementation: no additional restrictions
        return True

    def _build_cache_key(
        self,
        admin_id: UUID,
        permission_key: str,
        hostel_id: Optional[UUID] = None,
    ) -> str:
        """
        Build cache key for permission check.
        
        Args:
            admin_id: Admin user ID
            permission_key: Permission identifier
            hostel_id: Optional hostel ID
            
        Returns:
            Cache key string
        """
        parts = [str(admin_id), permission_key]
        if hostel_id:
            parts.append(str(hostel_id))
        return ":".join(parts)