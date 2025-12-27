"""
Notification Template Management API Endpoints

Provides CRUD operations for notification templates supporting multiple channels
(email, SMS, push) with dynamic variable substitution and preview functionality.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.dependencies import AuthenticationDependency
from app.services.notification.notification_template_service import NotificationTemplateService
from app.schemas.notification import (
    NotificationTemplate,
    NotificationTemplateCreate,
    NotificationTemplateUpdate,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/notifications/templates",
    tags=["Notifications - Templates"],
)


def get_template_service() -> NotificationTemplateService:
    """
    Dependency injection for NotificationTemplateService.
    
    Raises:
        NotImplementedError: When DI container is not configured
    """
    raise NotImplementedError(
        "NotificationTemplateService dependency must be configured in your DI container"
    )


def get_current_user(auth: AuthenticationDependency = Depends()):
    """
    Extract and validate the current authenticated user.
    
    Returns:
        Current authenticated user object
    """
    try:
        return auth.get_current_user()
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )


def verify_admin_user(current_user) -> None:
    """
    Verify that the current user has admin privileges.
    
    Args:
        current_user: Authenticated user object
        
    Raises:
        HTTPException: If user is not an admin
    """
    if not getattr(current_user, 'is_admin', False) and \
       not getattr(current_user, 'is_superuser', False):
        logger.warning(
            f"Unauthorized template management attempt by user_id={current_user.id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for template management"
        )


@router.post(
    "",
    response_model=NotificationTemplate,
    status_code=status.HTTP_201_CREATED,
    summary="Create notification template",
    description="Create a new notification template for email, SMS, or push notifications",
    response_description="Created notification template",
)
async def create_template(
    payload: NotificationTemplateCreate,
    template_service: NotificationTemplateService = Depends(get_template_service),
    current_user = Depends(get_current_user),
) -> NotificationTemplate:
    """
    Create a new notification template.
    
    Templates support variable substitution using placeholders like {{variable_name}}.
    Requires admin privileges.
    
    Args:
        payload: Template creation data
        template_service: Injected template service
        current_user: Authenticated user from dependency
        
    Returns:
        NotificationTemplate: Created template
        
    Raises:
        HTTPException: If creation fails or user lacks permissions
    """
    try:
        # Verify admin privileges
        verify_admin_user(current_user)
        
        logger.info(
            f"Creating template: name={payload.name}, channel={payload.channel}, "
            f"created_by={current_user.id}"
        )
        
        result = template_service.create_template(data=payload)
        template = result.unwrap()
        
        logger.info(
            f"Template created successfully: template_id={template.id}, "
            f"name={template.name}"
        )
        
        return template
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid template data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid template data: {str(e)}"
        )
    except Exception as e:
        logger.error(
            f"Failed to create template: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create notification template"
        )


@router.get(
    "",
    response_model=List[NotificationTemplate],
    summary="List notification templates",
    description="Retrieve all notification templates with optional filtering",
    response_description="List of notification templates",
)
async def list_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    channel: Optional[str] = Query(None, description="Filter by channel (email, sms, push)"),
    active_only: bool = Query(True, description="Show only active templates"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    template_service: NotificationTemplateService = Depends(get_template_service),
    current_user = Depends(get_current_user),
) -> List[NotificationTemplate]:
    """
    List all notification templates with optional filtering.
    
    Supports filtering by category, channel, and active status.
    Requires admin privileges.
    
    Args:
        category: Optional category filter
        channel: Optional channel filter (email, sms, push)
        active_only: Only return active templates
        page: Page number for pagination
        page_size: Number of items per page
        template_service: Injected template service
        current_user: Authenticated user from dependency
        
    Returns:
        List[NotificationTemplate]: Filtered list of templates
        
    Raises:
        HTTPException: If retrieval fails or user lacks permissions
    """
    try:
        # Verify admin privileges
        verify_admin_user(current_user)
        
        logger.debug(
            f"Listing templates: category={category}, channel={channel}, "
            f"active_only={active_only}, page={page}"
        )
        
        filters = {
            "category": category,
            "channel": channel,
            "active_only": active_only,
            "page": page,
            "page_size": page_size,
        }
        
        result = template_service.list_templates(filters=filters)
        templates = result.unwrap()
        
        logger.info(f"Retrieved {len(templates)} template(s)")
        
        return templates
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to list templates: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve templates"
        )


@router.get(
    "/{template_id}",
    response_model=NotificationTemplate,
    summary="Get notification template",
    description="Retrieve a specific notification template by ID",
    response_description="Notification template details",
)
async def get_template(
    template_id: str = Path(..., description="Template ID"),
    template_service: NotificationTemplateService = Depends(get_template_service),
    current_user = Depends(get_current_user),
) -> NotificationTemplate:
    """
    Get a specific notification template by ID.
    
    Requires admin privileges.
    
    Args:
        template_id: ID of the template to retrieve
        template_service: Injected template service
        current_user: Authenticated user from dependency
        
    Returns:
        NotificationTemplate: Template details
        
    Raises:
        HTTPException: If template not found or user lacks permissions
    """
    try:
        # Verify admin privileges
        verify_admin_user(current_user)
        
        logger.debug(f"Fetching template: template_id={template_id}")
        
        result = template_service.get_template(template_id=template_id)
        template = result.unwrap()
        
        logger.info(f"Template retrieved: template_id={template_id}")
        
        return template
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Template not found: template_id={template_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    except Exception as e:
        logger.error(
            f"Failed to get template {template_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve template"
        )


@router.patch(
    "/{template_id}",
    response_model=NotificationTemplate,
    summary="Update notification template",
    description="Partially update a notification template",
    response_description="Updated notification template",
)
async def update_template(
    template_id: str = Path(..., description="Template ID"),
    payload: NotificationTemplateUpdate = ...,
    template_service: NotificationTemplateService = Depends(get_template_service),
    current_user = Depends(get_current_user),
) -> NotificationTemplate:
    """
    Update a notification template.
    
    Only the fields provided in the payload will be updated.
    Requires admin privileges.
    
    Args:
        template_id: ID of the template to update
        payload: Partial template update data
        template_service: Injected template service
        current_user: Authenticated user from dependency
        
    Returns:
        NotificationTemplate: Updated template
        
    Raises:
        HTTPException: If update fails or user lacks permissions
    """
    try:
        # Verify admin privileges
        verify_admin_user(current_user)
        
        logger.info(
            f"Updating template: template_id={template_id}, "
            f"fields={payload.dict(exclude_unset=True).keys()}"
        )
        
        result = template_service.update_template(
            template_id=template_id, 
            data=payload
        )
        template = result.unwrap()
        
        logger.info(f"Template updated successfully: template_id={template_id}")
        
        return template
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            f"Invalid update data or template not found: template_id={template_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    except Exception as e:
        logger.error(
            f"Failed to update template {template_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update template"
        )


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete notification template",
    description="Delete a notification template (soft delete if configured)",
    response_description="Template deleted successfully",
)
async def delete_template(
    template_id: str = Path(..., description="Template ID"),
    template_service: NotificationTemplateService = Depends(get_template_service),
    current_user = Depends(get_current_user),
) -> None:
    """
    Delete a notification template.
    
    This may perform a soft delete (marking as inactive) rather than 
    permanent deletion to preserve historical data.
    Requires admin privileges.
    
    Args:
        template_id: ID of the template to delete
        template_service: Injected template service
        current_user: Authenticated user from dependency
        
    Raises:
        HTTPException: If deletion fails or user lacks permissions
    """
    try:
        # Verify admin privileges
        verify_admin_user(current_user)
        
        logger.info(f"Deleting template: template_id={template_id}")
        
        result = template_service.delete_template(template_id=template_id)
        result.unwrap()
        
        logger.info(f"Template deleted successfully: template_id={template_id}")
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Template not found for deletion: template_id={template_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    except Exception as e:
        logger.error(
            f"Failed to delete template {template_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete template"
        )


@router.post(
    "/{template_id}/preview",
    response_model=TemplatePreviewResponse,
    summary="Preview notification template",
    description="Preview a template with sample variables rendered",
    response_description="Rendered template preview",
)
async def preview_template(
    template_id: str = Path(..., description="Template ID"),
    payload: TemplatePreviewRequest = ...,
    template_service: NotificationTemplateService = Depends(get_template_service),
    current_user = Depends(get_current_user),
) -> TemplatePreviewResponse:
    """
    Preview a notification template with variable substitution.
    
    Renders the template with provided variables to preview the final output.
    Useful for testing templates before deployment.
    Requires admin privileges.
    
    Args:
        template_id: ID of the template to preview
        payload: Variables to substitute in the template
        template_service: Injected template service
        current_user: Authenticated user from dependency
        
    Returns:
        TemplatePreviewResponse: Rendered template content
        
    Raises:
        HTTPException: If preview generation fails or user lacks permissions
    """
    try:
        # Verify admin privileges
        verify_admin_user(current_user)
        
        logger.info(
            f"Generating template preview: template_id={template_id}, "
            f"variables={list(payload.variables.keys()) if hasattr(payload, 'variables') else []}"
        )
        
        variables = payload.variables if hasattr(payload, 'variables') else payload
        
        result = template_service.preview_template(
            template_id=template_id, 
            variables=variables
        )
        preview = result.unwrap()
        
        logger.info(f"Preview generated successfully: template_id={template_id}")
        
        return preview
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(
            f"Invalid template or variables for preview: template_id={template_id}, "
            f"error={str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid template or variables: {str(e)}"
        )
    except Exception as e:
        logger.error(
            f"Failed to generate preview for template {template_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate template preview"
        )