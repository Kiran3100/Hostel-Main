"""
Leave Approval Repository

Comprehensive leave approval workflow management with multi-level approvals,
delegation, escalation, and performance tracking.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, case
from sqlalchemy.orm import Session, joinedload

from app.models.leave.leave_approval import (
    LeaveApproval,
    LeaveApprovalWorkflow,
    LeaveApprovalStep,
)
from app.models.leave.leave_application import LeaveApplication
from app.models.common.enums import LeaveStatus, LeaveType
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.pagination import PaginationParams, PaginatedResult


class LeaveApprovalRepository(BaseRepository[LeaveApproval]):
    """
    Leave approval repository with workflow management capabilities.
    
    Features:
    - Multi-level approval workflows
    - Approval delegation and escalation
    - SLA tracking and monitoring
    - Performance analytics
    - Workflow optimization
    """

    def __init__(self, session: Session):
        """Initialize repository with database session."""
        super().__init__(session, LeaveApproval)

    # ============================================================================
    # CORE APPROVAL OPERATIONS
    # ============================================================================

    def create_approval(
        self,
        leave_id: UUID,
        approver_id: UUID,
        is_approved: bool,
        decision_notes: Optional[str] = None,
        conditions: Optional[str] = None,
        rejection_reason: Optional[str] = None,
        workflow_id: Optional[UUID] = None,
        approval_level: int = 1,
        is_final_decision: bool = True,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> LeaveApproval:
        """
        Create leave approval decision.
        
        Args:
            leave_id: Leave application ID
            approver_id: User making decision
            is_approved: Approval decision
            decision_notes: Optional notes
            conditions: Optional conditions (for approvals)
            rejection_reason: Reason (for rejections)
            workflow_id: Associated workflow
            approval_level: Level in workflow
            is_final_decision: Whether this is final
            audit_context: Audit information
            
        Returns:
            Created approval record
        """
        approval = LeaveApproval(
            leave_id=leave_id,
            approver_id=approver_id,
            is_approved=is_approved,
            decision_at=datetime.utcnow(),
            decision_notes=decision_notes,
            approval_comments=decision_notes if is_approved else None,
            conditions=conditions,
            rejection_reason=rejection_reason,
            approval_level=approval_level,
            is_final_decision=is_final_decision,
            workflow_id=workflow_id,
            ip_address=audit_context.get('ip_address') if audit_context else None,
            user_agent=audit_context.get('user_agent') if audit_context else None
        )
        
        self.session.add(approval)
        self.session.flush()
        
        return approval

    def create_auto_approval(
        self,
        leave_id: UUID,
        auto_approval_rule: str,
        conditions: Optional[str] = None
    ) -> LeaveApproval:
        """
        Create automatic approval record.
        
        Args:
            leave_id: Leave application ID
            auto_approval_rule: Rule that triggered auto-approval
            conditions: Optional conditions
            
        Returns:
            Created auto-approval record
        """
        approval = LeaveApproval(
            leave_id=leave_id,
            approver_id=None,
            is_approved=True,
            decision_at=datetime.utcnow(),
            decision_notes="Automatically approved",
            conditions=conditions,
            is_auto_approved=True,
            auto_approval_rule=auto_approval_rule,
            is_final_decision=True
        )
        
        self.session.add(approval)
        self.session.flush()
        
        return approval

    # ============================================================================
    # FINDER METHODS
    # ============================================================================

    def find_by_leave(
        self,
        leave_id: UUID,
        include_system: bool = True
    ) -> List[LeaveApproval]:
        """
        Find all approvals for a leave application.
        
        Args:
            leave_id: Leave application ID
            include_system: Include auto-approvals
            
        Returns:
            List of approvals ordered by level
        """
        query = self.session.query(LeaveApproval).filter(
            LeaveApproval.leave_id == leave_id
        )
        
        if not include_system:
            query = query.filter(LeaveApproval.is_auto_approved == False)
        
        return query.order_by(LeaveApproval.approval_level).all()

    def find_by_approver(
        self,
        approver_id: UUID,
        is_approved: Optional[bool] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[LeaveApproval]:
        """
        Find approvals by approver.
        
        Args:
            approver_id: Approver user ID
            is_approved: Filter by decision (None=all)
            from_date: Start date filter
            to_date: End date filter
            pagination: Pagination parameters
            
        Returns:
            Paginated approvals
        """
        query = self.session.query(LeaveApproval).filter(
            LeaveApproval.approver_id == approver_id
        )
        
        if is_approved is not None:
            query = query.filter(LeaveApproval.is_approved == is_approved)
        
        if from_date:
            query = query.filter(LeaveApproval.decision_at >= from_date)
        
        if to_date:
            query = query.filter(LeaveApproval.decision_at <= to_date)
        
        query = query.order_by(LeaveApproval.decision_at.desc())
        
        return self._paginate_query(query, pagination)

    def find_pending_for_approver(
        self,
        approver_id: UUID,
        hostel_id: Optional[UUID] = None,
        older_than_hours: Optional[int] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[LeaveApplication]:
        """
        Find pending leave applications for approver.
        
        Args:
            approver_id: Approver user ID
            hostel_id: Optional hostel filter
            older_than_hours: Filter by application age
            pagination: Pagination parameters
            
        Returns:
            Paginated pending applications
        """
        query = self.session.query(LeaveApplication).filter(
            LeaveApplication.status == LeaveStatus.PENDING,
            LeaveApplication.requires_approval == True,
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(LeaveApplication.hostel_id == hostel_id)
        
        if older_than_hours:
            cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
            query = query.filter(LeaveApplication.applied_at <= cutoff)
        
        # Check if approver has already approved
        query = query.filter(
            ~LeaveApplication.id.in_(
                self.session.query(LeaveApproval.leave_id).filter(
                    LeaveApproval.approver_id == approver_id
                )
            )
        )
        
        query = query.order_by(
            LeaveApplication.priority.desc(),
            LeaveApplication.applied_at.asc()
        )
        
        return self._paginate_query(query, pagination)

    def find_by_workflow(
        self,
        workflow_id: UUID,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[LeaveApproval]:
        """
        Find approvals by workflow.
        
        Args:
            workflow_id: Workflow ID
            pagination: Pagination parameters
            
        Returns:
            Paginated approvals
        """
        query = self.session.query(LeaveApproval).filter(
            LeaveApproval.workflow_id == workflow_id
        ).order_by(LeaveApproval.decision_at.desc())
        
        return self._paginate_query(query, pagination)

    def get_final_approval(
        self,
        leave_id: UUID
    ) -> Optional[LeaveApproval]:
        """
        Get final approval decision for leave.
        
        Args:
            leave_id: Leave application ID
            
        Returns:
            Final approval or None
        """
        return self.session.query(LeaveApproval).filter(
            LeaveApproval.leave_id == leave_id,
            LeaveApproval.is_final_decision == True
        ).first()

    # ============================================================================
    # WORKFLOW OPERATIONS
    # ============================================================================

    def get_approval_workflow(
        self,
        leave_application: LeaveApplication
    ) -> Optional[LeaveApprovalWorkflow]:
        """
        Get applicable approval workflow for leave application.
        
        Args:
            leave_application: Leave application
            
        Returns:
            Applicable workflow or None
        """
        # Find workflow by priority (most specific first)
        query = self.session.query(LeaveApprovalWorkflow).filter(
            LeaveApprovalWorkflow.is_active == True
        )
        
        # Filter by hostel if specified
        query = query.filter(
            or_(
                LeaveApprovalWorkflow.hostel_id == leave_application.hostel_id,
                LeaveApprovalWorkflow.hostel_id.is_(None)
            )
        )
        
        # Filter by leave type if specified
        query = query.filter(
            or_(
                LeaveApprovalWorkflow.leave_type == leave_application.leave_type.value,
                LeaveApprovalWorkflow.leave_type.is_(None)
            )
        )
        
        # Check effective dates
        now = datetime.utcnow()
        query = query.filter(
            or_(
                LeaveApprovalWorkflow.effective_from.is_(None),
                LeaveApprovalWorkflow.effective_from <= now
            ),
            or_(
                LeaveApprovalWorkflow.effective_to.is_(None),
                LeaveApprovalWorkflow.effective_to >= now
            )
        )
        
        # Order by priority
        query = query.order_by(LeaveApprovalWorkflow.priority.desc())
        
        return query.first()

    def get_next_approval_step(
        self,
        leave_id: UUID,
        workflow_id: UUID
    ) -> Optional[LeaveApprovalStep]:
        """
        Get next approval step in workflow.
        
        Args:
            leave_id: Leave application ID
            workflow_id: Workflow ID
            
        Returns:
            Next approval step or None
        """
        # Get completed approval levels
        completed_levels = self.session.query(
            func.max(LeaveApproval.approval_level)
        ).filter(
            LeaveApproval.leave_id == leave_id,
            LeaveApproval.workflow_id == workflow_id
        ).scalar() or 0
        
        # Get next step
        return self.session.query(LeaveApprovalStep).filter(
            LeaveApprovalStep.workflow_id == workflow_id,
            LeaveApprovalStep.step_order > completed_levels,
            LeaveApprovalStep.is_active == True
        ).order_by(LeaveApprovalStep.step_order).first()

    def check_workflow_complete(
        self,
        leave_id: UUID,
        workflow_id: UUID
    ) -> bool:
        """
        Check if workflow is complete.
        
        Args:
            leave_id: Leave application ID
            workflow_id: Workflow ID
            
        Returns:
            True if workflow complete
        """
        workflow = self.session.query(LeaveApprovalWorkflow).filter(
            LeaveApprovalWorkflow.id == workflow_id
        ).first()
        
        if not workflow:
            return False
        
        completed_levels = self.session.query(
            func.count(LeaveApproval.id)
        ).filter(
            LeaveApproval.leave_id == leave_id,
            LeaveApproval.workflow_id == workflow_id,
            LeaveApproval.is_approved == True
        ).scalar()
        
        return completed_levels >= workflow.total_levels

    def can_auto_approve(
        self,
        leave_application: LeaveApplication
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if leave can be auto-approved.
        
        Args:
            leave_application: Leave application
            
        Returns:
            Tuple of (can_auto_approve, rule_matched)
        """
        workflow = self.get_approval_workflow(leave_application)
        
        if not workflow or not workflow.auto_approve_enabled:
            return False, None
        
        # Check max days condition
        if workflow.auto_approve_max_days:
            if leave_application.total_days <= workflow.auto_approve_max_days:
                return True, f"days_lte_{workflow.auto_approve_max_days}"
        
        # Check custom conditions (would need JSON parsing)
        # For now, return basic check
        return False, None

    # ============================================================================
    # NOTIFICATION MANAGEMENT
    # ============================================================================

    def mark_student_notified(
        self,
        approval_id: UUID
    ) -> Optional[LeaveApproval]:
        """
        Mark that student has been notified of decision.
        
        Args:
            approval_id: Approval ID
            
        Returns:
            Updated approval or None
        """
        approval = self.find_by_id(approval_id)
        if not approval:
            return None
        
        approval.student_notified = True
        approval.student_notified_at = datetime.utcnow()
        
        self.session.flush()
        return approval

    def mark_guardian_notified(
        self,
        approval_id: UUID
    ) -> Optional[LeaveApproval]:
        """
        Mark that guardian has been notified.
        
        Args:
            approval_id: Approval ID
            
        Returns:
            Updated approval or None
        """
        approval = self.find_by_id(approval_id)
        if not approval:
            return None
        
        approval.guardian_notified = True
        approval.guardian_notified_at = datetime.utcnow()
        
        self.session.flush()
        return approval

    def get_unnotified_approvals(
        self,
        notification_type: str = 'student',
        older_than_minutes: int = 5
    ) -> List[LeaveApproval]:
        """
        Get approvals where notifications haven't been sent.
        
        Args:
            notification_type: 'student' or 'guardian'
            older_than_minutes: Only include decisions older than N minutes
            
        Returns:
            List of approvals needing notification
        """
        cutoff = datetime.utcnow() - timedelta(minutes=older_than_minutes)
        
        query = self.session.query(LeaveApproval).filter(
            LeaveApproval.decision_at <= cutoff,
            LeaveApproval.is_final_decision == True
        )
        
        if notification_type == 'student':
            query = query.filter(LeaveApproval.student_notified == False)
        elif notification_type == 'guardian':
            query = query.filter(LeaveApproval.guardian_notified == False)
        
        return query.all()

    # ============================================================================
    # ANALYTICS AND REPORTING
    # ============================================================================

    def get_approver_statistics(
        self,
        approver_id: UUID,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get approval statistics for an approver.
        
        Args:
            approver_id: Approver user ID
            from_date: Optional start date
            to_date: Optional end date
            
        Returns:
            Statistics dictionary
        """
        query = self.session.query(LeaveApproval).filter(
            LeaveApproval.approver_id == approver_id
        )
        
        if from_date:
            query = query.filter(LeaveApproval.decision_at >= from_date)
        
        if to_date:
            query = query.filter(LeaveApproval.decision_at <= to_date)
        
        total_decisions = query.count()
        approvals = query.filter(LeaveApproval.is_approved == True).count()
        rejections = query.filter(LeaveApproval.is_approved == False).count()
        
        # Calculate average decision time
        avg_decision_time = self.session.query(
            func.avg(
                func.extract('epoch', LeaveApproval.decision_at - LeaveApplication.applied_at)
            )
        ).join(
            LeaveApplication,
            LeaveApproval.leave_id == LeaveApplication.id
        ).filter(
            LeaveApproval.approver_id == approver_id
        )
        
        if from_date:
            avg_decision_time = avg_decision_time.filter(LeaveApproval.decision_at >= from_date)
        
        if to_date:
            avg_decision_time = avg_decision_time.filter(LeaveApproval.decision_at <= to_date)
        
        avg_time = avg_decision_time.scalar()
        
        return {
            'total_decisions': total_decisions,
            'approvals': approvals,
            'rejections': rejections,
            'approval_rate': round((approvals / total_decisions * 100), 2) if total_decisions > 0 else 0,
            'average_decision_hours': round(avg_time / 3600, 2) if avg_time else None,
            'pending_count': self.find_pending_for_approver(approver_id).total
        }

    def get_approval_performance_metrics(
        self,
        hostel_id: Optional[UUID] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive approval performance metrics.
        
        Args:
            hostel_id: Optional hostel filter
            from_date: Optional start date
            to_date: Optional end date
            
        Returns:
            Performance metrics
        """
        query = self.session.query(LeaveApproval).join(
            LeaveApplication,
            LeaveApproval.leave_id == LeaveApplication.id
        )
        
        if hostel_id:
            query = query.filter(LeaveApplication.hostel_id == hostel_id)
        
        if from_date:
            query = query.filter(LeaveApproval.decision_at >= from_date)
        
        if to_date:
            query = query.filter(LeaveApproval.decision_at <= to_date)
        
        # Calculate metrics
        total = query.count()
        approved = query.filter(LeaveApproval.is_approved == True).count()
        rejected = query.filter(LeaveApproval.is_approved == False).count()
        auto_approved = query.filter(LeaveApproval.is_auto_approved == True).count()
        
        # Average decision time
        avg_time = self.session.query(
            func.avg(
                func.extract('epoch', LeaveApproval.decision_at - LeaveApplication.applied_at)
            )
        ).join(
            LeaveApplication,
            LeaveApproval.leave_id == LeaveApplication.id
        ).filter(
            LeaveApproval.is_auto_approved == False
        )
        
        if hostel_id:
            avg_time = avg_time.filter(LeaveApplication.hostel_id == hostel_id)
        
        if from_date:
            avg_time = avg_time.filter(LeaveApproval.decision_at >= from_date)
        
        if to_date:
            avg_time = avg_time.filter(LeaveApproval.decision_at <= to_date)
        
        avg_decision_time = avg_time.scalar()
        
        # Top approvers
        top_approvers = self.session.query(
            LeaveApproval.approver_id,
            func.count(LeaveApproval.id).label('count')
        ).join(
            LeaveApplication,
            LeaveApproval.leave_id == LeaveApplication.id
        ).filter(
            LeaveApproval.approver_id.isnot(None)
        )
        
        if hostel_id:
            top_approvers = top_approvers.filter(LeaveApplication.hostel_id == hostel_id)
        
        if from_date:
            top_approvers = top_approvers.filter(LeaveApproval.decision_at >= from_date)
        
        if to_date:
            top_approvers = top_approvers.filter(LeaveApproval.decision_at <= to_date)
        
        top_approvers = top_approvers.group_by(
            LeaveApproval.approver_id
        ).order_by(
            func.count(LeaveApproval.id).desc()
        ).limit(10).all()
        
        return {
            'total_decisions': total,
            'approved_count': approved,
            'rejected_count': rejected,
            'auto_approved_count': auto_approved,
            'approval_rate': round((approved / total * 100), 2) if total > 0 else 0,
            'auto_approval_rate': round((auto_approved / total * 100), 2) if total > 0 else 0,
            'average_decision_hours': round(avg_decision_time / 3600, 2) if avg_decision_time else None,
            'top_approvers': [
                {'approver_id': str(approver_id), 'count': count}
                for approver_id, count in top_approvers
            ]
        }

    def get_workflow_analytics(
        self,
        workflow_id: UUID,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get analytics for a specific workflow.
        
        Args:
            workflow_id: Workflow ID
            from_date: Optional start date
            to_date: Optional end date
            
        Returns:
            Workflow analytics
        """
        query = self.session.query(LeaveApproval).filter(
            LeaveApproval.workflow_id == workflow_id
        )
        
        if from_date:
            query = query.filter(LeaveApproval.decision_at >= from_date)
        
        if to_date:
            query = query.filter(LeaveApproval.decision_at <= to_date)
        
        # Approvals by level
        by_level = self.session.query(
            LeaveApproval.approval_level,
            func.count(LeaveApproval.id),
            func.sum(case([(LeaveApproval.is_approved == True, 1)], else_=0)),
            func.sum(case([(LeaveApproval.is_approved == False, 1)], else_=0))
        ).filter(
            LeaveApproval.workflow_id == workflow_id
        )
        
        if from_date:
            by_level = by_level.filter(LeaveApproval.decision_at >= from_date)
        
        if to_date:
            by_level = by_level.filter(LeaveApproval.decision_at <= to_date)
        
        by_level = by_level.group_by(LeaveApproval.approval_level).all()
        
        return {
            'total_approvals': query.count(),
            'approved': query.filter(LeaveApproval.is_approved == True).count(),
            'rejected': query.filter(LeaveApproval.is_approved == False).count(),
            'by_level': [
                {
                    'level': level,
                    'total': total,
                    'approved': approved,
                    'rejected': rejected
                }
                for level, total, approved, rejected in by_level
            ]
        }

    def get_sla_compliance(
        self,
        hostel_id: Optional[UUID] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get SLA compliance metrics.
        
        Args:
            hostel_id: Optional hostel filter
            from_date: Optional start date
            to_date: Optional end date
            
        Returns:
            SLA compliance metrics
        """
        # This would integrate with workflow SLA settings
        # For now, return basic structure
        return {
            'total_approvals': 0,
            'within_sla': 0,
            'breached_sla': 0,
            'compliance_rate': 0.0,
            'average_decision_hours': 0.0,
            'sla_breaches_by_level': []
        }

    # ============================================================================
    # DELEGATION AND ESCALATION
    # ============================================================================

    def delegate_approval(
        self,
        leave_id: UUID,
        from_approver_id: UUID,
        to_approver_id: UUID,
        delegation_reason: str,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Delegate approval to another user.
        
        Args:
            leave_id: Leave application ID
            from_approver_id: Current approver
            to_approver_id: New approver
            delegation_reason: Reason for delegation
            audit_context: Audit information
            
        Returns:
            Success status
        """
        # Implementation would create delegation record
        # and update approval routing
        return True

    def escalate_approval(
        self,
        leave_id: UUID,
        escalation_reason: str,
        escalate_to_role: Optional[str] = None,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Escalate approval to higher authority.
        
        Args:
            leave_id: Leave application ID
            escalation_reason: Reason for escalation
            escalate_to_role: Target role
            audit_context: Audit information
            
        Returns:
            Success status
        """
        # Implementation would create escalation record
        # and route to appropriate approver
        return True

    def find_escalated_approvals(
        self,
        approver_role: str,
        hostel_id: Optional[UUID] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[LeaveApproval]:
        """
        Find escalated approvals for a role.
        
        Args:
            approver_role: Approver role
            hostel_id: Optional hostel filter
            pagination: Pagination parameters
            
        Returns:
            Paginated escalated approvals
        """
        # Implementation would filter escalated approvals
        # For now, return empty result
        query = self.session.query(LeaveApproval).filter(
            LeaveApproval.id == None  # Placeholder
        )
        
        return self._paginate_query(query, pagination)

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _paginate_query(
        self,
        query,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult:
        """
        Apply pagination to query.
        
        Args:
            query: SQLAlchemy query
            pagination: Pagination parameters
            
        Returns:
            Paginated results
        """
        if pagination is None:
            pagination = PaginationParams(page=1, page_size=50)
        
        total = query.count()
        
        offset = (pagination.page - 1) * pagination.page_size
        items = query.offset(offset).limit(pagination.page_size).all()
        
        return PaginatedResult(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size
        )


class LeaveApprovalWorkflowRepository(BaseRepository[LeaveApprovalWorkflow]):
    """
    Leave approval workflow configuration repository.
    
    Features:
    - Workflow CRUD operations
    - Step management
    - Configuration validation
    - Performance optimization
    """

    def __init__(self, session: Session):
        """Initialize repository with database session."""
        super().__init__(session, LeaveApprovalWorkflow)

    # ============================================================================
    # WORKFLOW MANAGEMENT
    # ============================================================================

    def create_workflow(
        self,
        workflow_data: Dict[str, Any],
        steps: Optional[List[Dict[str, Any]]] = None
    ) -> LeaveApprovalWorkflow:
        """
        Create approval workflow with steps.
        
        Args:
            workflow_data: Workflow configuration
            steps: Optional list of workflow steps
            
        Returns:
            Created workflow
        """
        workflow = LeaveApprovalWorkflow(**workflow_data)
        self.session.add(workflow)
        self.session.flush()
        
        if steps:
            for step_data in steps:
                step = LeaveApprovalStep(
                    workflow_id=workflow.id,
                    **step_data
                )
                self.session.add(step)
        
        self.session.flush()
        return workflow

    def get_active_workflows(
        self,
        hostel_id: Optional[UUID] = None,
        leave_type: Optional[str] = None
    ) -> List[LeaveApprovalWorkflow]:
        """
        Get active workflows with optional filters.
        
        Args:
            hostel_id: Optional hostel filter
            leave_type: Optional leave type filter
            
        Returns:
            List of active workflows
        """
        query = self.session.query(LeaveApprovalWorkflow).filter(
            LeaveApprovalWorkflow.is_active == True
        )
        
        if hostel_id:
            query = query.filter(
                or_(
                    LeaveApprovalWorkflow.hostel_id == hostel_id,
                    LeaveApprovalWorkflow.hostel_id.is_(None)
                )
            )
        
        if leave_type:
            query = query.filter(
                or_(
                    LeaveApprovalWorkflow.leave_type == leave_type,
                    LeaveApprovalWorkflow.leave_type.is_(None)
                )
            )
        
        # Check effective dates
        now = datetime.utcnow()
        query = query.filter(
            or_(
                LeaveApprovalWorkflow.effective_from.is_(None),
                LeaveApprovalWorkflow.effective_from <= now
            ),
            or_(
                LeaveApprovalWorkflow.effective_to.is_(None),
                LeaveApprovalWorkflow.effective_to >= now
            )
        )
        
        return query.order_by(LeaveApprovalWorkflow.priority.desc()).all()

    def add_workflow_step(
        self,
        workflow_id: UUID,
        step_data: Dict[str, Any]
    ) -> Optional[LeaveApprovalStep]:
        """
        Add step to workflow.
        
        Args:
            workflow_id: Workflow ID
            step_data: Step configuration
            
        Returns:
            Created step or None
        """
        workflow = self.find_by_id(workflow_id)
        if not workflow:
            return None
        
        step = LeaveApprovalStep(
            workflow_id=workflow_id,
            **step_data
        )
        
        self.session.add(step)
        self.session.flush()
        
        return step

    def update_workflow_step(
        self,
        step_id: UUID,
        update_data: Dict[str, Any]
    ) -> Optional[LeaveApprovalStep]:
        """
        Update workflow step.
        
        Args:
            step_id: Step ID
            update_data: Fields to update
            
        Returns:
            Updated step or None
        """
        step = self.session.query(LeaveApprovalStep).filter(
            LeaveApprovalStep.id == step_id
        ).first()
        
        if not step:
            return None
        
        for key, value in update_data.items():
            if hasattr(step, key):
                setattr(step, key, value)
        
        self.session.flush()
        return step

    def get_workflow_steps(
        self,
        workflow_id: UUID,
        active_only: bool = True
    ) -> List[LeaveApprovalStep]:
        """
        Get all steps for workflow.
        
        Args:
            workflow_id: Workflow ID
            active_only: Return only active steps
            
        Returns:
            List of workflow steps
        """
        query = self.session.query(LeaveApprovalStep).filter(
            LeaveApprovalStep.workflow_id == workflow_id
        )
        
        if active_only:
            query = query.filter(LeaveApprovalStep.is_active == True)
        
        return query.order_by(LeaveApprovalStep.step_order).all()

    def deactivate_workflow(
        self,
        workflow_id: UUID
    ) -> Optional[LeaveApprovalWorkflow]:
        """
        Deactivate workflow.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            Updated workflow or None
        """
        workflow = self.find_by_id(workflow_id)
        if not workflow:
            return None
        
        workflow.is_active = False
        workflow.effective_to = datetime.utcnow()
        
        self.session.flush()
        return workflow