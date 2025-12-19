# --- File: complaint_resolution_repository.py ---
"""
Complaint resolution repository with quality tracking and follow-up management.

Handles resolution documentation, quality control, and follow-up scheduling
for comprehensive complaint closure management.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.models.complaint.complaint_resolution import ComplaintResolution
from app.models.complaint.complaint import Complaint
from app.repositories.base.base_repository import BaseRepository


class ComplaintResolutionRepository(BaseRepository[ComplaintResolution]):
    """
    Complaint resolution repository with quality management.
    
    Provides resolution tracking, quality control, follow-up management,
    and performance analytics for complaint resolution.
    """

    def __init__(self, session: Session):
        """
        Initialize complaint resolution repository.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(ComplaintResolution, session)

    # ==================== CRUD Operations ====================

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
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ComplaintResolution:
        """
        Create a new resolution record.
        
        Args:
            complaint_id: Complaint identifier
            resolved_by: User resolving the complaint
            resolution_notes: Resolution description
            resolution_attachments: Proof attachments
            actions_taken: List of actions performed
            materials_used: Materials/parts used
            actual_resolution_time: Actual completion time
            follow_up_required: Follow-up flag
            follow_up_date: Scheduled follow-up date
            follow_up_notes: Follow-up instructions
            metadata: Additional metadata
            
        Returns:
            Created resolution instance
        """
        # Mark previous resolutions as not final
        self._mark_previous_as_non_final(complaint_id)
        
        now = datetime.now(timezone.utc)
        
        # Get complaint to calculate resolution time
        complaint_query = select(Complaint).where(Complaint.id == complaint_id)
        complaint_result = self.session.execute(complaint_query)
        complaint = complaint_result.scalar_one_or_none()
        
        time_to_resolve = None
        if complaint:
            time_delta = now - complaint.opened_at
            time_to_resolve = int(time_delta.total_seconds() / 3600)
        
        resolution = ComplaintResolution(
            complaint_id=complaint_id,
            resolved_by=resolved_by,
            resolved_at=now,
            resolution_notes=resolution_notes,
            resolution_attachments=resolution_attachments or [],
            actions_taken=actions_taken or [],
            materials_used=materials_used,
            actual_resolution_time=actual_resolution_time or now,
            time_to_resolve_hours=time_to_resolve,
            follow_up_required=follow_up_required,
            follow_up_date=follow_up_date,
            follow_up_notes=follow_up_notes,
            is_final_resolution=True,
            metadata=metadata or {},
        )
        
        return self.create(resolution)

    def perform_quality_check(
        self,
        resolution_id: str,
        quality_checked_by: str,
        quality_score: int,
        quality_notes: Optional[str] = None,
    ) -> Optional[ComplaintResolution]:
        """
        Perform quality check on resolution.
        
        Args:
            resolution_id: Resolution identifier
            quality_checked_by: User performing quality check
            quality_score: Quality score (1-10)
            quality_notes: Quality check notes
            
        Returns:
            Updated resolution or None
        """
        update_data = {
            "quality_checked": True,
            "quality_checked_by": quality_checked_by,
            "quality_checked_at": datetime.now(timezone.utc),
            "quality_score": quality_score,
            "quality_notes": quality_notes,
        }
        
        return self.update(resolution_id, update_data)

    def complete_follow_up(
        self,
        resolution_id: str,
    ) -> Optional[ComplaintResolution]:
        """
        Mark follow-up as completed.
        
        Args:
            resolution_id: Resolution identifier
            
        Returns:
            Updated resolution or None
        """
        update_data = {
            "follow_up_completed": True,
            "follow_up_completed_at": datetime.now(timezone.utc),
        }
        
        return self.update(resolution_id, update_data)

    def reopen_resolution(
        self,
        resolution_id: str,
        reopen_reason: str,
    ) -> Optional[ComplaintResolution]:
        """
        Mark resolution as reopened.
        
        Args:
            resolution_id: Resolution identifier
            reopen_reason: Reason for reopening
            
        Returns:
            Updated resolution or None
        """
        update_data = {
            "reopened": True,
            "reopened_at": datetime.now(timezone.utc),
            "reopen_reason": reopen_reason,
            "is_final_resolution": False,
        }
        
        return self.update(resolution_id, update_data)

    # ==================== Query Operations ====================

    def find_by_complaint(
        self,
        complaint_id: str,
        final_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintResolution]:
        """
        Find all resolutions for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            final_only: Only final resolution
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of resolutions
        """
        query = select(ComplaintResolution).where(
            ComplaintResolution.complaint_id == complaint_id
        )
        
        if final_only:
            query = query.where(ComplaintResolution.is_final_resolution == True)
        
        query = query.order_by(desc(ComplaintResolution.resolved_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_final_resolution(
        self,
        complaint_id: str,
    ) -> Optional[ComplaintResolution]:
        """
        Find final resolution for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            
        Returns:
            Final resolution or None
        """
        query = select(ComplaintResolution).where(
            and_(
                ComplaintResolution.complaint_id == complaint_id,
                ComplaintResolution.is_final_resolution == True,
            )
        )
        
        result = self.session.execute(query)
        return result.scalar_one_or_none()

    def find_by_resolver(
        self,
        user_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        reopened_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintResolution]:
        """
        Find resolutions by a specific user.
        
        Args:
            user_id: User identifier
            date_from: Start date filter
            date_to: End date filter
            reopened_only: Only reopened resolutions
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of resolutions
        """
        query = select(ComplaintResolution).where(
            ComplaintResolution.resolved_by == user_id
        )
        
        if date_from:
            query = query.where(ComplaintResolution.resolved_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintResolution.resolved_at <= date_to)
        
        if reopened_only:
            query = query.where(ComplaintResolution.reopened == True)
        
        query = query.order_by(desc(ComplaintResolution.resolved_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_pending_follow_ups(
        self,
        hostel_id: Optional[str] = None,
        overdue_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintResolution]:
        """
        Find resolutions with pending follow-ups.
        
        Args:
            hostel_id: Optional hostel filter
            overdue_only: Only overdue follow-ups
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of resolutions needing follow-up
        """
        query = select(ComplaintResolution).where(
            and_(
                ComplaintResolution.follow_up_required == True,
                ComplaintResolution.follow_up_completed == False,
            )
        )
        
        if hostel_id:
            query = query.join(Complaint).where(Complaint.hostel_id == hostel_id)
        
        if overdue_only:
            today = date.today()
            query = query.where(
                and_(
                    ComplaintResolution.follow_up_date.isnot(None),
                    ComplaintResolution.follow_up_date < today,
                )
            )
        
        query = query.order_by(ComplaintResolution.follow_up_date.asc())
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_pending_quality_checks(
        self,
        hostel_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintResolution]:
        """
        Find resolutions pending quality check.
        
        Args:
            hostel_id: Optional hostel filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of resolutions needing quality check
        """
        query = select(ComplaintResolution).where(
            and_(
                ComplaintResolution.quality_checked == False,
                ComplaintResolution.is_final_resolution == True,
            )
        )
        
        if hostel_id:
            query = query.join(Complaint).where(Complaint.hostel_id == hostel_id)
        
        query = query.order_by(ComplaintResolution.resolved_at.asc())
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_by_quality_score(
        self,
        min_score: Optional[int] = None,
        max_score: Optional[int] = None,
        hostel_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintResolution]:
        """
        Find resolutions by quality score range.
        
        Args:
            min_score: Minimum quality score
            max_score: Maximum quality score
            hostel_id: Optional hostel filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of resolutions in score range
        """
        query = select(ComplaintResolution).where(
            ComplaintResolution.quality_checked == True
        )
        
        if min_score is not None:
            query = query.where(ComplaintResolution.quality_score >= min_score)
        
        if max_score is not None:
            query = query.where(ComplaintResolution.quality_score <= max_score)
        
        if hostel_id:
            query = query.join(Complaint).where(Complaint.hostel_id == hostel_id)
        
        query = query.order_by(desc(ComplaintResolution.quality_score))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ==================== Analytics ====================

    def get_resolution_statistics(
        self,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive resolution statistics.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Dictionary with resolution statistics
        """
        query = select(ComplaintResolution)
        
        if hostel_id:
            query = query.join(Complaint).where(Complaint.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(ComplaintResolution.resolved_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintResolution.resolved_at <= date_to)
        
        result = self.session.execute(query)
        resolutions = list(result.scalars().all())
        
        if not resolutions:
            return {
                "total_resolutions": 0,
                "average_resolution_time_hours": None,
                "reopened_count": 0,
                "reopen_rate": 0,
                "quality_checked_count": 0,
                "average_quality_score": None,
            }
        
        total = len(resolutions)
        reopened = len([r for r in resolutions if r.reopened])
        quality_checked = len([r for r in resolutions if r.quality_checked])
        
        # Average resolution time
        resolutions_with_time = [
            r for r in resolutions
            if r.time_to_resolve_hours is not None
        ]
        avg_time = (
            sum(r.time_to_resolve_hours for r in resolutions_with_time) / len(resolutions_with_time)
            if resolutions_with_time else None
        )
        
        # Average quality score
        quality_scored = [
            r for r in resolutions
            if r.quality_score is not None
        ]
        avg_quality = (
            sum(r.quality_score for r in quality_scored) / len(quality_scored)
            if quality_scored else None
        )
        
        # Follow-up metrics
        follow_up_required = len([r for r in resolutions if r.follow_up_required])
        follow_up_completed = len([r for r in resolutions if r.follow_up_completed])
        
        return {
            "total_resolutions": total,
            "average_resolution_time_hours": round(avg_time, 2) if avg_time else None,
            "median_resolution_time_hours": self._calculate_median_resolution_time(resolutions),
            "reopened_count": reopened,
            "reopen_rate": round(reopened / total * 100, 2) if total > 0 else 0,
            "quality_checked_count": quality_checked,
            "quality_check_rate": round(quality_checked / total * 100, 2) if total > 0 else 0,
            "average_quality_score": round(avg_quality, 2) if avg_quality else None,
            "follow_up_required_count": follow_up_required,
            "follow_up_completed_count": follow_up_completed,
            "follow_up_completion_rate": (
                round(follow_up_completed / follow_up_required * 100, 2)
                if follow_up_required > 0 else 0
            ),
        }

    def get_resolver_performance(
        self,
        user_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get resolution performance metrics for a user.
        
        Args:
            user_id: User identifier
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Dictionary with performance metrics
        """
        query = select(ComplaintResolution).where(
            ComplaintResolution.resolved_by == user_id
        )
        
        if date_from:
            query = query.where(ComplaintResolution.resolved_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintResolution.resolved_at <= date_to)
        
        result = self.session.execute(query)
        resolutions = list(result.scalars().all())
        
        if not resolutions:
            return {
                "user_id": user_id,
                "total_resolutions": 0,
                "average_resolution_time_hours": None,
                "reopen_rate": 0,
                "average_quality_score": None,
            }
        
        total = len(resolutions)
        reopened = len([r for r in resolutions if r.reopened])
        
        # Average resolution time
        resolutions_with_time = [
            r for r in resolutions
            if r.time_to_resolve_hours is not None
        ]
        avg_time = (
            sum(r.time_to_resolve_hours for r in resolutions_with_time) / len(resolutions_with_time)
            if resolutions_with_time else None
        )
        
        # Average quality score
        quality_scored = [
            r for r in resolutions
            if r.quality_score is not None
        ]
        avg_quality = (
            sum(r.quality_score for r in quality_scored) / len(quality_scored)
            if quality_scored else None
        )
        
        # Efficiency rating
        efficiency_rating = self._calculate_efficiency_rating(avg_time)
        
        return {
            "user_id": user_id,
            "total_resolutions": total,
            "average_resolution_time_hours": round(avg_time, 2) if avg_time else None,
            "reopen_count": reopened,
            "reopen_rate": round(reopened / total * 100, 2) if total > 0 else 0,
            "quality_checked_count": len(quality_scored),
            "average_quality_score": round(avg_quality, 2) if avg_quality else None,
            "efficiency_rating": efficiency_rating,
        }

    def get_quality_distribution(
        self,
        hostel_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[int, int]:
        """
        Get distribution of quality scores.
        
        Args:
            hostel_id: Optional hostel filter
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Dictionary mapping quality scores to counts
        """
        query = select(ComplaintResolution).where(
            ComplaintResolution.quality_checked == True
        )
        
        if hostel_id:
            query = query.join(Complaint).where(Complaint.hostel_id == hostel_id)
        
        if date_from:
            query = query.where(ComplaintResolution.resolved_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintResolution.resolved_at <= date_to)
        
        result = self.session.execute(query)
        resolutions = list(result.scalars().all())
        
        distribution = {}
        for i in range(1, 11):
            distribution[i] = len([
                r for r in resolutions
                if r.quality_score == i
            ])
        
        return distribution

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
            List of daily resolution metrics
        """
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        query = (
            select(
                func.date(ComplaintResolution.resolved_at).label("date"),
                func.count(ComplaintResolution.id).label("count"),
                func.avg(ComplaintResolution.time_to_resolve_hours).label("avg_time"),
                func.avg(ComplaintResolution.quality_score).label("avg_quality"),
            )
            .where(ComplaintResolution.resolved_at >= start_date)
            .group_by(func.date(ComplaintResolution.resolved_at))
            .order_by(func.date(ComplaintResolution.resolved_at))
        )
        
        if hostel_id:
            query = query.join(Complaint).where(Complaint.hostel_id == hostel_id)
        
        result = self.session.execute(query)
        
        return [
            {
                "date": row.date.isoformat(),
                "total_resolutions": row.count,
                "average_resolution_time_hours": round(float(row.avg_time), 2) if row.avg_time else None,
                "average_quality_score": round(float(row.avg_quality), 2) if row.avg_quality else None,
            }
            for row in result
        ]

    # ==================== Helper Methods ====================

    def _mark_previous_as_non_final(self, complaint_id: str) -> None:
        """
        Mark all previous resolutions as non-final.
        
        Args:
            complaint_id: Complaint identifier
        """
        stmt = (
            ComplaintResolution.__table__.update()
            .where(
                and_(
                    ComplaintResolution.complaint_id == complaint_id,
                    ComplaintResolution.is_final_resolution == True,
                )
            )
            .values(is_final_resolution=False)
        )
        
        self.session.execute(stmt)

    def _calculate_median_resolution_time(
        self,
        resolutions: List[ComplaintResolution],
    ) -> Optional[float]:
        """
        Calculate median resolution time.
        
        Args:
            resolutions: List of resolution instances
            
        Returns:
            Median time in hours or None
        """
        times = [
            r.time_to_resolve_hours for r in resolutions
            if r.time_to_resolve_hours is not None
        ]
        
        if not times:
            return None
        
        times.sort()
        n = len(times)
        
        if n % 2 == 0:
            return (times[n//2 - 1] + times[n//2]) / 2.0
        else:
            return float(times[n//2])

    def _calculate_efficiency_rating(
        self,
        avg_resolution_time: Optional[float],
    ) -> Optional[str]:
        """
        Calculate efficiency rating based on resolution time.
        
        Args:
            avg_resolution_time: Average resolution time in hours
            
        Returns:
            Efficiency rating or None
        """
        if avg_resolution_time is None:
            return None
        
        if avg_resolution_time <= 6:
            return "EXCELLENT"
        elif avg_resolution_time <= 12:
            return "GOOD"
        elif avg_resolution_time <= 24:
            return "AVERAGE"
        else:
            return "POOR"


