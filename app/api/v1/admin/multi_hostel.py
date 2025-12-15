"""
Multi-Hostel Dashboard API

Provides consolidated dashboard views for administrators managing
multiple hostels, aggregating metrics and analytics across properties.
"""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_active_user, get_uow
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ServiceError,
    ValidationError,
)
from app.models.core import User
from app.schemas.admin.multi_hostel_dashboard import MultiHostelDashboard
from app.services.admin import MultiHostelDashboardService
from app.services.common.unit_of_work import UnitOfWork

router = APIRouter(prefix="/multi-hostel")


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


# ==================== Helper Functions ====================


def _resolve_admin_id(
    admin_id: Optional[UUID],
    current_user: User,
) -> UUID:
    """
    Resolve admin ID from explicit parameter or current user.

    Args:
        admin_id: Explicitly provided admin ID (optional)
        current_user: Currently authenticated user

    Returns:
        Resolved admin ID

    Raises:
        HTTPException: If admin_id not provided and user is not an admin
    """
    if admin_id is not None:
        return admin_id

    # Attempt to derive from current user's admin profile
    admin_profile = getattr(current_user, "admin_profile", None)
    if admin_profile is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Current user does not have an admin profile. "
            "Please provide an explicit admin_id.",
        )

    return admin_profile.id


# ==================== Endpoints ====================


@router.get(
    "/dashboard",
    response_model=MultiHostelDashboard,
    status_code=status.HTTP_200_OK,
    summary="Get Multi-Hostel Dashboard",
    description="Retrieve consolidated dashboard data for an admin managing multiple hostels.",
    responses={
        200: {"description": "Successfully retrieved dashboard data"},
        403: {"description": "User is not an admin or lacks permissions"},
        404: {"description": "Admin not found or has no hostel assignments"},
    },
)
async def get_multi_hostel_dashboard(
    admin_id: Annotated[
        Optional[UUID],
        Query(
            description="Admin ID (optional; defaults to current user's admin profile)",
        ),
    ] = None,
    current_user: Annotated[User, Depends(get_current_active_user)] = ...,
    uow: Annotated[UnitOfWork, Depends(get_uow)] = ...,
) -> MultiHostelDashboard:
    """
    Build consolidated multi-hostel dashboard.

    Aggregates data across all hostels assigned to the admin:
    - Per-hostel key metrics (occupancy, revenue, issues)
    - Cross-hostel comparisons
    - Trend analysis
    - Alert notifications
    - Priority items requiring attention

    Admin ID resolution:
    - If `admin_id` is provided, uses that value
    - Otherwise, derives from current authenticated user's admin profile
    - Fails if user is not an admin and no admin_id provided

    Dashboard includes:
    - Summary cards for each hostel
    - Comparative analytics
    - Recent activity feed
    - Pending tasks and alerts
    - Performance indicators
    """
    # Resolve admin_id from parameter or current user
    resolved_admin_id = _resolve_admin_id(admin_id, current_user)

    service = MultiHostelDashboardService(uow)
    try:
        return await service.get_dashboard(admin_id=resolved_admin_id)
    except ServiceError as exc:
        raise _map_service_error(exc) from exc