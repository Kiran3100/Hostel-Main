"""
Inquiry conversion service: convert qualified inquiries to bookings.

Enhanced with:
- Pre-conversion validation
- Booking creation orchestration
- Conversion analytics tracking
- Rollback support for failed conversions
"""

from typing import Optional, Dict, Any
from uuid import UUID
import logging
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.inquiry.inquiry_repository import InquiryRepository
from app.models.inquiry.inquiry import Inquiry as InquiryModel
from app.schemas.inquiry.inquiry_status import InquiryConversion

logger = logging.getLogger(__name__)


class InquiryConversionService(BaseService[InquiryModel, InquiryRepository]):
    """
    Convert qualified inquiries to bookings.
    
    Handles:
    - Pre-conversion validation
    - Booking creation coordination
    - Inquiry status updates
    - Conversion metrics tracking
    - Rollback on failure
    """

    def __init__(self, repository: InquiryRepository, db_session: Session):
        """
        Initialize conversion service.
        
        Args:
            repository: InquiryRepository for data access
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)
        self._logger = logger

    # =========================================================================
    # CONVERSION OPERATIONS
    # =========================================================================

    def convert(
        self,
        request: InquiryConversion,
        converted_by: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Convert an inquiry to a booking with comprehensive validation.
        
        Args:
            request: InquiryConversion with conversion details
            converted_by: UUID of user performing conversion
            
        Returns:
            ServiceResult with conversion details including booking_id
        """
        try:
            self._logger.info(
                f"Converting inquiry {request.inquiry_id} to booking"
            )
            
            # Validate conversion request
            validation_error = self._validate_conversion(request)
            if validation_error:
                return ServiceResult.failure(validation_error)
            
            # Verify inquiry exists and is eligible for conversion
            inquiry = self.repository.get_by_id(request.inquiry_id)
            if not inquiry:
                self._logger.warning(f"Inquiry {request.inquiry_id} not found for conversion")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Inquiry with ID {request.inquiry_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Check if already converted
            if hasattr(inquiry, 'is_converted') and inquiry.is_converted:
                self._logger.warning(f"Inquiry {request.inquiry_id} already converted")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Inquiry has already been converted to a booking",
                        details={"booking_id": str(getattr(inquiry, 'booking_id', None))},
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Validate inquiry status allows conversion
            eligibility_error = self._check_conversion_eligibility(inquiry)
            if eligibility_error:
                return ServiceResult.failure(eligibility_error)
            
            # Perform conversion through repository
            # Repository handles booking creation and inquiry update
            payload = self.repository.convert_to_booking(request, converted_by=converted_by)
            
            if not payload or not payload.get('booking_id'):
                raise ValueError("Conversion failed: no booking_id returned")
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Successfully converted inquiry {request.inquiry_id} to "
                f"booking {payload.get('booking_id')}"
            )
            
            # Enrich payload with metadata
            result = {
                **payload,
                "inquiry_id": str(request.inquiry_id),
                "converted_by": str(converted_by) if converted_by else None,
                "converted_at": datetime.utcnow().isoformat(),
            }
            
            return ServiceResult.success(
                result,
                message="Inquiry successfully converted to booking",
                metadata={
                    "booking_id": str(payload.get('booking_id')),
                    "conversion_timestamp": datetime.utcnow().isoformat(),
                }
            )
            
        except ValueError as e:
            self.db.rollback()
            self._logger.error(f"Conversion validation error: {str(e)}")
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Conversion failed: {str(e)}",
                    severity=ErrorSeverity.ERROR,
                )
            )
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error converting inquiry {request.inquiry_id}: {str(e)}"
            )
            return self._handle_exception(e, "convert inquiry", request.inquiry_id)
        except Exception as e:
            self.db.rollback()
            self._logger.exception(
                f"Unexpected error converting inquiry {request.inquiry_id}: {str(e)}"
            )
            return self._handle_exception(e, "convert inquiry", request.inquiry_id)

    def reverse_conversion(
        self,
        inquiry_id: UUID,
        reason: str,
        reversed_by: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Reverse a conversion (mark inquiry as not converted).
        
        Note: This does NOT delete the booking, only updates inquiry status.
        
        Args:
            inquiry_id: UUID of inquiry to reverse
            reason: Reason for reversal
            reversed_by: User performing reversal
            
        Returns:
            ServiceResult with reversal details
        """
        try:
            self._logger.info(f"Reversing conversion for inquiry {inquiry_id}")
            
            # Verify inquiry exists and is converted
            inquiry = self.repository.get_by_id(inquiry_id)
            if not inquiry:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Inquiry with ID {inquiry_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            if not (hasattr(inquiry, 'is_converted') and inquiry.is_converted):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Inquiry is not in converted state",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            booking_id = getattr(inquiry, 'booking_id', None)
            
            # Use repository method if available
            if hasattr(self.repository, 'reverse_conversion'):
                result = self.repository.reverse_conversion(
                    inquiry_id,
                    reason=reason,
                    reversed_by=reversed_by
                )
            else:
                # Manual reversal
                inquiry.is_converted = False
                inquiry.booking_id = None
                inquiry.conversion_reversed_at = datetime.utcnow()
                inquiry.conversion_reversal_reason = reason
                inquiry.conversion_reversed_by = reversed_by
                
                result = {
                    "inquiry_id": str(inquiry_id),
                    "previous_booking_id": str(booking_id) if booking_id else None,
                    "reversed_by": str(reversed_by) if reversed_by else None,
                    "reason": reason,
                }
            
            self.db.commit()
            
            self._logger.info(f"Successfully reversed conversion for inquiry {inquiry_id}")
            
            return ServiceResult.success(
                result,
                message="Conversion reversed successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error reversing conversion: {str(e)}")
            return self._handle_exception(e, "reverse conversion", inquiry_id)
        except Exception as e:
            self.db.rollback()
            self._logger.exception(f"Unexpected error reversing conversion: {str(e)}")
            return self._handle_exception(e, "reverse conversion", inquiry_id)

    # =========================================================================
    # CONVERSION ANALYTICS
    # =========================================================================

    def get_conversion_metrics(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get conversion rate metrics and statistics.
        
        Args:
            hostel_id: Optional filter by hostel
            start_date: Optional start of date range
            end_date: Optional end of date range
            
        Returns:
            ServiceResult with conversion metrics
        """
        try:
            self._logger.debug(
                f"Calculating conversion metrics for hostel: {hostel_id or 'all'}"
            )
            
            # Use repository method if available
            if hasattr(self.repository, 'get_conversion_metrics'):
                metrics = self.repository.get_conversion_metrics(
                    hostel_id=hostel_id,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                # Calculate basic metrics
                query = self.db.query(InquiryModel)
                
                if hostel_id:
                    query = query.filter(InquiryModel.hostel_id == hostel_id)
                if start_date:
                    query = query.filter(InquiryModel.created_at >= start_date)
                if end_date:
                    query = query.filter(InquiryModel.created_at <= end_date)
                
                total_inquiries = query.count()
                converted_inquiries = query.filter(
                    InquiryModel.is_converted == True
                ).count()
                
                conversion_rate = (
                    (converted_inquiries / total_inquiries * 100)
                    if total_inquiries > 0 else 0
                )
                
                metrics = {
                    "total_inquiries": total_inquiries,
                    "converted_inquiries": converted_inquiries,
                    "conversion_rate": round(conversion_rate, 2),
                    "pending_inquiries": total_inquiries - converted_inquiries,
                    "hostel_id": str(hostel_id) if hostel_id else None,
                    "period": {
                        "start": start_date.isoformat() if start_date else None,
                        "end": end_date.isoformat() if end_date else None,
                    }
                }
            
            return ServiceResult.success(metrics)
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error calculating conversion metrics: {str(e)}")
            return self._handle_exception(e, "get conversion metrics")
        except Exception as e:
            self._logger.exception(f"Unexpected error calculating conversion metrics: {str(e)}")
            return self._handle_exception(e, "get conversion metrics")

    def get_conversion_funnel(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get conversion funnel data (inquiry stages to booking).
        
        Args:
            hostel_id: Optional filter by hostel
            
        Returns:
            ServiceResult with funnel stage metrics
        """
        try:
            self._logger.debug(f"Fetching conversion funnel for hostel: {hostel_id or 'all'}")
            
            # Use repository method if available
            if hasattr(self.repository, 'get_conversion_funnel'):
                funnel = self.repository.get_conversion_funnel(hostel_id=hostel_id)
            else:
                # Build basic funnel
                query = self.db.query(InquiryModel)
                if hostel_id:
                    query = query.filter(InquiryModel.hostel_id == hostel_id)
                
                funnel = {
                    "total_inquiries": query.count(),
                    "contacted": query.filter(
                        InquiryModel.status.in_(['contacted', 'qualified', 'converted'])
                    ).count(),
                    "qualified": query.filter(
                        InquiryModel.status.in_(['qualified', 'converted'])
                    ).count(),
                    "converted": query.filter(InquiryModel.is_converted == True).count(),
                    "hostel_id": str(hostel_id) if hostel_id else None,
                }
                
                # Calculate drop-off rates
                if funnel["total_inquiries"] > 0:
                    funnel["contact_rate"] = round(
                        funnel["contacted"] / funnel["total_inquiries"] * 100, 2
                    )
                    funnel["qualification_rate"] = round(
                        funnel["qualified"] / funnel["total_inquiries"] * 100, 2
                    )
                    funnel["conversion_rate"] = round(
                        funnel["converted"] / funnel["total_inquiries"] * 100, 2
                    )
            
            return ServiceResult.success(funnel)
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error fetching conversion funnel: {str(e)}")
            return self._handle_exception(e, "get conversion funnel")
        except Exception as e:
            self._logger.exception(f"Unexpected error fetching conversion funnel: {str(e)}")
            return self._handle_exception(e, "get conversion funnel")

    # =========================================================================
    # VALIDATION HELPERS
    # =========================================================================

    def _validate_conversion(self, request: InquiryConversion) -> Optional[ServiceError]:
        """
        Validate conversion request.
        
        Args:
            request: Conversion request to validate
            
        Returns:
            ServiceError if invalid, None if valid
        """
        if not request.inquiry_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Inquiry ID is required for conversion",
                severity=ErrorSeverity.ERROR,
            )
        
        # Validate booking details if present
        if hasattr(request, 'check_in_date') and hasattr(request, 'check_out_date'):
            if request.check_in_date and request.check_out_date:
                if request.check_in_date >= request.check_out_date:
                    return ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Check-in date must be before check-out date",
                        severity=ErrorSeverity.ERROR,
                    )
                
                if request.check_in_date < datetime.utcnow().date():
                    return ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Check-in date cannot be in the past",
                        severity=ErrorSeverity.WARNING,
                    )
        
        # Validate room/bed details
        if hasattr(request, 'room_id') and not request.room_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Room ID is required for conversion",
                severity=ErrorSeverity.ERROR,
            )
        
        return None

    def _check_conversion_eligibility(
        self,
        inquiry: InquiryModel
    ) -> Optional[ServiceError]:
        """
        Check if inquiry is eligible for conversion.
        
        Args:
            inquiry: Inquiry model to check
            
        Returns:
            ServiceError if not eligible, None if eligible
        """
        # Check status
        if hasattr(inquiry, 'status'):
            ineligible_statuses = ['cancelled', 'lost', 'spam']
            if inquiry.status in ineligible_statuses:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Cannot convert inquiry with status '{inquiry.status}'",
                    severity=ErrorSeverity.ERROR,
                )
        
        # Check if inquiry has required information
        if hasattr(inquiry, 'guest_name') and not inquiry.guest_name:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Guest name is required for conversion",
                severity=ErrorSeverity.ERROR,
            )
        
        # Add more eligibility checks as needed
        
        return None

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_convertible_inquiries(
        self,
        hostel_id: Optional[UUID] = None,
        limit: int = 50,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get list of inquiries eligible for conversion.
        
        Args:
            hostel_id: Optional filter by hostel
            limit: Maximum number of results
            
        Returns:
            ServiceResult with list of convertible inquiries
        """
        try:
            limit = min(max(1, limit), 100)
            
            self._logger.debug(f"Fetching convertible inquiries, limit: {limit}")
            
            query = self.db.query(InquiryModel).filter(
                InquiryModel.is_converted == False
            )
            
            if hostel_id:
                query = query.filter(InquiryModel.hostel_id == hostel_id)
            
            # Filter by eligible statuses
            eligible_statuses = ['qualified', 'contacted', 'pending']
            query = query.filter(InquiryModel.status.in_(eligible_statuses))
            
            inquiries = query.limit(limit).all()
            
            result = [
                {
                    "inquiry_id": str(inq.id),
                    "guest_name": getattr(inq, 'guest_name', None),
                    "status": getattr(inq, 'status', None),
                    "created_at": getattr(inq, 'created_at', None),
                    "assigned_to": str(getattr(inq, 'assigned_to', None)) if getattr(inq, 'assigned_to', None) else None,
                }
                for inq in inquiries
            ]
            
            return ServiceResult.success(
                result,
                metadata={
                    "count": len(result),
                    "hostel_id": str(hostel_id) if hostel_id else None,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error fetching convertible inquiries: {str(e)}")
            return self._handle_exception(e, "get convertible inquiries")
        except Exception as e:
            self._logger.exception(f"Unexpected error fetching convertible inquiries: {str(e)}")
            return self._handle_exception(e, "get convertible inquiries")