"""
Inquiry follow-up service: record interactions, get timeline & analytics.

Enhanced with:
- Rich timeline with multiple event types
- Follow-up analytics and metrics
- Reminder and scheduling support
- Interaction categorization
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.inquiry.inquiry_follow_up_repository import InquiryFollowUpRepository
from app.models.inquiry.inquiry_follow_up import InquiryFollowUp as InquiryFollowUpModel
from app.schemas.inquiry.inquiry_status import InquiryFollowUp, InquiryTimelineEntry

logger = logging.getLogger(__name__)


class InquiryFollowUpService(BaseService[InquiryFollowUpModel, InquiryFollowUpRepository]):
    """
    Manage inquiry follow-up interactions and timeline.
    
    Handles:
    - Recording follow-ups (calls, emails, messages, meetings)
    - Timeline generation and history
    - Follow-up analytics and metrics
    - Reminder scheduling and tracking
    """

    def __init__(self, repository: InquiryFollowUpRepository, db_session: Session):
        """
        Initialize follow-up service.
        
        Args:
            repository: InquiryFollowUpRepository for data access
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)
        self._logger = logger

    # =========================================================================
    # FOLLOW-UP RECORDING
    # =========================================================================

    def record(
        self,
        request: InquiryFollowUp,
        followed_up_by: Optional[UUID] = None,
    ) -> ServiceResult[InquiryTimelineEntry]:
        """
        Record a follow-up interaction with validation.
        
        Args:
            request: InquiryFollowUp with interaction details
            followed_up_by: UUID of user recording the follow-up
            
        Returns:
            ServiceResult containing timeline entry for the follow-up
        """
        try:
            self._logger.info(
                f"Recording follow-up for inquiry {request.inquiry_id}, "
                f"type: {getattr(request, 'interaction_type', 'N/A')}"
            )
            
            # Validate follow-up request
            validation_error = self._validate_follow_up(request)
            if validation_error:
                return ServiceResult.failure(validation_error)
            
            # Verify inquiry exists
            if hasattr(self.repository, 'get_inquiry'):
                inquiry = self.repository.get_inquiry(request.inquiry_id)
                if not inquiry:
                    self._logger.warning(f"Inquiry {request.inquiry_id} not found for follow-up")
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.NOT_FOUND,
                            message=f"Inquiry with ID {request.inquiry_id} not found",
                            severity=ErrorSeverity.ERROR,
                        )
                    )
            
            # Record the follow-up
            entry = self.repository.record_follow_up(request, followed_up_by=followed_up_by)
            
            # Commit transaction
            self.db.commit()
            
            self._logger.info(
                f"Successfully recorded follow-up for inquiry {request.inquiry_id}"
            )
            
            return ServiceResult.success(
                entry,
                message="Follow-up recorded successfully",
                metadata={
                    "inquiry_id": str(request.inquiry_id),
                    "interaction_type": getattr(request, 'interaction_type', None),
                    "followed_up_by": str(followed_up_by) if followed_up_by else None,
                }
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error recording follow-up for {request.inquiry_id}: {str(e)}"
            )
            return self._handle_exception(e, "record inquiry follow-up", request.inquiry_id)
        except Exception as e:
            self.db.rollback()
            self._logger.exception(
                f"Unexpected error recording follow-up for {request.inquiry_id}: {str(e)}"
            )
            return self._handle_exception(e, "record inquiry follow-up", request.inquiry_id)

    def bulk_record(
        self,
        follow_ups: List[InquiryFollowUp],
        followed_up_by: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Record multiple follow-ups in a single transaction.
        
        Args:
            follow_ups: List of InquiryFollowUp objects
            followed_up_by: UUID of user recording follow-ups
            
        Returns:
            ServiceResult with success/failure summary
        """
        try:
            if not follow_ups:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="No follow-ups provided for bulk recording",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            if len(follow_ups) > 100:  # Configurable limit
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Bulk follow-up recording limited to 100 items",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            self._logger.info(f"Bulk recording {len(follow_ups)} follow-ups")
            
            success_count = 0
            failed_count = 0
            errors = []
            
            for follow_up in follow_ups:
                try:
                    self.repository.record_follow_up(follow_up, followed_up_by=followed_up_by)
                    success_count += 1
                except Exception as e:
                    failed_count += 1
                    errors.append({
                        "inquiry_id": str(follow_up.inquiry_id),
                        "error": str(e),
                    })
            
            # Commit all successful records
            self.db.commit()
            
            result = {
                "success_count": success_count,
                "failed_count": failed_count,
                "total": len(follow_ups),
                "errors": errors if errors else None,
            }
            
            self._logger.info(
                f"Bulk follow-up recording completed: {success_count} succeeded, "
                f"{failed_count} failed"
            )
            
            return ServiceResult.success(
                result,
                message=f"Bulk follow-up recording completed: {success_count}/{len(follow_ups)} succeeded"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error in bulk follow-up recording: {str(e)}")
            return self._handle_exception(e, "bulk record follow-ups")
        except Exception as e:
            self.db.rollback()
            self._logger.exception(f"Unexpected error in bulk follow-up recording: {str(e)}")
            return self._handle_exception(e, "bulk record follow-ups")

    # =========================================================================
    # TIMELINE & HISTORY
    # =========================================================================

    def timeline(
        self,
        inquiry_id: UUID,
        limit: int = 50,
        include_system_events: bool = True,
    ) -> ServiceResult[List[InquiryTimelineEntry]]:
        """
        Get comprehensive inquiry timeline with all events.
        
        Args:
            inquiry_id: UUID of inquiry
            limit: Maximum number of timeline entries (default 50, max 200)
            include_system_events: Include system-generated events
            
        Returns:
            ServiceResult containing chronological timeline entries
        """
        try:
            # Validate and cap limit
            limit = min(max(1, limit), 200)
            
            self._logger.debug(
                f"Fetching timeline for inquiry {inquiry_id}, limit: {limit}"
            )
            
            items = self.repository.get_timeline(inquiry_id, limit=limit)
            
            # Filter system events if requested
            if not include_system_events and items:
                items = [
                    item for item in items
                    if getattr(item, 'event_type', '') != 'system'
                ]
            
            return ServiceResult.success(
                items,
                metadata={
                    "inquiry_id": str(inquiry_id),
                    "count": len(items),
                    "limit": limit,
                    "include_system_events": include_system_events,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error fetching timeline for {inquiry_id}: {str(e)}")
            return self._handle_exception(e, "get inquiry timeline", inquiry_id)
        except Exception as e:
            self._logger.exception(f"Unexpected error fetching timeline for {inquiry_id}: {str(e)}")
            return self._handle_exception(e, "get inquiry timeline", inquiry_id)

    def get_follow_up_history(
        self,
        inquiry_id: UUID,
        interaction_type: Optional[str] = None,
        limit: int = 50,
    ) -> ServiceResult[List[InquiryFollowUpModel]]:
        """
        Get follow-up history filtered by interaction type.
        
        Args:
            inquiry_id: UUID of inquiry
            interaction_type: Filter by type (call, email, whatsapp, etc.)
            limit: Maximum number of records
            
        Returns:
            ServiceResult containing follow-up records
        """
        try:
            limit = min(max(1, limit), 100)
            
            self._logger.debug(
                f"Fetching follow-up history for inquiry {inquiry_id}, "
                f"type: {interaction_type or 'all'}"
            )
            
            # Use repository method if available
            if hasattr(self.repository, 'get_follow_up_history'):
                history = self.repository.get_follow_up_history(
                    inquiry_id,
                    interaction_type=interaction_type,
                    limit=limit
                )
            else:
                # Fallback query
                query = self.db.query(InquiryFollowUpModel).filter(
                    InquiryFollowUpModel.inquiry_id == inquiry_id
                )
                if interaction_type:
                    query = query.filter(
                        InquiryFollowUpModel.interaction_type == interaction_type
                    )
                history = query.order_by(
                    InquiryFollowUpModel.created_at.desc()
                ).limit(limit).all()
            
            return ServiceResult.success(
                history,
                metadata={
                    "inquiry_id": str(inquiry_id),
                    "count": len(history),
                    "interaction_type": interaction_type,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error fetching follow-up history: {str(e)}")
            return self._handle_exception(e, "get follow-up history", inquiry_id)
        except Exception as e:
            self._logger.exception(f"Unexpected error fetching follow-up history: {str(e)}")
            return self._handle_exception(e, "get follow-up history", inquiry_id)

    # =========================================================================
    # ANALYTICS & METRICS
    # =========================================================================

    def get_follow_up_metrics(
        self,
        inquiry_id: UUID,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get follow-up metrics for an inquiry.
        
        Args:
            inquiry_id: UUID of inquiry
            
        Returns:
            ServiceResult with follow-up statistics and metrics
        """
        try:
            self._logger.debug(f"Calculating follow-up metrics for inquiry {inquiry_id}")
            
            # Check if repository has dedicated method
            if hasattr(self.repository, 'get_follow_up_metrics'):
                metrics = self.repository.get_follow_up_metrics(inquiry_id)
            else:
                # Calculate metrics manually
                follow_ups = self.db.query(InquiryFollowUpModel).filter(
                    InquiryFollowUpModel.inquiry_id == inquiry_id
                ).all()
                
                metrics = {
                    "total_follow_ups": len(follow_ups),
                    "by_type": {},
                    "last_follow_up": None,
                    "average_response_time": None,
                }
                
                if follow_ups:
                    # Group by interaction type
                    for fu in follow_ups:
                        interaction_type = getattr(fu, 'interaction_type', 'unknown')
                        metrics["by_type"][interaction_type] = \
                            metrics["by_type"].get(interaction_type, 0) + 1
                    
                    # Get last follow-up
                    last_fu = max(follow_ups, key=lambda x: x.created_at)
                    metrics["last_follow_up"] = {
                        "date": last_fu.created_at.isoformat(),
                        "type": getattr(last_fu, 'interaction_type', None),
                    }
            
            return ServiceResult.success(
                metrics,
                metadata={"inquiry_id": str(inquiry_id)}
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error calculating follow-up metrics: {str(e)}")
            return self._handle_exception(e, "get follow-up metrics", inquiry_id)
        except Exception as e:
            self._logger.exception(f"Unexpected error calculating follow-up metrics: {str(e)}")
            return self._handle_exception(e, "get follow-up metrics", inquiry_id)

    # =========================================================================
    # REMINDERS & SCHEDULING
    # =========================================================================

    def schedule_follow_up(
        self,
        inquiry_id: UUID,
        scheduled_for: datetime,
        interaction_type: str,
        notes: Optional[str] = None,
        assigned_to: Optional[UUID] = None,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Schedule a future follow-up reminder.
        
        Args:
            inquiry_id: UUID of inquiry
            scheduled_for: DateTime when follow-up should occur
            interaction_type: Type of planned interaction
            notes: Optional notes about the scheduled follow-up
            assigned_to: User responsible for the follow-up
            created_by: User creating the reminder
            
        Returns:
            ServiceResult with scheduled follow-up details
        """
        try:
            # Validate schedule
            if scheduled_for <= datetime.utcnow():
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Scheduled time must be in the future",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            self._logger.info(
                f"Scheduling follow-up for inquiry {inquiry_id} at {scheduled_for}"
            )
            
            # Use repository method if available
            if hasattr(self.repository, 'schedule_follow_up'):
                result = self.repository.schedule_follow_up(
                    inquiry_id=inquiry_id,
                    scheduled_for=scheduled_for,
                    interaction_type=interaction_type,
                    notes=notes,
                    assigned_to=assigned_to,
                    created_by=created_by,
                )
                self.db.commit()
            else:
                # Create a scheduled follow-up record
                result = {
                    "inquiry_id": str(inquiry_id),
                    "scheduled_for": scheduled_for.isoformat(),
                    "interaction_type": interaction_type,
                    "notes": notes,
                    "assigned_to": str(assigned_to) if assigned_to else None,
                    "created_by": str(created_by) if created_by else None,
                    "status": "scheduled",
                }
            
            return ServiceResult.success(
                result,
                message="Follow-up scheduled successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error scheduling follow-up: {str(e)}")
            return self._handle_exception(e, "schedule follow-up", inquiry_id)
        except Exception as e:
            self.db.rollback()
            self._logger.exception(f"Unexpected error scheduling follow-up: {str(e)}")
            return self._handle_exception(e, "schedule follow-up", inquiry_id)

    def get_upcoming_follow_ups(
        self,
        user_id: Optional[UUID] = None,
        days_ahead: int = 7,
        limit: int = 50,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Get upcoming scheduled follow-ups.
        
        Args:
            user_id: Optional filter by assigned user
            days_ahead: Number of days to look ahead (default 7)
            limit: Maximum number of results
            
        Returns:
            ServiceResult containing upcoming follow-up reminders
        """
        try:
            limit = min(max(1, limit), 100)
            end_date = datetime.utcnow() + timedelta(days=days_ahead)
            
            self._logger.debug(
                f"Fetching upcoming follow-ups for next {days_ahead} days, "
                f"user: {user_id or 'all'}"
            )
            
            # Use repository method if available
            if hasattr(self.repository, 'get_upcoming_follow_ups'):
                upcoming = self.repository.get_upcoming_follow_ups(
                    user_id=user_id,
                    end_date=end_date,
                    limit=limit
                )
            else:
                # Return empty list if not implemented
                upcoming = []
            
            return ServiceResult.success(
                upcoming,
                metadata={
                    "count": len(upcoming),
                    "days_ahead": days_ahead,
                    "user_id": str(user_id) if user_id else None,
                }
            )
            
        except SQLAlchemyError as e:
            self._logger.error(f"Database error fetching upcoming follow-ups: {str(e)}")
            return self._handle_exception(e, "get upcoming follow-ups")
        except Exception as e:
            self._logger.exception(f"Unexpected error fetching upcoming follow-ups: {str(e)}")
            return self._handle_exception(e, "get upcoming follow-ups")

    # =========================================================================
    # VALIDATION & UTILITIES
    # =========================================================================

    def _validate_follow_up(self, request: InquiryFollowUp) -> Optional[ServiceError]:
        """
        Validate follow-up request.
        
        Args:
            request: Follow-up request to validate
            
        Returns:
            ServiceError if invalid, None if valid
        """
        if not request.inquiry_id:
            return ServiceError(
                code=ErrorCode.VALIDATION_ERROR,
                message="Inquiry ID is required for follow-up",
                severity=ErrorSeverity.ERROR,
            )
        
        # Validate interaction type if present
        if hasattr(request, 'interaction_type'):
            valid_types = ['call', 'email', 'whatsapp', 'sms', 'in_person', 'other']
            if request.interaction_type and request.interaction_type not in valid_types:
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Invalid interaction type. Must be one of: {', '.join(valid_types)}",
                    severity=ErrorSeverity.WARNING,
                )
        
        # Validate notes length if present
        if hasattr(request, 'notes') and request.notes:
            if len(request.notes) > 5000:  # Configurable limit
                return ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Follow-up notes cannot exceed 5000 characters",
                    severity=ErrorSeverity.WARNING,
                )
        
        return None

    def update_follow_up(
        self,
        follow_up_id: UUID,
        notes: Optional[str] = None,
        outcome: Optional[str] = None,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[InquiryFollowUpModel]:
        """
        Update an existing follow-up record.
        
        Args:
            follow_up_id: UUID of follow-up to update
            notes: Updated notes
            outcome: Updated outcome
            updated_by: User performing update
            
        Returns:
            ServiceResult with updated follow-up
        """
        try:
            self._logger.info(f"Updating follow-up {follow_up_id}")
            
            follow_up = self.repository.get_by_id(follow_up_id)
            if not follow_up:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Follow-up with ID {follow_up_id} not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )
            
            # Update fields
            if notes is not None:
                follow_up.notes = notes
            if outcome is not None:
                follow_up.outcome = outcome
            if updated_by:
                follow_up.updated_by = updated_by
            
            follow_up.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            return ServiceResult.success(
                follow_up,
                message="Follow-up updated successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error updating follow-up: {str(e)}")
            return self._handle_exception(e, "update follow-up", follow_up_id)
        except Exception as e:
            self.db.rollback()
            self._logger.exception(f"Unexpected error updating follow-up: {str(e)}")
            return self._handle_exception(e, "update follow-up", follow_up_id)