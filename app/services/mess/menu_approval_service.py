# app/services/mess/menu_approval_service.py
"""
Menu Approval Service

Handles menu approval workflows:
- Submit for approval
- Approve/reject with multi-level workflows
- Track approval history & workflows
- Bulk approval operations

Performance Optimizations:
- Efficient status tracking
- Transaction management
- Audit trail maintenance
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.repositories.mess import MenuApprovalRepository
from app.schemas.mess import (
    MenuApprovalRequest,
    MenuApprovalResponse,
    ApprovalWorkflow,
    ApprovalHistory,
    BulkApproval,
)
from app.core.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)


class MenuApprovalService:
    """
    High-level service for menu approvals.
    
    This service manages:
    - Approval workflow submissions
    - Approval/rejection processing
    - Multi-level approval chains
    - Approval history and audit trails
    """

    def __init__(self, approval_repo: MenuApprovalRepository) -> None:
        """
        Initialize the menu approval service.
        
        Args:
            approval_repo: Repository for approval operations
        """
        self.approval_repo = approval_repo

    # -------------------------------------------------------------------------
    # Submissions
    # -------------------------------------------------------------------------

    def submit_for_approval(
        self,
        db: Session,
        menu_id: UUID,
        request: MenuApprovalRequest,
        requested_by: UUID,
    ) -> MenuApprovalResponse:
        """
        Submit a menu for approval.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            request: Approval request details
            requested_by: User ID submitting the request
            
        Returns:
            MenuApprovalResponse schema
            
        Raises:
            ValidationException: If menu is invalid or already pending
            BusinessLogicException: If menu cannot be submitted
        """
        try:
            # Check if menu already has pending approval
            existing_approval = self.approval_repo.get_current_approval_for_menu(
                db, menu_id
            )
            
            if existing_approval and self._is_pending_status(existing_approval):
                raise BusinessLogicException(
                    f"Menu {menu_id} already has a pending approval request"
                )
            
            # Validate menu is ready for approval
            self._validate_menu_for_approval(db, menu_id)
            
            payload = request.model_dump(exclude_none=True, exclude_unset=True)
            payload.update({
                "menu_id": menu_id,
                "requested_by": requested_by,
                "submitted_at": datetime.utcnow(),
                "status": "pending",
            })

            obj = self.approval_repo.submit_for_approval(db, payload)
            db.flush()
            
            return MenuApprovalResponse.model_validate(obj)
            
        except (ValidationException, BusinessLogicException):
            raise
        except IntegrityError as e:
            db.rollback()
            raise ValidationException(
                f"Database integrity error during submission: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error submitting menu for approval: {str(e)}"
            )

    def resubmit_for_approval(
        self,
        db: Session,
        menu_id: UUID,
        request: MenuApprovalRequest,
        requested_by: UUID,
    ) -> MenuApprovalResponse:
        """
        Resubmit a previously rejected menu for approval.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            request: Updated approval request details
            requested_by: User ID resubmitting the request
            
        Returns:
            MenuApprovalResponse schema
        """
        try:
            # Get previous approval
            previous_approval = self.approval_repo.get_current_approval_for_menu(
                db, menu_id
            )
            
            if not previous_approval:
                # No previous approval, treat as new submission
                return self.submit_for_approval(db, menu_id, request, requested_by)
            
            if not self._is_rejected_status(previous_approval):
                raise BusinessLogicException(
                    "Can only resubmit rejected menus"
                )
            
            # Archive the old approval
            self.approval_repo.archive_approval(db, previous_approval)
            
            # Create new submission
            return self.submit_for_approval(db, menu_id, request, requested_by)
            
        except (ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error resubmitting menu for approval: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Approve / Reject
    # -------------------------------------------------------------------------

    def approve_menu(
        self,
        db: Session,
        menu_id: UUID,
        approver_id: UUID,
        notes: Optional[str] = None,
        approval_level: Optional[int] = None,
    ) -> MenuApprovalResponse:
        """
        Approve a menu.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            approver_id: User ID approving the menu
            notes: Optional approval notes
            approval_level: Optional approval level for multi-stage approvals
            
        Returns:
            Updated MenuApprovalResponse schema
            
        Raises:
            NotFoundException: If no pending approval exists
            ValidationException: If approval is invalid
            BusinessLogicException: If approver is unauthorized
        """
        try:
            approval = self.approval_repo.get_current_approval_for_menu(db, menu_id)
            
            if not approval:
                raise NotFoundException(
                    f"No approval request found for menu {menu_id}"
                )
            
            if not self._is_pending_status(approval):
                raise BusinessLogicException(
                    f"Menu is not in pending status (current: {approval.status})"
                )
            
            # Verify approver has permission
            self._validate_approver_permission(db, approver_id, approval, approval_level)
            
            # Check if this is multi-level approval
            if self._requires_multi_level_approval(approval):
                return self._process_multi_level_approval(
                    db, approval, approver_id, notes, approval_level
                )
            
            # Single-level approval
            obj = self.approval_repo.approve(
                db,
                approval=approval,
                approver_id=approver_id,
                notes=notes,
                approved_at=datetime.utcnow(),
            )
            db.flush()
            
            # Trigger post-approval actions
            self._trigger_post_approval_actions(db, menu_id, obj)
            
            return MenuApprovalResponse.model_validate(obj)
            
        except (NotFoundException, ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error approving menu {menu_id}: {str(e)}"
            )

    def reject_menu(
        self,
        db: Session,
        menu_id: UUID,
        approver_id: UUID,
        reason: str,
        rejection_level: Optional[int] = None,
    ) -> MenuApprovalResponse:
        """
        Reject a menu approval request.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            approver_id: User ID rejecting the menu
            reason: Mandatory rejection reason
            rejection_level: Optional rejection level for multi-stage approvals
            
        Returns:
            Updated MenuApprovalResponse schema
            
        Raises:
            NotFoundException: If no pending approval exists
            ValidationException: If rejection is invalid
        """
        try:
            if not reason or not reason.strip():
                raise ValidationException("Rejection reason is required")
            
            approval = self.approval_repo.get_current_approval_for_menu(db, menu_id)
            
            if not approval:
                raise NotFoundException(
                    f"No approval request found for menu {menu_id}"
                )
            
            if not self._is_pending_status(approval):
                raise BusinessLogicException(
                    f"Menu is not in pending status (current: {approval.status})"
                )
            
            # Verify approver has permission
            self._validate_approver_permission(db, approver_id, approval, rejection_level)

            obj = self.approval_repo.reject(
                db,
                approval=approval,
                approver_id=approver_id,
                reason=reason,
                rejected_at=datetime.utcnow(),
            )
            db.flush()
            
            # Trigger post-rejection actions
            self._trigger_post_rejection_actions(db, menu_id, obj, reason)
            
            return MenuApprovalResponse.model_validate(obj)
            
        except (NotFoundException, ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error rejecting menu {menu_id}: {str(e)}"
            )

    def bulk_approve(
        self,
        db: Session,
        request: BulkApproval,
        approver_id: UUID,
    ) -> List[MenuApprovalResponse]:
        """
        Approve multiple menus in a single operation.
        
        Args:
            db: Database session
            request: Bulk approval request with menu IDs
            approver_id: User ID approving the menus
            
        Returns:
            List of MenuApprovalResponse schemas
            
        Note:
            If skip_failed is True, continues processing on errors
        """
        responses: List[MenuApprovalResponse] = []
        failed_menus: List[Dict[str, Any]] = []

        try:
            for menu_id in request.menu_ids:
                try:
                    resp = self.approve_menu(
                        db, menu_id, approver_id, request.notes
                    )
                    responses.append(resp)
                    
                except (ValidationException, BusinessLogicException, NotFoundException) as e:
                    failed_menus.append({
                        "menu_id": str(menu_id),
                        "error": str(e),
                    })
                    
                    if not request.skip_failed:
                        db.rollback()
                        raise
            
            # Log failed menus if any
            if failed_menus and request.skip_failed:
                self._log_bulk_approval_failures(db, failed_menus, approver_id)
            
            return responses
            
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error in bulk approval: {str(e)}"
            )

    def bulk_reject(
        self,
        db: Session,
        menu_ids: List[UUID],
        approver_id: UUID,
        reason: str,
        skip_failed: bool = False,
    ) -> List[MenuApprovalResponse]:
        """
        Reject multiple menus in a single operation.
        
        Args:
            db: Database session
            menu_ids: List of menu IDs to reject
            approver_id: User ID rejecting the menus
            reason: Rejection reason
            skip_failed: If True, continue on errors
            
        Returns:
            List of MenuApprovalResponse schemas
        """
        responses: List[MenuApprovalResponse] = []
        failed_menus: List[Dict[str, Any]] = []

        try:
            for menu_id in menu_ids:
                try:
                    resp = self.reject_menu(db, menu_id, approver_id, reason)
                    responses.append(resp)
                    
                except (ValidationException, BusinessLogicException, NotFoundException) as e:
                    failed_menus.append({
                        "menu_id": str(menu_id),
                        "error": str(e),
                    })
                    
                    if not skip_failed:
                        db.rollback()
                        raise
            
            if failed_menus and skip_failed:
                self._log_bulk_rejection_failures(db, failed_menus, approver_id)
            
            return responses
            
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error in bulk rejection: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Workflow & History
    # -------------------------------------------------------------------------

    def get_workflow_for_menu(
        self,
        db: Session,
        menu_id: UUID,
    ) -> ApprovalWorkflow:
        """
        Get the current approval workflow for a menu.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            
        Returns:
            ApprovalWorkflow schema
            
        Raises:
            NotFoundException: If workflow not found
        """
        try:
            data = self.approval_repo.get_workflow_for_menu(db, menu_id)
            
            if not data:
                raise NotFoundException(
                    f"Approval workflow not found for menu {menu_id}"
                )
            
            return ApprovalWorkflow.model_validate(data)
            
        except NotFoundException:
            raise
        except Exception as e:
            raise ValidationException(
                f"Error retrieving workflow for menu {menu_id}: {str(e)}"
            )

    def get_approval_history_for_menu(
        self,
        db: Session,
        menu_id: UUID,
        limit: Optional[int] = None,
    ) -> List[ApprovalHistory]:
        """
        Get the complete approval history for a menu.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            limit: Optional limit on number of records
            
        Returns:
            List of ApprovalHistory schemas
        """
        try:
            objs = self.approval_repo.get_history_for_menu(db, menu_id, limit)
            return [ApprovalHistory.model_validate(o) for o in objs]
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving approval history for menu {menu_id}: {str(e)}"
            )

    def get_pending_approvals_for_user(
        self,
        db: Session,
        approver_id: UUID,
        hostel_id: Optional[UUID] = None,
    ) -> List[MenuApprovalResponse]:
        """
        Get all pending approvals assigned to a user.
        
        Args:
            db: Database session
            approver_id: User ID of the approver
            hostel_id: Optional filter by hostel
            
        Returns:
            List of pending MenuApprovalResponse schemas
        """
        try:
            objs = self.approval_repo.get_pending_for_approver(
                db, approver_id, hostel_id
            )
            return [MenuApprovalResponse.model_validate(o) for o in objs]
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving pending approvals for user {approver_id}: {str(e)}"
            )

    def get_approval_statistics(
        self,
        db: Session,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get approval statistics for a hostel.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            
        Returns:
            Dictionary containing approval statistics
        """
        try:
            stats = self.approval_repo.get_statistics(
                db, hostel_id, start_date, end_date
            )
            
            return {
                "total_submissions": stats.get("total_submissions", 0),
                "total_approved": stats.get("total_approved", 0),
                "total_rejected": stats.get("total_rejected", 0),
                "total_pending": stats.get("total_pending", 0),
                "approval_rate": stats.get("approval_rate", 0.0),
                "average_approval_time_hours": stats.get("avg_approval_time", 0.0),
                "pending_by_level": stats.get("pending_by_level", {}),
            }
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving approval statistics: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Validation & Helper Methods
    # -------------------------------------------------------------------------

    def _validate_menu_for_approval(self, db: Session, menu_id: UUID) -> None:
        """
        Validate that a menu is ready for approval submission.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            
        Raises:
            ValidationException: If menu is invalid
        """
        # This should check:
        # - Menu exists
        # - Menu has required items
        # - Menu date is valid
        # - Nutritional info is complete (if required)
        pass

    def _validate_approver_permission(
        self,
        db: Session,
        approver_id: UUID,
        approval: Any,
        level: Optional[int] = None,
    ) -> None:
        """
        Validate that an approver has permission to approve/reject.
        
        Args:
            db: Database session
            approver_id: User ID of the approver
            approval: Approval object
            level: Optional approval level
            
        Raises:
            BusinessLogicException: If approver lacks permission
        """
        # Implement actual permission checking logic
        # This is a placeholder
        pass

    def _is_pending_status(self, approval: Any) -> bool:
        """Check if approval is in pending status."""
        return getattr(approval, 'status', '').lower() == 'pending'

    def _is_rejected_status(self, approval: Any) -> bool:
        """Check if approval is in rejected status."""
        return getattr(approval, 'status', '').lower() == 'rejected'

    def _requires_multi_level_approval(self, approval: Any) -> bool:
        """Check if approval requires multiple levels."""
        return getattr(approval, 'requires_multi_level', False)

    def _process_multi_level_approval(
        self,
        db: Session,
        approval: Any,
        approver_id: UUID,
        notes: Optional[str],
        level: Optional[int],
    ) -> MenuApprovalResponse:
        """
        Process multi-level approval workflow.
        
        This handles scenarios where multiple approvers are required.
        """
        # Implement multi-level approval logic
        # For now, delegate to repository
        obj = self.approval_repo.approve_level(
            db, approval, approver_id, notes, level
        )
        db.flush()
        return MenuApprovalResponse.model_validate(obj)

    def _trigger_post_approval_actions(
        self,
        db: Session,
        menu_id: UUID,
        approval: Any,
    ) -> None:
        """
        Trigger actions after successful approval.
        
        This could include:
        - Publishing the menu
        - Sending notifications
        - Updating inventory
        """
        # Implement post-approval hooks
        pass

    def _trigger_post_rejection_actions(
        self,
        db: Session,
        menu_id: UUID,
        approval: Any,
        reason: str,
    ) -> None:
        """
        Trigger actions after rejection.
        
        This could include:
        - Notifying the submitter
        - Logging the rejection
        """
        # Implement post-rejection hooks
        pass

    def _log_bulk_approval_failures(
        self,
        db: Session,
        failures: List[Dict[str, Any]],
        approver_id: UUID,
    ) -> None:
        """Log failures from bulk approval operations."""
        # Implement failure logging
        pass

    def _log_bulk_rejection_failures(
        self,
        db: Session,
        failures: List[Dict[str, Any]],
        approver_id: UUID,
    ) -> None:
        """Log failures from bulk rejection operations."""
        # Implement failure logging
        pass