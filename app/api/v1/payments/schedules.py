"""
Payment schedule management API endpoints.

Handles recurring payment schedules, installments, and automated payment generation.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Path, Query, status, HTTPException

from app.core.dependencies import get_current_user
from app.services.payment.payment_schedule_service import PaymentScheduleService
from app.schemas.payment import (
    PaymentSchedule,
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleListItem,
    BulkScheduleCreate,
    ScheduleGenerationResponse,
)
from app.core.exceptions import (
    ScheduleNotFoundError,
    UnauthorizedError,
    InvalidScheduleError,
)

router = APIRouter(tags=["Payments - Schedules"])


def get_schedule_service() -> PaymentScheduleService:
    """
    Factory for PaymentScheduleService dependency injection.
    Should be implemented by the DI container.
    """
    raise NotImplementedError(
        "Schedule service must be configured in dependency injection container"
    )


@router.post(
    "/schedules",
    response_model=PaymentSchedule,
    status_code=status.HTTP_201_CREATED,
    summary="Create payment schedule",
    description="Create a new payment schedule for recurring or installment payments.",
    responses={
        201: {"description": "Schedule created successfully"},
        400: {"description": "Invalid schedule data"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
    },
)
async def create_schedule(
    payload: ScheduleCreate,
    schedule_service: PaymentScheduleService = Depends(get_schedule_service),
    current_user: Any = Depends(get_current_user),
) -> PaymentSchedule:
    """
    Create a new payment schedule.

    Args:
        payload: Schedule details including frequency, amount, student, etc.
        schedule_service: Injected schedule service
        current_user: Currently authenticated user

    Returns:
        PaymentSchedule: Created schedule details

    Raises:
        HTTPException: 400 for invalid data, 403 if unauthorized
    """
    result = await schedule_service.create_schedule(
        data=payload,
        created_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, UnauthorizedError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(error)
            )
        elif isinstance(error, InvalidScheduleError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()


@router.get(
    "/schedules",
    response_model=List[ScheduleListItem],
    summary="List payment schedules",
    description="Retrieve list of payment schedules with optional filters.",
    responses={
        200: {"description": "Schedules retrieved successfully"},
        401: {"description": "Authentication required"},
    },
)
async def list_schedules(
    student_id: Optional[str] = Query(None, description="Filter by student ID"),
    hostel_id: Optional[str] = Query(None, description="Filter by hostel ID"),
    status_filter: Optional[str] = Query(
        None,
        description="Filter by schedule status",
        regex="^(active|suspended|completed|cancelled)$"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    schedule_service: PaymentScheduleService = Depends(get_schedule_service),
    current_user: Any = Depends(get_current_user),
) -> List[ScheduleListItem]:
    """
    List payment schedules with filters.

    Args:
        student_id: Optional filter by student
        hostel_id: Optional filter by hostel
        status_filter: Optional filter by status
        page: Page number
        page_size: Items per page
        schedule_service: Injected schedule service
        current_user: Currently authenticated user

    Returns:
        List[ScheduleListItem]: List of schedules

    Raises:
        HTTPException: 400 for invalid filters
    """
    filters = {
        "student_id": student_id,
        "hostel_id": hostel_id,
        "status": status_filter,
        "page": page,
        "page_size": page_size,
    }
    
    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}
    
    result = await schedule_service.list_schedules(
        filters=filters,
        requesting_user_id=current_user.id,
    )
    
    if result.is_err():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(result.unwrap_err())
        )
    
    return result.unwrap()


@router.get(
    "/schedules/{schedule_id}",
    response_model=PaymentSchedule,
    summary="Get schedule details",
    description="Retrieve detailed information about a payment schedule.",
    responses={
        200: {"description": "Schedule retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Schedule not found"},
    },
)
async def get_schedule(
    schedule_id: str = Path(..., description="Schedule ID"),
    schedule_service: PaymentScheduleService = Depends(get_schedule_service),
    current_user: Any = Depends(get_current_user),
) -> PaymentSchedule:
    """
    Get detailed information about a schedule.

    Args:
        schedule_id: ID of the schedule
        schedule_service: Injected schedule service
        current_user: Currently authenticated user

    Returns:
        PaymentSchedule: Schedule details

    Raises:
        HTTPException: 404 if not found
    """
    result = await schedule_service.get_schedule(
        schedule_id=schedule_id,
        requesting_user_id=current_user.id,
    )
    
    if result.is_err():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )
    
    return result.unwrap()


@router.patch(
    "/schedules/{schedule_id}",
    response_model=PaymentSchedule,
    summary="Update payment schedule",
    description="Update details of an existing payment schedule.",
    responses={
        200: {"description": "Schedule updated successfully"},
        400: {"description": "Invalid update data"},
        401: {"description": "Authentication required"},
        403: {"description": "Unauthorized to modify schedule"},
        404: {"description": "Schedule not found"},
    },
)
async def update_schedule(
    schedule_id: str = Path(..., description="Schedule ID"),
    payload: ScheduleUpdate = ...,
    schedule_service: PaymentScheduleService = Depends(get_schedule_service),
    current_user: Any = Depends(get_current_user),
) -> PaymentSchedule:
    """
    Update a payment schedule.

    Args:
        schedule_id: ID of the schedule to update
        payload: Update data
        schedule_service: Injected schedule service
        current_user: Currently authenticated user

    Returns:
        PaymentSchedule: Updated schedule

    Raises:
        HTTPException: 403 if unauthorized, 404 if not found, 400 for invalid data
    """
    result = await schedule_service.update_schedule(
        schedule_id=schedule_id,
        data=payload,
        updated_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, ScheduleNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        elif isinstance(error, UnauthorizedError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()


@router.post(
    "/schedules/{schedule_id}/suspend",
    summary="Suspend schedule",
    description="Temporarily suspend a payment schedule.",
    responses={
        200: {"description": "Schedule suspended successfully"},
        400: {"description": "Schedule cannot be suspended"},
        401: {"description": "Authentication required"},
        403: {"description": "Unauthorized"},
        404: {"description": "Schedule not found"},
    },
)
async def suspend_schedule(
    schedule_id: str = Path(..., description="Schedule ID"),
    reason: str = Query(..., description="Suspension reason", min_length=3),
    schedule_service: PaymentScheduleService = Depends(get_schedule_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Suspend a payment schedule.

    Args:
        schedule_id: ID of the schedule
        reason: Reason for suspension
        schedule_service: Injected schedule service
        current_user: Currently authenticated user

    Returns:
        dict: Suspension confirmation

    Raises:
        HTTPException: Various errors based on schedule state
    """
    result = await schedule_service.suspend_schedule(
        schedule_id=schedule_id,
        reason=reason,
        suspended_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, ScheduleNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        elif isinstance(error, UnauthorizedError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()


@router.post(
    "/schedules/{schedule_id}/resume",
    summary="Resume schedule",
    description="Resume a suspended payment schedule.",
    responses={
        200: {"description": "Schedule resumed successfully"},
        400: {"description": "Schedule cannot be resumed"},
        401: {"description": "Authentication required"},
        404: {"description": "Schedule not found"},
    },
)
async def resume_schedule(
    schedule_id: str = Path(..., description="Schedule ID"),
    schedule_service: PaymentScheduleService = Depends(get_schedule_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Resume a suspended schedule.

    Args:
        schedule_id: ID of the schedule
        schedule_service: Injected schedule service
        current_user: Currently authenticated user

    Returns:
        dict: Resume confirmation

    Raises:
        HTTPException: Various errors based on schedule state
    """
    result = await schedule_service.resume_schedule(
        schedule_id=schedule_id,
        resumed_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, ScheduleNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()


@router.delete(
    "/schedules/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate schedule",
    description="Permanently deactivate a payment schedule.",
    responses={
        204: {"description": "Schedule deactivated successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Unauthorized"},
        404: {"description": "Schedule not found"},
    },
)
async def deactivate_schedule(
    schedule_id: str = Path(..., description="Schedule ID"),
    schedule_service: PaymentScheduleService = Depends(get_schedule_service),
    current_user: Any = Depends(get_current_user),
) -> None:
    """
    Permanently deactivate a schedule.

    Args:
        schedule_id: ID of the schedule
        schedule_service: Injected schedule service
        current_user: Currently authenticated user

    Raises:
        HTTPException: 403 if unauthorized, 404 if not found
    """
    result = await schedule_service.deactivate_schedule(
        schedule_id=schedule_id,
        deactivated_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, ScheduleNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        elif isinstance(error, UnauthorizedError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )


@router.post(
    "/schedules/{schedule_id}/generate",
    response_model=ScheduleGenerationResponse,
    summary="Generate payments from schedule",
    description="Manually trigger payment generation for a schedule.",
    responses={
        200: {"description": "Payments generated successfully"},
        400: {"description": "Payment generation failed"},
        401: {"description": "Authentication required"},
        404: {"description": "Schedule not found"},
    },
)
async def generate_payments(
    schedule_id: str = Path(..., description="Schedule ID"),
    schedule_service: PaymentScheduleService = Depends(get_schedule_service),
    current_user: Any = Depends(get_current_user),
) -> ScheduleGenerationResponse:
    """
    Manually trigger payment generation for a schedule.

    This endpoint generates due payments based on the schedule's
    configuration and current date.

    Args:
        schedule_id: ID of the schedule
        schedule_service: Injected schedule service
        current_user: Currently authenticated user

    Returns:
        ScheduleGenerationResponse: Summary of generated payments

    Raises:
        HTTPException: 404 if schedule not found, 400 for generation errors
    """
    result = await schedule_service.generate_payments(
        schedule_id=schedule_id,
        triggered_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, ScheduleNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()


@router.post(
    "/schedules/bulk-create",
    response_model=dict,
    summary="Bulk create schedules",
    description="Create multiple payment schedules at once.",
    responses={
        201: {"description": "Schedules created successfully"},
        400: {"description": "Invalid schedule data"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
    },
)
async def bulk_create_schedules(
    payload: BulkScheduleCreate,
    schedule_service: PaymentScheduleService = Depends(get_schedule_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Create multiple schedules in bulk.

    Useful for setting up payment schedules for multiple students
    at the start of a semester or term.

    Args:
        payload: List of schedule creation requests
        schedule_service: Injected schedule service
        current_user: Currently authenticated user (must be admin)

    Returns:
        dict: Summary of successful and failed creations

    Raises:
        HTTPException: 403 if unauthorized, 400 for validation errors
    """
    result = await schedule_service.bulk_create_schedules(
        data_list=payload.schedules,
        created_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, UnauthorizedError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()