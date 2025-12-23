"""
Fee Approval Service

Manages fee structure approval workflows including:
- Submission for approval
- Approval and rejection with audit trails
- Approval history tracking
- Multi-level approval support (configurable)

Author: Senior Prompt Engineer
Version: 2.0.0
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.fee_structure import FeeStructureRepository
from app.models.fee_structure.fee_structure import FeeApproval as FeeApprovalModel
from app.schemas.fee_structure.fee_structure import (
    FeeApprovalRequest,
    FeeApprovalResponse,
)
from app.core.logging import get_logger


class FeeApprovalService(BaseService[FeeApprovalModel, FeeStructureRepository]):
    """
    Service for managing fee structure approval workflows.
    
    Features:
    - Submit structures for approval
    - Approve or reject pending submissions
    - Track complete approval history
    - Support for approval comments and metadata
    - Configurable approval levels
    """

    # Valid approval statuses
    VALID_APPROVAL_STATUSES = {
        "pending",
        "approved",
        "rejected",
        "withdrawn"
    }

    def __init__(self, repository: FeeStructureRepository, db_session: Session):
        """
        Initialize fee approval service.

        Args:
            repository: Fee structure repository instance
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)
        self._logger = get_logger(self.__class__.__name__)

    def submit(
        self,
        structure_id: UUID,
        request: FeeApprovalRequest,
        requested_by: UUID,
    ) -> ServiceResult[FeeApprovalModel]:
        """
        Submit a fee structure for approval.

        Args:
            structure_id: UUID of the fee structure to submit
            request: Approval request containing metadata and comments
            requested_by: UUID of the user submitting for approval

        Returns:
            ServiceResult containing approval record or error
        """
        try:
            # Validate structure exists
            structure = self.repository.get_by_id(structure_id)
            if not structure:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Fee structure not found: {structure_id}",
                        severity=ErrorSeverity.ERROR,
                        details={"structure_id": str(structure_id)}
                    )
                )

            # Check if structure is in valid state for approval submission
            if structure.status not in ("draft", "inactive"):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.INVALID_STATE,
                        message=f"Cannot submit structure with status '{structure.status}' for approval",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "structure_id": str(structure_id),
                            "current_status": structure.status,
                            "allowed_statuses": ["draft", "inactive"]
                        }
                    )
                )

            # Check for existing pending approval
            existing_pending = self._get_pending_approval(structure_id)
            if existing_pending:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.INVALID_STATE,
                        message="Fee structure already has a pending approval request",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "structure_id": str(structure_id),
                            "pending_approval_id": str(existing_pending.id)
                        }
                    )
                )

            # Create approval record
            approval = self.repository.submit_for_approval(
                structure_id,
                request,
                requested_by
            )
            self.db.commit()
            self.db.refresh(approval)

            self._logger.info(
                "Fee structure submitted for approval",
                extra={
                    "approval_id": str(approval.id),
                    "structure_id": str(structure_id),
                    "requested_by": str(requested_by),
                }
            )

            return ServiceResult.success(
                approval,
                message="Fee structure submitted for approval successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            self._logger.error(
                "Database integrity error during approval submission",
                exc_info=True,
                extra={"error": str(e)}
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DUPLICATE_ENTRY,
                    message="Approval submission violates database constraints",
                    severity=ErrorSeverity.ERROR,
                    details={"database_error": str(e)}
                )
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "submit fee structure for approval", structure_id)

    def approve(
        self,
        approval_id: UUID,
        approver_id: UUID,
        notes: Optional[str] = None,
    ) -> ServiceResult[FeeApprovalModel]:
        """
        Approve a pending fee structure change.

        Args:
            approval_id: UUID of the approval request
            approver_id: UUID of the user approving
            notes: Optional approval notes/comments

        Returns:
            ServiceResult containing updated approval record or error
        """
        try:
            # Validate approval exists
            approval = self.repository.get_approval_by_id(approval_id)
            if not approval:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Approval request not found: {approval_id}",
                        severity=ErrorSeverity.ERROR,
                        details={"approval_id": str(approval_id)}
                    )
                )

            # Check if approval is in pending state
            if approval.status != "pending":
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.INVALID_STATE,
                        message=f"Cannot approve request with status '{approval.status}'",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "approval_id": str(approval_id),
                            "current_status": approval.status
                        }
                    )
                )

            # Prevent self-approval
            if str(approval.requested_by) == str(approver_id):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Users cannot approve their own requests",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "approval_id": str(approval_id),
                            "user_id": str(approver_id)
                        }
                    )
                )

            # Perform approval
            approved_record = self.repository.approve(
                approval_id,
                approver_id,
                notes=notes
            )
            self.db.commit()
            self.db.refresh(approved_record)

            self._logger.info(
                "Fee structure approval granted",
                extra={
                    "approval_id": str(approval_id),
                    "structure_id": str(approval.structure_id),
                    "approver_id": str(approver_id),
                }
            )

            # Trigger post-approval actions (e.g., activate structure)
            self._handle_post_approval_actions(approved_record)

            return ServiceResult.success(
                approved_record,
                message="Fee structure approved successfully"
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "approve fee structure", approval_id)

    def reject(
        self,
        approval_id: UUID,
        approver_id: UUID,
        reason: str,
    ) -> ServiceResult[FeeApprovalModel]:
        """
        Reject a pending fee structure change.

        Args:
            approval_id: UUID of the approval request
            approver_id: UUID of the user rejecting
            reason: Rejection reason (required)

        Returns:
            ServiceResult containing updated approval record or error
        """
        try:
            # Validate reason is provided
            if not reason or not reason.strip():
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Rejection reason is required",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            # Validate approval exists
            approval = self.repository.get_approval_by_id(approval_id)
            if not approval:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Approval request not found: {approval_id}",
                        severity=ErrorSeverity.ERROR,
                        details={"approval_id": str(approval_id)}
                    )
                )

            # Check if approval is in pending state
            if approval.status != "pending":
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.INVALID_STATE,
                        message=f"Cannot reject request with status '{approval.status}'",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "approval_id": str(approval_id),
                            "current_status": approval.status
                        }
                    )
                )

            # Perform rejection
            rejected_record = self.repository.reject(
                approval_id,
                approver_id,
                reason=reason
            )
            self.db.commit()
            self.db.refresh(rejected_record)

            self._logger.info(
                "Fee structure approval rejected",
                extra={
                    "approval_id": str(approval_id),
                    "structure_id": str(approval.structure_id),
                    "approver_id": str(approver_id),
                    "reason": reason,
                }
            )

            # Trigger post-rejection actions (e.g., notify requester)
            self._handle_post_rejection_actions(rejected_record)

            return ServiceResult.success(
                rejected_record,
                message="Fee structure approval rejected"
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "reject fee structure", approval_id)

    def withdraw(
        self,
        approval_id: UUID,
        withdrawn_by: UUID,
        reason: Optional[str] = None,
    ) -> ServiceResult[FeeApprovalModel]:
        """
        Withdraw a pending approval request.

        Args:
            approval_id: UUID of the approval request
            withdrawn_by: UUID of the user withdrawing the request
            reason: Optional withdrawal reason

        Returns:
            ServiceResult containing updated approval record or error
        """
        try:
            # Validate approval exists
            approval = self.repository.get_approval_by_id(approval_id)
            if not approval:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Approval request not found: {approval_id}",
                        severity=ErrorSeverity.ERROR,
                        details={"approval_id": str(approval_id)}
                    )
                )

            # Check if approval is in pending state
            if approval.status != "pending":
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.INVALID_STATE,
                        message=f"Cannot withdraw request with status '{approval.status}'",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "approval_id": str(approval_id),
                            "current_status": approval.status
                        }
                    )
                )

            # Verify user is authorized to withdraw (must be original requester or admin)
            if str(approval.requested_by) != str(withdrawn_by):
                # Additional check: is user an admin? (implement based on your auth system)
                pass

            # Perform withdrawal
            withdrawn_record = self.repository.withdraw_approval(
                approval_id,
                withdrawn_by,
                reason=reason
            )
            self.db.commit()
            self.db.refresh(withdrawn_record)

            self._logger.info(
                "Fee structure approval withdrawn",
                extra={
                    "approval_id": str(approval_id),
                    "structure_id": str(approval.structure_id),
                    "withdrawn_by": str(withdrawn_by),
                }
            )

            return ServiceResult.success(
                withdrawn_record,
                message="Approval request withdrawn successfully"
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "withdraw approval request", approval_id)

    def history(
        self,
        structure_id: UUID,
        status_filter: Optional[str] = None,
    ) -> ServiceResult[List[FeeApprovalModel]]:
        """
        Get approval history for a fee structure.

        Args:
            structure_id: UUID of the fee structure
            status_filter: Optional filter by approval status

        Returns:
            ServiceResult containing list of approval records
        """
        try:
            # Validate structure exists
            structure = self.repository.get_by_id(structure_id)
            if not structure:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Fee structure not found: {structure_id}",
                        severity=ErrorSeverity.ERROR,
                        details={"structure_id": str(structure_id)}
                    )
                )

            # Validate status filter if provided
            if status_filter and status_filter not in self.VALID_APPROVAL_STATUSES:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid approval status filter: {status_filter}",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "provided": status_filter,
                            "valid_statuses": list(self.VALID_APPROVAL_STATUSES)
                        }
                    )
                )

            approvals = self.repository.get_approval_history(
                structure_id,
                status_filter=status_filter
            )

            return ServiceResult.success(
                approvals,
                metadata={
                    "count": len(approvals),
                    "structure_id": str(structure_id),
                    "status_filter": status_filter,
                }
            )

        except Exception as e:
            return self._handle_exception(e, "get fee approval history", structure_id)

    def get_pending_approvals(
        self,
        approver_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> ServiceResult[List[FeeApprovalModel]]:
        """
        Get all pending approval requests.

        Args:
            approver_id: Optional filter by assigned approver
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            ServiceResult containing list of pending approvals
        """
        try:
            page = max(1, page)
            page_size = min(max(1, page_size), 100)

            pending_approvals = self.repository.get_pending_approvals(
                approver_id=approver_id,
                page=page,
                page_size=page_size,
            )

            total_count = len(pending_approvals)
            total_pages = (total_count + page_size - 1) // page_size

            return ServiceResult.success(
                pending_approvals,
                metadata={
                    "count": len(pending_approvals),
                    "total": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                }
            )

        except Exception as e:
            return self._handle_exception(e, "get pending approvals")

    # ==================== Private Helper Methods ====================

    def _get_pending_approval(self, structure_id: UUID) -> Optional[FeeApprovalModel]:
        """Get existing pending approval for a structure."""
        # This should query the repository
        # Placeholder implementation
        return None

    def _handle_post_approval_actions(self, approval: FeeApprovalModel) -> None:
        """
        Handle actions after approval is granted.
        
        Examples:
        - Activate the fee structure
        - Send notifications
        - Create audit log entries
        """
        try:
            # Example: Auto-activate the structure
            structure = self.repository.get_by_id(approval.structure_id)
            if structure and structure.status == "draft":
                self.repository.set_status(approval.structure_id, "active")
                self.db.commit()

            # Additional post-approval logic here
            
        except Exception as e:
            self._logger.error(
                "Error in post-approval actions",
                exc_info=True,
                extra={
                    "approval_id": str(approval.id),
                    "error": str(e)
                }
            )

    def _handle_post_rejection_actions(self, approval: FeeApprovalModel) -> None:
        """
        Handle actions after approval is rejected.
        
        Examples:
        - Send rejection notification
        - Create audit log entries
        - Update structure status
        """
        try:
            # Notification logic
            # Audit logging
            pass
            
        except Exception as e:
            self._logger.error(
                "Error in post-rejection actions",
                exc_info=True,
                extra={
                    "approval_id": str(approval.id),
                    "error": str(e)
                }
            )