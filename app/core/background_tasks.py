"""
Background Task Management

Comprehensive background task system with Redis/Celery integration,
task scheduling, monitoring, and retry mechanisms.
"""

import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional, Callable, Union
from datetime import datetime, timedelta
from functools import wraps
from enum import Enum
from contextlib import asynccontextmanager

import redis.asyncio as redis
from celery import Celery
from celery.result import AsyncResult
from celery.schedules import crontab

from .config import settings
from .exceptions import TaskExecutionError, TaskTimeoutError, TaskRetryExhaustedError
from .logging import get_logger

logger = get_logger(__name__)


class TaskStatus(str, Enum):
    """Task status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    REVOKED = "revoked"


class TaskPriority(str, Enum):
    """Task priority enumeration"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskResult:
    """Task result container"""
    
    def __init__(
        self,
        task_id: str,
        status: TaskStatus,
        result: Any = None,
        error: Optional[str] = None,
        traceback: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        retries: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.task_id = task_id
        self.status = status
        self.result = result
        self.error = error
        self.traceback = traceback
        self.started_at = started_at
        self.completed_at = completed_at
        self.retries = retries
        self.metadata = metadata or {}
    
    @property
    def execution_time(self) -> Optional[float]:
        """Calculate execution time if task is completed"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "traceback": self.traceback,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time": self.execution_time,
            "retries": self.retries,
            "metadata": self.metadata
        }


class BackgroundTaskManager:
    """Main background task manager"""
    
    def __init__(self):
        self.celery_app: Optional[Celery] = None
        self.redis_client: Optional[redis.Redis] = None
        self._initialized = False
        self._registered_tasks: Dict[str, Callable] = {}
        self._task_configs: Dict[str, Dict[str, Any]] = {}
    
    async def initialize(self):
        """Initialize background task system"""
        if self._initialized:
            return
        
        try:
            # Initialize Redis client
            self.redis_client = redis.Redis.from_url(
                settings.redis.redis_url,
                decode_responses=True
            )
            await self.redis_client.ping()
            
            # Initialize Celery if configured
            if settings.tasks.TASK_BACKEND == "redis":
                self._initialize_celery()
            
            self._initialized = True
            logger.info("Background task manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize background task manager: {str(e)}")
            raise TaskExecutionError(f"Task manager initialization failed: {str(e)}")
    
    def _initialize_celery(self):
        """Initialize Celery application"""
        broker_url = settings.tasks.TASK_BROKER_URL or settings.redis.redis_url
        result_backend = settings.tasks.TASK_RESULT_BACKEND or settings.redis.redis_url
        
        self.celery_app = Celery(
            'hostel_tasks',
            broker=broker_url,
            backend=result_backend,
            include=['app.tasks']  # Task modules
        )
        
        # Configure Celery
        self.celery_app.conf.update(
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='UTC',
            enable_utc=True,
            task_track_started=True,
            task_time_limit=settings.tasks.TASK_TIMEOUT,
            task_soft_time_limit=settings.tasks.TASK_TIMEOUT - 30,
            worker_prefetch_multiplier=1,
            task_acks_late=True,
            worker_disable_rate_limits=False,
            task_compression='gzip',
            result_compression='gzip',
            task_routes={
                'app.tasks.high_priority.*': {'queue': settings.tasks.HIGH_PRIORITY_QUEUE},
                'app.tasks.low_priority.*': {'queue': settings.tasks.LOW_PRIORITY_QUEUE},
            }
        )
        
        # Configure periodic tasks
        if settings.tasks.ENABLE_PERIODIC_TASKS:
            self._configure_periodic_tasks()
    
    def _configure_periodic_tasks(self):
        """Configure periodic/scheduled tasks"""
        self.celery_app.conf.beat_schedule = {
            'cleanup-expired-tasks': {
                'task': 'app.tasks.cleanup_expired_tasks',
                'schedule': crontab(minute=0),  # Every hour
            },
            'generate-daily-reports': {
                'task': 'app.tasks.generate_daily_reports',
                'schedule': crontab(hour=6, minute=0),  # 6 AM daily
            },
            'refresh-dashboard-cache': {
                'task': 'app.tasks.refresh_dashboard_cache',
                'schedule': crontab(minute='*/15'),  # Every 15 minutes
            },
            'send-notification-digest': {
                'task': 'app.tasks.send_notification_digest',
                'schedule': crontab(hour=9, minute=0),  # 9 AM daily
            }
        }
    
    def register_task(
        self,
        name: str,
        func: Callable,
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
        retry_delay: int = 60,
        timeout: Optional[int] = None,
        queue: Optional[str] = None
    ):
        """Register a task function"""
        self._registered_tasks[name] = func
        self._task_configs[name] = {
            'priority': priority,
            'max_retries': max_retries,
            'retry_delay': retry_delay,
            'timeout': timeout or settings.tasks.TASK_TIMEOUT,
            'queue': queue or settings.tasks.DEFAULT_QUEUE
        }
        
        logger.info(f"Registered task: {name}")
    
    async def enqueue_task(
        self,
        task_name: str,
        *args,
        priority: Optional[TaskPriority] = None,
        delay: Optional[timedelta] = None,
        eta: Optional[datetime] = None,
        task_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """Enqueue a background task"""
        if not self._initialized:
            await self.initialize()
        
        if task_name not in self._registered_tasks:
            raise TaskExecutionError(f"Task '{task_name}' not registered")
        
        task_id = task_id or str(uuid.uuid4())
        config = self._task_configs[task_name]
        
        # Determine queue based on priority
        queue = config['queue']
        if priority:
            if priority == TaskPriority.HIGH:
                queue = settings.tasks.HIGH_PRIORITY_QUEUE
            elif priority == TaskPriority.LOW:
                queue = settings.tasks.LOW_PRIORITY_QUEUE
        
        try:
            if self.celery_app:
                # Use Celery for task execution
                task_kwargs = {
                    'task_id': task_id,
                    'queue': queue,
                    'retry': True,
                    'retry_policy': {
                        'max_retries': config['max_retries'],
                        'interval_start': config['retry_delay'],
                        'interval_step': config['retry_delay'],
                        'interval_max': config['retry_delay'] * 4,
                    }
                }
                
                if delay:
                    task_kwargs['countdown'] = delay.total_seconds()
                elif eta:
                    task_kwargs['eta'] = eta
                
                celery_result = self.celery_app.send_task(
                    f'app.tasks.{task_name}',
                    args=args,
                    kwargs=kwargs,
                    **task_kwargs
                )
                
                # Store task metadata in Redis
                await self._store_task_metadata(task_id, {
                    'task_name': task_name,
                    'args': args,
                    'kwargs': kwargs,
                    'priority': priority.value if priority else config['priority'].value,
                    'queue': queue,
                    'created_at': datetime.utcnow().isoformat(),
                    'celery_id': celery_result.id
                })
                
            else:
                # Simple Redis-based task queue
                await self._enqueue_simple_task(task_id, task_name, args, kwargs, config, delay, eta)
            
            logger.info(f"Task enqueued: {task_name} (ID: {task_id})")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to enqueue task {task_name}: {str(e)}")
            raise TaskExecutionError(f"Task enqueue failed: {str(e)}")
    
    async def _enqueue_simple_task(
        self,
        task_id: str,
        task_name: str,
        args: tuple,
        kwargs: dict,
        config: dict,
        delay: Optional[timedelta],
        eta: Optional[datetime]
    ):
        """Enqueue task in simple Redis queue"""
        execute_at = None
        if delay:
            execute_at = datetime.utcnow() + delay
        elif eta:
            execute_at = eta
        
        task_data = {
            'task_id': task_id,
            'task_name': task_name,
            'args': args,
            'kwargs': kwargs,
            'config': config,
            'created_at': datetime.utcnow().isoformat(),
            'execute_at': execute_at.isoformat() if execute_at else None,
            'status': TaskStatus.PENDING.value
        }
        
        queue_key = f"task_queue:{config['queue']}"
        
        if execute_at:
            # Scheduled task
            await self.redis_client.zadd(
                f"scheduled_tasks:{config['queue']}",
                {json.dumps(task_data): execute_at.timestamp()}
            )
        else:
            # Immediate task
            await self.redis_client.lpush(queue_key, json.dumps(task_data))
        
        # Store task metadata
        await self._store_task_metadata(task_id, task_data)
    
    async def _store_task_metadata(self, task_id: str, metadata: dict):
        """Store task metadata in Redis"""
        metadata_key = f"task_metadata:{task_id}"
        await self.redis_client.hset(metadata_key, mapping=metadata)
        await self.redis_client.expire(metadata_key, 86400 * 7)  # 7 days
    
    async def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get task result by ID"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Get metadata
            metadata_key = f"task_metadata:{task_id}"
            metadata = await self.redis_client.hgetall(metadata_key)
            
            if not metadata:
                return None
            
            if self.celery_app and 'celery_id' in metadata:
                # Get result from Celery
                celery_result = AsyncResult(metadata['celery_id'], app=self.celery_app)
                
                status = TaskStatus.PENDING
                if celery_result.state == 'PENDING':
                    status = TaskStatus.PENDING
                elif celery_result.state == 'STARTED':
                    status = TaskStatus.RUNNING
                elif celery_result.state == 'SUCCESS':
                    status = TaskStatus.SUCCESS
                elif celery_result.state == 'FAILURE':
                    status = TaskStatus.FAILURE
                elif celery_result.state == 'RETRY':
                    status = TaskStatus.RETRY
                elif celery_result.state == 'REVOKED':
                    status = TaskStatus.REVOKED
                
                return TaskResult(
                    task_id=task_id,
                    status=status,
                    result=celery_result.result if status == TaskStatus.SUCCESS else None,
                    error=str(celery_result.info) if status == TaskStatus.FAILURE else None,
                    traceback=getattr(celery_result.info, 'traceback', None) if status == TaskStatus.FAILURE else None,
                    started_at=datetime.fromisoformat(metadata.get('started_at')) if metadata.get('started_at') else None,
                    completed_at=datetime.fromisoformat(metadata.get('completed_at')) if metadata.get('completed_at') else None,
                    retries=int(metadata.get('retries', 0)),
                    metadata=metadata
                )
            else:
                # Get result from simple storage
                result_key = f"task_result:{task_id}"
                result_data = await self.redis_client.hgetall(result_key)
                
                if result_data:
                    return TaskResult(
                        task_id=task_id,
                        status=TaskStatus(result_data.get('status', TaskStatus.PENDING.value)),
                        result=json.loads(result_data['result']) if result_data.get('result') else None,
                        error=result_data.get('error'),
                        traceback=result_data.get('traceback'),
                        started_at=datetime.fromisoformat(result_data['started_at']) if result_data.get('started_at') else None,
                        completed_at=datetime.fromisoformat(result_data['completed_at']) if result_data.get('completed_at') else None,
                        retries=int(result_data.get('retries', 0)),
                        metadata=metadata
                    )
                
                # Task exists but no result yet
                return TaskResult(
                    task_id=task_id,
                    status=TaskStatus(metadata.get('status', TaskStatus.PENDING.value)),
                    metadata=metadata
                )
                
        except Exception as e:
            logger.error(f"Failed to get task result for {task_id}: {str(e)}")
            return None
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or running task"""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Get task metadata
            metadata_key = f"task_metadata:{task_id}"
            metadata = await self.redis_client.hgetall(metadata_key)
            
            if not metadata:
                return False
            
            if self.celery_app and 'celery_id' in metadata:
                # Cancel Celery task
                self.celery_app.control.revoke(metadata['celery_id'], terminate=True)
                
                # Update metadata
                await self.redis_client.hset(metadata_key, 'status', TaskStatus.REVOKED.value)
                
            else:
                # Remove from simple queue
                queue = metadata.get('queue', settings.tasks.DEFAULT_QUEUE)
                queue_key = f"task_queue:{queue}"
                
                # Try to remove from queue (this is approximate for simple queue)
                await self.redis_client.hset(metadata_key, 'status', TaskStatus.REVOKED.value)
            
            logger.info(f"Task cancelled: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {str(e)}")
            return False
    
    async def get_queue_info(self, queue_name: Optional[str] = None) -> Dict[str, Any]:
        """Get queue information and statistics"""
        if not self._initialized:
            await self.initialize()
        
        try:
            queue_name = queue_name or settings.tasks.DEFAULT_QUEUE
            
            if self.celery_app:
                # Get Celery queue info
                inspect = self.celery_app.control.inspect()
                active_tasks = inspect.active() or {}
                scheduled_tasks = inspect.scheduled() or {}
                
                return {
                    'queue_name': queue_name,
                    'active_tasks': sum(len(tasks) for tasks in active_tasks.values()),
                    'scheduled_tasks': sum(len(tasks) for tasks in scheduled_tasks.values()),
                    'workers': list(active_tasks.keys()),
                    'backend': 'celery'
                }
            else:
                # Get simple queue info
                queue_key = f"task_queue:{queue_name}"
                scheduled_key = f"scheduled_tasks:{queue_name}"
                
                pending_count = await self.redis_client.llen(queue_key)
                scheduled_count = await self.redis_client.zcard(scheduled_key)
                
                return {
                    'queue_name': queue_name,
                    'pending_tasks': pending_count,
                    'scheduled_tasks': scheduled_count,
                    'backend': 'simple'
                }
                
        except Exception as e:
            logger.error(f"Failed to get queue info: {str(e)}")
            return {'error': str(e)}
    
    async def cleanup_completed_tasks(self, older_than_days: int = 7) -> int:
        """Cleanup completed tasks older than specified days"""
        if not self._initialized:
            await self.initialize()
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
            pattern = "task_metadata:*"
            
            cleaned_count = 0
            async for key in self.redis_client.scan_iter(match=pattern):
                metadata = await self.redis_client.hgetall(key)
                
                if metadata.get('completed_at'):
                    completed_at = datetime.fromisoformat(metadata['completed_at'])
                    if completed_at < cutoff_date:
                        task_id = key.split(':')[-1]
                        
                        # Delete metadata and result
                        await self.redis_client.delete(key)
                        await self.redis_client.delete(f"task_result:{task_id}")
                        
                        cleaned_count += 1
            
            logger.info(f"Cleaned up {cleaned_count} completed tasks")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup completed tasks: {str(e)}")
            return 0
    
    async def close(self):
        """Close connections and cleanup"""
        if self.redis_client:
            await self.redis_client.close()
        
        if self.celery_app:
            self.celery_app.close()


# Global task manager instance
background_task_manager = BackgroundTaskManager()


def background_task(
    name: Optional[str] = None,
    priority: TaskPriority = TaskPriority.NORMAL,
    max_retries: int = 3,
    retry_delay: int = 60,
    timeout: Optional[int] = None,
    queue: Optional[str] = None
):
    """
    Decorator to register a function as a background task.
    
    Args:
        name: Task name (defaults to function name)
        priority: Task priority
        max_retries: Maximum retry attempts
        retry_delay: Delay between retries in seconds
        timeout: Task timeout in seconds
        queue: Queue name
    """
    def decorator(func: Callable):
        task_name = name or func.__name__
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        # Register the task
        background_task_manager.register_task(
            task_name,
            wrapper,
            priority=priority,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
            queue=queue
        )
        
        # Add enqueue method to function
        async def enqueue(*args, **kwargs):
            return await background_task_manager.enqueue_task(task_name, *args, **kwargs)
        
        wrapper.enqueue = enqueue
        wrapper.task_name = task_name
        
        return wrapper
    
    return decorator


async def enqueue_task(
    task_name: str,
    *args,
    priority: Optional[TaskPriority] = None,
    delay: Optional[timedelta] = None,
    eta: Optional[datetime] = None,
    task_id: Optional[str] = None,
    **kwargs
) -> str:
    """Convenience function to enqueue a task"""
    return await background_task_manager.enqueue_task(
        task_name,
        *args,
        priority=priority,
        delay=delay,
        eta=eta,
        task_id=task_id,
        **kwargs
    )


async def get_task_status(task_id: str) -> Optional[TaskResult]:
    """Convenience function to get task status"""
    return await background_task_manager.get_task_result(task_id)


@asynccontextmanager
async def task_context():
    """Context manager for background task operations"""
    try:
        await background_task_manager.initialize()
        yield background_task_manager
    finally:
        await background_task_manager.close()


# Export main functions and classes
__all__ = [
    'TaskStatus',
    'TaskPriority', 
    'TaskResult',
    'BackgroundTaskManager',
    'background_task_manager',
    'background_task',
    'enqueue_task',
    'get_task_status',
    'task_context'
]