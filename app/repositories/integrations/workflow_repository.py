"""
Workflow Repository for automated workflow and process management.

This repository handles workflow automation, business process orchestration,
task scheduling, and workflow execution tracking.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Callable
from uuid import UUID, uuid4
from enum import Enum as PyEnum

from sqlalchemy import and_, or_, func, case
from sqlalchemy.orm import Session

from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.core.exceptions import NotFoundError, ValidationException


class WorkflowStatus(str, PyEnum):
    """Workflow execution status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowTriggerType(str, PyEnum):
    """Workflow trigger types."""
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    EVENT_BASED = "event_based"
    WEBHOOK = "webhook"
    API_CALL = "api_call"


class TaskStatus(str, PyEnum):
    """Individual task status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING = "waiting"


class TaskType(str, PyEnum):
    """Task type enumeration."""
    EMAIL = "email"
    SMS = "sms"
    NOTIFICATION = "notification"
    API_CALL = "api_call"
    DATA_SYNC = "data_sync"
    APPROVAL = "approval"
    CONDITION = "condition"
    DELAY = "delay"
    SCRIPT = "script"
    WEBHOOK = "webhook"


class ApprovalStatus(str, PyEnum):
    """Approval task status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class WorkflowRepository(BaseRepository):
    """
    Repository for workflow automation and process management.
    
    Provides methods for creating workflows, executing tasks,
    tracking progress, and managing approvals.
    """
    
    def __init__(self, session: Session):
        """Initialize workflow repository."""
        self.session = session
    
    # ============================================================================
    # WORKFLOW DEFINITION
    # ============================================================================
    
    async def create_workflow(
        self,
        name: str,
        description: str,
        trigger_type: WorkflowTriggerType,
        trigger_config: Dict[str, Any],
        tasks: List[Dict[str, Any]],
        hostel_id: Optional[UUID] = None,
        is_active: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create workflow definition.
        
        Args:
            name: Workflow name
            description: Workflow description
            trigger_type: Trigger type
            trigger_config: Trigger configuration
            tasks: List of task definitions
            hostel_id: Optional hostel scope
            is_active: Whether workflow is active
            metadata: Additional metadata
            audit_context: Audit information
            
        Returns:
            Created workflow
        """
        # Validate workflow structure
        await self._validate_workflow_structure(tasks)
        
        workflow = {
            "id": uuid4(),
            "name": name,
            "description": description,
            "trigger_type": trigger_type,
            "trigger_config": trigger_config,
            "tasks": tasks,
            "hostel_id": hostel_id,
            "is_active": is_active,
            "status": WorkflowStatus.DRAFT,
            "version": 1,
            "execution_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "metadata": metadata or {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Set up triggers if active
        if is_active:
            await self._setup_workflow_triggers(workflow)
            workflow["status"] = WorkflowStatus.ACTIVE
            workflow["activated_at"] = datetime.utcnow()
        
        return workflow
    
    async def update_workflow(
        self,
        workflow_id: UUID,
        update_data: Dict[str, Any],
        create_version: bool = True,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update workflow definition.
        
        Args:
            workflow_id: Workflow ID
            update_data: Update data
            create_version: Whether to create new version
            audit_context: Audit information
            
        Returns:
            Updated workflow
        """
        workflow = await self.get_workflow_by_id(workflow_id)
        
        # Check if workflow has active executions
        active_executions = await self.get_active_executions(workflow_id)
        if active_executions and "tasks" in update_data:
            raise ValidationException(
                "Cannot modify tasks while workflow has active executions"
            )
        
        if create_version:
            # Archive current version
            await self._archive_workflow_version(workflow)
            update_data["version"] = workflow["version"] + 1
        
        # Validate structure if tasks changed
        if "tasks" in update_data:
            await self._validate_workflow_structure(update_data["tasks"])
        
        update_data["updated_at"] = datetime.utcnow()
        
        workflow.update(update_data)
        return workflow
    
    async def activate_workflow(
        self,
        workflow_id: UUID,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Activate workflow.
        
        Args:
            workflow_id: Workflow ID
            audit_context: Audit information
            
        Returns:
            Activated workflow
        """
        workflow = await self.get_workflow_by_id(workflow_id)
        
        # Validate workflow is ready for activation
        await self._validate_workflow_activation(workflow)
        
        # Setup triggers
        await self._setup_workflow_triggers(workflow)
        
        workflow["is_active"] = True
        workflow["status"] = WorkflowStatus.ACTIVE
        workflow["activated_at"] = datetime.utcnow()
        workflow["updated_at"] = datetime.utcnow()
        
        return workflow
    
    async def deactivate_workflow(
        self,
        workflow_id: UUID,
        reason: Optional[str] = None,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Deactivate workflow.
        
        Args:
            workflow_id: Workflow ID
            reason: Deactivation reason
            audit_context: Audit information
            
        Returns:
            Deactivated workflow
        """
        workflow = await self.get_workflow_by_id(workflow_id)
        
        # Cleanup triggers
        await self._cleanup_workflow_triggers(workflow)
        
        workflow["is_active"] = False
        workflow["status"] = WorkflowStatus.PAUSED
        workflow["deactivated_at"] = datetime.utcnow()
        workflow["deactivation_reason"] = reason
        workflow["updated_at"] = datetime.utcnow()
        
        return workflow
    
    # ============================================================================
    # WORKFLOW EXECUTION
    # ============================================================================
    
    async def execute_workflow(
        self,
        workflow_id: UUID,
        trigger_data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute workflow.
        
        Args:
            workflow_id: Workflow ID
            trigger_data: Data that triggered the workflow
            context: Execution context
            
        Returns:
            Workflow execution record
        """
        workflow = await self.get_workflow_by_id(workflow_id)
        
        if not workflow["is_active"]:
            raise ValidationException("Workflow is not active")
        
        execution = {
            "id": uuid4(),
            "workflow_id": workflow_id,
            "workflow_version": workflow["version"],
            "trigger_data": trigger_data or {},
            "context": context or {},
            "status": WorkflowStatus.ACTIVE,
            "current_task_index": 0,
            "completed_tasks": [],
            "failed_tasks": [],
            "task_results": {},
            "started_at": datetime.utcnow(),
            "completed_at": None,
            "error_message": None
        }
        
        try:
            # Execute workflow tasks
            execution = await self._execute_workflow_tasks(workflow, execution)
            
            execution["status"] = WorkflowStatus.COMPLETED
            execution["completed_at"] = datetime.utcnow()
            
            # Update workflow statistics
            workflow["execution_count"] += 1
            workflow["success_count"] += 1
            workflow["last_execution_at"] = datetime.utcnow()
            
        except Exception as e:
            execution["status"] = WorkflowStatus.FAILED
            execution["error_message"] = str(e)
            execution["completed_at"] = datetime.utcnow()
            
            # Update workflow statistics
            workflow["execution_count"] += 1
            workflow["failure_count"] += 1
            workflow["last_execution_at"] = datetime.utcnow()
            workflow["last_error"] = str(e)
        
        return execution
    
    async def execute_task(
        self,
        execution_id: UUID,
        task_index: int,
        task_definition: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute individual workflow task.
        
        Args:
            execution_id: Execution ID
            task_index: Task index in workflow
            task_definition: Task definition
            context: Execution context
            
        Returns:
            Task execution result
        """
        task_execution = {
            "id": uuid4(),
            "execution_id": execution_id,
            "task_index": task_index,
            "task_type": task_definition["type"],
            "task_name": task_definition.get("name", f"Task {task_index}"),
            "status": TaskStatus.RUNNING,
            "input_data": context,
            "output_data": None,
            "started_at": datetime.utcnow(),
            "completed_at": None,
            "error_message": None,
            "retry_count": 0
        }
        
        try:
            # Execute task based on type
            result = await self._execute_task_by_type(
                task_definition,
                context
            )
            
            task_execution["status"] = TaskStatus.COMPLETED
            task_execution["output_data"] = result
            task_execution["completed_at"] = datetime.utcnow()
            
        except Exception as e:
            task_execution["status"] = TaskStatus.FAILED
            task_execution["error_message"] = str(e)
            task_execution["completed_at"] = datetime.utcnow()
            
            # Retry logic
            max_retries = task_definition.get("max_retries", 0)
            if task_execution["retry_count"] < max_retries:
                task_execution["retry_count"] += 1
                task_execution["status"] = TaskStatus.PENDING
                # Schedule retry
                await self._schedule_task_retry(task_execution, task_definition)
        
        return task_execution
    
    async def retry_failed_execution(
        self,
        execution_id: UUID,
        from_task: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Retry failed workflow execution.
        
        Args:
            execution_id: Execution ID
            from_task: Optional task index to retry from
            
        Returns:
            New execution record
        """
        original_execution = await self.get_execution_by_id(execution_id)
        
        if original_execution["status"] != WorkflowStatus.FAILED:
            raise ValidationException(
                f"Cannot retry execution with status: {original_execution['status']}"
            )
        
        workflow = await self.get_workflow_by_id(
            original_execution["workflow_id"]
        )
        
        # Create new execution with context from failed execution
        retry_context = original_execution["context"].copy()
        retry_context["retry_from_task"] = from_task
        retry_context["original_execution_id"] = execution_id
        
        return await self.execute_workflow(
            workflow["id"],
            trigger_data=original_execution["trigger_data"],
            context=retry_context
        )
    
    async def cancel_execution(
        self,
        execution_id: UUID,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cancel running workflow execution.
        
        Args:
            execution_id: Execution ID
            reason: Cancellation reason
            
        Returns:
            Cancelled execution
        """
        execution = await self.get_execution_by_id(execution_id)
        
        if execution["status"] not in [WorkflowStatus.ACTIVE, TaskStatus.WAITING]:
            raise ValidationException(
                f"Cannot cancel execution with status: {execution['status']}"
            )
        
        execution["status"] = WorkflowStatus.CANCELLED
        execution["cancelled_at"] = datetime.utcnow()
        execution["cancellation_reason"] = reason
        execution["completed_at"] = datetime.utcnow()
        
        return execution
    
    # ============================================================================
    # TASK SCHEDULING
    # ============================================================================
    
    async def schedule_task(
        self,
        workflow_id: UUID,
        schedule: str,  # cron expression
        task_config: Dict[str, Any],
        is_active: bool = True
    ) -> Dict[str, Any]:
        """
        Schedule recurring task.
        
        Args:
            workflow_id: Workflow ID
            schedule: Cron schedule expression
            task_config: Task configuration
            is_active: Whether schedule is active
            
        Returns:
            Scheduled task configuration
        """
        scheduled_task = {
            "id": uuid4(),
            "workflow_id": workflow_id,
            "schedule": schedule,
            "task_config": task_config,
            "is_active": is_active,
            "last_run_at": None,
            "next_run_at": self._calculate_next_run(schedule),
            "run_count": 0,
            "failure_count": 0,
            "created_at": datetime.utcnow()
        }
        
        return scheduled_task
    
    async def get_pending_scheduled_tasks(
        self,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get scheduled tasks pending execution.
        
        Args:
            limit: Maximum results
            
        Returns:
            List of pending scheduled tasks
        """
        now = datetime.utcnow()
        
        # Placeholder implementation
        return []
    
    async def execute_scheduled_task(
        self,
        scheduled_task_id: UUID
    ) -> Dict[str, Any]:
        """
        Execute scheduled task.
        
        Args:
            scheduled_task_id: Scheduled task ID
            
        Returns:
            Execution result
        """
        scheduled_task = await self.get_scheduled_task_by_id(scheduled_task_id)
        
        # Execute the workflow
        execution = await self.execute_workflow(
            scheduled_task["workflow_id"],
            trigger_data={"scheduled_task_id": scheduled_task_id},
            context=scheduled_task["task_config"]
        )
        
        # Update scheduled task
        scheduled_task["last_run_at"] = datetime.utcnow()
        scheduled_task["next_run_at"] = self._calculate_next_run(
            scheduled_task["schedule"]
        )
        scheduled_task["run_count"] += 1
        
        if execution["status"] == WorkflowStatus.FAILED:
            scheduled_task["failure_count"] += 1
        
        return execution
    
    # ============================================================================
    # APPROVAL WORKFLOWS
    # ============================================================================
    
    async def create_approval_request(
        self,
        workflow_id: UUID,
        execution_id: UUID,
        task_index: int,
        approver_ids: List[UUID],
        approval_data: Dict[str, Any],
        timeout_hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create approval request.
        
        Args:
            workflow_id: Workflow ID
            execution_id: Execution ID
            task_index: Task index
            approver_ids: List of approver user IDs
            approval_data: Data for approval decision
            timeout_hours: Optional timeout in hours
            
        Returns:
            Approval request
        """
        approval_request = {
            "id": uuid4(),
            "workflow_id": workflow_id,
            "execution_id": execution_id,
            "task_index": task_index,
            "approver_ids": approver_ids,
            "approval_data": approval_data,
            "status": ApprovalStatus.PENDING,
            "responses": {},
            "approved_by": None,
            "rejected_by": None,
            "approved_at": None,
            "rejected_at": None,
            "timeout_at": (
                datetime.utcnow() + timedelta(hours=timeout_hours)
                if timeout_hours else None
            ),
            "created_at": datetime.utcnow()
        }
        
        # Send notifications to approvers
        await self._notify_approvers(approval_request)
        
        return approval_request
    
    async def submit_approval_response(
        self,
        approval_id: UUID,
        approver_id: UUID,
        approved: bool,
        comments: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submit approval response.
        
        Args:
            approval_id: Approval request ID
            approver_id: Approver user ID
            approved: Whether approved
            comments: Optional comments
            
        Returns:
            Updated approval request
        """
        approval_request = await self.get_approval_request_by_id(approval_id)
        
        if approval_request["status"] != ApprovalStatus.PENDING:
            raise ValidationException(
                f"Approval already {approval_request['status']}"
            )
        
        if approver_id not in approval_request["approver_ids"]:
            raise ValidationException("User not authorized to approve")
        
        # Record response
        approval_request["responses"][str(approver_id)] = {
            "approved": approved,
            "comments": comments,
            "responded_at": datetime.utcnow()
        }
        
        if approved:
            approval_request["status"] = ApprovalStatus.APPROVED
            approval_request["approved_by"] = approver_id
            approval_request["approved_at"] = datetime.utcnow()
            
            # Continue workflow execution
            await self._resume_workflow_after_approval(approval_request)
        else:
            approval_request["status"] = ApprovalStatus.REJECTED
            approval_request["rejected_by"] = approver_id
            approval_request["rejected_at"] = datetime.utcnow()
            
            # Handle rejection
            await self._handle_approval_rejection(approval_request)
        
        return approval_request
    
    async def get_pending_approvals(
        self,
        approver_id: UUID,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get pending approvals for user.
        
        Args:
            approver_id: Approver user ID
            limit: Maximum results
            
        Returns:
            List of pending approval requests
        """
        # Placeholder implementation
        return []
    
    # ============================================================================
    # CONDITIONAL LOGIC
    # ============================================================================
    
    async def evaluate_condition(
        self,
        condition: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """
        Evaluate workflow condition.
        
        Args:
            condition: Condition definition
            context: Execution context
            
        Returns:
            True if condition met
        """
        condition_type = condition.get("type")
        
        if condition_type == "equals":
            return context.get(condition["field"]) == condition["value"]
        
        elif condition_type == "not_equals":
            return context.get(condition["field"]) != condition["value"]
        
        elif condition_type == "greater_than":
            return context.get(condition["field"]) > condition["value"]
        
        elif condition_type == "less_than":
            return context.get(condition["field"]) < condition["value"]
        
        elif condition_type == "contains":
            field_value = context.get(condition["field"], "")
            return condition["value"] in str(field_value)
        
        elif condition_type == "regex":
            import re
            field_value = context.get(condition["field"], "")
            pattern = condition["pattern"]
            return bool(re.match(pattern, str(field_value)))
        
        elif condition_type == "and":
            return all(
                await self.evaluate_condition(cond, context)
                for cond in condition["conditions"]
            )
        
        elif condition_type == "or":
            return any(
                await self.evaluate_condition(cond, context)
                for cond in condition["conditions"]
            )
        
        elif condition_type == "custom":
            # Execute custom condition function
            return await self._execute_custom_condition(
                condition["function"],
                context
            )
        
        return False
    
    # ============================================================================
    # ANALYTICS & MONITORING
    # ============================================================================
    
    async def get_workflow_analytics(
        self,
        workflow_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get workflow execution analytics.
        
        Args:
            workflow_id: Workflow ID
            days: Time period in days
            
        Returns:
            Analytics data
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Placeholder implementation
        return {
            "workflow_id": workflow_id,
            "period_days": days,
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "cancelled_executions": 0,
            "success_rate": 0,
            "avg_execution_time_seconds": 0,
            "task_failure_breakdown": {},
            "execution_trend": []
        }
    
    async def get_task_performance(
        self,
        workflow_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get task performance metrics.
        
        Args:
            workflow_id: Workflow ID
            days: Time period in days
            
        Returns:
            Task performance data
        """
        # Placeholder implementation
        return []
    
    async def get_execution_timeline(
        self,
        execution_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get execution timeline with task details.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            Execution timeline
        """
        execution = await self.get_execution_by_id(execution_id)
        
        timeline = [
            {
                "event": "workflow_started",
                "timestamp": execution["started_at"],
                "details": {
                    "trigger_data": execution["trigger_data"]
                }
            }
        ]
        
        # Add task events
        for task_result in execution.get("task_results", {}).values():
            timeline.append({
                "event": "task_started",
                "timestamp": task_result["started_at"],
                "details": {
                    "task_name": task_result["task_name"],
                    "task_type": task_result["task_type"]
                }
            })
            
            timeline.append({
                "event": "task_completed",
                "timestamp": task_result["completed_at"],
                "details": {
                    "task_name": task_result["task_name"],
                    "status": task_result["status"]
                }
            })
        
        if execution["completed_at"]:
            timeline.append({
                "event": "workflow_completed",
                "timestamp": execution["completed_at"],
                "details": {
                    "status": execution["status"]
                }
            })
        
        return sorted(timeline, key=lambda x: x["timestamp"])
    
    async def get_workflow_bottlenecks(
        self,
        workflow_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Identify workflow bottlenecks.
        
        Args:
            workflow_id: Workflow ID
            days: Time period in days
            
        Returns:
            List of bottlenecks
        """
        # Placeholder implementation
        return []
    
    # ============================================================================
    # QUERY METHODS
    # ============================================================================
    
    async def get_workflow_by_id(
        self,
        workflow_id: UUID
    ) -> Dict[str, Any]:
        """Get workflow by ID."""
        # Placeholder implementation
        return {
            "id": workflow_id,
            "name": "Sample Workflow",
            "is_active": True,
            "version": 1
        }
    
    async def get_execution_by_id(
        self,
        execution_id: UUID
    ) -> Dict[str, Any]:
        """Get execution by ID."""
        # Placeholder implementation
        return {
            "id": execution_id,
            "workflow_id": uuid4(),
            "status": WorkflowStatus.ACTIVE
        }
    
    async def get_active_executions(
        self,
        workflow_id: UUID
    ) -> List[Dict[str, Any]]:
        """Get active executions for workflow."""
        # Placeholder implementation
        return []
    
    async def get_scheduled_task_by_id(
        self,
        scheduled_task_id: UUID
    ) -> Dict[str, Any]:
        """Get scheduled task by ID."""
        # Placeholder implementation
        return {
            "id": scheduled_task_id,
            "workflow_id": uuid4(),
            "schedule": "0 * * * *"
        }
    
    async def get_approval_request_by_id(
        self,
        approval_id: UUID
    ) -> Dict[str, Any]:
        """Get approval request by ID."""
        # Placeholder implementation
        return {
            "id": approval_id,
            "status": ApprovalStatus.PENDING,
            "approver_ids": []
        }
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    async def _validate_workflow_structure(
        self,
        tasks: List[Dict[str, Any]]
    ) -> None:
        """Validate workflow task structure."""
        if not tasks:
            raise ValidationException("Workflow must have at least one task")
        
        for i, task in enumerate(tasks):
            if "type" not in task:
                raise ValidationException(f"Task {i} missing 'type' field")
            
            task_type = task["type"]
            if task_type not in [t.value for t in TaskType]:
                raise ValidationException(f"Invalid task type: {task_type}")
    
    async def _validate_workflow_activation(
        self,
        workflow: Dict[str, Any]
    ) -> None:
        """Validate workflow can be activated."""
        if not workflow.get("tasks"):
            raise ValidationException("Cannot activate workflow without tasks")
        
        # Check trigger configuration
        trigger_type = workflow["trigger_type"]
        if trigger_type == WorkflowTriggerType.SCHEDULED:
            if "schedule" not in workflow["trigger_config"]:
                raise ValidationException("Scheduled workflow missing schedule")
    
    async def _setup_workflow_triggers(
        self,
        workflow: Dict[str, Any]
    ) -> None:
        """Setup workflow triggers."""
        trigger_type = workflow["trigger_type"]
        
        if trigger_type == WorkflowTriggerType.SCHEDULED:
            schedule = workflow["trigger_config"]["schedule"]
            await self.schedule_task(
                workflow["id"],
                schedule,
                workflow["trigger_config"]
            )
        
        elif trigger_type == WorkflowTriggerType.EVENT_BASED:
            # Register event listeners
            pass
        
        elif trigger_type == WorkflowTriggerType.WEBHOOK:
            # Register webhook endpoint
            pass
    
    async def _cleanup_workflow_triggers(
        self,
        workflow: Dict[str, Any]
    ) -> None:
        """Cleanup workflow triggers."""
        pass
    
    async def _archive_workflow_version(
        self,
        workflow: Dict[str, Any]
    ) -> None:
        """Archive workflow version."""
        pass
    
    async def _execute_workflow_tasks(
        self,
        workflow: Dict[str, Any],
        execution: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute all workflow tasks."""
        tasks = workflow["tasks"]
        context = execution["context"].copy()
        
        for i, task_def in enumerate(tasks):
            # Check if should skip based on conditions
            if "condition" in task_def:
                condition_met = await self.evaluate_condition(
                    task_def["condition"],
                    context
                )
                if not condition_met:
                    execution["completed_tasks"].append(i)
                    continue
            
            # Execute task
            task_result = await self.execute_task(
                execution["id"],
                i,
                task_def,
                context
            )
            
            execution["task_results"][str(i)] = task_result
            
            if task_result["status"] == TaskStatus.COMPLETED:
                execution["completed_tasks"].append(i)
                # Update context with task output
                if task_result["output_data"]:
                    context.update(task_result["output_data"])
            
            elif task_result["status"] == TaskStatus.FAILED:
                execution["failed_tasks"].append(i)
                
                # Check if should continue on failure
                if not task_def.get("continue_on_failure", False):
                    raise Exception(
                        f"Task {i} failed: {task_result['error_message']}"
                    )
            
            execution["current_task_index"] = i + 1
        
        return execution
    
    async def _execute_task_by_type(
        self,
        task_definition: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute task based on type."""
        task_type = task_definition["type"]
        
        if task_type == TaskType.EMAIL:
            return await self._execute_email_task(task_definition, context)
        
        elif task_type == TaskType.SMS:
            return await self._execute_sms_task(task_definition, context)
        
        elif task_type == TaskType.API_CALL:
            return await self._execute_api_call_task(task_definition, context)
        
        elif task_type == TaskType.DATA_SYNC:
            return await self._execute_data_sync_task(task_definition, context)
        
        elif task_type == TaskType.DELAY:
            return await self._execute_delay_task(task_definition, context)
        
        elif task_type == TaskType.SCRIPT:
            return await self._execute_script_task(task_definition, context)
        
        elif task_type == TaskType.WEBHOOK:
            return await self._execute_webhook_task(task_definition, context)
        
        elif task_type == TaskType.APPROVAL:
            return await self._execute_approval_task(task_definition, context)
        
        else:
            raise ValidationException(f"Unsupported task type: {task_type}")
    
    async def _execute_email_task(
        self,
        task_definition: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute email task."""
        # Placeholder implementation
        return {"sent": True}
    
    async def _execute_sms_task(
        self,
        task_definition: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute SMS task."""
        # Placeholder implementation
        return {"sent": True}
    
    async def _execute_api_call_task(
        self,
        task_definition: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute API call task."""
        # Placeholder implementation
        return {"status_code": 200, "response": {}}
    
    async def _execute_data_sync_task(
        self,
        task_definition: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute data sync task."""
        # Placeholder implementation
        return {"synced": 0}
    
    async def _execute_delay_task(
        self,
        task_definition: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute delay task."""
        import asyncio
        delay_seconds = task_definition.get("delay_seconds", 0)
        await asyncio.sleep(delay_seconds)
        return {"delayed_seconds": delay_seconds}
    
    async def _execute_script_task(
        self,
        task_definition: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute script task."""
        # Placeholder implementation
        return {"result": None}
    
    async def _execute_webhook_task(
        self,
        task_definition: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute webhook task."""
        # Placeholder implementation
        return {"status_code": 200}
    
    async def _execute_approval_task(
        self,
        task_definition: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute approval task."""
        # Create approval request and wait
        approval_request = await self.create_approval_request(
            workflow_id=context["workflow_id"],
            execution_id=context["execution_id"],
            task_index=context["task_index"],
            approver_ids=task_definition["approver_ids"],
            approval_data=task_definition.get("approval_data", {}),
            timeout_hours=task_definition.get("timeout_hours")
        )
        
        return {"approval_id": approval_request["id"]}
    
    async def _schedule_task_retry(
        self,
        task_execution: Dict[str, Any],
        task_definition: Dict[str, Any]
    ) -> None:
        """Schedule task retry."""
        pass
    
    async def _notify_approvers(
        self,
        approval_request: Dict[str, Any]
    ) -> None:
        """Notify approvers of pending approval."""
        pass
    
    async def _resume_workflow_after_approval(
        self,
        approval_request: Dict[str, Any]
    ) -> None:
        """Resume workflow execution after approval."""
        pass
    
    async def _handle_approval_rejection(
        self,
        approval_request: Dict[str, Any]
    ) -> None:
        """Handle approval rejection."""
        pass
    
    async def _execute_custom_condition(
        self,
        function_name: str,
        context: Dict[str, Any]
    ) -> bool:
        """Execute custom condition function."""
        # Placeholder implementation
        return True
    
    def _calculate_next_run(
        self,
        cron_expression: str
    ) -> datetime:
        """Calculate next run time from cron expression."""
        # Placeholder - would use cron library
        return datetime.utcnow() + timedelta(hours=1)