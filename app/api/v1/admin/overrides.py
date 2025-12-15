"""
Admin Override Management API

Handles administrator overrides of supervisor/system decisions with
comprehensive audit logging and statistical tracking.
"""

from datetime import date
from typing import Annotated, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.deps import get_uow
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ServiceError,
    ValidationError,
)
from app.schemas.admin.admin_override import (
    AdminOverrideRequest,
    OverrideLog,
    OverrideSummary,
    SupervisorOverrideStats,
)
from app.services.admin import AdminOverrideService
from app.services.common.unit_of_work import UnitOfWork

router = APIRouter(prefix="/overrides")


# ==================== Error Mapping ====================


def _map_service_error(exc: ServiceError) -> HTTPException:
    """
    Map service-layer exceptions to appropriate HTTP exceptions.

    Args:
        exc: Service exception to map

    Returns:
        Corresponding HTTPException with appropriate status code
    """
    error_map = {
        NotFoundError: (status.HTTP_404_NOT_FOUND, str(exc)),
        ValidationError: (status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)),
        ConflictError: (status.HTTP_409_CONFLICT, str(exc)),
    }

    for error_type, (status_code, detail) in error_map.items():
        if isinstance(exc, error_type):
            return HTTPException(status_code=status_code, detail=detail)

    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


# ==================== Endpoints ====================


@router.post(
    "/",
    response_model=OverrideLog,
    status_code=status.HTTP_201_CREATED,
    summary="Create Admin Override",
    description="Record an administrative override of a supervisor or system decision.",
    responses={
        201: {"description": "Override successfully recorded"},
        400: {"description": "Invalid override data"},
        403: {"description": "Insufficient privileges to override"},
        404: {"description": "Target entity not found"},
        409: {"description": "Override conflicts with existing decision"},
        422: {"description": "Validation error in override request"},
    },
)
async def create_admin_override(
    payload: AdminOverrideRequest,
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> OverrideLog:
    """
    Record an admin override of a previous decision.

    Use cases:
    - Overriding supervisor complaint resolutions
    - Bypassing automated rejection rules
    - Emergency leave approvals
    - Maintenance priority escalation

    Actions performed:
    - Validates admin authority
    - Records original decision
    - Logs override justification
    - Updates entity status
    - Creates audit trail
    - Notifies affected parties

    All overrides are immutable and fully audited.
    """
    service = AdminOverrideService(uow)
    try:
        return await service.create_override(request=payload)
    except ServiceError as exc:
        raise _map_service_error(exc) from exc


@router.get(
    "/entity/{entity_type}/{entity_id}",
    response_model=list[OverrideLog],
    status_code=status.HTTP_200_OK,
    summary="List Overrides for Entity",
    description="Retrieve all administrative overrides applied to a specific entity.",
    responses={
        200: {"description": "Successfully retrieved override history"},
        404: {"description": "Entity not found"},
    },
)
async def list_overrides_for_entity(
    entity_type: Annotated[
        str,
        Path(
            description="Entity type (e.g., complaint, maintenance_request, leave_application)",
            example="complaint",
        ),
    ],
    entity_id: Annotated[
        UUID,
        Path(description="Unique identifier of the entity"),
    ],
    uow: Annotated[UnitOfWork, Depends(get_uow)],
) -> list[OverrideLog]:
    """
    Fetch complete override history for an entity.

    Returns chronological list of all overrides including:
    - Override timestamp
    - Admin who performed override
    - Original decision details
    - Override justification
    - Resulting status change

    Useful for:
    - Decision audit trails
    - Compliance reviews
    - Dispute resolution
    - Pattern analysis
    """
    service = AdminOverrideService(uow)
    try:
        return await service.list_overrides_for_entity(
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except ServiceError as exc:
        raise _map_service_error(exc) from exc


@router.get(
    "/summary",
    response_model=OverrideSummary,
    status_code=status.HTTP_200_OK,
    summary="Get Override Summary",
    description="Retrieve aggregated override statistics for a period with optional filters.",
    responses={
        200: {"description": "Successfully retrieved override summary"},
        400: {"description": "Invalid filter or date parameters"},
        422: {"description": "Validation error in query parameters"},
    },
)
async def get_override_summary(
    hostel_id: Annotated[
        Union[UUID, None],
        Query(description="Filter by specific hostel"),
    ] = None,
    supervisor_id: Annotated[
        Union[UUID, None],
        Query(description="Filter by supervisor whose decisions were overridden"),
    ] = None,
    start_date: Annotated[
        Union[date, None],
        Query(description="Start date for summary period (inclusive)"),
    ] = None,
    end_date: Annotated[
        Union[date, None],
        Query(description="End date for summary period (inclusive)"),
    ] = None,
    uow: Annotated[UnitOfWork, Depends(get_uow)] = ...,
) -> OverrideSummary:
    """
    Generate override statistics summary.

    Provides aggregated metrics:
    - Total override count
    - Overrides by entity type
    - Overrides by reason
    - Trend analysis
    - Hostel/supervisor breakdown

    Supports filtering by:
    - Date range
    - Specific hostel
    - Specific supervisor
    """
    # Validate date range if both provided
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date must be before or equal to end_date",
        )

    service = AdminOverrideService(uow)
    try:
        return await service.get_override_summary(
            hostel_id=hostel_id,
            supervisor_id=supervisor_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ServiceError as exc:
        raise _map_service_error(exc) from exc


@router.get(
    "/supervisors/{supervisor_id}/stats",
    response_model=SupervisorOverrideStats,
    status_code=status.HTTP_200_OK,
    summary="Get Supervisor Override Statistics",
    description="Retrieve detailed override statistics for a specific supervisor.",
    responses={
        200: {"description": "Successfully retrieved supervisor stats"},
        404: {"description": "Supervisor not found"},
    },
)
async def get_supervisor_override_stats(
    supervisor_id: Annotated[
        UUID,
        Path(description="Unique identifier of the supervisor"),
    ],
    start_date: Annotated[
        Union[date, None],
        Query(description="Start date for statistics period (inclusive)"),
    ] = None,
    end_date: Annotated[
        Union[date, None],
        Query(description="End date for statistics period (inclusive)"),
    ] = None,
    uow: Annotated[UnitOfWork, Depends(get_uow)] = ...,
) -> SupervisorOverrideStats:
    """
    Get detailed override statistics for a supervisor.

    Analyzes:
    - Total decisions made
    - Number of decisions overridden
    - Override rate percentage
    - Override reasons breakdown
    - Time-based trends
    - Entity type distribution

    Useful for:
    - Performance reviews
    - Training needs assessment
    - Quality assurance
    - Process improvement
    """
    # Validate date range if both provided
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date must be before or equal to end_date",
        )

    service = AdminOverrideService(uow)
    try:
        return await service.get_supervisor_override_stats(
            supervisor_id=supervisor_id,
            start_date=start_date,
            end_date=end_date,
        )
    except ServiceError as exc:
        raise _map_service_error(exc) from exc