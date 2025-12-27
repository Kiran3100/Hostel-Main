"""
Enhanced Scheduled Task Service

Advanced orchestration for periodic/background tasks with intelligent scheduling,
performance monitoring, and failure recovery.
"""

from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import asyncio
import logging
from functools import wraps
import traceback

from sqlalchemy.orm import Session
from celery import Celery
from redis import Redis

from app.repositories.analytics import (
    BookingAnalyticsRepository,
    ComplaintAnalyticsRepository,
    FinancialAnalyticsRepository,
    OccupancyAnalyticsRepository,
)
from app.repositories.announcement import AnnouncementSchedulingRepository
from app.repositories.payment import PaymentReminderRepository
from app.repositories.maintenance import MaintenanceScheduleRepository
from app.repositories.audit import AuditAggregateRepository
from app.repositories.hostel import HostelRepository
from app.services.workflows.escalation_workflow_service import EscalationWorkflowService
from app.services.workflows.workflow_engine_service import workflow_engine
from app.core1.config import settings
from app.core1.exceptions import BusinessLogicException


logger = logging.getLogger(__name__)


class TaskPriority(str, Enum):
    """Task execution priorities."""
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskFrequency(str, Enum):
    """Task execution frequencies."""
    CONTINUOUS = "continuous"
    EVERY_MINUTE = "every_minute"
    EVERY_5_MINUTES = "every_5_minutes"
    EVERY_15_MINUTES = "every_15_minutes"
    EVERY_30_MINUTES = "every_30_minutes"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class TaskConfiguration:
    """Enhanced task configuration."""
    task_id: str
    name: str
    description: str
    frequency: TaskFrequency
    priority: TaskPriority
    handler: Callable
    enabled: bool = True
    retry_count: int = 3
    retry_delay: int = 60  # seconds
    timeout: int = 300  # seconds
    dependencies: List[str] = field(default_factory=list)
    conditions: List[Callable] = field(default_factory=list)
    notification_on_failure: bool = True
    max_concurrent: int = 1
    resource_requirements: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.dependencies:
            self.dependencies = []
        if not self.conditions:
            self.conditions = []
        if not self.resource_requirements:
            self.resource_requirements = {"cpu": 0.5, "memory": "256MB"}


@dataclass
class TaskExecution:
    """Task execution tracking."""
    execution_id: str
    task_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    execution_time: float = 0.0
    resource_usage: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "task_id": self.task_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status.value,
            "execution_time": self.execution_time,
            "retry_count": self.retry_count,
            "result": self.result,
            "error": self.error,
            "resource_usage": self.resource_usage
        }


@dataclass
class TaskMetrics:
    """Comprehensive task metrics."""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    average_execution_time: float = 0.0
    total_execution_time: float = 0.0
    last_execution: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    failure_rate: float = 0.0
    performance_trend: str = "stable"
    resource_efficiency: Dict[str, float] = field(default_factory=dict)


class ScheduledTaskService:
    """
    Enhanced orchestration for scheduled and background tasks.
    
    Features:
    - Intelligent task scheduling with dependency management
    - Dynamic resource allocation and optimization
    - Comprehensive monitoring and alerting
    - Failure recovery and retry mechanisms
    - Performance analytics and optimization
    - Distributed task execution support
    - Real-time task management dashboard
    """
    
    def __init__(
        self,
        escalation_service: EscalationWorkflowService,
        announcement_schedule_repo: AnnouncementSchedulingRepository,
        payment_reminder_repo: PaymentReminderRepository,
        booking_analytics_repo: BookingAnalyticsRepository,
        complaint_analytics_repo: ComplaintAnalyticsRepository,
        financial_analytics_repo: FinancialAnalyticsRepository,
        occupancy_analytics_repo: OccupancyAnalyticsRepository,
        maintenance_schedule_repo: MaintenanceScheduleRepository,
        audit_aggregate_repo: AuditAggregateRepository,
        hostel_repo: HostelRepository,
        redis_client: Optional[Redis] = None,
        celery_app: Optional[Celery] = None
    ):
        # Repository dependencies
        self.escalation_service = escalation_service
        self.announcement_schedule_repo = announcement_schedule_repo
        self.payment_reminder_repo = payment_reminder_repo
        self.booking_analytics_repo = booking_analytics_repo
        self.complaint_analytics_repo = complaint_analytics_repo
        self.financial_analytics_repo = financial_analytics_repo
        self.occupancy_analytics_repo = occupancy_analytics_repo
        self.maintenance_schedule_repo = maintenance_schedule_repo
        self.audit_aggregate_repo = audit_aggregate_repo
        self.hostel_repo = hostel_repo
        
        # Infrastructure
        self.redis_client = redis_client
        self.celery_app = celery_app
        
        # Task management
        self.task_configs: Dict[str, TaskConfiguration] = {}
        self.active_executions: Dict[str, TaskExecution] = {}
        self.task_metrics: Dict[str, TaskMetrics] = defaultdict(TaskMetrics)
        self.task_schedules: Dict[str, datetime] = {}
        
        # Performance monitoring
        self.system_metrics = {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "active_tasks": 0,
            "queue_depth": 0,
            "average_response_time": 0.0
        }
        
        # Task execution locks
        self.task_locks: Dict[str, asyncio.Lock] = {}
        
        self._setup_core_tasks()
        self._start_task_scheduler()
        self._start_monitoring()
    
    def _setup_core_tasks(self) -> None:
        """Setup core system tasks with intelligent configurations."""
        
        # SLA monitoring and escalation tasks
        sla_monitoring_task = TaskConfiguration(
            task_id="sla_monitoring",
            name="SLA Breach Monitoring",
            description="Monitor and auto-escalate SLA breaches",
            frequency=TaskFrequency.EVERY_15_MINUTES,
            priority=TaskPriority.CRITICAL,
            handler=self._run_comprehensive_sla_checks,
            retry_count=2,
            timeout=180,
            notification_on_failure=True,
            resource_requirements={"cpu": 0.3, "memory": "128MB"}
        )
        
        # Analytics aggregation tasks
        analytics_daily_task = TaskConfiguration(
            task_id="daily_analytics_aggregation",
            name="Daily Analytics Aggregation",
            description="Generate comprehensive daily analytics snapshots",
            frequency=TaskFrequency.DAILY,
            priority=TaskPriority.HIGH,
            handler=self._run_comprehensive_daily_analytics,
            retry_count=3,
            timeout=1800,  # 30 minutes
            dependencies=["data_validation"],
            resource_requirements={"cpu": 1.0, "memory": "512MB"}
        )
        
        # Payment reminder tasks
        payment_reminder_task = TaskConfiguration(
            task_id="payment_reminders",
            name="Payment Reminder Processing",
            description="Send intelligent payment reminders",
            frequency=TaskFrequency.DAILY,
            priority=TaskPriority.NORMAL,
            handler=self._send_intelligent_payment_reminders,
            retry_count=2,
            timeout=900,  # 15 minutes
            resource_requirements={"cpu": 0.5, "memory": "256MB"}
        )
        
        # Announcement processing
        announcement_task = TaskConfiguration(
            task_id="announcement_processing",
            name="Scheduled Announcement Processing",
            description="Process and deliver scheduled announcements",
            frequency=TaskFrequency.EVERY_30_MINUTES,
            priority=TaskPriority.NORMAL,
            handler=self._process_intelligent_announcements,
            retry_count=2,
            timeout=300,
            resource_requirements={"cpu": 0.4, "memory": "192MB"}
        )
        
        # Maintenance scheduling
        maintenance_scheduling_task = TaskConfiguration(
            task_id="maintenance_scheduling",
            name="Preventive Maintenance Scheduling",
            description="Schedule and execute preventive maintenance",
            frequency=TaskFrequency.DAILY,
            priority=TaskPriority.HIGH,
            handler=self._run_intelligent_maintenance_scheduling,
            retry_count=1,
            timeout=600,
            conditions=[self._check_maintenance_window],
            resource_requirements={"cpu": 0.6, "memory": "256MB"}
        )
        
        # System optimization tasks
        workflow_cleanup_task = TaskConfiguration(
            task_id="workflow_cleanup",
            name="Workflow Engine Cleanup",
            description="Clean up old workflow executions and optimize performance",
            frequency=TaskFrequency.DAILY,
            priority=TaskPriority.LOW,
            handler=self._run_workflow_engine_optimization,
            retry_count=1,
            timeout=300,
            conditions=[self._check_low_system_load],
            resource_requirements={"cpu": 0.3, "memory": "128MB"}
        )
        
        # Data integrity and validation
        data_validation_task = TaskConfiguration(
            task_id="data_validation",
            name="Data Integrity Validation",
            description="Validate data integrity across all systems",
            frequency=TaskFrequency.DAILY,
            priority=TaskPriority.HIGH,
            handler=self._run_comprehensive_data_validation,
            retry_count=2,
            timeout=900,
            notification_on_failure=True,
            resource_requirements={"cpu": 0.7, "memory": "384MB"}
        )
        
        # Performance monitoring
        performance_monitoring_task = TaskConfiguration(
            task_id="performance_monitoring",
            name="System Performance Monitoring",
            description="Monitor and optimize system performance",
            frequency=TaskFrequency.EVERY_5_MINUTES,
            priority=TaskPriority.HIGH,
            handler=self._monitor_system_performance,
            retry_count=1,
            timeout=60,
            max_concurrent=1,
            resource_requirements={"cpu": 0.2, "memory": "64MB"}
        )
        
        # Register all tasks
        tasks = [
            sla_monitoring_task,
            analytics_daily_task,
            payment_reminder_task,
            announcement_task,
            maintenance_scheduling_task,
            workflow_cleanup_task,
            data_validation_task,
            performance_monitoring_task
        ]
        
        for task in tasks:
            self.register_task(task)
    
    def register_task(self, task_config: TaskConfiguration) -> None:
        """Register a new scheduled task with validation."""
        # Validate task configuration
        self._validate_task_configuration(task_config)
        
        # Store configuration
        self.task_configs[task_config.task_id] = task_config
        
        # Initialize metrics
        self.task_metrics[task_config.task_id] = TaskMetrics()
        
        # Create execution lock
        self.task_locks[task_config.task_id] = asyncio.Lock()
        
        # Schedule next execution
        self._schedule_next_execution(task_config)
        
        logger.info(f"Registered task: {task_config.task_id} ({task_config.frequency.value})")
    
    def _validate_task_configuration(self, config: TaskConfiguration) -> None:
        """Validate task configuration."""
        if not config.task_id:
            raise ValueError("Task ID is required")
        
        if not callable(config.handler):
            raise ValueError("Task handler must be callable")
        
        if config.task_id in self.task_configs:
            raise ValueError(f"Task {config.task_id} already registered")
        
        # Validate dependencies exist
        for dep in config.dependencies:
            if dep not in self.task_configs:
                raise ValueError(f"Dependency {dep} not found")
    
    def _schedule_next_execution(self, task_config: TaskConfiguration) -> None:
        """Schedule next execution for a task."""
        if not task_config.enabled:
            return
        
        now = datetime.utcnow()
        
        # Calculate next execution time based on frequency
        if task_config.frequency == TaskFrequency.CONTINUOUS:
            next_execution = now
        elif task_config.frequency == TaskFrequency.EVERY_MINUTE:
            next_execution = now + timedelta(minutes=1)
        elif task_config.frequency == TaskFrequency.EVERY_5_MINUTES:
            next_execution = now + timedelta(minutes=5)
        elif task_config.frequency == TaskFrequency.EVERY_15_MINUTES:
            next_execution = now + timedelta(minutes=15)
        elif task_config.frequency == TaskFrequency.EVERY_30_MINUTES:
            next_execution = now + timedelta(minutes=30)
        elif task_config.frequency == TaskFrequency.HOURLY:
            next_execution = now + timedelta(hours=1)
        elif task_config.frequency == TaskFrequency.DAILY:
            # Schedule for 2 AM next day
            next_execution = (now + timedelta(days=1)).replace(hour=2, minute=0, second=0, microsecond=0)
        elif task_config.frequency == TaskFrequency.WEEKLY:
            # Schedule for next Monday 2 AM
            days_ahead = 7 - now.weekday()
            next_execution = (now + timedelta(days=days_ahead)).replace(hour=2, minute=0, second=0, microsecond=0)
        elif task_config.frequency == TaskFrequency.MONTHLY:
            # Schedule for 1st of next month 2 AM
            if now.month == 12:
                next_execution = datetime(now.year + 1, 1, 1, 2, 0, 0)
            else:
                next_execution = datetime(now.year, now.month + 1, 1, 2, 0, 0)
        else:
            next_execution = now + timedelta(hours=1)  # Default
        
        self.task_schedules[task_config.task_id] = next_execution
        
        logger.debug(f"Scheduled task {task_config.task_id} for {next_execution}")
    
    def _start_task_scheduler(self) -> None:
        """Start the main task scheduler loop."""
        async def scheduler_loop():
            while True:
                try:
                    await self._execute_due_tasks()
                    await asyncio.sleep(30)  # Check every 30 seconds
                except Exception as e:
                    logger.error(f"Task scheduler error: {str(e)}")
                    await asyncio.sleep(60)  # Wait longer on error
        
        # Start scheduler as background task
        asyncio.create_task(scheduler_loop())
    
    def _start_monitoring(self) -> None:
        """Start system monitoring and health checks."""
        async def monitoring_loop():
            while True:
                try:
                    await self._update_system_metrics()
                    await self._check_task_health()
                    await self._optimize_resource_allocation()
                    await asyncio.sleep(60)  # Monitor every minute
                except Exception as e:
                    logger.error(f"Monitoring loop error: {str(e)}")
                    await asyncio.sleep(120)
        
        # Start monitoring as background task
        asyncio.create_task(monitoring_loop())
    
    async def _execute_due_tasks(self) -> None:
        """Execute tasks that are due for execution."""
        now = datetime.utcnow()
        due_tasks = []
        
        # Find tasks that are due
        for task_id, scheduled_time in self.task_schedules.items():
            if scheduled_time <= now:
                task_config = self.task_configs.get(task_id)
                if task_config and task_config.enabled:
                    due_tasks.append(task_config)
        
        # Sort by priority
        due_tasks.sort(key=lambda t: self._get_priority_value(t.priority), reverse=True)
        
        # Execute tasks
        for task_config in due_tasks:
            await self._execute_task_with_management(task_config)
    
    async def _execute_task_with_management(self, task_config: TaskConfiguration) -> None:
        """Execute a task with comprehensive management and monitoring."""
        task_id = task_config.task_id
        
        # Check if already running (respect max_concurrent)
        running_count = sum(
            1 for exec in self.active_executions.values()
            if exec.task_id == task_id and exec.status == TaskStatus.RUNNING
        )
        
        if running_count >= task_config.max_concurrent:
            logger.warning(f"Task {task_id} already running {running_count} instances, skipping")
            return
        
        # Check dependencies
        if not await self._check_dependencies(task_config):
            logger.warning(f"Dependencies not met for task {task_id}, rescheduling")
            self._schedule_next_execution(task_config)
            return
        
        # Check conditions
        if not await self._check_conditions(task_config):
            logger.info(f"Conditions not met for task {task_id}, rescheduling")
            self._schedule_next_execution(task_config)
            return
        
        # Check resource availability
        if not await self._check_resource_availability(task_config):
            logger.warning(f"Insufficient resources for task {task_id}, rescheduling")
            # Reschedule for 5 minutes later
            self.task_schedules[task_id] = datetime.utcnow() + timedelta(minutes=5)
            return
        
        # Create execution record
        execution = TaskExecution(
            execution_id=str(uuid4()),
            task_id=task_id,
            started_at=datetime.utcnow()
        )
        
        self.active_executions[execution.execution_id] = execution
        
        # Execute task in background
        asyncio.create_task(self._execute_task_safely(task_config, execution))
        
        # Schedule next execution
        self._schedule_next_execution(task_config)
    
    async def _execute_task_safely(
        self,
        task_config: TaskConfiguration,
        execution: TaskExecution
    ) -> None:
        """Execute a task safely with error handling and retry logic."""
        async with self.task_locks[task_config.task_id]:
            start_time = datetime.utcnow()
            execution.status = TaskStatus.RUNNING
            
            logger.info(f"Starting task execution: {task_config.task_id}")
            
            try:
                # Execute task with timeout
                result = await asyncio.wait_for(
                    self._execute_task_handler(task_config, execution),
                    timeout=task_config.timeout
                )
                
                # Task completed successfully
                execution.status = TaskStatus.COMPLETED
                execution.completed_at = datetime.utcnow()
                execution.result = result
                execution.execution_time = (execution.completed_at - start_time).total_seconds()
                
                # Update metrics
                self._update_task_metrics_success(task_config.task_id, execution.execution_time)
                
                logger.info(
                    f"Task {task_config.task_id} completed successfully in {execution.execution_time:.2f}s"
                )
                
            except asyncio.TimeoutError:
                # Task timed out
                execution.status = TaskStatus.FAILED
                execution.completed_at = datetime.utcnow()
                execution.error = f"Task timed out after {task_config.timeout} seconds"
                execution.execution_time = (execution.completed_at - start_time).total_seconds()
                
                await self._handle_task_failure(task_config, execution, "timeout")
                
            except Exception as e:
                # Task failed with exception
                execution.status = TaskStatus.FAILED
                execution.completed_at = datetime.utcnow()
                execution.error = str(e)
                execution.execution_time = (execution.completed_at - start_time).total_seconds()
                
                # Check if we should retry
                if execution.retry_count < task_config.retry_count:
                    execution.retry_count += 1
                    execution.status = TaskStatus.RETRYING
                    
                    logger.warning(
                        f"Task {task_config.task_id} failed (attempt {execution.retry_count}), retrying in {task_config.retry_delay}s: {str(e)}"
                    )
                    
                    # Schedule retry
                    await asyncio.sleep(task_config.retry_delay)
                    await self._execute_task_safely(task_config, execution)
                    return
                else:
                    await self._handle_task_failure(task_config, execution, "exception", e)
            
            finally:
                # Clean up execution record
                if execution.execution_id in self.active_executions:
                    del self.active_executions[execution.execution_id]
    
    async def _execute_task_handler(
        self,
        task_config: TaskConfiguration,
        execution: TaskExecution
    ) -> Dict[str, Any]:
        """Execute the actual task handler."""
        # Create database session if needed
        from app.database import SessionLocal
        db = SessionLocal()
        
        try:
            # Execute handler
            if asyncio.iscoroutinefunction(task_config.handler):
                result = await task_config.handler(db)
            else:
                result = task_config.handler(db)
            
            return result or {"status": "completed"}
            
        finally:
            db.close()
    
    # Core task implementations
    
    async def _run_comprehensive_sla_checks(self, db: Session) -> Dict[str, Any]:
        """Enhanced SLA monitoring with intelligent escalation."""
        logger.info("Starting comprehensive SLA breach monitoring")
        
        sla_results = {
            "checked_entities": 0,
            "breaches_found": 0,
            "escalations_triggered": 0,
            "breach_details": []
        }
        
        # Check complaint SLAs
        complaint_breaches = await self._check_complaint_sla_breaches(db)
        sla_results["breach_details"].extend(complaint_breaches)
        
        # Check maintenance SLAs
        maintenance_breaches = await self._check_maintenance_sla_breaches(db)
        sla_results["breach_details"].extend(maintenance_breaches)
        
        # Check booking approval SLAs
        booking_breaches = await self._check_booking_sla_breaches(db)
        sla_results["breach_details"].extend(booking_breaches)
        
        sla_results["breaches_found"] = len(sla_results["breach_details"])
        
        # Process breaches and trigger escalations
        for breach in sla_results["breach_details"]:
            try:
                escalation_result = await self.escalation_service.auto_escalate_on_sla_breach(
                    db=db,
                    entity_type=breach["entity_type"],
                    entity_id=breach["entity_id"],
                    sla_breach_hours=breach["breach_hours"],
                    breach_severity=breach["severity"]
                )
                
                if escalation_result.get("escalation_triggered"):
                    sla_results["escalations_triggered"] += 1
                    
            except Exception as e:
                logger.error(f"Failed to escalate SLA breach {breach['entity_id']}: {str(e)}")
        
        logger.info(
            f"SLA check completed: {sla_results['breaches_found']} breaches, "
            f"{sla_results['escalations_triggered']} escalations triggered"
        )
        
        return sla_results
    
    async def _run_comprehensive_daily_analytics(self, db: Session) -> Dict[str, Any]:
        """Generate comprehensive daily analytics across all modules."""
        logger.info("Starting daily analytics aggregation")
        
        analytics_result = {
            "date": datetime.utcnow().date().isoformat(),
            "hostels_processed": 0,
            "analytics_generated": [],
            "errors": []
        }
        
        # Get all active hostels
        hostels = self.hostel_repo.get_all_active(db)
        analytics_result["hostels_processed"] = len(hostels)
        
        for hostel in hostels:
            try:
                # Generate booking analytics
                booking_analytics = await self._generate_booking_analytics(db, hostel.id)
                analytics_result["analytics_generated"].append({
                    "type": "booking",
                    "hostel_id": str(hostel.id),
                    "result": booking_analytics
                })
                
                # Generate complaint analytics
                complaint_analytics = await self._generate_complaint_analytics(db, hostel.id)
                analytics_result["analytics_generated"].append({
                    "type": "complaint",
                    "hostel_id": str(hostel.id),
                    "result": complaint_analytics
                })
                
                # Generate financial analytics
                financial_analytics = await self._generate_financial_analytics(db, hostel.id)
                analytics_result["analytics_generated"].append({
                    "type": "financial",
                    "hostel_id": str(hostel.id),
                    "result": financial_analytics
                })
                
                # Generate occupancy analytics
                occupancy_analytics = await self._generate_occupancy_analytics(db, hostel.id)
                analytics_result["analytics_generated"].append({
                    "type": "occupancy",
                    "hostel_id": str(hostel.id),
                    "result": occupancy_analytics
                })
                
            except Exception as e:
                error_detail = {
                    "hostel_id": str(hostel.id),
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
                analytics_result["errors"].append(error_detail)
                logger.error(f"Analytics generation failed for hostel {hostel.id}: {str(e)}")
        
        logger.info(
            f"Daily analytics completed: {len(analytics_result['analytics_generated'])} generated, "
            f"{len(analytics_result['errors'])} errors"
        )
        
        return analytics_result
    
    async def _send_intelligent_payment_reminders(self, db: Session) -> Dict[str, Any]:
        """Send intelligent payment reminders with optimization."""
        logger.info("Starting intelligent payment reminder processing")
        
        reminder_result = {
            "total_due_payments": 0,
            "reminders_sent": 0,
            "reminders_skipped": 0,
            "channels_used": defaultdict(int),
            "errors": []
        }
        
        # Get active reminder configurations
        reminder_configs = self.payment_reminder_repo.get_active_configs(db)
        
        for config in reminder_configs:
            try:
                # Get due payments for this configuration
                due_payments = self.payment_reminder_repo.get_due_payments_for_config(
                    db, config, datetime.utcnow()
                )
                
                reminder_result["total_due_payments"] += len(due_payments)
                
                # Process reminders intelligently
                for payment in due_payments:
                    reminder_sent = await self._send_payment_reminder(db, payment, config)
                    
                    if reminder_sent:
                        reminder_result["reminders_sent"] += 1
                        reminder_result["channels_used"][reminder_sent["channel"]] += 1
                    else:
                        reminder_result["reminders_skipped"] += 1
                        
            except Exception as e:
                error_detail = {
                    "config_id": str(config.id),
                    "error": str(e)
                }
                reminder_result["errors"].append(error_detail)
                logger.error(f"Payment reminder processing failed for config {config.id}: {str(e)}")
        
        logger.info(
            f"Payment reminders completed: {reminder_result['reminders_sent']} sent, "
            f"{reminder_result['reminders_skipped']} skipped"
        )
        
        return reminder_result
    
    async def _process_intelligent_announcements(self, db: Session) -> Dict[str, Any]:
        """Process and deliver scheduled announcements intelligently."""
        logger.info("Starting intelligent announcement processing")
        
        announcement_result = {
            "processed_announcements": 0,
            "delivered_announcements": 0,
            "failed_announcements": 0,
            "recurring_generated": 0,
            "errors": []
        }
        
        now = datetime.utcnow()
        
        # Process due scheduled announcements
        due_schedules = self.announcement_schedule_repo.get_due_schedules(db, now)
        announcement_result["processed_announcements"] = len(due_schedules)
        
        for schedule in due_schedules:
            try:
                # Deliver announcement
                delivery_result = await self._deliver_announcement(db, schedule)
                
                if delivery_result["success"]:
                    announcement_result["delivered_announcements"] += 1
                    # Mark as published
                    self.announcement_schedule_repo.mark_as_published(db, schedule.id, now)
                else:
                    announcement_result["failed_announcements"] += 1
                    
            except Exception as e:
                announcement_result["failed_announcements"] += 1
                error_detail = {
                    "schedule_id": str(schedule.id),
                    "error": str(e)
                }
                announcement_result["errors"].append(error_detail)
        
        # Process recurring announcements
        recurring_templates = self.announcement_schedule_repo.get_active_recurring_templates(db, now)
        
        for template in recurring_templates:
            try:
                if self._is_recurring_due(template, now):
                    new_schedule = self.announcement_schedule_repo.materialize_next_occurrence(
                        db, template, now
                    )
                    announcement_result["recurring_generated"] += 1
                    
            except Exception as e:
                error_detail = {
                    "template_id": str(template.id),
                    "error": str(e)
                }
                announcement_result["errors"].append(error_detail)
        
        logger.info(
            f"Announcement processing completed: {announcement_result['delivered_announcements']} delivered, "
            f"{announcement_result['recurring_generated']} recurring generated"
        )
        
        return announcement_result
    
    async def _run_intelligent_maintenance_scheduling(self, db: Session) -> Dict[str, Any]:
        """Execute intelligent preventive maintenance scheduling."""
        logger.info("Starting intelligent maintenance scheduling")
        
        maintenance_result = {
            "scheduled_executions": 0,
            "completed_executions": 0,
            "failed_executions": 0,
            "optimizations_applied": 0,
            "errors": []
        }
        
        now = datetime.utcnow()
        
        # Get due maintenance schedules
        due_schedules = self.maintenance_schedule_repo.get_due_executions(db, now)
        maintenance_result["scheduled_executions"] = len(due_schedules)
        
        for schedule in due_schedules:
            try:
                # Execute maintenance task
                execution_result = await self._execute_maintenance_schedule(db, schedule)
                
                if execution_result["success"]:
                    maintenance_result["completed_executions"] += 1
                    # Create execution record
                    self.maintenance_schedule_repo.create_execution_record(db, schedule, now)
                else:
                    maintenance_result["failed_executions"] += 1
                    
            except Exception as e:
                maintenance_result["failed_executions"] += 1
                error_detail = {
                    "schedule_id": str(schedule.id),
                    "error": str(e)
                }
                maintenance_result["errors"].append(error_detail)
        
        # Apply intelligent optimizations
        optimizations = await self._optimize_maintenance_schedules(db)
        maintenance_result["optimizations_applied"] = optimizations["count"]
        
        logger.info(
            f"Maintenance scheduling completed: {maintenance_result['completed_executions']} executed, "
            f"{maintenance_result['optimizations_applied']} optimizations applied"
        )
        
        return maintenance_result
    
    async def _run_workflow_engine_optimization(self, db: Session) -> Dict[str, Any]:
        """Optimize workflow engine performance and clean up old data."""
        logger.info("Starting workflow engine optimization")
        
        optimization_result = {
            "cleaned_executions": 0,
            "optimized_workflows": 0,
            "memory_freed_mb": 0,
            "performance_improvements": []
        }
        
        # Clean up old executions
        cleanup_result = workflow_engine._cleanup_old_executions()
        optimization_result["cleaned_executions"] = cleanup_result.get("cleaned_count", 0)
        
        # Optimize workflow definitions
        for workflow_type, definition in workflow_engine.workflows.items():
            try:
                optimizations = await self._optimize_workflow_definition(definition)
                if optimizations:
                    optimization_result["optimized_workflows"] += 1
                    optimization_result["performance_improvements"].extend(optimizations)
                    
            except Exception as e:
                logger.error(f"Failed to optimize workflow {workflow_type}: {str(e)}")
        
        # Calculate memory freed (simplified)
        optimization_result["memory_freed_mb"] = optimization_result["cleaned_executions"] * 0.1
        
        logger.info(
            f"Workflow optimization completed: {optimization_result['cleaned_executions']} executions cleaned, "
            f"{optimization_result['optimized_workflows']} workflows optimized"
        )
        
        return optimization_result
    
    async def _run_comprehensive_data_validation(self, db: Session) -> Dict[str, Any]:
        """Comprehensive data integrity validation across all systems."""
        logger.info("Starting comprehensive data validation")
        
        validation_result = {
            "validations_performed": 0,
            "issues_found": 0,
            "auto_fixes_applied": 0,
            "validation_details": [],
            "critical_issues": []
        }
        
        # Validate booking data integrity
        booking_validation = await self._validate_booking_data_integrity(db)
        validation_result["validation_details"].append(booking_validation)
        validation_result["validations_performed"] += 1
        
        # Validate financial data consistency
        financial_validation = await self._validate_financial_data_consistency(db)
        validation_result["validation_details"].append(financial_validation)
        validation_result["validations_performed"] += 1
        
        # Validate student data completeness
        student_validation = await self._validate_student_data_completeness(db)
        validation_result["validation_details"].append(student_validation)
        validation_result["validations_performed"] += 1
        
        # Validate room assignment consistency
        room_validation = await self._validate_room_assignment_consistency(db)
        validation_result["validation_details"].append(room_validation)
        validation_result["validations_performed"] += 1
        
        # Aggregate results
        for validation in validation_result["validation_details"]:
            validation_result["issues_found"] += validation.get("issues_found", 0)
            validation_result["auto_fixes_applied"] += validation.get("auto_fixes_applied", 0)
            
            if validation.get("critical_issues"):
                validation_result["critical_issues"].extend(validation["critical_issues"])
        
        # Send alerts for critical issues
        if validation_result["critical_issues"]:
            await self._send_critical_issue_alerts(validation_result["critical_issues"])
        
        logger.info(
            f"Data validation completed: {validation_result['issues_found']} issues found, "
            f"{validation_result['auto_fixes_applied']} auto-fixes applied"
        )
        
        return validation_result
    
    async def _monitor_system_performance(self, db: Session) -> Dict[str, Any]:
        """Monitor and optimize system performance in real-time."""
        monitoring_result = {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "active_tasks": len(self.active_executions),
            "database_connections": 0,
            "response_times": {},
            "alerts_generated": []
        }
        
        # Update system metrics
        await self._update_system_metrics()
        monitoring_result.update(self.system_metrics)
        
        # Check for performance issues and generate alerts
        alerts = await self._check_performance_thresholds()
        monitoring_result["alerts_generated"] = alerts
        
        # Apply automatic optimizations if needed
        if monitoring_result["cpu_usage"] > 80:
            await self._apply_cpu_optimization()
        
        if monitoring_result["memory_usage"] > 85:
            await self._apply_memory_optimization()
        
        return monitoring_result
    
    # Helper methods
    
    async def _check_dependencies(self, task_config: TaskConfiguration) -> bool:
        """Check if all task dependencies are satisfied."""
        for dep_task_id in task_config.dependencies:
            # Check if dependency completed successfully recently
            dep_metrics = self.task_metrics.get(dep_task_id)
            if not dep_metrics or not dep_metrics.last_success:
                return False
            
            # Check if dependency ran within acceptable timeframe
            time_since_success = datetime.utcnow() - dep_metrics.last_success
            if time_since_success > timedelta(hours=25):  # For daily tasks
                return False
        
        return True
    
    async def _check_conditions(self, task_config: TaskConfiguration) -> bool:
        """Check if all task execution conditions are met."""
        for condition in task_config.conditions:
            try:
                if not condition():
                    return False
            except Exception as e:
                logger.error(f"Condition check failed for task {task_config.task_id}: {str(e)}")
                return False
        
        return True
    
    async def _check_resource_availability(self, task_config: TaskConfiguration) -> bool:
        """Check if required resources are available."""
        # Simplified resource checking
        required_cpu = task_config.resource_requirements.get("cpu", 0.1)
        required_memory = task_config.resource_requirements.get("memory", "64MB")
        
        # Check CPU availability
        if self.system_metrics["cpu_usage"] + (required_cpu * 100) > 90:
            return False
        
        # Check memory availability (simplified)
        memory_mb = float(required_memory.replace("MB", ""))
        if self.system_metrics["memory_usage"] + (memory_mb / 1024) > 90:
            return False
        
        return True
    
    def _get_priority_value(self, priority: TaskPriority) -> int:
        """Get numeric value for task priority."""
        mapping = {
            TaskPriority.CRITICAL: 4,
            TaskPriority.HIGH: 3,
            TaskPriority.NORMAL: 2,
            TaskPriority.LOW: 1
        }
        return mapping.get(priority, 1)
    
    def _update_task_metrics_success(self, task_id: str, execution_time: float) -> None:
        """Update task metrics after successful execution."""
        metrics = self.task_metrics[task_id]
        
        metrics.total_executions += 1
        metrics.successful_executions += 1
        metrics.last_execution = datetime.utcnow()
        metrics.last_success = datetime.utcnow()
        
        # Update execution time metrics
        metrics.total_execution_time += execution_time
        metrics.average_execution_time = metrics.total_execution_time / metrics.total_executions
        
        # Update failure rate
        metrics.failure_rate = (metrics.failed_executions / metrics.total_executions) * 100
    
    async def _handle_task_failure(
        self,
        task_config: TaskConfiguration,
        execution: TaskExecution,
        failure_type: str,
        exception: Optional[Exception] = None
    ) -> None:
        """Handle task failure with comprehensive error management."""
        # Update metrics
        metrics = self.task_metrics[task_config.task_id]
        metrics.total_executions += 1
        metrics.failed_executions += 1
        metrics.last_execution = datetime.utcnow()
        metrics.last_failure = datetime.utcnow()
        metrics.failure_rate = (metrics.failed_executions / metrics.total_executions) * 100
        
        logger.error(
            f"Task {task_config.task_id} failed ({failure_type}): {execution.error}"
        )
        
        # Send failure notification if configured
        if task_config.notification_on_failure:
            await self._send_task_failure_notification(task_config, execution, failure_type)
        
        # Check if task is consistently failing
        if metrics.failure_rate > 50 and metrics.total_executions > 5:
            await self._handle_consistently_failing_task(task_config, metrics)
    
    # Condition check methods
    
    def _check_maintenance_window(self) -> bool:
        """Check if we're in a maintenance window."""
        now = datetime.utcnow()
        # Maintenance window: 1 AM to 5 AM UTC
        return 1 <= now.hour <= 5
    
    def _check_low_system_load(self) -> bool:
        """Check if system load is low enough for optimization tasks."""
        return self.system_metrics["cpu_usage"] < 50 and len(self.active_executions) < 5
    
    # Additional helper methods would continue here...
    
    async def _update_system_metrics(self) -> None:
        """Update system performance metrics."""
        # This would integrate with actual system monitoring
        import psutil
        
        self.system_metrics.update({
            "cpu_usage": psutil.cpu_percent(interval=1),
            "memory_usage": psutil.virtual_memory().percent,
            "active_tasks": len(self.active_executions),
            "queue_depth": sum(len(queue) for queue in self._delivery_queues.values()) if hasattr(self, '_delivery_queues') else 0
        })
    
    async def _check_performance_thresholds(self) -> List[str]:
        """Check performance thresholds and generate alerts."""
        alerts = []
        
        if self.system_metrics["cpu_usage"] > 90:
            alerts.append("HIGH_CPU_USAGE")
        
        if self.system_metrics["memory_usage"] > 90:
            alerts.append("HIGH_MEMORY_USAGE")
        
        if len(self.active_executions) > 20:
            alerts.append("HIGH_TASK_CONCURRENCY")
        
        return alerts
    
    # Public API methods
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive status for a specific task."""
        if task_id not in self.task_configs:
            return None
        
        config = self.task_configs[task_id]
        metrics = self.task_metrics[task_id]
        next_execution = self.task_schedules.get(task_id)
        
        # Get active executions for this task
        active_executions = [
            exec.to_dict() for exec in self.active_executions.values()
            if exec.task_id == task_id
        ]
        
        return {
            "task_id": task_id,
            "name": config.name,
            "description": config.description,
            "frequency": config.frequency.value,
            "priority": config.priority.value,
            "enabled": config.enabled,
            "next_execution": next_execution.isoformat() if next_execution else None,
            "metrics": {
                "total_executions": metrics.total_executions,
                "successful_executions": metrics.successful_executions,
                "failed_executions": metrics.failed_executions,
                "failure_rate": metrics.failure_rate,
                "average_execution_time": metrics.average_execution_time,
                "last_execution": metrics.last_execution.isoformat() if metrics.last_execution else None,
                "last_success": metrics.last_success.isoformat() if metrics.last_success else None,
                "last_failure": metrics.last_failure.isoformat() if metrics.last_failure else None
            },
            "active_executions": active_executions,
            "resource_requirements": config.resource_requirements
        }
    
    def get_system_overview(self) -> Dict[str, Any]:
        """Get comprehensive system overview."""
        return {
            "system_metrics": self.system_metrics,
            "total_registered_tasks": len(self.task_configs),
            "enabled_tasks": sum(1 for config in self.task_configs.values() if config.enabled),
            "active_executions": len(self.active_executions),
            "task_summary": {
                task_id: {
                    "enabled": config.enabled,
                    "frequency": config.frequency.value,
                    "next_execution": self.task_schedules.get(task_id).isoformat() if self.task_schedules.get(task_id) else None,
                    "total_executions": self.task_metrics[task_id].total_executions,
                    "failure_rate": self.task_metrics[task_id].failure_rate
                }
                for task_id, config in self.task_configs.items()
            }
        }
    
    def enable_task(self, task_id: str) -> bool:
        """Enable a task."""
        if task_id in self.task_configs:
            self.task_configs[task_id].enabled = True
            self._schedule_next_execution(self.task_configs[task_id])
            return True
        return False
    
    def disable_task(self, task_id: str) -> bool:
        """Disable a task."""
        if task_id in self.task_configs:
            self.task_configs[task_id].enabled = False
            # Remove from schedule
            if task_id in self.task_schedules:
                del self.task_schedules[task_id]
            return True
        return False
    
    async def trigger_task_manually(self, task_id: str) -> Dict[str, Any]:
        """Manually trigger a task execution."""
        if task_id not in self.task_configs:
            raise ValueError(f"Task {task_id} not found")
        
        task_config = self.task_configs[task_id]
        
        # Execute task immediately
        execution = TaskExecution(
            execution_id=str(uuid4()),
            task_id=task_id,
            started_at=datetime.utcnow()
        )
        
        self.active_executions[execution.execution_id] = execution
        
        # Execute in background
        asyncio.create_task(self._execute_task_safely(task_config, execution))
        
        return {
            "execution_id": execution.execution_id,
            "task_id": task_id,
            "triggered_at": execution.started_at.isoformat(),
            "status": "triggered"
        }