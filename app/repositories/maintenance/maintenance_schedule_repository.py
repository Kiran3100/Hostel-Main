# app/repositories/maintenance/maintenance_schedule_repository.py
"""
Maintenance Schedule Repository.

Preventive maintenance scheduling with recurrence management,
execution tracking, and predictive analytics.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from dateutil.relativedelta import relativedelta
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.maintenance import (
    MaintenanceSchedule,
    ScheduleExecution,
    MaintenanceRequest,
)
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.pagination import PaginationParams, PaginatedResult
from app.schemas.common.enums import MaintenanceCategory, MaintenanceRecurrence


class MaintenanceScheduleRepository(BaseRepository[MaintenanceSchedule]):
    """
    Repository for maintenance schedule operations.
    
    Manages preventive maintenance schedules with intelligent
    recurrence handling and execution tracking.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with session."""
        super().__init__(MaintenanceSchedule, session)
    
    # ============================================================================
    # CREATE OPERATIONS
    # ============================================================================
    
    def create_schedule(
        self,
        hostel_id: UUID,
        title: str,
        category: MaintenanceCategory,
        recurrence: MaintenanceRecurrence,
        start_date: date,
        description: Optional[str] = None,
        schedule_code: Optional[str] = None,
        end_date: Optional[date] = None,
        assigned_to: Optional[UUID] = None,
        estimated_cost: Optional[Decimal] = None,
        estimated_duration_hours: Optional[Decimal] = None,
        priority_level: Optional[str] = None,
        checklist: Optional[List[Dict[str, Any]]] = None,
        recurrence_config: Optional[Dict[str, Any]] = None,
        auto_create_requests: bool = True,
        notification_days_before: int = 3,
        **kwargs
    ) -> MaintenanceSchedule:
        """
        Create new preventive maintenance schedule.
        
        Args:
            hostel_id: Hostel identifier
            title: Schedule title
            category: Maintenance category
            recurrence: Recurrence pattern
            start_date: First scheduled date
            description: Schedule description
            schedule_code: Optional schedule code
            end_date: Optional end date
            assigned_to: Default assignee
            estimated_cost: Estimated cost per execution
            estimated_duration_hours: Estimated duration
            priority_level: Default priority
            checklist: Maintenance checklist
            recurrence_config: Recurrence configuration
            auto_create_requests: Auto-create requests
            notification_days_before: Notification days
            **kwargs: Additional schedule attributes
            
        Returns:
            Created maintenance schedule
        """
        # Calculate next due date
        next_due_date = start_date
        
        schedule_data = {
            "hostel_id": hostel_id,
            "schedule_code": schedule_code or self._generate_schedule_code(hostel_id),
            "title": title,
            "description": description,
            "category": category,
            "recurrence": recurrence,
            "recurrence_config": recurrence_config or {},
            "start_date": start_date,
            "end_date": end_date,
            "next_due_date": next_due_date,
            "assigned_to": assigned_to,
            "estimated_cost": estimated_cost,
            "estimated_duration_hours": estimated_duration_hours,
            "priority_level": priority_level,
            "checklist": checklist or [],
            "auto_create_requests": auto_create_requests,
            "notification_days_before": notification_days_before,
            "is_active": True,
            **kwargs
        }
        
        return self.create(schedule_data)
    
    def create_execution_record(
        self,
        schedule_id: UUID,
        scheduled_date: date,
        execution_date: date,
        executed_by: UUID,
        completed: bool = False,
        maintenance_request_id: Optional[UUID] = None,
        completion_notes: Optional[str] = None,
        actual_cost: Optional[Decimal] = None,
        actual_duration_hours: Optional[Decimal] = None,
        checklist_results: Optional[List[Dict[str, Any]]] = None,
        materials_used: Optional[List[Dict[str, Any]]] = None,
        issues_found: Optional[str] = None,
        recommendations: Optional[str] = None,
        quality_rating: Optional[int] = None,
        **kwargs
    ) -> ScheduleExecution:
        """
        Create schedule execution record.
        
        Args:
            schedule_id: Schedule identifier
            scheduled_date: Originally scheduled date
            execution_date: Actual execution date
            executed_by: User who executed
            completed: Completion status
            maintenance_request_id: Related request
            completion_notes: Completion notes
            actual_cost: Actual cost
            actual_duration_hours: Actual duration
            checklist_results: Checklist results
            materials_used: Materials used
            issues_found: Issues identified
            recommendations: Recommendations
            quality_rating: Quality rating
            **kwargs: Additional execution attributes
            
        Returns:
            Created execution record
        """
        # Calculate delay
        was_on_time = execution_date <= scheduled_date
        days_delayed = max(0, (execution_date - scheduled_date).days)
        
        execution_data = {
            "schedule_id": schedule_id,
            "maintenance_request_id": maintenance_request_id,
            "scheduled_date": scheduled_date,
            "execution_date": execution_date,
            "executed_by": executed_by,
            "completed": completed,
            "completion_notes": completion_notes,
            "actual_cost": actual_cost,
            "actual_duration_hours": actual_duration_hours,
            "checklist_results": checklist_results or [],
            "materials_used": materials_used or [],
            "issues_found": issues_found,
            "recommendations": recommendations,
            "was_on_time": was_on_time,
            "days_delayed": days_delayed,
            "quality_rating": quality_rating,
            **kwargs
        }
        
        execution = ScheduleExecution(**execution_data)
        self.session.add(execution)
        self.session.commit()
        self.session.refresh(execution)
        
        # Update schedule statistics
        self._update_schedule_statistics(schedule_id, completed)
        
        return execution
    
    # ============================================================================
    # READ OPERATIONS - SCHEDULES
    # ============================================================================
    
    def find_by_hostel(
        self,
        hostel_id: UUID,
        is_active: Optional[bool] = True,
        category: Optional[MaintenanceCategory] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceSchedule]:
        """
        Find maintenance schedules for hostel.
        
        Args:
            hostel_id: Hostel identifier
            is_active: Filter by active status
            category: Optional category filter
            pagination: Pagination parameters
            
        Returns:
            Paginated maintenance schedules
        """
        query = select(MaintenanceSchedule).where(
            MaintenanceSchedule.hostel_id == hostel_id,
            MaintenanceSchedule.deleted_at.is_(None)
        )
        
        if is_active is not None:
            query = query.where(MaintenanceSchedule.is_active == is_active)
        
        if category:
            query = query.where(MaintenanceSchedule.category == category)
        
        query = query.order_by(
            MaintenanceSchedule.next_due_date.asc(),
            MaintenanceSchedule.created_at.desc()
        )
        
        return self.paginate(query, pagination)
    
    def find_by_assignee(
        self,
        assignee_id: UUID,
        is_active: bool = True,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceSchedule]:
        """
        Find schedules assigned to user.
        
        Args:
            assignee_id: Assignee identifier
            is_active: Filter by active status
            pagination: Pagination parameters
            
        Returns:
            Paginated assigned schedules
        """
        query = select(MaintenanceSchedule).where(
            MaintenanceSchedule.assigned_to == assignee_id,
            MaintenanceSchedule.is_active == is_active,
            MaintenanceSchedule.deleted_at.is_(None)
        ).order_by(MaintenanceSchedule.next_due_date.asc())
        
        return self.paginate(query, pagination)
    
    def find_by_schedule_code(
        self,
        schedule_code: str
    ) -> Optional[MaintenanceSchedule]:
        """
        Find schedule by schedule code.
        
        Args:
            schedule_code: Schedule code
            
        Returns:
            Schedule if found
        """
        query = select(MaintenanceSchedule).where(
            MaintenanceSchedule.schedule_code == schedule_code,
            MaintenanceSchedule.deleted_at.is_(None)
        )
        
        return self.session.execute(query).scalar_one_or_none()
    
    def find_due_schedules(
        self,
        hostel_id: Optional[UUID] = None,
        due_date: Optional[date] = None,
        include_overdue: bool = True,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceSchedule]:
        """
        Find schedules that are due.
        
        Args:
            hostel_id: Optional hostel filter
            due_date: Check due date (defaults to today)
            include_overdue: Include overdue schedules
            pagination: Pagination parameters
            
        Returns:
            Paginated due schedules
        """
        check_date = due_date or date.today()
        
        query = select(MaintenanceSchedule).where(
            MaintenanceSchedule.is_active == True,
            MaintenanceSchedule.deleted_at.is_(None)
        )
        
        if include_overdue:
            query = query.where(MaintenanceSchedule.next_due_date <= check_date)
        else:
            query = query.where(MaintenanceSchedule.next_due_date == check_date)
        
        if hostel_id:
            query = query.where(MaintenanceSchedule.hostel_id == hostel_id)
        
        query = query.order_by(MaintenanceSchedule.next_due_date.asc())
        
        return self.paginate(query, pagination)
    
    def find_overdue_schedules(
        self,
        hostel_id: Optional[UUID] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceSchedule]:
        """
        Find overdue maintenance schedules.
        
        Args:
            hostel_id: Optional hostel filter
            pagination: Pagination parameters
            
        Returns:
            Paginated overdue schedules
        """
        today = date.today()
        
        query = select(MaintenanceSchedule).where(
            MaintenanceSchedule.is_active == True,
            MaintenanceSchedule.next_due_date < today,
            MaintenanceSchedule.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.where(MaintenanceSchedule.hostel_id == hostel_id)
        
        query = query.order_by(MaintenanceSchedule.next_due_date.asc())
        
        return self.paginate(query, pagination)
    
    def find_upcoming_schedules(
        self,
        hostel_id: UUID,
        days: int = 7,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceSchedule]:
        """
        Find schedules due in upcoming days.
        
        Args:
            hostel_id: Hostel identifier
            days: Number of days to look ahead
            pagination: Pagination parameters
            
        Returns:
            Paginated upcoming schedules
        """
        today = date.today()
        future_date = today + timedelta(days=days)
        
        query = select(MaintenanceSchedule).where(
            MaintenanceSchedule.hostel_id == hostel_id,
            MaintenanceSchedule.is_active == True,
            MaintenanceSchedule.next_due_date >= today,
            MaintenanceSchedule.next_due_date <= future_date,
            MaintenanceSchedule.deleted_at.is_(None)
        ).order_by(MaintenanceSchedule.next_due_date.asc())
        
        return self.paginate(query, pagination)
    
    # ============================================================================
    # READ OPERATIONS - EXECUTIONS
    # ============================================================================
    
    def find_executions_by_schedule(
        self,
        schedule_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[ScheduleExecution]:
        """
        Find executions for a schedule.
        
        Args:
            schedule_id: Schedule identifier
            start_date: Optional start date filter
            end_date: Optional end date filter
            pagination: Pagination parameters
            
        Returns:
            Paginated schedule executions
        """
        query = select(ScheduleExecution).where(
            ScheduleExecution.schedule_id == schedule_id
        )
        
        if start_date:
            query = query.where(ScheduleExecution.execution_date >= start_date)
        if end_date:
            query = query.where(ScheduleExecution.execution_date <= end_date)
        
        query = query.order_by(ScheduleExecution.execution_date.desc())
        
        return self.paginate(query, pagination)
    
    def find_executions_by_executor(
        self,
        executor_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[ScheduleExecution]:
        """
        Find executions by executor.
        
        Args:
            executor_id: Executor identifier
            start_date: Optional start date filter
            end_date: Optional end date filter
            pagination: Pagination parameters
            
        Returns:
            Paginated executions
        """
        query = select(ScheduleExecution).where(
            ScheduleExecution.executed_by == executor_id
        )
        
        if start_date:
            query = query.where(ScheduleExecution.execution_date >= start_date)
        if end_date:
            query = query.where(ScheduleExecution.execution_date <= end_date)
        
        query = query.order_by(ScheduleExecution.execution_date.desc())
        
        return self.paginate(query, pagination)
    
    def find_incomplete_executions(
        self,
        schedule_id: Optional[UUID] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[ScheduleExecution]:
        """
        Find incomplete schedule executions.
        
        Args:
            schedule_id: Optional schedule filter
            pagination: Pagination parameters
            
        Returns:
            Paginated incomplete executions
        """
        query = select(ScheduleExecution).where(
            ScheduleExecution.completed == False
        )
        
        if schedule_id:
            query = query.where(ScheduleExecution.schedule_id == schedule_id)
        
        query = query.order_by(ScheduleExecution.scheduled_date.asc())
        
        return self.paginate(query, pagination)
    
    def get_latest_execution(
        self,
        schedule_id: UUID
    ) -> Optional[ScheduleExecution]:
        """
        Get latest execution for schedule.
        
        Args:
            schedule_id: Schedule identifier
            
        Returns:
            Latest execution if exists
        """
        query = select(ScheduleExecution).where(
            ScheduleExecution.schedule_id == schedule_id
        ).order_by(
            ScheduleExecution.execution_date.desc()
        )
        
        return self.session.execute(query).scalars().first()
    
    # ============================================================================
    # UPDATE OPERATIONS
    # ============================================================================
    
    def update_next_due_date(
        self,
        schedule_id: UUID,
        calculate_from_last: bool = True
    ) -> MaintenanceSchedule:
        """
        Update next due date based on recurrence.
        
        Args:
            schedule_id: Schedule identifier
            calculate_from_last: Calculate from last execution
            
        Returns:
            Updated schedule
        """
        schedule = self.find_by_id(schedule_id)
        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")
        
        # Calculate next due date
        if calculate_from_last and schedule.last_execution_date:
            base_date = schedule.last_execution_date
        else:
            base_date = schedule.next_due_date
        
        next_date = self._calculate_next_date(
            base_date,
            schedule.recurrence,
            schedule.recurrence_config
        )
        
        schedule.next_due_date = next_date
        
        self.session.commit()
        self.session.refresh(schedule)
        
        return schedule
    
    def mark_execution_completed(
        self,
        execution_id: UUID,
        completion_notes: Optional[str] = None,
        actual_cost: Optional[Decimal] = None,
        actual_duration_hours: Optional[Decimal] = None,
        quality_rating: Optional[int] = None
    ) -> ScheduleExecution:
        """
        Mark execution as completed.
        
        Args:
            execution_id: Execution identifier
            completion_notes: Completion notes
            actual_cost: Actual cost
            actual_duration_hours: Actual duration
            quality_rating: Quality rating
            
        Returns:
            Updated execution
        """
        execution = self.session.get(ScheduleExecution, execution_id)
        if not execution:
            raise ValueError(f"Execution {execution_id} not found")
        
        execution.completed = True
        execution.completed_at = datetime.utcnow()
        
        if completion_notes:
            execution.completion_notes = completion_notes
        if actual_cost is not None:
            execution.actual_cost = actual_cost
        if actual_duration_hours is not None:
            execution.actual_duration_hours = actual_duration_hours
        if quality_rating is not None:
            execution.quality_rating = quality_rating
        
        self.session.commit()
        self.session.refresh(execution)
        
        # Update schedule
        self._update_schedule_statistics(execution.schedule_id, True)
        self.update_next_due_date(execution.schedule_id)
        
        return execution
    
    def activate_schedule(
        self,
        schedule_id: UUID
    ) -> MaintenanceSchedule:
        """
        Activate a schedule.
        
        Args:
            schedule_id: Schedule identifier
            
        Returns:
            Activated schedule
        """
        schedule = self.find_by_id(schedule_id)
        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")
        
        schedule.is_active = True
        
        self.session.commit()
        self.session.refresh(schedule)
        
        return schedule
    
    def deactivate_schedule(
        self,
        schedule_id: UUID
    ) -> MaintenanceSchedule:
        """
        Deactivate a schedule.
        
        Args:
            schedule_id: Schedule identifier
            
        Returns:
            Deactivated schedule
        """
        schedule = self.find_by_id(schedule_id)
        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")
        
        schedule.is_active = False
        
        self.session.commit()
        self.session.refresh(schedule)
        
        return schedule
    
    def update_schedule_checklist(
        self,
        schedule_id: UUID,
        checklist: List[Dict[str, Any]]
    ) -> MaintenanceSchedule:
        """
        Update schedule checklist.
        
        Args:
            schedule_id: Schedule identifier
            checklist: Updated checklist
            
        Returns:
            Updated schedule
        """
        schedule = self.find_by_id(schedule_id)
        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")
        
        schedule.checklist = checklist
        
        self.session.commit()
        self.session.refresh(schedule)
        
        return schedule
    
    # ============================================================================
    # ANALYTICS AND REPORTING
    # ============================================================================
    
    def get_schedule_statistics(
        self,
        hostel_id: UUID,
        category: Optional[MaintenanceCategory] = None
    ) -> Dict[str, Any]:
        """
        Get schedule statistics for hostel.
        
        Args:
            hostel_id: Hostel identifier
            category: Optional category filter
            
        Returns:
            Schedule statistics
        """
        query = select(
            func.count(MaintenanceSchedule.id).label("total_schedules"),
            func.sum(
                func.case(
                    (MaintenanceSchedule.is_active == True, 1),
                    else_=0
                )
            ).label("active_schedules"),
            func.sum(MaintenanceSchedule.total_executions).label("total_executions"),
            func.sum(MaintenanceSchedule.successful_executions).label("successful_executions"),
            func.avg(
                func.cast(MaintenanceSchedule.successful_executions, Decimal) /
                func.nullif(func.cast(MaintenanceSchedule.total_executions, Decimal), 0) * 100
            ).label("avg_success_rate")
        ).where(
            MaintenanceSchedule.hostel_id == hostel_id,
            MaintenanceSchedule.deleted_at.is_(None)
        )
        
        if category:
            query = query.where(MaintenanceSchedule.category == category)
        
        result = self.session.execute(query).first()
        
        return {
            "total_schedules": result.total_schedules or 0,
            "active_schedules": result.active_schedules or 0,
            "total_executions": result.total_executions or 0,
            "successful_executions": result.successful_executions or 0,
            "average_success_rate": float(result.avg_success_rate or 0)
        }
    
    def get_execution_performance(
        self,
        schedule_id: UUID
    ) -> Dict[str, Any]:
        """
        Get execution performance for schedule.
        
        Args:
            schedule_id: Schedule identifier
            
        Returns:
            Performance metrics
        """
        query = select(
            func.count(ScheduleExecution.id).label("total_executions"),
            func.sum(
                func.case(
                    (ScheduleExecution.completed == True, 1),
                    else_=0
                )
            ).label("completed"),
            func.sum(
                func.case(
                    (ScheduleExecution.was_on_time == True, 1),
                    else_=0
                )
            ).label("on_time"),
            func.avg(ScheduleExecution.days_delayed).label("avg_delay"),
            func.avg(ScheduleExecution.actual_cost).label("avg_cost"),
            func.avg(ScheduleExecution.actual_duration_hours).label("avg_duration"),
            func.avg(ScheduleExecution.quality_rating).label("avg_quality")
        ).where(
            ScheduleExecution.schedule_id == schedule_id
        )
        
        result = self.session.execute(query).first()
        
        completion_rate = Decimal("0.00")
        on_time_rate = Decimal("0.00")
        
        if result.total_executions and result.total_executions > 0:
            completion_rate = round(
                Decimal(result.completed or 0) / Decimal(result.total_executions) * 100,
                2
            )
            on_time_rate = round(
                Decimal(result.on_time or 0) / Decimal(result.total_executions) * 100,
                2
            )
        
        return {
            "total_executions": result.total_executions or 0,
            "completed": result.completed or 0,
            "completion_rate": float(completion_rate),
            "on_time": result.on_time or 0,
            "on_time_rate": float(on_time_rate),
            "average_delay_days": float(result.avg_delay or 0),
            "average_cost": float(result.avg_cost or 0),
            "average_duration_hours": float(result.avg_duration or 0),
            "average_quality_rating": float(result.avg_quality or 0)
        }
    
    def get_recurrence_distribution(
        self,
        hostel_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get distribution of schedules by recurrence.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            Recurrence distribution
        """
        query = select(
            MaintenanceSchedule.recurrence,
            func.count(MaintenanceSchedule.id).label("count")
        ).where(
            MaintenanceSchedule.hostel_id == hostel_id,
            MaintenanceSchedule.is_active == True,
            MaintenanceSchedule.deleted_at.is_(None)
        ).group_by(
            MaintenanceSchedule.recurrence
        ).order_by(
            desc("count")
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "recurrence": str(row.recurrence.value),
                "count": row.count
            }
            for row in results
        ]
    
    def get_category_distribution(
        self,
        hostel_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get distribution of schedules by category.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            Category distribution
        """
        query = select(
            MaintenanceSchedule.category,
            func.count(MaintenanceSchedule.id).label("count"),
            func.sum(MaintenanceSchedule.estimated_cost).label("total_estimated_cost")
        ).where(
            MaintenanceSchedule.hostel_id == hostel_id,
            MaintenanceSchedule.is_active == True,
            MaintenanceSchedule.deleted_at.is_(None)
        ).group_by(
            MaintenanceSchedule.category
        ).order_by(
            desc("count")
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "category": str(row.category.value),
                "schedule_count": row.count,
                "total_estimated_cost": float(row.total_estimated_cost or 0)
            }
            for row in results
        ]
    
    def calculate_cost_trends(
        self,
        schedule_id: UUID,
        months: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Calculate cost trends for schedule.
        
        Args:
            schedule_id: Schedule identifier
            months: Number of months to analyze
            
        Returns:
            Monthly cost trends
        """
        cutoff_date = date.today() - timedelta(days=months * 30)
        
        query = select(
            func.date_trunc('month', ScheduleExecution.execution_date).label('month'),
            func.count(ScheduleExecution.id).label("execution_count"),
            func.sum(ScheduleExecution.actual_cost).label("total_cost"),
            func.avg(ScheduleExecution.actual_cost).label("avg_cost")
        ).where(
            ScheduleExecution.schedule_id == schedule_id,
            ScheduleExecution.execution_date >= cutoff_date,
            ScheduleExecution.actual_cost.isnot(None)
        ).group_by(
            'month'
        ).order_by(
            'month'
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "month": row.month.strftime("%Y-%m"),
                "execution_count": row.execution_count,
                "total_cost": float(row.total_cost or 0),
                "average_cost": float(row.avg_cost or 0)
            }
            for row in results
        ]
    
    def get_upcoming_maintenance_calendar(
        self,
        hostel_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming maintenance calendar.
        
        Args:
            hostel_id: Hostel identifier
            days: Number of days to look ahead
            
        Returns:
            Calendar of upcoming maintenance
        """
        today = date.today()
        future_date = today + timedelta(days=days)
        
        query = select(
            MaintenanceSchedule.id,
            MaintenanceSchedule.schedule_code,
            MaintenanceSchedule.title,
            MaintenanceSchedule.category,
            MaintenanceSchedule.next_due_date,
            MaintenanceSchedule.estimated_duration_hours,
            MaintenanceSchedule.assigned_to,
            MaintenanceSchedule.priority_level
        ).where(
            MaintenanceSchedule.hostel_id == hostel_id,
            MaintenanceSchedule.is_active == True,
            MaintenanceSchedule.next_due_date >= today,
            MaintenanceSchedule.next_due_date <= future_date,
            MaintenanceSchedule.deleted_at.is_(None)
        ).order_by(
            MaintenanceSchedule.next_due_date.asc()
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "schedule_id": str(row.id),
                "schedule_code": row.schedule_code,
                "title": row.title,
                "category": str(row.category.value),
                "due_date": row.next_due_date.isoformat(),
                "estimated_duration_hours": float(row.estimated_duration_hours or 0),
                "assigned_to": str(row.assigned_to) if row.assigned_to else None,
                "priority_level": row.priority_level
            }
            for row in results
        ]
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _generate_schedule_code(self, hostel_id: UUID) -> str:
        """
        Generate unique schedule code.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            Unique schedule code
        """
        # Count schedules for this hostel
        count_query = select(
            func.count(MaintenanceSchedule.id)
        ).where(
            MaintenanceSchedule.hostel_id == hostel_id
        )
        
        count = self.session.execute(count_query).scalar_one() + 1
        
        # Format: SCH-0001
        return f"SCH-{count:04d}"
    
    def _calculate_next_date(
        self,
        current_date: date,
        recurrence: MaintenanceRecurrence,
        config: Dict[str, Any]
    ) -> date:
        """
        Calculate next occurrence date.
        
        Args:
            current_date: Current date
            recurrence: Recurrence pattern
            config: Recurrence configuration
            
        Returns:
            Next occurrence date
        """
        if recurrence == MaintenanceRecurrence.DAILY:
            return current_date + timedelta(days=1)
        elif recurrence == MaintenanceRecurrence.WEEKLY:
            return current_date + timedelta(weeks=1)
        elif recurrence == MaintenanceRecurrence.MONTHLY:
            return current_date + relativedelta(months=1)
        elif recurrence == MaintenanceRecurrence.QUARTERLY:
            return current_date + relativedelta(months=3)
        elif recurrence == MaintenanceRecurrence.SEMI_ANNUAL:
            return current_date + relativedelta(months=6)
        elif recurrence == MaintenanceRecurrence.ANNUAL:
            return current_date + relativedelta(years=1)
        else:
            # Custom recurrence - use config
            if config and "interval_days" in config:
                return current_date + timedelta(days=config["interval_days"])
            return current_date + timedelta(days=30)  # Default
    
    def _update_schedule_statistics(
        self,
        schedule_id: UUID,
        was_successful: bool
    ) -> None:
        """
        Update schedule execution statistics.
        
        Args:
            schedule_id: Schedule identifier
            was_successful: Whether execution was successful
        """
        schedule = self.find_by_id(schedule_id)
        if not schedule:
            return
        
        schedule.total_executions += 1
        if was_successful:
            schedule.successful_executions += 1
        
        # Update last execution date
        latest_execution = self.get_latest_execution(schedule_id)
        if latest_execution and latest_execution.completed:
            schedule.last_execution_date = latest_execution.execution_date
            schedule.last_completed_date = latest_execution.execution_date
        
        self.session.commit()