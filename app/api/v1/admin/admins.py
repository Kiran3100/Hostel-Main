from typing import Any, Dict, List, Optional
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status  # ✅ ADDED Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator

from app.api import deps
from app.core.exceptions import AdminNotFoundError, ValidationError
from app.services.admin.admin_user_service import AdminUserService
from app.services.admin.admin_role_service import AdminRoleService
from app.schemas.user.user_response import UserDetail, UserListItem, UserStats
from app.core.cache import cache_result
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admins", tags=["admin:admins"])


# Enhanced Pydantic schemas
class AdminCreateRequest(BaseModel):
    """Schema for creating admin users"""
    full_name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    employee_id: Optional[str] = Field(None, max_length=50)
    role: str = Field(..., min_length=1)
    department: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, pattern=r'^\+?1?-?\.?\s?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$')
    is_active: bool = Field(default=True)
    
    @validator('email')
    def validate_email_domain(cls, v):
        """Validate email domain if needed"""
        # Add custom domain validation if required
        return v.lower()


class AdminUpdateRequest(BaseModel):
    """Schema for updating admin users"""
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    employee_id: Optional[str] = Field(None, max_length=50)
    role: Optional[str] = None
    department: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, pattern=r'^\+?1?-?\.?\s?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$')
    is_active: Optional[bool] = None


class AdminResponse(BaseModel):
    """Enhanced admin response schema"""
    id: str
    full_name: str
    email: str
    employee_id: Optional[str]
    role: str
    department: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str
    last_login: Optional[str]


# Dependency injection with caching
@lru_cache()
def get_admin_user_service(db: Session = Depends(deps.get_db)) -> AdminUserService:
    """
    Optimized dependency for AdminUserService with caching.
    
    Args:
        db: Database session
        
    Returns:
        AdminUserService instance
    """
    return AdminUserService(db=db)


@lru_cache()
def get_admin_role_service(db: Session = Depends(deps.get_db)) -> AdminRoleService:
    """
    Optimized dependency for AdminRoleService with caching.
    
    Args:
        db: Database session
        
    Returns:
        AdminRoleService instance
    """
    return AdminRoleService(db=db)


# Enhanced endpoints with better error handling and validation
@router.get(
    "",
    response_model=List[UserListItem],
    summary="List admin users with advanced filtering",
    description="Retrieve a list of admin users with optional search and filtering capabilities",
)
async def list_admins(
    q: Optional[str] = Query(
        None, 
        description="Search term (name/email/employee ID)",
        max_length=100
    ),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(deps.get_db),
    current_admin=Depends(deps.get_super_admin_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> List[UserListItem]:
    """
    Search/filter admin users with enhanced pagination and sorting.
    
    Features:
    - Full-text search across name, email, and employee ID
    - Active/inactive filtering
    - Pagination support
    - Flexible sorting
    - Performance optimized queries
    """
    try:
        return await service.search_admins(
            query=q,
            is_active=is_active,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            db=db
        )
    except ValidationError as e:
        logger.warning(f"Validation error in list_admins: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid search parameters: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in list_admins: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve admin list"
        )


@router.get(
    "/{admin_id}",
    response_model=UserDetail,
    summary="Get detailed admin information",
    description="Retrieve comprehensive details for a specific admin user",
)
async def get_admin_detail(
    admin_id: str = Path(..., min_length=1, description="Admin user ID"),
    include_permissions: bool = Query(False, description="Include permission details"),
    include_audit_log: bool = Query(False, description="Include recent audit activities"),
    db: Session = Depends(deps.get_db),
    current_admin=Depends(deps.get_admin_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> UserDetail:
    """
    Get comprehensive admin details with optional extended information.
    """
    try:
        admin = await service.get_admin_by_id(
            admin_id=admin_id,
            include_permissions=include_permissions,
            include_audit_log=include_audit_log,
            db=db
        )
        
        if not admin:
            raise AdminNotFoundError(f"Admin with ID {admin_id} not found")
            
        return admin
        
    except AdminNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admin with ID {admin_id} not found"
        )
    except Exception as e:
        logger.error(f"Error retrieving admin {admin_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve admin details"
        )


@router.post(
    "",
    response_model=AdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new admin user",
    description="Create a new admin user with comprehensive validation",
)
async def create_admin(
    payload: AdminCreateRequest,
    send_invitation: bool = Query(True, description="Send email invitation to new admin"),
    db: Session = Depends(deps.get_db),
    current_admin=Depends(deps.get_super_admin_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> AdminResponse:
    """
    Create a new admin user with enhanced validation and optional invitation email.
    
    Features:
    - Comprehensive input validation
    - Duplicate detection
    - Automatic invitation email
    - Audit logging
    """
    try:
        # Check for existing admin with same email
        existing_admin = await service.get_admin_by_email(payload.email, db=db)
        if existing_admin:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Admin with email {payload.email} already exists"
            )
        
        admin = await service.create_admin_user(
            payload=payload.dict(),
            send_invitation=send_invitation,
            created_by=current_admin.id,
            db=db
        )
        
        logger.info(f"Admin {admin.id} created successfully by {current_admin.id}")
        return admin
        
    except HTTPException:
        raise
    except ValidationError as e:
        logger.warning(f"Validation error in create_admin: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to create admin: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create admin user"
        )


@router.patch(
    "/{admin_id}",
    response_model=AdminResponse,
    summary="Update admin user",
    description="Update existing admin user with partial data",
)
async def update_admin(
    admin_id: str = Path(..., description="Admin user ID"),
    payload: AdminUpdateRequest = ...,
    db: Session = Depends(deps.get_db),
    current_admin=Depends(deps.get_super_admin_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> AdminResponse:
    """
    Update admin user with enhanced validation and audit logging.
    """
    try:
        # Verify admin exists
        existing_admin = await service.get_admin_by_id(admin_id, db=db)
        if not existing_admin:
            raise AdminNotFoundError(f"Admin with ID {admin_id} not found")
        
        updated_admin = await service.update_admin_user(
            admin_id=admin_id,
            payload=payload.dict(exclude_unset=True),
            updated_by=current_admin.id,
            db=db
        )
        
        logger.info(f"Admin {admin_id} updated successfully by {current_admin.id}")
        return updated_admin
        
    except AdminNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admin with ID {admin_id} not found"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to update admin {admin_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update admin user"
        )


@router.post(
    "/{admin_id}/activate",
    response_model=AdminResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate admin account",
    description="Activate a suspended or inactive admin account",
)
async def activate_admin(
    admin_id: str = Path(..., description="Admin user ID"),
    reason: Optional[str] = Query(None, max_length=500, description="Reason for activation"),
    send_notification: bool = Query(True, description="Send notification to admin"),
    db: Session = Depends(deps.get_db),
    current_admin=Depends(deps.get_super_admin_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> AdminResponse:
    """
    Activate admin account with proper audit trail and notifications.
    """
    try:
        activated_admin = await service.activate_admin(
            admin_id=admin_id,
            reason=reason,
            activated_by=current_admin.id,
            send_notification=send_notification,
            db=db
        )
        
        logger.info(f"Admin {admin_id} activated by {current_admin.id}")
        return activated_admin
        
    except AdminNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admin with ID {admin_id} not found"
        )
    except Exception as e:
        logger.error(f"Failed to activate admin {admin_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate admin account"
        )


@router.post(
    "/{admin_id}/suspend",
    response_model=AdminResponse,
    status_code=status.HTTP_200_OK,
    summary="Suspend admin account",
    description="Suspend an admin account with mandatory reason",
)
async def suspend_admin(
    admin_id: str = Path(..., description="Admin user ID"),
    reason: str = Query(..., min_length=10, max_length=500, description="Required reason for suspension"),
    notify_admin: bool = Query(True, description="Send notification to suspended admin"),
    effective_date: Optional[str] = Query(None, description="ISO date when suspension takes effect"),
    db: Session = Depends(deps.get_db),
    current_admin=Depends(deps.get_super_admin_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> AdminResponse:
    """
    Suspend admin account with comprehensive audit trail.
    """
    try:
        suspended_admin = await service.suspend_admin(
            admin_id=admin_id,
            reason=reason,
            suspended_by=current_admin.id,
            notify_admin=notify_admin,
            effective_date=effective_date,
            db=db
        )
        
        logger.warning(f"Admin {admin_id} suspended by {current_admin.id}. Reason: {reason}")
        return suspended_admin
        
    except AdminNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admin with ID {admin_id} not found"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid suspension parameters: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to suspend admin {admin_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to suspend admin account"
        )


# Enhanced hierarchy and statistics endpoints
@router.get(
    "/hierarchy",
    response_model=Dict[str, Any],
    summary="Get comprehensive admin hierarchy",
    description="Retrieve organizational hierarchy with reporting relationships",
)
@cache_result(expire_time=300)  # Cache for 5 minutes
async def get_admin_hierarchy(
    include_inactive: bool = Query(False, description="Include inactive admins in hierarchy"),
    depth: int = Query(10, ge=1, le=20, description="Maximum hierarchy depth"),
    db: Session = Depends(deps.get_db),
    current_admin=Depends(deps.get_super_admin_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> Dict[str, Any]:
    """
    Return comprehensive organizational hierarchy with enhanced filtering.
    """
    try:
        hierarchy = await service.get_admin_hierarchy(
            include_inactive=include_inactive,
            max_depth=depth,
            db=db
        )
        return hierarchy
        
    except Exception as e:
        logger.error(f"Failed to retrieve admin hierarchy: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve admin hierarchy"
        )


@router.get(
    "/stats",
    response_model=UserStats,
    summary="Get comprehensive admin statistics",
    description="Retrieve detailed statistics about admin users and activities",
)
@cache_result(expire_time=600)  # Cache for 10 minutes
async def get_admin_stats(
    period_days: int = Query(30, ge=1, le=365, description="Statistics period in days"),
    include_inactive: bool = Query(False, description="Include inactive admins in stats"),
    breakdown_by_role: bool = Query(True, description="Include role-based breakdown"),
    db: Session = Depends(deps.get_db),
    current_admin=Depends(deps.get_super_admin_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> UserStats:
    """
    Get comprehensive admin statistics with customizable parameters.
    """
    try:
        stats = await service.get_admin_statistics(
            period_days=period_days,
            include_inactive=include_inactive,
            breakdown_by_role=breakdown_by_role,
            db=db
        )
        return stats
        
    except Exception as e:
        logger.error(f"Failed to retrieve admin statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve admin statistics"
        )


# Bulk operations endpoint
@router.post(
    "/bulk/update",
    response_model=List[AdminResponse],
    summary="Bulk update admin users",
    description="Update multiple admin users in a single operation",
)
async def bulk_update_admins(
    updates: List[Dict[str, Any]] = Body(..., min_items=1, max_items=100),  # ✅ FIXED: Changed Field to Body
    dry_run: bool = Query(False, description="Preview changes without applying them"),
    db: Session = Depends(deps.get_db),
    current_admin=Depends(deps.get_super_admin_user),
    service: AdminUserService = Depends(get_admin_user_service),
) -> List[AdminResponse]:
    """
    Perform bulk updates on admin users with validation and rollback capability.
    """
    try:
        updated_admins = await service.bulk_update_admins(
            updates=updates,
            updated_by=current_admin.id,
            dry_run=dry_run,
            db=db
        )
        
        if not dry_run:
            logger.info(f"Bulk updated {len(updated_admins)} admins by {current_admin.id}")
            
        return updated_admins
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bulk update validation failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to perform bulk update: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform bulk update"
        )