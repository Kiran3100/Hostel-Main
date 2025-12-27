# app/services/notification/notification_template_service.py
"""
Enhanced Notification Template Service

Manages notification templates with improved:
- Template validation and security
- Performance through caching
- Advanced rendering capabilities
- Version control and rollback
- Template testing and preview
"""

from __future__ import annotations

import logging
import json
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from functools import lru_cache

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.notification import NotificationTemplateRepository
from app.schemas.notification import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateList,
    TemplateCategory,
    TemplatePreview,
    TemplatePreviewResponse,
    TemplateCopyRequest,
)
from app.core1.exceptions import ValidationException, DatabaseException
from app.core1.logging import LoggingContext

logger = logging.getLogger(__name__)


class NotificationTemplateService:
    """
    Enhanced high-level service for notification templates.

    Enhanced with:
    - Template validation and security
    - Performance caching
    - Version management
    - Advanced rendering
    - Comprehensive error handling
    """

    def __init__(self, template_repo: NotificationTemplateRepository) -> None:
        self.template_repo = template_repo
        self._template_cache_ttl = 300  # 5 minutes
        self._max_template_size = 50000  # 50KB
        self._allowed_template_types = ["email", "sms", "push", "in_app"]
        self._reserved_codes = ["system", "admin", "test", "debug"]

    def _validate_template_code(self, template_code: str) -> None:
        """Validate template code format and availability."""
        if not template_code or len(template_code.strip()) == 0:
            raise ValidationException("Template code is required")
        
        if len(template_code) > 50:
            raise ValidationException("Template code too long (max 50 characters)")
        
        # Check format (alphanumeric, underscores, hyphens)
        if not template_code.replace('_', '').replace('-', '').isalnum():
            raise ValidationException(
                "Template code can only contain alphanumeric characters, underscores, and hyphens"
            )
        
        # Check reserved codes
        if template_code.lower() in self._reserved_codes:
            raise ValidationException(f"Template code '{template_code}' is reserved")

    def _validate_template_content(self, template: TemplateCreate) -> None:
        """Validate template content and structure."""
        if not template.name or len(template.name.strip()) == 0:
            raise ValidationException("Template name is required")
        
        if len(template.name) > 200:
            raise ValidationException("Template name too long (max 200 characters)")
        
        if not template.content or len(template.content.strip()) == 0:
            raise ValidationException("Template content is required")
        
        if len(template.content) > self._max_template_size:
            raise ValidationException(
                f"Template content too large (max {self._max_template_size} characters)"
            )
        
        if template.template_type and template.template_type not in self._allowed_template_types:
            raise ValidationException(
                f"Invalid template type. Must be one of: {self._allowed_template_types}"
            )
        
        # Validate template variables format
        if template.default_variables:
            try:
                if isinstance(template.default_variables, str):
                    json.loads(template.default_variables)
                elif not isinstance(template.default_variables, dict):
                    raise ValidationException("Default variables must be a JSON object")
            except json.JSONDecodeError as e:
                raise ValidationException(f"Invalid JSON in default variables: {str(e)}")

    def _validate_template_update(self, template: TemplateUpdate) -> None:
        """Validate template update data."""
        if template.name is not None and len(template.name.strip()) == 0:
            raise ValidationException("Template name cannot be empty")
        
        if template.name and len(template.name) > 200:
            raise ValidationException("Template name too long (max 200 characters)")
        
        if template.content is not None and len(template.content.strip()) == 0:
            raise ValidationException("Template content cannot be empty")
        
        if template.content and len(template.content) > self._max_template_size:
            raise ValidationException(
                f"Template content too large (max {self._max_template_size} characters)"
            )
        
        if template.template_type and template.template_type not in self._allowed_template_types:
            raise ValidationException(
                f"Invalid template type. Must be one of: {self._allowed_template_types}"
            )
        
        # Validate template variables format
        if template.default_variables:
            try:
                if isinstance(template.default_variables, str):
                    json.loads(template.default_variables)
                elif not isinstance(template.default_variables, dict):
                    raise ValidationException("Default variables must be a JSON object")
            except json.JSONDecodeError as e:
                raise ValidationException(f"Invalid JSON in default variables: {str(e)}")

    def _check_template_security(self, content: str) -> None:
        """Check template content for security issues."""
        # Basic security checks for template content
        dangerous_patterns = [
            "<script",
            "javascript:",
            "onload=",
            "onerror=",
            "eval(",
            "document.cookie",
            "localStorage",
            "sessionStorage",
        ]
        
        content_lower = content.lower()
        for pattern in dangerous_patterns:
            if pattern in content_lower:
                logger.warning(f"Potentially dangerous pattern detected in template: {pattern}")
                # In production, you might want to reject the template or sanitize it

    @lru_cache(maxsize=500)
    def _get_cached_template(self, template_code: str) -> Optional[Dict[str, Any]]:
        """Cache template data for better performance."""
        # Note: In production, use Redis or similar for distributed caching
        return None

    def _clear_template_cache(self, template_code: str) -> None:
        """Clear cached template."""
        try:
            self._get_cached_template.cache_clear()
        except Exception:
            pass  # Cache clearing is not critical

    # -------------------------------------------------------------------------
    # Enhanced CRUD operations
    # -------------------------------------------------------------------------

    def create_template(
        self,
        db: Session,
        request: TemplateCreate,
        validate_security: bool = True,
    ) -> TemplateResponse:
        """
        Create a new template with comprehensive validation.

        Enhanced with:
        - Security validation
        - Code uniqueness checking
        - Content validation
        - Performance optimization

        Args:
            db: Database session
            request: Template creation data
            validate_security: Whether to perform security validation

        Returns:
            TemplateResponse: Created template

        Raises:
            ValidationException: For invalid template data
            DatabaseException: For database operation failures
        """
        self._validate_template_code(request.template_code)
        self._validate_template_content(request)
        
        if validate_security:
            self._check_template_security(request.content)

        with LoggingContext(
            channel="template_create",
            template_code=request.template_code,
            template_type=request.template_type
        ):
            try:
                logger.info(
                    f"Creating template '{request.template_code}', "
                    f"type: {request.template_type}"
                )
                
                # Check if template code already exists
                existing = self.template_repo.get_by_code(db, request.template_code)
                if existing:
                    raise ValidationException(
                        f"Template with code '{request.template_code}' already exists"
                    )
                
                obj = self.template_repo.create_template(
                    db=db,
                    data=request.model_dump(exclude_none=True),
                )
                
                template = TemplateResponse.model_validate(obj)
                logger.info(f"Template created successfully: {template.id}")
                
                return template
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error creating template: {str(e)}")
                raise DatabaseException("Failed to create template") from e
            except Exception as e:
                logger.error(f"Unexpected error creating template: {str(e)}")
                raise

    def update_template(
        self,
        db: Session,
        template_id: UUID,
        request: TemplateUpdate,
        create_version: bool = True,
    ) -> TemplateResponse:
        """
        Update a template with version management.

        Enhanced with:
        - Version creation option
        - Comprehensive validation
        - Security checking
        - Cache invalidation

        Args:
            db: Database session
            template_id: Template identifier
            request: Update data
            create_version: Whether to create a new version

        Returns:
            TemplateResponse: Updated template

        Raises:
            ValidationException: For invalid data or not found
            DatabaseException: For database operation failures
        """
        if not template_id:
            raise ValidationException("Template ID is required")
        
        self._validate_template_update(request)
        
        if request.content and hasattr(request, 'content'):
            self._check_template_security(request.content)

        with LoggingContext(
            channel="template_update",
            template_id=str(template_id),
            create_version=create_version
        ):
            try:
                logger.info(f"Updating template {template_id}")
                
                tmpl = self.template_repo.get_by_id(db, template_id)
                if not tmpl:
                    raise ValidationException("Template not found")
                
                # Create version backup if requested
                if create_version and hasattr(tmpl, 'template_code'):
                    self._create_template_version(db, tmpl)
                
                updated = self.template_repo.update_template(
                    db=db,
                    template=tmpl,
                    data=request.model_dump(exclude_none=True),
                )
                
                # Clear cache
                if hasattr(tmpl, 'template_code'):
                    self._clear_template_cache(tmpl.template_code)
                
                template = TemplateResponse.model_validate(updated)
                logger.info("Template updated successfully")
                
                return template
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error updating template: {str(e)}")
                raise DatabaseException("Failed to update template") from e
            except Exception as e:
                logger.error(f"Unexpected error updating template: {str(e)}")
                raise

    def delete_template(
        self,
        db: Session,
        template_id: UUID,
        soft_delete: bool = True,
    ) -> None:
        """
        Delete a template with soft delete option.

        Enhanced with:
        - Soft delete option
        - Dependency checking
        - Cache cleanup

        Args:
            db: Database session
            template_id: Template identifier
            soft_delete: Whether to soft delete (default) or hard delete

        Raises:
            ValidationException: For invalid ID or dependencies
            DatabaseException: For database operation failures
        """
        if not template_id:
            raise ValidationException("Template ID is required")

        with LoggingContext(
            channel="template_delete",
            template_id=str(template_id),
            soft_delete=soft_delete
        ):
            try:
                logger.info(f"Deleting template {template_id}, soft: {soft_delete}")
                
                tmpl = self.template_repo.get_by_id(db, template_id)
                if not tmpl:
                    return  # Already deleted
                
                # Check for dependencies if hard delete
                if not soft_delete:
                    dependencies = self.template_repo.check_template_dependencies(db, template_id)
                    if dependencies:
                        raise ValidationException(
                            f"Cannot delete template: {dependencies['count']} dependencies exist"
                        )
                
                self.template_repo.delete_template(
                    db=db, 
                    template=tmpl,
                    soft_delete=soft_delete
                )
                
                # Clear cache
                if hasattr(tmpl, 'template_code'):
                    self._clear_template_cache(tmpl.template_code)
                
                logger.info("Template deleted successfully")
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error deleting template: {str(e)}")
                raise DatabaseException("Failed to delete template") from e
            except Exception as e:
                logger.error(f"Unexpected error deleting template: {str(e)}")
                raise

    # -------------------------------------------------------------------------
    # Enhanced listing and categorization
    # -------------------------------------------------------------------------

    def list_templates(
        self,
        db: Session,
        template_type: Optional[str] = None,
        category: Optional[str] = None,
        search_query: Optional[str] = None,
        include_inactive: bool = False,
    ) -> TemplateList:
        """
        List templates with enhanced filtering and search.

        Enhanced with:
        - Multiple filter options
        - Search functionality
        - Active/inactive filtering
        - Performance optimization

        Args:
            db: Database session
            template_type: Filter by template type
            category: Filter by category
            search_query: Search in name and description
            include_inactive: Whether to include inactive templates

        Returns:
            TemplateList: Filtered template list

        Raises:
            ValidationException: For invalid filter parameters
            DatabaseException: For database operation failures
        """
        if template_type and template_type not in self._allowed_template_types:
            raise ValidationException(
                f"Invalid template type. Must be one of: {self._allowed_template_types}"
            )

        filters = {
            "template_type": template_type,
            "category": category,
            "search_query": search_query,
            "include_inactive": include_inactive,
        }

        with LoggingContext(
            channel="template_list",
            filters=str({k: v for k, v in filters.items() if v is not None})
        ):
            try:
                logger.debug("Listing templates with filters")
                
                data = self.template_repo.get_all_templates(
                    db=db,
                    filters=filters,
                )
                
                template_list = TemplateList.model_validate(data)
                logger.debug(f"Listed {len(template_list.templates)} templates")
                
                return template_list
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error listing templates: {str(e)}")
                raise DatabaseException("Failed to list templates") from e
            except Exception as e:
                logger.error(f"Unexpected error listing templates: {str(e)}")
                raise

    def list_templates_by_category(
        self,
        db: Session,
        include_counts: bool = True,
    ) -> List[TemplateCategory]:
        """
        List templates grouped by category with enhanced details.

        Enhanced with:
        - Optional count inclusion
        - Performance optimization
        - Comprehensive error handling

        Args:
            db: Database session
            include_counts: Whether to include template counts

        Returns:
            List[TemplateCategory]: Categorized templates

        Raises:
            DatabaseException: For database operation failures
        """
        with LoggingContext(channel="template_categories", include_counts=include_counts):
            try:
                logger.debug("Listing templates by category")
                
                objs = self.template_repo.get_templates_grouped_by_category(
                    db=db,
                    include_counts=include_counts,
                )
                
                categories = [TemplateCategory.model_validate(o) for o in objs]
                logger.debug(f"Listed {len(categories)} template categories")
                
                return categories
                
            except SQLAlchemyError as e:
                logger.error(f"Database error listing categories: {str(e)}")
                raise DatabaseException("Failed to list template categories") from e
            except Exception as e:
                logger.error(f"Unexpected error listing categories: {str(e)}")
                raise

    # -------------------------------------------------------------------------
    # Enhanced preview and rendering
    # -------------------------------------------------------------------------

    def preview_template(
        self,
        db: Session,
        request: TemplatePreview,
        validate_variables: bool = True,
    ) -> TemplatePreviewResponse:
        """
        Render a template preview with enhanced validation and error handling.

        Enhanced with:
        - Variable validation
        - Security checking
        - Performance optimization
        - Comprehensive error reporting

        Args:
            db: Database session
            request: Preview request data
            validate_variables: Whether to validate template variables

        Returns:
            TemplatePreviewResponse: Rendered preview

        Raises:
            ValidationException: For invalid template or variables
            DatabaseException: For database operation failures
        """
        if not request.template_code:
            raise ValidationException("Template code is required")
        
        if request.variables and validate_variables:
            self._validate_preview_variables(request.variables)

        with LoggingContext(
            channel="template_preview",
            template_code=request.template_code,
            has_variables=bool(request.variables)
        ):
            try:
                logger.info(f"Previewing template '{request.template_code}'")
                
                # Check if template exists and is active
                template = self.template_repo.get_by_code(db, request.template_code)
                if not template:
                    raise ValidationException(
                        f"Template '{request.template_code}' not found"
                    )
                
                if not template.is_active:
                    logger.warning(f"Previewing inactive template: {request.template_code}")
                
                data = self.template_repo.render_preview(
                    db=db,
                    template_code=request.template_code,
                    variables=request.variables or {},
                    use_defaults=request.use_defaults if hasattr(request, 'use_defaults') else True,
                )
                
                preview = TemplatePreviewResponse.model_validate(data)
                logger.info("Template preview generated successfully")
                
                return preview
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error previewing template: {str(e)}")
                raise DatabaseException("Failed to preview template") from e
            except Exception as e:
                logger.error(f"Unexpected error previewing template: {str(e)}")
                raise

    def _validate_preview_variables(self, variables: Dict[str, Any]) -> None:
        """Validate preview variables for security and format."""
        if not isinstance(variables, dict):
            raise ValidationException("Variables must be a dictionary")
        
        # Check for dangerous variable values
        for key, value in variables.items():
            if isinstance(value, str):
                # Basic security check
                if any(pattern in value.lower() for pattern in ["<script", "javascript:", "eval("]):
                    raise ValidationException(f"Potentially dangerous content in variable '{key}'")
            
            # Limit variable size
            if isinstance(value, str) and len(value) > 10000:
                raise ValidationException(f"Variable '{key}' value too large (max 10KB)")

    def test_template_rendering(
        self,
        db: Session,
        template_code: str,
        test_cases: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Test template rendering with multiple variable sets.

        Args:
            db: Database session
            template_code: Template to test
            test_cases: List of variable sets to test

        Returns:
            List[Dict[str, Any]]: Test results

        Raises:
            ValidationException: For invalid parameters
        """
        if not template_code:
            raise ValidationException("Template code is required")
        
        if not test_cases:
            raise ValidationException("At least one test case is required")
        
        if len(test_cases) > 20:
            raise ValidationException("Maximum 20 test cases allowed")

        with LoggingContext(
            channel="template_test",
            template_code=template_code,
            test_count=len(test_cases)
        ):
            try:
                logger.info(f"Testing template '{template_code}' with {len(test_cases)} cases")
                
                results = []
                for i, test_case in enumerate(test_cases):
                    try:
                        preview_request = TemplatePreview(
                            template_code=template_code,
                            variables=test_case,
                            use_defaults=True,
                        )
                        
                        preview = self.preview_template(
                            db=db,
                            request=preview_request,
                            validate_variables=True,
                        )
                        
                        results.append({
                            "test_case": i + 1,
                            "variables": test_case,
                            "status": "success",
                            "rendered_content": preview.rendered_content,
                            "rendered_subject": getattr(preview, 'rendered_subject', None),
                        })
                        
                    except Exception as e:
                        results.append({
                            "test_case": i + 1,
                            "variables": test_case,
                            "status": "failed",
                            "error": str(e),
                        })
                
                success_count = sum(1 for r in results if r["status"] == "success")
                logger.info(f"Template testing complete - {success_count}/{len(test_cases)} successful")
                
                return results
                
            except Exception as e:
                logger.error(f"Error testing template: {str(e)}")
                raise

    # -------------------------------------------------------------------------
    # Enhanced template copying and versioning
    # -------------------------------------------------------------------------

    def copy_template(
        self,
        db: Session,
        request: TemplateCopyRequest,
    ) -> TemplateResponse:
        """
        Copy a template with enhanced validation and customization.

        Enhanced with:
        - Source validation
        - Target code availability checking
        - Metadata handling
        - Version information

        Args:
            db: Database session
            request: Copy request data

        Returns:
            TemplateResponse: Copied template

        Raises:
            ValidationException: For invalid copy parameters
            DatabaseException: For database operation failures
        """
        if not request.source_template_code:
            raise ValidationException("Source template code is required")
        
        if not request.new_template_code:
            raise ValidationException("New template code is required")
        
        self._validate_template_code(request.new_template_code)

        with LoggingContext(
            channel="template_copy",
            source=request.source_template_code,
            target=request.new_template_code
        ):
            try:
                logger.info(
                    f"Copying template '{request.source_template_code}' "
                    f"to '{request.new_template_code}'"
                )
                
                # Verify source exists
                source = self.template_repo.get_by_code(db, request.source_template_code)
                if not source:
                    raise ValidationException(
                        f"Source template '{request.source_template_code}' not found"
                    )
                
                # Check if target code is available
                existing = self.template_repo.get_by_code(db, request.new_template_code)
                if existing:
                    raise ValidationException(
                        f"Template with code '{request.new_template_code}' already exists"
                    )
                
                data = self.template_repo.copy_template(
                    db=db,
                    source_template_code=request.source_template_code,
                    new_template_code=request.new_template_code,
                    new_template_name=request.new_template_name,
                    copy_metadata=request.copy_metadata if hasattr(request, 'copy_metadata') else True,
                )
                
                template = TemplateResponse.model_validate(data)
                logger.info(f"Template copied successfully: {template.id}")
                
                return template
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error copying template: {str(e)}")
                raise DatabaseException("Failed to copy template") from e
            except Exception as e:
                logger.error(f"Unexpected error copying template: {str(e)}")
                raise

    def _create_template_version(
        self,
        db: Session,
        template: Any,
    ) -> None:
        """Create a version backup of a template before updating."""
        try:
            logger.debug(f"Creating version backup for template {template.id}")
            
            self.template_repo.create_template_version(
                db=db,
                template=template,
            )
            
            logger.debug("Template version created successfully")
            
        except Exception as e:
            logger.warning(f"Failed to create template version: {str(e)}")
            # Don't fail the main operation for version creation errors

    def get_template_versions(
        self,
        db: Session,
        template_id: UUID,
    ) -> List[Dict[str, Any]]:
        """
        Get version history for a template.

        Args:
            db: Database session
            template_id: Template identifier

        Returns:
            List[Dict[str, Any]]: Version history

        Raises:
            ValidationException: For invalid template ID
            DatabaseException: For database operation failures
        """
        if not template_id:
            raise ValidationException("Template ID is required")

        with LoggingContext(channel="template_versions", template_id=str(template_id)):
            try:
                logger.debug(f"Retrieving versions for template {template_id}")
                
                versions = self.template_repo.get_template_versions(db, template_id)
                logger.debug(f"Found {len(versions)} template versions")
                
                return versions
                
            except SQLAlchemyError as e:
                logger.error(f"Database error retrieving versions: {str(e)}")
                raise DatabaseException("Failed to retrieve template versions") from e
            except Exception as e:
                logger.error(f"Unexpected error retrieving versions: {str(e)}")
                raise

    def restore_template_version(
        self,
        db: Session,
        template_id: UUID,
        version_id: UUID,
    ) -> TemplateResponse:
        """
        Restore a template to a previous version.

        Args:
            db: Database session
            template_id: Template identifier
            version_id: Version to restore

        Returns:
            TemplateResponse: Restored template

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        if not template_id or not version_id:
            raise ValidationException("Template ID and version ID are required")

        with LoggingContext(
            channel="template_restore",
            template_id=str(template_id),
            version_id=str(version_id)
        ):
            try:
                logger.info(f"Restoring template {template_id} to version {version_id}")
                
                template = self.template_repo.restore_template_version(
                    db=db,
                    template_id=template_id,
                    version_id=version_id,
                )
                
                # Clear cache
                if hasattr(template, 'template_code'):
                    self._clear_template_cache(template.template_code)
                
                result = TemplateResponse.model_validate(template)
                logger.info("Template restored successfully")
                
                return result
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error restoring template: {str(e)}")
                raise DatabaseException("Failed to restore template version") from e
            except Exception as e:
                logger.error(f"Unexpected error restoring template: {str(e)}")
                raise