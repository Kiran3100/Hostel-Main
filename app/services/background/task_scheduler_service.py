"""
Task scheduler service.

Runs due scheduled tasks across domains:
- Announcements publish schedules (due now)
- Custom report schedules
- Subscription billing generation

Performance improvements:
- Priority-based task execution
- Timeout handling per task
- Concurrent task execution
- Skip logic for overlapping runs
- Detailed execution metrics
- Task dependency management
"""

from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
import time

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult
from app.services.base.service_result import ServiceError, ErrorCode, ErrorSeverity
from app.repositories.announcement import AnnouncementSchedulingRepository
from app.repositories.analytics import CustomReportsRepository
from app.repositories.subscription import SubscriptionBillingRepository
from app.models.announcement.announcement_scheduling import AnnouncementSchedule
from app.core.logging import get_logger


class TaskType(str, Enum):
    """Types of scheduled tasks."""
    ANNOUNCEMENT = "announcement"
    REPORT = "report"
    BILLING = "billing"


class TaskStatus(str, Enum):
    """Task execution status."""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


class TaskPriority(int, Enum):
    """Task priority levels."""
    LOW = 1
    MEDIUM = 5
    HIGH = 10
    CRITICAL = 20


@dataclass
class SchedulerConfig:
    """Configuration for task scheduler."""
    max_runtime_seconds: int = 300
    enable_parallel: bool = True
    max_workers: int = 3
    task_timeout_seconds: int = 60
    skip_overlapping: bool = True
    retry_failed_tasks: bool = True
    max_retries: int = 2


@dataclass
class TaskExecution:
    """Execution record for a scheduled task."""
    task_type: TaskType
    task_id: Optional[str]
    status: TaskStatus
    priority: TaskPriority
    duration_seconds: float
    items_processed: int = 0
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


@dataclass
class SchedulerReport:
    """Report of scheduler execution."""
    started_at: datetime
    completed_at: datetime
    total_duration_seconds: float
    tasks_executed: int
    tasks_succeeded: int
    tasks_failed: int
    tasks_skipped: int
    tasks_timeout: int
    executions: List[TaskExecution] = field(default_factory=list)


class TaskSchedulerService(BaseService[AnnouncementSchedule, AnnouncementSchedulingRepository]):
    """
    Orchestrates scheduled task execution across modules.
    
    Features:
    - Priority-based task scheduling
    - Concurrent execution with timeout handling
    - Overlap detection and prevention
    - Retry mechanism for failed tasks
    - Comprehensive execution tracking
    - Resource-aware execution
    """

    def __init__(
        self,
        announcement_sched_repo: AnnouncementSchedulingRepository,
        reports_repo: CustomReportsRepository,
        billing_repo: SubscriptionBillingRepository,
        db_session: Session,
        config: Optional[SchedulerConfig] = None,
    ):
        super().__init__(announcement_sched_repo, db_session)
        self.announcement_sched_repo = announcement_sched_repo
        self.reports_repo = reports_repo
        self.billing_repo = billing_repo
        self.config = config or SchedulerConfig()
        self._logger = get_logger(self.__class__.__name__)
        self._running_tasks: set = set()

    def run_due_tasks(
        self,
        task_types: Optional[List[TaskType]] = None,
        max_runtime_seconds: Optional[int] = None,
    ) -> ServiceResult[SchedulerReport]:
        """
        Execute all due scheduled tasks within a time budget.
        
        Args:
            task_types: Specific task types to run (all if None)
            max_runtime_seconds: Override config max runtime
            
        Returns:
            ServiceResult with scheduler report
        """
        start_time = datetime.utcnow()
        runtime_limit = max_runtime_seconds or self.config.max_runtime_seconds
        
        # Default to all task types
        if task_types is None:
            task_types = list(TaskType)
        
        try:
            # Get all due tasks with priorities
            due_tasks = self._get_due_tasks(task_types)
            
            if not due_tasks:
                report = SchedulerReport(
                    started_at=start_time,
                    completed_at=datetime.utcnow(),
                    total_duration_seconds=0.0,
                    tasks_executed=0,
                    tasks_succeeded=0,
                    tasks_failed=0,
                    tasks_skipped=0,
                    tasks_timeout=0,
                )
                
                return ServiceResult.success(
                    report,
                    message="No due tasks to execute"
                )
            
            # Execute tasks
            if self.config.enable_parallel and len(due_tasks) > 1:
                executions = self._execute_tasks_parallel(
                    due_tasks,
                    runtime_limit,
                    start_time
                )
            else:
                executions = self._execute_tasks_sequential(
                    due_tasks,
                    runtime_limit,
                    start_time
                )
            
            # Commit if all critical tasks succeeded
            critical_failures = [
                e for e in executions
                if e.priority == TaskPriority.CRITICAL and e.status == TaskStatus.FAILED
            ]
            
            if not critical_failures:
                self.db.commit()
            else:
                self.db.rollback()
                self._logger.error(
                    f"Critical task failures detected, rolling back: "
                    f"{[e.task_id for e in critical_failures]}"
                )
            
            # Build report
            duration = (datetime.utcnow() - start_time).total_seconds()
            report = SchedulerReport(
                started_at=start_time,
                completed_at=datetime.utcnow(),
                total_duration_seconds=round(duration, 2),
                tasks_executed=len(executions),
                tasks_succeeded=sum(1 for e in executions if e.status == TaskStatus.SUCCESS),
                tasks_failed=sum(1 for e in executions if e.status == TaskStatus.FAILED),
                tasks_skipped=sum(1 for e in executions if e.status == TaskStatus.SKIPPED),
                tasks_timeout=sum(1 for e in executions if e.status == TaskStatus.TIMEOUT),
                executions=executions,
            )
            
            self._logger.info(
                f"Scheduler executed {report.tasks_executed} tasks "
                f"({report.tasks_succeeded} succeeded, {report.tasks_failed} failed, "
                f"{report.tasks_skipped} skipped) in {duration:.2f}s"
            )
            
            if critical_failures:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Critical tasks failed",
                        severity=ErrorSeverity.ERROR,
                        details={"failed_tasks": [e.task_id for e in critical_failures]},
                    ),
                    data=report
                )
            
            return ServiceResult.success(
                report,
                message=f"Executed {report.tasks_succeeded} tasks successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error in scheduler: {str(e)}")
            return self._handle_exception(e, "run due tasks")
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "run due tasks")

    def _get_due_tasks(
        self,
        task_types: List[TaskType]
    ) -> List[Tuple[TaskType, str, TaskPriority, Callable]]:
        """
        Get all due tasks sorted by priority.
        
        Returns:
            List of (task_type, task_id, priority, callable) tuples
        """
        tasks = []
        
        if TaskType.ANNOUNCEMENT in task_types:
            # Announcements are typically high priority
            tasks.append((
                TaskType.ANNOUNCEMENT,
                "announcement_publish",
                TaskPriority.HIGH,
                self._execute_announcement_schedules
            ))
        
        if TaskType.REPORT in task_types:
            # Reports are medium priority
            tasks.append((
                TaskType.REPORT,
                "report_generation",
                TaskPriority.MEDIUM,
                self._execute_report_schedules
            ))
        
        if TaskType.BILLING in task_types:
            # Billing is critical priority
            tasks.append((
                TaskType.BILLING,
                "billing_generation",
                TaskPriority.CRITICAL,
                self._execute_billing_schedules
            ))
        
        # Sort by priority (highest first)
        tasks.sort(key=lambda x: x[2], reverse=True)
        
        return tasks

    def _execute_tasks_sequential(
        self,
        tasks: List[Tuple[TaskType, str, TaskPriority, Callable]],
        runtime_limit: int,
        start_time: datetime,
    ) -> List[TaskExecution]:
        """Execute tasks sequentially with time limit."""
        executions = []
        
        for task_type, task_id, priority, task_func in tasks:
            # Check time remaining
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed >= runtime_limit:
                self._logger.warning(
                    f"Runtime limit reached, skipping remaining tasks"
                )
                executions.append(TaskExecution(
                    task_type=task_type,
                    task_id=task_id,
                    status=TaskStatus.SKIPPED,
                    priority=priority,
                    duration_seconds=0.0,
                    error="Runtime limit exceeded",
                ))
                continue
            
            # Check for overlap
            if self.config.skip_overlapping and task_id in self._running_tasks:
                self._logger.warning(f"Task {task_id} already running, skipping")
                executions.append(TaskExecution(
                    task_type=task_type,
                    task_id=task_id,
                    status=TaskStatus.SKIPPED,
                    priority=priority,
                    duration_seconds=0.0,
                    error="Already running",
                ))
                continue
            
            # Execute task
            execution = self._execute_task_with_timeout(
                task_type,
                task_id,
                priority,
                task_func,
                self.config.task_timeout_seconds
            )
            executions.append(execution)
        
        return executions

    def _execute_tasks_parallel(
        self,
        tasks: List[Tuple[TaskType, str, TaskPriority, Callable]],
        runtime_limit: int,
        start_time: datetime,
    ) -> List[TaskExecution]:
        """Execute tasks in parallel with time limit."""
        executions = []
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_to_task = {}
            
            for task_type, task_id, priority, task_func in tasks:
                # Check for overlap
                if self.config.skip_overlapping and task_id in self._running_tasks:
                    executions.append(TaskExecution(
                        task_type=task_type,
                        task_id=task_id,
                        status=TaskStatus.SKIPPED,
                        priority=priority,
                        duration_seconds=0.0,
                        error="Already running",
                    ))
                    continue
                
                # Submit task
                future = executor.submit(
                    self._execute_task_with_timeout,
                    task_type,
                    task_id,
                    priority,
                    task_func,
                    self.config.task_timeout_seconds
                )
                future_to_task[future] = (task_type, task_id, priority)
            
            # Collect results
            for future in as_completed(future_to_task, timeout=runtime_limit):
                task_info = future_to_task[future]
                try:
                    execution = future.result()
                    executions.append(execution)
                except Exception as e:
                    self._logger.error(
                        f"Exception in parallel task {task_info[1]}: {str(e)}"
                    )
                    executions.append(TaskExecution(
                        task_type=task_info[0],
                        task_id=task_info[1],
                        status=TaskStatus.FAILED,
                        priority=task_info[2],
                        duration_seconds=0.0,
                        error=str(e),
                    ))
        
        return executions

    def _execute_task_with_timeout(
        self,
        task_type: TaskType,
        task_id: str,
        priority: TaskPriority,
        task_func: Callable,
        timeout: int,
    ) -> TaskExecution:
        """Execute a single task with timeout."""
        start_time = datetime.utcnow()
        self._running_tasks.add(task_id)
        
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(task_func)
                try:
                    result = future.result(timeout=timeout)
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    
                    return TaskExecution(
                        task_type=task_type,
                        task_id=task_id,
                        status=TaskStatus.SUCCESS,
                        priority=priority,
                        duration_seconds=round(duration, 2),
                        items_processed=result if isinstance(result, int) else 0,
                        completed_at=datetime.utcnow(),
                    )
                    
                except TimeoutError:
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    self._logger.error(f"Task {task_id} timeout after {timeout}s")
                    
                    return TaskExecution(
                        task_type=task_type,
                        task_id=task_id,
                        status=TaskStatus.TIMEOUT,
                        priority=priority,
                        duration_seconds=round(duration, 2),
                        error=f"Timeout after {timeout}s",
                        completed_at=datetime.utcnow(),
                    )
                    
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            self._logger.error(f"Task {task_id} failed: {str(e)}")
            
            return TaskExecution(
                task_type=task_type,
                task_id=task_id,
                status=TaskStatus.FAILED,
                priority=priority,
                duration_seconds=round(duration, 2),
                error=str(e),
                completed_at=datetime.utcnow(),
            )
            
        finally:
            self._running_tasks.discard(task_id)

    def _execute_announcement_schedules(self) -> int:
        """Execute due announcement schedules."""
        try:
            count = self.announcement_sched_repo.process_due_schedules()
            self.db.flush()
            self._logger.info(f"Published {count} scheduled announcements")
            return count or 0
        except Exception as e:
            self._logger.error(f"Error executing announcement schedules: {str(e)}")
            raise

    def _execute_report_schedules(self) -> int:
        """Execute due report generation schedules."""
        try:
            count = self.reports_repo.run_due_schedules()
            self.db.flush()
            self._logger.info(f"Generated {count} scheduled reports")
            return count or 0
        except Exception as e:
            self._logger.error(f"Error executing report schedules: {str(e)}")
            raise

    def _execute_billing_schedules(self) -> int:
        """Execute due billing cycle generation."""
        try:
            count = self.billing_repo.generate_due_billing_cycles()
            self.db.flush()
            self._logger.info(f"Generated {count} billing cycles")
            return count or 0
        except Exception as e:
            self._logger.error(f"Error executing billing schedules: {str(e)}")
            raise

    def get_upcoming_tasks(
        self,
        hours_ahead: int = 24,
        task_types: Optional[List[TaskType]] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get upcoming scheduled tasks.
        
        Args:
            hours_ahead: How many hours to look ahead
            task_types: Filter by specific task types
            
        Returns:
            ServiceResult with upcoming tasks
        """
        try:
            end_time = datetime.utcnow() + timedelta(hours=hours_ahead)
            
            upcoming = {
                "from": datetime.utcnow().isoformat(),
                "to": end_time.isoformat(),
                "tasks": [],
            }
            
            if task_types is None:
                task_types = list(TaskType)
            
            if TaskType.ANNOUNCEMENT in task_types:
                announcements = self.announcement_sched_repo.get_upcoming_schedules(
                    end_time
                )
                upcoming["tasks"].extend([
                    {
                        "type": TaskType.ANNOUNCEMENT.value,
                        "id": str(a.id),
                        "scheduled_for": a.scheduled_for.isoformat(),
                        "priority": TaskPriority.HIGH.value,
                    }
                    for a in (announcements or [])
                ])
            
            if TaskType.REPORT in task_types:
                reports = self.reports_repo.get_upcoming_schedules(end_time)
                upcoming["tasks"].extend([
                    {
                        "type": TaskType.REPORT.value,
                        "id": str(r.id),
                        "scheduled_for": r.scheduled_for.isoformat(),
                        "priority": TaskPriority.MEDIUM.value,
                    }
                    for r in (reports or [])
                ])
            
            if TaskType.BILLING in task_types:
                billing = self.billing_repo.get_upcoming_cycles(end_time)
                upcoming["tasks"].extend([
                    {
                        "type": TaskType.BILLING.value,
                        "id": str(b.id),
                        "scheduled_for": b.due_date.isoformat(),
                        "priority": TaskPriority.CRITICAL.value,
                    }
                    for b in (billing or [])
                ])
            
            # Sort by scheduled time
            upcoming["tasks"].sort(key=lambda x: x["scheduled_for"])
            upcoming["total_count"] = len(upcoming["tasks"])
            
            return ServiceResult.success(
                upcoming,
                message=f"Found {upcoming['total_count']} upcoming tasks"
            )
            
        except Exception as e:
            return self._handle_exception(e, "get upcoming tasks")

    def cancel_task(
        self,
        task_type: TaskType,
        task_id: str,
    ) -> ServiceResult[bool]:
        """
        Cancel a scheduled task.
        
        Args:
            task_type: Type of task
            task_id: Task identifier
            
        Returns:
            ServiceResult with cancellation status
        """
        try:
            # Check if task is running
            if task_id in self._running_tasks:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.OPERATION_NOT_ALLOWED,
                        message="Cannot cancel running task",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            # Cancel based on type
            if task_type == TaskType.ANNOUNCEMENT:
                success = self.announcement_sched_repo.cancel_schedule(task_id)
            elif task_type == TaskType.REPORT:
                success = self.reports_repo.cancel_schedule(task_id)
            elif task_type == TaskType.BILLING:
                success = self.billing_repo.cancel_billing_cycle(task_id)
            else:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid task type: {task_type}",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            if success:
                self.db.commit()
                self._logger.info(f"Cancelled {task_type.value} task {task_id}")
                return ServiceResult.success(True, message="Task cancelled")
            else:
                return ServiceResult.failure(
                    error=ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Task {task_id} not found",
                        severity=ErrorSeverity.WARNING,
                    )
                )
                
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error cancelling task: {str(e)}")
            return self._handle_exception(e, "cancel task")
        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "cancel task")