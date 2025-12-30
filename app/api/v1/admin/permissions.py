from typing import Any, List, Optional, Dict
from functools import lru_cache
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, status, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator

from app.api import deps
from app.core.exceptions import PermissionNotFoundError, InvalidPermissionError
from app.core.logging import get_logger
from app.core.cache import cache_result, invalidate_cache
from app.core.security import PermissionValidator
from app.schemas.admin import (
    AdminPermissions,
    PermissionMatrix,
    RolePermissions,
    PermissionCheck,
)
from app.services.admin.admin_permission_service import AdminPermissionService

logger = get_logger(__name__)
router = APIRouter(prefix="/permissions", tags=["admin:permissions"])


class PermissionScope(str, Enum):
    """Permission scope enumeration"""
    GLOBAL = "global"
    HOSTEL = "hostel"
    DEPARTMENT = "department"
    TEAM = "team"
    PERSONAL = "personal"


class PermissionAction(str, Enum):
    """Permission action enumeration"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    APPROVE = "approve"
    OVERRIDE = "override"
    EXPORT = "export"
    IMPORT = "import"


class PermissionResource(str, Enum):
    """Permission resource enumeration"""
    BOOKINGS = "bookings"
    GUESTS = "guests"
    ROOMS = "rooms"
    PAYMENTS = "payments"
    REPORTS = "reports"
    USERS = "users"
    SETTINGS = "settings"
    OVERRIDES = "overrides"


class EnhancedPermissionCheck(BaseModel):
    """Enhanced permission check schema"""
    resource: PermissionResource = Field(...)
    action: PermissionAction = Field(...)
    scope: PermissionScope = Field(default=PermissionScope.HOSTEL)
    hostel_id: Optional[str] = None
    resource_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    check_inheritance: bool = Field(default=True)
    
    @validator('hostel_id')
    def validate_hostel_id(cls, v, values):
        """Validate hostel_id is provided for hostel-scoped permissions"""
        if values.get('scope') == PermissionScope.HOSTEL and not v:
            raise ValueError("hostel_id is required for hostel-scoped permissions")
        return v


class PermissionUpdateRequest(BaseModel):
    """Schema for updating permissions"""
    permissions: Dict[str, Any] = Field(...)
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    reason: str = Field(..., min_length=10, max_length=500)
    notify_admin: bool = Field(default=True)
    
    @validator('permissions')
    def validate_permissions_structure(cls, v):
        """Validate permission structure"""
        if not isinstance(v, dict):
            raise ValueError("Permissions must be a dictionary")
        # Add more specific validation as needed
        return v


class RolePermissionTemplate(BaseModel):
    """Schema for role permission template"""
    role_name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=10, max_length=500)
    permissions: Dict[str, Any] = Field(...)
    is_template: bool = Field(default=True)
    parent_role: Optional[str] = None
    restrictions: Optional[Dict[str, Any]] = Field(default_factory=dict)


class PermissionAuditLog(BaseModel):
    """Schema for permission audit log"""
    id: str
    admin_id: str
    hostel_id: Optional[str]
    action: str
    resource: str
    old_permissions: Optional[Dict[str, Any]]
    new_permissions: Optional[Dict[str, Any]]
    reason: Optional[str]
    changed_by: str
    changed_at: str
    effective_date: Optional[str]
    expiry_date: Optional[str]


# Enhanced dependency injection
@lru_cache()
def get_permission_service(
    db: Session = Depends(deps.get_db),
) -> AdminPermissionService:
    """Optimized permission service dependency with caching."""
    return AdminPermissionService(db=db)


@router.get(
    "/admins/{admin_id}/hostels/{hostel_id}",
    response_model=AdminPermissions,
    summary="Get comprehensive admin permissions for hostel",
    description="Retrieve detailed admin permissions with inheritance and context",
)
@cache_result(expire_time=300)  # Cache for 5 minutes
async def get_admin_permissions(
    admin_id: str,
    hostel_id: str,
    include_inherited: bool = Query(True, description="Include inherited permissions"),
    include_effective_permissions: bool = Query(True, description="Include computed effective permissions"),
    include_restrictions: bool = Query(True, description="Include permission restrictions"),
    as_of_date: Optional[str] = Query(None, description="Get permissions as of specific date (ISO format)"),
    current_admin=Depends(deps.get_super_admin_user),
    service: AdminPermissionService = Depends(get_permission_service),
) -> AdminPermissions:
    """
    Get comprehensive admin permissions with inheritance resolution and temporal queries.
    """
    try:
        # Verify requesting admin has permission to view target admin's permissions
        can_view = await service.validate_permission_view_access(
            requesting_admin_id=current_admin.id,
            target_admin_id=admin_id,
            hostel_id=hostel_id
        )
        if not can_view:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view target admin's permissions"
            )
        
        permissions = await service.get_admin_permissions(
            admin_id=admin_id,
            hostel_id=hostel_id,
            include_inherited=include_inherited,
            include_effective_permissions=include_effective_permissions,
            include_restrictions=include_restrictions,
            as_of_date=as_of_date
        )
        
        if not permissions:
            raise PermissionNotFoundError(f"Permissions not found for admin {admin_id} in hostel {hostel_id}")
        
        return permissions
        
    except (HTTPException, PermissionNotFoundError):
        raise
    except Exception as e:
        logger.error(f"Failed to get admin permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve admin permissions"
        )


@router.put(
    "/admins/{admin_id}/hostels/{hostel_id}",
    response_model=AdminPermissions,
    summary="Update admin permissions with validation",
    description="Update admin permissions with comprehensive validation and audit trail",
)
async def update_admin_permissions(
    admin_id: str,
    hostel_id: str,
    payload: PermissionUpdateRequest,
    validate_business_rules: bool = Query(True, description="Validate against business rules"),
    create_backup: bool = Query(True, description="Create permission backup before update"),
    current_admin=Depends(deps.get_super_admin_user),
    service: AdminPermissionService = Depends(get_permission_service),
) -> AdminPermissions:
    """
    Update admin permissions with comprehensive validation, backup, and audit trail.
    """
    try:
        # Verify requesting admin has permission to modify target admin's permissions
        can_modify = await service.validate_permission_modify_access(
            requesting_admin_id=current_admin.id,
            target_admin_id=admin_id,
            hostel_id=hostel_id
        )
        if not can_modify:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to modify target admin's permissions"
            )
        
        # Validate business rules if requested
        if validate_business_rules:
            rule_violations = await service.validate_permission_business_rules(
                admin_id=admin_id,
                hostel_id=hostel_id,
                new_permissions=payload.permissions
            )
            if rule_violations:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Business rule violations: {', '.join(rule_violations)}"
                )
        
        # Create backup if requested
        if create_backup:
            await service.create_permission_backup(
                admin_id=admin_id,
                hostel_id=hostel_id,
                created_by=current_admin.id
            )
        
        updated_permissions = await service.update_admin_permissions(
            admin_id=admin_id,
            hostel_id=hostel_id,
            payload=payload,
            updated_by=current_admin.id
        )
        
        # Invalidate related caches
        await invalidate_cache(f"permissions:admin:{admin_id}:hostel:{hostel_id}")
        await invalidate_cache(f"permissions:matrix")
        
        logger.info(f"Permissions updated for admin {admin_id} in hostel {hostel_id} by {current_admin.id}")
        return updated_permissions
        
    except HTTPException:
        raise
    except InvalidPermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid permission update: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to update admin permissions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update admin permissions"
        )


@router.post(
    "/check",
    summary="Check admin permission with context",
    description="Check if current admin has specific permission with contextual validation",
)
async def check_permission(
    payload: EnhancedPermissionCheck,
    include_reasoning: bool = Query(True, description="Include reasoning for permission decision"),
    check_temporal: bool = Query(False, description="Check if permission is temporally valid"),
    current_admin=Depends(deps.get_admin_user),
    service: AdminPermissionService = Depends(get_permission_service),
) -> Dict[str, Any]:
    """
    Check permission with enhanced validation and contextual reasoning.
    """
    try:
        permission_result = await service.check_permission_enhanced(
            admin_id=current_admin.id,
            payload=payload,
            include_reasoning=include_reasoning,
            check_temporal=check_temporal
        )
        
        return permission_result
        
    except Exception as e:
        logger.error(f"Failed to check permission: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check permission"
        )


@router.get(
    "/matrix",
    response_model=PermissionMatrix,
    summary="Get comprehensive permission matrix",
    description="Retrieve complete permission matrix with role hierarchies and inheritance",
)
@cache_result(expire_time=1800)  # Cache for 30 minutes
async def get_permission_matrix(
    include_templates: bool = Query(True, description="Include role templates"),
    include_inheritance: bool = Query(True, description="Show inheritance relationships"),
    include_restrictions: bool = Query(True, description="Include permission restrictions"),
    format_output: str = Query("detailed", regex="^(summary|detailed|export)$", description="Output format"),
    current_admin=Depends(deps.get_super_admin_user),
    service: AdminPermissionService = Depends(get_permission_service),
) -> PermissionMatrix:
    """
    Get comprehensive permission matrix with enhanced information and formatting.
    """
    try:
        matrix = await service.get_permission_matrix(
            include_templates=include_templates,
            include_inheritance=include_inheritance,
            include_restrictions=include_restrictions,
            format_output=format_output
        )
        
        return matrix
        
    except Exception as e:
        logger.error(f"Failed to get permission matrix: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve permission matrix"
        )


@router.get(
    "/roles/{role_name}",
    response_model=RolePermissions,
    summary="Get detailed role permissions",
    description="Retrieve comprehensive permissions for specific role with inheritance",
)
@cache_result(expire_time=900)  # Cache for 15 minutes
async def get_role_permissions(
    role_name: str,
    include_inherited: bool = Query(True, description="Include inherited permissions"),
    include_restrictions: bool = Query(True, description="Include role restrictions"),
    include_usage_stats: bool = Query(False, description="Include usage statistics"),
    current_admin=Depends(deps.get_super_admin_user),
    service: AdminPermissionService = Depends(get_permission_service),
) -> RolePermissions:
    """
    Get detailed role permissions with inheritance and usage analytics.
    """
    try:
        role_permissions = await service.get_role_permissions(
            role_name=role_name,
            include_inherited=include_inherited,
            include_restrictions=include_restrictions,
            include_usage_stats=include_usage_stats
        )
        
        if not role_permissions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role '{role_name}' not found"
            )
        
        return role_permissions
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get role permissions for {role_name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve role permissions"
        )


@router.put(
    "/roles/{role_name}",
    response_model=RolePermissions,
    summary="Update role permissions with validation",
    description="Update role permissions with comprehensive validation and impact analysis",
)
async def update_role_permissions(
    role_name: str,
    payload: RolePermissionTemplate,
    validate_impact: bool = Query(True, description="Validate impact on existing admins"),
    create_backup: bool = Query(True, description="Create backup before update"),
    notify_affected_admins: bool = Query(False, description="Notify affected admins"),
    current_admin=Depends(deps.get_super_admin_user),
    service: AdminPermissionService = Depends(get_permission_service),
) -> RolePermissions:
    """
    Update role permissions with impact analysis and affected admin notifications.
    """
    try:
        # Validate impact on existing admins if requested
        if validate_impact:
            impact_analysis = await service.analyze_role_permission_impact(
                role_name=role_name,
                new_permissions=payload.permissions
            )
            if impact_analysis['high_impact_count'] > 0:
                logger.warning(f"High impact role update for {role_name}: {impact_analysis['high_impact_count']} admins affected")
        
        # Create backup if requested
        if create_backup:
            await service.create_role_permission_backup(
                role_name=role_name,
                created_by=current_admin.id
            )
        
        updated_role = await service.update_role_permissions(
            role_name=role_name,
            payload=payload,
            updated_by=current_admin.id,
            notify_affected_admins=notify_affected_admins
        )
        
        # Invalidate related caches
        await invalidate_cache(f"permissions:role:{role_name}")
        await invalidate_cache(f"permissions:matrix")
        
        logger.info(f"Role permissions updated for {role_name} by {current_admin.id}")
        return updated_role
        
    except Exception as e:
        logger.error(f"Failed to update role permissions for {role_name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update role permissions"
        )


@router.get(
    "/audit/{admin_id}",
    response_model=List[PermissionAuditLog],
    summary="Get permission audit log for admin",
    description="Retrieve comprehensive audit log of permission changes for admin",
)
async def get_permission_audit_log(
    admin_id: str,
    hostel_id: Optional[str] = Query(None, description="Filter by hostel ID"),
    days: int = Query(90, ge=1, le=365, description="Days to look back"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    include_system_changes: bool = Query(False, description="Include system-initiated changes"),
    current_admin=Depends(deps.get_admin_user),
    service: AdminPermissionService = Depends(get_permission_service),
) -> List[PermissionAuditLog]:
    """
    Get comprehensive permission audit log with filtering and pagination.
    """
    try:
        # Verify access to audit log
        can_view_audit = await service.validate_audit_access(
            requesting_admin_id=current_admin.id,
            target_admin_id=admin_id
        )
        if not can_view_audit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view audit log"
            )
        
        audit_log = await service.get_permission_audit_log(
            admin_id=admin_id,
            hostel_id=hostel_id,
            days=days,
            page=page,
            limit=limit,
            include_system_changes=include_system_changes
        )
        
        return audit_log
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get permission audit log: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve permission audit log"
        )


@router.post(
    "/validate/bulk",
    summary="Bulk validate permissions",
    description="Validate multiple permission checks in a single request",
)
async def bulk_validate_permissions(
    permission_checks: List[EnhancedPermissionCheck] = Body(..., min_items=1, max_items=100),
    fail_on_first_deny: bool = Query(False, description="Stop processing on first denied permission"),
    current_admin=Depends(deps.get_admin_user),
    service: AdminPermissionService = Depends(get_permission_service),
) -> Dict[str, Any]:
    """
    Perform bulk permission validation with optimization and early termination.
    """
    try:
        results = await service.bulk_validate_permissions(
            admin_id=current_admin.id,
            permission_checks=permission_checks,
            fail_on_first_deny=fail_on_first_deny
        )
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to perform bulk permission validation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate permissions"
        )


@router.get(
    "/templates",
    summary="Get role permission templates",
    description="Retrieve available role permission templates",
)
@cache_result(expire_time=3600)  # Cache for 1 hour
async def get_permission_templates(
    category: Optional[str] = Query(None, description="Filter by template category"),
    include_inactive: bool = Query(False, description="Include inactive templates"),
    current_admin=Depends(deps.get_super_admin_user),
    service: AdminPermissionService = Depends(get_permission_service),
) -> List[RolePermissionTemplate]:
    """
    Get available role permission templates for role creation and modification.
    """
    try:
        templates = await service.get_permission_templates(
            category=category,
            include_inactive=include_inactive
        )
        
        return templates
        
    except Exception as e:
        logger.error(f"Failed to get permission templates: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve permission templates"
        )