# app/models/maintenance/maintenance_schedule.py
"""
Preventive maintenance schedule models.

Scheduled preventive maintenance with recurrence patterns,
execution tracking, and checklist management.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin, AuditMixin

from app.schemas.common.enums import MaintenanceCategory, MaintenanceRecurrence


class MaintenanceSchedule(BaseModel, UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin):
    """
    Preventive maintenance schedule.
    
    Defines recurring maintenance tasks with scheduling
    and execution tracking.
    """
    
    __tablename__ = "maintenance_schedules"
    
    hostel_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel unique identifier",
    )
    
    # Schedule identification
    schedule_code = Column(
        String(50),
        nullable=True,
        unique=True,
        comment="Schedule code/reference",
    )
    
    title = Column(
        String(255),
        nullable=False,
        comment="Schedule title",
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Schedule description",
    )
    
    # Category
    category = Column(
        Enum(MaintenanceCategory),
        nullable=False,
        index=True,
        comment="Maintenance category",
    )
    
    # Recurrence
    recurrence = Column(
        Enum(MaintenanceRecurrence),
        nullable=False,
        comment="Recurrence pattern",
    )
    
    recurrence_config = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Detailed recurrence configuration",
    )
    
    # Scheduling
    start_date = Column(
        Date,
        nullable=False,
        comment="First scheduled date",
    )
    
    end_date = Column(
        Date,
        nullable=True,
        comment="Last scheduled date (optional)",
    )
    
    next_due_date = Column(
        Date,
        nullable=False,
        index=True,
        comment="Next scheduled execution date",
    )
    
    last_execution_date = Column(
        Date,
        nullable=True,
        comment="Last execution date",
    )
    
    # Assignment
    assigned_to = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Default assignee user ID",
    )
    
    # Estimates
    estimated_cost = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Estimated cost per execution",
    )
    
    estimated_duration_hours = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Estimated duration in hours",
    )
    
    # Status
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether schedule is active",
    )
    
    # Execution tracking
    total_executions = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total times executed",
    )
    
    successful_executions = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Successfully completed executions",
    )
    
    last_completed_date = Column(
        Date,
        nullable=True,
        comment="Last successful completion date",
    )
    
    # Automation
    auto_create_requests = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Auto-create maintenance requests on due date",
    )
    
    notification_days_before = Column(
        Integer,
        nullable=False,
        default=3,
        comment="Days before due date to send notification",
    )
    
    # Priority
    priority_level = Column(
        String(20),
        nullable=True,
        comment="Default priority level",
    )
    
    # Checklist
    checklist = Column(
        JSONB,
        nullable=True,
        default=[],
        comment="Maintenance checklist items",
    )
    
    # Metadata
    metadata = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional schedule metadata",
    )
    
    # Relationships
    hostel = relationship("Hostel", back_populates="maintenance_schedules")
    assignee = relationship("User", back_populates="assigned_schedules")
    maintenance_requests = relationship(
        "MaintenanceRequest",
        back_populates="preventive_schedule",
        cascade="all, delete-orphan"
    )
    executions = relationship(
        "ScheduleExecution",
        back_populates="schedule",
        cascade="all, delete-orphan",
        order_by="ScheduleExecution.execution_date.desc()"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "estimated_cost >= 0",
            name="ck_schedule_estimated_cost_positive"
        ),
        CheckConstraint(
            "estimated_duration_hours >= 0",
            name="ck_schedule_duration_positive"
        ),
        CheckConstraint(
            "total_executions >= 0",
            name="ck_schedule_executions_positive"
        ),
        CheckConstraint(
            "successful_executions >= 0",
            name="ck_schedule_successful_positive"
        ),
        CheckConstraint(
            "notification_days_before >= 0 AND notification_days_before <= 30",
            name="ck_schedule_notification_days_range"
        ),
        Index("idx_schedule_hostel_active", "hostel_id", "is_active"),
        Index("idx_schedule_next_due", "next_due_date", "is_active"),
        Index("idx_schedule_category", "category", "is_active"),
        {"comment": "Preventive maintenance schedules"}
    )
    
    def __repr__(self) -> str:
        return f"<MaintenanceSchedule {self.title} - {self.recurrence.value}>"
    
    @validates("estimated_cost", "estimated_duration_hours")
    def validate_positive_values(self, key: str, value: Optional[Decimal]) -> Optional[Decimal]:
        """Validate numeric values are positive."""
        if value is not None and value < 0:
            raise ValueError(f"{key} must be positive")
        return value
    
    @hybrid_property
    def is_overdue(self) -> bool:
        """Check if schedule is overdue."""
        if not self.is_active:
            return False
        return self.next_due_date < date.today()
    
    @hybrid_property
    def days_until_due(self) -> int:
        """Calculate days until next due date."""
        return (self.next_due_date - date.today()).days
    
    @hybrid_property
    def success_rate(self) -> Decimal:
        """Calculate execution success rate."""
        if self.total_executions == 0:
            return Decimal("0.00")
        return round(
            Decimal(self.successful_executions) / Decimal(self.total_executions) * 100,
            2
        )
    
    def calculate_next_due_date(self) -> date:
        """
        Calculate next due date based on recurrence pattern.
        
        Returns:
            Next scheduled date
        """
        from dateutil.relativedelta import relativedelta
        
        current_due = self.next_due_date
        
        if self.recurrence == MaintenanceRecurrence.DAILY:
            return current_due + relativedelta(days=1)
        elif self.recurrence == MaintenanceRecurrence.WEEKLY:
            return current_due + relativedelta(weeks=1)
        elif self.recurrence == MaintenanceRecurrence.MONTHLY:
            return current_due + relativedelta(months=1)
        elif self.recurrence == MaintenanceRecurrence.QUARTERLY:
            return current_due + relativedelta(months=3)
        elif self.recurrence == MaintenanceRecurrence.SEMI_ANNUAL:
            return current_due + relativedelta(months=6)
        elif self.recurrence == MaintenanceRecurrence.ANNUAL:
            return current_due + relativedelta(years=1)
        else:
            # Custom recurrence - use config
            if self.recurrence_config and "interval_days" in self.recurrence_config:
                return current_due + relativedelta(days=self.recurrence_config["interval_days"])
            return current_due + relativedelta(days=30)  # Default to monthly


class ScheduleExecution(BaseModel, UUIDMixin, TimestampModel, AuditMixin):
    """
    Schedule execution record.
    
    Tracks individual executions of preventive maintenance schedules
    with completion details and results.
    """
    
    __tablename__ = "schedule_executions"
    
    schedule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_schedules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Related schedule",
    )
    
    maintenance_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maintenance_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Created maintenance request (if auto-created)",
    )
    
    # Execution details
    scheduled_date = Column(
        Date,
        nullable=False,
        comment="Originally scheduled date",
    )
    
    execution_date = Column(
        Date,
        nullable=False,
        index=True,
        comment="Actual execution date",
    )
    
    executed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        comment="User who executed the maintenance",
    )
    
    # Completion
    completed = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether execution was completed successfully",
    )
    
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Completion timestamp",
    )
    
    completion_notes = Column(
        Text,
        nullable=True,
        comment="Detailed completion notes",
    )
    
    # Cost and time
    actual_cost = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Actual cost incurred",
    )
    
    actual_duration_hours = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Actual time taken in hours",
    )
    
    # Checklist results
    checklist_results = Column(
        JSONB,
        nullable=True,
        default=[],
        comment="Results for each checklist item",
    )
    
    # Materials
    materials_used = Column(
        JSONB,
        nullable=True,
        default=[],
        comment="Materials used in execution",
    )
    
    # Issues and recommendations
    issues_found = Column(
        Text,
        nullable=True,
        comment="Issues or concerns identified",
    )
    
    recommendations = Column(
        Text,
        nullable=True,
        comment="Recommendations for future maintenance",
    )
    
    # Performance tracking
    was_on_time = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether executed on scheduled date",
    )
    
    days_delayed = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Days delayed from scheduled date",
    )
    
    quality_rating = Column(
        Integer,
        nullable=True,
        comment="Quality rating for execution (1-5)",
    )
    
    # Next occurrence
    skip_next_occurrence = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Skip the next scheduled occurrence",
    )
    
    reschedule_next_to = Column(
        Date,
        nullable=True,
        comment="Reschedule next occurrence to specific date",
    )
    
    # Metadata
    metadata = Column(
        JSONB,
        nullable=True,
        default={},
        comment="Additional execution metadata",
    )
    
    # Relationships
    schedule = relationship(
        "MaintenanceSchedule",
        back_populates="executions"
    )
    maintenance_request = relationship("MaintenanceRequest")
    executor = relationship("User")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "actual_cost >= 0",
            name="ck_execution_cost_positive"
        ),
        CheckConstraint(
            "actual_duration_hours >= 0",
            name="ck_execution_duration_positive"
        ),
        CheckConstraint(
            "days_delayed >= 0",
            name="ck_execution_delay_positive"
        ),
        CheckConstraint(
            "quality_rating >= 1 AND quality_rating <= 5",
            name="ck_execution_quality_rating_range"
        ),
        Index("idx_execution_schedule_date", "schedule_id", "execution_date"),
        Index("idx_execution_executor", "executed_by", "execution_date"),
        {"comment": "Schedule execution records"}
    )
    
    def __repr__(self) -> str:
        status = "Completed" if self.completed else "Incomplete"
        return f"<ScheduleExecution {self.schedule_id} - {status} on {self.execution_date}>"
    
    @validates("quality_rating")
    def validate_quality_rating(self, key: str, value: Optional[int]) -> Optional[int]:
        """Validate quality rating is in valid range."""
        if value is not None and (value < 1 or value > 5):
            raise ValueError("Quality rating must be between 1 and 5")
        return value
    
    @hybrid_property
    def execution_status(self) -> str:
        """Get execution status summary."""
        if not self.completed:
            return "incomplete"
        elif self.was_on_time:
            return "on_time"
        else:
            return "delayed"