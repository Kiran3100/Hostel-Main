# --- File: C:\Hostel-Main\app\repositories\mess\menu_approval_repository.py ---

"""
Menu Approval Repository Module.

Manages menu approval workflows, requests, history tracking,
approval rules, and bulk operations with compliance monitoring.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from app.models.mess.menu_approval import (
    ApprovalAttempt,
    ApprovalHistory,
    ApprovalRule,
    ApprovalWorkflow,
    BulkApproval,
    MenuApproval,
    MenuApprovalRequest,
)
from app.repositories.base.base_repository import BaseRepository


class MenuApprovalRepository(BaseRepository[MenuApproval]):
    """
    Repository for managing menu approvals.
    
    Handles approval workflow, decision tracking, escalation,
    and approval performance metrics.
    """

    def __init__(self, db_session):
        """Initialize repository with MenuApproval model."""
        super().__init__(MenuApproval, db_session)

    async def get_by_menu(
        self,
        menu_id: UUID,
        include_deleted: bool = False
    ) -> Optional[MenuApproval]:
        """
        Get approval record for a menu.
        
        Args:
            menu_id: Menu identifier
            include_deleted: Include soft-deleted records
            
        Returns:
            MenuApproval if found
        """
        query = select(MenuApproval).where(MenuApproval.menu_id == menu_id)
        
        if not include_deleted:
            query = query.where(MenuApproval.deleted_at.is_(None))
            
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_pending_approvals(
        self,
        approver_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        priority: Optional[str] = None
    ) -> List[MenuApproval]:
        """
        Get pending approval requests.
        
        Args:
            approver_id: Specific approver (optional)
            hostel_id: Hostel filter (optional)
            priority: Priority filter (optional)
            
        Returns:
            List of pending approvals
        """
        from app.models.mess.mess_menu import MessMenu
        
        conditions = [
            MenuApproval.approval_status == 'pending',
            MenuApproval.deleted_at.is_(None)
        ]
        
        if approver_id:
            conditions.append(MenuApproval.current_approver_id == approver_id)
            
        if priority:
            conditions.append(MenuApproval.priority == priority)
            
        query = select(MenuApproval).where(and_(*conditions))
        
        if hostel_id:
            query = query.join(MessMenu).where(MessMenu.hostel_id == hostel_id)
            
        query = query.order_by(
            MenuApproval.priority.desc(),
            MenuApproval.created_at
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_overdue_approvals(
        self,
        approver_id: Optional[UUID] = None
    ) -> List[MenuApproval]:
        """
        Get overdue approval requests.
        
        Args:
            approver_id: Specific approver (optional)
            
        Returns:
            List of overdue approvals
        """
        conditions = [
            MenuApproval.approval_status == 'pending',
            MenuApproval.is_overdue == True,
            MenuApproval.deleted_at.is_(None)
        ]
        
        if approver_id:
            conditions.append(MenuApproval.current_approver_id == approver_id)
            
        query = (
            select(MenuApproval)
            .where(and_(*conditions))
            .order_by(MenuApproval.approval_deadline)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def approve_menu(
        self,
        approval_id: UUID,
        approver_id: UUID,
        notes: Optional[str] = None,
        conditions: Optional[str] = None,
        approved_budget: Optional[Decimal] = None
    ) -> Optional[MenuApproval]:
        """
        Approve a menu.
        
        Args:
            approval_id: MenuApproval identifier
            approver_id: User approving
            notes: Approval notes (optional)
            conditions: Approval conditions (optional)
            approved_budget: Approved budget (optional)
            
        Returns:
            Updated MenuApproval
        """
        approval = await self.get_by_id(approval_id)
        if not approval:
            return None
            
        approval.approval_status = 'approved'
        approval.approved_by = approver_id
        approval.approved_at = datetime.utcnow()
        approval.approval_notes = notes
        approval.conditions = conditions
        
        if approved_budget is not None:
            approval.approved_budget = approved_budget
            
        approval.can_publish = True
        approval.is_overdue = False
        
        await self.db_session.commit()
        await self.db_session.refresh(approval)
        
        return approval

    async def reject_menu(
        self,
        approval_id: UUID,
        rejector_id: UUID,
        rejection_reason: str,
        suggested_changes: Optional[str] = None
    ) -> Optional[MenuApproval]:
        """
        Reject a menu.
        
        Args:
            approval_id: MenuApproval identifier
            rejector_id: User rejecting
            rejection_reason: Reason for rejection
            suggested_changes: Suggested changes (optional)
            
        Returns:
            Updated MenuApproval
        """
        approval = await self.get_by_id(approval_id)
        if not approval:
            return None
            
        approval.approval_status = 'rejected'
        approval.rejected_by = rejector_id
        approval.rejected_at = datetime.utcnow()
        approval.rejection_reason = rejection_reason
        approval.suggested_changes = suggested_changes
        approval.requires_resubmission = True
        approval.is_overdue = False
        
        await self.db_session.commit()
        await self.db_session.refresh(approval)
        
        return approval

    async def request_revision(
        self,
        approval_id: UUID,
        requester_id: UUID,
        revision_notes: str
    ) -> Optional[MenuApproval]:
        """
        Request revision for a menu.
        
        Args:
            approval_id: MenuApproval identifier
            requester_id: User requesting revision
            revision_notes: Notes for revision
            
        Returns:
            Updated MenuApproval
        """
        approval = await self.get_by_id(approval_id)
        if not approval:
            return None
            
        approval.approval_status = 'revision_requested'
        approval.requires_revision = True
        approval.revision_count += 1
        approval.last_revision_at = datetime.utcnow()
        approval.suggested_changes = revision_notes
        approval.current_approver_id = None
        
        await self.db_session.commit()
        await self.db_session.refresh(approval)
        
        return approval

    async def escalate_approval(
        self,
        approval_id: UUID,
        escalate_to: UUID,
        escalation_reason: str
    ) -> Optional[MenuApproval]:
        """
        Escalate approval to higher authority.
        
        Args:
            approval_id: MenuApproval identifier
            escalate_to: User to escalate to
            escalation_reason: Reason for escalation
            
        Returns:
            Updated MenuApproval
        """
        approval = await self.get_by_id(approval_id)
        if not approval:
            return None
            
        approval.is_escalated = True
        approval.escalated_to = escalate_to
        approval.escalated_at = datetime.utcnow()
        approval.escalation_reason = escalation_reason
        approval.current_approver_id = escalate_to
        approval.priority = 'urgent'
        
        await self.db_session.commit()
        await self.db_session.refresh(approval)
        
        return approval

    async def get_approval_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, any]:
        """
        Get approval statistics.
        
        Args:
            hostel_id: Hostel filter (optional)
            start_date: Start date (optional)
            end_date: End date (optional)
            
        Returns:
            Dictionary of approval statistics
        """
        from app.models.mess.mess_menu import MessMenu
        
        conditions = [MenuApproval.deleted_at.is_(None)]
        
        if start_date:
            conditions.append(MenuApproval.created_at >= start_date)
        if end_date:
            conditions.append(MenuApproval.created_at <= end_date)
            
        query = select(
            MenuApproval.approval_status,
            func.count(MenuApproval.id),
            func.avg(
                func.extract('epoch', MenuApproval.approved_at - MenuApproval.created_at) / 3600
            )
        ).where(and_(*conditions))
        
        if hostel_id:
            query = query.join(MessMenu).where(MessMenu.hostel_id == hostel_id)
            
        query = query.group_by(MenuApproval.approval_status)
        
        result = await self.db_session.execute(query)
        rows = result.all()
        
        stats = {
            'by_status': {},
            'total_approvals': 0,
            'average_time_hours': 0.0
        }
        
        total_time = 0.0
        total_count = 0
        
        for status, count, avg_time in rows:
            stats['by_status'][status] = {
                'count': count,
                'average_time_hours': float(avg_time) if avg_time else 0.0
            }
            stats['total_approvals'] += count
            if avg_time:
                total_time += avg_time * count
                total_count += count
                
        if total_count > 0:
            stats['average_time_hours'] = total_time / total_count
            
        return stats

    async def get_with_attempts(
        self,
        approval_id: UUID
    ) -> Optional[MenuApproval]:
        """
        Get approval with all attempts loaded.
        
        Args:
            approval_id: MenuApproval identifier
            
        Returns:
            MenuApproval with attempts
        """
        query = (
            select(MenuApproval)
            .where(MenuApproval.id == approval_id)
            .options(selectinload(MenuApproval.approval_attempts))
        )
        
        result = await self.db_session.execute(query)
        return result.unique().scalar_one_or_none()


class MenuApprovalRequestRepository(BaseRepository[MenuApprovalRequest]):
    """
    Repository for managing approval requests.
    
    Handles submission, tracking, and analytics of approval
    requests with cost estimation and justification.
    """

    def __init__(self, db_session):
        """Initialize repository with MenuApprovalRequest model."""
        super().__init__(MenuApprovalRequest, db_session)

    async def create_request(
        self,
        menu_id: UUID,
        requester_id: UUID,
        request_data: Dict
    ) -> MenuApprovalRequest:
        """
        Create new approval request.
        
        Args:
            menu_id: Menu identifier
            requester_id: User creating request
            request_data: Request details
            
        Returns:
            Created MenuApprovalRequest
        """
        request = MenuApprovalRequest(
            menu_id=menu_id,
            requested_by=requester_id,
            **request_data
        )
        
        self.db_session.add(request)
        await self.db_session.commit()
        await self.db_session.refresh(request)
        
        return request

    async def find_by_menu(
        self,
        menu_id: UUID
    ) -> List[MenuApprovalRequest]:
        """
        Get approval requests for a menu.
        
        Args:
            menu_id: Menu identifier
            
        Returns:
            List of approval requests
        """
        query = (
            select(MenuApprovalRequest)
            .where(MenuApprovalRequest.menu_id == menu_id)
            .order_by(desc(MenuApprovalRequest.created_at))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_by_status(
        self,
        status: str,
        hostel_id: Optional[UUID] = None
    ) -> List[MenuApprovalRequest]:
        """
        Find requests by status.
        
        Args:
            status: Request status
            hostel_id: Hostel filter (optional)
            
        Returns:
            List of requests
        """
        from app.models.mess.mess_menu import MessMenu
        
        query = (
            select(MenuApprovalRequest)
            .where(MenuApprovalRequest.request_status == status)
        )
        
        if hostel_id:
            query = query.join(MessMenu).where(MessMenu.hostel_id == hostel_id)
            
        result = await self.db_session.execute(query)
        return list(result.scalars().all())


class ApprovalWorkflowRepository(BaseRepository[ApprovalWorkflow]):
    """
    Repository for managing approval workflows.
    
    Tracks complete workflow state with stages, transitions,
    and timeline management.
    """

    def __init__(self, db_session):
        """Initialize repository with ApprovalWorkflow model."""
        super().__init__(ApprovalWorkflow, db_session)

    async def get_by_menu(
        self,
        menu_id: UUID
    ) -> Optional[ApprovalWorkflow]:
        """
        Get workflow for a menu.
        
        Args:
            menu_id: Menu identifier
            
        Returns:
            ApprovalWorkflow if found
        """
        query = select(ApprovalWorkflow).where(
            ApprovalWorkflow.menu_id == menu_id
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_workflows(
        self,
        hostel_id: UUID,
        current_stage: Optional[str] = None
    ) -> List[ApprovalWorkflow]:
        """
        Get active workflows.
        
        Args:
            hostel_id: Hostel identifier
            current_stage: Filter by stage (optional)
            
        Returns:
            List of active workflows
        """
        conditions = [
            ApprovalWorkflow.hostel_id == hostel_id,
            ApprovalWorkflow.current_stage.in_([
                'draft', 'submitted', 'under_review'
            ])
        ]
        
        if current_stage:
            conditions.append(ApprovalWorkflow.current_stage == current_stage)
            
        query = select(ApprovalWorkflow).where(and_(*conditions))
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def advance_stage(
        self,
        workflow_id: UUID,
        new_stage: str,
        pending_with: Optional[UUID] = None
    ) -> Optional[ApprovalWorkflow]:
        """
        Advance workflow to next stage.
        
        Args:
            workflow_id: ApprovalWorkflow identifier
            new_stage: New stage name
            pending_with: User handling next stage
            
        Returns:
            Updated ApprovalWorkflow
        """
        workflow = await self.get_by_id(workflow_id)
        if not workflow:
            return None
            
        # Update stage history
        stage_history = workflow.stage_history or {}
        stage_history[new_stage] = {
            'entered_at': datetime.utcnow().isoformat(),
            'from_stage': workflow.current_stage
        }
        
        workflow.current_stage = new_stage
        workflow.stage_history = stage_history
        workflow.pending_with = pending_with
        
        # Update stage-specific timestamps
        if new_stage == 'submitted':
            workflow.submitted_for_approval_at = datetime.utcnow()
        elif new_stage == 'under_review':
            workflow.review_started_at = datetime.utcnow()
        elif new_stage == 'approved':
            workflow.approved_at = datetime.utcnow()
        elif new_stage == 'rejected':
            workflow.rejected_at = datetime.utcnow()
        elif new_stage == 'published':
            workflow.published_at = datetime.utcnow()
            
        await self.db_session.commit()
        await self.db_session.refresh(workflow)
        
        return workflow


class ApprovalHistoryRepository(BaseRepository[ApprovalHistory]):
    """
    Repository for approval history tracking.
    
    Maintains complete audit trail of approval decisions
    and timeline.
    """

    def __init__(self, db_session):
        """Initialize repository with ApprovalHistory model."""
        super().__init__(ApprovalHistory, db_session)

    async def get_by_menu(
        self,
        menu_id: UUID
    ) -> Optional[ApprovalHistory]:
        """
        Get approval history for menu.
        
        Args:
            menu_id: Menu identifier
            
        Returns:
            ApprovalHistory if found
        """
        query = select(ApprovalHistory).where(
            ApprovalHistory.menu_id == menu_id
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def record_submission(
        self,
        menu_id: UUID
    ) -> ApprovalHistory:
        """
        Record menu submission in history.
        
        Args:
            menu_id: Menu identifier
            
        Returns:
            Updated or created ApprovalHistory
        """
        history = await self.get_by_menu(menu_id)
        
        if not history:
            history = ApprovalHistory(
                menu_id=menu_id,
                total_submissions=1,
                first_submission_date=datetime.utcnow(),
                last_submission_date=datetime.utcnow(),
                current_status='pending'
            )
            self.db_session.add(history)
        else:
            history.total_submissions += 1
            history.last_submission_date = datetime.utcnow()
            
        await self.db_session.commit()
        await self.db_session.refresh(history)
        
        return history

    async def record_decision(
        self,
        menu_id: UUID,
        decision: str,
        approver_name: str
    ) -> Optional[ApprovalHistory]:
        """
        Record approval decision.
        
        Args:
            menu_id: Menu identifier
            decision: Decision made (approved/rejected)
            approver_name: Name of approver
            
        Returns:
            Updated ApprovalHistory
        """
        history = await self.get_by_menu(menu_id)
        if not history:
            return None
            
        if decision == 'approved':
            history.total_approvals += 1
            history.final_decision = 'approved'
            history.final_approver = approver_name
            history.final_decision_date = datetime.utcnow()
        elif decision == 'rejected':
            history.total_rejections += 1
            history.final_decision = 'rejected'
            history.final_approver = approver_name
            history.final_decision_date = datetime.utcnow()
            
        history.current_status = decision
        
        await self.db_session.commit()
        await self.db_session.refresh(history)
        
        return history


class ApprovalAttemptRepository(BaseRepository[ApprovalAttempt]):
    """
    Repository for tracking individual approval attempts.
    
    Records each submission attempt with changes and feedback.
    """

    def __init__(self, db_session):
        """Initialize repository with ApprovalAttempt model."""
        super().__init__(ApprovalAttempt, db_session)

    async def create_attempt(
        self,
        menu_approval_id: UUID,
        attempt_data: Dict
    ) -> ApprovalAttempt:
        """
        Create new approval attempt.
        
        Args:
            menu_approval_id: MenuApproval identifier
            attempt_data: Attempt details
            
        Returns:
            Created ApprovalAttempt
        """
        # Get current max attempt number
        query = (
            select(func.max(ApprovalAttempt.attempt_number))
            .where(ApprovalAttempt.menu_approval_id == menu_approval_id)
        )
        
        result = await self.db_session.execute(query)
        max_attempt = result.scalar() or 0
        
        attempt = ApprovalAttempt(
            menu_approval_id=menu_approval_id,
            attempt_number=max_attempt + 1,
            **attempt_data
        )
        
        self.db_session.add(attempt)
        await self.db_session.commit()
        await self.db_session.refresh(attempt)
        
        return attempt

    async def find_by_approval(
        self,
        menu_approval_id: UUID
    ) -> List[ApprovalAttempt]:
        """
        Get all attempts for an approval.
        
        Args:
            menu_approval_id: MenuApproval identifier
            
        Returns:
            List of attempts in chronological order
        """
        query = (
            select(ApprovalAttempt)
            .where(ApprovalAttempt.menu_approval_id == menu_approval_id)
            .order_by(ApprovalAttempt.attempt_number)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())


class ApprovalRuleRepository(BaseRepository[ApprovalRule]):
    """
    Repository for managing approval rules.
    
    Handles automated approval rules with conditions and
    effectiveness tracking.
    """

    def __init__(self, db_session):
        """Initialize repository with ApprovalRule model."""
        super().__init__(ApprovalRule, db_session)

    async def get_active_rules(
        self,
        hostel_id: Optional[UUID] = None,
        rule_type: Optional[str] = None
    ) -> List[ApprovalRule]:
        """
        Get active approval rules.
        
        Args:
            hostel_id: Hostel identifier (optional for global rules)
            rule_type: Rule type filter (optional)
            
        Returns:
            List of active rules
        """
        conditions = [
            ApprovalRule.is_active == True,
            ApprovalRule.deleted_at.is_(None)
        ]
        
        if hostel_id:
            conditions.append(
                or_(
                    ApprovalRule.hostel_id == hostel_id,
                    ApprovalRule.hostel_id.is_(None)
                )
            )
            
        if rule_type:
            conditions.append(ApprovalRule.rule_type == rule_type)
            
        query = (
            select(ApprovalRule)
            .where(and_(*conditions))
            .order_by(desc(ApprovalRule.priority))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def check_auto_approval_eligibility(
        self,
        menu_data: Dict
    ) -> Optional[ApprovalRule]:
        """
        Check if menu qualifies for auto-approval.
        
        Args:
            menu_data: Menu data to check
            
        Returns:
            Matching ApprovalRule if eligible
        """
        rules = await self.get_active_rules(
            hostel_id=menu_data.get('hostel_id'),
            rule_type='auto_approve'
        )
        
        for rule in rules:
            if self._evaluate_rule(rule, menu_data):
                return rule
                
        return None

    def _evaluate_rule(
        self,
        rule: ApprovalRule,
        menu_data: Dict
    ) -> bool:
        """
        Evaluate if rule conditions are met.
        
        Args:
            rule: ApprovalRule to evaluate
            menu_data: Menu data to check against
            
        Returns:
            True if conditions met
        """
        # Cost check
        if rule.max_cost_per_person:
            cost = menu_data.get('estimated_cost_per_person', 0)
            if cost > rule.max_cost_per_person:
                return False
                
        # Menu type check
        if rule.allowed_menu_types:
            menu_type = menu_data.get('menu_type')
            if menu_type not in rule.allowed_menu_types:
                return False
                
        # Excluded items check
        if rule.excluded_items:
            menu_items = menu_data.get('items', [])
            if any(item in rule.excluded_items for item in menu_items):
                return False
                
        # Add more condition checks based on rule.conditions JSON
        
        return True

    async def record_rule_usage(
        self,
        rule_id: UUID,
        success: bool
    ) -> Optional[ApprovalRule]:
        """
        Record rule usage for effectiveness tracking.
        
        Args:
            rule_id: ApprovalRule identifier
            success: Whether application was successful
            
        Returns:
            Updated ApprovalRule
        """
        rule = await self.get_by_id(rule_id)
        if not rule:
            return None
            
        rule.times_applied += 1
        if success:
            rule.successful_applications += 1
            
        await self.db_session.commit()
        await self.db_session.refresh(rule)
        
        return rule


class BulkApprovalRepository(BaseRepository[BulkApproval]):
    """
    Repository for bulk approval operations.
    
    Manages bulk approval/rejection operations with
    tracking and error handling.
    """

    def __init__(self, db_session):
        """Initialize repository with BulkApproval model."""
        super().__init__(BulkApproval, db_session)

    async def create_bulk_operation(
        self,
        operation_data: Dict
    ) -> BulkApproval:
        """
        Create new bulk approval operation.
        
        Args:
            operation_data: Operation details
            
        Returns:
            Created BulkApproval
        """
        operation = BulkApproval(**operation_data)
        
        self.db_session.add(operation)
        await self.db_session.commit()
        await self.db_session.refresh(operation)
        
        return operation

    async def update_operation_progress(
        self,
        operation_id: UUID,
        success_ids: List[UUID],
        failed_ids: List[UUID],
        error_details: Optional[Dict] = None
    ) -> Optional[BulkApproval]:
        """
        Update bulk operation progress.
        
        Args:
            operation_id: BulkApproval identifier
            success_ids: List of successful menu IDs
            failed_ids: List of failed menu IDs
            error_details: Error details (optional)
            
        Returns:
            Updated BulkApproval
        """
        operation = await self.get_by_id(operation_id)
        if not operation:
            return None
            
        operation.successful_count = len(success_ids)
        operation.failed_count = len(failed_ids)
        operation.success_menu_ids = success_ids
        operation.failed_menu_ids = failed_ids
        
        if error_details:
            operation.error_details = error_details
            
        # Update status
        if operation.failed_count == 0:
            operation.operation_status = 'completed'
        elif operation.successful_count == 0:
            operation.operation_status = 'failed'
        else:
            operation.operation_status = 'partial_success'
            
        operation.completed_at = datetime.utcnow()
        
        await self.db_session.commit()
        await self.db_session.refresh(operation)
        
        return operation

    async def get_recent_operations(
        self,
        approver_id: UUID,
        limit: int = 10
    ) -> List[BulkApproval]:
        """
        Get recent bulk operations by approver.
        
        Args:
            approver_id: Approver identifier
            limit: Maximum number of results
            
        Returns:
            List of recent operations
        """
        query = (
            select(BulkApproval)
            .where(BulkApproval.approver_id == approver_id)
            .order_by(desc(BulkApproval.created_at))
            .limit(limit)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())