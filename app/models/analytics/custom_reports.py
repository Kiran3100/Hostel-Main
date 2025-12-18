"""
Custom report builder models for flexible reporting.

Provides persistent storage for:
- Saved report definitions
- Report schedules
- Cached report results
- Report execution history
"""

from datetime import datetime, time
from decimal import Decimal
from sqlalchemy import (
    Column, String, Integer, Numeric, DateTime, Date, Boolean, Time,
    ForeignKey, Text, Index, CheckConstraint, UniqueConstraint,
    Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
import uuid

from app.models.analytics.base_analytics import (
    BaseAnalyticsModel,
    CachedAnalyticsMixin
)


class CustomReportDefinition(BaseAnalyticsModel, CachedAnalyticsMixin):
    """
    Saved custom report definition.
    
    Stores report configuration for reuse and sharing.
    """
    
    __tablename__ = 'custom_report_definitions'
    
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        comment="Report creator"
    )
    
    report_name = Column(
        String(255),
        nullable=False,
        comment="Report name"
    )
    
    description = Column(
        Text,
        nullable=True,
        comment="Report description"
    )
    
    module = Column(
        SQLEnum(
            'bookings', 'payments', 'complaints', 'maintenance',
            'attendance', 'students', 'hostels', 'rooms',
            'users', 'announcements', 'reviews',
            name='report_module_enum'
        ),
        nullable=False,
        index=True,
        comment="Module to report on"
    )
    
    # Report configuration
    fields = Column(
        JSONB,
        nullable=False,
        comment="Field definitions"
    )
    
    filters = Column(
        JSONB,
        nullable=True,
        comment="Filter conditions"
    )
    
    group_by = Column(
        ARRAY(String),
        nullable=True,
        comment="Grouping fields"
    )
    
    sort_by = Column(
        String(100),
        nullable=True,
        comment="Sort field"
    )
    
    sort_order = Column(
        String(10),
        nullable=False,
        default='asc',
        comment="Sort order"
    )
    
    # Sharing and permissions
    is_public = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="Publicly accessible"
    )
    
    is_template = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="System template"
    )
    
    shared_with_user_ids = Column(
        ARRAY(UUID),
        nullable=True,
        comment="Shared user IDs"
    )
    
    shared_with_role = Column(
        String(50),
        nullable=True,
        comment="Shared role"
    )
    
    # Usage tracking
    run_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Execution count"
    )
    
    last_run_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last execution"
    )
    
    # Metadata
    is_shared = Column(
        Boolean,
        nullable=True,
        comment="Is shared with anyone"
    )
    
    complexity_score = Column(
        Integer,
        nullable=True,
        comment="Complexity score (0-100)"
    )
    
    __table_args__ = (
        Index('ix_custom_report_owner', 'owner_id'),
        Index('ix_custom_report_module', 'module'),
        Index('ix_custom_report_public', 'is_public'),
    )
    
    # Relationships
    schedules = relationship(
        'ReportSchedule',
        back_populates='report_definition',
        cascade='all, delete-orphan'
    )
    
    execution_history = relationship(
        'ReportExecutionHistory',
        back_populates='report_definition',
        cascade='all, delete-orphan'
    )


class ReportSchedule(BaseAnalyticsModel):
    """
    Scheduled report execution configuration.
    
    Manages automated report generation and delivery.
    """
    
    __tablename__ = 'report_schedules'
    
    report_definition_id = Column(
        UUID(as_uuid=True),
        ForeignKey('custom_report_definitions.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    schedule_name = Column(
        String(255),
        nullable=False,
        comment="Schedule name"
    )
    
    # Schedule configuration
    frequency = Column(
        SQLEnum(
            'daily', 'weekly', 'monthly', 'quarterly',
            name='schedule_frequency_enum'
        ),
        nullable=False,
        comment="Execution frequency"
    )
    
    time_of_day = Column(
        Time,
        nullable=False,
        comment="Execution time"
    )
    
    day_of_week = Column(
        Integer,
        nullable=True,
        comment="Day for weekly (0=Monday)"
    )
    
    day_of_month = Column(
        Integer,
        nullable=True,
        comment="Day for monthly (1-31)"
    )
    
    timezone = Column(
        String(50),
        nullable=False,
        default='UTC',
        comment="Timezone for scheduling"
    )
    
    # Delivery configuration
    recipients = Column(
        ARRAY(String),
        nullable=False,
        comment="Email recipients"
    )
    
    format = Column(
        SQLEnum(
            'csv', 'excel', 'json', 'pdf',
            name='report_format_enum'
        ),
        nullable=False,
        default='pdf',
        comment="Report format"
    )
    
    # Status
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Schedule active"
    )
    
    last_run_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last execution"
    )
    
    next_run_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Next scheduled run"
    )
    
    last_run_status = Column(
        String(20),
        nullable=True,
        comment="Last run status"
    )
    
    execution_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total executions"
    )
    
    failure_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Failed executions"
    )
    
    __table_args__ = (
        Index('ix_report_schedule_next_run', 'next_run_at'),
        Index('ix_report_schedule_active', 'is_active'),
        CheckConstraint(
            "day_of_week IS NULL OR (day_of_week >= 0 AND day_of_week <= 6)",
            name='ck_schedule_day_of_week_valid'
        ),
        CheckConstraint(
            "day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 31)",
            name='ck_schedule_day_of_month_valid'
        ),
    )
    
    # Relationships
    report_definition = relationship('CustomReportDefinition', back_populates='schedules')


class ReportExecutionHistory(BaseAnalyticsModel):
    """
    Report execution history tracking.
    
    Logs each report execution for audit and debugging.
    """
    
    __tablename__ = 'report_execution_history'
    
    report_definition_id = Column(
        UUID(as_uuid=True),
        ForeignKey('custom_report_definitions.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    schedule_id = Column(
        UUID(as_uuid=True),
        ForeignKey('report_schedules.id', ondelete='SET NULL'),
        nullable=True,
        comment="Schedule if automated"
    )
    
    executed_by = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        comment="User who executed"
    )
    
    execution_type = Column(
        SQLEnum(
            'manual', 'scheduled', 'api',
            name='execution_type_enum'
        ),
        nullable=False,
        comment="Execution type"
    )
    
    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True
    )
    
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True
    )
    
    execution_time_ms = Column(
        Integer,
        nullable=True,
        comment="Execution time in ms"
    )
    
    status = Column(
        SQLEnum(
            'running', 'completed', 'failed', 'cancelled',
            name='execution_status_enum'
        ),
        nullable=False,
        default='running',
        index=True
    )
    
    rows_returned = Column(
        Integer,
        nullable=True,
        comment="Rows in result"
    )
    
    result_size_bytes = Column(
        Integer,
        nullable=True,
        comment="Result size"
    )
    
    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if failed"
    )
    
    parameters_used = Column(
        JSONB,
        nullable=True,
        comment="Execution parameters"
    )
    
    __table_args__ = (
        Index('ix_execution_history_report', 'report_definition_id'),
        Index('ix_execution_history_started', 'started_at'),
        Index('ix_execution_history_status', 'status'),
    )
    
    # Relationships
    report_definition = relationship(
        'CustomReportDefinition',
        back_populates='execution_history'
    )


class CachedReportResult(BaseAnalyticsModel, CachedAnalyticsMixin):
    """
    Cached report results for performance.
    
    Stores pre-computed report results for quick access.
    """
    
    __tablename__ = 'cached_report_results'
    
    report_definition_id = Column(
        UUID(as_uuid=True),
        ForeignKey('custom_report_definitions.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    
    execution_history_id = Column(
        UUID(as_uuid=True),
        ForeignKey('report_execution_history.id', ondelete='SET NULL'),
        nullable=True
    )
    
    # Result data
    result_data = Column(
        JSONB,
        nullable=False,
        comment="Cached result data"
    )
    
    row_count = Column(
        Integer,
        nullable=False,
        comment="Number of rows"
    )
    
    column_definitions = Column(
        JSONB,
        nullable=True,
        comment="Column metadata"
    )
    
    summary_stats = Column(
        JSONB,
        nullable=True,
        comment="Summary statistics"
    )
    
    # Cache metadata
    generated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True
    )
    
    parameters_hash = Column(
        String(64),
        nullable=False,
        index=True,
        comment="Hash of execution parameters"
    )
    
    data_size_bytes = Column(
        Integer,
        nullable=True,
        comment="Size of cached data"
    )
    
    __table_args__ = (
        Index(
            'ix_cached_result_report_hash',
            'report_definition_id',
            'parameters_hash'
        ),
        Index('ix_cached_result_expires', 'cache_expires_at'),
    )