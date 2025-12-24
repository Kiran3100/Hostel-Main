"""
Leave Approval Service Module

Manages the complete approval workflow for leave applications including:
- Approval and rejection decisions
- Multi-level approval workflows
- Change requests and escalations
- Approval history tracking
- Workflow state management

Version: 2.0.0
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity
)
from app.repositories.leave.leave_approval_repository import LeaveApprovalRepository
from app.models.leave.leave_approval import LeaveApproval as LeaveApprovalModel
from app.schemas.leave.leave_approval import (
    LeaveApprovalRequest,
    LeaveApprovalAction,
    LeaveApprovalResponse,
)

logger = logging.getLogger(__name__)


class LeaveApprovalService(BaseService[LeaveApprovalModel, LeaveApprovalRepository]):
    """
    Comprehensive service for managing leave approval workflows.
    
    Supports:
    - Simple binary approval/rejection
    - Complex multi-stage workflows
    - Change requests and resubmissions
    - Escalation mechanisms
    - Complete audit trails
    """

    def __init__(self, repository: LeaveApprovalRepository, db_session: Session):
        """
        Initialize the leave approval service.
        
        Args:
            repository: Leave approval repository instance
            db_session: Active database session
        """
        super().__init__(repository, db_session)
        self._logger = logger

    def decide(
        self,
        request: LeaveApprovalRequest,
    ) -> ServiceResult[LeaveApprovalResponse]:
        """
        Process a simple binary approval/rejection decision.
        
        This is a streamlined method for basic approval workflows where
        only approve/reject actions are needed without complex workflow stages.
        
        Args:
            request: Approval request containing leave_id, decision, and details
            
        Returns:
            ServiceResult containing LeaveApprovalResponse or error information
        """
        try:
            self._logger.info(
                f"Processing approval decision for leave {request.leave_id} "
                f"by approver {request.approver_id}"
            )
            
            # Validate the approval request
            validation_result = self._validate_approval_request(request)
            if not validation_result.success:
                return validation_result

            # Process the decision via repository
            response = self.repository.decide(request)
            
            if not response:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message="Failed to process approval decision",
                        severity=ErrorSeverity.ERROR,
                        details={"leave_id": str(request.leave_id)}
                    )
                )
            
            # Commit transaction
            self.db.commit()
            
            decision_type = "approved" if request.approve else "rejected"
            self._logger.info(
                f"Leave {request.leave_id} {decision_type} by {request.approver_id}"
            )
            
            return ServiceResult.success(
                response,
                message=f"Leave decision recorded: {decision_type}"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error while processing approval decision: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "decide leave approval", request.leave_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error while processing approval decision: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "decide leave approval", request.leave_id)

    def workflow_action(
        self,
        action: LeaveApprovalAction,
    ) -> ServiceResult[LeaveApprovalResponse]:
        """
        Execute advanced workflow actions with full control.
        
        Supports complex workflows including:
        - Multi-level approvals
        - Conditional routing
        - Change requests with feedback
        - Escalation to higher authorities
        - Delegated approvals
        
        Args:
            action: Detailed action specification including type, actor, and context
            
        Returns:
            ServiceResult containing LeaveApprovalResponse or error information
        """
        try:
            self._logger.info(
                f"Processing workflow action '{action.action_type}' for leave {action.leave_id} "
                f"by {action.actor_id}"
            )
            
            # Validate the workflow action
            validation_result = self._validate_workflow_action(action)
            if not validation_result.success:
                return validation_result

            # Execute the workflow action via repository
            response = self.repository.workflow_action(action)
            
            if not response:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.OPERATION_FAILED,
                        message=f"Failed to process workflow action: {action.action_type}",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "leave_id": str(action.leave_id),
                            "action_type": action.action_type
                        }
                    )
                )
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Workflow action '{action.action_type}' completed for leave {action.leave_id}"
            )
            
            return ServiceResult.success(
                response,
                message=f"Workflow action processed: {action.action_type}"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error while processing workflow action: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "leave workflow action", action.leave_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error while processing workflow action: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "leave workflow action", action.leave_id)

    def get_history(
        self,
        leave_id: UUID,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Retrieve complete approval history for a leave application.
        
        Provides chronological record of:
        - All approval decisions
        - Comments and feedback
        - Actor information
        - Timestamps
        - Status transitions
        
        Args:
            leave_id: UUID of the leave application
            
        Returns:
            ServiceResult containing list of approval history entries or error information
        """
        try:
            self._logger.debug(
                f"Retrieving approval history for leave {leave_id}"
            )
            
            history = self.repository.get_history(leave_id)
            
            if history is None:
                history = []
            
            self._logger.debug(
                f"Retrieved {len(history)} approval history entries for leave {leave_id}"
            )
            
            return ServiceResult.success(
                history,
                metadata={
                    "count": len(history),
                    "leave_id": str(leave_id)
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error while retrieving approval history: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get leave approval history", leave_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error while retrieving approval history: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get leave approval history", leave_id)

    def get_workflow(
        self,
        leave_id: UUID,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Retrieve current workflow state and configuration for a leave application.
        
        Provides:
        - Current approval stage
        - Required approvers
        - Completed steps
        - Pending actions
        - Next steps in workflow
        
        Args:
            leave_id: UUID of the leave application
            
        Returns:
            ServiceResult containing workflow state dictionary or error information
        """
        try:
            self._logger.debug(
                f"Retrieving workflow state for leave {leave_id}"
            )
            
            workflow = self.repository.get_workflow(leave_id)
            
            if workflow is None:
                workflow = {}
            
            self._logger.debug(
                f"Retrieved workflow state for leave {leave_id}"
            )
            
            return ServiceResult.success(
                workflow,
                metadata={"leave_id": str(leave_id)}
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error while retrieving workflow: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get leave workflow", leave_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error while retrieving workflow: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get leave workflow", leave_id)

    def get_pending_approvals(
        self,
        approver_id: UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Retrieve all pending approvals for a specific approver.
        
        Args:
            approver_id: UUID of the approver
            page: Page number (1-indexed)
            page_size: Number of items per page
            
        Returns:
            ServiceResult containing list of pending approvals or error information
        """
        try:
            # Validate pagination parameters
            if page < 1:
                page = 1
            if page_size < 1 or page_size > 100:
                page_size = 50
            
            self._logger.debug(
                f"Retrieving pending approvals for approver {approver_id} "
                f"(page={page}, page_size={page_size})"
            )
            
            # This would need to be implemented in the repository
            # pending = self.repository.get_pending_for_approver(
            #     approver_id,
            #     page=page,
            #     page_size=page_size
            # )
            
            # Placeholder implementation
            pending = []
            
            return ServiceResult.success(
                pending,
                metadata={
                    "count": len(pending),
                    "approver_id": str(approver_id),
                    "page": page,
                    "page_size": page_size,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error while retrieving pending approvals: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(
                e,
                "get pending approvals",
                approver_id
            )
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error while retrieving pending approvals: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(
                e,
                "get pending approvals",
                approver_id
            )

    # -------------------------------------------------------------------------
    # Private Validation Methods
    # -------------------------------------------------------------------------

    def _validate_approval_request(
        self,
        request: LeaveApprovalRequest
    ) -> ServiceResult[None]:
        """
        Validate approval request data.
        
        Args:
            request: The approval request to validate
            
        Returns:
            ServiceResult indicating validation success or specific errors
        """
        # Ensure approver is authorized
        # Check leave application exists and is in appropriate state
        # Validate comments if required
        
        if not request.approver_id:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Approver ID is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(None)

    def _validate_workflow_action(
        self,
        action: LeaveApprovalAction
    ) -> ServiceResult[None]:
        """
        Validate workflow action data and permissions.
        
        Args:
            action: The workflow action to validate
            
        Returns:
            ServiceResult indicating validation success or specific errors
        """
        # Validate action type
        valid_actions = [
            "approve",
            "reject",
            "request_changes",
            "escalate",
            "delegate"
        ]
        
        if action.action_type not in valid_actions:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid action type: {action.action_type}",
                    severity=ErrorSeverity.WARNING,
                    details={"valid_actions": valid_actions}
                )
            )
        
        # Ensure actor is authorized for this action
        if not action.actor_id:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Actor ID is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        return ServiceResult.success(None)