"""
Maintenance Schedule Service

Manages preventive maintenance schedules with intelligent scheduling,
execution tracking, and performance analytics.

Features:
- Flexible scheduling (daily, weekly, monthly, quarterly, yearly)
- Schedule execution tracking and history
- Automated schedule generation
- Performance metrics and compliance tracking
- Due date calculations and reminders
- Execution checklist management
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceScheduleRepository
from app.schemas.maintenance import (
    PreventiveSchedule,
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleExecution,
    ExecutionHistoryItem,
    ScheduleHistory,
)
from app.core1.exceptions import ValidationException, BusinessLogicException
from app.core1.logging import logger


class MaintenanceScheduleService:
    """
    High-level service for preventive maintenance scheduling.

    Provides intelligent scheduling capabilities to reduce reactive
    maintenance and extend asset lifespan.
    """

    # Valid frequency options
    VALID_FREQUENCIES = {
        "daily",
        "weekly",
        "biweekly",
        "monthly",
        "quarterly",
        "semiannual",
        "annual",
    }

    # Days in advance to send reminders
    REMINDER_DAYS = {
        "daily": 1,
        "weekly": 2,
        "biweekly": 3,
        "monthly": 7,
        "quarterly": 14,
        "semiannual": 21,
        "annual": 30,
    }

    def __init__(self, schedule_repo: MaintenanceScheduleRepository) -> None:
        """
        Initialize the schedule service.

        Args:
            schedule_repo: Repository for schedule persistence
        """
        if not schedule_repo:
            raise ValueError("MaintenanceScheduleRepository is required")
        self.schedule_repo = schedule_repo

    # -------------------------------------------------------------------------
    # Schedule Management Operations
    # -------------------------------------------------------------------------

    def create_schedule(
        self,
        db: Session,
        request: ScheduleCreate,
    ) -> PreventiveSchedule:
        """
        Create a new preventive maintenance schedule.

        Automatically calculates next due date based on frequency.

        Args:
            db: Database session
            request: Schedule creation details

        Returns:
            Created PreventiveSchedule

        Raises:
            ValidationException: If schedule data is invalid
            BusinessLogicException: If scheduling conflicts exist
        """
        # Validate schedule data
        self._validate_schedule_create(request)

        try:
            logger.info(
                f"Creating preventive schedule for {request.asset_type} "
                f"in hostel {request.hostel_id}"
            )

            payload = request.model_dump(exclude_none=True)

            # Calculate next due date if not provided
            if "next_due_date" not in payload or not payload["next_due_date"]:
                payload["next_due_date"] = self._calculate_next_due_date(
                    start_date=payload.get("start_date", datetime.utcnow()),
                    frequency=payload["frequency"],
                )

            # Calculate reminder date
            if "reminder_date" not in payload or not payload["reminder_date"]:
                payload["reminder_date"] = self._calculate_reminder_date(
                    due_date=payload["next_due_date"],
                    frequency=payload["frequency"],
                )

            obj = self.schedule_repo.create_schedule(db=db, data=payload)

            logger.info(
                f"Successfully created schedule {obj.id} - "
                f"next due: {obj.next_due_date}"
            )

            # TODO: Schedule reminder notification
            # await self._schedule_reminder_notification(obj)

            return PreventiveSchedule.model_validate(obj)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error creating schedule: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to create preventive schedule: {str(e)}"
            )

    def update_schedule(
        self,
        db: Session,
        schedule_id: UUID,
        request: ScheduleUpdate,
    ) -> PreventiveSchedule:
        """
        Update an existing preventive maintenance schedule.

        Args:
            db: Database session
            schedule_id: UUID of schedule to update
            request: Update data

        Returns:
            Updated PreventiveSchedule

        Raises:
            ValidationException: If schedule not found or update invalid
        """
        if not schedule_id:
            raise ValidationException("Schedule ID is required")

        # Validate update data
        self._validate_schedule_update(request)

        try:
            schedule = self.schedule_repo.get_by_id(db, schedule_id)
            if not schedule:
                raise ValidationException(
                    f"Schedule {schedule_id} not found"
                )

            logger.info(f"Updating schedule {schedule_id}")

            payload = request.model_dump(exclude_none=True)

            # Recalculate dates if frequency changed
            if "frequency" in payload and payload["frequency"] != schedule.frequency:
                payload["next_due_date"] = self._calculate_next_due_date(
                    start_date=schedule.last_completed_date or datetime.utcnow(),
                    frequency=payload["frequency"],
                )
                payload["reminder_date"] = self._calculate_reminder_date(
                    due_date=payload["next_due_date"],
                    frequency=payload["frequency"],
                )

            updated = self.schedule_repo.update_schedule(
                db=db,
                schedule=schedule,
                data=payload,
            )

            logger.info(f"Successfully updated schedule {schedule_id}")
            return PreventiveSchedule.model_validate(updated)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error updating schedule {schedule_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to update schedule: {str(e)}"
            )

    def get_schedule(
        self,
        db: Session,
        schedule_id: UUID,
    ) -> PreventiveSchedule:
        """
        Retrieve a specific preventive maintenance schedule.

        Args:
            db: Database session
            schedule_id: UUID of the schedule

        Returns:
            PreventiveSchedule details

        Raises:
            ValidationException: If schedule not found
        """
        if not schedule_id:
            raise ValidationException("Schedule ID is required")

        try:
            schedule = self.schedule_repo.get_by_id(db, schedule_id)
            if not schedule:
                raise ValidationException(
                    f"Schedule {schedule_id} not found"
                )
            
            return PreventiveSchedule.model_validate(schedule)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving schedule {schedule_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve schedule: {str(e)}"
            )

    def delete_schedule(
        self,
        db: Session,
        schedule_id: UUID,
        soft_delete: bool = True,
    ) -> bool:
        """
        Delete or deactivate a preventive maintenance schedule.

        Args:
            db: Database session
            schedule_id: UUID of schedule to delete
            soft_delete: If True, deactivate instead of hard delete

        Returns:
            True if successful

        Raises:
            ValidationException: If schedule not found
        """
        if not schedule_id:
            raise ValidationException("Schedule ID is required")

        try:
            schedule = self.schedule_repo.get_by_id(db, schedule_id)
            if not schedule:
                raise ValidationException(
                    f"Schedule {schedule_id} not found"
                )

            if soft_delete:
                # Deactivate instead of delete
                self.schedule_repo.update_schedule(
                    db=db,
                    schedule=schedule,
                    data={"is_active": False, "deactivated_at": datetime.utcnow()},
                )
                logger.info(f"Deactivated schedule {schedule_id}")
            else:
                # Hard delete
                self.schedule_repo.delete(db, schedule)
                logger.info(f"Deleted schedule {schedule_id}")

            return True

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error deleting schedule {schedule_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to delete schedule: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Schedule Listing and Filtering
    # -------------------------------------------------------------------------

    def list_schedules_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        active_only: bool = True,
        include_overdue: bool = False,
    ) -> List[PreventiveSchedule]:
        """
        List all preventive maintenance schedules for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            active_only: If True, return only active schedules
            include_overdue: If True, mark overdue schedules

        Returns:
            List of PreventiveSchedule records
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        try:
            objs = self.schedule_repo.get_by_hostel_id(
                db,
                hostel_id,
                active_only=active_only
            )
            
            schedules = [PreventiveSchedule.model_validate(o) for o in objs]

            # Mark overdue schedules if requested
            if include_overdue:
                now = datetime.utcnow()
                for schedule in schedules:
                    if schedule.next_due_date and schedule.next_due_date < now:
                        schedule.is_overdue = True

            logger.debug(
                f"Retrieved {len(schedules)} schedules for hostel {hostel_id}"
            )

            return schedules

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error listing schedules for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve schedules: {str(e)}"
            )

    def get_due_schedules(
        self,
        db: Session,
        hostel_id: UUID,
        days_ahead: int = 7,
    ) -> List[PreventiveSchedule]:
        """
        Get schedules that are due or will be due within specified days.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            days_ahead: Number of days to look ahead

        Returns:
            List of due or upcoming schedules
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        if days_ahead < 0:
            raise ValidationException("days_ahead must be non-negative")

        try:
            cutoff_date = datetime.utcnow() + timedelta(days=days_ahead)
            
            schedules = self.schedule_repo.get_due_schedules(
                db=db,
                hostel_id=hostel_id,
                before_date=cutoff_date,
            )

            results = [PreventiveSchedule.model_validate(s) for s in schedules]

            logger.info(
                f"Found {len(results)} schedules due within {days_ahead} days "
                f"for hostel {hostel_id}"
            )

            return results

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error getting due schedules: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve due schedules: {str(e)}"
            )

    def get_overdue_schedules(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> List[PreventiveSchedule]:
        """
        Get all overdue preventive maintenance schedules.

        Args:
            db: Database session
            hostel_id: UUID of the hostel

        Returns:
            List of overdue schedules
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        try:
            now = datetime.utcnow()
            schedules = self.schedule_repo.get_due_schedules(
                db=db,
                hostel_id=hostel_id,
                before_date=now,
                overdue_only=True,
            )

            results = [PreventiveSchedule.model_validate(s) for s in schedules]

            if results:
                logger.warning(
                    f"Found {len(results)} overdue schedules for hostel {hostel_id}"
                )

            return results

        except Exception as e:
            logger.error(
                f"Error getting overdue schedules: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve overdue schedules: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Execution Tracking Operations
    # -------------------------------------------------------------------------

    def record_execution(
        self,
        db: Session,
        request: ScheduleExecution,
    ) -> ExecutionHistoryItem:
        """
        Record execution of a preventive maintenance schedule.

        Updates the schedule's last completed date and calculates next due date.

        Args:
            db: Database session
            request: Execution details

        Returns:
            Created ExecutionHistoryItem

        Raises:
            ValidationException: If execution data is invalid
            BusinessLogicException: If schedule not found
        """
        # Validate execution data
        self._validate_schedule_execution(request)

        try:
            logger.info(
                f"Recording execution for schedule {request.schedule_id}"
            )

            # Retrieve schedule to update
            schedule = self.schedule_repo.get_by_id(db, request.schedule_id)
            if not schedule:
                raise BusinessLogicException(
                    f"Schedule {request.schedule_id} not found"
                )

            payload = request.model_dump(exclude_none=True)

            # Ensure execution timestamp
            if "executed_at" not in payload or not payload["executed_at"]:
                payload["executed_at"] = datetime.utcnow()

            # Record the execution
            obj = self.schedule_repo.record_execution(db, payload)

            # Update schedule's last completed date and calculate next due
            execution_date = payload["executed_at"]
            next_due = self._calculate_next_due_date(
                start_date=execution_date,
                frequency=schedule.frequency,
            )
            reminder_date = self._calculate_reminder_date(
                due_date=next_due,
                frequency=schedule.frequency,
            )

            self.schedule_repo.update_schedule(
                db=db,
                schedule=schedule,
                data={
                    "last_completed_date": execution_date,
                    "next_due_date": next_due,
                    "reminder_date": reminder_date,
                    "execution_count": (schedule.execution_count or 0) + 1,
                },
            )

            logger.info(
                f"Execution recorded for schedule {request.schedule_id}. "
                f"Next due: {next_due}"
            )

            # TODO: Update completion metrics
            # await self._update_schedule_metrics(schedule.id)

            return ExecutionHistoryItem.model_validate(obj)

        except ValidationException:
            raise
        except BusinessLogicException:
            raise
        except Exception as e:
            logger.error(
                f"Error recording execution: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to record schedule execution: {str(e)}"
            )

    def update_execution(
        self,
        db: Session,
        execution_id: UUID,
        updates: Dict[str, Any],
    ) -> ExecutionHistoryItem:
        """
        Update an execution record.

        Args:
            db: Database session
            execution_id: UUID of execution record
            updates: Fields to update

        Returns:
            Updated ExecutionHistoryItem
        """
        if not execution_id:
            raise ValidationException("Execution ID is required")

        try:
            execution = self.schedule_repo.get_execution_by_id(db, execution_id)
            if not execution:
                raise ValidationException(
                    f"Execution record {execution_id} not found"
                )

            updated = self.schedule_repo.update_execution(
                db=db,
                execution=execution,
                data=updates,
            )

            logger.info(f"Updated execution record {execution_id}")
            return ExecutionHistoryItem.model_validate(updated)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error updating execution: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to update execution record: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # History and Analytics
    # -------------------------------------------------------------------------

    def get_history_for_schedule(
        self,
        db: Session,
        schedule_id: UUID,
        limit: Optional[int] = None,
    ) -> ScheduleHistory:
        """
        Retrieve execution history for a schedule with analytics.

        Args:
            db: Database session
            schedule_id: UUID of the schedule
            limit: Optional limit on number of executions to return

        Returns:
            ScheduleHistory with executions and metrics
        """
        if not schedule_id:
            raise ValidationException("Schedule ID is required")

        try:
            data = self.schedule_repo.get_history_for_schedule(
                db,
                schedule_id,
                limit=limit
            )
            
            if not data:
                # Return empty history
                logger.debug(
                    f"No execution history found for schedule {schedule_id}"
                )
                return ScheduleHistory(
                    schedule_id=schedule_id,
                    executions=[],
                    total_executions=0,
                    average_completion_time_hours=None,
                    on_time_rate=None,
                    compliance_rate=None,
                )
            
            history = ScheduleHistory.model_validate(data)

            # Calculate additional metrics
            history = self._enrich_schedule_history(history)

            return history

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving schedule history: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve schedule history: {str(e)}"
            )

    def get_compliance_report(
        self,
        db: Session,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Generate compliance report for preventive maintenance schedules.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            start_date: Optional start date for report period
            end_date: Optional end date for report period

        Returns:
            Dictionary with compliance metrics
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        # Default to last 90 days if not specified
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=90)

        try:
            logger.info(
                f"Generating compliance report for hostel {hostel_id} "
                f"from {start_date} to {end_date}"
            )

            report = self.schedule_repo.get_compliance_report(
                db=db,
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
            )

            # Enrich with insights
            report["period_start"] = start_date.isoformat()
            report["period_end"] = end_date.isoformat()
            report["insights"] = self._generate_compliance_insights(report)

            logger.info(
                f"Compliance report generated: "
                f"{report.get('compliance_rate', 0):.1f}% compliance rate"
            )

            return report

        except Exception as e:
            logger.error(
                f"Error generating compliance report: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to generate compliance report: {str(e)}"
            )

    def get_schedule_performance_metrics(
        self,
        db: Session,
        schedule_id: UUID,
    ) -> Dict[str, Any]:
        """
        Get performance metrics for a specific schedule.

        Args:
            db: Database session
            schedule_id: UUID of the schedule

        Returns:
            Dictionary with performance metrics
        """
        if not schedule_id:
            raise ValidationException("Schedule ID is required")

        try:
            history = self.get_history_for_schedule(db, schedule_id)

            metrics = {
                "schedule_id": str(schedule_id),
                "total_executions": history.total_executions,
                "average_completion_time_hours": history.average_completion_time_hours,
                "on_time_rate": history.on_time_rate,
                "compliance_rate": history.compliance_rate,
                "last_execution_date": None,
                "next_due_date": None,
                "is_overdue": False,
            }

            # Get current schedule state
            schedule = self.get_schedule(db, schedule_id)
            metrics["next_due_date"] = (
                schedule.next_due_date.isoformat()
                if schedule.next_due_date
                else None
            )
            metrics["last_execution_date"] = (
                schedule.last_completed_date.isoformat()
                if schedule.last_completed_date
                else None
            )
            
            if schedule.next_due_date:
                metrics["is_overdue"] = schedule.next_due_date < datetime.utcnow()

            return metrics

        except Exception as e:
            logger.error(
                f"Error getting schedule metrics: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve schedule metrics: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _validate_schedule_create(self, request: ScheduleCreate) -> None:
        """Validate schedule creation data."""
        if not request.hostel_id:
            raise ValidationException("Hostel ID is required")

        if not request.schedule_name or len(request.schedule_name.strip()) < 3:
            raise ValidationException(
                "Schedule name must be at least 3 characters"
            )

        if not request.frequency:
            raise ValidationException("Frequency is required")

        if request.frequency not in self.VALID_FREQUENCIES:
            raise ValidationException(
                f"Invalid frequency. Must be one of: {self.VALID_FREQUENCIES}"
            )

        if request.estimated_duration_hours is not None:
            if request.estimated_duration_hours <= 0:
                raise ValidationException(
                    "Estimated duration must be greater than zero"
                )

    def _validate_schedule_update(self, request: ScheduleUpdate) -> None:
        """Validate schedule update data."""
        if request.frequency and request.frequency not in self.VALID_FREQUENCIES:
            raise ValidationException(
                f"Invalid frequency. Must be one of: {self.VALID_FREQUENCIES}"
            )

        if request.estimated_duration_hours is not None:
            if request.estimated_duration_hours <= 0:
                raise ValidationException(
                    "Estimated duration must be greater than zero"
                )

    def _validate_schedule_execution(self, request: ScheduleExecution) -> None:
        """Validate schedule execution data."""
        if not request.schedule_id:
            raise ValidationException("Schedule ID is required")

        if not request.executed_by:
            raise ValidationException("Executed by field is required")

        if request.actual_duration_hours is not None:
            if request.actual_duration_hours <= 0:
                raise ValidationException(
                    "Actual duration must be greater than zero"
                )

        valid_statuses = ["completed", "partial", "skipped"]
        if request.status and request.status not in valid_statuses:
            raise ValidationException(
                f"Invalid execution status. Must be one of: {valid_statuses}"
            )

    def _calculate_next_due_date(
        self,
        start_date: datetime,
        frequency: str,
    ) -> datetime:
        """
        Calculate the next due date based on frequency.

        Args:
            start_date: Starting date for calculation
            frequency: Schedule frequency

        Returns:
            Next due date
        """
        if frequency == "daily":
            return start_date + timedelta(days=1)
        elif frequency == "weekly":
            return start_date + timedelta(weeks=1)
        elif frequency == "biweekly":
            return start_date + timedelta(weeks=2)
        elif frequency == "monthly":
            return start_date + relativedelta(months=1)
        elif frequency == "quarterly":
            return start_date + relativedelta(months=3)
        elif frequency == "semiannual":
            return start_date + relativedelta(months=6)
        elif frequency == "annual":
            return start_date + relativedelta(years=1)
        else:
            # Default to monthly if unknown
            logger.warning(f"Unknown frequency {frequency}, defaulting to monthly")
            return start_date + relativedelta(months=1)

    def _calculate_reminder_date(
        self,
        due_date: datetime,
        frequency: str,
    ) -> datetime:
        """
        Calculate reminder date based on due date and frequency.

        Args:
            due_date: Schedule due date
            frequency: Schedule frequency

        Returns:
            Reminder date
        """
        days_before = self.REMINDER_DAYS.get(frequency, 7)
        return due_date - timedelta(days=days_before)

    def _enrich_schedule_history(self, history: ScheduleHistory) -> ScheduleHistory:
        """
        Add calculated metrics to schedule history.

        Args:
            history: Base schedule history

        Returns:
            Enriched schedule history
        """
        if not history.executions:
            return history

        # Calculate on-time completion rate
        on_time_count = sum(
            1 for exec in history.executions
            if exec.was_on_time
        )
        history.on_time_rate = (
            (on_time_count / len(history.executions) * 100)
            if history.executions
            else None
        )

        # Calculate compliance rate (completed vs skipped)
        completed_count = sum(
            1 for exec in history.executions
            if exec.status == "completed"
        )
        history.compliance_rate = (
            (completed_count / len(history.executions) * 100)
            if history.executions
            else None
        )

        return history

    def _generate_compliance_insights(
        self,
        report: Dict[str, Any]
    ) -> List[str]:
        """
        Generate insights from compliance report.

        Args:
            report: Compliance report data

        Returns:
            List of insight strings
        """
        insights = []
        
        compliance_rate = report.get("compliance_rate", 0)
        on_time_rate = report.get("on_time_rate", 0)
        overdue_count = report.get("overdue_schedules", 0)

        if compliance_rate >= 95:
            insights.append("Excellent compliance rate - maintain current practices")
        elif compliance_rate >= 80:
            insights.append("Good compliance rate - monitor for improvements")
        elif compliance_rate >= 60:
            insights.append("Compliance needs improvement - review schedule capacity")
        else:
            insights.append("Critical: Low compliance rate - immediate action required")

        if on_time_rate < 70:
            insights.append(
                "Many schedules completed late - review workload distribution"
            )

        if overdue_count > 0:
            insights.append(
                f"{overdue_count} schedule(s) overdue - prioritize completion"
            )

        return insights