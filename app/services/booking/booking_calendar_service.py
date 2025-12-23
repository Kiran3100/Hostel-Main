"""
Calendar & availability views for bookings.

Enhanced with:
- Efficient date range queries
- Caching for calendar views
- Occupancy analytics
- Performance optimization
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, date
import logging
import calendar
from dateutil.relativedelta import relativedelta

from sqlalchemy.orm import Session

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.booking import BookingCalendarRepository
from app.models.booking.booking_calendar import BookingCalendarEvent as BookingCalendarEventModel
from app.schemas.booking.booking_calendar import (
    CalendarView,
    DayBookings,
    BookingEvent,
    AvailabilityCalendar,
    DayAvailability,
)

logger = logging.getLogger(__name__)


class BookingCalendarService(BaseService[BookingCalendarEventModel, BookingCalendarRepository]):
    """
    Provide calendar-style and capacity-planning representations.
    
    Features:
    - Monthly/weekly calendar views
    - Availability tracking
    - Occupancy statistics
    - Capacity planning
    """

    def __init__(self, repository: BookingCalendarRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._calendar_cache: Dict[str, Any] = {}
        self._cache_ttl = 600  # 10 minutes for calendar data

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validate_month_format(self, month: str) -> Optional[ServiceError]:
        """
        Validate month format (YYYY-MM).
        
        Args:
            month: Month string in YYYY-MM format
            
        Returns:
            ServiceError if invalid, None otherwise
        """
        try:
            parts = month.split('-')
            if len(parts) != 2:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Invalid month format. Expected YYYY-MM",
                    severity=ErrorSeverity.ERROR,
                    details={"month": month, "expected_format": "YYYY-MM"}
                )
            
            year = int(parts[0])
            month_num = int(parts[1])
            
            if year < 2000 or year > 2100:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Year must be between 2000 and 2100",
                    severity=ErrorSeverity.ERROR,
                    details={"year": year}
                )
            
            if month_num < 1 or month_num > 12:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Month must be between 1 and 12",
                    severity=ErrorSeverity.ERROR,
                    details={"month": month_num}
                )
            
            return None
            
        except ValueError:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Invalid month format. Expected YYYY-MM with numeric values",
                severity=ErrorSeverity.ERROR,
                details={"month": month}
            )

    def _parse_month(self, month: str) -> Optional[date]:
        """Parse month string to date object."""
        try:
            parts = month.split('-')
            year = int(parts[0])
            month_num = int(parts[1])
            return date(year, month_num, 1)
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # Cache Management
    # -------------------------------------------------------------------------

    def _get_cache_key(self, hostel_id: UUID, month: str, room_id: Optional[UUID] = None) -> str:
        """Generate cache key for calendar data."""
        key_parts = [str(hostel_id), month]
        if room_id:
            key_parts.append(str(room_id))
        return ":".join(key_parts)

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get calendar data from cache if valid."""
        if cache_key in self._calendar_cache:
            cached_data, cached_time = self._calendar_cache[cache_key]
            age = (datetime.utcnow() - cached_time).total_seconds()
            
            if age < self._cache_ttl:
                self._logger.debug(f"Calendar cache hit for key {cache_key[:20]}... (age: {age:.1f}s)")
                return cached_data
            else:
                del self._calendar_cache[cache_key]
        
        return None

    def _set_cache(self, cache_key: str, data: Any) -> None:
        """Set calendar cache entry."""
        self._calendar_cache[cache_key] = (data, datetime.utcnow())
        
        # Limit cache size
        if len(self._calendar_cache) > 50:
            oldest_key = min(self._calendar_cache.keys(), key=lambda k: self._calendar_cache[k][1])
            del self._calendar_cache[oldest_key]

    def clear_cache(self, hostel_id: Optional[UUID] = None) -> None:
        """
        Clear calendar cache.
        
        Args:
            hostel_id: Optional hostel ID to clear specific cache
        """
        if hostel_id:
            # Clear cache for specific hostel
            keys_to_remove = [k for k in self._calendar_cache.keys() if k.startswith(str(hostel_id))]
            for key in keys_to_remove:
                del self._calendar_cache[key]
            self._logger.info(f"Cleared calendar cache for hostel {hostel_id}")
        else:
            # Clear all cache
            self._calendar_cache.clear()
            self._logger.info("Cleared all calendar cache")

    # -------------------------------------------------------------------------
    # Calendar Views
    # -------------------------------------------------------------------------

    def get_month_view(
        self,
        hostel_id: UUID,
        month: str,  # YYYY-MM
        use_cache: bool = True,
    ) -> ServiceResult[CalendarView]:
        """
        Get monthly calendar view of bookings.
        
        Args:
            hostel_id: UUID of hostel
            month: Month in YYYY-MM format
            use_cache: Whether to use cached data
            
        Returns:
            ServiceResult containing CalendarView or error
        """
        try:
            # Validate month format
            validation_error = self._validate_month_format(month)
            if validation_error:
                return ServiceResult.failure(validation_error)

            # Check cache
            cache_key = self._get_cache_key(hostel_id, month)
            if use_cache:
                cached_result = self._get_from_cache(cache_key)
                if cached_result is not None:
                    return ServiceResult.success(
                        cached_result,
                        metadata={"cached": True}
                    )

            self._logger.info(
                f"Fetching monthly calendar view for hostel {hostel_id}, month {month}",
                extra={
                    "hostel_id": str(hostel_id),
                    "month": month
                }
            )

            start_time = datetime.utcnow()

            # Fetch calendar view
            cv = self.repository.get_month_view(hostel_id, month)
            
            # Cache result
            if use_cache:
                self._set_cache(cache_key, cv)

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            self._logger.info(
                f"Calendar view fetched in {duration_ms:.2f}ms",
                extra={
                    "hostel_id": str(hostel_id),
                    "month": month,
                    "duration_ms": duration_ms
                }
            )

            return ServiceResult.success(
                cv,
                metadata={
                    "cached": False,
                    "duration_ms": duration_ms
                }
            )

        except Exception as e:
            self._logger.error(f"Error fetching monthly calendar view: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get monthly booking calendar", hostel_id)

    def get_week_view(
        self,
        hostel_id: UUID,
        start_date: date,
    ) -> ServiceResult[CalendarView]:
        """
        Get weekly calendar view of bookings.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start date of week
            
        Returns:
            ServiceResult containing CalendarView or error
        """
        try:
            if start_date < date(2000, 1, 1) or start_date > date(2100, 12, 31):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Start date must be between 2000-01-01 and 2100-12-31",
                        severity=ErrorSeverity.ERROR,
                        details={"start_date": str(start_date)}
                    )
                )

            self._logger.debug(
                f"Fetching weekly calendar view for hostel {hostel_id}",
                extra={
                    "hostel_id": str(hostel_id),
                    "start_date": str(start_date)
                }
            )

            cv = self.repository.get_week_view(hostel_id, start_date)

            return ServiceResult.success(cv)

        except Exception as e:
            self._logger.error(f"Error fetching weekly calendar view: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get weekly booking calendar", hostel_id)

    def get_day_view(
        self,
        hostel_id: UUID,
        target_date: date,
    ) -> ServiceResult[DayBookings]:
        """
        Get daily view of bookings.
        
        Args:
            hostel_id: UUID of hostel
            target_date: Target date
            
        Returns:
            ServiceResult containing DayBookings or error
        """
        try:
            self._logger.debug(
                f"Fetching daily view for hostel {hostel_id}, date {target_date}",
                extra={
                    "hostel_id": str(hostel_id),
                    "date": str(target_date)
                }
            )

            day_bookings = self.repository.get_day_view(hostel_id, target_date)

            return ServiceResult.success(day_bookings)

        except Exception as e:
            self._logger.error(f"Error fetching daily view: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get daily booking view", hostel_id)

    # -------------------------------------------------------------------------
    # Availability Calendar
    # -------------------------------------------------------------------------

    def get_availability_calendar(
        self,
        hostel_id: UUID,
        month: str,
        room_id: Optional[UUID] = None,
        use_cache: bool = True,
    ) -> ServiceResult[AvailabilityCalendar]:
        """
        Get availability calendar for capacity planning.
        
        Args:
            hostel_id: UUID of hostel
            month: Month in YYYY-MM format
            room_id: Optional room filter
            use_cache: Whether to use cached data
            
        Returns:
            ServiceResult containing AvailabilityCalendar or error
        """
        try:
            # Validate month format
            validation_error = self._validate_month_format(month)
            if validation_error:
                return ServiceResult.failure(validation_error)

            # Check cache
            cache_key = self._get_cache_key(hostel_id, month, room_id)
            if use_cache:
                cached_result = self._get_from_cache(cache_key)
                if cached_result is not None:
                    return ServiceResult.success(
                        cached_result,
                        metadata={"cached": True}
                    )

            self._logger.info(
                f"Fetching availability calendar for hostel {hostel_id}, month {month}",
                extra={
                    "hostel_id": str(hostel_id),
                    "month": month,
                    "room_id": str(room_id) if room_id else None
                }
            )

            start_time = datetime.utcnow()

            # Fetch availability calendar
            cal = self.repository.get_availability_calendar(hostel_id, month, room_id=room_id)
            
            # Cache result
            if use_cache:
                self._set_cache(cache_key, cal)

            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            self._logger.info(
                f"Availability calendar fetched in {duration_ms:.2f}ms",
                extra={
                    "hostel_id": str(hostel_id),
                    "month": month,
                    "duration_ms": duration_ms
                }
            )

            return ServiceResult.success(
                cal,
                metadata={
                    "cached": False,
                    "duration_ms": duration_ms
                }
            )

        except Exception as e:
            self._logger.error(f"Error fetching availability calendar: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get availability calendar", hostel_id)

    def get_occupancy_rate(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        room_id: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get occupancy rate for date range.
        
        Args:
            hostel_id: UUID of hostel
            start_date: Start date
            end_date: End date
            room_id: Optional room filter
            
        Returns:
            ServiceResult containing occupancy statistics
        """
        try:
            # Validate date range
            if start_date >= end_date:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Start date must be before end date",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "start_date": str(start_date),
                            "end_date": str(end_date)
                        }
                    )
                )

            # Limit date range to 1 year
            days_diff = (end_date - start_date).days
            if days_diff > 365:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Date range cannot exceed 365 days",
                        severity=ErrorSeverity.ERROR,
                        details={"days": days_diff}
                    )
                )

            self._logger.debug(
                f"Calculating occupancy rate for hostel {hostel_id}",
                extra={
                    "hostel_id": str(hostel_id),
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "room_id": str(room_id) if room_id else None
                }
            )

            occupancy = self.repository.get_occupancy_rate(
                hostel_id,
                start_date,
                end_date,
                room_id=room_id
            )

            return ServiceResult.success(
                occupancy,
                metadata={
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "days": days_diff
                }
            )

        except Exception as e:
            self._logger.error(f"Error calculating occupancy rate: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get occupancy rate", hostel_id)

    # -------------------------------------------------------------------------
    # Capacity Planning
    # -------------------------------------------------------------------------

    def get_capacity_forecast(
        self,
        hostel_id: UUID,
        forecast_months: int = 3,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get capacity forecast for planning.
        
        Args:
            hostel_id: UUID of hostel
            forecast_months: Number of months to forecast
            
        Returns:
            ServiceResult containing forecast data
        """
        try:
            if forecast_months < 1 or forecast_months > 12:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Forecast months must be between 1 and 12",
                        severity=ErrorSeverity.ERROR,
                        details={"forecast_months": forecast_months}
                    )
                )

            self._logger.info(
                f"Generating capacity forecast for hostel {hostel_id}",
                extra={
                    "hostel_id": str(hostel_id),
                    "forecast_months": forecast_months
                }
            )

            forecast = self.repository.get_capacity_forecast(hostel_id, forecast_months)

            return ServiceResult.success(
                forecast,
                metadata={"forecast_months": forecast_months}
            )

        except Exception as e:
            self._logger.error(f"Error generating capacity forecast: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get capacity forecast", hostel_id)

    def get_peak_periods(
        self,
        hostel_id: UUID,
        year: int,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Identify peak booking periods.
        
        Args:
            hostel_id: UUID of hostel
            year: Year to analyze
            
        Returns:
            ServiceResult containing peak periods
        """
        try:
            if year < 2000 or year > 2100:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Year must be between 2000 and 2100",
                        severity=ErrorSeverity.ERROR,
                        details={"year": year}
                    )
                )

            self._logger.debug(
                f"Identifying peak periods for hostel {hostel_id}, year {year}",
                extra={
                    "hostel_id": str(hostel_id),
                    "year": year
                }
            )

            peak_periods = self.repository.get_peak_periods(hostel_id, year)

            return ServiceResult.success(
                peak_periods,
                metadata={
                    "year": year,
                    "period_count": len(peak_periods)
                }
            )

        except Exception as e:
            self._logger.error(f"Error identifying peak periods: {str(e)}", exc_info=True)
            return self._handle_exception(e, "get peak periods", hostel_id)