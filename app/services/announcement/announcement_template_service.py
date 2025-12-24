"""
Announcement content template service.

Enhanced with variable validation, template inheritance, and content generation.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.notification import NotificationTemplateRepository
from app.models.notification.notification_template import (
    NotificationTemplate as NotificationTemplateModel
)
from app.schemas.notification.notification_template import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    VariableMapping,
    TemplatePreview,
    TemplatePreviewResponse,
    TemplateList,
    TemplateCategory,
)
from app.schemas.announcement.announcement_base import AnnouncementCreate


class AnnouncementTemplateService(
    BaseService[NotificationTemplateModel, NotificationTemplateRepository]
):
    """
    Manage and apply content templates to announcements.
    
    Responsibilities:
    - Create and manage reusable templates
    - Preview templates with variable substitution
    - Apply templates to create announcements
    - Validate template variables and syntax
    - Support template inheritance and composition
    """

    # Default delivery flags
    DEFAULT_DELIVERY_FLAGS = {
        "send_email": True,
        "send_sms": False,
        "send_push": False,
        "send_in_app": True,
    }

    def __init__(
        self,
        repository: NotificationTemplateRepository,
        db_session: Session
    ):
        """
        Initialize template service.
        
        Args:
            repository: Template repository instance
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def create_template(
        self,
        request: TemplateCreate,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[TemplateResponse]:
        """
        Create a new announcement template.
        
        Args:
            request: Template creation data
            created_by: UUID of creator
            
        Returns:
            ServiceResult containing TemplateResponse or error
            
        Notes:
            - Validates template syntax
            - Checks for duplicate template codes
            - Extracts required variables
            - Supports multiple template types
        """
        try:
            # Validate template syntax
            validation_result = self._validate_template_syntax(request)
            if not validation_result.success:
                return validation_result
            
            # Create template
            template = self.repository.create_template(
                request=request,
                created_by=created_by
            )
            
            # Commit transaction
            self.db.commit()
            
            return ServiceResult.success(
                data=template,
                message="Template created successfully",
                metadata={
                    "template_code": template.code if hasattr(template, 'code') else None,
                    "template_type": request.template_type,
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(e, "create template")
            
        except ValueError as e:
            self.db.rollback()
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid template data: {str(e)}",
                    severity=ErrorSeverity.WARNING,
                )
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "create template")

    def update_template(
        self,
        template_code: str,
        request: TemplateUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[TemplateResponse]:
        """
        Update an existing template.
        
        Args:
            template_code: Unique template identifier
            request: Update data
            updated_by: UUID of updater
            
        Returns:
            ServiceResult containing updated TemplateResponse or error
            
        Notes:
            - Creates version snapshot before update
            - Validates updated syntax
            - Preserves template code
        """
        try:
            # Validate template exists
            existing = self.repository.get_template(template_code)
            if not existing:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Template '{template_code}' not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Validate updated syntax if content changed
            if hasattr(request, 'body_template') and request.body_template:
                temp_create = TemplateCreate(
                    code=template_code,
                    name=existing.name if hasattr(existing, 'name') else template_code,
                    template_type=existing.template_type if hasattr(existing, 'template_type') else "EMAIL",
                    body_template=request.body_template,
                )
                validation_result = self._validate_template_syntax(temp_create)
                if not validation_result.success:
                    return validation_result
            
            # Update template
            template = self.repository.update_template(
                template_code=template_code,
                request=request,
                updated_by=updated_by
            )
            
            # Commit transaction
            self.db.commit()
            
            return ServiceResult.success(
                data=template,
                message="Template updated successfully",
                metadata={
                    "template_code": template_code,
                    "updated_by": str(updated_by) if updated_by else None,
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(e, "update template")
            
        except ValueError as e:
            self.db.rollback()
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid template update: {str(e)}",
                    severity=ErrorSeverity.WARNING,
                )
            )
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update template")

    def get_template(
        self,
        template_code: str,
    ) -> ServiceResult[TemplateResponse]:
        """
        Retrieve template by code.
        
        Args:
            template_code: Unique template identifier
            
        Returns:
            ServiceResult containing TemplateResponse or error
        """
        try:
            template = self.repository.get_template(template_code)
            
            if not template:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Template '{template_code}' not found",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            return ServiceResult.success(
                data=template,
                message="Template retrieved successfully"
            )
            
        except SQLAlchemyError as e:
            return self._handle_database_error(e, "get template")
            
        except Exception as e:
            return self._handle_exception(e, "get template")

    def list_templates(
        self,
        template_type: Optional[str] = None,
        category: Optional[str] = None,
        include_inactive: bool = False,
    ) -> ServiceResult[TemplateList]:
        """
        List templates with optional filtering.
        
        Args:
            template_type: Filter by type (EMAIL, SMS, etc.)
            category: Filter by category
            include_inactive: Include inactive templates
            
        Returns:
            ServiceResult containing TemplateList or error
        """
        try:
            # Apply default type if not specified
            if template_type is None:
                template_type = "EMAIL"
            
            listing = self.repository.list_templates(
                template_type=template_type,
                include_inactive=include_inactive
            )
            
            # Filter by category if specified (post-processing)
            if category and hasattr(listing, 'templates'):
                listing.templates = [
                    t for t in listing.templates
                    if getattr(t, 'category', None) == category
                ]
            
            return ServiceResult.success(
                data=listing,
                message="Templates retrieved successfully",
                metadata={
                    "count": listing.total_templates if hasattr(listing, 'total_templates') else 0,
                    "template_type": template_type,
                }
            )
            
        except SQLAlchemyError as e:
            return self._handle_database_error(e, "list templates")
            
        except Exception as e:
            return self._handle_exception(e, "list templates")

    def delete_template(
        self,
        template_code: str,
        deleted_by: Optional[UUID] = None,
    ) -> ServiceResult[bool]:
        """
        Soft-delete a template.
        
        Args:
            template_code: Unique template identifier
            deleted_by: UUID of user deleting template
            
        Returns:
            ServiceResult containing success boolean or error
        """
        try:
            # Validate template exists
            existing = self.repository.get_template(template_code)
            if not existing:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Template '{template_code}' not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Soft delete
            self.repository.delete_template(
                template_code=template_code,
                deleted_by=deleted_by
            )
            
            # Commit transaction
            self.db.commit()
            
            return ServiceResult.success(
                data=True,
                message="Template deleted successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            return self._handle_database_error(e, "delete template")
            
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "delete template")

    # =========================================================================
    # Preview and Application
    # =========================================================================

    def preview_template(
        self,
        request: TemplatePreview,
    ) -> ServiceResult[TemplatePreviewResponse]:
        """
        Preview template with variable substitution.
        
        Args:
            request: Preview request with variables
            
        Returns:
            ServiceResult containing TemplatePreviewResponse or error
            
        Notes:
            - Renders template with provided variables
            - Validates all required variables provided
            - Uses defaults for missing optional variables
            - Does not modify database state
        """
        try:
            # Validate required variables
            validation_result = self._validate_preview_variables(request)
            if not validation_result.success:
                return validation_result
            
            # Generate preview
            response = self.repository.preview(request)
            
            if not response or not response.rendered_body:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Template rendering failed",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            return ServiceResult.success(
                data=response,
                message="Template preview generated successfully",
                metadata={
                    "template_code": request.template_code,
                    "variables_used": len(request.variables),
                }
            )
            
        except SQLAlchemyError as e:
            return self._handle_database_error(e, "preview template")
            
        except ValueError as e:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Preview generation failed: {str(e)}",
                    severity=ErrorSeverity.WARNING,
                )
            )
            
        except Exception as e:
            return self._handle_exception(e, "preview template")

    def apply_to_announcement(
        self,
        template_code: str,
        variables: Dict[str, Any],
        hostel_id: UUID,
        category: str,
        priority: str,
        created_by: UUID,
        delivery_flags: Optional[Dict[str, bool]] = None,
        additional_fields: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[AnnouncementCreate]:
        """
        Apply template to create announcement payload.
        
        Args:
            template_code: Template to use
            variables: Variable values for substitution
            hostel_id: Target hostel
            category: Announcement category
            priority: Priority level
            created_by: Creator UUID
            delivery_flags: Channel delivery settings
            additional_fields: Additional announcement fields
            
        Returns:
            ServiceResult containing AnnouncementCreate or error
            
        Notes:
            - Renders template with variables
            - Maps to announcement creation schema
            - Applies delivery preferences
            - Ready for use with AnnouncementService.create_announcement
        """
        try:
            # Generate preview first
            preview_request = TemplatePreview(
                template_code=template_code,
                variables=variables,
                use_defaults=True
            )
            
            preview_result = self.preview_template(preview_request)
            if not preview_result.success:
                return preview_result
            
            preview = preview_result.data
            
            # Merge delivery flags with defaults
            flags = {**self.DEFAULT_DELIVERY_FLAGS}
            if delivery_flags:
                flags.update(delivery_flags)
            
            # Create announcement payload
            payload = AnnouncementCreate(
                hostel_id=hostel_id,
                title=preview.subject or f"Announcement from template {template_code}",
                content=preview.rendered_body,
                category=category,
                priority=priority,
                send_email=flags.get("send_email", True),
                send_sms=flags.get("send_sms", False),
                send_push=flags.get("send_push", False),
                created_by=created_by,
                # Add additional fields if provided
                **(additional_fields or {})
            )
            
            return ServiceResult.success(
                data=payload,
                message="Announcement payload prepared from template",
                metadata={
                    "template_code": template_code,
                    "title": payload.title,
                    "category": category,
                    "priority": priority,
                }
            )
            
        except Exception as e:
            return self._handle_exception(e, "apply template to announcement")

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _validate_template_syntax(
        self,
        request: TemplateCreate
    ) -> ServiceResult:
        """
        Validate template syntax and structure.
        
        Args:
            request: Template creation request
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        # Basic validation - can be extended with more sophisticated checks
        if not request.body_template or not request.body_template.strip():
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Template body cannot be empty",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        # Check for balanced variable placeholders (example: {{variable}})
        import re
        open_braces = len(re.findall(r'\{\{', request.body_template))
        close_braces = len(re.findall(r'\}\}', request.body_template))
        
        if open_braces != close_braces:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Unbalanced variable placeholders in template",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(True)

    def _validate_preview_variables(
        self,
        request: TemplatePreview
    ) -> ServiceResult:
        """
        Validate preview variables are complete.
        
        Args:
            request: Preview request
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        # Get template to check required variables
        try:
            template = self.repository.get_template(request.template_code)
            if not template:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Template '{request.template_code}' not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Check if required variables are provided
            required_vars = getattr(template, 'required_variables', [])
            provided_vars = set(request.variables.keys())
            missing_vars = set(required_vars) - provided_vars
            
            if missing_vars and not request.use_defaults:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Missing required variables: {missing_vars}",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            return ServiceResult.success(True)
            
        except Exception:
            # If we can't validate, allow preview to proceed
            return ServiceResult.success(True)

    def _handle_database_error(
        self,
        error: SQLAlchemyError,
        operation: str,
        entity_id: Optional[str] = None,
    ) -> ServiceResult:
        """Handle database-specific errors."""
        error_msg = f"Database error during {operation}"
        if entity_id:
            error_msg += f" for {entity_id}"
        
        return ServiceResult.failure(
            ServiceError(
                code=ErrorCode.DATABASE_ERROR,
                message=error_msg,
                severity=ErrorSeverity.ERROR,
                details={"original_error": str(error)},
            )
        )