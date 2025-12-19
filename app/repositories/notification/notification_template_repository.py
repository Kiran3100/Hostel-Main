# --- File: C:\Hostel-Main\app\repositories\notification\notification_template_repository.py ---
"""
Notification Template Repository with versioning and content management.

Handles template lifecycle, variable validation, performance tracking,
and multi-language support with comprehensive version control.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import re

from sqlalchemy import and_, or_, func, desc, asc, text
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql import select

from app.models.notification.notification_template import (
    NotificationTemplate,
    NotificationTemplateVersion
)
from app.models.notification.notification import Notification
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.specifications import Specification
from app.repositories.base.pagination import PaginationParams, PaginatedResult
from app.schemas.common.enums import NotificationType


class ActiveTemplatesSpec(Specification):
    """Specification for active templates."""
    
    def __init__(self, template_type: Optional[NotificationType] = None):
        self.template_type = template_type
    
    def is_satisfied_by(self, query):
        conditions = [NotificationTemplate.is_active == True]
        if self.template_type:
            conditions.append(NotificationTemplate.template_type == self.template_type)
        return query.filter(and_(*conditions))


class PopularTemplatesSpec(Specification):
    """Specification for frequently used templates."""
    
    def __init__(self, min_usage_count: int = 100):
        self.min_usage_count = min_usage_count
    
    def is_satisfied_by(self, query):
        return query.filter(NotificationTemplate.usage_count >= self.min_usage_count)


class NotificationTemplateRepository(BaseRepository[NotificationTemplate]):
    """
    Repository for notification template management with versioning and analytics.
    """

    def __init__(self, db_session: Session):
        super().__init__(NotificationTemplate, db_session)

    # Core template operations
    def create_template_with_version(
        self,
        template_data: Dict[str, Any],
        created_by_id: Optional[UUID] = None
    ) -> NotificationTemplate:
        """Create template with initial version."""
        # Extract version data
        version_data = {
            'subject': template_data.get('subject'),
            'body_template': template_data['body_template'],
            'variables': template_data.get('variables', []),
            'optional_variables': template_data.get('optional_variables', [])
        }
        
        # Create template
        template_data['created_by_id'] = created_by_id
        template = NotificationTemplate(**template_data)
        template = self.create(template)
        
        # Create initial version
        self._create_template_version(template.id, version_data, created_by_id, "Initial version")
        
        return template

    def find_by_code(self, template_code: str) -> Optional[NotificationTemplate]:
        """Find template by unique code."""
        return self.db_session.query(NotificationTemplate).filter(
            NotificationTemplate.template_code == template_code
        ).options(
            selectinload(NotificationTemplate.versions)
        ).first()

    def find_by_type_and_category(
        self,
        template_type: NotificationType,
        category: Optional[str] = None,
        language: str = 'en'
    ) -> List[NotificationTemplate]:
        """Find templates by type and category."""
        query = self.db_session.query(NotificationTemplate).filter(
            and_(
                NotificationTemplate.template_type == template_type,
                NotificationTemplate.language == language,
                NotificationTemplate.is_active == True
            )
        )
        
        if category:
            query = query.filter(NotificationTemplate.category == category)
        
        return query.order_by(NotificationTemplate.template_name).all()

    def search_templates(
        self,
        search_term: str,
        template_type: Optional[NotificationType] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[NotificationTemplate]:
        """Search templates by name, code, or content."""
        query = self.db_session.query(NotificationTemplate).filter(
            or_(
                NotificationTemplate.template_name.ilike(f'%{search_term}%'),
                NotificationTemplate.template_code.ilike(f'%{search_term}%'),
                NotificationTemplate.body_template.ilike(f'%{search_term}%'),
                NotificationTemplate.description.ilike(f'%{search_term}%')
            )
        )
        
        if template_type:
            query = query.filter(NotificationTemplate.template_type == template_type)
        
        query = query.order_by(NotificationTemplate.usage_count.desc())
        
        if pagination:
            return self.paginate_query(query, pagination)
        
        return PaginatedResult(
            items=query.all(),
            total_count=query.count(),
            page=1,
            page_size=len(query.all())
        )

    # Template versioning
    def update_template_content(
        self,
        template_id: UUID,
        content_updates: Dict[str, Any],
        changed_by_id: Optional[UUID] = None,
        change_summary: Optional[str] = None
    ) -> NotificationTemplate:
        """Update template content and create new version."""
        template = self.find_by_id(template_id)
        if not template:
            raise ValueError("Template not found")
        
        # Validate variables in new content
        if 'body_template' in content_updates:
            extracted_vars = self._extract_variables(content_updates['body_template'])
            declared_vars = content_updates.get('variables', template.variables)
            
            missing_vars = set(extracted_vars) - set(declared_vars)
            if missing_vars:
                raise ValueError(f"Undeclared variables found: {missing_vars}")
        
        # Update template
        for key, value in content_updates.items():
            if hasattr(template, key):
                setattr(template, key, value)
        
        # Create new version
        version_data = {
            'subject': template.subject,
            'body_template': template.body_template,
            'variables': template.variables,
            'optional_variables': template.optional_variables
        }
        
        self._create_template_version(
            template_id, version_data, changed_by_id, change_summary
        )
        
        self.db_session.commit()
        return template

    def get_template_versions(
        self,
        template_id: UUID,
        limit: int = 10
    ) -> List[NotificationTemplateVersion]:
        """Get template version history."""
        return self.db_session.query(NotificationTemplateVersion).filter(
            NotificationTemplateVersion.template_id == template_id
        ).order_by(desc(NotificationTemplateVersion.version_number)).limit(limit).all()

    def revert_to_version(
        self,
        template_id: UUID,
        version_number: int,
        reverted_by_id: Optional[UUID] = None
    ) -> NotificationTemplate:
        """Revert template to specific version."""
        template = self.find_by_id(template_id)
        if not template:
            raise ValueError("Template not found")
        
        target_version = self.db_session.query(NotificationTemplateVersion).filter(
            and_(
                NotificationTemplateVersion.template_id == template_id,
                NotificationTemplateVersion.version_number == version_number
            )
        ).first()
        
        if not target_version:
            raise ValueError("Version not found")
        
        # Update template with version content
        template.subject = target_version.subject
        template.body_template = target_version.body_template
        template.variables = target_version.variables
        template.optional_variables = target_version.optional_variables
        
        # Create revert version
        version_data = {
            'subject': template.subject,
            'body_template': template.body_template,
            'variables': template.variables,
            'optional_variables': template.optional_variables
        }
        
        self._create_template_version(
            template_id, 
            version_data, 
            reverted_by_id, 
            f"Reverted to version {version_number}"
        )
        
        self.db_session.commit()
        return template

    # Template rendering and validation
    def render_template(
        self,
        template_code: str,
        variables: Dict[str, Any],
        validate_variables: bool = True
    ) -> Dict[str, str]:
        """Render template with provided variables."""
        template = self.find_by_code(template_code)
        if not template:
            raise ValueError("Template not found")
        
        if validate_variables:
            self._validate_template_variables(template, variables)
        
        # Render subject and body
        rendered_subject = self._render_content(template.subject or '', variables)
        rendered_body = self._render_content(template.body_template, variables)
        
        # Track usage
        self._increment_template_usage(template.id)
        
        return {
            'subject': rendered_subject,
            'body': rendered_body,
            'template_id': str(template.id)
        }

    def validate_template_syntax(self, template_id: UUID) -> Dict[str, Any]:
        """Validate template syntax and variable usage."""
        template = self.find_by_id(template_id)
        if not template:
            return {'valid': False, 'error': 'Template not found'}
        
        issues = []
        
        # Extract variables from content
        body_vars = self._extract_variables(template.body_template)
        subject_vars = self._extract_variables(template.subject or '')
        
        all_used_vars = set(body_vars + subject_vars)
        declared_vars = set(template.variables + template.optional_variables)
        
        # Check for undeclared variables
        undeclared = all_used_vars - declared_vars
        if undeclared:
            issues.append(f"Undeclared variables: {list(undeclared)}")
        
        # Check for unused declared variables
        unused = declared_vars - all_used_vars
        if unused:
            issues.append(f"Unused declared variables: {list(unused)}")
        
        # Validate template syntax (basic check)
        try:
            test_vars = {var: f"test_{var}" for var in declared_vars}
            self._render_content(template.body_template, test_vars)
            if template.subject:
                self._render_content(template.subject, test_vars)
        except Exception as e:
            issues.append(f"Template syntax error: {str(e)}")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'used_variables': list(all_used_vars),
            'declared_variables': list(declared_vars)
        }

    # Analytics and reporting
    def get_template_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        template_type: Optional[NotificationType] = None
    ) -> Dict[str, Any]:
        """Get comprehensive template usage analytics."""
        base_query = self.db_session.query(NotificationTemplate)
        
        if template_type:
            base_query = base_query.filter(
                NotificationTemplate.template_type == template_type
            )
        
        # Usage statistics
        usage_stats = base_query.with_entities(
            func.count().label('total_templates'),
            func.sum(NotificationTemplate.usage_count).label('total_usage'),
            func.avg(NotificationTemplate.usage_count).label('avg_usage'),
            func.max(NotificationTemplate.usage_count).label('max_usage')
        ).first()
        
        # Top templates by usage
        top_templates = base_query.filter(
            and_(
                NotificationTemplate.last_used_at >= start_date,
                NotificationTemplate.last_used_at <= end_date
            )
        ).order_by(desc(NotificationTemplate.usage_count)).limit(10).all()
        
        # Performance by category
        category_stats = base_query.with_entities(
            NotificationTemplate.category,
            func.count().label('template_count'),
            func.sum(NotificationTemplate.usage_count).label('total_usage')
        ).filter(
            NotificationTemplate.category.isnot(None)
        ).group_by(NotificationTemplate.category).all()
        
        return {
            'summary': {
                'total_templates': usage_stats.total_templates or 0,
                'total_usage': usage_stats.total_usage or 0,
                'average_usage': float(usage_stats.avg_usage or 0),
                'max_usage': usage_stats.max_usage or 0
            },
            'top_templates': [
                {
                    'code': template.template_code,
                    'name': template.template_name,
                    'usage_count': template.usage_count,
                    'last_used': template.last_used_at.isoformat() if template.last_used_at else None
                }
                for template in top_templates
            ],
            'category_breakdown': [
                {
                    'category': stat.category,
                    'template_count': stat.template_count,
                    'total_usage': stat.total_usage
                }
                for stat in category_stats
            ]
        }

    def get_template_performance_metrics(
        self,
        template_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get performance metrics for specific template."""
        template = self.find_by_id(template_id)
        if not template:
            return {}
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get notifications using this template
        notifications_query = self.db_session.query(Notification).filter(
            and_(
                Notification.template_id == template_id,
                Notification.created_at >= cutoff_date
            )
        )
        
        total_notifications = notifications_query.count()
        delivered_notifications = notifications_query.filter(
            Notification.status.in_(['DELIVERED', 'COMPLETED'])
        ).count()
        read_notifications = notifications_query.filter(
            Notification.read_at.isnot(None)
        ).count()
        clicked_notifications = notifications_query.filter(
            Notification.clicked_at.isnot(None)
        ).count()
        
        # Calculate rates
        delivery_rate = (delivered_notifications / total_notifications * 100) if total_notifications > 0 else 0
        read_rate = (read_notifications / delivered_notifications * 100) if delivered_notifications > 0 else 0
        click_rate = (clicked_notifications / delivered_notifications * 100) if delivered_notifications > 0 else 0
        
        return {
            'template_code': template.template_code,
            'template_name': template.template_name,
            'period_days': days,
            'total_notifications': total_notifications,
            'delivered_notifications': delivered_notifications,
            'read_notifications': read_notifications,
            'clicked_notifications': clicked_notifications,
            'delivery_rate': round(delivery_rate, 2),
            'read_rate': round(read_rate, 2),
            'click_rate': round(click_rate, 2)
        }

    # Template management
    def find_unused_templates(self, days: int = 180) -> List[NotificationTemplate]:
        """Find templates not used in specified period."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        return self.db_session.query(NotificationTemplate).filter(
            or_(
                NotificationTemplate.last_used_at < cutoff_date,
                NotificationTemplate.last_used_at.is_(None)
            )
        ).order_by(NotificationTemplate.created_at).all()

    def find_templates_with_issues(self) -> List[Dict[str, Any]]:
        """Find templates with potential issues."""
        templates_with_issues = []
        
        templates = self.db_session.query(NotificationTemplate).filter(
            NotificationTemplate.is_active == True
        ).all()
        
        for template in templates:
            validation = self.validate_template_syntax(template.id)
            if not validation['valid']:
                templates_with_issues.append({
                    'template_id': template.id,
                    'template_code': template.template_code,
                    'template_name': template.template_name,
                    'issues': validation['issues']
                })
        
        return templates_with_issues

    def duplicate_template(
        self,
        source_template_id: UUID,
        new_code: str,
        new_name: str,
        created_by_id: Optional[UUID] = None
    ) -> NotificationTemplate:
        """Create duplicate of existing template."""
        source = self.find_by_id(source_template_id)
        if not source:
            raise ValueError("Source template not found")
        
        # Check if new code already exists
        if self.find_by_code(new_code):
            raise ValueError("Template code already exists")
        
        # Create duplicate
        duplicate_data = {
            'template_code': new_code,
            'template_name': new_name,
            'template_type': source.template_type,
            'subject': source.subject,
            'body_template': source.body_template,
            'variables': source.variables.copy(),
            'optional_variables': source.optional_variables.copy(),
            'category': source.category,
            'language': source.language,
            'description': f"Duplicate of {source.template_name}"
        }
        
        return self.create_template_with_version(duplicate_data, created_by_id)

    # Helper methods
    def _extract_variables(self, content: str) -> List[str]:
        """Extract variable names from template content."""
        if not content:
            return []
        
        # Find all {{variable}} patterns
        pattern = r'\{\{([^}]+)\}\}'
        matches = re.findall(pattern, content)
        
        # Clean up variable names (remove spaces)
        variables = [var.strip() for var in matches]
        
        return list(set(variables))  # Remove duplicates

    def _render_content(self, content: str, variables: Dict[str, Any]) -> str:
        """Render template content with variables."""
        if not content:
            return ''
        
        rendered_content = content
        for var_name, var_value in variables.items():
            placeholder = f'{{{{{var_name}}}}}'
            rendered_content = rendered_content.replace(placeholder, str(var_value))
        
        return rendered_content

    def _validate_template_variables(
        self,
        template: NotificationTemplate,
        variables: Dict[str, Any]
    ) -> None:
        """Validate provided variables against template requirements."""
        required_vars = set(template.variables)
        provided_vars = set(variables.keys())
        
        missing_vars = required_vars - provided_vars
        if missing_vars:
            raise ValueError(f"Missing required variables: {list(missing_vars)}")

    def _create_template_version(
        self,
        template_id: UUID,
        version_data: Dict[str, Any],
        changed_by_id: Optional[UUID] = None,
        change_summary: Optional[str] = None
    ) -> NotificationTemplateVersion:
        """Create new template version."""
        # Get next version number
        max_version = self.db_session.query(
            func.max(NotificationTemplateVersion.version_number)
        ).filter(
            NotificationTemplateVersion.template_id == template_id
        ).scalar() or 0
        
        version = NotificationTemplateVersion(
            template_id=template_id,
            version_number=max_version + 1,
            changed_by_id=changed_by_id,
            change_summary=change_summary,
            **version_data
        )
        
        self.db_session.add(version)
        return version

    def _increment_template_usage(self, template_id: UUID) -> None:
        """Increment template usage count."""
        self.db_session.query(NotificationTemplate).filter(
            NotificationTemplate.id == template_id
        ).update({
            'usage_count': NotificationTemplate.usage_count + 1,
            'last_used_at': datetime.utcnow()
        }, synchronize_session=False)