"""
Booking pricing/quote service integrating fee structure.

Enhanced with:
- Dynamic pricing calculation
- Discount application
- Tax calculation
- Price breakdown
- Quote caching
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
import logging

from sqlalchemy.orm import Session

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.booking import BookingRepository
from app.repositories.fee_structure import FeeStructureRepository, FeeCalculationRepository
from app.models.booking.booking import Booking as BookingModel
from app.schemas.booking.booking_base import BookingCreate
from app.schemas.fee_structure import FeeCalculation

logger = logging.getLogger(__name__)


class BookingPricingService(BaseService[BookingModel, BookingRepository]):
    """
    Compute booking pricing/quotes using fee structures and generate fee calculation records.
    
    Features:
    - Dynamic pricing calculation
    - Discount and promotion application
    - Tax calculation
    - Detailed price breakdown
    - Quote generation and caching
    """

    def __init__(
        self,
        booking_repo: BookingRepository,
        fee_structure_repo: FeeStructureRepository,
        fee_calc_repo: FeeCalculationRepository,
        db_session: Session,
    ):
        super().__init__(booking_repo, db_session)
        self.fee_structure_repo = fee_structure_repo
        self.fee_calc_repo = fee_calc_repo
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._quote_cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validate_quote_params(
        self,
        hostel_id: UUID,
        room_type: str,
        check_in_date: date,
        duration_months: int,
    ) -> Optional[ServiceError]:
        """Validate quote parameters."""
        if duration_months <= 0:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Duration must be positive",
                severity=ErrorSeverity.ERROR,
                details={"duration_months": duration_months}
            )

        if duration_months > 24:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Maximum duration is 24 months",
                severity=ErrorSeverity.ERROR,
                details={"duration_months": duration_months}
            )

        if check_in_date < date.today():
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Check-in date cannot be in the past",
                severity=ErrorSeverity.ERROR,
                details={"check_in_date": str(check_in_date)}
            )

        if not room_type or len(room_type.strip()) == 0:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Room type is required",
                severity=ErrorSeverity.ERROR
            )

        return None

    # -------------------------------------------------------------------------
    # Cache Management
    # -------------------------------------------------------------------------

    def _get_cache_key(
        self,
        hostel_id: UUID,
        room_type: str,
        check_in_date: date,
        duration_months: int,
        student_id: Optional[UUID] = None,
    ) -> str:
        """Generate cache key for quote."""
        key_parts = [
            str(hostel_id),
            room_type,
            str(check_in_date),
            str(duration_months)
        ]
        if student_id:
            key_parts.append(str(student_id))
        return ":".join(key_parts)

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get quote from cache if valid."""
        if cache_key in self._quote_cache:
            cached_data, cached_time = self._quote_cache[cache_key]
            age = (datetime.utcnow() - cached_time).total_seconds()
            
            if age < self._cache_ttl:
                self._logger.debug(f"Quote cache hit for key {cache_key[:20]}... (age: {age:.1f}s)")
                return cached_data
            else:
                del self._quote_cache[cache_key]
        
        return None

    def _set_cache(self, cache_key: str, data: Any) -> None:
        """Set quote cache entry."""
        self._quote_cache[cache_key] = (data, datetime.utcnow())
        
        # Limit cache size
        if len(self._quote_cache) > 100:
            oldest_key = min(self._quote_cache.keys(), key=lambda k: self._quote_cache[k][1])
            del self._quote_cache[oldest_key]

    def clear_cache(self, hostel_id: Optional[UUID] = None) -> None:
        """
        Clear pricing cache.
        
        Args:
            hostel_id: Optional hostel ID to clear specific cache
        """
        if hostel_id:
            keys_to_remove = [k for k in self._quote_cache.keys() if k.startswith(str(hostel_id))]
            for key in keys_to_remove:
                del self._quote_cache[key]
            self._logger.info(f"Cleared pricing cache for hostel {hostel_id}")
        else:
            self._quote_cache.clear()
            self._logger.info("Cleared all pricing cache")

    # -------------------------------------------------------------------------
    # Quote Operations
    # -------------------------------------------------------------------------

    def quote(
        self,
        hostel_id: UUID,
        room_type: str,
        check_in_date: date,
        duration_months: int,
        student_id: Optional[UUID] = None,
        discount_code: Optional[str] = None,
        use_cache: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Calculate a quote for given inputs, using current fee structure and rules.
        
        Args:
            hostel_id: UUID of hostel
            room_type: Type of room
            check_in_date: Check-in date
            duration_months: Duration in months
            student_id: Optional student ID for special pricing
            discount_code: Optional discount code
            use_cache: Whether to use cached quotes
            
        Returns:
            ServiceResult containing quote details or error
        """
        try:
            # Validate parameters
            validation_error = self._validate_quote_params(
                hostel_id, room_type, check_in_date, duration_months
            )
            if validation_error:
                return ServiceResult.failure(validation_error)

            # Check cache (only if no discount code)
            cache_key = None
            if use_cache and not discount_code:
                cache_key = self._get_cache_key(
                    hostel_id, room_type, check_in_date, duration_months, student_id
                )
                cached_quote = self._get_from_cache(cache_key)
                if cached_quote is not None:
                    return ServiceResult.success(
                        cached_quote,
                        metadata={"cached": True}
                    )

            self._logger.info(
                f"Calculating quote for hostel {hostel_id}",
                extra={
                    "hostel_id": str(hostel_id),
                    "room_type": room_type,
                    "check_in_date": str(check_in_date),
                    "duration_months": duration_months,
                    "student_id": str(student_id) if student_id else None
                }
            )

            start_time = datetime.utcnow()

            # Find applicable fee structure
            structure = self.fee_structure_repo.find_applicable(
                hostel_id, room_type, check_in_date
            )

            if not structure:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="No fee structure found for the given parameters",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "hostel_id": str(hostel_id),
                            "room_type": room_type,
                            "check_in_date": str(check_in_date)
                        }
                    )
                )

            # Calculate quote
            calc = self.fee_calc_repo.calculate_quote(
                structure,
                check_in_date,
                duration_months,
                student_id=student_id,
                discount_code=discount_code
            )

            # Cache result (if applicable)
            if cache_key and use_cache and not discount_code:
                self._set_cache(cache_key, calc)

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            self._logger.info(
                f"Quote calculated in {duration_ms:.2f}ms",
                extra={
                    "hostel_id": str(hostel_id),
                    "duration_ms": duration_ms,
                    "total_amount": str(calc.get('total_amount', 0)) if calc else None
                }
            )

            return ServiceResult.success(
                calc or {},
                message="Quote calculated successfully",
                metadata={
                    "cached": False,
                    "duration_ms": duration_ms
                }
            )

        except ValueError as e:
            self._logger.error(f"Validation error calculating quote: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.BUSINESS_RULE_VIOLATION,
                    message=str(e),
                    severity=ErrorSeverity.ERROR,
                    details={"hostel_id": str(hostel_id)}
                )
            )
        except Exception as e:
            self._logger.error(f"Error calculating quote: {str(e)}", exc_info=True)
            return self._handle_exception(e, "calculate booking quote", hostel_id)

    def recompute_for_booking(
        self,
        booking_id: UUID,
        effective_date: Optional[date] = None,
    ) -> ServiceResult[FeeCalculation]:
        """
        Recompute fees for an existing booking (e.g., after modification).
        
        Args:
            booking_id: UUID of booking
            effective_date: Optional effective date for recalculation
            
        Returns:
            ServiceResult containing FeeCalculation or error
        """
        try:
            self._logger.info(
                f"Recomputing fees for booking {booking_id}",
                extra={
                    "booking_id": str(booking_id),
                    "effective_date": str(effective_date) if effective_date else None
                }
            )

            start_time = datetime.utcnow()

            # Recompute fees
            calc = self.fee_calc_repo.recompute_for_booking(
                booking_id,
                effective_date=effective_date
            )

            # Commit transaction
            self.db.commit()

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            self._logger.info(
                f"Fees recomputed for booking {booking_id} in {duration_ms:.2f}ms",
                extra={
                    "booking_id": str(booking_id),
                    "duration_ms": duration_ms
                }
            )

            return ServiceResult.success(
                calc,
                message="Fees recomputed successfully",
                metadata={"duration_ms": duration_ms}
            )

        except ValueError as e:
            self.db.rollback()
            self._logger.error(f"Validation error recomputing fees: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.BUSINESS_RULE_VIOLATION,
                    message=str(e),
                    severity=ErrorSeverity.ERROR,
                    details={"booking_id": str(booking_id)}
                )
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error recomputing fees: {str(e)}", exc_info=True)
            return self._handle_exception(e, "recompute fees", booking_id)

    # -------------------------------------------------------------------------
    # Price Breakdown Operations
    # -------------------------------------------------------------------------

    def get_price_breakdown(
        self,
        hostel_id: UUID,
        room_type: str,
        check_in_date: date,
        duration_months: int,
        include_taxes: bool = True,
        include_fees: bool = True,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get detailed price breakdown.
        
        Args:
            hostel_id: UUID of hostel
            room_type: Type of room
            check_in_date: Check-in date
            duration_months: Duration in months
            include_taxes: Whether to include taxes
            include_fees: Whether to include additional fees
            
        Returns:
            ServiceResult containing detailed breakdown
        """
        try:
            # Validate parameters
            validation_error = self._validate_quote_params(
                hostel_id, room_type, check_in_date, duration_months
            )
            if validation_error:
                return ServiceResult.failure(validation_error)

            self._logger.debug(
                f"Getting price breakdown for hostel {hostel_id}",
                extra={
                    "hostel_id": str(hostel_id),
                    "room_type": room_type
                }
            )

            breakdown = self.fee_calc_repo.get_price_breakdown(
                hostel_id,
                room_type,
                check_in_date,
                duration_months,
                include_taxes=include_taxes,
                include_fees=include_fees
            )

            return ServiceResult.success(breakdown)

        except Exception as e:
            self._logger.error(f"Error getting price breakdown: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get price breakdown", hostel_id)

    def apply_discount(
        self,
        booking_id: UUID,
        discount_code: str,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Apply discount to a booking.
        
        Args:
            booking_id: UUID of booking
            discount_code: Discount code to apply
            
        Returns:
            ServiceResult containing updated pricing
        """
        try:
            if not discount_code or len(discount_code.strip()) == 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Discount code is required",
                        severity=ErrorSeverity.ERROR
                    )
                )

            self._logger.info(
                f"Applying discount to booking {booking_id}",
                extra={
                    "booking_id": str(booking_id),
                    "discount_code": discount_code
                }
            )

            result = self.fee_calc_repo.apply_discount(booking_id, discount_code)

            self.db.commit()

            return ServiceResult.success(
                result,
                message="Discount applied successfully"
            )

        except ValueError as e:
            self.db.rollback()
            self._logger.error(f"Error applying discount: {str(e)}", exc_info=True)
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.BUSINESS_RULE_VIOLATION,
                    message=str(e),
                    severity=ErrorSeverity.ERROR,
                    details={"booking_id": str(booking_id), "discount_code": discount_code}
                )
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Error applying discount: {str(e)}", exc_info=True)
            return self._handle_exception(e, "apply discount", booking_id)

    def compare_prices(
        self,
        hostel_id: UUID,
        room_types: List[str],
        check_in_date: date,
        duration_months: int,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Compare prices across multiple room types.
        
        Args:
            hostel_id: UUID of hostel
            room_types: List of room types to compare
            check_in_date: Check-in date
            duration_months: Duration in months
            
        Returns:
            ServiceResult containing price comparison
        """
        try:
            if not room_types or len(room_types) == 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="At least one room type is required",
                        severity=ErrorSeverity.ERROR
                    )
                )

            if len(room_types) > 10:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Cannot compare more than 10 room types at once",
                        severity=ErrorSeverity.ERROR,
                        details={"count": len(room_types)}
                    )
                )

            self._logger.debug(
                f"Comparing prices for {len(room_types)} room types",
                extra={
                    "hostel_id": str(hostel_id),
                    "room_type_count": len(room_types)
                }
            )

            comparison = {
                "hostel_id": str(hostel_id),
                "check_in_date": str(check_in_date),
                "duration_months": duration_months,
                "room_types": []
            }

            for room_type in room_types:
                quote_result = self.quote(
                    hostel_id,
                    room_type,
                    check_in_date,
                    duration_months,
                    use_cache=True
                )

                if quote_result.success:
                    comparison["room_types"].append({
                        "room_type": room_type,
                        "pricing": quote_result.data
                    })

            return ServiceResult.success(comparison)

        except Exception as e:
            self._logger.error(f"Error comparing prices: {str(e)}", exc_info=True)
            return self._handle_exception(e, "compare prices", hostel_id)