"""
Supervisor Scheduling Service

Provides high-level operations around daily schedules for supervisors with calendar integration.
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories.supervisor import SupervisorDashboardRepository
from app.schemas.supervisor import TodaySchedule
from app.core1.exceptions import ValidationException

logger = logging.getLogger(__name__)


class SupervisorSchedulingService:
    """
    Orchestrates schedule-related views for supervisors.

    Currently reuses SupervisorDashboardRepository for building 'TodaySchedule'.

    Responsibilities:
    - Get daily/weekly schedules
    - Manage schedule updates
    - Handle schedule conflicts
    - Generate schedule reports

    Example:
        >>> service = SupervisorSchedulingService(dashboard_repo)
        >>> schedule = service.get_today_schedule(db, supervisor_id, hostel_id)
        >>> weekly = service.get_weekly_schedule(db, supervisor_id, hostel_id)
    """

    def __init__(
        self,
        dashboard_repo: SupervisorDashboardRepository,
    ) -> None:
        """
        Initialize the supervisor scheduling service.

        Args:
            dashboard_repo: Repository for dashboard/schedule operations
        """
        if not dashboard_repo:
            raise ValueError("dashboard_repo cannot be None")
            
        self.dashboard_repo = dashboard_repo

    # -------------------------------------------------------------------------
    # Schedule Retrieval
    # -------------------------------------------------------------------------

    def get_today_schedule(
        self,
        db: Session,
        supervisor_id: UUID,
        hostel_id: UUID,
        schedule_date: Optional[date] = None,
    ) -> TodaySchedule:
        """
        Get today's (or a specific date's) schedule for a supervisor.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            hostel_id: UUID of the hostel
            schedule_date: Optional specific date (defaults to today)

        Returns:
            TodaySchedule: Schedule data for the specified date

        Raises:
            ValidationException: If validation fails or no schedule available

        Example:
            >>> schedule = service.get_today_schedule(
            ...     db, supervisor_id, hostel_id,
            ...     schedule_date=datetime(2024, 1, 15).date()
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")
        
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        try:
            target_date = schedule_date or date.today()
            
            logger.info(
                f"Getting schedule for supervisor: {supervisor_id}, "
                f"hostel: {hostel_id}, date: {target_date}"
            )
            
            data = self.dashboard_repo.get_today_schedule(
                db=db,
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                schedule_date=target_date,
            )
            
            if data is None:
                logger.warning(
                    f"No schedule data available for supervisor: {supervisor_id}, "
                    f"hostel: {hostel_id}, date: {target_date}"
                )
                raise ValidationException(
                    f"No schedule data available for supervisor {supervisor_id} "
                    f"in hostel {hostel_id} on {target_date}"
                )
            
            # Provide default empty schedule if repo returns empty dict
            if not data:
                logger.info(
                    f"Empty schedule for supervisor: {supervisor_id}, "
                    f"date: {target_date}"
                )
                data = {
                    "supervisor_id": str(supervisor_id),
                    "hostel_id": str(hostel_id),
                    "schedule_date": target_date.isoformat(),
                    "tasks": [],
                    "meetings": [],
                    "inspections": [],
                }
            
            logger.info(
                f"Successfully retrieved schedule for supervisor: {supervisor_id}"
            )
            return TodaySchedule.model_validate(data)
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get schedule for supervisor {supervisor_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to retrieve schedule: {str(e)}")

    def get_weekly_schedule(
        self,
        db: Session,
        supervisor_id: UUID,
        hostel_id: UUID,
        start_date: Optional[date] = None,
    ) -> List[TodaySchedule]:
        """
        Get weekly schedule (7 days) for a supervisor.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            hostel_id: UUID of the hostel
            start_date: Optional start date (defaults to today)

        Returns:
            List[TodaySchedule]: List of 7 daily schedules

        Raises:
            ValidationException: If validation fails

        Example:
            >>> weekly = service.get_weekly_schedule(
            ...     db, supervisor_id, hostel_id,
            ...     start_date=datetime(2024, 1, 15).date()
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")
        
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        try:
            base_date = start_date or date.today()
            
            logger.info(
                f"Getting weekly schedule for supervisor: {supervisor_id}, "
                f"starting: {base_date}"
            )
            
            weekly_schedules = []
            for day_offset in range(7):
                current_date = base_date + timedelta(days=day_offset)
                
                try:
                    day_schedule = self.get_today_schedule(
                        db=db,
                        supervisor_id=supervisor_id,
                        hostel_id=hostel_id,
                        schedule_date=current_date,
                    )
                    weekly_schedules.append(day_schedule)
                except ValidationException:
                    # If no schedule for a day, add empty schedule
                    empty_schedule = TodaySchedule(
                        supervisor_id=supervisor_id,
                        hostel_id=hostel_id,
                        schedule_date=current_date,
                        tasks=[],
                        meetings=[],
                        inspections=[],
                    )
                    weekly_schedules.append(empty_schedule)
            
            logger.info(
                f"Successfully retrieved weekly schedule for supervisor: {supervisor_id}"
            )
            return weekly_schedules
            
        except Exception as e:
            logger.error(
                f"Failed to get weekly schedule for supervisor {supervisor_id}: {str(e)}"
            )
            raise ValidationException(f"Failed to retrieve weekly schedule: {str(e)}")

    def get_monthly_schedule_summary(
        self,
        db: Session,
        supervisor_id: UUID,
        hostel_id: UUID,
        year: int,
        month: int,
    ) -> Dict[str, Any]:
        """
        Get monthly schedule summary.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            hostel_id: UUID of the hostel
            year: Year for the summary
            month: Month for the summary (1-12)

        Returns:
            Dict[str, Any]: Monthly schedule summary with statistics

        Raises:
            ValidationException: If validation fails

        Example:
            >>> summary = service.get_monthly_schedule_summary(
            ...     db, supervisor_id, hostel_id, year=2024, month=1
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id or not hostel_id:
            raise ValidationException("Supervisor ID and Hostel ID are required")
        
        if month < 1 or month > 12:
            raise ValidationException("Month must be between 1 and 12")
        
        if year < 2000 or year > 2100:
            raise ValidationException("Invalid year")

        try:
            logger.info(
                f"Getting monthly schedule summary for supervisor: {supervisor_id}, "
                f"period: {year}-{month:02d}"
            )
            
            summary = self.dashboard_repo.get_monthly_schedule_summary(
                db=db,
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                year=year,
                month=month,
            )
            
            return summary or {
                "supervisor_id": str(supervisor_id),
                "hostel_id": str(hostel_id),
                "year": year,
                "month": month,
                "total_tasks": 0,
                "total_meetings": 0,
                "total_inspections": 0,
            }
            
        except Exception as e:
            logger.error(f"Failed to get monthly schedule summary: {str(e)}")
            raise ValidationException(
                f"Failed to retrieve monthly schedule summary: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Schedule Management
    # -------------------------------------------------------------------------

    def add_schedule_item(
        self,
        db: Session,
        supervisor_id: UUID,
        hostel_id: UUID,
        item_type: str,
        item_data: Dict[str, Any],
        schedule_date: date,
    ) -> Dict[str, Any]:
        """
        Add a new item to supervisor's schedule.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            hostel_id: UUID of the hostel
            item_type: Type of item ("task", "meeting", "inspection")
            item_data: Data for the schedule item
            schedule_date: Date for the schedule item

        Returns:
            Dict[str, Any]: Created schedule item

        Raises:
            ValidationException: If validation fails

        Example:
            >>> item = service.add_schedule_item(
            ...     db, supervisor_id, hostel_id,
            ...     item_type="task",
            ...     item_data={"title": "Room inspection", "priority": "high"},
            ...     schedule_date=datetime(2024, 1, 15).date()
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id or not hostel_id:
            raise ValidationException("Supervisor ID and Hostel ID are required")
        
        if item_type not in ["task", "meeting", "inspection"]:
            raise ValidationException(
                "item_type must be one of: task, meeting, inspection"
            )
        
        if not item_data:
            raise ValidationException("Item data is required")

        try:
            logger.info(
                f"Adding schedule item for supervisor: {supervisor_id}, "
                f"type: {item_type}, date: {schedule_date}"
            )
            
            item_data["supervisor_id"] = str(supervisor_id)
            item_data["hostel_id"] = str(hostel_id)
            item_data["schedule_date"] = schedule_date.isoformat()
            item_data["item_type"] = item_type
            
            created_item = self.dashboard_repo.create_schedule_item(
                db=db,
                item_data=item_data,
            )
            
            logger.info(
                f"Successfully added schedule item for supervisor: {supervisor_id}"
            )
            return created_item
            
        except Exception as e:
            logger.error(f"Failed to add schedule item: {str(e)}")
            raise ValidationException(f"Failed to add schedule item: {str(e)}")

    def update_schedule_item(
        self,
        db: Session,
        item_id: UUID,
        update_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update an existing schedule item.

        Args:
            db: Database session
            item_id: UUID of the schedule item
            update_data: Data to update

        Returns:
            Dict[str, Any]: Updated schedule item

        Raises:
            ValidationException: If validation fails or item not found

        Example:
            >>> updated = service.update_schedule_item(
            ...     db, item_id, {"status": "completed"}
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not item_id:
            raise ValidationException("Item ID is required")
        
        if not update_data:
            raise ValidationException("Update data is required")

        try:
            logger.info(f"Updating schedule item: {item_id}")
            
            updated_item = self.dashboard_repo.update_schedule_item(
                db=db,
                item_id=item_id,
                update_data=update_data,
            )
            
            if not updated_item:
                raise ValidationException(
                    f"Schedule item not found with ID: {item_id}"
                )
            
            logger.info(f"Successfully updated schedule item: {item_id}")
            return updated_item
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Failed to update schedule item {item_id}: {str(e)}")
            raise ValidationException(f"Failed to update schedule item: {str(e)}")

    def delete_schedule_item(
        self,
        db: Session,
        item_id: UUID,
    ) -> bool:
        """
        Delete a schedule item.

        Args:
            db: Database session
            item_id: UUID of the schedule item

        Returns:
            bool: True if deleted successfully

        Raises:
            ValidationException: If validation fails

        Example:
            >>> deleted = service.delete_schedule_item(db, item_id)
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not item_id:
            raise ValidationException("Item ID is required")

        try:
            logger.info(f"Deleting schedule item: {item_id}")
            
            success = self.dashboard_repo.delete_schedule_item(
                db=db,
                item_id=item_id,
            )
            
            if success:
                logger.info(f"Successfully deleted schedule item: {item_id}")
            else:
                logger.warning(f"Schedule item not found: {item_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete schedule item {item_id}: {str(e)}")
            raise ValidationException(f"Failed to delete schedule item: {str(e)}")

    # -------------------------------------------------------------------------
    # Conflict Detection
    # -------------------------------------------------------------------------

    def check_schedule_conflicts(
        self,
        db: Session,
        supervisor_id: UUID,
        hostel_id: UUID,
        schedule_date: date,
        start_time: str,
        end_time: str,
    ) -> List[Dict[str, Any]]:
        """
        Check for schedule conflicts on a specific date and time range.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            hostel_id: UUID of the hostel
            schedule_date: Date to check
            start_time: Start time (HH:MM format)
            end_time: End time (HH:MM format)

        Returns:
            List[Dict[str, Any]]: List of conflicting schedule items

        Example:
            >>> conflicts = service.check_schedule_conflicts(
            ...     db, supervisor_id, hostel_id,
            ...     schedule_date=date.today(),
            ...     start_time="09:00",
            ...     end_time="10:00"
            ... )
        """
        if not db or not supervisor_id or not hostel_id:
            return []
        
        try:
            logger.debug(
                f"Checking schedule conflicts for supervisor: {supervisor_id}, "
                f"date: {schedule_date}, time: {start_time}-{end_time}"
            )
            
            conflicts = self.dashboard_repo.find_schedule_conflicts(
                db=db,
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                schedule_date=schedule_date,
                start_time=start_time,
                end_time=end_time,
            )
            
            if conflicts:
                logger.warning(
                    f"Found {len(conflicts)} schedule conflicts for: {supervisor_id}"
                )
            
            return conflicts or []
            
        except Exception as e:
            logger.error(f"Failed to check schedule conflicts: {str(e)}")
            return []