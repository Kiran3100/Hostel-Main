"""
Announcement Template Service

Template management service providing template CRUD operations,
rendering with variables, and template sharing capabilities.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
from dataclasses import dataclass
import re

from sqlalchemy.orm import Session
from pydantic import BaseModel, validator, Field

from app.repositories.announcement import AnnouncementRepository
from app.models.announcement import Announcement
from app.models.base.enums import AnnouncementCategory, Priority
from app.core.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    BusinessLogicError,
)
from app.core.events import EventPublisher


# ==================== DTOs ====================

class CreateTemplateDTO(BaseModel):
    """DTO for creating template."""
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    title_template: str = Field(..., min_length=3, max_length=255)
    content_template: str = Field(..., min_length=10)
    category: AnnouncementCategory
    priority: Priority = Priority.MEDIUM
    variables: List[str] = Field(default_factory=list)
    is_shared: bool = False
    metadata: Optional[Dict[str, Any]] = None


class UpdateTemplateDTO(BaseModel):
    """DTO for updating template."""
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = None
    title_template: Optional[str] = None
    content_template: Optional[str] = None
    category: Optional[AnnouncementCategory] = None
    priority: Optional[Priority] = None
    is_shared: Optional[bool] = None


class RenderTemplateDTO(BaseModel):
    """DTO for rendering template."""
    variables: Dict[str, Any]
    
    @validator('variables')
    def validate_variables(cls, v):
        # Ensure all values are serializable
        for key, value in v.items():
            if not isinstance(value, (str, int, float, bool, type(None))):
                raise ValueError(f'Variable {key} must be a primitive type')
        return v


class CreateFromTemplateDTO(BaseModel):
    """DTO for creating from template."""
    variable_overrides: Dict[str, Any] = Field(default_factory=dict)
    field_overrides: Optional[Dict[str, Any]] = None


@dataclass
class ServiceResult:
    """Standard service result wrapper."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @classmethod
    def ok(cls, data: Any = None, **metadata) -> 'ServiceResult':
        return cls(success=True, data=data, metadata=metadata)
    
    @classmethod
    def fail(cls, error: str, error_code: str = None, **metadata) -> 'ServiceResult':
        return cls(success=False, error=error, error_code=error_code, metadata=metadata)


# ==================== Service ====================

class AnnouncementTemplateService:
    """
    Template management service.
    
    Provides template capabilities including:
    - Template CRUD operations
    - Template rendering with variable substitution
    - Template validation
    - Template sharing across hostels
    - Template versioning
    - Popular template tracking
    """
    
    def __init__(
        self,
        session: Session,
        event_publisher: Optional[EventPublisher] = None
    ):
        self.session = session
        self.repository = AnnouncementRepository(session)
        self.event_publisher = event_publisher or EventPublisher()
    
    # ==================== Template CRUD ====================
    
    def create_template(
        self,
        hostel_id: UUID,
        dto: CreateTemplateDTO,
        user_id: UUID
    ) -> ServiceResult:
        """
        Create announcement template.
        
        Args:
            hostel_id: Hostel UUID
            dto: Template data
            user_id: User creating template
            
        Returns:
            ServiceResult with template
        """
        try:
            # Extract variables from templates
            detected_variables = self._extract_variables(
                dto.title_template,
                dto.content_template
            )
            
            # Merge with declared variables
            all_variables = list(set(dto.variables + detected_variables))
            
            # Create template as announcement
            metadata = dto.metadata or {}
            metadata.update({
                'is_template': True,
                'template_name': dto.name,
                'template_description': dto.description,
                'template_variables': all_variables,
                'is_shared_template': dto.is_shared,
            })
            
            announcement = Announcement(
                hostel_id=hostel_id,
                created_by_id=user_id,
                title=dto.title_template,
                content=dto.content_template,
                category=dto.category,
                priority=dto.priority,
                status='draft',
                metadata=metadata,
            )
            
            self.session.add(announcement)
            self.session.commit()
            
            # Publish event
            self.event_publisher.publish('template.created', {
                'template_id': str(announcement.id),
                'template_name': dto.name,
                'hostel_id': str(hostel_id),
                'is_shared': dto.is_shared,
            })
            
            return ServiceResult.ok(
                data=self._serialize_template(announcement),
                template_id=str(announcement.id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="TEMPLATE_CREATE_FAILED")
    
    def update_template(
        self,
        template_id: UUID,
        dto: UpdateTemplateDTO
    ) -> ServiceResult:
        """
        Update template.
        
        Args:
            template_id: Template UUID
            dto: Update data
            
        Returns:
            ServiceResult with updated template
        """
        try:
            template = self.repository.find_by_id(template_id)
            if not template:
                return ServiceResult.fail(
                    f"Template {template_id} not found",
                    error_code="NOT_FOUND"
                )
            
            # Verify it's a template
            if not template.metadata or not template.metadata.get('is_template'):
                return ServiceResult.fail(
                    "Not a template announcement",
                    error_code="INVALID_TYPE"
                )
            
            # Update fields
            if dto.name:
                template.metadata['template_name'] = dto.name
            if dto.description is not None:
                template.metadata['template_description'] = dto.description
            if dto.title_template:
                template.title = dto.title_template
            if dto.content_template:
                template.content = dto.content_template
            if dto.category:
                template.category = dto.category
            if dto.priority:
                template.priority = dto.priority
            if dto.is_shared is not None:
                template.metadata['is_shared_template'] = dto.is_shared
            
            # Re-extract variables if templates changed
            if dto.title_template or dto.content_template:
                variables = self._extract_variables(
                    template.title,
                    template.content
                )
                template.metadata['template_variables'] = variables
            
            template.updated_at = datetime.utcnow()
            
            # Mark metadata as modified
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(template, 'metadata')
            
            self.session.commit()
            
            return ServiceResult.ok(
                data=self._serialize_template(template),
                template_id=str(template_id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="UPDATE_FAILED")
    
    def delete_template(
        self,
        template_id: UUID
    ) -> ServiceResult:
        """
        Delete template.
        
        Args:
            template_id: Template UUID
            
        Returns:
            ServiceResult
        """
        try:
            template = self.repository.find_by_id(template_id)
            if not template:
                return ServiceResult.fail(
                    f"Template {template_id} not found",
                    error_code="NOT_FOUND"
                )
            
            self.repository.soft_delete(template)
            self.session.commit()
            
            self.event_publisher.publish('template.deleted', {
                'template_id': str(template_id),
            })
            
            return ServiceResult.ok(data={'status': 'deleted'})
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="DELETE_FAILED")
    
    def get_template(
        self,
        template_id: UUID
    ) -> ServiceResult:
        """
        Get template by ID.
        
        Args:
            template_id: Template UUID
            
        Returns:
            ServiceResult with template
        """
        try:
            template = self.repository.find_by_id(template_id)
            if not template:
                return ServiceResult.fail(
                    f"Template {template_id} not found",
                    error_code="NOT_FOUND"
                )
            
            if not template.metadata or not template.metadata.get('is_template'):
                return ServiceResult.fail(
                    "Not a template announcement",
                    error_code="INVALID_TYPE"
                )
            
            return ServiceResult.ok(data=self._serialize_template(template))
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="FETCH_FAILED")
    
    def list_templates(
        self,
        hostel_id: UUID,
        include_shared: bool = True,
        category: Optional[AnnouncementCategory] = None
    ) -> ServiceResult:
        """
        List templates for hostel.
        
        Args:
            hostel_id: Hostel UUID
            include_shared: Include shared templates
            category: Optional category filter
            
        Returns:
            ServiceResult with templates
        """
        try:
            query = self.session.query(Announcement).filter(
                Announcement.is_deleted == False,
                Announcement.metadata.op('->>')('is_template') == 'true'
            )
            
            if include_shared:
                query = query.filter(
                    (Announcement.hostel_id == hostel_id) |
                    (Announcement.metadata.op('->>')('is_shared_template') == 'true')
                )
            else:
                query = query.filter(Announcement.hostel_id == hostel_id)
            
            if category:
                query = query.filter(Announcement.category == category)
            
            templates = query.order_by(Announcement.created_at.desc()).all()
            
            return ServiceResult.ok(data={
                'templates': [self._serialize_template(t) for t in templates],
                'total': len(templates),
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="LIST_FAILED")
    
    # ==================== Template Rendering ====================
    
    def render_template(
        self,
        template_id: UUID,
        dto: RenderTemplateDTO
    ) -> ServiceResult:
        """
        Render template with variable substitution.
        
        Args:
            template_id: Template UUID
            dto: Rendering data
            
        Returns:
            ServiceResult with rendered content
        """
        try:
            template = self.repository.find_by_id(template_id)
            if not template:
                return ServiceResult.fail(
                    f"Template {template_id} not found",
                    error_code="NOT_FOUND"
                )
            
            # Render title and content
            rendered_title = self._render_string(template.title, dto.variables)
            rendered_content = self._render_string(template.content, dto.variables)
            
            # Validate all variables were provided
            template_variables = template.metadata.get('template_variables', [])
            missing_variables = [
                v for v in template_variables
                if v not in dto.variables
            ]
            
            return ServiceResult.ok(data={
                'rendered_title': rendered_title,
                'rendered_content': rendered_content,
                'variables_used': list(dto.variables.keys()),
                'missing_variables': missing_variables,
                'has_missing_variables': len(missing_variables) > 0,
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="RENDER_FAILED")
    
    def validate_template(
        self,
        template_id: UUID
    ) -> ServiceResult:
        """
        Validate template structure and variables.
        
        Args:
            template_id: Template UUID
            
        Returns:
            ServiceResult with validation results
        """
        try:
            template = self.repository.find_by_id(template_id)
            if not template:
                return ServiceResult.fail(
                    f"Template {template_id} not found",
                    error_code="NOT_FOUND"
                )
            
            errors = []
            warnings = []
            
            # Extract variables
            title_vars = self._extract_variables(template.title)
            content_vars = self._extract_variables(template.content)
            all_vars = list(set(title_vars + content_vars))
            
            # Check for undefined variables
            declared_vars = template.metadata.get('template_variables', [])
            undefined = [v for v in all_vars if v not in declared_vars]
            if undefined:
                warnings.append(f"Undeclared variables: {', '.join(undefined)}")
            
            # Check for unused declared variables
            unused = [v for v in declared_vars if v not in all_vars]
            if unused:
                warnings.append(f"Unused variables: {', '.join(unused)}")
            
            # Check template syntax
            try:
                test_vars = {v: 'test' for v in all_vars}
                self._render_string(template.title, test_vars)
                self._render_string(template.content, test_vars)
            except Exception as e:
                errors.append(f"Template syntax error: {str(e)}")
            
            is_valid = len(errors) == 0
            
            return ServiceResult.ok(data={
                'is_valid': is_valid,
                'errors': errors,
                'warnings': warnings,
                'detected_variables': all_vars,
                'declared_variables': declared_vars,
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="VALIDATION_FAILED")
    
    # ==================== Template Usage ====================
    
    def create_from_template(
        self,
        template_id: UUID,
        hostel_id: UUID,
        dto: CreateFromTemplateDTO,
        user_id: UUID
    ) -> ServiceResult:
        """
        Create announcement from template.
        
        Args:
            template_id: Template UUID
            hostel_id: Target hostel UUID
            dto: Creation data
            user_id: User creating announcement
            
        Returns:
            ServiceResult with created announcement
        """
        try:
            template = self.repository.find_by_id(template_id)
            if not template:
                return ServiceResult.fail(
                    f"Template {template_id} not found",
                    error_code="NOT_FOUND"
                )
            
            # Render with variables
            rendered_title = self._render_string(
                template.title,
                dto.variable_overrides
            )
            rendered_content = self._render_string(
                template.content,
                dto.variable_overrides
            )
            
            # Create announcement
            announcement = Announcement(
                hostel_id=hostel_id,
                created_by_id=user_id,
                title=rendered_title,
                content=rendered_content,
                category=template.category,
                priority=template.priority,
                status='draft',
                metadata={
                    'created_from_template': str(template_id),
                    'template_name': template.metadata.get('template_name'),
                }
            )
            
            # Apply field overrides
            if dto.field_overrides:
                for field, value in dto.field_overrides.items():
                    if hasattr(announcement, field):
                        setattr(announcement, field, value)
            
            self.session.add(announcement)
            
            # Update template usage count
            if not template.metadata:
                template.metadata = {}
            usage_count = template.metadata.get('usage_count', 0)
            template.metadata['usage_count'] = usage_count + 1
            template.metadata['last_used_at'] = datetime.utcnow().isoformat()
            
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(template, 'metadata')
            
            self.session.commit()
            
            self.event_publisher.publish('announcement.created_from_template', {
                'announcement_id': str(announcement.id),
                'template_id': str(template_id),
                'hostel_id': str(hostel_id),
            })
            
            return ServiceResult.ok(
                data={
                    'announcement_id': str(announcement.id),
                    'title': rendered_title,
                    'template_id': str(template_id),
                },
                announcement_id=str(announcement.id)
            )
            
        except Exception as e:
            self.session.rollback()
            return ServiceResult.fail(str(e), error_code="CREATE_FROM_TEMPLATE_FAILED")
    
    def get_popular_templates(
        self,
        hostel_id: UUID,
        limit: int = 10
    ) -> ServiceResult:
        """
        Get most popular templates by usage.
        
        Args:
            hostel_id: Hostel UUID
            limit: Maximum results
            
        Returns:
            ServiceResult with popular templates
        """
        try:
            templates = (
                self.session.query(Announcement)
                .filter(
                    Announcement.is_deleted == False,
                    Announcement.metadata.op('->>')('is_template') == 'true',
                    (Announcement.hostel_id == hostel_id) |
                    (Announcement.metadata.op('->>')('is_shared_template') == 'true')
                )
                .all()
            )
            
            # Sort by usage count
            templates_with_usage = [
                (t, t.metadata.get('usage_count', 0))
                for t in templates
            ]
            templates_with_usage.sort(key=lambda x: x[1], reverse=True)
            
            popular = templates_with_usage[:limit]
            
            return ServiceResult.ok(data={
                'templates': [
                    {
                        **self._serialize_template(t),
                        'usage_count': usage,
                    }
                    for t, usage in popular
                ],
                'total': len(popular),
            })
            
        except Exception as e:
            return ServiceResult.fail(str(e), error_code="FETCH_POPULAR_FAILED")
    
    # ==================== Helper Methods ====================
    
    def _extract_variables(
        self,
        title: Optional[str] = None,
        content: Optional[str] = None
    ) -> List[str]:
        """Extract variable names from template strings."""
        variables = set()
        
        # Pattern: {variable_name}
        pattern = r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}'
        
        if title:
            variables.update(re.findall(pattern, title))
        if content:
            variables.update(re.findall(pattern, content))
        
        return sorted(list(variables))
    
    def _render_string(
        self,
        template_string: str,
        variables: Dict[str, Any]
    ) -> str:
        """Render template string with variables."""
        rendered = template_string
        
        for key, value in variables.items():
            placeholder = f'{{{key}}}'
            rendered = rendered.replace(placeholder, str(value))
        
        return rendered
    
    def _serialize_template(self, template) -> Dict[str, Any]:
        """Serialize template to dictionary."""
        metadata = template.metadata or {}
        
        return {
            'id': str(template.id),
            'name': metadata.get('template_name', 'Untitled Template'),
            'description': metadata.get('template_description'),
            'title_template': template.title,
            'content_template': template.content,
            'category': template.category.value,
            'priority': template.priority.value,
            'variables': metadata.get('template_variables', []),
            'is_shared': metadata.get('is_shared_template', False),
            'usage_count': metadata.get('usage_count', 0),
            'last_used_at': metadata.get('last_used_at'),
            'created_at': template.created_at.isoformat(),
            'updated_at': template.updated_at.isoformat() if template.updated_at else None,
        }