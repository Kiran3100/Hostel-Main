# app/repositories/supervisor/supervisor_permissions_repository.py
"""
Supervisor Permissions Repository - Permission management and access control.

Handles granular permission configuration, template management,
and comprehensive audit logging for compliance and security.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from app.models.supervisor.supervisor_permissions import (
    SupervisorPermission,
    PermissionTemplate,
    PermissionAuditLog,
)
from app.models.supervisor.supervisor import Supervisor
from app.repositories.base.base_repository import BaseRepository
from app.core1.exceptions import (
    ResourceNotFoundError,
    BusinessLogicError,
    ValidationError,
)
from app.core1.logging import logger


class SupervisorPermissionsRepository(BaseRepository[SupervisorPermission]):
    """
    Supervisor permissions repository for granular access control.
    
    Manages permission configuration, templates, validation,
    and complete audit trail for security and compliance.
    """
    
    def __init__(self, db: Session):
        """Initialize permissions repository."""
        super().__init__(SupervisorPermission, db)
        self.db = db
    
    # ==================== Core Permission Operations ====================
    
    def create_permissions(
        self,
        supervisor_id: str,
        permissions_config: Dict[str, Any],
        created_by: str,
        template_name: Optional[str] = None,
        reason: Optional[str] = None
    ) -> SupervisorPermission:
        """
        Create permission configuration for supervisor.
        
        Args:
            supervisor_id: Supervisor ID
            permissions_config: Permission configuration dictionary
            created_by: Admin creating permissions
            template_name: Optional template name if applied
            reason: Reason for permission creation
            
        Returns:
            Created permission instance
            
        Raises:
            BusinessLogicError: If permissions already exist
        """
        # Check if permissions already exist
        existing = self.db.query(SupervisorPermission).filter(
            SupervisorPermission.supervisor_id == supervisor_id
        ).first()
        
        if existing:
            raise BusinessLogicError(
                f"Permissions already exist for supervisor {supervisor_id}"
            )
        
        try:
            # Create permissions
            permissions = SupervisorPermission(
                supervisor_id=supervisor_id,
                template_applied=template_name,
                last_modified_by=created_by,
                **permissions_config
            )
            
            self.db.add(permissions)
            self.db.flush()
            
            # Create audit log
            self._create_audit_log(
                supervisor_id=supervisor_id,
                change_type="grant",
                permission_changes=permissions_config,
                changed_by=created_by,
                reason=reason or "Initial permission setup",
                template_applied=template_name
            )
            
            self.db.commit()
            self.db.refresh(permissions)
            
            logger.info(f"Created permissions for supervisor {supervisor_id}")
            return permissions
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error creating permissions: {str(e)}")
            raise ValidationError(f"Invalid permission data: {str(e)}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating permissions: {str(e)}")
            raise
    
    def get_permissions(
        self,
        supervisor_id: str,
        load_supervisor: bool = False
    ) -> Optional[SupervisorPermission]:
        """
        Get permission configuration for supervisor.
        
        Args:
            supervisor_id: Supervisor ID
            load_supervisor: Load supervisor relationship
            
        Returns:
            Permission instance or None
        """
        query = self.db.query(SupervisorPermission).filter(
            SupervisorPermission.supervisor_id == supervisor_id
        )
        
        if load_supervisor:
            query = query.options(joinedload(SupervisorPermission.supervisor))
        
        return query.first()
    
    def update_permissions(
        self,
        supervisor_id: str,
        permission_updates: Dict[str, Any],
        updated_by: str,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> SupervisorPermission:
        """
        Update supervisor permissions with audit logging.
        
        Args:
            supervisor_id: Supervisor ID
            permission_updates: Permissions to update
            updated_by: Admin making update
            reason: Reason for update
            ip_address: IP address of updater
            user_agent: User agent string
            
        Returns:
            Updated permission instance
        """
        permissions = self.get_permissions(supervisor_id)
        if not permissions:
            raise ResourceNotFoundError(
                f"Permissions not found for supervisor {supervisor_id}"
            )
        
        try:
            # Track changes for audit
            changes = {}
            for field, new_value in permission_updates.items():
                if hasattr(permissions, field):
                    old_value = getattr(permissions, field)
                    if old_value != new_value:
                        changes[field] = {
                            'old': old_value,
                            'new': new_value
                        }
                        setattr(permissions, field, new_value)
            
            if changes:
                permissions.last_modified_by = updated_by
                
                # Create audit log
                self._create_audit_log(
                    supervisor_id=supervisor_id,
                    change_type="update",
                    permission_changes=changes,
                    changed_by=updated_by,
                    reason=reason,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                
                self.db.commit()
                self.db.refresh(permissions)
                
                logger.info(
                    f"Updated {len(changes)} permissions for supervisor {supervisor_id}"
                )
            
            return permissions
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating permissions: {str(e)}")
            raise
    
    def apply_template(
        self,
        supervisor_id: str,
        template_name: str,
        applied_by: str,
        reason: Optional[str] = None
    ) -> SupervisorPermission:
        """
        Apply permission template to supervisor.
        
        Args:
            supervisor_id: Supervisor ID
            template_name: Template name to apply
            applied_by: Admin applying template
            reason: Reason for applying template
            
        Returns:
            Updated permission instance
        """
        # Get template
        template = self.get_template_by_name(template_name)
        if not template:
            raise ResourceNotFoundError(f"Template '{template_name}' not found")
        
        if not template.is_active:
            raise BusinessLogicError(f"Template '{template_name}' is not active")
        
        # Get or create permissions
        permissions = self.get_permissions(supervisor_id)
        
        if permissions:
            # Update existing permissions
            permissions = self.update_permissions(
                supervisor_id=supervisor_id,
                permission_updates=template.permissions_config,
                updated_by=applied_by,
                reason=reason or f"Applied template: {template_name}"
            )
        else:
            # Create new permissions
            permissions = self.create_permissions(
                supervisor_id=supervisor_id,
                permissions_config=template.permissions_config,
                created_by=applied_by,
                template_name=template_name,
                reason=reason
            )
        
        # Update template usage count
        template.usage_count += 1
        
        # Update template reference
        permissions.template_applied = template_name
        
        self.db.commit()
        self.db.refresh(permissions)
        
        logger.info(
            f"Applied template '{template_name}' to supervisor {supervisor_id}"
        )
        
        return permissions
    
    # ==================== Permission Validation ====================
    
    def has_permission(
        self,
        supervisor_id: str,
        permission_name: str
    ) -> bool:
        """
        Check if supervisor has specific permission.
        
        Args:
            supervisor_id: Supervisor ID
            permission_name: Permission field name
            
        Returns:
            True if permission granted, False otherwise
        """
        permissions = self.get_permissions(supervisor_id)
        if not permissions:
            return False
        
        if not hasattr(permissions, permission_name):
            logger.warning(f"Invalid permission name: {permission_name}")
            return False
        
        return bool(getattr(permissions, permission_name))
    
    def get_granted_permissions(
        self,
        supervisor_id: str
    ) -> List[str]:
        """
        Get list of all granted permission names.
        
        Args:
            supervisor_id: Supervisor ID
            
        Returns:
            List of granted permission names
        """
        permissions = self.get_permissions(supervisor_id)
        if not permissions:
            return []
        
        granted = []
        
        # Get all boolean permission fields
        for column in SupervisorPermission.__table__.columns:
            if column.type.python_type == bool:
                field_name = column.name
                if getattr(permissions, field_name, False):
                    granted.append(field_name)
        
        return granted
    
    def validate_permission_set(
        self,
        permissions_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate permission configuration for conflicts and dependencies.
        
        Args:
            permissions_config: Permission configuration to validate
            
        Returns:
            Validation result with errors and warnings
        """
        errors = []
        warnings = []
        
        # Check dependencies
        if permissions_config.get('can_close_complaints') and \
           not permissions_config.get('can_resolve_complaints'):
            errors.append(
                "Cannot grant close_complaints without resolve_complaints"
            )
        
        if permissions_config.get('can_approve_maintenance_costs') and \
           not permissions_config.get('can_manage_maintenance'):
            errors.append(
                "Cannot approve maintenance costs without manage_maintenance"
            )
        
        if permissions_config.get('can_assign_beds') and \
           not permissions_config.get('can_view_room_availability'):
            warnings.append(
                "Assigning beds without viewing room availability may be limited"
            )
        
        # Check threshold values
        if 'max_leave_days_approval' in permissions_config:
            max_days = permissions_config['max_leave_days_approval']
            if max_days > 30:
                warnings.append(
                    f"Leave approval threshold of {max_days} days is very high"
                )
        
        if 'maintenance_approval_threshold' in permissions_config:
            threshold = permissions_config['maintenance_approval_threshold']
            if threshold > 100000:
                warnings.append(
                    f"Maintenance approval threshold of {threshold} is very high"
                )
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    # ==================== Template Management ====================
    
    def create_template(
        self,
        template_name: str,
        permissions_config: Dict[str, Any],
        created_by: str,
        description: Optional[str] = None,
        is_system_template: bool = False
    ) -> PermissionTemplate:
        """
        Create permission template.
        
        Args:
            template_name: Unique template name
            permissions_config: Permission configuration
            created_by: Admin creating template
            description: Template description
            is_system_template: System-defined template flag
            
        Returns:
            Created template instance
        """
        # Validate permissions
        validation = self.validate_permission_set(permissions_config)
        if not validation['is_valid']:
            raise ValidationError(
                f"Invalid permissions: {', '.join(validation['errors'])}"
            )
        
        try:
            template = PermissionTemplate(
                template_name=template_name,
                description=description,
                permissions_config=permissions_config,
                is_system_template=is_system_template,
                created_by=created_by,
                is_active=True
            )
            
            self.db.add(template)
            self.db.commit()
            self.db.refresh(template)
            
            logger.info(f"Created permission template: {template_name}")
            return template
            
        except IntegrityError:
            self.db.rollback()
            raise BusinessLogicError(
                f"Template with name '{template_name}' already exists"
            )
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating template: {str(e)}")
            raise
    
    def get_template_by_name(
        self,
        template_name: str
    ) -> Optional[PermissionTemplate]:
        """Get template by name."""
        return self.db.query(PermissionTemplate).filter(
            PermissionTemplate.template_name == template_name
        ).first()
    
    def get_all_templates(
        self,
        active_only: bool = True,
        include_system: bool = True
    ) -> List[PermissionTemplate]:
        """
        Get all permission templates.
        
        Args:
            active_only: Only active templates
            include_system: Include system templates
            
        Returns:
            List of templates
        """
        query = self.db.query(PermissionTemplate)
        
        if active_only:
            query = query.filter(PermissionTemplate.is_active == True)
        
        if not include_system:
            query = query.filter(PermissionTemplate.is_system_template == False)
        
        return query.order_by(PermissionTemplate.template_name).all()
    
    def update_template(
        self,
        template_id: str,
        update_data: Dict[str, Any]
    ) -> PermissionTemplate:
        """Update permission template."""
        template = self.db.query(PermissionTemplate).filter(
            PermissionTemplate.id == template_id
        ).first()
        
        if not template:
            raise ResourceNotFoundError(f"Template {template_id} not found")
        
        if template.is_system_template:
            raise BusinessLogicError("Cannot modify system templates")
        
        # Validate if updating permissions_config
        if 'permissions_config' in update_data:
            validation = self.validate_permission_set(update_data['permissions_config'])
            if not validation['is_valid']:
                raise ValidationError(
                    f"Invalid permissions: {', '.join(validation['errors'])}"
                )
        
        for field, value in update_data.items():
            if hasattr(template, field):
                setattr(template, field, value)
        
        self.db.commit()
        self.db.refresh(template)
        
        logger.info(f"Updated template: {template.template_name}")
        return template
    
    def deactivate_template(
        self,
        template_id: str
    ) -> PermissionTemplate:
        """Deactivate permission template."""
        template = self.db.query(PermissionTemplate).filter(
            PermissionTemplate.id == template_id
        ).first()
        
        if not template:
            raise ResourceNotFoundError(f"Template {template_id} not found")
        
        template.is_active = False
        self.db.commit()
        self.db.refresh(template)
        
        logger.info(f"Deactivated template: {template.template_name}")
        return template
    
    # ==================== Audit Logging ====================
    
    def _create_audit_log(
        self,
        supervisor_id: str,
        change_type: str,
        permission_changes: Dict[str, Any],
        changed_by: str,
        reason: Optional[str] = None,
        template_applied: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        requires_approval: bool = False
    ) -> PermissionAuditLog:
        """Create permission audit log entry."""
        audit_log = PermissionAuditLog(
            supervisor_id=supervisor_id,
            change_type=change_type,
            permission_changes=permission_changes,
            changed_by=changed_by,
            reason=reason,
            template_applied=template_applied,
            ip_address=ip_address,
            user_agent=user_agent,
            requires_approval=requires_approval
        )
        
        self.db.add(audit_log)
        return audit_log
    
    def get_audit_logs(
        self,
        supervisor_id: Optional[str] = None,
        change_type: Optional[str] = None,
        changed_by: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[PermissionAuditLog]:
        """
        Get permission audit logs with filters.
        
        Args:
            supervisor_id: Filter by supervisor
            change_type: Filter by change type
            changed_by: Filter by admin who made change
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum results
            
        Returns:
            List of audit logs
        """
        query = self.db.query(PermissionAuditLog)
        
        if supervisor_id:
            query = query.filter(
                PermissionAuditLog.supervisor_id == supervisor_id
            )
        
        if change_type:
            query = query.filter(
                PermissionAuditLog.change_type == change_type
            )
        
        if changed_by:
            query = query.filter(
                PermissionAuditLog.changed_by == changed_by
            )
        
        if start_date:
            query = query.filter(
                PermissionAuditLog.changed_at >= start_date
            )
        
        if end_date:
            query = query.filter(
                PermissionAuditLog.changed_at <= end_date
            )
        
        return query.order_by(
            PermissionAuditLog.changed_at.desc()
        ).limit(limit).all()
    
    def get_permission_history(
        self,
        supervisor_id: str
    ) -> List[PermissionAuditLog]:
        """Get complete permission change history for supervisor."""
        return self.db.query(PermissionAuditLog).filter(
            PermissionAuditLog.supervisor_id == supervisor_id
        ).options(
            joinedload(PermissionAuditLog.changed_by_user)
        ).order_by(
            PermissionAuditLog.changed_at.desc()
        ).all()
    
    # ==================== Analytics ====================
    
    def get_permission_usage_statistics(
        self,
        hostel_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get permission usage statistics across supervisors.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Statistics dictionary
        """
        # Build base query
        query = self.db.query(SupervisorPermission)
        
        if hostel_id:
            query = query.join(Supervisor).filter(
                Supervisor.assigned_hostel_id == hostel_id
            )
        
        permissions = query.all()
        total = len(permissions)
        
        if total == 0:
            return {'total_supervisors': 0}
        
        # Calculate statistics for key permissions
        stats = {
            'total_supervisors': total,
            'can_manage_complaints': sum(1 for p in permissions if p.can_manage_complaints),
            'can_resolve_complaints': sum(1 for p in permissions if p.can_resolve_complaints),
            'can_record_attendance': sum(1 for p in permissions if p.can_record_attendance),
            'can_approve_leaves': sum(1 for p in permissions if p.can_approve_leaves),
            'can_manage_maintenance': sum(1 for p in permissions if p.can_manage_maintenance),
            'can_create_announcements': sum(1 for p in permissions if p.can_create_announcements),
            'can_export_data': sum(1 for p in permissions if p.can_export_data),
        }
        
        # Calculate percentages
        for key in list(stats.keys()):
            if key != 'total_supervisors':
                stats[f'{key}_percentage'] = round(
                    (stats[key] / total * 100), 2
                )
        
        return stats
    
    def get_template_usage_statistics(self) -> List[Dict[str, Any]]:
        """Get template usage statistics."""
        templates = self.db.query(PermissionTemplate).all()
        
        return [
            {
                'template_name': t.template_name,
                'usage_count': t.usage_count,
                'is_system': t.is_system_template,
                'is_active': t.is_active,
                'description': t.description
            }
            for t in templates
        ]
    
    def find_permission_conflicts(
        self,
        supervisor_id: str
    ) -> List[str]:
        """
        Identify permission conflicts or unusual combinations.
        
        Args:
            supervisor_id: Supervisor ID
            
        Returns:
            List of conflict descriptions
        """
        permissions = self.get_permissions(supervisor_id)
        if not permissions:
            return []
        
        conflicts = []
        
        # Check for unusual combinations
        if permissions.can_close_complaints and \
           not permissions.can_resolve_complaints:
            conflicts.append(
                "Can close complaints but cannot resolve them"
            )
        
        if permissions.can_approve_maintenance_costs and \
           not permissions.can_manage_maintenance:
            conflicts.append(
                "Can approve maintenance costs but cannot manage maintenance"
            )
        
        if permissions.can_export_data and \
           not permissions.can_generate_reports:
            conflicts.append(
                "Can export data but cannot generate reports"
            )
        
        if permissions.can_assign_beds and \
           not permissions.can_view_room_availability:
            conflicts.append(
                "Can assign beds but cannot view room availability"
            )
        
        return conflicts
    
    # ==================== Bulk Operations ====================
    
    def bulk_apply_template(
        self,
        supervisor_ids: List[str],
        template_name: str,
        applied_by: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Apply template to multiple supervisors.
        
        Args:
            supervisor_ids: List of supervisor IDs
            template_name: Template to apply
            applied_by: Admin applying template
            reason: Reason for bulk application
            
        Returns:
            Result summary
        """
        success_count = 0
        failed_count = 0
        errors = []
        
        for supervisor_id in supervisor_ids:
            try:
                self.apply_template(
                    supervisor_id=supervisor_id,
                    template_name=template_name,
                    applied_by=applied_by,
                    reason=reason
                )
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append({
                    'supervisor_id': supervisor_id,
                    'error': str(e)
                })
                logger.error(
                    f"Error applying template to supervisor {supervisor_id}: {str(e)}"
                )
        
        return {
            'total': len(supervisor_ids),
            'success': success_count,
            'failed': failed_count,
            'errors': errors
        }
    
    def bulk_update_permission(
        self,
        supervisor_ids: List[str],
        permission_name: str,
        value: Any,
        updated_by: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update specific permission for multiple supervisors.
        
        Args:
            supervisor_ids: List of supervisor IDs
            permission_name: Permission field name
            value: New value
            updated_by: Admin making update
            reason: Reason for update
            
        Returns:
            Result summary
        """
        success_count = 0
        failed_count = 0
        errors = []
        
        for supervisor_id in supervisor_ids:
            try:
                self.update_permissions(
                    supervisor_id=supervisor_id,
                    permission_updates={permission_name: value},
                    updated_by=updated_by,
                    reason=reason
                )
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append({
                    'supervisor_id': supervisor_id,
                    'error': str(e)
                })
        
        return {
            'total': len(supervisor_ids),
            'success': success_count,
            'failed': failed_count,
            'errors': errors
        }