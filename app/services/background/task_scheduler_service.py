# task_scheduler_service.py

from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import logging
from enum import Enum
import uuid
from croniter import croniter
import heapq
from contextlib import contextmanager

class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3

class TaskStatus(Enum):
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"

@dataclass
class TaskDefinition:
    """Task definition with scheduling parameters"""
    task_id: str
    name: str
    handler: Callable
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    priority: TaskPriority = TaskPriority.NORMAL
    timeout_seconds: int = 300
    max_retries: int = 3
    retry_delay_seconds: int = 60
    dependencies: List[str] = None
    metadata: Dict[str, Any] = None

    @classmethod
    def create(
        cls,
        name: str,
        handler: Callable,
        **kwargs: Any
    ) -> 'TaskDefinition':
        return cls(
            task_id=str(uuid.uuid4()),
            name=name,
            handler=handler,
            dependencies=[],
            metadata={},
            **kwargs
        )

@dataclass
class TaskExecution:
    """Task execution instance"""
    execution_id: str
    task_id: str
    status: TaskStatus
    scheduled_time: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = None

class CronEngine:
    """Handles cron-based task scheduling"""
    
    def __init__(self):
        self._schedules: Dict[str, croniter] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_schedule(
        self,
        task_id: str,
        cron_expression: str
    ) -> None:
        """Add cron schedule for task"""
        try:
            self._schedules[task_id] = croniter(cron_expression, datetime.utcnow())
            self.logger.info(f"Added schedule for task {task_id}: {cron_expression}")
        except Exception as e:
            self.logger.error(f"Invalid cron expression for task {task_id}: {str(e)}")
            raise

    def get_next_execution(self, task_id: str) -> Optional[datetime]:
        """Get next execution time for task"""
        cron = self._schedules.get(task_id)
        if cron:
            return cron.get_next(datetime)
        return None

    def update_schedule(
        self,
        task_id: str,
        cron_expression: str
    ) -> None:
        """Update task schedule"""
        self.add_schedule(task_id, cron_expression)

class TaskQueue:
    """Priority queue for task execution"""
    
    def __init__(self):
        self._queue: List[tuple[int, datetime, TaskDefinition]] = []
        self._tasks: Dict[str, TaskDefinition] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    async def enqueue(
        self,
        task: TaskDefinition,
        scheduled_time: datetime
    ) -> None:
        """Add task to queue"""
        self._tasks[task.task_id] = task
        heapq.heappush(
            self._queue,
            (task.priority.value, scheduled_time, task)
        )
        self.logger.debug(f"Enqueued task {task.task_id} for {scheduled_time}")

    async def dequeue(self) -> Optional[tuple[TaskDefinition, datetime]]:
        """Get next task from queue"""
        if not self._queue:
            return None

        _, scheduled_time, task = heapq.heappop(self._queue)
        return task, scheduled_time

    def remove_task(self, task_id: str) -> None:
        """Remove task from queue"""
        self._tasks.pop(task_id, None)
        self._queue = [
            (p, t, task) for p, t, task in self._queue
            if task.task_id != task_id
        ]
        heapq.heapify(self._queue)

class DependencyResolver:
    """Resolves task dependencies"""
    
    def __init__(self):
        self._dependencies: Dict[str, List[str]] = {}
        self._completed_tasks: Set[str] = set()
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_dependencies(
        self,
        task_id: str,
        dependencies: List[str]
    ) -> None:
        """Add task dependencies"""
        self._dependencies[task_id] = dependencies
        self.logger.info(f"Added dependencies for task {task_id}: {dependencies}")

    def mark_completed(self, task_id: str) -> None:
        """Mark task as completed"""
        self._completed_tasks.add(task_id)

    def can_execute(self, task_id: str) -> bool:
        """Check if task dependencies are satisfied"""
        dependencies = self._dependencies.get(task_id, [])
        return all(dep in self._completed_tasks for dep in dependencies)

class PriorityManager:
    """Manages task priorities"""
    
    def __init__(self):
        self._priority_rules: List[Callable] = []
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_rule(self, rule: Callable) -> None:
        """Add priority calculation rule"""
        self._priority_rules.append(rule)
        self.logger.info(f"Added priority rule: {rule.__name__}")

    async def calculate_priority(
        self,
        task: TaskDefinition
    ) -> TaskPriority:
        """Calculate task priority"""
        priority = task.priority
        
        for rule in self._priority_rules:
            try:
                new_priority = await rule(task)
                if new_priority.value > priority.value:
                    priority = new_priority
            except Exception as e:
                self.logger.error(f"Priority rule error: {str(e)}")
        
        return priority

class RetryHandler:
    """Handles task retry logic"""
    
    def __init__(self):
        self._retry_strategies: Dict[str, Callable] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_strategy(
        self,
        strategy_name: str,
        strategy: Callable
    ) -> None:
        """Add retry strategy"""
        self._retry_strategies[strategy_name] = strategy
        self.logger.info(f"Added retry strategy: {strategy_name}")

    async def should_retry(
        self,
        task: TaskDefinition,
        execution: TaskExecution
    ) -> bool:
        """Determine if task should be retried"""
        if execution.retry_count >= task.max_retries:
            return False

        strategy = self._retry_strategies.get(task.metadata.get('retry_strategy'))
        if strategy:
            return await strategy(task, execution)
        
        return True

    async def get_retry_delay(
        self,
        task: TaskDefinition,
        execution: TaskExecution
    ) -> int:
        """Calculate retry delay"""
        base_delay = task.retry_delay_seconds
        return base_delay * (2 ** execution.retry_count)  # Exponential backoff

class TaskMonitor:
    """Monitors task execution and health"""
    
    def __init__(self):
        self._executions: Dict[str, List[TaskExecution]] = {}
        self._active_tasks: Dict[str, TaskExecution] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def start_execution(
        self,
        task: TaskDefinition,
        scheduled_time: datetime
    ) -> TaskExecution:
        """Record task execution start"""
        execution = TaskExecution(
            execution_id=str(uuid.uuid4()),
            task_id=task.task_id,
            status=TaskStatus.RUNNING,
            scheduled_time=scheduled_time,
            start_time=datetime.utcnow(),
            metadata={}
        )
        
        if task.task_id not in self._executions:
            self._executions[task.task_id] = []
        
        self._executions[task.task_id].append(execution)
        self._active_tasks[task.task_id] = execution
        
        return execution

    def complete_execution(
        self,
        execution: TaskExecution,
        result: Any = None,
        error: Optional[str] = None
    ) -> None:
        """Record task execution completion"""
        execution.end_time = datetime.utcnow()
        execution.result = result
        execution.error = error
        execution.status = TaskStatus.COMPLETED if not error else TaskStatus.FAILED
        
        self._active_tasks.pop(execution.task_id, None)

    def get_task_stats(
        self,
        task_id: str
    ) -> Dict[str, Any]:
        """Get task execution statistics"""
        executions = self._executions.get(task_id, [])
        total = len(executions)
        failed = sum(1 for e in executions if e.status == TaskStatus.FAILED)
        avg_duration = 0
        
        if executions:
            durations = [
                (e.end_time - e.start_time).total_seconds()
                for e in executions
                if e.end_time and e.start_time
            ]
            if durations:
                avg_duration = sum(durations) / len(durations)
        
        return {
            'total_executions': total,
            'failed_executions': failed,
            'success_rate': (total - failed) / total if total > 0 else 0,
            'average_duration': avg_duration,
            'last_execution': executions[-1] if executions else None
        }

class TaskScheduler:
    """Core task scheduling engine"""
    
    def __init__(self):
        self.cron_engine = CronEngine()
        self.queue = TaskQueue()
        self.dependencies = DependencyResolver()
        self.priority_manager = PriorityManager()
        self.retry_handler = RetryHandler()
        self.monitor = TaskMonitor()
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self.logger = logging.getLogger(self.__class__.__name__)

    async def schedule_task(
        self,
        task: TaskDefinition
    ) -> None:
        """Schedule a task"""
        if task.cron_expression:
            self.cron_engine.add_schedule(task.task_id, task.cron_expression)
        
        if task.dependencies:
            self.dependencies.add_dependencies(task.task_id, task.dependencies)
        
        next_execution = (
            self.cron_engine.get_next_execution(task.task_id)
            if task.cron_expression
            else datetime.utcnow() + timedelta(seconds=task.interval_seconds or 0)
        )
        
        await self.queue.enqueue(task, next_execution)
        self.logger.info(f"Scheduled task {task.task_id} for {next_execution}")

    async def start(self) -> None:
        """Start task scheduler"""
        self._running = True
        self._scheduler_task = asyncio.create_task(self._run_scheduler())
        self.logger.info("Task scheduler started")

    async def stop(self) -> None:
        """Stop task scheduler"""
        self._running = False
        if self._scheduler_task:
            await self._scheduler_task
        self.logger.info("Task scheduler stopped")

    async def _run_scheduler(self) -> None:
        """Main scheduler loop"""
        while self._running:
            try:
                task_tuple = await self.queue.dequeue()
                if not task_tuple:
                    await asyncio.sleep(1)
                    continue

                task, scheduled_time = task_tuple
                
                if datetime.utcnow() < scheduled_time:
                    await self.queue.enqueue(task, scheduled_time)
                    await asyncio.sleep(1)
                    continue

                if not self.dependencies.can_execute(task.task_id):
                    await self.queue.enqueue(
                        task,
                        datetime.utcnow() + timedelta(seconds=60)
                    )
                    continue

                await self._execute_task(task, scheduled_time)
            except Exception as e:
                self.logger.error(f"Scheduler error: {str(e)}")
                await asyncio.sleep(1)

    async def _execute_task(
        self,
        task: TaskDefinition,
        scheduled_time: datetime
    ) -> None:
        """Execute a task"""
        execution = self.monitor.start_execution(task, scheduled_time)
        
        try:
            result = await asyncio.wait_for(
                task.handler(),
                timeout=task.timeout_seconds
            )
            self.monitor.complete_execution(execution, result=result)
            self.dependencies.mark_completed(task.task_id)
            
            # Schedule next execution if needed
            if task.cron_expression or task.interval_seconds:
                next_time = (
                    self.cron_engine.get_next_execution(task.task_id)
                    if task.cron_expression
                    else datetime.utcnow() + timedelta(seconds=task.interval_seconds)
                )
                await self.queue.enqueue(task, next_time)
        except Exception as e:
            self.monitor.complete_execution(execution, error=str(e))
            
            if await self.retry_handler.should_retry(task, execution):
                delay = await self.retry_handler.get_retry_delay(task, execution)
                execution.retry_count += 1
                await self.queue.enqueue(
                    task,
                    datetime.utcnow() + timedelta(seconds=delay)
                )
            else:
                self.logger.error(
                    f"Task {task.task_id} failed after {execution.retry_count} retries"
                )

class TaskSchedulerService:
    """Main task scheduler service interface"""
    
    def __init__(self):
        self.scheduler = TaskScheduler()
        self.logger = logging.getLogger(self.__class__.__name__)

    async def start(self) -> None:
        """Start scheduler service"""
        await self.scheduler.start()

    async def stop(self) -> None:
        """Stop scheduler service"""
        await self.scheduler.stop()

    async def schedule_task(
        self,
        name: str,
        handler: Callable,
        cron_expression: Optional[str] = None,
        interval_seconds: Optional[int] = None,
        **kwargs: Any
    ) -> TaskDefinition:
        """Schedule a new task"""
        task = TaskDefinition.create(
            name=name,
            handler=handler,
            cron_expression=cron_expression,
            interval_seconds=interval_seconds,
            **kwargs
        )
        await self.scheduler.schedule_task(task)
        return task

    def add_retry_strategy(
        self,
        strategy_name: str,
        strategy: Callable
    ) -> None:
        """Add custom retry strategy"""
        self.scheduler.retry_handler.add_strategy(strategy_name, strategy)

    def add_priority_rule(self, rule: Callable) -> None:
        """Add custom priority rule"""
        self