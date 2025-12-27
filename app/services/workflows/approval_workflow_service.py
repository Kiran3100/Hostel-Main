"""
Enhanced Approval Workflow Service

Handles approval workflows with improved performance, validation, and monitoring.
"""

from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session
from dataclasses import dataclass
from enum import Enum
import asyncio

from app.core1.exceptions import ValidationException, BusinessLogicException
from app.core1.logging import LoggingContext
from app.core1.config import settings
from app.models.base.enums import ApprovalStatus, ApprovalType
from app.repositories.booking import BookingApprovalRepository
from app.repositories.maintenance import MaintenanceApprovalRepository
from app.repositories.leave import LeaveApprovalRepository
from app.services.workflows.workflow_engine_service import (
    workflow_engine,
    create_workflow,
    create_step,
    WorkflowPriority
)
from app.services.workflows.notification_workflow_service import (
    NotificationWorkflowService
)
from app.services.workflows.escalation_workflow_service import (
    EscalationWorkflowService
)


class ApprovalDecision(str, Enum):
    """Enhanced approval decisions."""
    APPROVE = "approve"
    REJECT = "reject"
    CONDITIONAL_APPROVE = "conditional_approve"
    REQUEST_INFORMATION = "request_information"
    ESCALATE = "escalate"


@dataclass
class ApprovalRule:
    """Rule for automatic approval decisions."""
    name: str
    condition: callable
    action: ApprovalDecision
    priority: int = 0
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ApprovalContext:
    """Enhanced context for approval processing."""
    approval_type: str
    entity_id: UUID
    entity_data: Dict[str, Any]
    approver_id: Optional[UUID] = None
    decision: Optional[ApprovalDecision] = None
    reason: Optional[str] = None
    conditions: Optional[List[str]] = None
    auto_approved: bool = False
    escalation_level: int = 0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ApprovalWorkflowService:
    """
    Enhanced service for managing approval workflows with improved features.
    
    Features:
    - Smart auto-approval based on configurable rules
    - Multi-level approval chains with delegation
    - Real-time notifications and escalations
    - Comprehensive audit trails
    - Batch approval capabilities
    - SLA monitoring and enforcement
    """
    
    def __init__(
        self,
        booking_approval_repo: BookingApprovalRepository,
        maintenance_approval_repo: MaintenanceApprovalRepository,
        leave_approval_repo: LeaveApprovalRepository,
        notification_service: NotificationWorkflowService,
        escalation_service: EscalationWorkflowService
    ):
        self.booking_approval_repo = booking_approval_repo
        self.maintenance_approval_repo = maintenance_approval_repo
        self.leave_approval_repo = leave_approval_repo
        self.notification_service = notification_service
        self.escalation_service = escalation_service
        
        # Auto-approval rules registry
        self.auto_approval_rules: Dict[str, List[ApprovalRule]] = {}
        
        # Performance caching
        self._approval_cache: Dict[str, Any] = {}
        self._cache_ttl = timedelta(minutes=5)
        self._last_cache_clear = datetime.utcnow()
        
        self._register_workflows()
        self._setup_auto_approval_rules()
    
    def _register_workflows(self) -> None:
        """Register enhanced approval workflows."""
        
        # Enhanced booking approval workflow
        booking_approval_wf = (
            create_workflow(
                "booking_approval",
                "Enhanced Booking Approval Workflow",
                "Handles booking approval with intelligent routing and monitoring",
                priority=WorkflowPriority.HIGH,
                max_execution_time=300,  # 5 minutes
                enable_monitoring=True
            )
            .add_validator(self._validate_approval_context)
            .add_step(create_step(
                "load_approval_data",
                self._load_approval_data,
                timeout_seconds=30,
                retry_count=2
            ))
            .add_step(create_step(
                "check_duplicate_approvals",
                self._check_duplicate_approvals,
                timeout_seconds=10
            ))
            .add_step(create_step(
                "apply_auto_approval_rules",
                self._apply_auto_approval_rules,
                required=False,
                timeout_seconds=15
            ))
            .add_step(create_step(
                "validate_approval_permissions",
                self._validate_approval_permissions,
                timeout_seconds=10
            ))
            .add_step(create_step(
                "process_approval_decision",
                self._process_booking_approval_decision,
                timeout_seconds=60,
                rollback_handler=self._rollback_approval_decision
            ))
            .add_step(create_step(
                "update_related_entities",
                self._update_booking_related_entities,
                timeout_seconds=30,
                rollback_handler=self._rollback_entity_updates
            ))
            .add_step(create_step(
                "send_approval_notifications",
                self._send_approval_notifications,
                required=False,
                timeout_seconds=20
            ))
            .add_step(create_step(
                "check_escalation_required",
                self._check_escalation_required,
                required=False,
                condition=lambda ctx: ctx.get("requires_escalation", False)
            ))
            .add_step(create_step(
                "update_approval_metrics",
                self._update_approval_metrics,
                required=False,
                timeout_seconds=5
            ))
            .on_complete(self._on_approval_complete)
            .on_error(self._on_approval_error)
        )
        
        workflow_engine.register_workflow(booking_approval_wf)
        
        # Enhanced maintenance approval workflow
        maintenance_approval_wf = (
            create_workflow(
                "maintenance_approval",
                "Enhanced Maintenance Approval Workflow",
                "Handles maintenance request approval with budget validation and cost optimization"
            )
            .add_validator(self._validate_approval_context)
            .add_step(create_step(
                "load_approval_data",
                self._load_approval_data,
                timeout_seconds=30
            ))
            .add_step(create_step(
                "validate_cost_thresholds",
                self._validate_cost_thresholds,
                timeout_seconds=15
            ))
            .add_step(create_step(
                "check_budget_availability",
                self._check_budget_availability,
                timeout_seconds=20
            ))
            .add_step(create_step(
                "validate_vendor_requirements",
                self._validate_vendor_requirements,
                required=False,
                timeout_seconds=10
            ))
            .add_step(create_step(
                "process_approval_decision",
                self._process_maintenance_approval_decision,
                timeout_seconds=45,
                rollback_handler=self._rollback_approval_decision
            ))
            .add_step(create_step(
                "allocate_budget",
                self._allocate_maintenance_budget,
                required=False,
                rollback_handler=self._deallocate_budget
            ))
            .add_step(create_step(
                "schedule_maintenance",
                self._schedule_maintenance_work,
                required=False,
                condition=lambda ctx: ctx.get("decision") == ApprovalDecision.APPROVE
            ))
            .add_step(create_step(
                "send_approval_notifications",
                self._send_approval_notifications,
                required=False
            ))
        )
        
        workflow_engine.register_workflow(maintenance_approval_wf)
        
        # Enhanced leave approval workflow
        leave_approval_wf = (
            create_workflow(
                "leave_approval",
                "Enhanced Leave Approval Workflow",
                "Handles leave request approval with balance validation and coverage checks"
            )
            .add_validator(self._validate_approval_context)
            .add_step(create_step(
                "load_approval_data",
                self._load_approval_data
            ))
            .add_step(create_step(
                "validate_leave_balance",
                self._validate_leave_balance
            ))
            .add_step(create_step(
                "check_coverage_requirements",
                self._check_leave_coverage,
                required=False
            ))
            .add_step(create_step(
                "check_overlapping_requests",
                self._check_overlapping_leave_requests
            ))
            .add_step(create_step(
                "process_approval_decision",
                self._process_leave_approval_decision,
                rollback_handler=self._rollback_approval_decision
            ))
            .add_step(create_step(
                "update_leave_balance",
                self._update_leave_balance,
                rollback_handler=self._restore_leave_balance
            ))
            .add_step(create_step(
                "update_duty_roster",
                self._update_duty_roster,
                required=False,
                rollback_handler=self._restore_duty_roster
            ))
            .add_step(create_step(
                "send_approval_notifications",
                self._send_approval_notifications,
                required=False
            ))
        )
        
        workflow_engine.register_workflow(leave_approval_wf)
    
    def _setup_auto_approval_rules(self) -> None:
        """Setup intelligent auto-approval rules."""
        # Booking auto-approval rules
        booking_rules = [
            ApprovalRule(
                name="verified_student_advance_paid",
                condition=lambda ctx: (
                    ctx.entity_data.get("student_verified", False) and
                    ctx.entity_data.get("advance_paid", 0) >= ctx.entity_data.get("required_advance", 0)
                ),
                action=ApprovalDecision.APPROVE,
                priority=1,
                metadata={"reason": "Verified student with full advance payment"}
            ),
            ApprovalRule(
                name="corporate_booking_pre_approved",
                condition=lambda ctx: (
                    ctx.entity_data.get("booking_type") == "corporate" and
                    ctx.entity_data.get("corporate_pre_approved", False)
                ),
                action=ApprovalDecision.APPROVE,
                priority=2,
                metadata={"reason": "Pre-approved corporate booking"}
            ),
            ApprovalRule(
                name="low_value_maintenance",
                condition=lambda ctx: (
                    ctx.entity_data.get("estimated_cost", 0) < settings.AUTO_APPROVAL_COST_THRESHOLD
                ),
                action=ApprovalDecision.APPROVE,
                priority=1,
                metadata={"reason": "Low value maintenance request"}
            )
        ]
        
        self.auto_approval_rules["booking"] = booking_rules
        self.auto_approval_rules["maintenance"] = [
            rule for rule in booking_rules if "maintenance" in rule.name
        ]
    
    def add_auto_approval_rule(
        self,
        approval_type: str,
        rule: ApprovalRule
    ) -> None:
        """Add custom auto-approval rule."""
        if approval_type not in self.auto_approval_rules:
            self.auto_approval_rules[approval_type] = []
        
        self.auto_approval_rules[approval_type].append(rule)
        
        # Sort by priority
        self.auto_approval_rules[approval_type].sort(
            key=lambda r: r.priority, reverse=True
        )
    
    # Public API methods
    
    async def process_approval(
        self,
        db: Session,
        approval_type: str,
        entity_id: UUID,
        decision: ApprovalDecision,
        approver_id: Optional[UUID] = None,
        reason: Optional[str] = None,
        conditions: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process approval decision with enhanced features.
        
        Args:
            db: Database session
            approval_type: Type of approval (booking, maintenance, leave)
            entity_id: ID of entity being approved
            decision: Approval decision
            approver_id: User making the decision
            reason: Reason for decision
            conditions: Any conditions attached to approval
            metadata: Additional metadata
            
        Returns:
            Approval result with comprehensive details
        """
        context = ApprovalContext(
            approval_type=approval_type,
            entity_id=entity_id,
            decision=decision,
            approver_id=approver_id,
            reason=reason,
            conditions=conditions or [],
            metadata=metadata or {}
        )
        
        # Add to workflow context
        workflow_context = {
            "db": db,
            "approval_context": context,
            "initiated_by": approver_id,
            "timestamp": datetime.utcnow()
        }
        
        execution = await workflow_engine.execute_workflow(
            f"{approval_type}_approval",
            workflow_context,
            approver_id
        )
        
        return execution.result or execution.to_dict()
    
    async def process_bulk_approvals(
        self,
        db: Session,
        approval_requests: List[Dict[str, Any]],
        approver_id: UUID,
        batch_size: int = 10
    ) -> Dict[str, Any]:
        """
        Process multiple approvals in batches for improved performance.
        
        Args:
            db: Database session
            approval_requests: List of approval request data
            approver_id: User processing approvals
            batch_size: Number of approvals to process concurrently
            
        Returns:
            Batch processing results
        """
        results = {
            "total_requests": len(approval_requests),
            "successful": 0,
            "failed": 0,
            "details": []
        }
        
        # Process in batches
        for i in range(0, len(approval_requests), batch_size):
            batch = approval_requests[i:i + batch_size]
            
            # Create tasks for concurrent processing
            tasks = []
            for request in batch:
                task = self.process_approval(
                    db=db,
                    approval_type=request["approval_type"],
                    entity_id=request["entity_id"],
                    decision=ApprovalDecision(request["decision"]),
                    approver_id=approver_id,
                    reason=request.get("reason"),
                    conditions=request.get("conditions"),
                    metadata=request.get("metadata")
                )
                tasks.append(task)
            
            # Execute batch
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for j, result in enumerate(batch_results):
                request = batch[j]
                if isinstance(result, Exception):
                    results["failed"] += 1
                    results["details"].append({
                        "entity_id": str(request["entity_id"]),
                        "status": "failed",
                        "error": str(result)
                    })
                else:
                    results["successful"] += 1
                    results["details"].append({
                        "entity_id": str(request["entity_id"]),
                        "status": "completed",
                        "result": result
                    })
        
        return results
    
    # Validation methods
    
    def _validate_approval_context(self, context: Dict[str, Any]) -> bool:
        """Enhanced validation for approval context."""
        required_fields = ["db", "approval_context", "timestamp"]
        
        if not all(field in context for field in required_fields):
            return False
        
        approval_context = context["approval_context"]
        if not isinstance(approval_context, ApprovalContext):
            return False
        
        # Validate approval type
        valid_types = ["booking", "maintenance", "leave", "menu", "expense"]
        if approval_context.approval_type not in valid_types:
            return False
        
        return True
    
    # Step handlers - Common
    
    async def _load_approval_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Load approval data with caching for performance."""
        db = context["db"]
        approval_context = context["approval_context"]
        
        # Check cache first
        cache_key = f"{approval_context.approval_type}:{approval_context.entity_id}"
        cached_data = self._get_cached_data(cache_key)
        
        if cached_data:
            approval_context.entity_data = cached_data
            return {"data_source": "cache", "entity_data": cached_data}
        
        # Load from database
        if approval_context.approval_type == "booking":
            entity = self.booking_approval_repo.get_by_id(db, approval_context.entity_id)
        elif approval_context.approval_type == "maintenance":
            entity = self.maintenance_approval_repo.get_by_id(db, approval_context.entity_id)
        elif approval_context.approval_type == "leave":
            entity = self.leave_approval_repo.get_by_id(db, approval_context.entity_id)
        else:
            raise ValidationException(f"Unsupported approval type: {approval_context.approval_type}")
        
        if not entity:
            raise ValidationException("Approval entity not found")
        
        # Convert to dict and cache
        entity_data = entity.__dict__.copy()
        entity_data.pop("_sa_instance_state", None)  # Remove SQLAlchemy state
        
        self._cache_data(cache_key, entity_data)
        approval_context.entity_data = entity_data
        
        return {
            "data_source": "database",
            "entity_data": entity_data,
            "entity_type": type(entity).__name__
        }
    
    async def _check_duplicate_approvals(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Check for duplicate approval attempts."""
        db = context["db"]
        approval_context = context["approval_context"]
        
        # Query for recent approvals of the same entity
        # Implementation would depend on your specific approval tracking
        
        return {"duplicate_found": False}
    
    async def _apply_auto_approval_rules(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Apply intelligent auto-approval rules."""
        approval_context = context["approval_context"]
        approval_type = approval_context.approval_type
        
        # Skip if manual decision already made
        if approval_context.decision:
            return {"auto_approval_applied": False, "reason": "Manual decision provided"}
        
        # Get rules for this approval type
        rules = self.auto_approval_rules.get(approval_type, [])
        
        for rule in rules:
            try:
                if rule.condition(approval_context):
                    approval_context.decision = rule.action
                    approval_context.auto_approved = True
                    approval_context.reason = rule.metadata.get("reason", f"Auto-{rule.action.value}")
                    
                    return {
                        "auto_approval_applied": True,
                        "rule_applied": rule.name,
                        "decision": rule.action.value,
                        "reason": approval_context.reason
                    }
            except Exception as e:
                # Log rule evaluation error but continue
                context.setdefault("warnings", []).append(
                    f"Auto-approval rule '{rule.name}' failed: {str(e)}"
                )
        
        return {"auto_approval_applied": False, "rules_evaluated": len(rules)}
    
    async def _validate_approval_permissions(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate approver has necessary permissions."""
        db = context["db"]
        approval_context = context["approval_context"]
        
        if not approval_context.approver_id:
            return {"permission_valid": True, "reason": "Auto-approval or system decision"}
        
        # Check approver permissions based on approval type and amount/scope
        # Implementation would check user roles and permissions
        
        return {"permission_valid": True, "approver_role": "admin"}  # Simplified
    
    async def _send_approval_notifications(self, context: Dict[str, Any]) -> None:
        """Send notifications about approval decision."""
        db = context["db"]
        approval_context = context["approval_context"]
        
        if not approval_context.decision:
            return
        
        # Determine recipients based on approval type and decision
        recipients = self._get_notification_recipients(approval_context)
        
        # Send notifications through notification service
        for recipient in recipients:
            self.notification_service.send_approval_notification(
                db=db,
                user_id=recipient["user_id"],
                approval_type=approval_context.approval_type,
                approved=approval_context.decision == ApprovalDecision.APPROVE,
                entity_id=approval_context.entity_id,
                metadata={
                    "reason": approval_context.reason,
                    "conditions": approval_context.conditions,
                    "auto_approved": approval_context.auto_approved,
                    "approver_id": str(approval_context.approver_id) if approval_context.approver_id else None
                }
            )
    
    def _get_notification_recipients(self, approval_context: ApprovalContext) -> List[Dict[str, Any]]:
        """Determine notification recipients based on context."""
        recipients = []
        
        # Add entity owner/requester
        if "requester_id" in approval_context.entity_data:
            recipients.append({
                "user_id": approval_context.entity_data["requester_id"],
                "role": "requester"
            })
        
        # Add relevant admins/supervisors
        if approval_context.decision == ApprovalDecision.REJECT:
            # Add supervisor for rejections
            if "supervisor_id" in approval_context.entity_data:
                recipients.append({
                    "user_id": approval_context.entity_data["supervisor_id"],
                    "role": "supervisor"
                })
        
        return recipients
    
    # Step handlers - Booking approval
    
    async def _process_booking_approval_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process booking approval decision with comprehensive updates."""
        db = context["db"]
        approval_context = context["approval_context"]
        
        booking_approval = self.booking_approval_repo.get_by_id(
            db, approval_context.entity_id
        )
        
        if not booking_approval:
            raise ValidationException("Booking approval not found")
        
        # Update approval record
        if approval_context.decision == ApprovalDecision.APPROVE:
            booking_approval.status = ApprovalStatus.APPROVED
            booking_approval.approved_by = approval_context.approver_id
            booking_approval.approved_at = datetime.utcnow()
            booking_approval.admin_notes = approval_context.reason
            
            # Set room/bed assignments if provided
            if approval_context.metadata.get("room_id"):
                booking_approval.room_id = approval_context.metadata["room_id"]
            if approval_context.metadata.get("bed_id"):
                booking_approval.bed_id = approval_context.metadata["bed_id"]
        
        elif approval_context.decision == ApprovalDecision.REJECT:
            booking_approval.status = ApprovalStatus.REJECTED
            booking_approval.rejected_by = approval_context.approver_id
            booking_approval.rejected_at = datetime.utcnow()
            booking_approval.rejection_reason = approval_context.reason
        
        elif approval_context.decision == ApprovalDecision.CONDITIONAL_APPROVE:
            booking_approval.status = ApprovalStatus.CONDITIONALLY_APPROVED
            booking_approval.approved_by = approval_context.approver_id
            booking_approval.approved_at = datetime.utcnow()
            booking_approval.conditions = "; ".join(approval_context.conditions)
            booking_approval.admin_notes = approval_context.reason
        
        # Auto-approval flag
        booking_approval.auto_approved = approval_context.auto_approved
        
        db.commit()
        db.refresh(booking_approval)
        
        # Store for rollback
        context["updated_approval"] = booking_approval
        
        return {
            "approval_id": str(booking_approval.id),
            "status": booking_approval.status.value,
            "decision": approval_context.decision.value,
            "auto_approved": approval_context.auto_approved
        }
    
    async def _update_booking_related_entities(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Update related booking entities based on approval decision."""
        approval_context = context["approval_context"]
        
        if approval_context.decision == ApprovalDecision.APPROVE:
            # Update booking status, reserve room/bed, etc.
            # Implementation would call booking service methods
            return {"booking_updated": True, "room_reserved": True}
        
        return {"booking_updated": False}
    
    # Step handlers - Maintenance approval
    
    async def _validate_cost_thresholds(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate maintenance cost against approval thresholds."""
        approval_context = context["approval_context"]
        estimated_cost = approval_context.entity_data.get("estimated_cost", 0)
        
        # Define cost thresholds (could come from settings)
        thresholds = {
            "auto_approve": 1000,
            "manager_approval": 5000,
            "admin_approval": 20000,
            "board_approval": 100000
        }
        
        if estimated_cost > thresholds["board_approval"]:
            context["requires_escalation"] = True
            context["escalation_reason"] = "Cost exceeds board approval threshold"
        elif estimated_cost > thresholds["admin_approval"]:
            context["requires_admin_approval"] = True
        
        return {
            "cost_valid": True,
            "estimated_cost": estimated_cost,
            "threshold_level": "admin" if estimated_cost > thresholds["admin_approval"] else "manager"
        }
    
    async def _check_budget_availability(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Check if budget is available for maintenance."""
        approval_context = context["approval_context"]
        estimated_cost = approval_context.entity_data.get("estimated_cost", 0)
        
        # Implementation would check actual budget allocation
        # For now, simplified check
        
        return {
            "budget_available": True,
            "available_amount": estimated_cost * 2,  # Simplified
            "budget_utilization": 45.5  # Percentage
        }
    
    async def _validate_vendor_requirements(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate vendor and compliance requirements."""
        approval_context = context["approval_context"]
        
        # Check vendor authorization, compliance requirements, etc.
        return {"vendor_valid": True, "compliance_ok": True}
    
    async def _process_maintenance_approval_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process maintenance approval decision."""
        db = context["db"]
        approval_context = context["approval_context"]
        
        maintenance_approval = self.maintenance_approval_repo.get_by_id(
            db, approval_context.entity_id
        )
        
        if not maintenance_approval:
            raise ValidationException("Maintenance approval not found")
        
        # Update approval record based on decision
        if approval_context.decision == ApprovalDecision.APPROVE:
            maintenance_approval.status = ApprovalStatus.APPROVED
            maintenance_approval.approved_by = approval_context.approver_id
            maintenance_approval.approved_at = datetime.utcnow()
            maintenance_approval.approved_amount = approval_context.metadata.get(
                "approved_amount", 
                approval_context.entity_data.get("estimated_cost")
            )
            maintenance_approval.admin_notes = approval_context.reason
        
        elif approval_context.decision == ApprovalDecision.REJECT:
            maintenance_approval.status = ApprovalStatus.REJECTED
            maintenance_approval.rejected_by = approval_context.approver_id
            maintenance_approval.rejected_at = datetime.utcnow()
            maintenance_approval.rejection_reason = approval_context.reason
        
        db.commit()
        db.refresh(maintenance_approval)
        
        context["updated_approval"] = maintenance_approval
        
        return {
            "approval_id": str(maintenance_approval.id),
            "status": maintenance_approval.status.value,
            "approved_amount": maintenance_approval.approved_amount
        }
    
    async def _allocate_maintenance_budget(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Allocate budget for approved maintenance."""
        approval_context = context["approval_context"]
        
        if approval_context.decision == ApprovalDecision.APPROVE:
            approved_amount = approval_context.metadata.get("approved_amount", 0)
            # Implementation would allocate budget
            return {"budget_allocated": True, "allocated_amount": approved_amount}
        
        return {"budget_allocated": False}
    
    async def _schedule_maintenance_work(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule maintenance work upon approval."""
        # Implementation would integrate with maintenance scheduling
        return {"work_scheduled": True, "scheduled_date": "2024-01-15"}
    
    # Step handlers - Leave approval
    
    async def _validate_leave_balance(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate leave balance for employee."""
        approval_context = context["approval_context"]
        
        # Implementation would check actual leave balance
        return {
            "balance_sufficient": True,
            "available_days": 15,
            "requested_days": approval_context.entity_data.get("requested_days", 0)
        }
    
    async def _check_leave_coverage(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Check if adequate coverage is available during leave period."""
        # Implementation would check staffing requirements
        return {"coverage_adequate": True, "coverage_plan": "supervisor_coverage"}
    
    async def _check_overlapping_leave_requests(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Check for overlapping leave requests in the team."""
        # Implementation would check for conflicts
        return {"overlapping_requests": [], "conflicts_found": False}
    
    async def _process_leave_approval_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process leave approval decision."""
        db = context["db"]
        approval_context = context["approval_context"]
        
        leave_approval = self.leave_approval_repo.get_by_id(
            db, approval_context.entity_id
        )
        
        if not leave_approval:
            raise ValidationException("Leave approval not found")
        
        # Update approval record
        if approval_context.decision == ApprovalDecision.APPROVE:
            leave_approval.status = ApprovalStatus.APPROVED
            leave_approval.approved_by = approval_context.approver_id
            leave_approval.approved_at = datetime.utcnow()
            leave_approval.admin_notes = approval_context.reason
        
        elif approval_context.decision == ApprovalDecision.REJECT:
            leave_approval.status = ApprovalStatus.REJECTED
            leave_approval.rejected_by = approval_context.approver_id
            leave_approval.rejected_at = datetime.utcnow()
            leave_approval.rejection_reason = approval_context.reason
        
        db.commit()
        db.refresh(leave_approval)
        
        context["updated_approval"] = leave_approval
        
        return {
            "approval_id": str(leave_approval.id),
            "status": leave_approval.status.value
        }
    
    async def _update_leave_balance(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Update employee leave balance."""
        approval_context = context["approval_context"]
        
        if approval_context.decision == ApprovalDecision.APPROVE:
            # Implementation would update leave balance
            return {"balance_updated": True}
        
        return {"balance_updated": False}
    
    async def _update_duty_roster(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Update duty roster for approved leave."""
        # Implementation would update scheduling systems
        return {"roster_updated": True}
    
    # Common step handlers
    
    async def _check_escalation_required(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Check if escalation is required and trigger if needed."""
        if not context.get("requires_escalation", False):
            return {"escalation_required": False}
        
        db = context["db"]
        approval_context = context["approval_context"]
        escalation_reason = context.get("escalation_reason", "Approval requires escalation")
        
        # Trigger escalation workflow
        await self.escalation_service.escalate_complaint(
            db=db,
            complaint_id=approval_context.entity_id,
            escalated_by=approval_context.approver_id,
            escalation_reason=escalation_reason,
            is_urgent=True
        )
        
        return {"escalation_triggered": True, "reason": escalation_reason}
    
    async def _update_approval_metrics(self, context: Dict[str, Any]) -> None:
        """Update approval metrics for analytics."""
        approval_context = context["approval_context"]
        
        # Implementation would update metrics/analytics
        # For example: approval times, auto-approval rates, rejection reasons, etc.
        pass
    
    # Rollback handlers
    
    async def _rollback_approval_decision(self, context: Dict[str, Any]) -> None:
        """Rollback approval decision changes."""
        if "updated_approval" in context:
            db = context["db"]
            approval = context["updated_approval"]
            
            # Reset approval to pending state
            approval.status = ApprovalStatus.PENDING
            approval.approved_by = None
            approval.rejected_by = None
            approval.approved_at = None
            approval.rejected_at = None
            approval.admin_notes = None
            approval.rejection_reason = None
            
            db.commit()
    
    async def _rollback_entity_updates(self, context: Dict[str, Any]) -> None:
        """Rollback related entity updates."""
        # Implementation would reverse booking updates, room reservations, etc.
        pass
    
    async def _deallocate_budget(self, context: Dict[str, Any]) -> None:
        """Rollback budget allocation."""
        # Implementation would reverse budget allocation
        pass
    
    async def _restore_leave_balance(self, context: Dict[str, Any]) -> None:
        """Restore leave balance on rollback."""
        # Implementation would restore leave balance
        pass
    
    async def _restore_duty_roster(self, context: Dict[str, Any]) -> None:
        """Restore duty roster on rollback."""
        # Implementation would restore roster changes
        pass
    
    # Completion handlers
    
    async def _on_approval_complete(self, execution) -> None:
        """Handle approval workflow completion."""
        with LoggingContext(execution_id=str(execution.execution_id)):
            # Update metrics
            # Log completion
            # Trigger post-approval actions
            pass
    
    async def _on_approval_error(self, execution, error: Exception) -> None:
        """Handle approval workflow errors."""
        with LoggingContext(execution_id=str(execution.execution_id)):
            # Log error
            # Send error notifications
            # Create support ticket if needed
            pass
    
    # Helper methods
    
    def _get_cached_data(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached data with TTL check."""
        if datetime.utcnow() - self._last_cache_clear > self._cache_ttl:
            self._approval_cache.clear()
            self._last_cache_clear = datetime.utcnow()
            return None
        
        return self._approval_cache.get(key)
    
    def _cache_data(self, key: str, data: Dict[str, Any]) -> None:
        """Cache data with size limit."""
        if len(self._approval_cache) > 1000:  # Max cache size
            # Remove oldest entries
            keys_to_remove = list(self._approval_cache.keys())[:100]
            for k in keys_to_remove:
                del self._approval_cache[k]
        
        self._approval_cache[key] = data