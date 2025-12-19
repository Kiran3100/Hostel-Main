# app/repositories/maintenance/maintenance_approval_repository.py
"""
Maintenance Approval Repository.

Approval workflow management with multi-level approvals,
threshold management, and compliance tracking.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.maintenance import (
    MaintenanceApproval,
    ApprovalThreshold,
    ApprovalWorkflow,
    MaintenanceRequest,
)
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.pagination import PaginationParams, PaginatedResult


class MaintenanceApprovalRepository(BaseRepository[MaintenanceApproval]):
    """
    Repository for maintenance approval operations.
    
    Manages approval requests, workflows, and threshold configurations
    with comprehensive tracking and analytics.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with session."""
        super().__init__(MaintenanceApproval, session)
    
    # ============================================================================
    # CREATE OPERATIONS
    # ============================================================================
    
    def create_approval_request(
        self,
        maintenance_request_id: UUID,
        requested_by: UUID,
        estimated_cost: Decimal,
        cost_justification: str,
        approval_reason: str,
        cost_breakdown: Optional[Dict[str, Any]] = None,
        business_impact: Optional[str] = None,
        urgent: bool = False,
        urgency_reason: Optional[str] = None,
        **kwargs
    ) -> MaintenanceApproval:
        """
        Create new approval request for maintenance.
        
        Args:
            maintenance_request_id: Related maintenance request
            requested_by: User requesting approval
            estimated_cost: Cost requiring approval
            cost_justification: Justification for cost
            approval_reason: Reason approval needed
            cost_breakdown: Detailed cost breakdown
            business_impact: Business impact description
            urgent: Whether approval is urgent
            urgency_reason: Reason for urgency
            **kwargs: Additional approval attributes
            
        Returns:
            Created approval request
        """
        # Determine approval level based on cost
        approval_level = self._determine_approval_level(
            estimated_cost,
            maintenance_request_id
        )
        
        approval_data = {
            "maintenance_request_id": maintenance_request_id,
            "requested_by": requested_by,
            "estimated_cost": estimated_cost,
            "cost_breakdown": cost_breakdown or {},
            "cost_justification": cost_justification,
            "approval_reason": approval_reason,
            "business_impact": business_impact,
            "urgent": urgent,
            "urgency_reason": urgency_reason,
            "approval_level": approval_level,
            "approved": None,  # Pending
            **kwargs
        }
        
        approval = self.create(approval_data)
        
        # Create workflow entry
        self._create_workflow_entry(approval.id, approval_level)
        
        return approval
    
    def create_threshold_config(
        self,
        hostel_id: UUID,
        supervisor_limit: Decimal,
        admin_required_above: Decimal,
        auto_approve_below: Decimal,
        auto_approve_enabled: bool = True,
        **kwargs
    ) -> ApprovalThreshold:
        """
        Create approval threshold configuration for hostel.
        
        Args:
            hostel_id: Hostel identifier
            supervisor_limit: Supervisor approval limit
            admin_required_above: Admin approval threshold
            auto_approve_below: Auto-approval threshold
            auto_approve_enabled: Enable auto-approval
            **kwargs: Additional threshold attributes
            
        Returns:
            Created threshold configuration
        """
        threshold_data = {
            "hostel_id": hostel_id,
            "supervisor_approval_limit": supervisor_limit,
            "admin_approval_required_above": admin_required_above,
            "auto_approve_below": auto_approve_below,
            "auto_approve_enabled": auto_approve_enabled,
            "is_active": True,
            **kwargs
        }
        
        threshold = ApprovalThreshold(**threshold_data)
        self.session.add(threshold)
        self.session.commit()
        self.session.refresh(threshold)
        
        return threshold
    
    # ============================================================================
    # READ OPERATIONS
    # ============================================================================
    
    def find_by_request(
        self,
        request_id: UUID,
        include_historical: bool = True
    ) -> List[MaintenanceApproval]:
        """
        Find all approval requests for a maintenance request.
        
        Args:
            request_id: Maintenance request identifier
            include_historical: Include historical approvals
            
        Returns:
            List of approval requests
        """
        query = select(MaintenanceApproval).where(
            MaintenanceApproval.maintenance_request_id == request_id,
            MaintenanceApproval.deleted_at.is_(None)
        )
        
        if not include_historical:
            query = query.where(MaintenanceApproval.approved.is_(None))
        
        query = query.order_by(MaintenanceApproval.requested_at.desc())
        
        return list(self.session.execute(query).scalars().all())
    
    def find_pending_approvals(
        self,
        approver_id: Optional[UUID] = None,
        urgent_only: bool = False,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceApproval]:
        """
        Find pending approval requests.
        
        Args:
            approver_id: Optional approver filter
            urgent_only: Only urgent approvals
            pagination: Pagination parameters
            
        Returns:
            Paginated pending approvals
        """
        query = select(MaintenanceApproval).where(
            MaintenanceApproval.approved.is_(None),
            MaintenanceApproval.deleted_at.is_(None)
        )
        
        if urgent_only:
            query = query.where(MaintenanceApproval.urgent == True)
        
        # Order by urgency and request date
        query = query.order_by(
            MaintenanceApproval.urgent.desc(),
            MaintenanceApproval.requested_at.asc()
        )
        
        return self.paginate(query, pagination)
    
    def find_by_requester(
        self,
        requester_id: UUID,
        status: Optional[str] = None,  # 'pending', 'approved', 'rejected'
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceApproval]:
        """
        Find approval requests by requester.
        
        Args:
            requester_id: Requester identifier
            status: Optional status filter
            pagination: Pagination parameters
            
        Returns:
            Paginated approval requests
        """
        query = select(MaintenanceApproval).where(
            MaintenanceApproval.requested_by == requester_id,
            MaintenanceApproval.deleted_at.is_(None)
        )
        
        if status == 'pending':
            query = query.where(MaintenanceApproval.approved.is_(None))
        elif status == 'approved':
            query = query.where(MaintenanceApproval.approved == True)
        elif status == 'rejected':
            query = query.where(MaintenanceApproval.approved == False)
        
        query = query.order_by(MaintenanceApproval.requested_at.desc())
        
        return self.paginate(query, pagination)
    
    def find_overdue_approvals(
        self,
        hours: int = 24,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceApproval]:
        """
        Find approval requests pending beyond specified hours.
        
        Args:
            hours: Hours threshold for overdue
            pagination: Pagination parameters
            
        Returns:
            Paginated overdue approvals
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = select(MaintenanceApproval).where(
            MaintenanceApproval.approved.is_(None),
            MaintenanceApproval.requested_at < cutoff_time,
            MaintenanceApproval.deleted_at.is_(None)
        ).order_by(MaintenanceApproval.requested_at.asc())
        
        return self.paginate(query, pagination)
    
    def find_escalated_approvals(
        self,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceApproval]:
        """
        Find escalated approval requests.
        
        Args:
            pagination: Pagination parameters
            
        Returns:
            Paginated escalated approvals
        """
        query = select(MaintenanceApproval).where(
            MaintenanceApproval.escalated == True,
            MaintenanceApproval.approved.is_(None),
            MaintenanceApproval.deleted_at.is_(None)
        ).order_by(MaintenanceApproval.escalated_at.desc())
        
        return self.paginate(query, pagination)
    
    def get_threshold_config(
        self,
        hostel_id: UUID
    ) -> Optional[ApprovalThreshold]:
        """
        Get active approval threshold configuration for hostel.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            Active threshold configuration, or None
        """
        query = select(ApprovalThreshold).where(
            ApprovalThreshold.hostel_id == hostel_id,
            ApprovalThreshold.is_active == True
        ).order_by(ApprovalThreshold.created_at.desc())
        
        return self.session.execute(query).scalar_one_or_none()
    
    # ============================================================================
    # UPDATE OPERATIONS
    # ============================================================================
    
    def approve_request(
        self,
        approval_id: UUID,
        approved_by: UUID,
        approved_amount: Optional[Decimal] = None,
        conditions: Optional[str] = None,
        notes: Optional[str] = None
    ) -> MaintenanceApproval:
        """
        Approve maintenance request.
        
        Args:
            approval_id: Approval request identifier
            approved_by: User approving request
            approved_amount: Approved amount (defaults to requested)
            conditions: Approval conditions
            notes: Approval notes
            
        Returns:
            Updated approval request
        """
        approval = self.find_by_id(approval_id)
        if not approval:
            raise ValueError(f"Approval {approval_id} not found")
        
        if approval.approved is not None:
            raise ValueError("Approval already processed")
        
        approval.approve(
            approved_by=approved_by,
            approved_amount=approved_amount,
            conditions=conditions,
            notes=notes
        )
        
        # Update workflow
        self._update_workflow_status(approval_id, "approved")
        
        self.session.commit()
        self.session.refresh(approval)
        
        return approval
    
    def reject_request(
        self,
        approval_id: UUID,
        rejected_by: UUID,
        rejection_reason: str,
        suggested_alternative: Optional[str] = None,
        allow_resubmission: bool = True
    ) -> MaintenanceApproval:
        """
        Reject maintenance approval request.
        
        Args:
            approval_id: Approval request identifier
            rejected_by: User rejecting request
            rejection_reason: Reason for rejection
            suggested_alternative: Alternative suggestion
            allow_resubmission: Allow resubmission
            
        Returns:
            Updated approval request
        """
        approval = self.find_by_id(approval_id)
        if not approval:
            raise ValueError(f"Approval {approval_id} not found")
        
        if approval.approved is not None:
            raise ValueError("Approval already processed")
        
        approval.reject(
            rejected_by=rejected_by,
            rejection_reason=rejection_reason,
            suggested_alternative=suggested_alternative,
            allow_resubmission=allow_resubmission
        )
        
        # Update workflow
        self._update_workflow_status(approval_id, "rejected")
        
        self.session.commit()
        self.session.refresh(approval)
        
        return approval
    
    def escalate_approval(
        self,
        approval_id: UUID,
        escalation_reason: str,
        new_approval_level: str
    ) -> MaintenanceApproval:
        """
        Escalate approval to higher authority.
        
        Args:
            approval_id: Approval request identifier
            escalation_reason: Reason for escalation
            new_approval_level: New approval level
            
        Returns:
            Updated approval request
        """
        approval = self.find_by_id(approval_id)
        if not approval:
            raise ValueError(f"Approval {approval_id} not found")
        
        approval.escalate(
            escalation_reason=escalation_reason,
            new_approval_level=new_approval_level
        )
        
        self.session.commit()
        self.session.refresh(approval)
        
        return approval
    
    # ============================================================================
    # ANALYTICS AND REPORTING
    # ============================================================================
    
    def get_approval_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get approval statistics for analysis.
        
        Args:
            hostel_id: Optional hostel filter
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            Approval statistics dictionary
        """
        # Base query
        query = select(
            func.count(MaintenanceApproval.id).label("total_requests"),
            func.sum(
                func.case(
                    (MaintenanceApproval.approved == True, 1),
                    else_=0
                )
            ).label("approved"),
            func.sum(
                func.case(
                    (MaintenanceApproval.approved == False, 1),
                    else_=0
                )
            ).label("rejected"),
            func.sum(
                func.case(
                    (MaintenanceApproval.approved.is_(None), 1),
                    else_=0
                )
            ).label("pending"),
            func.avg(MaintenanceApproval.estimated_cost).label("avg_cost"),
            func.sum(MaintenanceApproval.approved_amount).label("total_approved_amount"),
            func.avg(
                func.extract(
                    'epoch',
                    MaintenanceApproval.approved_at - MaintenanceApproval.requested_at
                ) / 3600
            ).label("avg_approval_time_hours")
        ).where(
            MaintenanceApproval.deleted_at.is_(None)
        )
        
        # Apply filters
        if start_date:
            query = query.where(MaintenanceApproval.requested_at >= start_date)
        if end_date:
            query = query.where(MaintenanceApproval.requested_at <= end_date)
        
        result = self.session.execute(query).first()
        
        approval_rate = Decimal("0.00")
        if result.total_requests and result.total_requests > 0:
            approval_rate = round(
                Decimal(result.approved or 0) / Decimal(result.total_requests) * 100,
                2
            )
        
        return {
            "total_requests": result.total_requests or 0,
            "approved": result.approved or 0,
            "rejected": result.rejected or 0,
            "pending": result.pending or 0,
            "approval_rate": float(approval_rate),
            "average_cost": float(result.avg_cost or 0),
            "total_approved_amount": float(result.total_approved_amount or 0),
            "average_approval_time_hours": float(result.avg_approval_time_hours or 0)
        }
    
    def get_approval_trends(
        self,
        hostel_id: UUID,
        months: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Get monthly approval trends.
        
        Args:
            hostel_id: Hostel identifier
            months: Number of months to analyze
            
        Returns:
            List of monthly trend data
        """
        cutoff_date = datetime.utcnow() - timedelta(days=months * 30)
        
        # Get monthly aggregates
        query = select(
            func.date_trunc('month', MaintenanceApproval.requested_at).label('month'),
            func.count(MaintenanceApproval.id).label("total"),
            func.sum(
                func.case(
                    (MaintenanceApproval.approved == True, 1),
                    else_=0
                )
            ).label("approved"),
            func.sum(MaintenanceApproval.estimated_cost).label("total_cost")
        ).where(
            MaintenanceApproval.requested_at >= cutoff_date,
            MaintenanceApproval.deleted_at.is_(None)
        ).group_by(
            'month'
        ).order_by(
            'month'
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "month": row.month.strftime("%Y-%m"),
                "total_requests": row.total,
                "approved": row.approved,
                "total_cost": float(row.total_cost or 0)
            }
            for row in results
        ]
    
    def calculate_average_response_time(
        self,
        approval_level: Optional[str] = None,
        days: int = 90
    ) -> Optional[float]:
        """
        Calculate average approval response time.
        
        Args:
            approval_level: Optional approval level filter
            days: Time period in days
            
        Returns:
            Average response time in hours, or None
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = select(
            func.avg(
                func.extract(
                    'epoch',
                    MaintenanceApproval.approved_at - MaintenanceApproval.requested_at
                ) / 3600
            ).label("avg_hours")
        ).where(
            MaintenanceApproval.approved_at.isnot(None),
            MaintenanceApproval.requested_at >= cutoff_date,
            MaintenanceApproval.deleted_at.is_(None)
        )
        
        if approval_level:
            query = query.where(MaintenanceApproval.approval_level == approval_level)
        
        result = self.session.execute(query).scalar_one_or_none()
        
        return float(result) if result else None
    
    # ============================================================================
    # WORKFLOW MANAGEMENT
    # ============================================================================
    
    def get_workflow_status(
        self,
        request_id: UUID
    ) -> Optional[ApprovalWorkflow]:
        """
        Get approval workflow status for request.
        
        Args:
            request_id: Maintenance request identifier
            
        Returns:
            Workflow status, or None
        """
        query = select(ApprovalWorkflow).where(
            ApprovalWorkflow.maintenance_request_id == request_id
        )
        
        return self.session.execute(query).scalar_one_or_none()
    
    def update_workflow_deadline(
        self,
        request_id: UUID,
        new_deadline: datetime
    ) -> ApprovalWorkflow:
        """
        Update approval workflow deadline.
        
        Args:
            request_id: Maintenance request identifier
            new_deadline: New approval deadline
            
        Returns:
            Updated workflow
        """
        workflow = self.get_workflow_status(request_id)
        if not workflow:
            raise ValueError(f"Workflow for request {request_id} not found")
        
        workflow.approval_deadline = new_deadline
        workflow.update_overdue_status()
        
        self.session.commit()
        self.session.refresh(workflow)
        
        return workflow
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _determine_approval_level(
        self,
        estimated_cost: Decimal,
        request_id: UUID
    ) -> str:
        """
        Determine required approval level based on cost.
        
        Args:
            estimated_cost: Estimated cost
            request_id: Maintenance request identifier
            
        Returns:
            Required approval level
        """
        # Get request to find hostel
        request_query = select(MaintenanceRequest).where(
            MaintenanceRequest.id == request_id
        )
        request = self.session.execute(request_query).scalar_one_or_none()
        
        if not request:
            return "supervisor"
        
        # Get threshold config
        threshold = self.get_threshold_config(request.hostel_id)
        
        if not threshold:
            # Default thresholds
            if estimated_cost < Decimal("1000.00"):
                return "auto"
            elif estimated_cost < Decimal("5000.00"):
                return "supervisor"
            else:
                return "admin"
        
        return threshold.get_required_approval_level(estimated_cost)
    
    def _create_workflow_entry(
        self,
        approval_id: UUID,
        approval_level: str
    ) -> None:
        """
        Create workflow entry for approval.
        
        Args:
            approval_id: Approval identifier
            approval_level: Required approval level
        """
        approval = self.find_by_id(approval_id)
        if not approval:
            return
        
        workflow = ApprovalWorkflow(
            maintenance_request_id=approval.maintenance_request_id,
            requires_approval=True,
            approval_pending=True,
            approval_level_required=approval_level,
            submitted_for_approval_at=datetime.utcnow(),
            approval_deadline=datetime.utcnow() + timedelta(hours=48),
            total_approval_steps=1
        )
        
        self.session.add(workflow)
        self.session.commit()
    
    def _update_workflow_status(
        self,
        approval_id: UUID,
        status: str
    ) -> None:
        """
        Update workflow status after approval decision.
        
        Args:
            approval_id: Approval identifier
            status: New status ('approved' or 'rejected')
        """
        approval = self.find_by_id(approval_id)
        if not approval:
            return
        
        workflow = self.get_workflow_status(approval.maintenance_request_id)
        if not workflow:
            return
        
        workflow.approval_pending = False
        workflow.approval_steps_completed = 1
        
        self.session.commit()