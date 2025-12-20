# --- File: C:\Hostel-Main\app\services\fee_structure\fee_approval_service.py ---
"""
Fee Approval Service

Business logic layer for fee structure approval workflows including
creation, review, approval, rejection, and audit trail management.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.fee_structure.fee_structure import FeeStructure, FeeApproval
from app.repositories.fee_structure.fee_structure_repository import (
    FeeStructureRepository,
)
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    BusinessLogicException,
)
from app.core.logging import logger


class FeeApprovalService:
    """
    Fee Approval Service
    
    Manages approval workflows for fee structure changes including
    multi-level approvals, audit trails, and automated notifications.
    """
    
    def __init__(self, session: Session):
        """
        Initialize service with database session.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.fee_structure_repo = FeeStructureRepository(session)
    
    # ============================================================
    # Core Approval Operations
    # ============================================================
    
    def submit_for_approval(
        self,
        fee_structure_id: UUID,
        submitted_by_id: UUID,
        change_summary: str,
        justification: Optional[str] = None,
        supporting_documents: Optional[List[str]] = None
    ) -> FeeApproval:
        """
        Submit fee structure for approval.
        
        Args:
            fee_structure_id: Fee structure identifier
            submitted_by_id: User submitting for approval
            change_summary: Summary of changes
            justification: Justification for changes
            supporting_documents: List of document references
            
        Returns:
            Created FeeApproval instance
            
        Raises:
            NotFoundException: If fee structure not found
            BusinessLogicException: If already pending approval
        """
        logger.info(f"Submitting fee structure {fee_structure_id} for approval")
        
        # Get fee structure
        fee_structure = self.fee_structure_repo.find_by_id(fee_structure_id)
        if not fee_structure:
            raise NotFoundException(f"Fee structure {fee_structure_id} not found")
        
        # Check if already pending approval
        existing_approvals = self._get_pending_approvals(fee_structure_id)
        if existing_approvals:
            raise BusinessLogicException(
                "Fee structure already has pending approval"
            )
        
        # Get previous amount for comparison
        previous_amount = self._get_previous_amount(fee_structure)
        
        try:
            # Create approval record
            approval = FeeApproval(
                fee_structure_id=fee_structure_id,
                approval_status='pending',
                change_summary=change_summary,
                previous_amount=previous_amount,
                new_amount=fee_structure.amount,
                created_by=submitted_by_id,
                created_at=datetime.utcnow()
            )
            
            # Store additional data
            approval.rejection_reason = justification  # Temporarily use this field
            
            self.session.add(approval)
            self.session.commit()
            
            logger.info(f"Approval record created: {approval.id}")
            
            # Send notification (async)
            self._send_approval_notification(approval, 'submitted')
            
            return approval
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error submitting for approval: {str(e)}")
            raise
    
    def approve_fee_structure(
        self,
        approval_id: UUID,
        approved_by_id: UUID,
        approval_notes: Optional[str] = None,
        effective_date: Optional[Date] = None
    ) -> FeeApproval:
        """
        Approve a fee structure.
        
        Args:
            approval_id: Approval record identifier
            approved_by_id: User approving
            approval_notes: Optional approval notes
            effective_date: Optional effective date override
            
        Returns:
            Updated FeeApproval instance
            
        Raises:
            NotFoundException: If approval not found
            BusinessLogicException: If not in pending status
        """
        logger.info(f"Approving fee structure approval {approval_id}")
        
        # Get approval record
        approval = self._get_approval(approval_id)
        
        if approval.approval_status != 'pending':
            raise BusinessLogicException(
                f"Cannot approve - current status is {approval.approval_status}"
            )
        
        # Validate approver authority
        self._validate_approver_authority(approved_by_id, approval.new_amount)
        
        try:
            # Update approval record
            approval.approval_status = 'approved'
            approval.approved_by_id = approved_by_id
            approval.approved_at = datetime.utcnow()
            
            if approval_notes:
                approval.change_summary += f"\n\nApproval Notes: {approval_notes}"
            
            # Activate fee structure
            fee_structure = self.fee_structure_repo.find_by_id(
                approval.fee_structure_id
            )
            
            if fee_structure:
                fee_structure.is_active = True
                
                # Update effective date if provided
                if effective_date:
                    fee_structure.effective_from = effective_date
            
            self.session.commit()
            
            logger.info(f"Fee structure approved: {approval.fee_structure_id}")
            
            # Send notification
            self._send_approval_notification(approval, 'approved')
            
            return approval
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error approving fee structure: {str(e)}")
            raise
    
    def reject_fee_structure(
        self,
        approval_id: UUID,
        rejected_by_id: UUID,
        rejection_reason: str,
        requires_resubmission: bool = True
    ) -> FeeApproval:
        """
        Reject a fee structure.
        
        Args:
            approval_id: Approval record identifier
            rejected_by_id: User rejecting
            rejection_reason: Reason for rejection
            requires_resubmission: Whether resubmission is required
            
        Returns:
            Updated FeeApproval instance
            
        Raises:
            NotFoundException: If approval not found
            BusinessLogicException: If not in pending status
        """
        logger.info(f"Rejecting fee structure approval {approval_id}")
        
        # Get approval record
        approval = self._get_approval(approval_id)
        
        if approval.approval_status != 'pending':
            raise BusinessLogicException(
                f"Cannot reject - current status is {approval.approval_status}"
            )
        
        try:
            # Update approval record
            approval.approval_status = 'rejected'
            approval.approved_by_id = rejected_by_id
            approval.approved_at = datetime.utcnow()
            approval.rejection_reason = rejection_reason
            
            # Deactivate fee structure if it was active
            if not requires_resubmission:
                fee_structure = self.fee_structure_repo.find_by_id(
                    approval.fee_structure_id
                )
                if fee_structure:
                    fee_structure.is_active = False
            
            self.session.commit()
            
            logger.info(f"Fee structure rejected: {approval.fee_structure_id}")
            
            # Send notification
            self._send_approval_notification(approval, 'rejected')
            
            return approval
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error rejecting fee structure: {str(e)}")
            raise
    
    def request_revision(
        self,
        approval_id: UUID,
        reviewer_id: UUID,
        revision_notes: str,
        specific_changes_required: List[str]
    ) -> FeeApproval:
        """
        Request revisions to a fee structure.
        
        Args:
            approval_id: Approval record identifier
            reviewer_id: User requesting revision
            revision_notes: Notes on required revisions
            specific_changes_required: List of specific changes needed
            
        Returns:
            Updated FeeApproval instance
        """
        logger.info(f"Requesting revision for approval {approval_id}")
        
        approval = self._get_approval(approval_id)
        
        try:
            # Update status to indicate revision needed
            approval.approval_status = 'pending'  # Keep as pending but flag for revision
            approval.rejection_reason = f"REVISION REQUESTED: {revision_notes}\n\nRequired Changes:\n" + \
                                       "\n".join(f"- {change}" for change in specific_changes_required)
            
            self.session.commit()
            
            logger.info(f"Revision requested for approval {approval_id}")
            
            # Send notification
            self._send_approval_notification(approval, 'revision_requested')
            
            return approval
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error requesting revision: {str(e)}")
            raise
    
    # ============================================================
    # Approval Retrieval and Queries
    # ============================================================
    
    def get_approval(self, approval_id: UUID) -> FeeApproval:
        """Get approval record by ID."""
        return self._get_approval(approval_id)
    
    def get_pending_approvals(
        self,
        approved_by_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        limit: int = 50
    ) -> List[FeeApproval]:
        """
        Get pending approval records.
        
        Args:
            approved_by_id: Optional approver filter
            hostel_id: Optional hostel filter
            limit: Maximum records to return
            
        Returns:
            List of pending FeeApproval instances
        """
        from sqlalchemy import and_
        
        query = self.session.query(FeeApproval).join(
            FeeStructure
        ).filter(
            FeeApproval.approval_status == 'pending'
        )
        
        if hostel_id:
            query = query.filter(FeeStructure.hostel_id == hostel_id)
        
        # Note: approved_by filtering would need additional logic
        # as approvals don't have assigned approvers until approval
        
        return query.order_by(
            FeeApproval.created_at.asc()
        ).limit(limit).all()
    
    def get_approval_history(
        self,
        fee_structure_id: UUID
    ) -> List[FeeApproval]:
        """
        Get complete approval history for a fee structure.
        
        Args:
            fee_structure_id: Fee structure identifier
            
        Returns:
            List of all approval records
        """
        return self.session.query(FeeApproval).filter(
            FeeApproval.fee_structure_id == fee_structure_id
        ).order_by(
            FeeApproval.created_at.desc()
        ).all()
    
    def get_approvals_by_user(
        self,
        user_id: UUID,
        status: Optional[str] = None,
        start_date: Optional[Date] = None,
        end_date: Optional[Date] = None
    ) -> List[FeeApproval]:
        """
        Get approvals by approver.
        
        Args:
            user_id: User identifier
            status: Optional status filter
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            List of FeeApproval instances
        """
        query = self.session.query(FeeApproval).filter(
            FeeApproval.approved_by_id == user_id
        )
        
        if status:
            query = query.filter(FeeApproval.approval_status == status)
        
        if start_date:
            query = query.filter(FeeApproval.created_at >= start_date)
        
        if end_date:
            query = query.filter(FeeApproval.created_at <= end_date)
        
        return query.order_by(FeeApproval.created_at.desc()).all()
    
    # ============================================================
    # Bulk Operations
    # ============================================================
    
    def bulk_approve(
        self,
        approval_ids: List[UUID],
        approved_by_id: UUID,
        approval_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Bulk approve multiple fee structures.
        
        Args:
            approval_ids: List of approval IDs
            approved_by_id: User approving
            approval_notes: Optional notes
            
        Returns:
            Dictionary with approval results
        """
        logger.info(f"Bulk approving {len(approval_ids)} fee structures")
        
        results = {
            'approved': [],
            'failed': [],
            'total': len(approval_ids)
        }
        
        for approval_id in approval_ids:
            try:
                approval = self.approve_fee_structure(
                    approval_id=approval_id,
                    approved_by_id=approved_by_id,
                    approval_notes=approval_notes
                )
                results['approved'].append(str(approval_id))
            except Exception as e:
                logger.error(f"Failed to approve {approval_id}: {str(e)}")
                results['failed'].append({
                    'approval_id': str(approval_id),
                    'error': str(e)
                })
        
        return results
    
    # ============================================================
    # Analytics and Reporting
    # ============================================================
    
    def get_approval_statistics(
        self,
        start_date: Optional[Date] = None,
        end_date: Optional[Date] = None,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Get approval statistics.
        
        Args:
            start_date: Optional start date
            end_date: Optional end date
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary with approval statistics
        """
        from sqlalchemy import func, case
        
        query = self.session.query(
            func.count(FeeApproval.id).label('total'),
            func.sum(case((FeeApproval.approval_status == 'approved', 1), else_=0)).label('approved'),
            func.sum(case((FeeApproval.approval_status == 'rejected', 1), else_=0)).label('rejected'),
            func.sum(case((FeeApproval.approval_status == 'pending', 1), else_=0)).label('pending'),
            func.avg(
                func.extract('epoch', FeeApproval.approved_at - FeeApproval.created_at)
            ).label('avg_approval_time_seconds')
        )
        
        if hostel_id:
            query = query.join(FeeStructure).filter(
                FeeStructure.hostel_id == hostel_id
            )
        
        if start_date:
            query = query.filter(FeeApproval.created_at >= start_date)
        
        if end_date:
            query = query.filter(FeeApproval.created_at <= end_date)
        
        result = query.first()
        
        total = result.total or 0
        approved = result.approved or 0
        rejected = result.rejected or 0
        pending = result.pending or 0
        
        return {
            'total_submissions': total,
            'approved_count': approved,
            'rejected_count': rejected,
            'pending_count': pending,
            'approval_rate': (approved / total * 100) if total > 0 else 0,
            'rejection_rate': (rejected / total * 100) if total > 0 else 0,
            'average_approval_time_hours': (result.avg_approval_time_seconds / 3600) 
                                          if result.avg_approval_time_seconds else 0,
            'period': {
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None
            }
        }
    
    def get_approval_timeline(
        self,
        fee_structure_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get timeline of approval events for a fee structure.
        
        Args:
            fee_structure_id: Fee structure identifier
            
        Returns:
            List of timeline events
        """
        approvals = self.get_approval_history(fee_structure_id)
        
        timeline = []
        for approval in approvals:
            timeline.append({
                'approval_id': str(approval.id),
                'event_type': 'submitted',
                'timestamp': approval.created_at.isoformat(),
                'user_id': str(approval.created_by) if approval.created_by else None,
                'details': approval.change_summary
            })
            
            if approval.approved_at:
                timeline.append({
                    'approval_id': str(approval.id),
                    'event_type': approval.approval_status,
                    'timestamp': approval.approved_at.isoformat(),
                    'user_id': str(approval.approved_by_id) if approval.approved_by_id else None,
                    'details': approval.rejection_reason if approval.approval_status == 'rejected' else None
                })
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x['timestamp'])
        
        return timeline
    
    # ============================================================
    # Helper Methods
    # ============================================================
    
    def _get_approval(self, approval_id: UUID) -> FeeApproval:
        """Get approval record or raise not found."""
        approval = self.session.query(FeeApproval).filter(
            FeeApproval.id == approval_id
        ).first()
        
        if not approval:
            raise NotFoundException(f"Approval {approval_id} not found")
        
        return approval
    
    def _get_pending_approvals(self, fee_structure_id: UUID) -> List[FeeApproval]:
        """Get pending approvals for a fee structure."""
        return self.session.query(FeeApproval).filter(
            FeeApproval.fee_structure_id == fee_structure_id,
            FeeApproval.approval_status == 'pending'
        ).all()
    
    def _get_previous_amount(self, fee_structure: FeeStructure) -> Optional[Decimal]:
        """Get previous amount from version history."""
        if fee_structure.version <= 1:
            return None
        
        # Get previous version
        previous = self.session.query(FeeStructure).filter(
            FeeStructure.hostel_id == fee_structure.hostel_id,
            FeeStructure.room_type == fee_structure.room_type,
            FeeStructure.fee_type == fee_structure.fee_type,
            FeeStructure.version == fee_structure.version - 1
        ).first()
        
        return previous.amount if previous else None
    
    def _validate_approver_authority(
        self,
        approver_id: UUID,
        amount: Decimal
    ) -> None:
        """
        Validate approver has authority for the amount.
        
        This is a simplified implementation. In production, you would
        check user roles, approval limits, etc.
        """
        # TODO: Implement actual authority checking
        # Example: Check if user has role with approval limit >= amount
        pass
    
    def _send_approval_notification(
        self,
        approval: FeeApproval,
        event_type: str
    ) -> None:
        """
        Send notification for approval event.
        
        This is a placeholder. Actual implementation would use
        notification service (email, SMS, push, etc.)
        """
        logger.info(
            f"Notification: Approval {approval.id} - {event_type} "
            f"for fee structure {approval.fee_structure_id}"
        )
        
        # TODO: Implement actual notification sending
        # Example: notification_service.send_email(...)