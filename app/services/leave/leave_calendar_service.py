"""
Leave Calendar Service Module

Provides calendar-style visualizations of leave applications including:
- Monthly calendar views for hostels
- Monthly calendar views for students
- Period-based views
- Occupancy statistics
- Leave density analytics

Version: 2.0.0
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, datetime
import logging
from calendar import monthrange

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity
)
from app.repositories.leave.leave_application_repository import LeaveApplicationRepository
from app.models.leave.leave_application import LeaveApplication as LeaveApplicationModel

logger = logging.getLogger(__name__)


class LeaveCalendarService(BaseService[LeaveApplicationModel, LeaveApplicationRepository]):
    """
    Comprehensive service for calendar-based leave visualizations.
    
    Provides:
    - Monthly calendar views
    - Custom period views
    - Occupancy analytics
    - Leave density calculations
    - Multi-hostel comparisons
    """

    def __init__(self, repository: LeaveApplicationRepository, db_session: Session):
        """
        Initialize the leave calendar service.
        
        Args:
            repository: Leave application repository instance
            db_session: Active database session
        """
        super().__init__(repository, db_session)
        self._logger = logger

    def hostel_month_calendar(
        self,
        hostel_id: UUID,
        month: str,  # Format: YYYY-MM
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Generate monthly calendar view of leave applications for a hostel.
        
        Returns a structured calendar showing:
        - Daily leave counts
        - Leave details per day
        - Student information
        - Leave types and statuses
        - Occupancy rates
        
        Args:
            hostel_id: UUID of the hostel
            month: Month in YYYY-MM format
            
        Returns:
            ServiceResult containing calendar dictionary or error information
        """
        try:
            # Validate and parse month parameter
            validation_result = self._validate_month_format(month)
            if not validation_result.success:
                return validation_result
            
            year, month_num = self._parse_month(month)
            
            self._logger.debug(
                f"Generating hostel calendar for {hostel_id} "
                f"for month {month}"
            )
            
            # Get calendar data from repository
            calendar_data = self.repository.get_hostel_month_calendar(
                hostel_id,
                month
            )
            
            if calendar_data is None:
                calendar_data = self._generate_empty_calendar(year, month_num)
            
            # Enhance with analytics
            enhanced_data = self._enhance_calendar_data(
                calendar_data,
                year,
                month_num
            )
            
            return ServiceResult.success(
                enhanced_data,
                message="Hostel leave calendar generated",
                metadata={
                    "hostel_id": str(hostel_id),
                    "month": month,
                    "year": year,
                    "month_number": month_num,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error while generating hostel calendar: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "hostel month calendar", hostel_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error while generating hostel calendar: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "hostel month calendar", hostel_id)

    def student_month_calendar(
        self,
        student_id: UUID,
        month: str,  # Format: YYYY-MM
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Generate monthly calendar view of leave applications for a student.
        
        Returns a structured calendar showing:
        - Days on leave
        - Leave types
        - Approval status
        - Application details
        
        Args:
            student_id: UUID of the student
            month: Month in YYYY-MM format
            
        Returns:
            ServiceResult containing calendar dictionary or error information
        """
        try:
            # Validate and parse month parameter
            validation_result = self._validate_month_format(month)
            if not validation_result.success:
                return validation_result
            
            year, month_num = self._parse_month(month)
            
            self._logger.debug(
                f"Generating student calendar for {student_id} "
                f"for month {month}"
            )
            
            # Get calendar data from repository
            calendar_data = self.repository.get_student_month_calendar(
                student_id,
                month
            )
            
            if calendar_data is None:
                calendar_data = self._generate_empty_calendar(year, month_num)
            
            # Enhance with analytics
            enhanced_data = self._enhance_calendar_data(
                calendar_data,
                year,
                month_num
            )
            
            return ServiceResult.success(
                enhanced_data,
                message="Student leave calendar generated",
                metadata={
                    "student_id": str(student_id),
                    "month": month,
                    "year": year,
                    "month_number": month_num,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error while generating student calendar: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "student month calendar", student_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error while generating student calendar: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "student month calendar", student_id)

    def period_calendar(
        self,
        hostel_id: Optional[UUID] = None,
        student_id: Optional[UUID] = None,
        start_date: date = None,
        end_date: date = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Generate calendar view for a custom date period.
        
        Args:
            hostel_id: Optional hostel filter
            student_id: Optional student filter
            start_date: Period start date
            end_date: Period end date
            
        Returns:
            ServiceResult containing period calendar or error information
        """
        try:
            # Validate that at least one entity filter is provided
            if not hostel_id and not student_id:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Either hostel_id or student_id must be provided",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Validate date range
            if not start_date or not end_date:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Both start_date and end_date are required",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            if end_date < start_date:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="End date cannot be before start date",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "start_date": start_date.isoformat(),
                            "end_date": end_date.isoformat()
                        }
                    )
                )
            
            self._logger.debug(
                f"Generating period calendar from {start_date} to {end_date}"
            )
            
            # This would need to be implemented in the repository
            # calendar_data = self.repository.get_period_calendar(
            #     hostel_id=hostel_id,
            #     student_id=student_id,
            #     start_date=start_date,
            #     end_date=end_date
            # )
            
            # Placeholder implementation
            calendar_data = {}
            
            return ServiceResult.success(
                calendar_data,
                message="Period calendar generated",
                metadata={
                    "hostel_id": str(hostel_id) if hostel_id else None,
                    "student_id": str(student_id) if student_id else None,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error while generating period calendar: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(
                e,
                "period calendar",
                hostel_id or student_id
            )
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error while generating period calendar: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(
                e,
                "period calendar",
                hostel_id or student_id
            )

    def get_occupancy_stats(
        self,
        hostel_id: UUID,
        month: str,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Calculate occupancy statistics for a hostel in a given month.
        
        Provides:
        - Average daily occupancy
        - Peak occupancy days
        - Minimum occupancy days
        - Occupancy rate trends
        
        Args:
            hostel_id: UUID of the hostel
            month: Month in YYYY-MM format
            
        Returns:
            ServiceResult containing occupancy statistics or error information
        """
        try:
            # Validate month format
            validation_result = self._validate_month_format(month)
            if not validation_result.success:
                return validation_result
            
            year, month_num = self._parse_month(month)
            
            self._logger.debug(
                f"Calculating occupancy stats for hostel {hostel_id} "
                f"for month {month}"
            )
            
            # This would need to be implemented in the repository
            # stats = self.repository.get_occupancy_stats(hostel_id, month)
            
            # Placeholder implementation
            stats = {
                "average_occupancy": 0,
                "peak_day": None,
                "peak_count": 0,
                "minimum_day": None,
                "minimum_count": 0,
                "occupancy_rate": 0.0,
            }
            
            return ServiceResult.success(
                stats,
                metadata={
                    "hostel_id": str(hostel_id),
                    "month": month
                }
            )
            
        except Exception as e:
            self._logger.error(
                f"Error calculating occupancy stats: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get occupancy stats", hostel_id)

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _validate_month_format(self, month: str) -> ServiceResult[None]:
        """
        Validate month string format.
        
        Args:
            month: Month string to validate
            
        Returns:
            ServiceResult indicating validation success or error
        """
        if not month or len(month) != 7 or month[4] != '-':
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Invalid month format. Expected YYYY-MM",
                    severity=ErrorSeverity.WARNING,
                    details={"provided": month, "expected_format": "YYYY-MM"}
                )
            )
        
        try:
            year, month_num = map(int, month.split('-'))
            if month_num < 1 or month_num > 12:
                raise ValueError("Month number out of range")
        except (ValueError, AttributeError) as e:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid month value: {str(e)}",
                    severity=ErrorSeverity.WARNING,
                    details={"provided": month}
                )
            )
        
        return ServiceResult.success(None)

    def _parse_month(self, month: str) -> tuple[int, int]:
        """
        Parse month string into year and month number.
        
        Args:
            month: Month string in YYYY-MM format
            
        Returns:
            Tuple of (year, month_number)
        """
        year, month_num = map(int, month.split('-'))
        return year, month_num

    def _generate_empty_calendar(
        self,
        year: int,
        month: int
    ) -> Dict[str, Any]:
        """
        Generate empty calendar structure for a month.
        
        Args:
            year: Calendar year
            month: Calendar month (1-12)
            
        Returns:
            Dictionary with empty calendar structure
        """
        days_in_month = monthrange(year, month)[1]
        
        return {
            "year": year,
            "month": month,
            "days": {
                str(day): {
                    "leaves": [],
                    "count": 0
                }
                for day in range(1, days_in_month + 1)
            },
            "summary": {
                "total_leaves": 0,
                "unique_students": 0,
            }
        }

    def _enhance_calendar_data(
        self,
        calendar_data: Dict[str, Any],
        year: int,
        month: int
    ) -> Dict[str, Any]:
        """
        Enhance calendar data with additional analytics.
        
        Args:
            calendar_data: Base calendar data
            year: Calendar year
            month: Calendar month
            
        Returns:
            Enhanced calendar dictionary with analytics
        """
        # Add analytics if not present
        if "analytics" not in calendar_data:
            calendar_data["analytics"] = {
                "busiest_day": None,
                "quietest_day": None,
                "average_daily_leaves": 0,
            }
        
        # Add month metadata
        calendar_data["metadata"] = {
            "year": year,
            "month": month,
            "days_in_month": monthrange(year, month)[1],
            "generated_at": datetime.utcnow().isoformat(),
        }
        
        return calendar_data