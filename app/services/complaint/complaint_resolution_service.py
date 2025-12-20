"""
Complaint resolution service with quality tracking and follow-up management.

Handles resolution workflow, quality control, follow-up scheduling,
and resolution performance tracking.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.complaint.complaint_resolution import ComplaintResolution
from app.repositories.complaint.complaint_repository import ComplaintRepository
from app.repositories.complaint.complaint_resolution_repository import (
    ComplaintResolutionRepository,
)
from app.core.exceptions import (
    BusinessLogicError,
    NotFoundError,
    ValidationError,
)


class ComplaintResolutionService:
    """
    Complaint resolution service with quality management.
    
    Manages resolution workflow, quality control, follow-up tracking,
    and resolution performance analytics.
    """

    def __init__(self, session: Session):
        """
        Initialize resolution service.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.complaint_repo = ComplaintRepository(session)
        self.resolution_repo = ComplaintResolutionRepository(session)

    # ==================== Resolution Creation ====================

    def create_resolution(
        self,
        complaint_id: str,
        resolved_by: str,
        resolution_notes: str,
        resolution_attachments: Optional[List[str]] = None,
        actions_taken: Optional[List[str]] = None,
        materials_used: Optional[str] = None,
        actual_resolution_time: Optional[datetime] = None,
        follow_up_required: bool = False,
        follow_up_date: Optional[date] = None,
        follow_up_notes: Optional[str] = None,
    ) -> ComplaintResolution:
        """
        Create resolution record for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            resolved_by: User resolving complaint
            resolution_notes: Resolution description
            resolution_attachments: Proof attachments
            actions_taken: Actions performed
            materials_used: Materials/parts used
            actual_resolution_time: Actual completion time
            follow_up_required: Follow-up flag
            follow_up_date: Scheduled follow-up date
            follow_up_notes: Follow-up instructions
            
        Returns:
            Created resolution instance
            
        Raises:
            NotFoundError: If complaint not found
            ValidationError: If resolution data invalid
            BusinessLogicError: If resolution not allowed
        """
        # Verify complaint exists
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            raise NotFoundError(f"Complaint {complaint_id} not found")
        
        # Validate resolution notes
        if not resolution_notes or not resolution_notes.strip():
            raise ValidationError("Resolution notes are required")
        
        if len(resolution_notes) < 10:
            raise ValidationError("Resolution notes must be at least 10 characters")
        
        # Validate follow-up date if required
        if follow_up_required:
            if not follow_up_date:
                # Default to 7 days from now
                follow_up_date = (datetime.now(timezone.utc) + timedelta(days=7)).date()
            
            if follow_up_date < datetime.now(timezone.utc).date():
                raise ValidationError("Follow-up date cannot be in the past")
        
        # Create resolution
        resolution = self.resolution_repo.create_resolution(
            complaint_id=complaint_id,
            resolved_by=resolved_by,
            resolution_notes=resolution_notes,
            resolution_attachments=resolution_attachments,
            actions_taken=actions_taken,
            materials_used=materials_used,
            actual_resolution_time=actual_resolution_time,
            follow_up_required=follow_up_required,
            follow_up_date=follow_up_date,
            follow_up_notes=follow_up_notes,
        )
        
        self.session.commit()
        self.session.refresh(resolution)
        
        # Schedule follow-up if required
        if follow_up_required:
            self._schedule_follow_up(resolution)
        
        return resolution

    def update_resolution(
        self,
        resolution_id: str,
        user_id: str,
        resolution_notes: Optional[str] = None,
        resolution_attachments: Optional[List[str]] = None,
        actions_taken: Optional[List[str]] = None,
        materials_used: Optional[str] = None,
    ) -> ComplaintResolution:
        """
        Update resolution details.
        
        Args:
            resolution_id: Resolution identifier
            user_id: User updating resolution
            resolution_notes: Updated notes
            resolution_attachments: Updated attachments
            actions_taken: Updated actions
            materials_used: Updated materials
            
        Returns:
            Updated resolution
            
        Raises:
            NotFoundError: If resolution not found
            BusinessLogicError: If update not allowed
        """
        resolution = self.resolution_repo.find_by_id(resolution_id)
        if not resolution:
            raise NotFoundError(f"Resolution {resolution_id} not found")
        
        # Verify user resolved the complaint
        if resolution.resolved_by != user_id:
            raise BusinessLogicError("Only resolver can update resolution")
        
        # Check if resolution was reopened
        if resolution.reopened:
            raise BusinessLogicError("Cannot update reopened resolution")
        
        # Prepare update data
        update_data = {}
        
        if resolution_notes is not None:
            if not resolution_notes.strip():
                raise ValidationError("Resolution notes cannot be empty")
            update_data["resolution_notes"] = resolution_notes
        
        if resolution_attachments is not None:
            update_data["resolution_attachments"] = resolution_attachments
        
        if actions_taken is not None:
            update_data["actions_taken"] = actions_taken
        
        if materials_used is not None:
            update_data["materials_used"] = materials_used
        
        # Update resolution
        updated = self.resolution_repo.update(resolution_id, update_data)
        
        self.session.commit()
        self.session.refresh(updated)
        
        return updated

    # ==================== Quality Control ====================

    def perform_quality_check(
        self,
        resolution_id: str,
        quality_checked_by: str,
        quality_score: int,
        quality_notes: Optional[str] = None,
    ) -> ComplaintResolution:
        """
        Perform quality check on resolution.
        
        Args:
            resolution_id: Resolution identifier
            quality_checked_by: User performing check
            quality_score: Quality score (1-10)
            quality_notes: Quality check notes
            
        Returns:
            Updated resolution
            
        Raises:
            NotFoundError: If resolution not found
            ValidationError: If quality score invalid
        """
        resolution = self.resolution_repo.find_by_id(resolution_id)
        if not resolution:
            raise NotFoundError(f"Resolution {resolution_id} not found")
        
        if resolution.quality_checked:
            raise BusinessLogicError("Resolution already quality checked")
        
        if not (1 <= quality_score <= 10):
            raise ValidationError("Quality score must be between 1 and 10")
        
        updated = self.resolution_repo.perform_quality_check(
            resolution_id=resolution_id,
            quality_checked_by=quality_checked_by,
            quality_score=quality_score,
            quality_notes=quality_notes,
        )
        
        self.session.commit()
        self.session.refresh(updated)
        
        # If quality score is low, might trigger alerts
        if quality_score <= 4:
            self._handle_low_quality_score(updated)
        
        return updated

    def bulk_quality_check(
        self,
        resolution_ids: List[str],
        quality_checked_by: str,
        default_score: int = 7,
    ) -> int:
        """
        Perform bulk quality checks.
        
        Args:
            resolution_ids: List of resolution IDs
            quality_checked_by: User performing checks
            default_score: Default quality score
            
        Returns:
            Number of resolutions checked
        """
        checked_count = 0
        
        for resolution_id in resolution_ids:
            try:
                self.perform_quality_check(
                    resolution_id=resolution_id,
                    quality_checked_by=quality_checked_by,
                    quality_score=default_score,
                )
                checked_count += 1
            except Exception as e:
                print(f"Quality check failed for {resolution_id}: {str(e)}")
        
        return checked_count

    # ==================== Follow-up Management ====================

    def complete_follow_up(
        self,
        resolution_id: str,
        notes: Optional[str] = None,
    ) -> ComplaintResolution:
        """
        Mark follow-up as completed.
        
        Args:
            resolution_id: Resolution identifier
            notes: Follow-up completion notes
            
        Returns:
            Updated resolution
            
        Raises:
            NotFoundError: If resolution not found
            BusinessLogicError: If follow-up not required
        """
        resolution = self.resolution_repo.find_by_id(resolution_id)
        if not resolution:
            raise NotFoundError(f"Resolution {resolution_id} not found")
        
        if not resolution.follow_up_required:
            raise BusinessLogicError("Follow-up not required for this resolution")
        
        if resolution.follow_up_completed:
            raise BusinessLogicError("Follow-up already completed")
        
        updated = self.resolution_repo.complete_follow_up(resolution_id)
        
        # Optionally add notes to metadata
        if notes:
            metadata = resolution.metadata or {}
            metadata["follow_up_completion_notes"] = notes
            self.resolution_repo.update(resolution_id, {"metadata": metadata})
        
        self.session.commit()
        self.session.refresh(updated)
        
        return updated

    def get_pending_follow_ups(
        self,
        hostel_id: Optional[str] = None,
        overdue_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintResolution]:
        """
        Get resolutions with pending follow-ups.
        
        Args:
            hostel_id: Optional hostel filter
            overdue_only: Only overdue follow-ups
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of resolutions
        """
        return self.resolution_repo.find_pending_follow_ups(
            hostel_id=hostel_id,
            overdue_only=overdue_only,
            skip=skip,
            limit=limit,
        )

    def get_overdue_follow_ups(
        self,
        hostel_id: Optional[str] = None,
    ) -> List[ComplaintResolution]:
        """
        Get overdue follow-ups.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of overdue resolutions
        """
        return self.get_pending_follow_ups(
            hostel_id=hostel_id,
            overdue_only=True,
            limit=1000,
        )

    # ==================== Reopening ====================

    def mark_reopened(
        self,
        complaint_id: str,
        reopen_reason: str,
    ) -> Optional[ComplaintResolution]:
        """
        Mark resolution as reopened.
        
        Args:
            complaint_id: Complaint identifier
            reopen_reason: Reason for reopening
            
        Returns:
            Updated resolution or None
        """
        # Find final resolution
        resolution = self.resolution_repo.find_final_resolution(complaint_id)
        if not resolution:
            return None
        
        updated = self.resolution_repo.reopen_resolution(
            resolution_id=resolution.id,
            reopen_reason=reopen_reason,
        )
        
        self.session.commit()
        
        return updated

    # ==================== Query Operations ====================

    def get_resolution(
        self,
        resolution_id: str,
    ) -> Optional[ComplaintResolution]:
        """
        Get resolution by ID.
        
        Args:
            resolution_id: Resolution identifier
            
        Returns:
            Resolution instance or None
        """
        return self.resolution_repo.find_by_id(resolution_id)

    def get_complaint_resolutions(
        self,
        complaint_id: str,
        final_only: bool = False,
    ) -> List[ComplaintResolution]:
        """
        Get all resolutions for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            final_only: Only final resolution
            
        Returns:
            List of resolutions
        """
        return self.resolution_repo.find_by_complaint(
            complaint_id=complaint_id,
            final_only=final_only,
        )

    def get_final_resolution(
        self,
        complaint_id: str,
    ) -> Optional[ComplaintResolution]:
        """
        Get final resolution for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            
        Returns:
            Final resolution or None
        """
        return self.resolution_repo.find_final_resolution(complaint_id)

    def get_user_resolutions(
        self,
        user_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        reopened_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintResolution]:
        """
        Get resolutions by a user.
        
        Args:
            user_id: User identifier
            date_from: Start date filter
            date_to: End date filter
            reopened_only: Only reopened resolutions
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of resolutions
        """
        return self.resolution_repo.find_by_resolver(
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
            reopened_only=reopened_only,
            skip=skip,
            limit=limit,
        )

    def get_pending_quality_checks(
        self,
        hostel_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintResolution]:
        """
        Get resolutions pending quality check.
        
        Args:
            hostel_id: Optional hostel filter
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of resolutions
        """
        return self.resolution_repo.find_pending_quality_checks(
            hostel_id=hostel_id,
            skip=skip,
            limit=limit,
        )

    def get_resolutions_by_quality_score(
        self,
        min_score: Optional[int] = None,
        max_score: Optional[int] = None,
        hostel_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintResolution]:
        """
        Get resolutions by quality score range.
        
        Args:
            min_score: Minimum quality score
            max_score: Maximum quality score
            hostel_id: Optional hostel filter
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of resolutions
        """
        return self.resolution_repo.find_by_quality_score(
            min_score=min_score,
            max_score=max_score,
            hostel_id=hostel_id,
            skip=skip,
            limit=limit,
        )

    # ==================== Analytics ====================

    def get_resolution_statistics(
        self,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get resolution statistics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Resolution statistics
        """
        return self.resolution_repo.get_resolution_statistics(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )

    def get_resolver_performance(
        self,
        user_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get resolution performance for a user.
        
        Args:
            user_id: User identifier
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Performance metrics
        """
        return self.resolution_repo.get_resolver_performance(
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
        )

    def get_quality_distribution(
        self,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[int, int]:
        """
        Get quality score distribution.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Score distribution
        """
        return self.resolution_repo.get_quality_distribution(
            hostel_id=hostel_id,
            date_from=date_from,
            date_to=date_to,
        )

    def get_resolution_trends(
        self,
        hostel_id: Optional[str] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Get resolution trends over time.
        
        Args:
            hostel_id: Optional hostel filter
            days: Number of days to analyze
            
        Returns:
            Daily resolution metrics
        """
        return self.resolution_repo.get_resolution_trends(
            hostel_id=hostel_id,
            days=days,
        )

    # ==================== Helper Methods ====================

    def _schedule_follow_up(
        self,
        resolution: ComplaintResolution,
    ) -> None:
        """
        Schedule follow-up task/reminder.
        
        Args:
            resolution: Resolution instance
        """
        # Would integrate with task scheduler/notification service
        print(f"Scheduling follow-up for resolution {resolution.id} on {resolution.follow_up_date}")

    def _handle_low_quality_score(
        self,
        resolution: ComplaintResolution,
    ) -> None:
        """
        Handle low quality score alert.
        
        Args:
            resolution: Resolution instance
        """
        # Would integrate with notification/escalation service
        print(f"ALERT: Low quality score ({resolution.quality_score}) for resolution {resolution.id}")