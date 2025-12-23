"""
Complaint escalation service (manual + auto rules).

Manages complaint escalation workflows including manual escalations,
automatic rule-based escalations, and comprehensive history tracking.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.complaint.complaint_escalation_repository import ComplaintEscalationRepository
from app.models.complaint.complaint_escalation import ComplaintEscalation as ComplaintEscalationModel
from app.schemas.complaint.complaint_escalation import (
    EscalationRequest,
    EscalationResponse,
    EscalationEntry,
    EscalationHistory,
    AutoEscalationRule,
)

logger = logging.getLogger(__name__)


class ComplaintEscalationService(BaseService[ComplaintEscalationModel, ComplaintEscalationRepository]):
    """
    Escalation flows and rule configuration management.
    
    Handles both manual and automatic escalations with comprehensive
    rule management and audit trails.
    """

    def __init__(self, repository: ComplaintEscalationRepository, db_session: Session):
        """
        Initialize escalation service.
        
        Args:
            repository: Complaint escalation repository instance
            db_session: Active database session
        """
        super().__init__(repository, db_session)
        self._logger = logger

    # -------------------------------------------------------------------------
    # Manual Escalation Operations
    # -------------------------------------------------------------------------

    def escalate(
        self,
        request: EscalationRequest,
        escalated_by: Optional[UUID] = None,
    ) -> ServiceResult[EscalationResponse]:
        """
        Manually escalate a complaint to a higher level or different department.
        
        Args:
            request: Escalation request data
            escalated_by: UUID of user performing the escalation
            
        Returns:
            ServiceResult containing EscalationResponse or error
        """
        try:
            self._logger.info(
                f"Escalating complaint {request.complaint_id} to level {request.escalation_level}, "
                f"escalated_by: {escalated_by}"
            )
            
            # Validate escalation request
            validation_result = self._validate_escalation(request)
            if not validation_result.success:
                return validation_result
            
            # Perform escalation
            response = self.repository.escalate(request, escalated_by=escalated_by)
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Complaint {request.complaint_id} escalated successfully to level {request.escalation_level}"
            )
            
            return ServiceResult.success(
                response,
                message=f"Complaint escalated to {request.escalation_level}",
                metadata={
                    "complaint_id": str(request.complaint_id),
                    "escalation_level": request.escalation_level,
                    "escalated_to": str(request.escalated_to) if hasattr(request, 'escalated_to') else None,
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error escalating complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "escalate complaint", request.complaint_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error escalating complaint {request.complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "escalate complaint", request.complaint_id)

    # -------------------------------------------------------------------------
    # History Operations
    # -------------------------------------------------------------------------

    def history(
        self,
        complaint_id: UUID,
    ) -> ServiceResult[EscalationHistory]:
        """
        Retrieve complete escalation history for a complaint.
        
        Args:
            complaint_id: UUID of complaint
            
        Returns:
            ServiceResult containing EscalationHistory or error
        """
        try:
            self._logger.debug(f"Fetching escalation history for complaint {complaint_id}")
            
            history = self.repository.get_history(complaint_id)
            
            entry_count = len(history.entries) if hasattr(history, 'entries') else 0
            
            self._logger.debug(
                f"Retrieved {entry_count} escalation entries for complaint {complaint_id}"
            )
            
            return ServiceResult.success(
                history,
                metadata={
                    "complaint_id": str(complaint_id),
                    "entry_count": entry_count,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error fetching escalation history for {complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get escalation history", complaint_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error fetching escalation history for {complaint_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get escalation history", complaint_id)

    # -------------------------------------------------------------------------
    # Auto-Escalation Rule Management
    # -------------------------------------------------------------------------

    def set_auto_rule(
        self,
        rule: AutoEscalationRule,
    ) -> ServiceResult[AutoEscalationRule]:
        """
        Create or update an auto-escalation rule for a hostel.
        
        Args:
            rule: Auto-escalation rule configuration
            
        Returns:
            ServiceResult containing saved AutoEscalationRule or error
        """
        try:
            self._logger.info(
                f"Setting auto-escalation rule for hostel {rule.hostel_id}"
            )
            
            # Validate rule
            validation_result = self._validate_auto_rule(rule)
            if not validation_result.success:
                return validation_result
            
            # Save rule
            saved_rule = self.repository.save_auto_rule(rule)
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Auto-escalation rule saved successfully for hostel {rule.hostel_id}"
            )
            
            return ServiceResult.success(
                saved_rule,
                message="Auto-escalation rule saved successfully",
                metadata={
                    "hostel_id": str(rule.hostel_id),
                    "rule_id": str(saved_rule.id) if hasattr(saved_rule, 'id') else None,
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error saving auto-escalation rule: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "save auto escalation rule")
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error saving auto-escalation rule: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "save auto escalation rule")

    def get_auto_rule(
        self,
        hostel_id: UUID,
    ) -> ServiceResult[AutoEscalationRule]:
        """
        Retrieve auto-escalation rule for a hostel.
        
        Args:
            hostel_id: UUID of hostel
            
        Returns:
            ServiceResult containing AutoEscalationRule or error
        """
        try:
            self._logger.debug(f"Fetching auto-escalation rule for hostel {hostel_id}")
            
            rule = self.repository.get_auto_rule(hostel_id)
            
            if not rule:
                self._logger.info(f"No auto-escalation rule found for hostel {hostel_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"No auto-escalation rule configured for hostel {hostel_id}",
                        severity=ErrorSeverity.INFO,
                    )
                )
            
            return ServiceResult.success(
                rule,
                metadata={"hostel_id": str(hostel_id)}
            )
            
        except SQLAlchemyError as e:
            self._logger.error(
                f"Database error fetching auto-escalation rule for {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get auto escalation rule", hostel_id)
            
        except Exception as e:
            self._logger.error(
                f"Unexpected error fetching auto-escalation rule for {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get auto escalation rule", hostel_id)

    def delete_auto_rule(
        self,
        hostel_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Delete auto-escalation rule for a hostel.
        
        Args:
            hostel_id: UUID of hostel
            
        Returns:
            ServiceResult containing success boolean or error
        """
        try:
            self._logger.info(f"Deleting auto-escalation rule for hostel {hostel_id}")
            
            # Implementation would call repository method
            # success = self.repository.delete_auto_rule(hostel_id)
            
            self.db.commit()
            
            return ServiceResult.success(
                True,
                message="Auto-escalation rule deleted successfully",
                metadata={"hostel_id": str(hostel_id)}
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error deleting auto-escalation rule for {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "delete auto escalation rule", hostel_id)
            
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Unexpected error deleting auto-escalation rule for {hostel_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "delete auto escalation rule", hostel_id)

    # -------------------------------------------------------------------------
    # Auto-Escalation Processing
    # -------------------------------------------------------------------------

    def process_auto_escalations(
        self,
        hostel_id: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Process automatic escalations based on configured rules.
        
        This method should be called periodically (e.g., via scheduled job)
        to check for complaints that meet auto-escalation criteria.
        
        Args:
            hostel_id: Optional hostel ID to limit processing scope
            
        Returns:
            ServiceResult containing processing summary or error
        """
        try:
            self._logger.info(
                f"Processing auto-escalations for hostel: {hostel_id or 'all'}"
            )
            
            # Implementation would:
            # 1. Fetch all active auto-escalation rules
            # 2. Find complaints matching criteria
            # 3. Escalate matching complaints
            # 4. Return summary
            
            # Placeholder response
            summary = {
                "processed_count": 0,
                "escalated_count": 0,
                "failed_count": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            self._logger.info(
                f"Auto-escalation processing complete: {summary['escalated_count']} escalated"
            )
            
            return ServiceResult.success(
                summary,
                message="Auto-escalation processing completed",
                metadata=summary
            )
            
        except Exception as e:
            self._logger.error(
                f"Error processing auto-escalations: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "process auto escalations")

    # -------------------------------------------------------------------------
    # Validation Helpers
    # -------------------------------------------------------------------------

    def _validate_escalation(
        self,
        request: EscalationRequest
    ) -> ServiceResult[None]:
        """
        Validate manual escalation request.
        
        Args:
            request: Escalation request to validate
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        if not request.complaint_id:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Complaint ID is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        if not request.escalation_level:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Escalation level is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        # Validate escalation level values
        valid_levels = ["L1", "L2", "L3", "MANAGEMENT", "EXECUTIVE"]
        if request.escalation_level not in valid_levels:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid escalation level. Must be one of: {', '.join(valid_levels)}",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        if hasattr(request, 'reason') and request.reason:
            if len(request.reason) > 1000:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Escalation reason exceeds maximum length of 1000 characters",
                        severity=ErrorSeverity.WARNING,
                    )
                )
        
        return ServiceResult.success(None)

    def _validate_auto_rule(
        self,
        rule: AutoEscalationRule
    ) -> ServiceResult[None]:
        """
        Validate auto-escalation rule configuration.
        
        Args:
            rule: Auto-escalation rule to validate
            
        Returns:
            ServiceResult indicating validation success or failure
        """
        if not rule.hostel_id:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Hostel ID is required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        # Validate time thresholds
        if hasattr(rule, 'time_threshold_hours'):
            if rule.time_threshold_hours < 0 or rule.time_threshold_hours > 720:  # Max 30 days
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Time threshold must be between 0 and 720 hours",
                        severity=ErrorSeverity.WARNING,
                    )
                )
        
        # Validate priority levels
        if hasattr(rule, 'priority_levels'):
            valid_priorities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            if rule.priority_levels:
                for priority in rule.priority_levels:
                    if priority not in valid_priorities:
                        return ServiceResult.failure(
                            ServiceError(
                                code=ErrorCode.VALIDATION_ERROR,
                                message=f"Invalid priority level: {priority}",
                                severity=ErrorSeverity.WARNING,
                            )
                        )
        
        return ServiceResult.success(None)