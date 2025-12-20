# --- File: C:\Hostel-Main\app\services\notification\notification_template_service.py ---
"""
Notification Template Service - Manages templates with versioning and rendering.

Handles template lifecycle, variable validation, content rendering,
version control, and performance analytics.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import logging
import re
from jinja2 import Environment, Template, TemplateError, meta

from sqlalchemy.orm import Session

from app.models.notification.notification_template import (
    NotificationTemplate,
    NotificationTemplateVersion
)
from app.repositories.notification.notification_template_repository import (
    NotificationTemplateRepository
)
from app.schemas.common.enums import NotificationType
from app.core.exceptions import (
    TemplateNotFoundError,
    TemplateValidationError,
    TemplateRenderError
)

logger = logging.getLogger(__name__)


class NotificationTemplateService:
    """
    Service for notification template management and rendering.
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.template_repo = NotificationTemplateRepository(db_session)
        
        # Initialize Jinja2 environment for template rendering
        self.jinja_env = Environment(autoescape=True)

    def create_template(
        self,
        template_code: str,
        template_name: str,
        template_type: NotificationType,
        body_template: str,
        subject: Optional[str] = None,
        variables: Optional[List[str]] = None,
        optional_variables: Optional[List[str]] = None,
        category: Optional[str] = None,
        language: str = 'en',
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        created_by_id: Optional[UUID] = None
    ) -> NotificationTemplate:
        """
        Create new notification template with validation.
        
        Args:
            template_code: Unique identifier code
            template_name: Human-readable name
            template_type: Notification channel type
            body_template: Template body with {{variables}}
            subject: Template subject (for email/push)
            variables: Required variable names
            optional_variables: Optional variable names
            category: Template category
            language: Template language code
            description: Template description
            tags: Tags for discovery
            created_by_id: User who created template
            
        Returns:
            Created NotificationTemplate
        """
        try:
            # Validate template code uniqueness
            existing = self.template_repo.find_by_code(template_code)
            if existing:
                raise TemplateValidationError(
                    f"Template with code '{template_code}' already exists"
                )
            
            # Auto-detect variables if not provided
            if variables is None:
                variables = self._extract_variables_from_template(body_template)
                if subject:
                    subject_vars = self._extract_variables_from_template(subject)
                    variables = list(set(variables + subject_vars))
            
            # Validate template syntax
            self._validate_template_syntax(body_template, variables)
            if subject:
                self._validate_template_syntax(subject, variables)
            
            # Prepare template data
            template_data = {
                'template_code': template_code.lower(),
                'template_name': template_name,
                'template_type': template_type,
                'subject': subject,
                'body_template': body_template,
                'variables': variables or [],
                'optional_variables': optional_variables or [],
                'category': category,
                'language': language,
                'description': description,
                'tags': tags or [],
                'is_active': True
            }
            
            # Create template with initial version
            template = self.template_repo.create_template_with_version(
                template_data,
                created_by_id
            )
            
            logger.info(f"Template created: {template_code}")
            
            return template
            
        except Exception as e:
            logger.error(f"Error creating template: {str(e)}", exc_info=True)
            raise TemplateValidationError(f"Failed to create template: {str(e)}")

    def update_template(
        self,
        template_id: UUID,
        subject: Optional[str] = None,
        body_template: Optional[str] = None,
        variables: Optional[List[str]] = None,
        optional_variables: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
        changed_by_id: Optional[UUID] = None,
        change_summary: Optional[str] = None
    ) -> NotificationTemplate:
        """
        Update template content and create new version.
        
        Args:
            template_id: Template to update
            subject: New subject template
            body_template: New body template
            variables: Updated required variables
            optional_variables: Updated optional variables
            is_active: Active status
            changed_by_id: User making changes
            change_summary: Description of changes
            
        Returns:
            Updated NotificationTemplate
        """
        try:
            template = self.template_repo.find_by_id(template_id)
            if not template:
                raise TemplateNotFoundError(f"Template {template_id} not found")
            
            # Prepare updates
            content_updates = {}
            
            if subject is not None:
                self._validate_template_syntax(subject, variables or template.variables)
                content_updates['subject'] = subject
            
            if body_template is not None:
                self._validate_template_syntax(
                    body_template,
                    variables or template.variables
                )
                content_updates['body_template'] = body_template
            
            if variables is not None:
                content_updates['variables'] = variables
            
            if optional_variables is not None:
                content_updates['optional_variables'] = optional_variables
            
            if is_active is not None:
                content_updates['is_active'] = is_active
            
            # Update template
            updated_template = self.template_repo.update_template_content(
                template_id,
                content_updates,
                changed_by_id,
                change_summary
            )
            
            logger.info(f"Template updated: {template.template_code}")
            
            return updated_template
            
        except Exception as e:
            logger.error(f"Error updating template: {str(e)}", exc_info=True)
            raise TemplateValidationError(f"Failed to update template: {str(e)}")

    def render_template(
        self,
        template_code: str,
        variables: Dict[str, Any],
        validate: bool = True
    ) -> Dict[str, str]:
        """
        Render template with provided variables.
        
        Args:
            template_code: Template code to render
            variables: Variable values for rendering
            validate: Whether to validate variables
            
        Returns:
            Dict with rendered 'subject' and 'body'
        """
        try:
            # Get template
            template = self.template_repo.find_by_code(template_code)
            if not template:
                raise TemplateNotFoundError(f"Template '{template_code}' not found")
            
            if not template.is_active:
                logger.warning(f"Rendering inactive template: {template_code}")
            
            # Validate variables if requested
            if validate:
                self._validate_variables(template, variables)
            
            # Render subject
            rendered_subject = None
            if template.subject:
                rendered_subject = self._render_content(
                    template.subject,
                    variables,
                    template_code
                )
            
            # Render body
            rendered_body = self._render_content(
                template.body_template,
                variables,
                template_code
            )
            
            # Track usage
            template.increment_usage()
            self.db_session.commit()
            
            return {
                'subject': rendered_subject,
                'body': rendered_body,
                'template_id': str(template.id)
            }
            
        except TemplateNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error rendering template: {str(e)}", exc_info=True)
            raise TemplateRenderError(f"Failed to render template: {str(e)}")

    def preview_template(
        self,
        template_code: str,
        sample_variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Preview template with sample data.
        
        Args:
            template_code: Template to preview
            sample_variables: Sample variable values
            
        Returns:
            Preview data with rendered content and metadata
        """
        try:
            template = self.template_repo.find_by_code(template_code)
            if not template:
                raise TemplateNotFoundError(f"Template '{template_code}' not found")
            
            # Generate sample variables if not provided
            if sample_variables is None:
                sample_variables = self._generate_sample_variables(template)
            
            # Render template
            rendered = self._render_content(
                template.body_template,
                sample_variables,
                template_code
            )
            
            rendered_subject = None
            if template.subject:
                rendered_subject = self._render_content(
                    template.subject,
                    sample_variables,
                    template_code
                )
            
            return {
                'template_code': template.template_code,
                'template_name': template.template_name,
                'type': template.template_type.value,
                'subject': {
                    'template': template.subject,
                    'rendered': rendered_subject
                },
                'body': {
                    'template': template.body_template,
                    'rendered': rendered
                },
                'variables': {
                    'required': template.variables,
                    'optional': template.optional_variables,
                    'sample_values': sample_variables
                },
                'metadata': {
                    'category': template.category,
                    'language': template.language,
                    'usage_count': template.usage_count,
                    'is_active': template.is_active
                }
            }
            
        except Exception as e:
            logger.error(f"Error previewing template: {str(e)}", exc_info=True)
            raise

    def validate_template(
        self,
        template_id: UUID
    ) -> Dict[str, Any]:
        """
        Validate template syntax and variable usage.
        
        Args:
            template_id: Template to validate
            
        Returns:
            Validation results with issues and warnings
        """
        try:
            return self.template_repo.validate_template_syntax(template_id)
        except Exception as e:
            logger.error(f"Error validating template: {str(e)}", exc_info=True)
            raise

    def get_template_versions(
        self,
        template_id: UUID,
        limit: int = 10
    ) -> List[NotificationTemplateVersion]:
        """Get template version history."""
        try:
            return self.template_repo.get_template_versions(template_id, limit)
        except Exception as e:
            logger.error(f"Error getting template versions: {str(e)}", exc_info=True)
            raise

    def revert_to_version(
        self,
        template_id: UUID,
        version_number: int,
        reverted_by_id: Optional[UUID] = None
    ) -> NotificationTemplate:
        """Revert template to specific version."""
        try:
            template = self.template_repo.revert_to_version(
                template_id,
                version_number,
                reverted_by_id
            )
            
            logger.info(
                f"Template {template_id} reverted to version {version_number}"
            )
            
            return template
            
        except Exception as e:
            logger.error(f"Error reverting template: {str(e)}", exc_info=True)
            raise

    def duplicate_template(
        self,
        source_template_id: UUID,
        new_code: str,
        new_name: str,
        created_by_id: Optional[UUID] = None
    ) -> NotificationTemplate:
        """Create duplicate of existing template."""
        try:
            return self.template_repo.duplicate_template(
                source_template_id,
                new_code,
                new_name,
                created_by_id
            )
        except Exception as e:
            logger.error(f"Error duplicating template: {str(e)}", exc_info=True)
            raise

    def search_templates(
        self,
        search_term: str,
        template_type: Optional[NotificationType] = None,
        category: Optional[str] = None,
        language: str = 'en',
        active_only: bool = True
    ) -> List[NotificationTemplate]:
        """
        Search templates by various criteria.
        
        Args:
            search_term: Search in name, code, content
            template_type: Filter by type
            category: Filter by category
            language: Filter by language
            active_only: Only return active templates
            
        Returns:
            List of matching templates
        """
        try:
            from app.repositories.base.pagination import PaginationParams
            
            result = self.template_repo.search_templates(
                search_term,
                template_type,
                PaginationParams(page=1, page_size=100)
            )
            
            templates = result.items
            
            # Additional filtering
            if category:
                templates = [t for t in templates if t.category == category]
            
            if language:
                templates = [t for t in templates if t.language == language]
            
            if active_only:
                templates = [t for t in templates if t.is_active]
            
            return templates
            
        except Exception as e:
            logger.error(f"Error searching templates: {str(e)}", exc_info=True)
            raise

    def get_template_analytics(
        self,
        template_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get performance analytics for template."""
        try:
            return self.template_repo.get_template_performance_metrics(
                template_id,
                days
            )
        except Exception as e:
            logger.error(f"Error getting template analytics: {str(e)}", exc_info=True)
            raise

    def find_unused_templates(
        self,
        days: int = 180
    ) -> List[NotificationTemplate]:
        """Find templates not used in specified period."""
        try:
            return self.template_repo.find_unused_templates(days)
        except Exception as e:
            logger.error(f"Error finding unused templates: {str(e)}", exc_info=True)
            raise

    def find_templates_with_issues(self) -> List[Dict[str, Any]]:
        """Find templates with validation issues."""
        try:
            return self.template_repo.find_templates_with_issues()
        except Exception as e:
            logger.error(f"Error finding templates with issues: {str(e)}", exc_info=True)
            raise

    def get_templates_by_category(
        self,
        category: str,
        language: str = 'en'
    ) -> List[NotificationTemplate]:
        """Get all templates in a category."""
        try:
            templates = self.db_session.query(NotificationTemplate).filter(
                NotificationTemplate.category == category,
                NotificationTemplate.language == language,
                NotificationTemplate.is_active == True
            ).order_by(NotificationTemplate.template_name).all()
            
            return templates
            
        except Exception as e:
            logger.error(f"Error getting templates by category: {str(e)}", exc_info=True)
            raise

    # Helper methods
    def _extract_variables_from_template(self, template_str: str) -> List[str]:
        """Extract variable names from template string."""
        # Use Jinja2 to parse template and extract variables
        try:
            ast = self.jinja_env.parse(template_str)
            variables = meta.find_undeclared_variables(ast)
            return sorted(list(variables))
        except Exception:
            # Fallback to regex if Jinja2 parsing fails
            pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}'
            matches = re.findall(pattern, template_str)
            return sorted(list(set(matches)))

    def _validate_template_syntax(
        self,
        template_str: str,
        variables: List[str]
    ) -> None:
        """Validate template syntax."""
        try:
            # Try to create Jinja2 template
            template = self.jinja_env.from_string(template_str)
            
            # Test render with dummy variables
            dummy_vars = {var: f"test_{var}" for var in variables}
            template.render(**dummy_vars)
            
        except TemplateError as e:
            raise TemplateValidationError(f"Template syntax error: {str(e)}")

    def _validate_variables(
        self,
        template: NotificationTemplate,
        variables: Dict[str, Any]
    ) -> None:
        """Validate that all required variables are provided."""
        required = set(template.variables)
        provided = set(variables.keys())
        
        missing = required - provided
        if missing:
            raise TemplateValidationError(
                f"Missing required variables: {', '.join(missing)}"
            )

    def _render_content(
        self,
        template_str: str,
        variables: Dict[str, Any],
        template_code: str
    ) -> str:
        """Render template content with variables."""
        try:
            template = self.jinja_env.from_string(template_str)
            return template.render(**variables)
        except TemplateError as e:
            raise TemplateRenderError(
                f"Error rendering template '{template_code}': {str(e)}"
            )

    def _generate_sample_variables(
        self,
        template: NotificationTemplate
    ) -> Dict[str, Any]:
        """Generate sample variable values for preview."""
        sample_vars = {}
        
        for var in template.variables + template.optional_variables:
            # Generate appropriate sample data based on variable name
            if 'name' in var.lower():
                sample_vars[var] = 'John Doe'
            elif 'email' in var.lower():
                sample_vars[var] = 'john.doe@example.com'
            elif 'phone' in var.lower():
                sample_vars[var] = '+91 98765 43210'
            elif 'date' in var.lower():
                sample_vars[var] = datetime.now().strftime('%Y-%m-%d')
            elif 'time' in var.lower():
                sample_vars[var] = datetime.now().strftime('%H:%M')
            elif 'amount' in var.lower() or 'price' in var.lower():
                sample_vars[var] = '₹1,500'
            elif 'url' in var.lower() or 'link' in var.lower():
                sample_vars[var] = 'https://example.com'
            else:
                sample_vars[var] = f'Sample {var}'
        
        return sample_vars


