"""
Admin permission management service.

Handles permission CRUD, validation, checking, templates,
and bulk operations.
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.admin import AdminPermissionsRepository
from app.models.admin import (
    AdminPermission,
    PermissionTemplate,
    PermissionAuditLog,
)
from app.schemas.admin.admin_permissions import (
    AdminPermissionsUpdate,
    PermissionCheckRequest,
    PermissionCheckResponse,
    BulkPermissionUpdate,
)


class AdminPermissionService(BaseService[AdminPermission, AdminPermissionsRepository]):
    """
    Service for admin permission management.
    
    Responsibilities:
    - Permission CRUD and validation
    - Permission templates
    - Permission checks and authorization
    - Permission audit logging
    - Bulk permission operations
    """
    
    def __init__(
        self,
        repository: AdminPermissionsRepository,
        db_session: Session,
    ):
        """
        Initialize permission service.
        
        Args:
            repository: Permission repository
            db_session: Database session
        """
        super().__init__(repository, db_session)
    
    # =========================================================================
    # Permission Management
    # =========================================================================
    
    def get_admin_permissions(
        self,
        admin_id: UUID,
        hostel_id: Optional[UUID] = None,
    ) -> ServiceResult[AdminPermission]:
        """
        Get permissions for an admin (optionally for specific hostel).
        
        Args:
            admin_id: Admin user ID
            hostel_id: Optional hostel ID for hostel-specific permissions
            
        Returns:
            ServiceResult containing permissions or default permissions
        """
        try:
            permissions = self.repository.get_admin_permissions(admin_id, hostel_id)
            
            if not permissions:
                # Return default permissions
                permissions = self._get_default_permissions(admin_id, hostel_id)
            
            return ServiceResult.success(
                permissions,
                message="Permissions retrieved successfully",
            )
            
        except Exception as e:
            return self._handle_exception(e, "get admin permissions", admin_id)
    
    def update_admin_permissions(
        self,
        admin_id: UUID,
        permission_update: AdminPermissionsUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[AdminPermission]:
        """
        Update admin permissions.
        
        Args:
            admin_id: Admin user ID
            permission_update: Permission updates
            updated_by: ID of user making update
            
        Returns:
            ServiceResult containing updated permissions
        """
        try:
            # Get existing permissions
            existing = self.repository.get_admin_permissions(
                admin_id,
                permission_update.hostel_id,
            )
            
            # Validate permission changes
            validation_result = self._validate_permission_update(
                admin_id,
                permission_update,
            )
            if not validation_result.is_success:
                return validation_result
            
            # Prepare update data
            update_data = permission_update.model_dump(exclude_unset=True)
            
            # Store old state for audit
            old_state = existing.to_dict() if existing else {}
            
            # Update or create
            if existing:
                updated_permissions = self.repository.update(existing.id, update_data)
            else:
                update_data.update({
                    'admin_id': admin_id,
                    'hostel_id': permission_update.hostel_id,
                })
                updated_permissions = self.repository.create(update_data)
            
            self.db.flush()
            
            # Log permission change
            self._log_permission_change(
                admin_id,
                old_state,
                updated_permissions.to_dict(),
                updated_by,
                "updated",
            )
            
            self.db.commit()
            
            self._logger.info(
                "Admin permissions updated",
                extra={
                    "admin_id": str(admin_id),
                    "hostel_id": str(permission_update.hostel_id) if permission_update.hostel_id else None,
                    "updated_by": str(updated_by) if updated_by else None,
                },
            )
            
            return ServiceResult.success(
                updated_permissions,
                message="Permissions updated successfully",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update admin permissions", admin_id)
    
    def apply_permission_template(
        self,
        admin_id: UUID,
        template_name: str,
        hostel_id: Optional[UUID] = None,
        applied_by: Optional[UUID] = None,
    ) -> ServiceResult[AdminPermission]:
        """
        Apply a permission template to admin.
        
        Args:
            admin_id: Admin user ID
            template_name: Name of template to apply
            hostel_id: Optional hostel ID
            applied_by: ID of user applying template
            
        Returns:
            ServiceResult containing updated permissions
        """
        try:
            # Get template
            template = self.repository.get_template_by_name(template_name)
            if not template:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Template '{template_name}' not found",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Get existing permissions for audit
            existing = self.repository.get_admin_permissions(admin_id, hostel_id)
            old_state = existing.to_dict() if existing else {}
            
            # Apply template permissions
            permissions_data = {
                'admin_id': admin_id,
                'hostel_id': hostel_id,
                **template.permissions,
            }
            
            # Update or create
            if existing:
                updated_permissions = self.repository.update(existing.id, permissions_data)
            else:
                updated_permissions = self.repository.create(permissions_data)
            
            self.db.flush()
            
            # Log template application
            self._log_permission_change(
                admin_id,
                old_state,
                updated_permissions.to_dict(),
                applied_by,
                f"applied_template_{template_name}",
            )
            
            self.db.commit()
            
            self._logger.info(
                f"Template '{template_name}' applied to admin",
                extra={
                    "admin_id": str(admin_id),
                    "template_name": template_name,
                    "applied_by": str(applied_by) if applied_by else None,
                },
            )
            
            return ServiceResult.success(
                updated_permissions,
                message=f"Template '{template_name}' applied successfully",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "apply permission template", admin_id)
    
    # =========================================================================
    # Permission Checking
    # =========================================================================
    
    def check_permission(
        self,
        admin_id: UUID,
        permission_key: str,
        hostel_id: Optional[UUID] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[PermissionCheckResponse]:
        """
        Check if admin has a specific permission.
        
        Args:
            admin_id: Admin user ID
            permission_key: Permission to check
            hostel_id: Optional hostel context
            context: Additional context (amounts, priorities, etc.)
            
        Returns:
            ServiceResult containing permission check result
        """
        try:
            # Get permissions
            permissions = self.repository.get_admin_permissions(admin_id, hostel_id)
            
            if not permissions:
                return ServiceResult.success(
                    PermissionCheckResponse(
                        has_permission=False,
                        reason="No permissions found for admin",
                    )
                )
            
            # Check base permission
            has_permission = getattr(permissions, permission_key, False)
            
            if not has_permission:
                return ServiceResult.success(
                    PermissionCheckResponse(
                        has_permission=False,
                        reason=f"Permission '{permission_key}' not granted",
                    )
                )
            
            # Apply contextual checks
            if context:
                context_check = self._check_permission_context(
                    permissions,
                    permission_key,
                    context,
                )
                if not context_check.is_success:
                    return ServiceResult.success(
                        PermissionCheckResponse(
                            has_permission=False,
                            reason=context_check.primary_error.message,
                        )
                    )
            
            return ServiceResult.success(
                PermissionCheckResponse(
                    has_permission=True,
                    reason="Permission granted",
                )
            )
            
        except Exception as e:
            return self._handle_exception(e, "check permission", admin_id)
    
    def check_multiple_permissions(
        self,
        admin_id: UUID,
        permission_keys: List[str],
        hostel_id: Optional[UUID] = None,
        require_all: bool = True,
    ) -> ServiceResult[Dict[str, bool]]:
        """
        Check multiple permissions at once.
        
        Args:
            admin_id: Admin user ID
            permission_keys: List of permissions to check
            hostel_id: Optional hostel context
            require_all: Whether all permissions must be granted
            
        Returns:
            ServiceResult containing permission check results
        """
        try:
            permissions = self.repository.get_admin_permissions(admin_id, hostel_id)
            
            if not permissions:
                results = {key: False for key in permission_keys}
            else:
                results = {
                    key: getattr(permissions, key, False)
                    for key in permission_keys
                }
            
            # Check if requirement met
            if require_all and not all(results.values()):
                denied_permissions = [k for k, v in results.items() if not v]
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.INSUFFICIENT_PERMISSIONS,
                        message="Not all required permissions granted",
                        details={
                            "results": results,
                            "denied": denied_permissions,
                        },
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            return ServiceResult.success(
                results,
                message="Permission check completed",
                metadata={"total": len(permission_keys), "granted": sum(results.values())},
            )
            
        except Exception as e:
            return self._handle_exception(e, "check multiple permissions", admin_id)
    
    def has_any_permission(
        self,
        admin_id: UUID,
        permission_keys: List[str],
        hostel_id: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Check if admin has at least one of the specified permissions.
        
        Args:
            admin_id: Admin user ID
            permission_keys: List of permissions to check
            hostel_id: Optional hostel context
            
        Returns:
            ServiceResult with True if any permission is granted
        """
        result = self.check_multiple_permissions(
            admin_id,
            permission_keys,
            hostel_id,
            require_all=False,
        )
        
        if result.is_success:
            has_any = any(result.data.values())
            return ServiceResult.success(has_any)
        
        return result
    
    # =========================================================================
    # Template Management
    # =========================================================================
    
    def create_permission_template(
        self,
        template_name: str,
        permissions: Dict[str, Any],
        description: Optional[str] = None,
        is_system: bool = False,
    ) -> ServiceResult[PermissionTemplate]:
        """
        Create a new permission template.
        
        Args:
            template_name: Template name
            permissions: Permission configuration
            description: Template description
            is_system: Whether this is a system template
            
        Returns:
            ServiceResult containing created template
        """
        try:
            # Check if template exists
            existing = self.repository.get_template_by_name(template_name)
            if existing:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.ALREADY_EXISTS,
                        message=f"Template '{template_name}' already exists",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Create template
            template_data = {
                'template_name': template_name,
                'permissions': permissions,
                'description': description,
                'is_system': is_system,
            }
            
            template = self.repository.create_template(template_data)
            self.db.commit()
            
            self._logger.info(
                f"Permission template created: {template_name}",
                extra={"template_name": template_name, "is_system": is_system},
            )
            
            return ServiceResult.success(
                template,
                message="Permission template created successfully",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "create permission template")
    
    def update_permission_template(
        self,
        template_id: UUID,
        permissions: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
    ) -> ServiceResult[PermissionTemplate]:
        """
        Update an existing permission template.
        
        Args:
            template_id: Template ID
            permissions: New permission configuration
            description: New description
            
        Returns:
            ServiceResult containing updated template
        """
        try:
            template = self.repository.get_template_by_id(template_id)
            if not template:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Template not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Prevent modification of system templates
            if template.is_system:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.BUSINESS_RULE_VIOLATION,
                        message="Cannot modify system templates",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            update_data = {}
            if permissions is not None:
                update_data['permissions'] = permissions
            if description is not None:
                update_data['description'] = description
            
            if not update_data:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="No update data provided",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            updated_template = self.repository.update_template(template_id, update_data)
            self.db.commit()
            
            return ServiceResult.success(
                updated_template,
                message="Template updated successfully",
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update permission template", template_id)
    
    def get_all_templates(
        self,
        include_system: bool = True,
    ) -> ServiceResult[List[PermissionTemplate]]:
        """
        Get all permission templates.
        
        Args:
            include_system: Whether to include system templates
            
        Returns:
            ServiceResult containing templates
        """
        try:
            templates = self.repository.get_all_templates(include_system)
            
            return ServiceResult.success(
                templates,
                message="Templates retrieved successfully",
                metadata={"count": len(templates)},
            )
            
        except Exception as e:
            return self._handle_exception(e, "get all templates")
    
    def delete_permission_template(
        self,
        template_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Delete a permission template.
        
        Args:
            template_id: Template ID
            
        Returns:
            ServiceResult indicating success or error
        """
        try:
            template = self.repository.get_template_by_id(template_id)
            if not template:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Template not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            if template.is_system:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.BUSINESS_RULE_VIOLATION,
                        message="Cannot delete system templates",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            self.repository.delete_template(template_id)
            self.db.commit()
            
            return ServiceResult.success(True, message="Template deleted successfully")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "delete permission template", template_id)
    
    # =========================================================================
    # Bulk Operations
    # =========================================================================
    
    def bulk_update_permissions(
        self,
        bulk_update: BulkPermissionUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Update permissions for multiple admins.
        
        Args:
            bulk_update: Bulk update request
            updated_by: ID of user making updates
            
        Returns:
            ServiceResult containing update summary
        """
        try:
            summary = {
                "total": len(bulk_update.admin_ids),
                "success": 0,
                "failed": 0,
                "errors": [],
            }
            
            for admin_id in bulk_update.admin_ids:
                result = self.update_admin_permissions(
                    admin_id,
                    AdminPermissionsUpdate(
                        permissions=bulk_update.permissions,
                        hostel_id=None,  # Global permissions
                    ),
                    updated_by,
                )
                
                if result.is_success:
                    summary["success"] += 1
                else:
                    summary["failed"] += 1
                    summary["errors"].append({
                        "admin_id": str(admin_id),
                        "error": result.primary_error.message,
                    })
            
            self.db.commit()
            
            message = f"Bulk update completed: {summary['success']} succeeded, {summary['failed']} failed"
            
            self._logger.info(
                "Bulk permission update completed",
                extra=summary,
            )
            
            return ServiceResult.success(summary, message=message)
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "bulk update permissions")
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _validate_permission_update(
        self,
        admin_id: UUID,
        permission_update: AdminPermissionsUpdate,
    ) -> ServiceResult[None]:
        """
        Validate permission update request.
        
        Can be extended to include:
        - Permission compatibility checks
        - Hierarchy validation
        - Business rule enforcement
        
        Args:
            admin_id: Admin user ID
            permission_update: Permission update data
            
        Returns:
            ServiceResult indicating validation result
        """
        # Placeholder for future validation logic
        return ServiceResult.success(None)
    
    def _check_permission_context(
        self,
        permissions: AdminPermission,
        permission_key: str,
        context: Dict[str, Any],
    ) -> ServiceResult[None]:
        """
        Check contextual permission constraints.
        
        Examples:
        - Amount thresholds for financial permissions
        - Priority levels for override permissions
        - Time-based restrictions
        
        Args:
            permissions: Admin permissions
            permission_key: Permission being checked
            context: Context data
            
        Returns:
            ServiceResult indicating context check result
        """
        # Placeholder for contextual validation
        # Can be extended based on business requirements
        return ServiceResult.success(None)
    
    def _log_permission_change(
        self,
        admin_id: UUID,
        old_state: Dict[str, Any],
        new_state: Dict[str, Any],
        changed_by: Optional[UUID],
        action: str,
    ) -> None:
        """
        Log permission change to audit log.
        
        Args:
            admin_id: Admin whose permissions changed
            old_state: Previous permission state
            new_state: New permission state
            changed_by: User who made the change
            action: Action performed
        """
        try:
            audit_data = {
                'admin_id': admin_id,
                'changed_by': changed_by,
                'action': action,
                'permissions_before': old_state,
                'permissions_after': new_state,
                'timestamp': datetime.utcnow(),
            }
            
            self.repository.create_audit_log(audit_data)
            self.db.flush()
            
        except Exception as e:
            self._logger.error(
                f"Failed to log permission change: {str(e)}",
                exc_info=True,
                extra={"admin_id": str(admin_id)},
            )
    
    def _get_default_permissions(
        self,
        admin_id: UUID,
        hostel_id: Optional[UUID],
    ) -> AdminPermission:
        """
        Get default permissions for an admin.
        
        Args:
            admin_id: Admin user ID
            hostel_id: Optional hostel ID
            
        Returns:
            Default AdminPermission object with all permissions False
        """
        return AdminPermission(
            admin_id=admin_id,
            hostel_id=hostel_id,
            # All permission fields default to False
        )