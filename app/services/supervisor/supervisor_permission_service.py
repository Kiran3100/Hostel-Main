"""
Supervisor Permission Service

Manages supervisor permissions and permission checks with role-based access control.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.supervisor import SupervisorPermissionsRepository
from app.schemas.supervisor import (
    SupervisorPermissions,
    PermissionUpdate,
    PermissionCheckRequest,
    PermissionCheckResponse,
)
from app.core1.exceptions import ValidationException

logger = logging.getLogger(__name__)


class SupervisorPermissionService:
    """
    High-level service for supervisor permissions.

    Responsibilities:
    - Get/update supervisor permissions with validation
    - Apply permission templates (role-based)
    - Check if a supervisor has a given permission in a context
    - Bulk permission operations
    - Permission audit logging

    Example:
        >>> service = SupervisorPermissionService(permissions_repo)
        >>> permissions = service.get_permissions(db, supervisor_id)
        >>> result = service.check_permission(db, supervisor_id, check_request)
    """

    def __init__(
        self,
        permissions_repo: SupervisorPermissionsRepository,
    ) -> None:
        """
        Initialize the supervisor permission service.

        Args:
            permissions_repo: Repository for permissions operations
        """
        if not permissions_repo:
            raise ValueError("permissions_repo cannot be None")
            
        self.permissions_repo = permissions_repo

    # -------------------------------------------------------------------------
    # Get/Set Permissions
    # -------------------------------------------------------------------------

    def get_permissions(
        self,
        db: Session,
        supervisor_id: UUID,
    ) -> SupervisorPermissions:
        """
        Retrieve supervisor's permissions.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor

        Returns:
            SupervisorPermissions: Supervisor's permissions object

        Raises:
            ValidationException: If permissions not configured or validation fails

        Example:
            >>> permissions = service.get_permissions(db, supervisor_id)
            >>> print(permissions.can_approve_leaves, permissions.max_approval_amount)
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")

        try:
            logger.debug(f"Getting permissions for supervisor: {supervisor_id}")
            
            obj = self.permissions_repo.get_by_supervisor_id(db, supervisor_id)
            if not obj:
                logger.warning(
                    f"Permissions not configured for supervisor: {supervisor_id}"
                )
                raise ValidationException(
                    f"Permissions not configured for supervisor {supervisor_id}"
                )
            
            return SupervisorPermissions.model_validate(obj)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get permissions for supervisor {supervisor_id}: {str(e)}"
            )
            raise ValidationException(
                f"Failed to retrieve permissions: {str(e)}"
            )

    def update_permissions(
        self,
        db: Session,
        supervisor_id: UUID,
        update: PermissionUpdate,
    ) -> SupervisorPermissions:
        """
        Partially update supervisor's permissions.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            update: Permission update data

        Returns:
            SupervisorPermissions: Updated permissions object

        Raises:
            ValidationException: If validation fails or permissions not found

        Example:
            >>> update = PermissionUpdate(
            ...     permissions={"can_approve_leaves": True, "max_approval_amount": 5000},
            ...     reason="Promotion to senior supervisor"
            ... )
            >>> updated = service.update_permissions(db, supervisor_id, update)
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")
        
        if not update:
            raise ValidationException("Update data is required")
        
        if not update.permissions:
            raise ValidationException("Permissions data is required")

        try:
            logger.info(f"Updating permissions for supervisor: {supervisor_id}")
            
            existing = self.permissions_repo.get_by_supervisor_id(db, supervisor_id)
            if not existing:
                logger.warning(
                    f"Permissions not configured for supervisor: {supervisor_id}"
                )
                raise ValidationException(
                    f"Permissions not configured for supervisor {supervisor_id}"
                )

            obj = self.permissions_repo.update_permissions(
                db=db,
                supervisor_id=supervisor_id,
                permission_data=update.permissions,
                reason=update.reason,
            )
            
            logger.info(
                f"Successfully updated permissions for supervisor: {supervisor_id}"
            )
            return SupervisorPermissions.model_validate(obj)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to update permissions for supervisor {supervisor_id}: {str(e)}"
            )
            raise ValidationException(
                f"Failed to update permissions: {str(e)}"
            )

    def create_default_permissions(
        self,
        db: Session,
        supervisor_id: UUID,
        template_name: str = "basic",
    ) -> SupervisorPermissions:
        """
        Create default permissions for a new supervisor.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            template_name: Permission template to apply

        Returns:
            SupervisorPermissions: Created permissions object

        Raises:
            ValidationException: If validation fails

        Example:
            >>> permissions = service.create_default_permissions(
            ...     db, supervisor_id, template_name="senior"
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")

        try:
            logger.info(
                f"Creating default permissions for supervisor: {supervisor_id}, "
                f"template: {template_name}"
            )
            
            # Check if permissions already exist
            existing = self.permissions_repo.get_by_supervisor_id(db, supervisor_id)
            if existing:
                logger.warning(
                    f"Permissions already exist for supervisor: {supervisor_id}"
                )
                raise ValidationException(
                    f"Permissions already configured for supervisor {supervisor_id}"
                )
            
            obj = self.permissions_repo.create_from_template(
                db=db,
                supervisor_id=supervisor_id,
                template_name=template_name,
            )
            
            logger.info(
                f"Successfully created default permissions for: {supervisor_id}"
            )
            return SupervisorPermissions.model_validate(obj)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to create default permissions for {supervisor_id}: {str(e)}"
            )
            raise ValidationException(
                f"Failed to create default permissions: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Templates
    # -------------------------------------------------------------------------

    def apply_permission_template(
        self,
        db: Session,
        supervisor_id: UUID,
        template_name: str,
        override_existing: bool = False,
    ) -> SupervisorPermissions:
        """
        Apply a named permission template to a single supervisor.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            template_name: Name of the template to apply
            override_existing: Whether to override existing permissions

        Returns:
            SupervisorPermissions: Updated permissions object

        Raises:
            ValidationException: If validation fails or template not found

        Example:
            >>> permissions = service.apply_permission_template(
            ...     db, supervisor_id, "senior", override_existing=True
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")
        
        if not template_name or not template_name.strip():
            raise ValidationException("Template name is required")

        try:
            logger.info(
                f"Applying permission template '{template_name}' "
                f"to supervisor: {supervisor_id}"
            )
            
            obj = self.permissions_repo.apply_template_to_supervisor(
                db=db,
                supervisor_id=supervisor_id,
                template_name=template_name.strip(),
                override_existing=override_existing,
            )
            
            if not obj:
                raise ValidationException(
                    f"Failed to apply template '{template_name}'"
                )
            
            logger.info(
                f"Successfully applied template '{template_name}' "
                f"to supervisor: {supervisor_id}"
            )
            return SupervisorPermissions.model_validate(obj)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to apply permission template to {supervisor_id}: {str(e)}"
            )
            raise ValidationException(
                f"Failed to apply permission template: {str(e)}"
            )

    def bulk_apply_permission_template(
        self,
        db: Session,
        supervisor_ids: List[UUID],
        template_name: str,
        override_existing: bool = False,
    ) -> int:
        """
        Apply a named template to multiple supervisors.

        Args:
            db: Database session
            supervisor_ids: List of supervisor UUIDs
            template_name: Name of the template to apply
            override_existing: Whether to override existing permissions

        Returns:
            int: Number of supervisors updated

        Raises:
            ValidationException: If validation fails

        Example:
            >>> count = service.bulk_apply_permission_template(
            ...     db, [id1, id2, id3], "senior", override_existing=False
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_ids:
            raise ValidationException("Supervisor IDs list cannot be empty")
        
        if not template_name or not template_name.strip():
            raise ValidationException("Template name is required")

        try:
            logger.info(
                f"Bulk applying permission template '{template_name}' "
                f"to {len(supervisor_ids)} supervisors"
            )
            
            count = self.permissions_repo.bulk_apply_template(
                db=db,
                supervisor_ids=supervisor_ids,
                template_name=template_name.strip(),
                override_existing=override_existing,
            )
            
            logger.info(
                f"Successfully applied template '{template_name}' "
                f"to {count} supervisors"
            )
            return count
            
        except Exception as e:
            logger.error(f"Failed to bulk apply permission template: {str(e)}")
            raise ValidationException(
                f"Failed to bulk apply permission template: {str(e)}"
            )

    def list_available_templates(self) -> List[Dict[str, Any]]:
        """
        List all available permission templates.

        Returns:
            List[Dict[str, Any]]: List of template definitions

        Example:
            >>> templates = service.list_available_templates()
            >>> for template in templates:
            ...     print(template["name"], template["description"])
        """
        try:
            logger.debug("Listing available permission templates")
            
            templates = self.permissions_repo.get_available_templates()
            
            logger.debug(f"Found {len(templates)} permission templates")
            return templates
            
        except Exception as e:
            logger.error(f"Failed to list permission templates: {str(e)}")
            return []

    # -------------------------------------------------------------------------
    # Permission Checks
    # -------------------------------------------------------------------------

    def check_permission(
        self,
        db: Session,
        supervisor_id: UUID,
        request: PermissionCheckRequest,
    ) -> PermissionCheckResponse:
        """
        Check if a supervisor has a given permission in a context (amount, days, etc.).

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            request: Permission check request with permission key and context

        Returns:
            PermissionCheckResponse: Permission check result

        Raises:
            ValidationException: If validation fails

        Example:
            >>> check = PermissionCheckRequest(
            ...     permission_key="can_approve_leaves",
            ...     context={"leave_days": 5}
            ... )
            >>> result = service.check_permission(db, supervisor_id, check)
            >>> if result.has_permission:
            ...     print("Permission granted")
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")
        
        if not request:
            raise ValidationException("Permission check request is required")
        
        if not request.permission_key or not request.permission_key.strip():
            raise ValidationException("Permission key is required")

        try:
            logger.debug(
                f"Checking permission '{request.permission_key}' "
                f"for supervisor: {supervisor_id}"
            )
            
            has_permission, reason, threshold = self.permissions_repo.check_permission(
                db=db,
                supervisor_id=supervisor_id,
                permission_key=request.permission_key.strip(),
                context=request.context or {},
            )

            response = PermissionCheckResponse(
                supervisor_id=supervisor_id,
                permission_key=request.permission_key,
                has_permission=has_permission,
                reason=reason,
                threshold=threshold,
            )
            
            logger.debug(
                f"Permission check result for {supervisor_id}: "
                f"{has_permission} - {reason}"
            )
            return response
            
        except Exception as e:
            logger.error(
                f"Failed to check permission for supervisor {supervisor_id}: {str(e)}"
            )
            raise ValidationException(
                f"Failed to check permission: {str(e)}"
            )

    def bulk_check_permissions(
        self,
        db: Session,
        supervisor_id: UUID,
        permission_keys: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, PermissionCheckResponse]:
        """
        Check multiple permissions at once.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            permission_keys: List of permission keys to check
            context: Optional context for all checks

        Returns:
            Dict[str, PermissionCheckResponse]: Map of permission keys to check results

        Example:
            >>> results = service.bulk_check_permissions(
            ...     db, supervisor_id,
            ...     ["can_approve_leaves", "can_manage_complaints"]
            ... )
        """
        if not db or not supervisor_id or not permission_keys:
            raise ValidationException("Required parameters missing")

        try:
            logger.debug(
                f"Bulk checking {len(permission_keys)} permissions "
                f"for supervisor: {supervisor_id}"
            )
            
            results = {}
            for key in permission_keys:
                request = PermissionCheckRequest(
                    permission_key=key,
                    context=context
                )
                results[key] = self.check_permission(db, supervisor_id, request)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to bulk check permissions: {str(e)}")
            raise ValidationException(f"Failed to bulk check permissions: {str(e)}")

    # -------------------------------------------------------------------------
    # Audit & History
    # -------------------------------------------------------------------------

    def get_permission_history(
        self,
        db: Session,
        supervisor_id: UUID,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get permission change history for a supervisor.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            limit: Maximum number of history records

        Returns:
            List[Dict[str, Any]]: List of permission change records

        Example:
            >>> history = service.get_permission_history(db, supervisor_id, limit=20)
        """
        if not db or not supervisor_id:
            return []
        
        try:
            logger.debug(
                f"Getting permission history for supervisor: {supervisor_id}"
            )
            
            history = self.permissions_repo.get_permission_history(
                db=db,
                supervisor_id=supervisor_id,
                limit=limit,
            )
            
            return history or []
            
        except Exception as e:
            logger.error(f"Failed to get permission history: {str(e)}")
            return []