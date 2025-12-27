"""
Referral Program Management API Endpoints

This module provides endpoints for creating, managing, and monitoring referral programs.
Includes program lifecycle management, statistics, and analytics.
"""

from typing import Any

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import Response

from app.core.dependencies import AuthenticationDependency, RequireRole
from app.services.referral.referral_program_service import ReferralProgramService
from app.schemas.referral import (
    ReferralProgramResponse,
    ReferralProgramCreate,
    ReferralProgramUpdate,
    ReferralProgramStats,
    ReferralProgramAnalytics,
    ReferralProgramListResponse,
)

router = APIRouter(
    prefix="/referrals/programs",
    tags=["Referrals - Programs"],
)


# ============================================================================
# Dependency Injection
# ============================================================================


def get_program_service() -> ReferralProgramService:
    """
    Dependency injection for ReferralProgramService.
    
    TODO: Wire this to your DI container
    Example:
        from app.core.container import Container
        return Container.referral_program_service()
    """
    raise NotImplementedError(
        "ReferralProgramService dependency must be configured in DI container"
    )


def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """
    Extract and validate current authenticated user from request.
    
    Args:
        auth: Authentication dependency that handles token validation
        
    Returns:
        Current authenticated user object
        
    Raises:
        HTTPException: If authentication fails
    """
    return auth.get_current_user()


def require_admin(auth: AuthenticationDependency = Depends()) -> Any:
    """
    Verify that the current user has admin privileges.
    
    TODO: Implement role-based access control
    Example:
        user = auth.get_current_user()
        if not user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")
        return user
    """
    return auth.get_current_user()


# ============================================================================
# Program CRUD Operations (Admin)
# ============================================================================


@router.post(
    "",
    response_model=ReferralProgramResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create referral program",
    description="""
    Create a new referral program with specified rewards and conditions.
    
    **Admin only endpoint**
    """,
    responses={
        201: {
            "description": "Referral program successfully created",
            "model": ReferralProgramResponse,
        },
        400: {"description": "Invalid program configuration"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        409: {"description": "Program with this name already exists"},
    },
)
async def create_program(
    payload: ReferralProgramCreate,
    program_service: ReferralProgramService = Depends(get_program_service),
    current_user: Any = Depends(require_admin),
) -> ReferralProgramResponse:
    """
    Create a new referral program (Admin only).
    
    Args:
        payload: Program configuration including rewards, conditions, and validity
        program_service: Injected referral program service
        current_user: Authenticated admin user
        
    Returns:
        Newly created referral program details
        
    Raises:
        HTTPException: If creation fails due to validation or business rules
    """
    result = program_service.create_program(data=payload, created_by=current_user.id)
    return result.unwrap()


@router.get(
    "",
    response_model=ReferralProgramListResponse,
    summary="List referral programs",
    description="""
    Retrieve a paginated list of referral programs.
    
    Supports filtering by status, program type, and date range.
    """,
    responses={
        200: {
            "description": "List of referral programs with pagination",
            "model": ReferralProgramListResponse,
        },
        401: {"description": "Authentication required"},
    },
)
async def list_programs(
    active_only: bool = Query(
        True,
        description="Filter for active programs only",
    ),
    program_type: str | None = Query(
        None,
        description="Filter by program type",
        regex="^(standard|tiered|milestone)$",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query(
        "created_at",
        description="Sort field",
        regex="^(created_at|name|total_referrals)$",
    ),
    sort_order: str = Query(
        "desc",
        description="Sort order",
        regex="^(asc|desc)$",
    ),
    program_service: ReferralProgramService = Depends(get_program_service),
    current_user: Any = Depends(get_current_user),
) -> ReferralProgramListResponse:
    """
    List all referral programs with optional filtering.
    
    Args:
        active_only: If True, only return active programs
        program_type: Optional filter by program type
        page: Page number for pagination
        page_size: Number of items per page
        sort_by: Field to sort by
        sort_order: Sorting direction
        program_service: Injected referral program service
        current_user: Authenticated user making the request
        
    Returns:
        Paginated list of referral programs
    """
    filters = {
        "active": active_only,
        "program_type": program_type,
    }
    
    result = program_service.list_programs(
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return result.unwrap()


@router.get(
    "/{program_id}",
    response_model=ReferralProgramResponse,
    summary="Get referral program",
    description="""
    Retrieve detailed information about a specific referral program.
    """,
    responses={
        200: {
            "description": "Referral program details",
            "model": ReferralProgramResponse,
        },
        401: {"description": "Authentication required"},
        404: {"description": "Program not found"},
    },
)
async def get_program(
    program_id: str = Path(
        ...,
        description="Unique identifier of the referral program",
        min_length=1,
    ),
    program_service: ReferralProgramService = Depends(get_program_service),
    current_user: Any = Depends(get_current_user),
) -> ReferralProgramResponse:
    """
    Get details of a specific referral program.
    
    Args:
        program_id: Unique identifier of the program
        program_service: Injected referral program service
        current_user: Authenticated user making the request
        
    Returns:
        Detailed program information
        
    Raises:
        HTTPException: If program not found
    """
    result = program_service.get_program(program_id=program_id)
    return result.unwrap()


@router.patch(
    "/{program_id}",
    response_model=ReferralProgramResponse,
    summary="Update referral program",
    description="""
    Update an existing referral program's configuration.
    
    **Admin only endpoint**
    """,
    responses={
        200: {
            "description": "Program successfully updated",
            "model": ReferralProgramResponse,
        },
        400: {"description": "Invalid update data"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Program not found"},
    },
)
async def update_program(
    program_id: str = Path(
        ...,
        description="Unique identifier of the referral program",
        min_length=1,
    ),
    payload: ReferralProgramUpdate = ...,
    program_service: ReferralProgramService = Depends(get_program_service),
    current_user: Any = Depends(require_admin),
) -> ReferralProgramResponse:
    """
    Update a referral program's configuration (Admin only).
    
    Args:
        program_id: Unique identifier of the program
        payload: Updated program configuration
        program_service: Injected referral program service
        current_user: Authenticated admin user
        
    Returns:
        Updated program details
        
    Raises:
        HTTPException: If update fails
    """
    result = program_service.update_program(
        program_id=program_id,
        data=payload,
        updated_by=current_user.id,
    )
    return result.unwrap()


@router.delete(
    "/{program_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete program",
    description="""
    Permanently delete a referral program.
    
    **Admin only endpoint**
    
    This will also deactivate all associated codes.
    """,
    responses={
        204: {"description": "Program successfully deleted"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Program not found"},
        409: {"description": "Cannot delete program with active referrals"},
    },
)
async def delete_program(
    program_id: str = Path(
        ...,
        description="Unique identifier of the referral program",
        min_length=1,
    ),
    program_service: ReferralProgramService = Depends(get_program_service),
    current_user: Any = Depends(require_admin),
) -> Response:
    """
    Permanently delete a referral program (Admin only).
    
    Args:
        program_id: Unique identifier of the program
        program_service: Injected referral program service
        current_user: Authenticated admin user
        
    Returns:
        Empty response with 204 status
        
    Raises:
        HTTPException: If deletion fails or program has active referrals
    """
    program_service.delete_program(
        program_id=program_id,
        deleted_by=current_user.id,
    ).unwrap()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# Program Lifecycle Management (Admin)
# ============================================================================


@router.post(
    "/{program_id}/activate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Activate program",
    description="""
    Activate a referral program, allowing code generation and usage.
    
    **Admin only endpoint**
    """,
    responses={
        204: {"description": "Program successfully activated"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Program not found"},
        409: {"description": "Program already active"},
    },
)
async def activate_program(
    program_id: str = Path(
        ...,
        description="Unique identifier of the referral program",
        min_length=1,
    ),
    program_service: ReferralProgramService = Depends(get_program_service),
    current_user: Any = Depends(require_admin),
) -> Response:
    """
    Activate a referral program (Admin only).
    
    Args:
        program_id: Unique identifier of the program
        program_service: Injected referral program service
        current_user: Authenticated admin user
        
    Returns:
        Empty response with 204 status
        
    Raises:
        HTTPException: If activation fails
    """
    program_service.activate_program(
        program_id=program_id,
        activated_by=current_user.id,
    ).unwrap()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{program_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate program",
    description="""
    Deactivate a referral program, preventing new code generation.
    
    **Admin only endpoint**
    
    Existing codes will still work until their expiration.
    """,
    responses={
        204: {"description": "Program successfully deactivated"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Program not found"},
        409: {"description": "Program already inactive"},
    },
)
async def deactivate_program(
    program_id: str = Path(
        ...,
        description="Unique identifier of the referral program",
        min_length=1,
    ),
    program_service: ReferralProgramService = Depends(get_program_service),
    current_user: Any = Depends(require_admin),
) -> Response:
    """
    Deactivate a referral program (Admin only).
    
    Args:
        program_id: Unique identifier of the program
        program_service: Injected referral program service
        current_user: Authenticated admin user
        
    Returns:
        Empty response with 204 status
        
    Raises:
        HTTPException: If deactivation fails
    """
    program_service.deactivate_program(
        program_id=program_id,
        deactivated_by=current_user.id,
    ).unwrap()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# Program Analytics & Statistics
# ============================================================================


@router.get(
    "/{program_id}/stats",
    response_model=ReferralProgramStats,
    summary="Get program statistics",
    description="""
    Retrieve aggregated statistics for a referral program.
    
    Includes metrics like total referrals, conversions, rewards distributed, etc.
    """,
    responses={
        200: {
            "description": "Program statistics",
            "model": ReferralProgramStats,
        },
        401: {"description": "Authentication required"},
        404: {"description": "Program not found"},
    },
)
async def get_program_stats(
    program_id: str = Path(
        ...,
        description="Unique identifier of the referral program",
        min_length=1,
    ),
    date_from: str | None = Query(
        None,
        description="Start date for stats (ISO format)",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    date_to: str | None = Query(
        None,
        description="End date for stats (ISO format)",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    program_service: ReferralProgramService = Depends(get_program_service),
    current_user: Any = Depends(get_current_user),
) -> ReferralProgramStats:
    """
    Get aggregated statistics for a referral program.
    
    Args:
        program_id: Unique identifier of the program
        date_from: Optional start date for filtering
        date_to: Optional end date for filtering
        program_service: Injected referral program service
        current_user: Authenticated user making the request
        
    Returns:
        Program statistics with various metrics
        
    Raises:
        HTTPException: If program not found
    """
    result = program_service.get_program_stats(
        program_id=program_id,
        date_from=date_from,
        date_to=date_to,
    )
    return result.unwrap()


@router.get(
    "/{program_id}/analytics",
    response_model=ReferralProgramAnalytics,
    summary="Get detailed analytics",
    description="""
    Retrieve detailed analytics for a referral program.
    
    Includes time-series data, conversion funnels, top performers, etc.
    """,
    responses={
        200: {
            "description": "Detailed program analytics",
            "model": ReferralProgramAnalytics,
        },
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Program not found"},
    },
)
async def get_program_analytics(
    program_id: str = Path(
        ...,
        description="Unique identifier of the referral program",
        min_length=1,
    ),
    date_from: str | None = Query(
        None,
        description="Start date for analytics (ISO format)",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    date_to: str | None = Query(
        None,
        description="End date for analytics (ISO format)",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    granularity: str = Query(
        "day",
        description="Time granularity for time-series data",
        regex="^(hour|day|week|month)$",
    ),
    program_service: ReferralProgramService = Depends(get_program_service),
    current_user: Any = Depends(require_admin),
) -> ReferralProgramAnalytics:
    """
    Get detailed analytics for a referral program (Admin only).
    
    Args:
        program_id: Unique identifier of the program
        date_from: Optional start date for filtering
        date_to: Optional end date for filtering
        granularity: Time granularity for time-series data
        program_service: Injected referral program service
        current_user: Authenticated admin user
        
    Returns:
        Detailed analytics including trends, funnels, and top performers
        
    Raises:
        HTTPException: If program not found
    """
    result = program_service.get_program_analytics(
        program_id=program_id,
        date_from=date_from,
        date_to=date_to,
        granularity=granularity,
    )
    return result.unwrap()


@router.get(
    "/{program_id}/top-referrers",
    summary="Get top referrers for program",
    description="""
    Retrieve the top performing referrers for a specific program.
    
    **Admin only endpoint**
    """,
    responses={
        200: {"description": "List of top referrers with metrics"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Program not found"},
    },
)
async def get_top_referrers(
    program_id: str = Path(
        ...,
        description="Unique identifier of the referral program",
        min_length=1,
    ),
    limit: int = Query(10, ge=1, le=100, description="Number of top referrers"),
    metric: str = Query(
        "conversions",
        description="Metric to rank by",
        regex="^(conversions|referrals|revenue)$",
    ),
    program_service: ReferralProgramService = Depends(get_program_service),
    current_user: Any = Depends(require_admin),
) -> dict[str, Any]:
    """
    Get top performing referrers for a program (Admin only).
    
    Args:
        program_id: Unique identifier of the program
        limit: Number of top referrers to return
        metric: Metric to rank by
        program_service: Injected referral program service
        current_user: Authenticated admin user
        
    Returns:
        List of top referrers with their metrics
        
    Raises:
        HTTPException: If program not found
    """
    result = program_service.get_top_referrers(
        program_id=program_id,
        limit=limit,
        metric=metric,
    )
    return result.unwrap()