"""
Leave Balance API Endpoints.

Manages leave balance tracking including:
- Balance summary and availability
- Manual adjustments (admin)
- Usage history and audit
- Balance forecasting

Ensures accurate tracking of leave entitlements and consumption.
"""
from typing import Any, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.api import deps
from app.api.v1.leaves.constants import LeaveType
from app.api.v1.leaves.dependencies import (
    PaginationParams,
    get_leave_balance_service,
    get_pagination_params,
    get_target_student_id,
    verify_student_or_admin,
)
from app.schemas.leave.leave_balance import (
    LeaveAdjustment,
    LeaveBalanceDetail,
    LeaveBalanceSummary,
    LeaveUsageDetail,
    LeaveUsageHistory,
)
from app.services.leave.leave_balance_service import LeaveBalanceService

# ============================================================================
# Router Configuration
# ============================================================================

router = APIRouter(prefix="/leaves/balance", tags=["leaves:balance"])


# ============================================================================
# Balance Query Endpoints
# ============================================================================

@router.get(
    "/summary",
    response_model=LeaveBalanceSummary,
    summary="Get comprehensive leave balance summary",
    description="""
    Retrieve complete leave balance information for a student.
    
    **Permission**:
    - Students: Can view only their own balance
    - Admins: Can view any student's balance
    
    **Returns**:
    - Available balance for each leave type
    - Total allocated days
    - Used days and pending applications
    - Remaining balance with expiry dates
    """,
    responses={
        200: {"description": "Balance summary retrieved successfully"},
        403: {"description": "Permission denied"},
        404: {"description": "Student not found"},
    },
)
async def get_leave_balance_summary(
    student_id: str = Depends(get_target_student_id),
    academic_year: Optional[str] = Query(None, description="Specific academic year"),
    current_user=Depends(deps.get_current_user),
    service: LeaveBalanceService = Depends(get_leave_balance_service),
) -> LeaveBalanceSummary:
    """
    Get comprehensive balance summary for a student.
    
    Includes breakdown by leave type, usage statistics, and availability.
    """
    try:
        summary = service.get_balance_summary(
            student_id=student_id,
            academic_year=academic_year,
        )
        
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No balance information found for student '{student_id}'",
            )
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve balance summary: {str(e)}",
        )


@router.get(
    "/detail/{leave_type}",
    response_model=LeaveBalanceDetail,
    summary="Get detailed balance for specific leave type",
    description="""
    Get detailed information for a specific leave type.
    
    **Includes**:
    - Allocated quota
    - Used days (approved leaves)
    - Pending days (applications under review)
    - Available balance
    - Carry-forward information
    - Expiry dates
    """,
)
async def get_leave_type_balance_detail(
    leave_type: str = Path(..., description="Leave type (casual, sick, etc.)"),
    student_id: str = Depends(get_target_student_id),
    current_user=Depends(verify_student_or_admin),
    service: LeaveBalanceService = Depends(get_leave_balance_service),
) -> LeaveBalanceDetail:
    """
    Get granular balance details for a specific leave type.
    """
    try:
        # Validate leave type
        try:
            LeaveType(leave_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid leave type: {leave_type}",
            )
        
        detail = service.get_balance_detail(
            student_id=student_id,
            leave_type=leave_type,
        )
        
        return detail
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve balance detail: {str(e)}",
        )


# ============================================================================
# Balance Adjustment Endpoints (Admin)
# ============================================================================

@router.post(
    "/adjust",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Manually adjust leave balance",
    description="""
    Perform manual adjustment to student's leave balance.
    
    **Permission**: Admins only
    
    **Use Cases**:
    - Correction of errors
    - Special allocations
    - Penalty deductions
    - Carry-forward adjustments
    
    **Requirements**:
    - Reason must be provided for audit
    - Adjustments are logged and tracked
    """,
    responses={
        200: {"description": "Adjustment applied successfully"},
        400: {"description": "Invalid adjustment parameters"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Student not found"},
    },
)
async def adjust_leave_balance(
    student_id: str = Query(..., description="Student ID"),
    leave_type: str = Query(..., description="Leave type to adjust"),
    days: int = Query(..., description="Days to adjust (positive or negative)"),
    reason: str = Query(..., min_length=10, description="Reason for adjustment"),
    reference: Optional[str] = Query(None, description="Reference number/document"),
    _admin=Depends(deps.get_admin_user),
    service: LeaveBalanceService = Depends(get_leave_balance_service),
) -> dict[str, Any]:
    """
    Apply manual adjustment to leave balance with full audit trail.
    
    All adjustments are logged for transparency and accountability.
    """
    try:
        # Validate leave type
        try:
            LeaveType(leave_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid leave type: {leave_type}",
            )
        
        # Validate adjustment magnitude
        if days == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Adjustment days cannot be zero",
            )
        
        if abs(days) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Adjustment magnitude too large (max: ±100 days)",
            )
        
        # Apply the adjustment
        result = service.adjust_balance(
            student_id=student_id,
            leave_type=leave_type,
            days=days,
            reason=reason,
            reference=reference,
            actor_id=_admin.id,
        )
        
        return {
            "status": "success",
            "message": "Balance adjusted successfully",
            "student_id": student_id,
            "leave_type": leave_type,
            "adjustment": days,
            "new_balance": result.get("new_balance"),
            "adjustment_id": result.get("adjustment_id"),
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except LookupError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to adjust balance: {str(e)}",
        )


@router.get(
    "/adjustments",
    response_model=List[LeaveAdjustment],
    summary="Get balance adjustment history",
    description="Retrieve history of all manual balance adjustments",
)
async def get_adjustment_history(
    student_id: str = Depends(get_target_student_id),
    leave_type: Optional[str] = Query(None, description="Filter by leave type"),
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user=Depends(verify_student_or_admin),
    service: LeaveBalanceService = Depends(get_leave_balance_service),
) -> List[LeaveAdjustment]:
    """
    Get complete history of balance adjustments for transparency.
    """
    try:
        adjustments = service.get_adjustment_history(
            student_id=student_id,
            leave_type=leave_type,
            pagination=pagination.to_dict(),
        )
        
        return adjustments
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve adjustment history: {str(e)}",
        )


# ============================================================================
# Usage Tracking Endpoints
# ============================================================================

@router.get(
    "/usage",
    response_model=LeaveUsageHistory,
    summary="Get detailed leave usage history",
    description="""
    Retrieve comprehensive usage history showing how leave balance was consumed.
    
    **Includes**:
    - Approved leave applications
    - Leave dates and durations
    - Leave types and purposes
    - Running balance calculations
    """,
)
async def get_usage_history(
    student_id: str = Depends(get_target_student_id),
    leave_type: Optional[str] = Query(None, description="Filter by leave type"),
    from_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    pagination: PaginationParams = Depends(get_pagination_params),
    current_user=Depends(verify_student_or_admin),
    service: LeaveBalanceService = Depends(get_leave_balance_service),
) -> LeaveUsageHistory:
    """
    Get detailed breakdown of how leave balance has been utilized.
    """
    try:
        usage_history = service.list_usage_details(
            student_id=student_id,
            leave_type=leave_type,
            from_date=from_date,
            to_date=to_date,
            pagination=pagination.to_dict(),
        )
        
        return usage_history
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve usage history: {str(e)}",
        )


# ============================================================================
# Balance Forecasting & Planning
# ============================================================================

@router.get(
    "/forecast",
    summary="Get balance forecast",
    description="""
    Forecast leave balance availability for future planning.
    
    **Includes**:
    - Projected available days
    - Pending deductions
    - Upcoming expiry dates
    - Carry-forward projections
    """,
)
async def get_balance_forecast(
    student_id: str = Depends(get_target_student_id),
    months_ahead: int = Query(3, ge=1, le=12, description="Months to forecast"),
    current_user=Depends(verify_student_or_admin),
    service: LeaveBalanceService = Depends(get_leave_balance_service),
) -> dict[str, Any]:
    """
    Get balance forecast for planning future leave applications.
    """
    try:
        forecast = service.forecast_balance(
            student_id=student_id,
            months_ahead=months_ahead,
        )
        
        return forecast
        
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Balance forecasting feature coming soon",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate forecast: {str(e)}",
        )


# ============================================================================
# Batch Operations
# ============================================================================

@router.post(
    "/batch/reset",
    summary="Reset balances for academic year",
    description="Admin endpoint to reset balances at year start",
)
async def batch_reset_balances(
    hostel_id: str = Query(...),
    academic_year: str = Query(...),
    _admin=Depends(deps.get_admin_user),
    service: LeaveBalanceService = Depends(get_leave_balance_service),
) -> dict[str, Any]:
    """
    Reset leave balances for all students in a hostel for new academic year.
    Admin only operation.
    """
    try:
        result = service.batch_reset_balances(
            hostel_id=hostel_id,
            academic_year=academic_year,
            actor_id=_admin.id,
        )
        
        return {
            "status": "success",
            "message": "Balances reset successfully",
            "hostel_id": hostel_id,
            "academic_year": academic_year,
            "students_affected": result.get("count", 0),
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch reset failed: {str(e)}",
        )