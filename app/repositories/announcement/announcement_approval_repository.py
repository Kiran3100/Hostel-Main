"""
Announcement Approval Repository

Approval workflow management with multi-level approval, SLA tracking, and decision history.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from decimal import Decimal

from sqlalchemy import and_, or_, func, select, case
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql import Select

from app.models.announcement import (
    AnnouncementApproval,
    ApprovalWorkflow,
    ApprovalHistory,
    ApprovalRule,
    Announcement,
)
from app.models.user.user import User
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.pagination import PaginationParams, PaginatedResult
from app.core1.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    BusinessLogicError,
)


class AnnouncementApprovalRepository(BaseRepository[AnnouncementApproval]):
    """
    Repository for announcement approval workflows.
    
    Provides comprehensive approval management including:
    - Multi-level approval workflows
    - Automatic approval rules
    - SLA monitoring and escalation
    - Approval history and audit trail
    - Performance analytics
    - Assignment and routing
    """
    
    def __init__(self, session: Session):
        super().__init__(AnnouncementApproval, session)
    
    # ==================== Approval Request Management ====================
    
    def create_approval_request(
        self,
        announcement_id: UUID,
        requested_by_id: UUID,
        approval_reason: Optional[str] = None,
        is_urgent: bool = False,
        preferred_approver_id: Optional[UUID] = None,
        auto_publish: bool = True
    ) -> AnnouncementApproval:
        """
        Create approval request for announcement.
        
        Args:
            announcement_id: Announcement UUID
            requested_by_id: Requester user UUID
            approval_reason: Justification for approval
            is_urgent: Urgent approval flag
            preferred_approver_id: Preferred approver UUID
            auto_publish: Auto-publish on approval
            
        Returns:
            Created approval request
        """
        # Check if already has approval request
        existing = self.find_by_announcement(announcement_id)
        if existing:
            raise BusinessLogicError(
                f"Approval request already exists for announcement {announcement_id}"
            )
        
        # Get announcement
        announcement = self.session.get(Announcement, announcement_id)
        if not announcement:
            raise ResourceNotFoundError(
                f"Announcement {announcement_id} not found"
            )
        
        # Calculate SLA deadline
        sla_deadline = self._calculate_sla_deadline(
            announcement.hostel_id,
            is_urgent
        )
        
        approval = AnnouncementApproval(
            announcement_id=announcement_id,
            requested_by_id=requested_by_id,
            approval_reason=approval_reason,
            is_urgent_request=is_urgent,
            preferred_approver_id=preferred_approver_id,
            auto_publish_on_approval=auto_publish,
            approval_status='pending',
            submitted_at=datetime.utcnow(),
            sla_deadline=sla_deadline,
        )
        
        self.session.add(approval)
        self.session.flush()
        
        # Record in history
        self._record_history(
            approval=approval,
            action='submitted',
            performed_by_id=requested_by_id,
            previous_status=None,
            new_status='pending',
            notes=approval_reason
        )
        
        # Check auto-approval rules
        if self._check_auto_approval(approval):
            return self.auto_approve(approval.id)
        
        # Assign to approver
        self._assign_approver(approval)
        
        self.session.flush()
        return approval
    
    def approve_announcement(
        self,
        approval_id: UUID,
        approved_by_id: UUID,
        approval_notes: Optional[str] = None,
        auto_publish: Optional[bool] = None
    ) -> AnnouncementApproval:
        """
        Approve announcement.
        
        Args:
            approval_id: Approval request UUID
            approved_by_id: Approver user UUID
            approval_notes: Approval notes
            auto_publish: Override auto-publish setting
            
        Returns:
            Approved request
        """
        approval = self.find_by_id(approval_id)
        if not approval:
            raise ResourceNotFoundError(f"Approval {approval_id} not found")
        
        if approval.approval_status != 'pending':
            raise BusinessLogicError(
                f"Cannot approve request in {approval.approval_status} status"
            )
        
        # Verify approver has authority
        self._verify_approval_authority(approved_by_id, approval)
        
        now = datetime.utcnow()
        
        # Update approval
        approval.approved = True
        approval.decided_by_id = approved_by_id
        approval.decided_at = now
        approval.approval_status = 'approved'
        approval.approval_notes = approval_notes
        
        # Calculate time pending
        if approval.submitted_at:
            time_diff = now - approval.submitted_at
            approval.time_pending_hours = time_diff.total_seconds() / 3600
        
        # Record in history
        self._record_history(
            approval=approval,
            action='approved',
            performed_by_id=approved_by_id,
            previous_status='pending',
            new_status='approved',
            notes=approval_notes
        )
        
        # Auto-publish if configured
        should_publish = (
            auto_publish if auto_publish is not None
            else approval.auto_publish_on_approval
        )
        
        if should_publish:
            self._publish_announcement(approval, approved_by_id)
        
        self.session.flush()
        return approval
    
    def reject_announcement(
        self,
        approval_id: UUID,
        rejected_by_id: UUID,
        rejection_reason: str,
        suggested_modifications: Optional[str] = None,
        allow_resubmission: bool = True
    ) -> AnnouncementApproval:
        """
        Reject announcement.
        
        Args:
            approval_id: Approval request UUID
            rejected_by_id: Rejector user UUID
            rejection_reason: Reason for rejection
            suggested_modifications: Suggestions for improvement
            allow_resubmission: Allow resubmission
            
        Returns:
            Rejected request
        """
        approval = self.find_by_id(approval_id)
        if not approval:
            raise ResourceNotFoundError(f"Approval {approval_id} not found")
        
        if approval.approval_status != 'pending':
            raise BusinessLogicError(
                f"Cannot reject request in {approval.approval_status} status"
            )
        
        # Verify rejector has authority
        self._verify_approval_authority(rejected_by_id, approval)
        
        now = datetime.utcnow()
        
        # Update approval
        approval.approved = False
        approval.decided_by_id = rejected_by_id
        approval.decided_at = now
        approval.approval_status = 'rejected'
        approval.rejection_reason = rejection_reason
        approval.suggested_modifications = suggested_modifications
        approval.allow_resubmission = allow_resubmission
        
        # Calculate time pending
        if approval.submitted_at:
            time_diff = now - approval.submitted_at
            approval.time_pending_hours = time_diff.total_seconds() / 3600
        
        # Record in history
        self._record_history(
            approval=approval,
            action='rejected',
            performed_by_id=rejected_by_id,
            previous_status='pending',
            new_status='rejected',
            notes=f"{rejection_reason}\n\nSuggestions: {suggested_modifications or 'None'}"
        )
        
        self.session.flush()
        return approval
    
    def resubmit_for_approval(
        self,
        approval_id: UUID,
        resubmitted_by_id: UUID,
        changes_made: str,
        new_approval_reason: Optional[str] = None
    ) -> AnnouncementApproval:
        """
        Resubmit rejected announcement for approval.
        
        Args:
            approval_id: Original approval UUID
            resubmitted_by_id: User resubmitting
            changes_made: Description of changes
            new_approval_reason: Updated approval reason
            
        Returns:
            Updated approval request
        """
        approval = self.find_by_id(approval_id)
        if not approval:
            raise ResourceNotFoundError(f"Approval {approval_id} not found")
        
        if approval.approval_status != 'rejected':
            raise BusinessLogicError(
                f"Can only resubmit rejected requests"
            )
        
        if not approval.allow_resubmission:
            raise BusinessLogicError(
                "Resubmission not allowed for this request"
            )
        
        # Reset approval status
        approval.approval_status = 'pending'
        approval.approved = None
        approval.decided_by_id = None
        approval.decided_at = None
        approval.submitted_at = datetime.utcnow()
        
        if new_approval_reason:
            approval.approval_reason = new_approval_reason
        
        # Recalculate SLA
        approval.sla_deadline = self._calculate_sla_deadline(
            approval.announcement.hostel_id,
            approval.is_urgent_request
        )
        approval.sla_breached = False
        
        # Record in history
        self._record_history(
            approval=approval,
            action='resubmitted',
            performed_by_id=resubmitted_by_id,
            previous_status='rejected',
            new_status='pending',
            notes=f"Resubmitted after changes: {changes_made}"
        )
        
        # Reassign
        self._assign_approver(approval)
        
        self.session.flush()
        return approval
    
    # ==================== Assignment and Routing ====================
    
    def assign_to_approver(
        self,
        approval_id: UUID,
        approver_id: UUID,
        assigned_by_id: Optional[UUID] = None
    ) -> AnnouncementApproval:
        """
        Manually assign approval to specific approver.
        
        Args:
            approval_id: Approval UUID
            approver_id: Approver user UUID
            assigned_by_id: User making assignment
            
        Returns:
            Updated approval
        """
        approval = self.find_by_id(approval_id)
        if not approval:
            raise ResourceNotFoundError(f"Approval {approval_id} not found")
        
        if approval.approval_status != 'pending':
            raise BusinessLogicError(
                f"Cannot assign approval in {approval.approval_status} status"
            )
        
        # Verify approver has authority
        self._verify_approval_authority(approver_id, approval)
        
        approval.assigned_to_id = approver_id
        approval.assigned_at = datetime.utcnow()
        
        # Record in history
        self._record_history(
            approval=approval,
            action='assigned',
            performed_by_id=assigned_by_id or approver_id,
            previous_status='pending',
            new_status='pending',
            notes=f"Assigned to approver"
        )
        
        self.session.flush()
        return approval
    
    def escalate_approval(
        self,
        approval_id: UUID,
        escalation_reason: str,
        escalated_by_id: Optional[UUID] = None
    ) -> AnnouncementApproval:
        """
        Escalate approval request.
        
        Args:
            approval_id: Approval UUID
            escalation_reason: Reason for escalation
            escalated_by_id: User escalating
            
        Returns:
            Escalated approval
        """
        approval = self.find_by_id(approval_id)
        if not approval:
            raise ResourceNotFoundError(f"Approval {approval_id} not found")
        
        if approval.approval_status != 'pending':
            raise BusinessLogicError(
                f"Cannot escalate approval in {approval.approval_status} status"
            )
        
        now = datetime.utcnow()
        
        approval.is_escalated = True
        approval.escalated_at = now
        approval.escalation_reason = escalation_reason
        
        # Find escalation approver
        escalation_approver = self._find_escalation_approver(approval)
        if escalation_approver:
            approval.assigned_to_id = escalation_approver
            approval.assigned_at = now
        
        # Record in history
        self._record_history(
            approval=approval,
            action='escalated',
            performed_by_id=escalated_by_id,
            previous_status='pending',
            new_status='pending',
            notes=f"Escalated: {escalation_reason}"
        )
        
        self.session.flush()
        return approval
    
    # ==================== Auto-Approval ====================
    
    def auto_approve(
        self,
        approval_id: UUID
    ) -> AnnouncementApproval:
        """
        Automatically approve based on rules.
        
        Args:
            approval_id: Approval UUID
            
        Returns:
            Auto-approved request
        """
        approval = self.find_by_id(approval_id)
        if not approval:
            raise ResourceNotFoundError(f"Approval {approval_id} not found")
        
        now = datetime.utcnow()
        
        approval.approved = True
        approval.decided_at = now
        approval.approval_status = 'approved'
        approval.approval_notes = "Auto-approved based on approval rules"
        
        # Record in history
        self._record_history(
            approval=approval,
            action='auto_approved',
            performed_by_id=None,
            previous_status='pending',
            new_status='approved',
            notes="Automatically approved"
        )
        
        # Auto-publish if configured
        if approval.auto_publish_on_approval:
            self._publish_announcement(approval, None)
        
        self.session.flush()
        return approval
    
    def create_approval_rule(
        self,
        hostel_id: UUID,
        created_by_id: UUID,
        rule_name: str,
        conditions: List[Dict[str, Any]],
        priority: int = 0,
        description: Optional[str] = None
    ) -> ApprovalRule:
        """
        Create automatic approval rule.
        
        Args:
            hostel_id: Hostel UUID
            created_by_id: Creator user UUID
            rule_name: Rule name
            conditions: List of conditions
            priority: Rule priority
            description: Rule description
            
        Returns:
            Created approval rule
        """
        rule = ApprovalRule(
            hostel_id=hostel_id,
            created_by_id=created_by_id,
            rule_name=rule_name,
            description=description,
            conditions=conditions,
            priority=priority,
            is_active=True,
        )
        
        self.session.add(rule)
        self.session.flush()
        return rule
    
    # ==================== SLA Monitoring ====================
    
    def check_sla_breaches(
        self,
        hostel_id: Optional[UUID] = None
    ) -> List[AnnouncementApproval]:
        """
        Find approval requests that have breached SLA.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of SLA-breached approvals
        """
        now = datetime.utcnow()
        
        query = (
            select(AnnouncementApproval)
            .join(Announcement)
            .where(
                AnnouncementApproval.approval_status == 'pending',
                AnnouncementApproval.sla_deadline < now,
                AnnouncementApproval.sla_breached == False
            )
        )
        
        if hostel_id:
            query = query.where(Announcement.hostel_id == hostel_id)
        
        result = self.session.execute(query)
        breached_approvals = list(result.scalars().all())
        
        # Mark as breached and escalate
        for approval in breached_approvals:
            approval.sla_breached = True
            
            # Auto-escalate if enabled
            workflow = self._get_workflow(approval.announcement.hostel_id)
            if workflow and workflow.escalation_enabled:
                self.escalate_approval(
                    approval.id,
                    "SLA deadline exceeded",
                    None
                )
        
        self.session.flush()
        return breached_approvals
    
    # ==================== Query Operations ====================
    
    def find_by_announcement(
        self,
        announcement_id: UUID
    ) -> Optional[AnnouncementApproval]:
        """Find approval request for announcement."""
        return (
            self.session.query(AnnouncementApproval)
            .filter(AnnouncementApproval.announcement_id == announcement_id)
            .first()
        )
    
    def find_pending_approvals(
        self,
        hostel_id: Optional[UUID] = None,
        assigned_to_id: Optional[UUID] = None,
        urgent_only: bool = False,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[AnnouncementApproval]:
        """
        Find pending approval requests.
        
        Args:
            hostel_id: Optional hostel filter
            assigned_to_id: Optional assignee filter
            urgent_only: Only urgent requests
            pagination: Pagination parameters
            
        Returns:
            Paginated pending approvals
        """
        query = (
            QueryBuilder(AnnouncementApproval, self.session)
            .join(Announcement, AnnouncementApproval.announcement_id == Announcement.id)
            .where(AnnouncementApproval.approval_status == 'pending')
        )
        
        if hostel_id:
            query = query.where(Announcement.hostel_id == hostel_id)
        
        if assigned_to_id:
            query = query.where(
                AnnouncementApproval.assigned_to_id == assigned_to_id
            )
        
        if urgent_only:
            query = query.where(AnnouncementApproval.is_urgent_request == True)
        
        query = query.order_by(
            AnnouncementApproval.is_urgent_request.desc(),
            AnnouncementApproval.sla_deadline.asc(),
            AnnouncementApproval.submitted_at.asc()
        )
        
        return query.paginate(pagination or PaginationParams())
    
    def get_approval_history(
        self,
        approval_id: UUID,
        limit: int = 50
    ) -> List[ApprovalHistory]:
        """
        Get approval history.
        
        Args:
            approval_id: Approval UUID
            limit: Maximum records
            
        Returns:
            List of history entries
        """
        query = (
            select(ApprovalHistory)
            .where(ApprovalHistory.approval_id == approval_id)
            .order_by(ApprovalHistory.performed_at.desc())
            .limit(limit)
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())
    
    def get_approval_statistics(
        self,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get approval statistics.
        
        Args:
            hostel_id: Hostel UUID
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            Statistics dictionary
        """
        query = (
            select(AnnouncementApproval)
            .join(Announcement)
            .where(Announcement.hostel_id == hostel_id)
        )
        
        if start_date:
            query = query.where(AnnouncementApproval.submitted_at >= start_date)
        if end_date:
            query = query.where(AnnouncementApproval.submitted_at <= end_date)
        
        approvals = self.session.execute(query).scalars().all()
        
        total_requests = len(approvals)
        approved_count = sum(1 for a in approvals if a.approval_status == 'approved')
        rejected_count = sum(1 for a in approvals if a.approval_status == 'rejected')
        pending_count = sum(1 for a in approvals if a.approval_status == 'pending')
        
        # Calculate average time to decision
        decided_approvals = [
            a for a in approvals
            if a.decided_at and a.submitted_at
        ]
        
        if decided_approvals:
            total_hours = sum(a.time_pending_hours or 0 for a in decided_approvals)
            avg_time_hours = total_hours / len(decided_approvals)
        else:
            avg_time_hours = 0
        
        # SLA compliance
        sla_breaches = sum(1 for a in approvals if a.sla_breached)
        sla_compliance_rate = (
            ((total_requests - sla_breaches) / total_requests * 100)
            if total_requests > 0 else 100
        )
        
        return {
            'total_requests': total_requests,
            'approved': approved_count,
            'rejected': rejected_count,
            'pending': pending_count,
            'approval_rate': (
                (approved_count / total_requests * 100)
                if total_requests > 0 else 0
            ),
            'rejection_rate': (
                (rejected_count / total_requests * 100)
                if total_requests > 0 else 0
            ),
            'average_decision_time_hours': round(avg_time_hours, 2),
            'sla_breaches': sla_breaches,
            'sla_compliance_rate': round(sla_compliance_rate, 2),
        }
    
    # ==================== Workflow Management ====================
    
    def create_approval_workflow(
        self,
        hostel_id: UUID,
        created_by_id: UUID,
        workflow_name: str,
        steps: List[Dict[str, Any]],
        sla_hours: Optional[int] = None,
        escalation_enabled: bool = True,
        escalation_after_hours: Optional[int] = None,
        **kwargs
    ) -> ApprovalWorkflow:
        """
        Create approval workflow.
        
        Args:
            hostel_id: Hostel UUID
            created_by_id: Creator user UUID
            workflow_name: Workflow name
            steps: Workflow steps
            sla_hours: SLA in hours
            escalation_enabled: Enable escalation
            escalation_after_hours: Escalation threshold
            **kwargs: Additional parameters
            
        Returns:
            Created workflow
        """
        workflow = ApprovalWorkflow(
            hostel_id=hostel_id,
            created_by_id=created_by_id,
            workflow_name=workflow_name,
            steps=steps,
            sla_hours=sla_hours,
            escalation_enabled=escalation_enabled,
            escalation_after_hours=escalation_after_hours,
            is_active=True,
            **kwargs
        )
        
        self.session.add(workflow)
        self.session.flush()
        return workflow
    
    # ==================== Helper Methods ====================
    
    def _record_history(
        self,
        approval: AnnouncementApproval,
        action: str,
        performed_by_id: Optional[UUID],
        previous_status: Optional[str],
        new_status: str,
        notes: Optional[str] = None
    ) -> ApprovalHistory:
        """Record approval history entry."""
        # Get performer details
        performer_name = None
        performer_role = None
        
        if performed_by_id:
            performer = self.session.get(User, performed_by_id)
            if performer:
                performer_name = performer.full_name
                performer_role = performer.role
        
        history = ApprovalHistory(
            approval_id=approval.id,
            announcement_id=approval.announcement_id,
            performed_by_id=performed_by_id,
            action=action,
            previous_status=previous_status,
            new_status=new_status,
            performed_by_name=performer_name,
            performed_by_role=performer_role,
            notes=notes,
            performed_at=datetime.utcnow(),
        )
        
        self.session.add(history)
        return history
    
    def _check_auto_approval(self, approval: AnnouncementApproval) -> bool:
        """Check if approval qualifies for auto-approval."""
        announcement = approval.announcement
        
        # Get active approval rules
        rules = (
            self.session.query(ApprovalRule)
            .filter(
                ApprovalRule.hostel_id == announcement.hostel_id,
                ApprovalRule.is_active == True
            )
            .order_by(ApprovalRule.priority.asc())
            .all()
        )
        
        for rule in rules:
            if self._evaluate_approval_rule(rule, announcement, approval):
                # Update rule usage
                rule.times_applied += 1
                rule.last_applied_at = datetime.utcnow()
                return True
        
        return False
    
    def _evaluate_approval_rule(
        self,
        rule: ApprovalRule,
        announcement: Announcement,
        approval: AnnouncementApproval
    ) -> bool:
        """Evaluate if approval rule conditions are met."""
        for condition in rule.conditions:
            field = condition.get('field')
            operator = condition.get('operator')
            value = condition.get('value')
            
            # Get field value from announcement or approval
            if hasattr(announcement, field):
                actual_value = getattr(announcement, field)
            elif hasattr(approval, field):
                actual_value = getattr(approval, field)
            else:
                return False
            
            # Evaluate condition
            if operator == 'equals':
                if actual_value != value:
                    return False
            elif operator == 'in':
                if actual_value not in value:
                    return False
            elif operator == 'less_than':
                if not (actual_value < value):
                    return False
            elif operator == 'greater_than':
                if not (actual_value > value):
                    return False
            else:
                return False
        
        return True
    
    def _assign_approver(self, approval: AnnouncementApproval) -> None:
        """Automatically assign approver based on workflow."""
        # Check if preferred approver specified
        if approval.preferred_approver_id:
            approval.assigned_to_id = approval.preferred_approver_id
            approval.assigned_at = datetime.utcnow()
            return
        
        # Get workflow
        workflow = self._get_workflow(approval.announcement.hostel_id)
        if not workflow or not workflow.default_approvers:
            return
        
        # Find approver with least workload
        approver_workloads = (
            self.session.query(
                AnnouncementApproval.assigned_to_id,
                func.count(AnnouncementApproval.id).label('workload')
            )
            .filter(
                AnnouncementApproval.assigned_to_id.in_(workflow.default_approvers),
                AnnouncementApproval.approval_status == 'pending'
            )
            .group_by(AnnouncementApproval.assigned_to_id)
            .all()
        )
        
        workload_dict = {str(aid): count for aid, count in approver_workloads}
        
        # Find approver with minimum workload
        min_workload_approver = None
        min_workload = float('inf')
        
        for approver_id in workflow.default_approvers:
            workload = workload_dict.get(str(approver_id), 0)
            if workload < min_workload:
                min_workload = workload
                min_workload_approver = approver_id
        
        if min_workload_approver:
            approval.assigned_to_id = min_workload_approver
            approval.assigned_at = datetime.utcnow()
    
    def _verify_approval_authority(
        self,
        approver_id: UUID,
        approval: AnnouncementApproval
    ) -> None:
        """Verify user has authority to approve."""
        approver = self.session.get(User, approver_id)
        if not approver:
            raise ResourceNotFoundError(f"Approver {approver_id} not found")
        
        # Check if user has admin or supervisor role
        if approver.role not in ['admin', 'supervisor']:
            raise BusinessLogicError(
                f"User does not have approval authority"
            )
        
        # Additional checks can be added based on business rules
    
    def _calculate_sla_deadline(
        self,
        hostel_id: UUID,
        is_urgent: bool
    ) -> datetime:
        """Calculate SLA deadline for approval."""
        workflow = self._get_workflow(hostel_id)
        
        if workflow and workflow.sla_hours:
            hours = workflow.sla_hours
        else:
            # Default SLA: 24 hours for normal, 4 hours for urgent
            hours = 4 if is_urgent else 24
        
        return datetime.utcnow() + timedelta(hours=hours)
    
    def _find_escalation_approver(
        self,
        approval: AnnouncementApproval
    ) -> Optional[UUID]:
        """Find escalation approver."""
        workflow = self._get_workflow(approval.announcement.hostel_id)
        
        if workflow and workflow.escalation_approvers:
            # Return first escalation approver
            return workflow.escalation_approvers[0]
        
        return None
    
    def _get_workflow(self, hostel_id: UUID) -> Optional[ApprovalWorkflow]:
        """Get active approval workflow for hostel."""
        return (
            self.session.query(ApprovalWorkflow)
            .filter(
                ApprovalWorkflow.hostel_id == hostel_id,
                ApprovalWorkflow.is_active == True
            )
            .first()
        )
    
    def _publish_announcement(
        self,
        approval: AnnouncementApproval,
        published_by_id: Optional[UUID]
    ) -> None:
        """Publish announcement after approval."""
        announcement = approval.announcement
        
        now = datetime.utcnow()
        announcement.is_published = True
        announcement.published_at = now
        announcement.published_by_id = published_by_id or approval.decided_by_id
        announcement.status = 'published'
        
        # Update approval
        approval.auto_published = True
        approval.published_at = now