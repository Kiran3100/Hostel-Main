"""
Maintenance Approval Service

Manages the approval workflow for maintenance requests with multi-level
approval support, threshold-based routing, and comprehensive audit trails.

Features:
- Multi-level approval workflows
- Dynamic threshold-based routing
- Approval/rejection with detailed reasons
- Workflow state management
- Integration with notification system
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceApprovalRepository
from app.schemas.maintenance import (
    ApprovalRequest,
    ApprovalResponse,
    ThresholdConfig,
    ApprovalWorkflow,
    RejectionRequest,
)
from app.core.exceptions import ValidationException, BusinessLogicException
from app.core.logging import logger
from app.services.workflows import ApprovalWorkflowService


class MaintenanceApprovalService:
    """
    High-level orchestration for maintenance approval workflows.

    Integrates with:
    - MaintenanceApprovalRepository for persistence and queries
    - ApprovalWorkflowService for multi-step workflow execution
    """

    def __init__(
        self,
        approval_repo: MaintenanceApprovalRepository,
        approval_workflow: ApprovalWorkflowService,
    ) -> None:
        """
        Initialize the approval service with required dependencies.

        Args:
            approval_repo: Repository for approval data access
            approval_workflow: Service for workflow orchestration
        """
        if not approval_repo:
            raise ValueError("MaintenanceApprovalRepository is required")
        if not approval_workflow:
            raise ValueError("ApprovalWorkflowService is required")
            
        self.approval_repo = approval_repo
        self.approval_workflow = approval_workflow

    # -------------------------------------------------------------------------
    # Approval Operations
    # -------------------------------------------------------------------------

    async def approve_maintenance_request(
        self,
        db: Session,
        approval_id: UUID,
        approved_by: UUID,
        approved_amount: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> ApprovalResponse:
        """
        Approve a maintenance request at the current approval level.

        The approval may trigger the next approval level or complete the workflow
        depending on the threshold configuration.

        Args:
            db: Database session
            approval_id: UUID of the approval record
            approved_by: UUID of the user approving
            approved_amount: Optional approved amount (may differ from requested)
            notes: Optional approval notes

        Returns:
            ApprovalResponse with updated approval state

        Raises:
            ValidationException: If approval record not found or invalid
            BusinessLogicException: If approval workflow fails
        """
        # Validate inputs
        if not approval_id:
            raise ValidationException("Approval ID is required")
        if not approved_by:
            raise ValidationException("Approver ID is required")
        
        # Validate approved amount if provided
        if approved_amount is not None and approved_amount < 0:
            raise ValidationException("Approved amount cannot be negative")

        try:
            logger.info(
                f"Processing approval {approval_id} by user {approved_by}"
            )
            
            # Execute approval through workflow service
            result = await self.approval_workflow.approve_maintenance(
                db=db,
                approval_id=approval_id,
                approved_by=approved_by,
                approved_amount=approved_amount,
                notes=notes,
            )

            if not result:
                raise BusinessLogicException(
                    "Approval workflow did not return a result"
                )

            logger.info(f"Approval {approval_id} processed successfully")
            
            # TODO: Trigger notification to requester
            # await self._notify_approval_status(result)
            
            return ApprovalResponse.model_validate(result)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error approving request {approval_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to approve maintenance request: {str(e)}"
            )

    async def reject_maintenance_request(
        self,
        db: Session,
        approval_id: UUID,
        rejected_by: UUID,
        reason: str,
    ) -> ApprovalResponse:
        """
        Reject a maintenance approval request.

        Rejection terminates the approval workflow and updates the
        maintenance request status accordingly.

        Args:
            db: Database session
            approval_id: UUID of the approval record
            rejected_by: UUID of the user rejecting
            reason: Reason for rejection (required)

        Returns:
            ApprovalResponse with rejection details

        Raises:
            ValidationException: If approval not found or invalid
            BusinessLogicException: If rejection fails
        """
        # Validate inputs
        if not approval_id:
            raise ValidationException("Approval ID is required")
        if not rejected_by:
            raise ValidationException("Rejector ID is required")
        if not reason or len(reason.strip()) < 10:
            raise ValidationException(
                "Rejection reason must be at least 10 characters"
            )

        try:
            logger.info(
                f"Processing rejection of approval {approval_id} by user {rejected_by}"
            )
            
            # Retrieve approval record
            approval = self.approval_repo.get_by_id(db, approval_id)
            if not approval:
                raise ValidationException(
                    f"Approval record {approval_id} not found"
                )

            # Check if already processed
            if approval.status in ["approved", "rejected"]:
                raise BusinessLogicException(
                    f"Approval already {approval.status}, cannot reject"
                )

            # Execute rejection
            updated = self.approval_repo.reject(
                db=db,
                approval=approval,
                rejected_by=rejected_by,
                reason=reason.strip(),
            )

            logger.info(f"Approval {approval_id} rejected successfully")
            
            # TODO: Trigger notification to requester
            # await self._notify_rejection(updated, reason)
            
            return ApprovalResponse.model_validate(updated)

        except (ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            logger.error(
                f"Error rejecting approval {approval_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to reject maintenance request: {str(e)}"
            )

    async def delegate_approval(
        self,
        db: Session,
        approval_id: UUID,
        current_approver: UUID,
        delegate_to: UUID,
        reason: str,
    ) -> ApprovalResponse:
        """
        Delegate an approval to another user.

        Args:
            db: Database session
            approval_id: UUID of the approval record
            current_approver: UUID of current approver
            delegate_to: UUID of user to delegate to
            reason: Reason for delegation

        Returns:
            ApprovalResponse with updated approver

        Raises:
            ValidationException: If delegation is invalid
        """
        if not all([approval_id, current_approver, delegate_to, reason]):
            raise ValidationException("All delegation fields are required")

        if current_approver == delegate_to:
            raise ValidationException("Cannot delegate to yourself")

        try:
            approval = self.approval_repo.get_by_id(db, approval_id)
            if not approval:
                raise ValidationException(f"Approval {approval_id} not found")

            # Verify current approver has permission
            if approval.current_approver_id != current_approver:
                raise BusinessLogicException(
                    "Only current approver can delegate"
                )

            updated = self.approval_repo.delegate(
                db=db,
                approval=approval,
                delegate_to=delegate_to,
                reason=reason,
            )

            logger.info(
                f"Approval {approval_id} delegated from "
                f"{current_approver} to {delegate_to}"
            )

            return ApprovalResponse.model_validate(updated)

        except (ValidationException, BusinessLogicException):
            raise
        except Exception as e:
            logger.error(
                f"Error delegating approval {approval_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(f"Failed to delegate approval: {str(e)}")

    # -------------------------------------------------------------------------
    # Threshold and Workflow Configuration
    # -------------------------------------------------------------------------

    def get_threshold_config_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> ThresholdConfig:
        """
        Retrieve approval threshold configuration for a hostel.

        The threshold configuration determines which approval levels
        are required based on the maintenance request cost.

        Args:
            db: Database session
            hostel_id: UUID of the hostel

        Returns:
            ThresholdConfig with approval thresholds

        Raises:
            ValidationException: If hostel_id is invalid
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        try:
            cfg = self.approval_repo.get_threshold_config_for_hostel(
                db,
                hostel_id
            )
            
            if not cfg:
                # Return default configuration
                logger.info(
                    f"No threshold config found for hostel {hostel_id}, "
                    "using defaults"
                )
                return ThresholdConfig(
                    hostel_id=hostel_id,
                    approval_required_above_amount=0.0,
                    manager_approval_above_amount=5000.0,
                    senior_manager_approval_above_amount=10000.0,
                    auto_approve_below_amount=1000.0,
                )
            
            return ThresholdConfig.model_validate(cfg)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving threshold config for hostel {hostel_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve threshold configuration: {str(e)}"
            )

    def update_threshold_config(
        self,
        db: Session,
        hostel_id: UUID,
        config: ThresholdConfig,
    ) -> ThresholdConfig:
        """
        Update approval threshold configuration for a hostel.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            config: New threshold configuration

        Returns:
            Updated ThresholdConfig

        Raises:
            ValidationException: If configuration is invalid
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        # Validate threshold values
        self._validate_threshold_config(config)

        try:
            updated = self.approval_repo.update_threshold_config(
                db=db,
                hostel_id=hostel_id,
                data=config.model_dump(exclude_none=True),
            )

            logger.info(f"Updated threshold config for hostel {hostel_id}")
            return ThresholdConfig.model_validate(updated)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error updating threshold config: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to update threshold configuration: {str(e)}"
            )

    def get_workflow_for_request(
        self,
        db: Session,
        request_id: UUID,
    ) -> ApprovalWorkflow:
        """
        Retrieve the complete approval workflow for a maintenance request.

        Args:
            db: Database session
            request_id: UUID of the maintenance request

        Returns:
            ApprovalWorkflow with all approval levels and their status

        Raises:
            ValidationException: If workflow not found
        """
        if not request_id:
            raise ValidationException("Request ID is required")

        try:
            data = self.approval_repo.get_workflow_for_request(db, request_id)
            if not data:
                raise ValidationException(
                    f"Approval workflow not found for request {request_id}"
                )
            
            return ApprovalWorkflow.model_validate(data)

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error retrieving workflow for request {request_id}: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to retrieve approval workflow: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _validate_threshold_config(self, config: ThresholdConfig) -> None:
        """
        Validate threshold configuration values.

        Args:
            config: Configuration to validate

        Raises:
            ValidationException: If configuration is invalid
        """
        amounts = [
            config.approval_required_above_amount,
            config.manager_approval_above_amount,
            config.senior_manager_approval_above_amount,
            config.auto_approve_below_amount,
        ]

        # Check for negative values
        if any(amt is not None and amt < 0 for amt in amounts):
            raise ValidationException("Threshold amounts cannot be negative")

        # Validate logical ordering
        if (config.auto_approve_below_amount is not None and
            config.approval_required_above_amount is not None and
            config.auto_approve_below_amount >= config.approval_required_above_amount):
            raise ValidationException(
                "Auto-approve threshold must be less than approval required threshold"
            )

        if (config.manager_approval_above_amount is not None and
            config.senior_manager_approval_above_amount is not None and
            config.manager_approval_above_amount >= config.senior_manager_approval_above_amount):
            raise ValidationException(
                "Manager approval threshold must be less than senior manager threshold"
            )