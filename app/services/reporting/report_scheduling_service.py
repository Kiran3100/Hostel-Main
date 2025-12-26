# app/services/reporting/report_scheduling_service.py
"""
Report Scheduling Service

Manages scheduled execution of custom reports with enhanced
validation, error handling, and monitoring.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.analytics import (
    ReportSchedule,
    ReportExecutionHistory,
)
from app.repositories.analytics import CustomReportsRepository
from app.core.exceptions import (
    ValidationException,
    NotFoundException,
    AuthorizationException,
)
from app.utils.metrics import track_performance

logger = logging.getLogger(__name__)


class ReportSchedulingService:
    """
    High-level service for scheduling & executing custom reports.

    Responsibilities:
    - Create/update/delete schedules with validation
    - List and manage schedules
    - Process due schedules (for cron/worker)
    - Handle schedule conflicts and errors
    - Track execution history

    Attributes:
        custom_reports_repo: Repository for custom reports
        max_concurrent_schedules: Max schedules per user
        max_execution_retries: Max retry attempts for failed executions
    """

    def __init__(
        self,
        custom_reports_repo: CustomReportsRepository,
        max_concurrent_schedules: int = 50,
        max_execution_retries: int = 3,
    ) -> None:
        """
        Initialize the report scheduling service.

        Args:
            custom_reports_repo: Repository for custom reports
            max_concurrent_schedules: Maximum schedules per user
            max_execution_retries: Maximum retry attempts
        """
        if not custom_reports_repo:
            raise ValueError("CustomReportsRepository cannot be None")
        
        self.custom_reports_repo = custom_reports_repo
        self.max_concurrent_schedules = max_concurrent_schedules
        self.max_execution_retries = max_execution_retries
        
        logger.info(
            f"ReportSchedulingService initialized with "
            f"max_schedules={max_concurrent_schedules}, "
            f"max_retries={max_execution_retries}"
        )

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def _validate_schedule(self, schedule: ReportSchedule) -> None:
        """
        Validate schedule configuration.

        Args:
            schedule: Schedule to validate

        Raises:
            ValidationException: If validation fails
        """
        if not schedule.name or not schedule.name.strip():
            raise ValidationException("Schedule name is required")
        
        if len(schedule.name) > 255:
            raise ValidationException("Schedule name cannot exceed 255 characters")
        
        if not schedule.frequency:
            raise ValidationException("Schedule frequency is required")
        
        valid_frequencies = ["hourly", "daily", "weekly", "monthly"]
        if schedule.frequency not in valid_frequencies:
            raise ValidationException(
                f"Invalid frequency. Must be one of: {', '.join(valid_frequencies)}"
            )
        
        # Validate time configurations based on frequency
        if schedule.frequency == "daily" and not schedule.time_of_day:
            raise ValidationException("time_of_day is required for daily schedules")
        
        if schedule.frequency == "weekly" and not schedule.day_of_week:
            raise ValidationException("day_of_week is required for weekly schedules")
        
        if schedule.frequency == "monthly" and not schedule.day_of_month:
            raise ValidationException("day_of_month is required for monthly schedules")
        
        # Validate day_of_week
        if schedule.day_of_week is not None:
            if not 0 <= schedule.day_of_week <= 6:
                raise ValidationException("day_of_week must be between 0 (Monday) and 6 (Sunday)")
        
        # Validate day_of_month
        if schedule.day_of_month is not None:
            if not 1 <= schedule.day_of_month <= 31:
                raise ValidationException("day_of_month must be between 1 and 31")

    # -------------------------------------------------------------------------
    # Schedule CRUD
    # -------------------------------------------------------------------------

    @track_performance("create_schedule")
    def create_schedule(
        self,
        db: Session,
        definition_id: UUID,
        schedule: ReportSchedule,
        owner_id: UUID,
    ) -> ReportSchedule:
        """
        Create a new report schedule with validation.

        Args:
            db: Database session
            definition_id: ID of report definition to schedule
            schedule: Schedule configuration
            owner_id: Owner ID

        Returns:
            ReportSchedule: Created schedule

        Raises:
            ValidationException: If validation fails
            NotFoundException: If definition not found
        """
        logger.info(
            f"Creating schedule '{schedule.name}' for definition {definition_id}"
        )
        
        try:
            # Validate schedule
            self._validate_schedule(schedule)
            
            # Check if definition exists
            definition = self.custom_reports_repo.get_definition_by_id(db, definition_id)
            if not definition:
                raise NotFoundException(f"Report definition {definition_id} not found")
            
            # Check authorization
            if definition.owner_id != owner_id:
                raise AuthorizationException(
                    "Not authorized to create schedule for this report"
                )
            
            # Check concurrent schedule limit
            existing_schedules = self.custom_reports_repo.get_schedules_for_owner(
                db, owner_id
            )
            if len(existing_schedules) >= self.max_concurrent_schedules:
                raise ValidationException(
                    f"Maximum concurrent schedules ({self.max_concurrent_schedules}) reached"
                )
            
            # Calculate next run time
            next_run = self._calculate_next_run(schedule, datetime.utcnow())
            
            # Prepare payload
            payload = schedule.model_dump(exclude_none=True)
            payload.update({
                "definition_id": definition_id,
                "owner_id": owner_id,
                "next_run": next_run,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            })
            
            # Create schedule
            obj = self.custom_reports_repo.create_schedule(db, payload)
            
            logger.info(
                f"Successfully created schedule {obj.id} for definition {definition_id}"
            )
            
            return ReportSchedule.model_validate(obj)
            
        except (ValidationException, NotFoundException, AuthorizationException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error creating schedule: {str(e)}")
            db.rollback()
            raise ValidationException(f"Failed to create schedule: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error creating schedule: {str(e)}")
            db.rollback()
            raise

    @track_performance("update_schedule")
    def update_schedule(
        self,
        db: Session,
        schedule_id: UUID,
        schedule: ReportSchedule,
        owner_id: Optional[UUID] = None,
    ) -> ReportSchedule:
        """
        Update an existing report schedule.

        Args:
            db: Database session
            schedule_id: ID of schedule to update
            schedule: Updated schedule configuration
            owner_id: Optional owner ID for authorization

        Returns:
            ReportSchedule: Updated schedule

        Raises:
            ValidationException: If validation fails
            NotFoundException: If schedule not found
            AuthorizationException: If not authorized
        """
        logger.info(f"Updating schedule {schedule_id}")
        
        try:
            # Fetch existing schedule
            existing = self.custom_reports_repo.get_schedule_by_id(db, schedule_id)
            if not existing:
                raise NotFoundException(f"Schedule {schedule_id} not found")
            
            # Check authorization
            if owner_id and existing.owner_id != owner_id:
                raise AuthorizationException(
                    "Not authorized to update this schedule"
                )
            
            # Validate schedule
            self._validate_schedule(schedule)
            
            # Calculate new next_run if frequency changed
            update_data = schedule.model_dump(exclude_none=True)
            if (
                schedule.frequency != existing.frequency
                or schedule.time_of_day != existing.time_of_day
                or schedule.day_of_week != existing.day_of_week
                or schedule.day_of_month != existing.day_of_month
            ):
                next_run = self._calculate_next_run(schedule, datetime.utcnow())
                update_data["next_run"] = next_run
            
            update_data["updated_at"] = datetime.utcnow()
            
            # Update schedule
            updated = self.custom_reports_repo.update_schedule(
                db, existing, update_data
            )
            
            logger.info(f"Successfully updated schedule {schedule_id}")
            
            return ReportSchedule.model_validate(updated)
            
        except (ValidationException, NotFoundException, AuthorizationException):
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error updating schedule: {str(e)}")
            db.rollback()
            raise ValidationException(f"Failed to update schedule: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error updating schedule: {str(e)}")
            db.rollback()
            raise

    @track_performance("delete_schedule")
    def delete_schedule(
        self,
        db: Session,
        schedule_id: UUID,
        owner_id: Optional[UUID] = None,
    ) -> None:
        """
        Delete a report schedule.

        Args:
            db: Database session
            schedule_id: ID of schedule to delete
            owner_id: Optional owner ID for authorization

        Raises:
            NotFoundException: If schedule not found
            AuthorizationException: If not authorized
        """
        logger.info(f"Deleting schedule {schedule_id}")
        
        try:
            existing = self.custom_reports_repo.get_schedule_by_id(db, schedule_id)
            
            if not existing:
                logger.warning(f"Schedule {schedule_id} not found")
                return
            
            # Check authorization
            if owner_id and existing.owner_id != owner_id:
                raise AuthorizationException(
                    "Not authorized to delete this schedule"
                )
            
            self.custom_reports_repo.delete_schedule(db, existing)
            
            logger.info(f"Successfully deleted schedule {schedule_id}")
            
        except AuthorizationException:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error deleting schedule: {str(e)}")
            db.rollback()
            raise ValidationException(f"Failed to delete schedule: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error deleting schedule: {str(e)}")
            db.rollback()
            raise

    def list_schedules_for_definition(
        self,
        db: Session,
        definition_id: UUID,
        owner_id: Optional[UUID] = None,
    ) -> List[ReportSchedule]:
        """
        List all schedules for a report definition.

        Args:
            db: Database session
            definition_id: Report definition ID
            owner_id: Optional owner ID for filtering

        Returns:
            List of ReportSchedule objects
        """
        logger.info(f"Listing schedules for definition {definition_id}")
        
        try:
            objs = self.custom_reports_repo.get_schedules_for_definition(
                db, definition_id
            )
            
            # Filter by owner if provided
            if owner_id:
                objs = [obj for obj in objs if obj.owner_id == owner_id]
            
            schedules = [ReportSchedule.model_validate(o) for o in objs]
            
            logger.info(f"Found {len(schedules)} schedules")
            
            return schedules
            
        except Exception as e:
            logger.error(f"Error listing schedules: {str(e)}")
            raise ValidationException(f"Failed to list schedules: {str(e)}")

    # -------------------------------------------------------------------------
    # Execution
    # -------------------------------------------------------------------------

    @track_performance("run_due_schedules")
    def run_due_schedules(
        self,
        db: Session,
        now: Optional[datetime] = None,
        max_schedules: Optional[int] = None,
    ) -> List[ReportExecutionHistory]:
        """
        Execute all schedules that are due as of `now`.

        This method is typically called by a cron job or background worker.

        Args:
            db: Database session
            now: Current datetime (defaults to utcnow)
            max_schedules: Maximum number of schedules to process

        Returns:
            List of ReportExecutionHistory records created
        """
        now = now or datetime.utcnow()
        
        logger.info(f"Processing due schedules as of {now}")
        
        try:
            # Fetch due schedules
            due_schedules = self.custom_reports_repo.get_due_schedules(db, now)
            
            if max_schedules:
                due_schedules = due_schedules[:max_schedules]
            
            logger.info(f"Found {len(due_schedules)} due schedules")
            
            histories: List[ReportExecutionHistory] = []
            
            for schedule in due_schedules:
                try:
                    # Execute scheduled report
                    history_obj = self.custom_reports_repo.execute_scheduled_report(
                        db=db,
                        schedule=schedule,
                        run_at=now,
                    )
                    
                    if history_obj:
                        histories.append(
                            ReportExecutionHistory.model_validate(history_obj)
                        )
                    
                    # Update schedule with next run time
                    self._update_schedule_next_run(db, schedule, now)
                    
                    logger.info(
                        f"Successfully executed schedule {schedule.id}"
                    )
                    
                except Exception as e:
                    logger.error(
                        f"Error executing schedule {schedule.id}: {str(e)}",
                        exc_info=True
                    )
                    
                    # Record failure in execution history
                    self._record_execution_failure(db, schedule, now, str(e))
            
            # Commit all changes
            db.commit()
            
            logger.info(
                f"Processed {len(due_schedules)} schedules, "
                f"{len(histories)} successful executions"
            )
            
            return histories
            
        except SQLAlchemyError as e:
            logger.error(f"Database error processing schedules: {str(e)}")
            db.rollback()
            raise ValidationException(f"Failed to process schedules: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error processing schedules: {str(e)}")
            db.rollback()
            raise

    def _update_schedule_next_run(
        self,
        db: Session,
        schedule: Any,
        current_run: datetime,
    ) -> None:
        """
        Update schedule with next run time.

        Args:
            db: Database session
            schedule: Schedule object
            current_run: Current execution time
        """
        try:
            # Calculate next run based on schedule configuration
            schedule_schema = ReportSchedule.model_validate(schedule)
            next_run = self._calculate_next_run(schedule_schema, current_run)
            
            self.custom_reports_repo.update_next_run(db, schedule, next_run)
            
        except Exception as e:
            logger.error(f"Error updating next run time: {str(e)}")

    def _record_execution_failure(
        self,
        db: Session,
        schedule: Any,
        run_at: datetime,
        error_message: str,
    ) -> None:
        """
        Record a failed execution in history.

        Args:
            db: Database session
            schedule: Schedule object
            run_at: Execution time
            error_message: Error message
        """
        try:
            self.custom_reports_repo.record_execution_failure(
                db=db,
                schedule=schedule,
                run_at=run_at,
                error_message=error_message,
            )
        except Exception as e:
            logger.error(f"Error recording execution failure: {str(e)}")

    def _calculate_next_run(
        self,
        schedule: ReportSchedule,
        from_time: datetime,
    ) -> datetime:
        """
        Calculate next run time based on schedule configuration.

        Args:
            schedule: Schedule configuration
            from_time: Starting time for calculation

        Returns:
            Next run datetime
        """
        if schedule.frequency == "hourly":
            return from_time + timedelta(hours=1)
        
        elif schedule.frequency == "daily":
            # Schedule for next day at specified time
            next_day = from_time.date() + timedelta(days=1)
            time_parts = schedule.time_of_day.split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            
            return datetime.combine(next_day, datetime.min.time()).replace(
                hour=hour, minute=minute
            )
        
        elif schedule.frequency == "weekly":
            # Schedule for next occurrence of specified day
            days_ahead = schedule.day_of_week - from_time.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            
            next_date = from_time.date() + timedelta(days=days_ahead)
            
            time_parts = schedule.time_of_day.split(":") if schedule.time_of_day else ["0", "0"]
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            
            return datetime.combine(next_date, datetime.min.time()).replace(
                hour=hour, minute=minute
            )
        
        elif schedule.frequency == "monthly":
            # Schedule for next month on specified day
            next_month = from_time.month + 1
            next_year = from_time.year
            
            if next_month > 12:
                next_month = 1
                next_year += 1
            
            # Handle invalid days (e.g., Feb 31)
            import calendar
            max_day = calendar.monthrange(next_year, next_month)[1]
            day = min(schedule.day_of_month, max_day)
            
            next_date = datetime(next_year, next_month, day)
            
            time_parts = schedule.time_of_day.split(":") if schedule.time_of_day else ["0", "0"]
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            
            return next_date.replace(hour=hour, minute=minute)
        
        else:
            # Default to 1 day
            return from_time + timedelta(days=1)

    def get_execution_history(
        self,
        db: Session,
        schedule_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ReportExecutionHistory]:
        """
        Get execution history for a schedule.

        Args:
            db: Database session
            schedule_id: Schedule ID
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List of ReportExecutionHistory records
        """
        logger.info(f"Fetching execution history for schedule {schedule_id}")
        
        try:
            objs = self.custom_reports_repo.get_execution_history(
                db=db,
                schedule_id=schedule_id,
                limit=limit,
                offset=offset,
            )
            
            history = [ReportExecutionHistory.model_validate(o) for o in objs]
            
            logger.info(f"Found {len(history)} execution history records")
            
            return history
            
        except Exception as e:
            logger.error(f"Error fetching execution history: {str(e)}")
            raise ValidationException(f"Failed to fetch execution history: {str(e)}")