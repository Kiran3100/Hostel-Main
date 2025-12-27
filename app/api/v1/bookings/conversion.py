"""
Booking Conversion API

Handles conversion of bookings to permanent student records including:
- Converting bookings to student accounts
- Pre-conversion checklist validation
- Conversion rollback (super admin only)
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.logging import get_logger
from app.schemas.booking.booking_conversion import (
    ConversionChecklist,
    ConversionResponse,
    ConversionRollback,
    ConvertToStudentRequest,
)
from app.services.booking.booking_conversion_service import BookingConversionService

logger = get_logger(__name__)

router = APIRouter(prefix="/bookings/conversion", tags=["bookings:conversion"])


def get_conversion_service(
    db: Session = Depends(deps.get_db),
) -> BookingConversionService:
    """
    Dependency injection for BookingConversionService.
    
    Args:
        db: Database session
        
    Returns:
        BookingConversionService instance
    """
    return BookingConversionService(db=db)


@router.post(
    "/{booking_id}",
    response_model=ConversionResponse,
    summary="Convert booking to student",
    description="Convert an approved booking to a permanent student record. Requires admin privileges.",
    responses={
        200: {"description": "Booking converted successfully"},
        400: {"description": "Invalid conversion request or missing prerequisites"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Booking not found"},
        409: {"description": "Booking cannot be converted in current status"},
    },
)
async def convert_booking(
    booking_id: str,
    payload: ConvertToStudentRequest,
    admin=Depends(deps.get_admin_user),
    service: BookingConversionService = Depends(get_conversion_service),
) -> ConversionResponse:
    """
    Convert booking to student account.
    
    Args:
        booking_id: Unique booking identifier
        payload: Conversion request data
        admin: Admin user performing the conversion
        service: Conversion service instance
        
    Returns:
        Conversion response with student details
        
    Raises:
        HTTPException: If conversion fails
    """
    try:
        logger.info(
            f"Admin {admin.id} converting booking {booking_id} to student",
            extra={"admin_id": admin.id, "booking_id": booking_id},
        )
        
        response = service.convert(booking_id, payload, actor_id=admin.id)
        
        logger.info(
            f"Booking {booking_id} converted successfully to student {response.student_id}"
        )
        return response
    except ValueError as e:
        logger.warning(f"Invalid conversion for booking {booking_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error converting booking {booking_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to convert booking to student",
        )


@router.get(
    "/{booking_id}/checklist",
    response_model=ConversionChecklist,
    summary="Get conversion checklist",
    description="Retrieve pre-conversion checklist to verify booking is ready for conversion.",
    responses={
        200: {"description": "Checklist retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Booking not found"},
    },
)
async def get_conversion_checklist(
    booking_id: str,
    admin=Depends(deps.get_admin_user),
    service: BookingConversionService = Depends(get_conversion_service),
) -> ConversionChecklist:
    """
    Get conversion checklist for a booking.
    
    Validates all prerequisites for conversion including:
    - Booking status
    - Payment completion
    - Required documents
    - Room assignment
    - Other hostel-specific requirements
    
    Args:
        booking_id: Unique booking identifier
        admin: Admin user requesting checklist
        service: Conversion service instance
        
    Returns:
        Conversion checklist with status of each requirement
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.debug(f"Fetching conversion checklist for booking {booking_id}")
        
        checklist = service.get_checklist(booking_id)
        
        logger.debug(
            f"Conversion checklist for booking {booking_id}: "
            f"ready={checklist.is_ready}, items={len(checklist.items)}"
        )
        return checklist
    except Exception as e:
        logger.error(
            f"Error fetching conversion checklist for booking {booking_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversion checklist",
        )


@router.post(
    "/{booking_id}/rollback",
    status_code=status.HTTP_200_OK,
    summary="Rollback conversion",
    description="Rollback a booking-to-student conversion. Requires super admin privileges. Use with extreme caution.",
    responses={
        200: {"description": "Conversion rolled back successfully"},
        400: {"description": "Invalid rollback request"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions (super admin required)"},
        404: {"description": "Booking or conversion record not found"},
        409: {"description": "Conversion cannot be rolled back"},
    },
)
async def rollback_conversion(
    booking_id: str,
    payload: ConversionRollback,
    super_admin=Depends(deps.get_super_admin_user),
    service: BookingConversionService = Depends(get_conversion_service),
) -> dict[str, str]:
    """
    Rollback a booking conversion.
    
    WARNING: This is a dangerous operation that should only be used in exceptional circumstances.
    It will reverse the student account creation and restore the booking to its pre-conversion state.
    
    Args:
        booking_id: Unique booking identifier
        payload: Rollback request with justification
        super_admin: Super admin user performing the rollback
        service: Conversion service instance
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If rollback fails
    """
    try:
        logger.warning(
            f"SUPER ADMIN {super_admin.id} rolling back conversion for booking {booking_id}",
            extra={
                "super_admin_id": super_admin.id,
                "booking_id": booking_id,
                "reason": payload.reason,
            },
        )
        
        service.rollback(booking_id, payload, actor_id=super_admin.id)
        
        logger.warning(
            f"Conversion rollback completed for booking {booking_id}",
            extra={"booking_id": booking_id},
        )
        
        return {
            "detail": "Conversion rolled back successfully",
            "booking_id": booking_id,
        }
    except ValueError as e:
        logger.error(f"Invalid rollback for booking {booking_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error rolling back conversion for booking {booking_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rollback conversion",
        )