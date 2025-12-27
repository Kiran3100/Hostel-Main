"""
Enhanced Workflow Engine Service

Central orchestration engine for managing complex business workflows with
improved performance, error handling, and monitoring capabilities.
"""

from typing import Dict, Any, Optional, List, Type, Callable, Union, Set
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
import asyncio
import logging
from contextlib import asynccontextmanager
from functools import wraps
import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from redis import Redis

from app.core1.exceptions import (
    BusinessLogicException,
    ValidationException,
    WorkflowException
)
from app.core1.logging import LoggingContext
from app.models.base.enums import WorkflowStatus, WorkflowType
from app.utils.datetime_utils import DateTimeHelper
from app.core1.config import settings


logger = logging.getLogger(__name__)


class WorkflowState(str, Enum):
    """Workflow execution states with enhanced tracking."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"
    RETRYING = "retrying"
    ROLLED_BACK = "rolled_back"


class WorkflowPriority(str, Enum):
    """Workflow execution priorities with numeric values for sorting."""
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    
    @property
    def value_int(self) -> int:
        """Return numeric priority value for sorting."""
        return {"critical": 4, "high": 3, "normal": 2, "low": 1}[self.value]


@dataclass
class StepMetrics:
    """Metrics for workflow step execution."""
    execution_time: float = 0.0
    retry_count: int = 0
    memory_usage: Optional[float] = None
    cpu_usage: Optional[float] = None


@dataclass
class WorkflowMetrics:
    """Comprehensive workflow execution metrics."""
    total_execution_time: float = 0.0
    step_metrics: Dict[str, StepMetrics] = field(default_factory=dict)
    context_size: int = 0
    peak_memory: Optional[float] = None
    error_count: int = 0
    retry_count: int = 0


class WorkflowStep:
    """
    Enhanced workflow step with improved error handling and metrics.
    """
    
    def __init__(
        self,
        name: str,
        handler: Callable,
        required: bool = True,
        rollback_handler: Optional[Callable] = None,
        timeout_seconds: Optional[int] = None,
        retry_count: int = 0,
        retry_delay: float = 1.0,
        retry_backoff: float = 2.0,
        condition: Optional[Callable] = None,
        validate_result: Optional[Callable] = None,
        tags: Optional[Set[str]] = None
    ):
        self.name = name
        self.handler = handler
        self.required = required
        self.rollback_handler = rollback_handler
        self.timeout_seconds = timeout_seconds or settings.DEFAULT_STEP_TIMEOUT
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.retry_backoff = retry_backoff
        self.condition = condition
        self.validate_result = validate_result
        self.tags = tags or set()
        
        # Execution state
        self.executed = False
        self.result = None
        self.error = None
        self.metrics = StepMetrics()
        self.execution_id: Optional[str] = None
    
    async def execute(self, context: Dict[str, Any], execution_id: str) -> Any:
        """Execute step with comprehensive error handling and metrics."""
        self.execution_id = execution_id
        
        # Check execution condition
        if self.condition and not await self._evaluate_condition(context):
            logger.info(f"Step '{self.name}' skipped due to condition")
            return None
        
        start_time = time.time()
        attempts = 0
        max_attempts = self.retry_count + 1
        last_error = None
        
        while attempts < max_attempts:
            try:
                attempts += 1
                self.metrics.retry_count = attempts - 1
                
                logger.info(
                    f"Executing step '{self.name}' (attempt {attempts}/{max_attempts})",
                    extra={"execution_id": execution_id, "step": self.name}
                )
                
                # Execute with timeout
                if self.timeout_seconds:
                    result = await asyncio.wait_for(
                        self._execute_handler(context),
                        timeout=self.timeout_seconds
                    )
                else:
                    result = await self._execute_handler(context)
                
                # Validate result if validator provided
                if self.validate_result and not await self._validate_result(result, context):
                    raise WorkflowException(f"Step '{self.name}' result validation failed")
                
                # Record successful execution
                self.executed = True
                self.result = result
                self.metrics.execution_time = time.time() - start_time
                
                logger.info(
                    f"Step '{self.name}' completed successfully",
                    extra={
                        "execution_id": execution_id,
                        "step": self.name,
                        "execution_time": self.metrics.execution_time,
                        "attempts": attempts
                    }
                )
                
                return result
                
            except asyncio.TimeoutError as e:
                last_error = WorkflowException(
                    f"Step '{self.name}' timed out after {self.timeout_seconds}s"
                )
                logger.warning(
                    f"Step '{self.name}' timed out (attempt {attempts}/{max_attempts})",
                    extra={"execution_id": execution_id, "step": self.name}
                )
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Step '{self.name}' failed (attempt {attempts}/{max_attempts}): {str(e)}",
                    extra={"execution_id": execution_id, "step": self.name, "error": str(e)}
                )
            
            # Wait before retry (with backoff)
            if attempts < max_attempts:
                delay = self.retry_delay * (self.retry_backoff ** (attempts - 1))
                await asyncio.sleep(delay)
        
        # All attempts failed
        self.error = str(last_error)
        self.metrics.execution_time = time.time() - start_time
        
        logger.error(
            f"Step '{self.name}' failed after {max_attempts} attempts",
            extra={"execution_id": execution_id, "step": self.name, "error": self.error}
        )
        
        raise last_error
    
    async def _execute_handler(self, context: Dict[str, Any]) -> Any:
        """Execute the step handler with proper async handling."""
        result = self.handler(context)
        if asyncio.iscoroutine(result):
            return await result
        return result
    
    async def _evaluate_condition(self, context: Dict[str, Any]) -> bool:
        """Evaluate step execution condition."""
        if not self.condition:
            return True
        
        result = self.condition(context)
        if asyncio.iscoroutine(result):
            return await result
        return bool(result)
    
    async def _validate_result(self, result: Any, context: Dict[str, Any]) -> bool:
        """Validate step execution result."""
        if not self.validate_result:
            return True
        
        validation_result = self.validate_result(result, context)
        if asyncio.iscoroutine(validation_result):
            return await validation_result
        return bool(validation_result)
    
    async def rollback(self, context: Dict[str, Any]) -> None:
        """Execute rollback with comprehensive error handling."""
        if not self.rollback_handler or not self.executed:
            return
        
        try:
            logger.info(
                f"Rolling back step '{self.name}'",
                extra={"execution_id": self.execution_id, "step": self.name}
            )
            
            result = self.rollback_handler(context)
            if asyncio.iscoroutine(result):
                await result
                
            logger.info(f"Step '{self.name}' rollback completed")
            
        except Exception as e:
            logger.error(
                f"Rollback failed for step '{self.name}': {str(e)}",
                extra={"execution_id": self.execution_id, "step": self.name, "error": str(e)}
            )
            # Don't re-raise rollback errors


class WorkflowDefinition:
    """
    Enhanced workflow definition with validation and caching.
    """
    
    def __init__(
        self,
        workflow_type: str,
        name: str,
        description: str,
        priority: WorkflowPriority = WorkflowPriority.NORMAL,
        max_execution_time: Optional[int] = None,
        max_concurrent_executions: Optional[int] = None,
        enable_persistence: bool = True,
        enable_monitoring: bool = True,
        tags: Optional[Set[str]] = None
    ):
        self.workflow_type = workflow_type
        self.name = name
        self.description = description
        self.priority = priority
        self.max_execution_time = max_execution_time or settings.DEFAULT_WORKFLOW_TIMEOUT
        self.max_concurrent_executions = max_concurrent_executions
        self.enable_persistence = enable_persistence
        self.enable_monitoring = enable_monitoring
        self.tags = tags or set()
        
        # Workflow components
        self.steps: List[WorkflowStep] = []
        self.validators: List[Callable] = []
        self.on_complete_handlers: List[Callable] = []
        self.on_error_handlers: List[Callable] = []
        self.on_step_complete_handlers: List[Callable] = []
        
        # Caching and optimization
        self._step_map: Optional[Dict[str, WorkflowStep]] = None
        self._required_steps: Optional[List[WorkflowStep]] = None
        self._optional_steps: Optional[List[WorkflowStep]] = None
    
    def add_step(self, step: WorkflowStep) -> "WorkflowDefinition":
        """Add a step with validation."""
        if self.get_step(step.name):
            raise ValidationException(f"Step '{step.name}' already exists")
        
        self.steps.append(step)
        self._invalidate_cache()
        return self
    
    def add_validator(self, validator: Callable) -> "WorkflowDefinition":
        """Add a pre-execution validator."""
        self.validators.append(validator)
        return self
    
    def on_complete(self, handler: Callable) -> "WorkflowDefinition":
        """Add a completion handler."""
        self.on_complete_handlers.append(handler)
        return self
    
    def on_error(self, handler: Callable) -> "WorkflowDefinition":
        """Add an error handler."""
        self.on_error_handlers.append(handler)
        return self
    
    def on_step_complete(self, handler: Callable) -> "WorkflowDefinition":
        """Add a step completion handler."""
        self.on_step_complete_handlers.append(handler)
        return self
    
    def get_step(self, name: str) -> Optional[WorkflowStep]:
        """Get step by name with caching."""
        if self._step_map is None:
            self._step_map = {step.name: step for step in self.steps}
        return self._step_map.get(name)
    
    def get_required_steps(self) -> List[WorkflowStep]:
        """Get required steps with caching."""
        if self._required_steps is None:
            self._required_steps = [step for step in self.steps if step.required]
        return self._required_steps
    
    def get_optional_steps(self) -> List[WorkflowStep]:
        """Get optional steps with caching."""
        if self._optional_steps is None:
            self._optional_steps = [step for step in self.steps if not step.required]
        return self._optional_steps
    
    def _invalidate_cache(self) -> None:
        """Invalidate cached data when workflow is modified."""
        self._step_map = None
        self._required_steps = None
        self._optional_steps = None


@dataclass
class WorkflowExecution:
    """
    Enhanced workflow execution with comprehensive tracking and state management.
    """
    execution_id: UUID
    definition: WorkflowDefinition
    context: Dict[str, Any]
    initiated_by: Optional[UUID]
    
    # State tracking
    state: WorkflowState = WorkflowState.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_step_index: int = 0
    current_step_name: Optional[str] = None
    
    # Execution history
    executed_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    skipped_steps: List[str] = field(default_factory=list)
    
    # Error tracking
    errors: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    
    # Results and metrics
    result: Optional[Dict[str, Any]] = None
    metrics: WorkflowMetrics = field(default_factory=WorkflowMetrics)
    
    # Additional metadata
    tags: Set[str] = field(default_factory=set)
    parent_execution_id: Optional[UUID] = None
    child_execution_ids: List[UUID] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert execution to comprehensive dictionary."""
        return {
            "execution_id": str(self.execution_id),
            "workflow_type": self.definition.workflow_type,
            "workflow_name": self.definition.name,
            "state": self.state.value,
            "priority": self.definition.priority.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.get_duration(),
            "current_step": self.current_step_index,
            "current_step_name": self.current_step_name,
            "total_steps": len(self.definition.steps),
            "progress_percentage": self.get_progress_percentage(),
            "executed_steps": self.executed_steps,
            "failed_steps": self.failed_steps,
            "skipped_steps": self.skipped_steps,
            "errors": self.errors,
            "warnings": self.warnings,
            "result": self.result,
            "metrics": {
                "total_execution_time": self.metrics.total_execution_time,
                "step_count": len(self.metrics.step_metrics),
                "error_count": self.metrics.error_count,
                "retry_count": self.metrics.retry_count,
                "context_size": self.metrics.context_size
            },
            "tags": list(self.tags),
            "parent_execution_id": str(self.parent_execution_id) if self.parent_execution_id else None,
            "child_execution_ids": [str(id) for id in self.child_execution_ids],
            "initiated_by": str(self.initiated_by) if self.initiated_by else None
        }
    
    def get_duration(self) -> Optional[float]:
        """Get execution duration in seconds."""
        if not self.started_at:
            return None
        
        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()
    
    def get_progress_percentage(self) -> float:
        """Calculate execution progress percentage."""
        if not self.definition.steps:
            return 0.0
        return (self.current_step_index / len(self.definition.steps)) * 100
    
    def add_error(self, error: str, step: Optional[str] = None, severity: str = "error") -> None:
        """Add error with metadata."""
        error_entry = {
            "error": error,
            "step": step or self.current_step_name,
            "step_index": self.current_step_index,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if severity == "warning":
            self.warnings.append(error_entry)
        else:
            self.errors.append(error_entry)
            self.metrics.error_count += 1
    
    def add_tag(self, tag: str) -> None:
        """Add execution tag."""
        self.tags.add(tag)
    
    def has_tag(self, tag: str) -> bool:
        """Check if execution has specific tag."""
        return tag in self.tags


class WorkflowEngineService:
    """
    Enhanced workflow engine with improved performance, monitoring, and reliability.
    """
    
    def __init__(
        self,
        redis_client: Optional[Redis] = None,
        thread_pool_size: int = 10,
        enable_persistence: bool = True,
        enable_monitoring: bool = True,
        max_execution_history: int = 10000
    ):
        # Core storage
        self.workflows: Dict[str, WorkflowDefinition] = {}
        self.executions: Dict[UUID, WorkflowExecution] = {}
        
        # Execution management
        self.execution_queue: List[WorkflowExecution] = []
        self.running_executions: Set[UUID] = set()
        self.execution_locks: Dict[UUID, asyncio.Lock] = {}
        
        # Performance optimization
        self.redis_client = redis_client
        self.thread_pool = ThreadPoolExecutor(max_workers=thread_pool_size)
        self.enable_persistence = enable_persistence
        self.enable_monitoring = enable_monitoring
        self.max_execution_history = max_execution_history
        
        # Statistics and monitoring
        self.stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "cancelled_executions": 0,
            "average_execution_time": 0.0,
            "total_execution_time": 0.0,
            "workflow_counts": defaultdict(int),
            "error_counts": defaultdict(int)
        }
        
        # Cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._start_cleanup_task()
    
    def register_workflow(self, definition: WorkflowDefinition) -> None:
        """Register workflow with enhanced validation and caching."""
        if definition.workflow_type in self.workflows:
            raise ValidationException(
                f"Workflow type '{definition.workflow_type}' already registered"
            )
        
        # Validate workflow definition
        self._validate_workflow_definition(definition)
        
        # Register workflow
        self.workflows[definition.workflow_type] = definition
        
        logger.info(
            f"Registered workflow '{definition.workflow_type}' with {len(definition.steps)} steps",
            extra={
                "workflow_type": definition.workflow_type,
                "step_count": len(definition.steps),
                "required_steps": len(definition.get_required_steps()),
                "optional_steps": len(definition.get_optional_steps())
            }
        )
    
    def _validate_workflow_definition(self, definition: WorkflowDefinition) -> None:
        """Validate workflow definition."""
        if not definition.steps:
            raise ValidationException("Workflow must have at least one step")
        
        # Check for duplicate step names
        step_names = [step.name for step in definition.steps]
        if len(step_names) != len(set(step_names)):
            raise ValidationException("Workflow steps must have unique names")
        
        # Validate step handlers
        for step in definition.steps:
            if not callable(step.handler):
                raise ValidationException(f"Step '{step.name}' handler must be callable")
    
    async def execute_workflow(
        self,
        workflow_type: str,
        context: Dict[str, Any],
        initiated_by: Optional[UUID] = None,
        execution_id: Optional[UUID] = None,
        parent_execution_id: Optional[UUID] = None,
        priority: Optional[WorkflowPriority] = None,
        tags: Optional[Set[str]] = None
    ) -> WorkflowExecution:
        """
        Execute workflow with enhanced features and monitoring.
        """
        # Get workflow definition
        definition = self.workflows.get(workflow_type)
        if not definition:
            raise ValidationException(f"Unknown workflow type: {workflow_type}")
        
        # Create execution instance
        if not execution_id:
            execution_id = uuid4()
        
        # Validate context size
        context_size = len(str(context))
        if context_size > settings.MAX_CONTEXT_SIZE:
            logger.warning(f"Large context size: {context_size} bytes")
        
        # Create execution
        execution = WorkflowExecution(
            execution_id=execution_id,
            definition=definition,
            context=context.copy(),  # Deep copy to prevent mutations
            initiated_by=initiated_by,
            parent_execution_id=parent_execution_id
        )
        
        # Set priority and tags
        if priority:
            execution.definition.priority = priority
        if tags:
            execution.tags.update(tags)
        
        # Initialize metrics
        execution.metrics.context_size = context_size
        
        # Store execution
        self.executions[execution_id] = execution
        self.execution_locks[execution_id] = asyncio.Lock()
        
        # Update parent-child relationship
        if parent_execution_id and parent_execution_id in self.executions:
            self.executions[parent_execution_id].child_execution_ids.append(execution_id)
        
        # Execute workflow
        async with self.execution_locks[execution_id]:
            execution_start_time = time.time()
            
            with LoggingContext(
                workflow_type=workflow_type,
                execution_id=str(execution_id)
            ):
                try:
                    # Update statistics
                    self.stats["total_executions"] += 1
                    self.stats["workflow_counts"][workflow_type] += 1
                    
                    # Check concurrent execution limits
                    await self._check_concurrency_limits(definition, execution)
                    
                    # Run pre-execution validators
                    await self._validate_execution(execution)
                    
                    # Execute workflow steps
                    execution.state = WorkflowState.RUNNING
                    execution.started_at = datetime.utcnow()
                    self.running_executions.add(execution_id)
                    
                    logger.info(
                        f"Starting workflow execution",
                        extra={
                            "workflow_type": workflow_type,
                            "execution_id": str(execution_id),
                            "step_count": len(definition.steps),
                            "priority": definition.priority.value
                        }
                    )
                    
                    await self._execute_steps(execution)
                    
                    # Mark as completed
                    execution.state = WorkflowState.COMPLETED
                    execution.completed_at = datetime.utcnow()
                    execution.metrics.total_execution_time = time.time() - execution_start_time
                    
                    # Update statistics
                    self.stats["successful_executions"] += 1
                    self._update_execution_time_stats(execution.metrics.total_execution_time)
                    
                    # Run completion handlers
                    await self._run_completion_handlers(execution)
                    
                    logger.info(
                        f"Workflow execution completed successfully",
                        extra={
                            "execution_id": str(execution_id),
                            "execution_time": execution.metrics.total_execution_time,
                            "steps_executed": len(execution.executed_steps)
                        }
                    )
                    
                except Exception as e:
                    execution.state = WorkflowState.FAILED
                    execution.completed_at = datetime.utcnow()
                    execution.metrics.total_execution_time = time.time() - execution_start_time
                    
                    # Record error
                    execution.add_error(str(e))
                    
                    # Update statistics
                    self.stats["failed_executions"] += 1
                    self.stats["error_counts"][type(e).__name__] += 1
                    self._update_execution_time_stats(execution.metrics.total_execution_time)
                    
                    # Run error handlers
                    await self._run_error_handlers(execution, e)
                    
                    # Attempt rollback
                    await self._rollback_execution(execution)
                    
                    logger.error(
                        f"Workflow execution failed: {str(e)}",
                        extra={
                            "execution_id": str(execution_id),
                            "error_type": type(e).__name__,
                            "execution_time": execution.metrics.total_execution_time
                        },
                        exc_info=True
                    )
                    
                    raise
                    
                finally:
                    # Cleanup
                    self.running_executions.discard(execution_id)
                    
                    # Persist execution if enabled
                    if self.enable_persistence:
                        await self._persist_execution(execution)
        
        return execution
    
    async def _check_concurrency_limits(
        self,
        definition: WorkflowDefinition,
        execution: WorkflowExecution
    ) -> None:
        """Check and enforce concurrency limits."""
        if definition.max_concurrent_executions is None:
            return
        
        # Count running executions of the same type
        running_count = sum(
            1 for exec_id in self.running_executions
            if exec_id in self.executions and 
            self.executions[exec_id].definition.workflow_type == definition.workflow_type
        )
        
        if running_count >= definition.max_concurrent_executions:
            execution.state = WorkflowState.QUEUED
            raise BusinessLogicException(
                f"Workflow '{definition.workflow_type}' has reached maximum concurrent executions "
                f"({definition.max_concurrent_executions})"
            )
    
    async def _validate_execution(self, execution: WorkflowExecution) -> None:
        """Run all validators with improved error handling."""
        for i, validator in enumerate(execution.definition.validators):
            try:
                result = validator(execution.context)
                if asyncio.iscoroutine(result):
                    result = await result
                
                if not result:
                    raise ValidationException(
                        f"Workflow validation failed at validator {i+1}"
                    )
                    
            except Exception as e:
                raise ValidationException(
                    f"Workflow validation error at validator {i+1}: {str(e)}"
                ) from e
    
    async def _execute_steps(self, execution: WorkflowExecution) -> None:
        """Execute workflow steps with enhanced monitoring and error handling."""
        steps = execution.definition.steps
        
        for i, step in enumerate(steps):
            execution.current_step_index = i
            execution.current_step_name = step.name
            
            try:
                logger.debug(
                    f"Executing workflow step {i+1}/{len(steps)}: {step.name}",
                    extra={"execution_id": str(execution.execution_id)}
                )
                
                # Execute step
                result = await step.execute(execution.context, str(execution.execution_id))
                
                # Record successful execution
                execution.executed_steps.append(step.name)
                execution.metrics.step_metrics[step.name] = step.metrics
                
                # Store step result in context
                execution.context[f"step_{step.name}_result"] = result
                
                # Run step completion handlers
                await self._run_step_completion_handlers(execution, step, result)
                
            except Exception as e:
                # Record step failure
                execution.failed_steps.append(step.name)
                execution.metrics.step_metrics[step.name] = step.metrics
                
                if step.required:
                    raise WorkflowException(
                        f"Required step '{step.name}' failed: {str(e)}"
                    ) from e
                else:
                    # Log and continue for optional steps
                    execution.add_error(str(e), step.name, "warning")
                    execution.skipped_steps.append(step.name)
                    
                    logger.warning(
                        f"Optional step '{step.name}' failed, continuing execution",
                        extra={
                            "execution_id": str(execution.execution_id),
                            "error": str(e)
                        }
                    )
    
    async def _run_step_completion_handlers(
        self,
        execution: WorkflowExecution,
        step: WorkflowStep,
        result: Any
    ) -> None:
        """Run step completion handlers."""
        for handler in execution.definition.on_step_complete_handlers:
            try:
                handler_result = handler(execution, step, result)
                if asyncio.iscoroutine(handler_result):
                    await handler_result
            except Exception as e:
                execution.add_error(
                    f"Step completion handler error: {str(e)}",
                    step.name,
                    "warning"
                )
    
    async def _rollback_execution(self, execution: WorkflowExecution) -> None:
        """Enhanced rollback with comprehensive error handling."""
        logger.info(
            f"Starting rollback for execution {execution.execution_id}",
            extra={"execution_id": str(execution.execution_id)}
        )
        
        # Get executed steps in reverse order
        executed_steps = [
            step for step in execution.definition.steps
            if step.name in execution.executed_steps and step.executed
        ]
        
        rollback_errors = []
        
        for step in reversed(executed_steps):
            try:
                await step.rollback(execution.context)
                logger.debug(f"Rolled back step: {step.name}")
            except Exception as e:
                error_msg = f"Rollback failed for step '{step.name}': {str(e)}"
                rollback_errors.append(error_msg)
                execution.add_error(error_msg, step.name, "warning")
        
        if rollback_errors:
            logger.warning(
                f"Rollback completed with {len(rollback_errors)} errors",
                extra={
                    "execution_id": str(execution.execution_id),
                    "rollback_errors": rollback_errors
                }
            )
        else:
            logger.info(f"Rollback completed successfully")
        
        execution.state = WorkflowState.ROLLED_BACK
    
    async def _run_completion_handlers(self, execution: WorkflowExecution) -> None:
        """Run completion handlers with error isolation."""
        for handler in execution.definition.on_complete_handlers:
            try:
                result = handler(execution)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                execution.add_error(
                    f"Completion handler error: {str(e)}",
                    severity="warning"
                )
    
    async def _run_error_handlers(
        self,
        execution: WorkflowExecution,
        error: Exception
    ) -> None:
        """Run error handlers with isolation."""
        for handler in execution.definition.on_error_handlers:
            try:
                result = handler(execution, error)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                pass  # Ignore errors in error handlers
    
    async def _persist_execution(self, execution: WorkflowExecution) -> None:
        """Persist execution state for recovery and auditing."""
        if not self.redis_client:
            return
        
        try:
            execution_data = execution.to_dict()
            await self.redis_client.setex(
                f"workflow_execution:{execution.execution_id}",
                86400,  # 24 hours
                str(execution_data)
            )
        except Exception as e:
            logger.warning(f"Failed to persist execution: {str(e)}")
    
    def _update_execution_time_stats(self, execution_time: float) -> None:
        """Update execution time statistics."""
        total_time = self.stats["total_execution_time"] + execution_time
        total_count = self.stats["successful_executions"] + self.stats["failed_executions"]
        
        self.stats["total_execution_time"] = total_time
        self.stats["average_execution_time"] = total_time / total_count if total_count > 0 else 0.0
    
    def get_execution(self, execution_id: UUID) -> Optional[WorkflowExecution]:
        """Get execution by ID with caching."""
        return self.executions.get(execution_id)
    
    def get_executions_by_type(
        self,
        workflow_type: str,
        state: Optional[WorkflowState] = None,
        limit: int = 100
    ) -> List[WorkflowExecution]:
        """Get executions by type with filtering and pagination."""
        executions = [
            ex for ex in self.executions.values()
            if ex.definition.workflow_type == workflow_type
        ]
        
        if state:
            executions = [ex for ex in executions if ex.state == state]
        
        # Sort by start time (newest first)
        executions.sort(
            key=lambda x: x.started_at or datetime.min,
            reverse=True
        )
        
        return executions[:limit]
    
    async def cancel_execution(self, execution_id: UUID, reason: str = "") -> bool:
        """Cancel execution with proper cleanup."""
        execution = self.executions.get(execution_id)
        if not execution:
            return False
        
        if execution.state in [WorkflowState.COMPLETED, WorkflowState.FAILED, WorkflowState.CANCELLED]:
            return False
        
        async with self.execution_locks.get(execution_id, asyncio.Lock()):
            execution.state = WorkflowState.CANCELLED
            execution.completed_at = datetime.utcnow()
            execution.add_error(f"Execution cancelled: {reason}")
            
            # Update statistics
            self.stats["cancelled_executions"] += 1
            
            # Cleanup
            self.running_executions.discard(execution_id)
            
            logger.info(
                f"Cancelled workflow execution",
                extra={
                    "execution_id": str(execution_id),
                    "reason": reason
                }
            )
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive engine statistics."""
        return {
            **self.stats,
            "current_executions": len(self.running_executions),
            "total_stored_executions": len(self.executions),
            "registered_workflows": len(self.workflows),
            "workflow_types": list(self.workflows.keys())
        }
    
    def _start_cleanup_task(self) -> None:
        """Start periodic cleanup task."""
        async def cleanup_task():
            while True:
                try:
                    await asyncio.sleep(3600)  # Run every hour
                    await self._cleanup_old_executions()
                except Exception as e:
                    logger.error(f"Cleanup task error: {str(e)}")
        
        self._cleanup_task = asyncio.create_task(cleanup_task())
    
    async def _cleanup_old_executions(self) -> None:
        """Clean up old execution records."""
        if len(self.executions) <= self.max_execution_history:
            return
        
        # Sort executions by completion time
        completed_executions = [
            (exec_id, execution) for exec_id, execution in self.executions.items()
            if execution.state in [WorkflowState.COMPLETED, WorkflowState.FAILED, WorkflowState.CANCELLED]
            and execution.completed_at
        ]
        
        completed_executions.sort(key=lambda x: x[1].completed_at)
        
        # Remove oldest executions
        excess_count = len(self.executions) - self.max_execution_history
        if excess_count > 0:
            for exec_id, _ in completed_executions[:excess_count]:
                del self.executions[exec_id]
                self.execution_locks.pop(exec_id, None)
            
            logger.info(f"Cleaned up {excess_count} old execution records")


# Global workflow engine instance
workflow_engine = WorkflowEngineService()


def create_workflow(
    workflow_type: str,
    name: str,
    description: str,
    priority: WorkflowPriority = WorkflowPriority.NORMAL,
    **kwargs
) -> WorkflowDefinition:
    """
    Factory function to create a workflow definition with enhanced features.
    """
    return WorkflowDefinition(
        workflow_type=workflow_type,
        name=name,
        description=description,
        priority=priority,
        **kwargs
    )


def create_step(
    name: str,
    handler: Callable,
    **kwargs
) -> WorkflowStep:
    """
    Factory function to create a workflow step with enhanced features.
    """
    return WorkflowStep(name=name, handler=handler, **kwargs)


# Decorators for workflow handlers
def workflow_step(
    name: str,
    required: bool = True,
    timeout_seconds: Optional[int] = None,
    retry_count: int = 0,
    **kwargs
):
    """Decorator to define workflow steps."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        wrapper._workflow_step = WorkflowStep(
            name=name,
            handler=wrapper,
            required=required,
            timeout_seconds=timeout_seconds,
            retry_count=retry_count,
            **kwargs
        )
        return wrapper
    
    return decorator


def workflow_validator(func: Callable):
    """Decorator to define workflow validators."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    
    wrapper._is_workflow_validator = True
    return wrapper