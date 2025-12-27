"""
Payment ledger and accounting API endpoints.

Handles account statements, balances, adjustments, write-offs, and receivables.
"""

from typing import Any, Optional
from datetime import date

from fastapi import APIRouter, Depends, Path, Query, status, HTTPException

from app.core.dependencies import get_current_user
from app.services.payment.payment_ledger_service import PaymentLedgerService
from app.schemas.payment import (
    AccountStatement,
    LedgerSummary,
    BalanceResponse,
    BalanceAdjustmentRequest,
    WriteOffRequest,
    AdjustmentResponse,
    WriteOffResponse,
)
from app.core.exceptions import (
    LedgerNotFoundError,
    UnauthorizedError,
    InvalidAdjustmentError,
)

router = APIRouter(tags=["Payments - Ledger"])


def get_ledger_service() -> PaymentLedgerService:
    """
    Factory for PaymentLedgerService dependency injection.
    Should be implemented by the DI container.
    """
    raise NotImplementedError(
        "Ledger service must be configured in dependency injection container"
    )


@router.get(
    "/ledger/student/{student_id}/statement",
    response_model=AccountStatement,
    summary="Get student account statement",
    description="Retrieve account statement with all transactions for a student.",
    responses={
        200: {"description": "Account statement retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied"},
        404: {"description": "Student not found"},
    },
)
async def get_student_statement(
    student_id: str = Path(..., description="Student ID"),
    start_date: Optional[str] = Query(
        None,
        description="Start date for statement (ISO format: YYYY-MM-DD)",
        regex=r"^\d{4}-\d{2}-\d{2}$"
    ),
    end_date: Optional[str] = Query(
        None,
        description="End date for statement (ISO format: YYYY-MM-DD)",
        regex=r"^\d{4}-\d{2}-\d{2}$"
    ),
    ledger_service: PaymentLedgerService = Depends(get_ledger_service),
    current_user: Any = Depends(get_current_user),
) -> AccountStatement:
    """
    Get comprehensive account statement for a student.

    Args:
        student_id: ID of the student
        start_date: Optional start date filter
        end_date: Optional end date filter
        ledger_service: Injected ledger service
        current_user: Currently authenticated user

    Returns:
        AccountStatement: Detailed account statement with all transactions

    Raises:
        HTTPException: 403 if unauthorized, 404 if student not found
    """
    result = await ledger_service.get_account_statement_for_student(
        student_id=student_id,
        start_date=start_date,
        end_date=end_date,
        requesting_user_id=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, LedgerNotFoundError):
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


@router.get(
    "/ledger/hostel/{hostel_id}/statement",
    response_model=AccountStatement,
    summary="Get hostel account statement",
    description="Retrieve account statement with all transactions for a hostel.",
    responses={
        200: {"description": "Account statement retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied"},
        404: {"description": "Hostel not found"},
    },
)
async def get_hostel_statement(
    hostel_id: str = Path(..., description="Hostel ID"),
    start_date: Optional[str] = Query(
        None,
        description="Start date for statement (ISO format: YYYY-MM-DD)",
        regex=r"^\d{4}-\d{2}-\d{2}$"
    ),
    end_date: Optional[str] = Query(
        None,
        description="End date for statement (ISO format: YYYY-MM-DD)",
        regex=r"^\d{4}-\d{2}-\d{2}$"
    ),
    ledger_service: PaymentLedgerService = Depends(get_ledger_service),
    current_user: Any = Depends(get_current_user),
) -> AccountStatement:
    """
    Get comprehensive account statement for a hostel.

    Args:
        hostel_id: ID of the hostel
        start_date: Optional start date filter
        end_date: Optional end date filter
        ledger_service: Injected ledger service
        current_user: Currently authenticated user

    Returns:
        AccountStatement: Detailed account statement with all transactions

    Raises:
        HTTPException: 403 if unauthorized, 404 if hostel not found
    """
    result = await ledger_service.get_account_statement_for_hostel(
        hostel_id=hostel_id,
        start_date=start_date,
        end_date=end_date,
        requesting_user_id=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, LedgerNotFoundError):
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


@router.get(
    "/ledger/student/{student_id}/balance",
    response_model=BalanceResponse,
    summary="Get current student balance",
    description="Retrieve the current account balance for a student.",
    responses={
        200: {"description": "Balance retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied"},
        404: {"description": "Student not found"},
    },
)
async def get_student_balance(
    student_id: str = Path(..., description="Student ID"),
    ledger_service: PaymentLedgerService = Depends(get_ledger_service),
    current_user: Any = Depends(get_current_user),
) -> BalanceResponse:
    """
    Get current account balance for a student.

    Args:
        student_id: ID of the student
        ledger_service: Injected ledger service
        current_user: Currently authenticated user

    Returns:
        BalanceResponse: Current balance information

    Raises:
        HTTPException: 403 if unauthorized, 404 if student not found
    """
    result = await ledger_service.get_current_balance(
        entity_id=student_id,
        entity_type="student",
        requesting_user_id=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, LedgerNotFoundError):
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
    "/ledger/adjustment",
    response_model=AdjustmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply balance adjustment",
    description="Apply a manual balance adjustment to an account (admin only).",
    responses={
        201: {"description": "Adjustment applied successfully"},
        400: {"description": "Invalid adjustment data"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Account not found"},
    },
)
async def apply_adjustment(
    payload: BalanceAdjustmentRequest,
    ledger_service: PaymentLedgerService = Depends(get_ledger_service),
    current_user: Any = Depends(get_current_user),
) -> AdjustmentResponse:
    """
    Apply a manual balance adjustment.

    This endpoint allows administrators to adjust account balances
    for corrections, credits, or other manual adjustments.

    Args:
        payload: Adjustment details including amount, reason, and account
        ledger_service: Injected ledger service
        current_user: Currently authenticated user (must be admin)

    Returns:
        AdjustmentResponse: Adjustment confirmation with updated balance

    Raises:
        HTTPException: 403 if unauthorized, 404 if account not found, 400 for invalid data
    """
    result = await ledger_service.apply_balance_adjustment(
        data=payload,
        adjusted_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, LedgerNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        elif isinstance(error, UnauthorizedError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(error)
            )
        elif isinstance(error, InvalidAdjustmentError):
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


@router.post(
    "/ledger/write-off",
    response_model=WriteOffResponse,
    summary="Apply write-off",
    description="Write off an uncollectible amount (admin only with approval).",
    responses={
        201: {"description": "Write-off applied successfully"},
        400: {"description": "Invalid write-off request"},
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient privileges"},
        404: {"description": "Account not found"},
    },
)
async def apply_write_off(
    payload: WriteOffRequest,
    ledger_service: PaymentLedgerService = Depends(get_ledger_service),
    current_user: Any = Depends(get_current_user),
) -> WriteOffResponse:
    """
    Apply a write-off for uncollectible amounts.

    This endpoint allows authorized administrators to write off
    uncollectible debts after proper approval process.

    Args:
        payload: Write-off details including amount, reason, and approvals
        ledger_service: Injected ledger service
        current_user: Currently authenticated user (must have write-off privileges)

    Returns:
        WriteOffResponse: Write-off confirmation

    Raises:
        HTTPException: 403 if unauthorized, 404 if account not found, 400 for invalid data
    """
    result = await ledger_service.apply_write_off(
        data=payload,
        authorized_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, LedgerNotFoundError):
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


@router.get(
    "/ledger/receivables",
    response_model=LedgerSummary,
    summary="Get accounts receivable summary",
    description="Get aggregated summary of all receivables (admin only).",
    responses={
        200: {"description": "Receivables summary retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
    },
)
async def get_receivables(
    hostel_id: Optional[str] = Query(None, description="Filter by hostel ID"),
    aging_bucket: Optional[str] = Query(
        None,
        description="Filter by aging bucket (current, 30days, 60days, 90days, over90days)",
        regex="^(current|30days|60days|90days|over90days)$"
    ),
    ledger_service: PaymentLedgerService = Depends(get_ledger_service),
    current_user: Any = Depends(get_current_user),
) -> LedgerSummary:
    """
    Get accounts receivable summary.

    Provides aggregated view of all outstanding receivables,
    optionally filtered by hostel and aging buckets.

    Args:
        hostel_id: Optional filter by hostel
        aging_bucket: Optional filter by aging period
        ledger_service: Injected ledger service
        current_user: Currently authenticated user (must be admin)

    Returns:
        LedgerSummary: Aggregated receivables summary

    Raises:
        HTTPException: 403 if not admin
    """
    result = await ledger_service.get_receivables_summary(
        hostel_id=hostel_id,
        aging_bucket=aging_bucket,
        requesting_user_id=current_user.id,
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


@router.get(
    "/ledger/hostel/{hostel_id}/balance",
    response_model=BalanceResponse,
    summary="Get hostel balance",
    description="Retrieve current balance for a hostel.",
    responses={
        200: {"description": "Balance retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied"},
        404: {"description": "Hostel not found"},
    },
)
async def get_hostel_balance(
    hostel_id: str = Path(..., description="Hostel ID"),
    ledger_service: PaymentLedgerService = Depends(get_ledger_service),
    current_user: Any = Depends(get_current_user),
) -> BalanceResponse:
    """
    Get current balance for a hostel.

    Args:
        hostel_id: ID of the hostel
        ledger_service: Injected ledger service
        current_user: Currently authenticated user

    Returns:
        BalanceResponse: Current balance information

    Raises:
        HTTPException: 403 if unauthorized, 404 if hostel not found
    """
    result = await ledger_service.get_current_balance(
        entity_id=hostel_id,
        entity_type="hostel",
        requesting_user_id=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, LedgerNotFoundError):
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