from typing import Any, List, Optional
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator

from app.api import deps
from app.core.exceptions import AssignmentNotFoundError, DuplicateAssignmentError
from app.core.logging import get_logger
from app.core.cache import cache_result, invalidate_cache
from app.schemas.admin import (
    AdminHostelAssignment,
    AssignmentCreate,
    AssignmentUpdate,
    BulkAssignment,
    RevokeAssignment,
    AssignmentList,
    HostelAdminList,
)
from app.services.admin.hostel_assignment_service import HostelAssignmentService

logger = get_logger(__name__)
router = APIRouter(prefix="/hostel-assignments", tags=["admin:hostel-assignments"])


class AssignmentFilter(BaseModel):
    """Enhanced filtering for assignments"""
    admin_ids: Optional[List[str]] = None
    hostel_ids: Optional[List[str]] = None
    roles: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_primary: Optional[bool] = None
    created_after: Optional[str] = None
    created_before: Optional[str] = None


class BulkAssignmentValidation(BaseModel):
    """Schema for bulk assignment validation"""
    assignments: List[Dict[str, Any]]
    validate_permissions: bool = Field(default=True)
    send_notifications: bool = Field(default=True)
    dry_run: bool = Field(default=False)


# Enhanced dependency injection
@lru_cache()
def get_hostel_assignment_service(
    db: Session = Depends(deps.get_db),
) -> HostelAssignmentService:
    """Optimized assignment service dependency with caching."""
    return HostelAssignmentService(db=db)


@router.post(
    "",
    response_model=AdminHostelAssignment,
    status_code=status.HTTP_201_CREATED,
    summary="Create admin-hostel assignment with validation",
    description="Assign admin to hostel with comprehensive validation and conflict detection",
)
async def create_assignment(
    payload: AssignmentCreate,
    validate_permissions: bool = Query(True, description="Validate admin permissions for hostel"),
    send_notification: bool = Query(True, description="Send notification to assigned admin"),
    check_conflicts: bool = Query(True, description="Check for assignment conflicts"),
    current_admin=Depends(deps.get_super_admin_user),
    service: HostelAssignmentService = Depends(get_hostel_assignment_service),
) -> AdminHostelAssignment:
    """
    Create admin-hostel assignment with comprehensive validation and audit logging.
    """
    try:
        # Check for existing assignment if conflict checking is enabled
        if check_conflicts:
            existing = await service.check_existing_assignment(
                admin_id=payload.admin_id,
                hostel_id=payload.hostel_id
            )
            if existing:
                raise DuplicateAssignmentError(
                    f"Assignment already exists between admin {payload.admin_id} and hostel {payload.hostel_id}"
                )
        
        assignment = await service.create_assignment(
            payload=payload,
            created_by=current_admin.id,
            validate_permissions=validate_permissions,
            send_notification=send_notification
        )
        
        # Invalidate related caches
        await invalidate_cache(f"assignments:admin:{payload.admin_id}")
        await invalidate_cache(f"assignments:hostel:{payload.hostel_id}")
        
        logger.info(f"Assignment created: admin {payload.admin_id} -> hostel {payload.hostel_id} by {current_admin.id}")
        return assignment
        
    except DuplicateAssignmentError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create assignment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create hostel assignment"
        )


@router.get(
    "",
    response_model=AssignmentList,
    summary="List assignments with advanced filtering",
    description="Retrieve assignments with comprehensive filtering, pagination, and sorting",
)
@cache_result(expire_time=300)  # Cache for 5 minutes
async def list_assignments(
    admin_id: Optional[str] = Query(None, description="Filter by admin ID"),
    hostel_id: Optional[str] = Query(None, description="Filter by hostel ID"),
    role: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_primary: Optional[bool] = Query(None, description="Filter by primary status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    include_metadata: bool = Query(True, description="Include assignment metadata"),
    current_admin=Depends(deps.get_admin_user),
    service: HostelAssignmentService = Depends(get_hostel_assignment_service),
) -> AssignmentList:
    """
    List assignments with advanced filtering and pagination.
    """
    try:
        # Use current admin's ID if not provided and user is not super admin
        target_admin_id = admin_id
        if not target_admin_id and not current_admin.is_super_admin:
            target_admin_id = current_admin.id
        
        assignments = await service.get_assignments_with_filters(
            admin_id=target_admin_id,
            hostel_id=hostel_id,
            role=role,
            is_active=is_active,
            is_primary=is_primary,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_order=sort_order,
            include_metadata=include_metadata,
            requesting_admin_id=current_admin.id
        )
        
        return assignments
        
    except Exception as e:
        logger.error(f"Failed to list assignments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve assignments"
        )


@router.get(
    "/hostel/{hostel_id}",
    response_model=HostelAdminList,
    summary="List all admins assigned to hostel",
    description="Retrieve comprehensive list of admins assigned to specific hostel",
)
@cache_result(expire_time=180)  # Cache for 3 minutes
async def list_hostel_admins(
    hostel_id: str,
    include_inactive: bool = Query(False, description="Include inactive assignments"),
    include_permissions: bool = Query(True, description="Include permission details"),
    include_statistics: bool = Query(False, description="Include usage statistics"),
    current_admin=Depends(deps.get_admin_user),
    service: HostelAssignmentService = Depends(get_hostel_assignment_service),
) -> HostelAdminList:
    """
    Get comprehensive list of admins assigned to a hostel with enhanced metadata.
    """
    try:
        # Verify admin has access to this hostel
        has_access = await service.verify_hostel_access(
            admin_id=current_admin.id,
            hostel_id=hostel_id
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin does not have access to this hostel"
            )
        
        hostel_admins = await service.get_hostel_assignments(
            hostel_id=hostel_id,
            include_inactive=include_inactive,
            include_permissions=include_permissions,
            include_statistics=include_statistics
        )
        
        return hostel_admins
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list hostel admins for {hostel_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve hostel admin assignments"
        )


@router.put(
    "/{assignment_id}",
    response_model=AdminHostelAssignment,
    summary="Update assignment with validation",
    description="Update assignment details with comprehensive validation",
)
async def update_assignment(
    assignment_id: str,
    payload: AssignmentUpdate,
    validate_changes: bool = Query(True, description="Validate assignment changes"),
    send_notification: bool = Query(True, description="Send notification about changes"),
    current_admin=Depends(deps.get_super_admin_user),
    service: HostelAssignmentService = Depends(get_hostel_assignment_service),
) -> AdminHostelAssignment:
    """
    Update assignment with comprehensive validation and audit logging.
    """
    try:
        # Verify assignment exists
        existing_assignment = await service.get_assignment_by_id(assignment_id)
        if not existing_assignment:
            raise AssignmentNotFoundError(f"Assignment {assignment_id} not found")
        
        updated_assignment = await service.update_assignment(
            assignment_id=assignment_id,
            payload=payload,
            updated_by=current_admin.id,
            validate_changes=validate_changes,
            send_notification=send_notification
        )
        
        # Invalidate related caches
        await invalidate_cache(f"assignments:admin:{existing_assignment.admin_id}")
        await invalidate_cache(f"assignments:hostel:{existing_assignment.hostel_id}")
        
        logger.info(f"Assignment {assignment_id} updated by {current_admin.id}")
        return updated_assignment
        
    except AssignmentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment {assignment_id} not found"
        )
    except Exception as e:
        logger.error(f"Failed to update assignment {assignment_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update assignment"
        )


@router.post(
    "/bulk",
    response_model=AssignmentList,
    summary="Bulk create assignments with validation",
    description="Create multiple assignments in a single operation with comprehensive validation",
)
async def bulk_assign(
    payload: BulkAssignment,
    validate_all: bool = Query(True, description="Validate all assignments before creating any"),
    continue_on_error: bool = Query(False, description="Continue processing on individual errors"),
    send_notifications: bool = Query(True, description="Send notifications to assigned admins"),
    current_admin=Depends(deps.get_super_admin_user),
    service: HostelAssignmentService = Depends(get_hostel_assignment_service),
) -> AssignmentList:
    """
    Perform bulk assignment creation with advanced error handling and rollback capability.
    """
    try:
        # Validate payload size
        if len(payload.assignments) > 100:  # Reasonable limit
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bulk assignment limited to 100 assignments per request"
            )
        
        assignments = await service.bulk_assign(
            payload=payload,
            created_by=current_admin.id,
            validate_all=validate_all,
            continue_on_error=continue_on_error,
            send_notifications=send_notifications
        )
        
        # Invalidate relevant caches
        affected_admins = {a.admin_id for a in payload.assignments}
        affected_hostels = {h for assignment in payload.assignments for h in assignment.hostel_ids}
        
        for admin_id in affected_admins:
            await invalidate_cache(f"assignments:admin:{admin_id}")
        for hostel_id in affected_hostels:
            await invalidate_cache(f"assignments:hostel:{hostel_id}")
        
        logger.info(f"Bulk assignment completed: {len(assignments.assignments)} assignments by {current_admin.id}")
        return assignments
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to perform bulk assignment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform bulk assignment"
        )


@router.post(
    "/{assignment_id}/revoke",
    status_code=status.HTTP_200_OK,
    summary="Revoke assignment with audit trail",
    description="Revoke admin-hostel assignment with comprehensive audit logging",
)
async def revoke_assignment(
    assignment_id: str,
    payload: RevokeAssignment,
    effective_date: Optional[str] = Query(None, description="ISO date when revocation takes effect"),
    send_notification: bool = Query(True, description="Send notification to affected admin"),
    current_admin=Depends(deps.get_super_admin_user),
    service: HostelAssignmentService = Depends(get_hostel_assignment_service),
) -> Dict[str, Any]:
    """
    Revoke assignment with comprehensive audit trail and optional delayed execution.
    """
    try:
        # Verify assignment exists
        assignment = await service.get_assignment_by_id(assignment_id)
        if not assignment:
            raise AssignmentNotFoundError(f"Assignment {assignment_id} not found")
        
        result = await service.revoke_assignment(
            assignment_id=assignment_id,
            payload=payload,
            revoked_by=current_admin.id,
            effective_date=effective_date,
            send_notification=send_notification
        )
        
        # Invalidate related caches
        await invalidate_cache(f"assignments:admin:{assignment.admin_id}")
        await invalidate_cache(f"assignments:hostel:{assignment.hostel_id}")
        
        logger.warning(f"Assignment {assignment_id} revoked by {current_admin.id}. Reason: {payload.reason}")
        
        return {
            "detail": "Assignment revoked successfully",
            "assignment_id": assignment_id,
            "effective_date": effective_date or "immediate",
            "reason": payload.reason
        }
        
    except AssignmentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment {assignment_id} not found"
        )
    except Exception as e:
        logger.error(f"Failed to revoke assignment {assignment_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke assignment"
        )


@router.post(
    "/{assignment_id}/primary",
    response_model=AdminHostelAssignment,
    summary="Set primary hostel assignment",
    description="Designate assignment as admin's primary hostel with automatic switching",
)
async def set_primary_hostel(
    assignment_id: str,
    switch_context: bool = Query(True, description="Automatically switch admin's active context"),
    current_admin=Depends(deps.get_super_admin_user),
    service: HostelAssignmentService = Depends(get_hostel_assignment_service),
) -> AdminHostelAssignment:
    """
    Set assignment as primary hostel with automatic context switching.
    """
    try:
        # Verify assignment exists
        assignment = await service.get_assignment_by_id(assignment_id)
        if not assignment:
            raise AssignmentNotFoundError(f"Assignment {assignment_id} not found")
        
        primary_assignment = await service.set_primary_hostel(
            assignment_id=assignment_id,
            updated_by=current_admin.id,
            switch_context=switch_context
        )
        
        # Invalidate related caches
        await invalidate_cache(f"assignments:admin:{assignment.admin_id}")
        await invalidate_cache(f"context:active:{assignment.admin_id}")
        
        logger.info(f"Primary hostel set for assignment {assignment_id} by {current_admin.id}")
        return primary_assignment
        
    except AssignmentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assignment {assignment_id} not found"
        )
    except Exception as e:
        logger.error(f"Failed to set primary hostel for assignment {assignment_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set primary hostel"
        )


@router.get(
    "/stats",
    summary="Get assignment statistics",
    description="Retrieve comprehensive assignment statistics and analytics",
)
@cache_result(expire_time=600)  # Cache for 10 minutes
async def get_assignment_stats(
    period_days: int = Query(30, ge=1, le=365, description="Statistics period in days"),
    breakdown_by: str = Query("role", regex="^(role|hostel|department)$", description="Breakdown dimension"),
    include_trends: bool = Query(True, description="Include trend analysis"),
    current_admin=Depends(deps.get_admin_user),
    service: HostelAssignmentService = Depends(get_hostel_assignment_service),
) -> Dict[str, Any]:
    """Get comprehensive assignment statistics and analytics."""
    try:
        stats = await service.get_assignment_statistics(
            period_days=period_days,
            breakdown_by=breakdown_by,
            include_trends=include_trends,
            requesting_admin_id=current_admin.id
        )
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get assignment statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve assignment statistics"
        )