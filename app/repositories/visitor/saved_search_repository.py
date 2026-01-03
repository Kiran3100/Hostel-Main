# --- File: app/repositories/visitor/saved_search_repository.py ---
"""
Saved search repository for persistent search criteria and alerts.

This module provides repository operations for saved searches including
execution tracking, match management, and notification handling.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.visitor.saved_search import (
    SavedSearch,
    SavedSearchExecution,
    SavedSearchMatch,
    SavedSearchNotification,
)
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.pagination import PaginationParams, PaginatedResult


class SavedSearchRepository(BaseRepository[SavedSearch]):
    """
    Repository for SavedSearch entity.
    
    Provides comprehensive saved search management with automated monitoring,
    execution tracking, and notification handling.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(SavedSearch, session)

    # ==================== Core CRUD Operations ====================

    def create_saved_search(
        self,
        visitor_id: UUID,
        search_name: str,
        search_criteria: Dict,
        search_description: Optional[str] = None,
        search_query: Optional[str] = None,
        cities: Optional[List[str]] = None,
        areas: Optional[List[str]] = None,
        room_types: Optional[List[str]] = None,
        hostel_types: Optional[List[str]] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        required_amenities: Optional[List[str]] = None,
        preferred_amenities: Optional[List[str]] = None,
        min_rating: Optional[Decimal] = None,
        require_availability: bool = True,
        notify_on_new_matches: bool = True,
        notification_frequency: str = "daily",
        notification_channels: Optional[List[str]] = None,
    ) -> SavedSearch:
        """
        Create a new saved search.
        
        Args:
            visitor_id: Visitor ID
            search_name: Name for the search
            search_criteria: Complete search criteria dictionary
            search_description: Optional description
            search_query: Text search query
            cities: Cities to search in
            areas: Specific areas/localities
            room_types: Room types to include
            hostel_types: Hostel types to include
            min_price: Minimum price
            max_price: Maximum price
            required_amenities: Required amenities
            preferred_amenities: Preferred amenities
            min_rating: Minimum rating
            require_availability: Only show available hostels
            notify_on_new_matches: Send notifications for new matches
            notification_frequency: Notification frequency
            notification_channels: Notification channels
            
        Returns:
            Created SavedSearch instance
        """
        saved_search = SavedSearch(
            visitor_id=visitor_id,
            search_name=search_name,
            search_description=search_description,
            search_query=search_query,
            cities=cities or [],
            areas=areas or [],
            room_types=room_types or [],
            hostel_types=hostel_types or [],
            min_price=min_price,
            max_price=max_price,
            required_amenities=required_amenities or [],
            preferred_amenities=preferred_amenities or [],
            min_rating=min_rating,
            require_availability=require_availability,
            search_criteria=search_criteria,
            notify_on_new_matches=notify_on_new_matches,
            notification_frequency=notification_frequency,
            notification_channels=notification_channels or ["email"],
            is_active=True,
            is_paused=False,
        )
        
        self.db.add(saved_search)
        self.db.flush()
        
        return saved_search

    def get_visitor_saved_searches(
        self,
        visitor_id: UUID,
        active_only: bool = True,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[SavedSearch]:
        """
        Get all saved searches for a visitor.
        
        Args:
            visitor_id: Visitor ID
            active_only: Only return active searches
            pagination: Pagination parameters
            
        Returns:
            Paginated list of saved searches
        """
        query = select(SavedSearch).where(
            and_(
                SavedSearch.visitor_id == visitor_id,
                SavedSearch.is_deleted == False,
            )
        )
        
        if active_only:
            query = query.where(SavedSearch.is_active == True)
        
        query = query.order_by(desc(SavedSearch.created_at))
        
        return self._paginate_query(query, pagination)

    def update_saved_search(
        self,
        search_id: UUID,
        search_name: Optional[str] = None,
        search_description: Optional[str] = None,
        search_criteria: Optional[Dict] = None,
        cities: Optional[List[str]] = None,
        min_price: Optional[Decimal] = None,
        max_price: Optional[Decimal] = None,
        required_amenities: Optional[List[str]] = None,
        notification_frequency: Optional[str] = None,
        notification_channels: Optional[List[str]] = None,
    ) -> SavedSearch:
        """
        Update a saved search.
        
        Args:
            search_id: Search ID
            search_name: Updated name
            search_description: Updated description
            search_criteria: Updated criteria
            cities: Updated cities
            min_price: Updated min price
            max_price: Updated max price
            required_amenities: Updated amenities
            notification_frequency: Updated frequency
            notification_channels: Updated channels
            
        Returns:
            Updated SavedSearch instance
        """
        saved_search = self.find_by_id(search_id)
        if not saved_search:
            raise ValueError(f"Saved search not found: {search_id}")
        
        if search_name is not None:
            saved_search.search_name = search_name
        if search_description is not None:
            saved_search.search_description = search_description
        if search_criteria is not None:
            saved_search.search_criteria = search_criteria
        if cities is not None:
            saved_search.cities = cities
        if min_price is not None:
            saved_search.min_price = min_price
        if max_price is not None:
            saved_search.max_price = max_price
        if required_amenities is not None:
            saved_search.required_amenities = required_amenities
        if notification_frequency is not None:
            saved_search.notification_frequency = notification_frequency
        if notification_channels is not None:
            saved_search.notification_channels = notification_channels
        
        # Track edits
        saved_search.times_edited += 1
        saved_search.last_edited_at = datetime.utcnow()
        
        self.db.flush()
        return saved_search

    def toggle_search_active(
        self,
        search_id: UUID,
        is_active: bool,
    ) -> SavedSearch:
        """
        Activate or deactivate a saved search.
        
        Args:
            search_id: Search ID
            is_active: Active status
            
        Returns:
            Updated SavedSearch instance
        """
        saved_search = self.find_by_id(search_id)
        if not saved_search:
            raise ValueError(f"Saved search not found: {search_id}")
        
        saved_search.is_active = is_active
        
        self.db.flush()
        return saved_search

    def pause_search(
        self,
        search_id: UUID,
    ) -> SavedSearch:
        """
        Pause a saved search temporarily.
        
        Args:
            search_id: Search ID
            
        Returns:
            Updated SavedSearch instance
        """
        saved_search = self.find_by_id(search_id)
        if not saved_search:
            raise ValueError(f"Saved search not found: {search_id}")
        
        saved_search.is_paused = True
        
        self.db.flush()
        return saved_search

    def resume_search(
        self,
        search_id: UUID,
    ) -> SavedSearch:
        """
        Resume a paused saved search.
        
        Args:
            search_id: Search ID
            
        Returns:
            Updated SavedSearch instance
        """
        saved_search = self.find_by_id(search_id)
        if not saved_search:
            raise ValueError(f"Saved search not found: {search_id}")
        
        saved_search.is_paused = False
        
        self.db.flush()
        return saved_search

    # ==================== Execution Management ====================

    def get_searches_to_execute(
        self,
        limit: Optional[int] = None,
    ) -> List[SavedSearch]:
        """
        Get saved searches that should be executed now.
        
        Args:
            limit: Maximum searches to return
            
        Returns:
            List of searches ready for execution
        """
        now = datetime.utcnow()
        
        query = select(SavedSearch).where(
            and_(
                SavedSearch.is_deleted == False,
                SavedSearch.is_active == True,
                SavedSearch.is_paused == False,
                or_(
                    SavedSearch.next_check_at.is_(None),
                    SavedSearch.next_check_at <= now,
                ),
            )
        ).order_by(SavedSearch.next_check_at.nulls_first())
        
        if limit:
            query = query.limit(limit)
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def update_search_execution(
        self,
        search_id: UUID,
        total_matches: int,
        new_matches_count: int,
        execution_time_ms: int,
    ) -> SavedSearch:
        """
        Update saved search after execution.
        
        Args:
            search_id: Search ID
            total_matches: Total current matches
            new_matches_count: New matches found
            execution_time_ms: Execution time in milliseconds
            
        Returns:
            Updated SavedSearch instance
        """
        saved_search = self.find_by_id(search_id)
        if not saved_search:
            raise ValueError(f"Saved search not found: {search_id}")
        
        # Update match counts
        saved_search.last_match_count = saved_search.total_matches
        saved_search.total_matches = total_matches
        saved_search.new_matches_count = new_matches_count
        
        # Update execution tracking
        saved_search.last_checked_at = datetime.utcnow()
        saved_search.total_executions += 1
        
        # Calculate next check time based on frequency
        next_check = self._calculate_next_check_time(
            saved_search.notification_frequency
        )
        saved_search.next_check_at = next_check
        
        # Update average execution time
        if saved_search.average_execution_time_ms:
            saved_search.average_execution_time_ms = int(
                (saved_search.average_execution_time_ms + execution_time_ms) / 2
            )
        else:
            saved_search.average_execution_time_ms = execution_time_ms
        
        self.db.flush()
        return saved_search

    def _calculate_next_check_time(
        self,
        frequency: str,
    ) -> datetime:
        """
        Calculate next check time based on frequency.
        
        Args:
            frequency: Notification frequency
            
        Returns:
            Next check datetime
        """
        now = datetime.utcnow()
        
        if frequency == "instant":
            return now + timedelta(hours=1)  # Check hourly for instant
        elif frequency == "daily":
            return now + timedelta(days=1)
        elif frequency == "weekly":
            return now + timedelta(weeks=1)
        elif frequency == "monthly":
            return now + timedelta(days=30)
        else:
            return now + timedelta(days=1)  # Default to daily

    def mark_notification_sent(
        self,
        search_id: UUID,
    ) -> SavedSearch:
        """
        Mark that notification was sent for search.
        
        Args:
            search_id: Search ID
            
        Returns:
            Updated SavedSearch instance
        """
        saved_search = self.find_by_id(search_id)
        if not saved_search:
            raise ValueError(f"Saved search not found: {search_id}")
        
        saved_search.last_notification_sent_at = datetime.utcnow()
        saved_search.new_matches_count = 0  # Reset after notification
        
        self.db.flush()
        return saved_search

    # ==================== Statistics & Analytics ====================

    def get_search_statistics(
        self,
        search_id: UUID,
    ) -> Dict:
        """
        Get statistics for a saved search.
        
        Args:
            search_id: Search ID
            
        Returns:
            Dictionary containing search statistics
        """
        saved_search = self.find_by_id(search_id)
        if not saved_search:
            raise ValueError(f"Saved search not found: {search_id}")
        
        # Get execution history
        executions_query = (
            select(func.count(SavedSearchExecution.id))
            .where(SavedSearchExecution.saved_search_id == search_id)
        )
        total_executions = self.db.execute(executions_query).scalar_one()
        
        # Get successful executions
        successful_query = (
            select(func.count(SavedSearchExecution.id))
            .where(
                and_(
                    SavedSearchExecution.saved_search_id == search_id,
                    SavedSearchExecution.execution_successful == True,
                )
            )
        )
        successful_executions = self.db.execute(successful_query).scalar_one()
        
        # Get total matches found
        matches_query = (
            select(func.count(SavedSearchMatch.id))
            .where(SavedSearchMatch.saved_search_id == search_id)
        )
        total_matches = self.db.execute(matches_query).scalar_one()
        
        # Get notifications sent
        notifications_query = (
            select(func.count(SavedSearchNotification.id))
            .where(SavedSearchNotification.saved_search_id == search_id)
        )
        notifications_sent = self.db.execute(notifications_query).scalar_one()
        
        success_rate = Decimal("0.00")
        if total_executions > 0:
            success_rate = (
                Decimal(successful_executions) / Decimal(total_executions) * 100
            ).quantize(Decimal("0.01"))
        
        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "success_rate": success_rate,
            "total_matches": total_matches,
            "current_matches": saved_search.total_matches,
            "new_matches": saved_search.new_matches_count,
            "notifications_sent": notifications_sent,
            "average_execution_time_ms": saved_search.average_execution_time_ms,
            "times_edited": saved_search.times_edited,
        }

    def get_visitor_search_summary(
        self,
        visitor_id: UUID,
    ) -> Dict:
        """
        Get summary of all saved searches for visitor.
        
        Args:
            visitor_id: Visitor ID
            
        Returns:
            Dictionary containing summary statistics
        """
        # Total searches
        total_query = select(func.count(SavedSearch.id)).where(
            and_(
                SavedSearch.visitor_id == visitor_id,
                SavedSearch.is_deleted == False,
            )
        )
        total_searches = self.db.execute(total_query).scalar_one()
        
        # Active searches
        active_query = select(func.count(SavedSearch.id)).where(
            and_(
                SavedSearch.visitor_id == visitor_id,
                SavedSearch.is_deleted == False,
                SavedSearch.is_active == True,
                SavedSearch.is_paused == False,
            )
        )
        active_searches = self.db.execute(active_query).scalar_one()
        
        # Total matches across all searches
        matches_query = (
            select(func.sum(SavedSearch.total_matches))
            .where(
                and_(
                    SavedSearch.visitor_id == visitor_id,
                    SavedSearch.is_deleted == False,
                )
            )
        )
        total_matches = self.db.execute(matches_query).scalar_one() or 0
        
        # New matches across all searches
        new_matches_query = (
            select(func.sum(SavedSearch.new_matches_count))
            .where(
                and_(
                    SavedSearch.visitor_id == visitor_id,
                    SavedSearch.is_deleted == False,
                    SavedSearch.is_active == True,
                )
            )
        )
        new_matches = self.db.execute(new_matches_query).scalar_one() or 0
        
        return {
            "total_saved_searches": total_searches,
            "active_searches": active_searches,
            "total_matches": total_matches,
            "new_matches": new_matches,
            "searches_with_new_matches": self._count_searches_with_new_matches(visitor_id),
        }

    def _count_searches_with_new_matches(
        self,
        visitor_id: UUID,
    ) -> int:
        """
        Count searches with new matches.
        
        Args:
            visitor_id: Visitor ID
            
        Returns:
            Count of searches with new matches
        """
        query = select(func.count(SavedSearch.id)).where(
            and_(
                SavedSearch.visitor_id == visitor_id,
                SavedSearch.is_deleted == False,
                SavedSearch.new_matches_count > 0,
            )
        )
        
        return self.db.execute(query).scalar_one()


class SavedSearchExecutionRepository(BaseRepository[SavedSearchExecution]):
    """Repository for SavedSearchExecution entity."""

    def __init__(self, session: Session):
        super().__init__(SavedSearchExecution, session)

    def create_execution_record(
        self,
        saved_search_id: UUID,
        execution_successful: bool,
        execution_time_ms: int,
        results_count: int,
        new_results_count: int,
        removed_results_count: int,
        result_hostel_ids: List[UUID],
        new_hostel_ids: List[UUID],
        criteria_used: Dict,
        execution_error: Optional[str] = None,
        database_query_time_ms: Optional[int] = None,
    ) -> SavedSearchExecution:
        """
        Create an execution record.
        
        Args:
            saved_search_id: Saved search ID
            execution_successful: Whether execution succeeded
            execution_time_ms: Execution time in milliseconds
            results_count: Total results found
            new_results_count: New results count
            removed_results_count: Removed results count
            result_hostel_ids: List of result hostel IDs
            new_hostel_ids: List of new hostel IDs
            criteria_used: Criteria snapshot
            execution_error: Error message if failed
            database_query_time_ms: Database query time
            
        Returns:
            Created SavedSearchExecution instance
        """
        execution = SavedSearchExecution(
            saved_search_id=saved_search_id,
            executed_at=datetime.utcnow(),
            execution_successful=execution_successful,
            execution_time_ms=execution_time_ms,
            results_count=results_count,
            new_results_count=new_results_count,
            removed_results_count=removed_results_count,
            result_hostel_ids=result_hostel_ids,
            new_hostel_ids=new_hostel_ids,
            criteria_used=criteria_used,
            execution_error=execution_error,
            database_query_time_ms=database_query_time_ms,
        )
        
        self.db.add(execution)
        self.db.flush()
        
        return execution

    def get_execution_history(
        self,
        saved_search_id: UUID,
        limit: int = 20,
    ) -> List[SavedSearchExecution]:
        """
        Get execution history for a saved search.
        
        Args:
            saved_search_id: Saved search ID
            limit: Maximum records to return
            
        Returns:
            List of execution records
        """
        query = (
            select(SavedSearchExecution)
            .where(SavedSearchExecution.saved_search_id == saved_search_id)
            .order_by(desc(SavedSearchExecution.executed_at))
            .limit(limit)
        )
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_execution_performance_metrics(
        self,
        saved_search_id: UUID,
    ) -> Dict:
        """
        Get performance metrics for search executions.
        
        Args:
            saved_search_id: Saved search ID
            
        Returns:
            Dictionary containing performance metrics
        """
        query = select(SavedSearchExecution).where(
            SavedSearchExecution.saved_search_id == saved_search_id
        )
        
        result = self.db.execute(query)
        executions = list(result.scalars().all())
        
        if not executions:
            return {
                "total_executions": 0,
                "successful_executions": 0,
                "average_execution_time_ms": 0,
                "average_results_count": 0,
            }
        
        successful = [e for e in executions if e.execution_successful]
        
        avg_time = sum(e.execution_time_ms for e in executions) / len(executions)
        avg_results = sum(e.results_count for e in executions) / len(executions)
        
        return {
            "total_executions": len(executions),
            "successful_executions": len(successful),
            "failed_executions": len(executions) - len(successful),
            "average_execution_time_ms": int(avg_time),
            "average_results_count": int(avg_results),
            "latest_execution": executions[0].executed_at if executions else None,
        }


class SavedSearchMatchRepository(BaseRepository[SavedSearchMatch]):
    """Repository for SavedSearchMatch entity."""

    def __init__(self, session: Session):
        super().__init__(SavedSearchMatch, session)

    def create_match(
        self,
        saved_search_id: UUID,
        hostel_id: UUID,
        hostel_name: str,
        hostel_slug: str,
        hostel_city: str,
        starting_price: Decimal,
        match_score: Decimal,
        match_criteria_met: Dict,
    ) -> SavedSearchMatch:
        """
        Create a search match record.
        
        Args:
            saved_search_id: Saved search ID
            hostel_id: Hostel ID
            hostel_name: Hostel name
            hostel_slug: Hostel slug
            hostel_city: Hostel city
            starting_price: Starting price
            match_score: Match quality score
            match_criteria_met: Criteria that were met
            
        Returns:
            Created SavedSearchMatch instance
        """
        now = datetime.utcnow()
        
        match = SavedSearchMatch(
            saved_search_id=saved_search_id,
            hostel_id=hostel_id,
            hostel_name=hostel_name,
            hostel_slug=hostel_slug,
            hostel_city=hostel_city,
            starting_price=starting_price,
            match_score=match_score,
            match_criteria_met=match_criteria_met,
            is_new=True,
            is_notified=False,
            first_matched_at=now,
            last_checked_at=now,
        )
        
        self.db.add(match)
        self.db.flush()
        
        return match

    def get_search_matches(
        self,
        saved_search_id: UUID,
        new_only: bool = False,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResult[SavedSearchMatch]:
        """
        Get matches for a saved search.
        
        Args:
            saved_search_id: Saved search ID
            new_only: Only return new matches
            pagination: Pagination parameters
            
        Returns:
            Paginated list of matches
        """
        query = select(SavedSearchMatch).where(
            and_(
                SavedSearchMatch.saved_search_id == saved_search_id,
                SavedSearchMatch.is_deleted == False,
            )
        )
        
        if new_only:
            query = query.where(SavedSearchMatch.is_new == True)
        
        query = query.order_by(desc(SavedSearchMatch.match_score))
        
        return self._paginate_query(query, pagination)

    def mark_matches_notified(
        self,
        match_ids: List[UUID],
    ) -> int:
        """
        Mark matches as notified.
        
        Args:
            match_ids: List of match IDs
            
        Returns:
            Number of matches updated
        """
        query = select(SavedSearchMatch).where(
            SavedSearchMatch.id.in_(match_ids)
        )
        
        result = self.db.execute(query)
        matches = result.scalars().all()
        
        count = 0
        for match in matches:
            match.is_new = False
            match.is_notified = True
            match.notified_at = datetime.utcnow()
            count += 1
        
        self.db.flush()
        return count

    def mark_match_viewed(
        self,
        match_id: UUID,
    ) -> SavedSearchMatch:
        """
        Mark match as viewed by visitor.
        
        Args:
            match_id: Match ID
            
        Returns:
            Updated SavedSearchMatch instance
        """
        match = self.find_by_id(match_id)
        if not match:
            raise ValueError(f"Match not found: {match_id}")
        
        match.was_viewed = True
        match.viewed_at = datetime.utcnow()
        
        self.db.flush()
        return match

    def update_match_verification(
        self,
        saved_search_id: UUID,
        hostel_id: UUID,
        still_matches: bool,
    ) -> Optional[SavedSearchMatch]:
        """
        Update match verification status.
        
        Args:
            saved_search_id: Saved search ID
            hostel_id: Hostel ID
            still_matches: Whether hostel still matches criteria
            
        Returns:
            Updated SavedSearchMatch instance or None
        """
        query = select(SavedSearchMatch).where(
            and_(
                SavedSearchMatch.saved_search_id == saved_search_id,
                SavedSearchMatch.hostel_id == hostel_id,
                SavedSearchMatch.is_deleted == False,
            )
        )
        
        result = self.db.execute(query)
        match = result.scalar_one_or_none()
        
        if not match:
            return None
        
        match.last_checked_at = datetime.utcnow()
        
        if not still_matches:
            # Soft delete if no longer matches
            match.is_deleted = True
            match.deleted_at = datetime.utcnow()
        
        self.db.flush()
        return match


class SavedSearchNotificationRepository(BaseRepository[SavedSearchNotification]):
    """Repository for SavedSearchNotification entity."""

    def __init__(self, session: Session):
        super().__init__(SavedSearchNotification, session)

    def create_notification(
        self,
        saved_search_id: UUID,
        notification_type: str,
        subject: str,
        message: str,
        new_matches_count: int,
        match_hostel_ids: List[UUID],
        delivery_channels: List[str],
    ) -> SavedSearchNotification:
        """
        Create a notification record.
        
        Args:
            saved_search_id: Saved search ID
            notification_type: Notification type
            subject: Notification subject
            message: Notification message
            new_matches_count: Number of new matches
            match_hostel_ids: List of matching hostel IDs
            delivery_channels: Delivery channels
            
        Returns:
            Created SavedSearchNotification instance
        """
        notification = SavedSearchNotification(
            saved_search_id=saved_search_id,
            notification_type=notification_type,
            subject=subject,
            message=message,
            new_matches_count=new_matches_count,
            match_hostel_ids=match_hostel_ids,
            delivery_channels=delivery_channels,
            delivery_status="pending",
            sent_at=datetime.utcnow(),
        )
        
        self.db.add(notification)
        self.db.flush()
        
        return notification

    def update_delivery_status(
        self,
        notification_id: UUID,
        status: str,
    ) -> SavedSearchNotification:
        """
        Update notification delivery status.
        
        Args:
            notification_id: Notification ID
            status: Delivery status
            
        Returns:
            Updated SavedSearchNotification instance
        """
        notification = self.find_by_id(notification_id)
        if not notification:
            raise ValueError(f"Notification not found: {notification_id}")
        
        notification.delivery_status = status
        
        if status in ["sent", "delivered"]:
            notification.delivered_at = datetime.utcnow()
        
        self.db.flush()
        return notification

    def mark_notification_opened(
        self,
        notification_id: UUID,
    ) -> SavedSearchNotification:
        """
        Mark notification as opened.
        
        Args:
            notification_id: Notification ID
            
        Returns:
            Updated SavedSearchNotification instance
        """
        notification = self.find_by_id(notification_id)
        if not notification:
            raise ValueError(f"Notification not found: {notification_id}")
        
        notification.was_opened = True
        notification.opened_at = datetime.utcnow()
        
        self.db.flush()
        return notification

    def track_link_click(
        self,
        notification_id: UUID,
    ) -> SavedSearchNotification:
        """
        Track link click in notification.
        
        Args:
            notification_id: Notification ID
            
        Returns:
            Updated SavedSearchNotification instance
        """
        notification = self.find_by_id(notification_id)
        if not notification:
            raise ValueError(f"Notification not found: {notification_id}")
        
        notification.links_clicked += 1
        
        self.db.flush()
        return notification

    def get_notification_history(
        self,
        saved_search_id: UUID,
        limit: int = 20,
    ) -> List[SavedSearchNotification]:
        """
        Get notification history for a saved search.
        
        Args:
            saved_search_id: Saved search ID
            limit: Maximum notifications to return
            
        Returns:
            List of notifications
        """
        query = (
            select(SavedSearchNotification)
            .where(SavedSearchNotification.saved_search_id == saved_search_id)
            .order_by(desc(SavedSearchNotification.sent_at))
            .limit(limit)
        )
        
        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_notification_performance(
        self,
        saved_search_id: UUID,
    ) -> Dict:
        """
        Get notification performance metrics.
        
        Args:
            saved_search_id: Saved search ID
            
        Returns:
            Dictionary containing performance metrics
        """
        query = select(SavedSearchNotification).where(
            SavedSearchNotification.saved_search_id == saved_search_id
        )
        
        result = self.db.execute(query)
        notifications = list(result.scalars().all())
        
        if not notifications:
            return {
                "total_notifications": 0,
                "delivery_rate": Decimal("0.00"),
                "open_rate": Decimal("0.00"),
                "click_rate": Decimal("0.00"),
            }
        
        total = len(notifications)
        delivered = sum(1 for n in notifications if n.is_successful)
        opened = sum(1 for n in notifications if n.was_opened)
        clicked = sum(1 for n in notifications if n.links_clicked > 0)
        
        return {
            "total_notifications": total,
            "delivery_rate": (Decimal(delivered) / total * 100).quantize(Decimal("0.01")),
            "open_rate": (Decimal(opened) / total * 100).quantize(Decimal("0.01")) if total > 0 else Decimal("0.00"),
            "click_rate": (Decimal(clicked) / total * 100).quantize(Decimal("0.01")) if total > 0 else Decimal("0.00"),
        }