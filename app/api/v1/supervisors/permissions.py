"""
Supervisor Permission Management

Handles supervisor permissions including:
- Permission retrieval and updates
- Permission templates
- Bulk permission operations
- Permission history and auditing
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from app.core.dependencies import AuthenticationDependency
from app.services.supervisor.supervisor_permission_service import SupervisorPermissionService
from app.schemas.supervisor import (
    SupervisorPermissionsUpdate,
    SupervisorPermissions,
    SupervisorPermissionTemplate,
    SupervisorPermissionHistory,
)

# Router configuration
router = APIRouter(
    prefix="",
    tags=["Supervisors - Permissions"],
)


# ============================================================================
# Dependency Injection
# ============================================================================

def get_permission_service() -> SupervisorPermissionService:
    """
    Dependency provider for SupervisorPermissionService.
    
    Wire this to your DI container or service factory.
    """
    raise NotImplementedError(
        "SupervisorPermissionService dependency must be implemented."
    )


def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """Extract and validate current authenticated user."""
    user = auth.get_current_user()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user


# ============================================================================
# Request/Response Models
# ============================================================================

class PermissionCheckRequest(BaseModel):
    """Request model for permission check"""
    supervisor_id: str = Field(..., description="Supervisor ID")
    permission_key: str = Field(..., description="Permission key to check")


class PermissionCheckResponse(BaseModel):
    """Response model for permission check"""
    supervisor_id: str = Field(..., description="Supervisor ID")
    permission_key: str = Field(..., description="Permission key")
    has_permission: bool = Field(..., description="Whether supervisor has the permission")
    reason: Optional[str] = Field(None, description="Reason for denial if applicable")


class BulkPermissionCheckResponse(BaseModel):
    """Response for bulk permission check"""
    results: List[PermissionCheckResponse] = Field(..., description="Check results")


# ============================================================================
# API Endpoints
# ============================================================================

@router.get(
    "/{supervisor_id}/permissions",
    response_model=SupervisorPermissions,
    summary="Get supervisor permissions",
    description="""
    Retrieve complete permission set for a supervisor.
    
    **Permission Categories**:
    - **Student Management**: View, edit, discipline students
    - **Hostel Operations**: Room management, facility access
    - **Reporting**: View reports, create reports, export data
    - **Administrative**: Manage staff, configure settings
    - **Financial**: View budgets, approve expenses
    - **Security**: Access control, emergency protocols
    
    **Permission Structure**:
    ```json
    {
      "can_manage_students": true,
      "can_approve_visitors": true,
      "can_handle_emergencies": true,
      "can_generate_reports": false,
      ...
    }
    ```
    
    **Includes**:
    - All permission flags
    - Permission source (default, template, custom)
    - Last updated timestamp
    - Effective scope
    """,
    responses={
        200: {"description": "Permissions retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def get_permissions(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    permission_service: SupervisorPermissionService = Depends(get_permission_service),
    current_user: Any = Depends(get_current_user),
) -> SupervisorPermissions:
    """Get complete permission set for supervisor."""
    result = permission_service.get_permissions(supervisor_id=supervisor_id)
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.put(
    "/{supervisor_id}/permissions",
    response_model=SupervisorPermissions,
    summary="Replace permissions",
    description="""
    Replace entire permission set for a supervisor.
    
    **Admin Operation**: Requires elevated privileges.
    
    **Behavior**:
    - Replaces all existing permissions
    - Validates permission structure
    - Maintains audit trail
    - Triggers permission sync
    
    **Validation**:
    - All required permissions must be specified
    - Permission keys must be valid
    - Cannot remove critical safety permissions
    
    **Side Effects**:
    - Invalidates permission cache
    - Logs permission change
    - Notifies affected systems
    - May revoke active sessions
    
    **Note**: Use PATCH for partial updates
    """,
    responses={
        200: {"description": "Permissions updated successfully"},
        400: {"description": "Invalid permission data"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient privileges"},
        404: {"description": "Supervisor not found"},
    }
)
async def update_permissions(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    payload: SupervisorPermissionsUpdate = ...,
    permission_service: SupervisorPermissionService = Depends(get_permission_service),
    current_user: Any = Depends(get_current_user),
) -> SupervisorPermissions:
    """Replace complete permission set."""
    result = permission_service.update_permissions(
        supervisor_id=supervisor_id,
        data=payload.dict(exclude_unset=True),
        updated_by=current_user.id if hasattr(current_user, 'id') else None,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        error_msg = str(error).lower()
        
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        if "permission" in error_msg or "forbidden" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient privileges to update permissions"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.post(
    "/{supervisor_id}/permissions/default",
    response_model=SupervisorPermissions,
    status_code=status.HTTP_201_CREATED,
    summary="Create default permissions for supervisor",
    description="""
    Initialize supervisor with default permission set.
    
    **Default Permissions**:
    - Basic student management
    - Standard reporting access
    - Read-only facility access
    - Emergency response protocols
    - No administrative privileges
    
    **Use Cases**:
    - New supervisor onboarding
    - Permission reset
    - Fallback configuration
    
    **Behavior**:
    - Only creates if no permissions exist
    - Uses system-defined defaults
    - Can be customized later
    
    **Note**: Fails if permissions already exist
    """,
    responses={
        201: {"description": "Default permissions created"},
        400: {"description": "Permissions already exist"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def create_default_permissions(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    permission_service: SupervisorPermissionService = Depends(get_permission_service),
    current_user: Any = Depends(get_current_user),
) -> SupervisorPermissions:
    """Create default permissions for supervisor."""
    result = permission_service.create_default_permissions(
        supervisor_id=supervisor_id,
        created_by=current_user.id if hasattr(current_user, 'id') else None,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        error_msg = str(error).lower()
        
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        if "already exist" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Permissions already exist for this supervisor"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.post(
    "/{supervisor_id}/permissions/apply-template",
    response_model=SupervisorPermissions,
    summary="Apply permission template to supervisor",
    description="""
    Apply a predefined permission template to a supervisor.
    
    **Available Templates**:
    - **basic**: Basic supervisor permissions
    - **standard**: Standard operational permissions
    - **senior**: Senior supervisor with extended access
    - **manager**: Manager-level permissions
    - **emergency**: Emergency response team permissions
    - **maintenance**: Maintenance supervisor permissions
    
    **Template Application**:
    - Replaces existing permissions
    - Inherits all template permissions
    - Can be further customized
    - Maintains template reference
    
    **Validation**:
    - Template must exist
    - Template must be active
    - User must have template application rights
    
    **Use Cases**:
    - Role-based setup
    - Bulk standardization
    - Quick configuration
    - Promotion updates
    """,
    responses={
        200: {"description": "Template applied successfully"},
        400: {"description": "Invalid template or application failed"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor or template not found"},
    }
)
async def apply_permission_template(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    template_name: str = Query(..., min_length=1, description="Template name to apply"),
    permission_service: SupervisorPermissionService = Depends(get_permission_service),
    current_user: Any = Depends(get_current_user),
    overwrite: bool = Query(True, description="Overwrite existing permissions"),
) -> SupervisorPermissions:
    """Apply permission template to supervisor."""
    result = permission_service.apply_permission_template(
        supervisor_id=supervisor_id,
        template_name=template_name,
        overwrite=overwrite,
        applied_by=current_user.id if hasattr(current_user, 'id') else None,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        error_msg = str(error).lower()
        
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.post(
    "/permissions/bulk-apply-template",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Bulk apply permission template",
    description="""
    Apply permission template to multiple supervisors in one operation.
    
    **Bulk Operation**:
    - Applies same template to all specified supervisors
    - Atomic transaction when possible
    - Detailed error reporting for failures
    - Partial success supported
    
    **Use Cases**:
    - Mass role updates
    - Department-wide standardization
    - Emergency permission changes
    - Organizational restructuring
    
    **Limits**:
    - Maximum 100 supervisors per request
    - Rate limited to prevent abuse
    
    **Processing**:
    - Synchronous for small batches (< 10)
    - Asynchronous for large batches (>= 10)
    
    **Admin Operation**: Requires elevated privileges
    """,
    responses={
        204: {"description": "Template applied to all supervisors"},
        207: {"description": "Partial success (multi-status response)"},
        400: {"description": "Invalid request"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient privileges"},
    }
)
async def bulk_apply_permission_template(
    template_name: str = Query(..., min_length=1, description="Template name"),
    supervisor_ids: List[str] = Query(..., min_items=1, max_items=100, description="List of supervisor IDs"),
    permission_service: SupervisorPermissionService = Depends(get_permission_service),
    current_user: Any = Depends(get_current_user),
) -> None:
    """Bulk apply permission template to multiple supervisors."""
    result = permission_service.bulk_apply_permission_template(
        template_name=template_name,
        supervisor_ids=supervisor_ids,
        applied_by=current_user.id if hasattr(current_user, 'id') else None,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        error_msg = str(error).lower()
        
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        if "permission" in error_msg or "forbidden" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient privileges for bulk operation"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )


@router.get(
    "/permissions/templates",
    response_model=List[SupervisorPermissionTemplate],
    summary="List available permission templates",
    description="""
    Retrieve list of all available permission templates.
    
    **Template Information**:
    - Template name and description
    - Included permissions
    - Target roles/positions
    - Usage statistics
    - Last updated date
    
    **Filtering**:
    - By active/inactive status
    - By category/department
    - By permission level
    
    **Use Cases**:
    - Template selection UI
    - Permission documentation
    - Template management
    - Audit and compliance
    """,
    responses={
        200: {"description": "Templates retrieved successfully"},
        401: {"description": "Authentication required"},
    }
)
async def list_permission_templates(
    permission_service: SupervisorPermissionService = Depends(get_permission_service),
    current_user: Any = Depends(get_current_user),
    include_inactive: bool = Query(False, description="Include inactive templates"),
    category: Optional[str] = Query(None, description="Filter by category"),
) -> List[SupervisorPermissionTemplate]:
    """List all available permission templates."""
    result = permission_service.list_available_templates(
        filters={
            "include_inactive": include_inactive,
            "category": category,
        }
    )
    
    if result.is_err():
        error = result.unwrap_err()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()


@router.post(
    "/{supervisor_id}/permissions/check",
    response_model=PermissionCheckResponse,
    summary="Check specific permission for supervisor",
    description="""
    Check if a supervisor has a specific permission.
    
    **Permission Check**:
    - Fast permission validation
    - Considers inherited permissions
    - Checks effective permissions
    - Returns denial reason if applicable
    
    **Use Cases**:
    - UI element visibility
    - Action authorization
    - Feature access control
    - API endpoint guards
    
    **Performance**:
    - Cached for performance
    - Millisecond response time
    - Batch-friendly
    """,
    responses={
        200: {"description": "Permission check completed"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def check_permission(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    permission_key: str = Query(..., min_length=1, description="Permission key to check"),
    permission_service: SupervisorPermissionService = Depends(get_permission_service),
    current_user: Any = Depends(get_current_user),
) -> PermissionCheckResponse:
    """Check if supervisor has specific permission."""
    result = permission_service.check_permission(
        supervisor_id=supervisor_id,
        permission_key=permission_key,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return PermissionCheckResponse(**result.unwrap())


@router.post(
    "/permissions/bulk-check",
    response_model=BulkPermissionCheckResponse,
    summary="Bulk check permissions",
    description="""
    Check multiple permissions for multiple supervisors in one request.
    
    **Bulk Check**:
    - Efficient batch permission validation
    - Single round-trip to server
    - Optimized database queries
    - Parallel processing
    
    **Request Format**:
    ```json
    [
      {"supervisor_id": "sup_123", "permission_key": "can_manage_students"},
      {"supervisor_id": "sup_456", "permission_key": "can_approve_expenses"}
    ]
    ```
    
    **Limits**:
    - Maximum 50 checks per request
    - Rate limited per user
    
    **Use Cases**:
    - UI batch rendering
    - Multi-user authorization
    - Report permission filtering
    - Bulk feature access checks
    """,
    responses={
        200: {"description": "Bulk check completed"},
        400: {"description": "Invalid request"},
        401: {"description": "Authentication required"},
    }
)
async def bulk_check_permissions(
    requests: List[PermissionCheckRequest] = Query(..., min_items=1, max_items=50),
    permission_service: SupervisorPermissionService = Depends(get_permission_service),
    current_user: Any = Depends(get_current_user),
) -> BulkPermissionCheckResponse:
    """Bulk check permissions for multiple supervisors."""
    result = permission_service.bulk_check_permissions(
        requests=[req.dict() for req in requests],
    )
    
    if result.is_err():
        error = result.unwrap_err()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    results_data = result.unwrap()
    return BulkPermissionCheckResponse(
        results=[PermissionCheckResponse(**r) for r in results_data.get("results", [])]
    )


@router.get(
    "/{supervisor_id}/permissions/history",
    response_model=List[SupervisorPermissionHistory],
    summary="Get permission change history",
    description="""
    Retrieve complete history of permission changes for a supervisor.
    
    **History Includes**:
    - All permission modifications
    - Who made the changes
    - When changes occurred
    - What was changed (before/after)
    - Change reason/notes
    - Change source (manual, template, automated)
    
    **Ordering**: Most recent first
    
    **Filtering**:
    - By date range
    - By changed_by user
    - By permission key
    - By change type
    
    **Use Cases**:
    - Compliance auditing
    - Security investigations
    - Change tracking
    - Access reviews
    - Debugging permission issues
    """,
    responses={
        200: {"description": "History retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Supervisor not found"},
    }
)
async def get_permission_history(
    supervisor_id: str = Path(..., description="Unique supervisor identifier"),
    permission_service: SupervisorPermissionService = Depends(get_permission_service),
    current_user: Any = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500, description="Maximum history entries"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> List[SupervisorPermissionHistory]:
    """Get permission change history."""
    result = permission_service.get_permission_history(
        supervisor_id=supervisor_id,
        limit=limit,
        offset=offset,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if "not found" in str(error).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supervisor with ID '{supervisor_id}' not found"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )
    
    return result.unwrap()