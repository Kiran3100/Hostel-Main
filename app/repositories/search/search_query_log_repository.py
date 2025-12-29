"""
Search Query Log Repository

Comprehensive repository for search query logging, session tracking,
and saved search management with advanced analytics and optimization.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import func, and_, or_, desc, asc, case, cast, extract
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.dialects.postgresql import insert

from app.models.search.search_query_log import (
    SearchQueryLog,
    SearchSession,
    SavedSearch
)
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.pagination import PaginationManager
from app.core.exceptions import NotFoundException, ValidationException


class SearchQueryLogRepository(BaseRepository[SearchQueryLog]):
    """
    Repository for search query logging with comprehensive analytics,
    performance tracking, and user behavior analysis.
    """

    def __init__(self, db: Session):
        super().__init__(SearchQueryLog, db)
        self.pagination_manager = PaginationManager()

    # ===== Core CRUD Operations =====

    def create_query_log(
        self,
        query_data: Dict[str, Any],
        user_id: Optional[UUID] = None,
        visitor_id: Optional[UUID] = None,
        session_id: Optional[str] = None
    ) -> SearchQueryLog:
        """
        Create a new search query log entry.

        Args:
            query_data: Complete query data dictionary
            user_id: Optional user ID
            visitor_id: Optional visitor ID
            session_id: Optional session ID

        Returns:
            Created SearchQueryLog instance
        """
        try:
            # Prepare log entry
            log_entry = SearchQueryLog(
                user_id=user_id,
                visitor_id=visitor_id,
                session_id=session_id or self._generate_session_id(),
                **query_data
            )

            self.db.add(log_entry)
            self.db.commit()
            self.db.refresh(log_entry)

            return log_entry

        except Exception as e:
            self.db.rollback()
            raise ValidationException(f"Failed to create query log: {str(e)}")

    def bulk_create_query_logs(
        self,
        query_logs: List[Dict[str, Any]],
        batch_size: int = 1000
    ) -> List[SearchQueryLog]:
        """
        Bulk insert query logs for high-volume logging.

        Args:
            query_logs: List of query log dictionaries
            batch_size: Batch size for insertion

        Returns:
            List of created SearchQueryLog instances
        """
        created_logs = []

        try:
            for i in range(0, len(query_logs), batch_size):
                batch = query_logs[i:i + batch_size]
                
                stmt = insert(SearchQueryLog).values(batch)
                stmt = stmt.on_conflict_do_nothing()
                
                self.db.execute(stmt)
                self.db.commit()

            # Fetch created logs (simplified - in production, use RETURNING clause)
            return created_logs

        except Exception as e:
            self.db.rollback()
            raise ValidationException(f"Bulk insert failed: {str(e)}")

    # ===== Query Log Retrieval =====

    def get_by_id(
        self,
        log_id: UUID,
        include_relationships: bool = False
    ) -> SearchQueryLog:
        """Get search query log by ID."""
        query = self.db.query(SearchQueryLog).filter(
            SearchQueryLog.id == log_id
        )

        if include_relationships:
            query = query.options(
                joinedload(SearchQueryLog.user),
                joinedload(SearchQueryLog.visitor),
                joinedload(SearchQueryLog.booking),
                joinedload(SearchQueryLog.saved_search)
            )

        log = query.first()
        if not log:
            raise NotFoundException(f"Search query log {log_id} not found")

        return log

    def get_user_search_history(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False
    ) -> Tuple[List[SearchQueryLog], int]:
        """
        Get search history for a specific user.

        Args:
            user_id: User ID
            limit: Maximum results
            offset: Offset for pagination
            include_deleted: Include soft-deleted logs

        Returns:
            Tuple of (search logs, total count)
        """
        query = self.db.query(SearchQueryLog).filter(
            SearchQueryLog.user_id == user_id
        )

        if not include_deleted:
            query = query.filter(SearchQueryLog.deleted_at.is_(None))

        # Get total count
        total = query.count()

        # Get paginated results
        logs = query.order_by(
            desc(SearchQueryLog.created_at)
        ).limit(limit).offset(offset).all()

        return logs, total

    def get_session_queries(
        self,
        session_id: str,
        order_by_created: bool = True
    ) -> List[SearchQueryLog]:
        """
        Get all queries in a search session.

        Args:
            session_id: Session ID
            order_by_created: Order by creation time

        Returns:
            List of search query logs
        """
        query = self.db.query(SearchQueryLog).filter(
            SearchQueryLog.session_id == session_id,
            SearchQueryLog.deleted_at.is_(None)
        )

        if order_by_created:
            query = query.order_by(asc(SearchQueryLog.created_at))

        return query.all()

    def get_zero_result_queries(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[SearchQueryLog]:
        """
        Get queries that returned zero results.

        Args:
            start_date: Start date filter
            end_date: End date filter
            limit: Maximum results

        Returns:
            List of zero-result search logs
        """
        query = self.db.query(SearchQueryLog).filter(
            SearchQueryLog.zero_results == True,
            SearchQueryLog.deleted_at.is_(None)
        )

        if start_date:
            query = query.filter(SearchQueryLog.created_at >= start_date)
        if end_date:
            query = query.filter(SearchQueryLog.created_at <= end_date)

        return query.order_by(
            desc(SearchQueryLog.created_at)
        ).limit(limit).all()

    # ===== Search Analytics =====

    def get_search_statistics(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[UUID] = None,
        group_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive search statistics for a date range.

        Args:
            start_date: Start date
            end_date: End date
            user_id: Optional user filter
            group_by: Optional grouping (daily, weekly, monthly)

        Returns:
            Dictionary of search statistics
        """
        query = self.db.query(SearchQueryLog).filter(
            SearchQueryLog.created_at.between(start_date, end_date),
            SearchQueryLog.deleted_at.is_(None)
        )

        if user_id:
            query = query.filter(SearchQueryLog.user_id == user_id)

        # Basic statistics
        total_searches = query.count()
        zero_results = query.filter(SearchQueryLog.zero_results == True).count()
        with_clicks = query.filter(SearchQueryLog.has_clicks == True).count()
        resulted_in_booking = query.filter(
            SearchQueryLog.resulted_in_booking == True
        ).count()

        # Performance metrics
        avg_execution_time = query.with_entities(
            func.avg(SearchQueryLog.execution_time_ms)
        ).scalar() or 0

        avg_results = query.with_entities(
            func.avg(SearchQueryLog.results_count)
        ).scalar() or 0

        # Calculate rates
        zero_result_rate = (zero_results / total_searches * 100) if total_searches > 0 else 0
        click_through_rate = (with_clicks / total_searches * 100) if total_searches > 0 else 0
        booking_conversion_rate = (resulted_in_booking / total_searches * 100) if total_searches > 0 else 0

        statistics = {
            'total_searches': total_searches,
            'zero_results': zero_results,
            'zero_result_rate': round(zero_result_rate, 2),
            'searches_with_clicks': with_clicks,
            'click_through_rate': round(click_through_rate, 2),
            'resulted_in_booking': resulted_in_booking,
            'booking_conversion_rate': round(booking_conversion_rate, 2),
            'avg_execution_time_ms': round(avg_execution_time, 2),
            'avg_results_count': round(avg_results, 2),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }

        # Add grouping if requested
        if group_by:
            statistics['grouped_data'] = self._get_grouped_statistics(
                query, group_by
            )

        return statistics

    def get_popular_search_terms(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 20,
        min_searches: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get most popular search terms in date range.

        Args:
            start_date: Start date
            end_date: End date
            limit: Maximum results
            min_searches: Minimum search count threshold

        Returns:
            List of popular search terms with counts
        """
        results = self.db.query(
            SearchQueryLog.normalized_query,
            func.count(SearchQueryLog.id).label('search_count'),
            func.count(func.distinct(SearchQueryLog.user_id)).label('unique_users'),
            func.avg(SearchQueryLog.results_count).label('avg_results'),
            func.sum(
                case([(SearchQueryLog.has_clicks == True, 1)], else_=0)
            ).label('clicks'),
            func.sum(
                case([(SearchQueryLog.resulted_in_booking == True, 1)], else_=0)
            ).label('bookings')
        ).filter(
            SearchQueryLog.created_at.between(start_date, end_date),
            SearchQueryLog.normalized_query.isnot(None),
            SearchQueryLog.normalized_query != '',
            SearchQueryLog.deleted_at.is_(None)
        ).group_by(
            SearchQueryLog.normalized_query
        ).having(
            func.count(SearchQueryLog.id) >= min_searches
        ).order_by(
            desc('search_count')
        ).limit(limit).all()

        popular_terms = []
        for result in results:
            term_data = {
                'term': result.normalized_query,
                'search_count': result.search_count,
                'unique_users': result.unique_users,
                'avg_results': float(result.avg_results or 0),
                'total_clicks': result.clicks,
                'total_bookings': result.bookings,
                'click_through_rate': round(
                    (result.clicks / result.search_count * 100) if result.search_count > 0 else 0,
                    2
                ),
                'booking_conversion_rate': round(
                    (result.bookings / result.search_count * 100) if result.search_count > 0 else 0,
                    2
                )
            }
            popular_terms.append(term_data)

        return popular_terms

    def get_search_filters_usage(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Analyze search filter usage patterns.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary of filter usage statistics
        """
        query = self.db.query(SearchQueryLog).filter(
            SearchQueryLog.created_at.between(start_date, end_date),
            SearchQueryLog.deleted_at.is_(None)
        )

        total_searches = query.count()

        # Location filters
        with_city = query.filter(SearchQueryLog.city.isnot(None)).count()
        with_state = query.filter(SearchQueryLog.state.isnot(None)).count()
        with_coordinates = query.filter(
            and_(
                SearchQueryLog.latitude.isnot(None),
                SearchQueryLog.longitude.isnot(None)
            )
        ).count()

        # Hostel type filters
        with_hostel_type = query.filter(
            SearchQueryLog.hostel_type.isnot(None)
        ).count()

        # Price filters
        with_price_range = query.filter(
            or_(
                SearchQueryLog.min_price.isnot(None),
                SearchQueryLog.max_price.isnot(None)
            )
        ).count()

        # Amenities
        with_amenities = query.filter(
            or_(
                SearchQueryLog.required_amenities.isnot(None),
                SearchQueryLog.optional_amenities.isnot(None)
            )
        ).count()

        # Rating filter
        with_rating = query.filter(SearchQueryLog.min_rating.isnot(None)).count()

        # Availability filters
        with_dates = query.filter(
            and_(
                SearchQueryLog.check_in_date.isnot(None),
                SearchQueryLog.check_out_date.isnot(None)
            )
        ).count()

        return {
            'total_searches': total_searches,
            'filters': {
                'city': {
                    'count': with_city,
                    'percentage': round((with_city / total_searches * 100) if total_searches > 0 else 0, 2)
                },
                'state': {
                    'count': with_state,
                    'percentage': round((with_state / total_searches * 100) if total_searches > 0 else 0, 2)
                },
                'coordinates': {
                    'count': with_coordinates,
                    'percentage': round((with_coordinates / total_searches * 100) if total_searches > 0 else 0, 2)
                },
                'hostel_type': {
                    'count': with_hostel_type,
                    'percentage': round((with_hostel_type / total_searches * 100) if total_searches > 0 else 0, 2)
                },
                'price_range': {
                    'count': with_price_range,
                    'percentage': round((with_price_range / total_searches * 100) if total_searches > 0 else 0, 2)
                },
                'amenities': {
                    'count': with_amenities,
                    'percentage': round((with_amenities / total_searches * 100) if total_searches > 0 else 0, 2)
                },
                'rating': {
                    'count': with_rating,
                    'percentage': round((with_rating / total_searches * 100) if total_searches > 0 else 0, 2)
                },
                'dates': {
                    'count': with_dates,
                    'percentage': round((with_dates / total_searches * 100) if total_searches > 0 else 0, 2)
                }
            }
        }

    def get_performance_metrics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get search performance metrics.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary of performance metrics
        """
        query = self.db.query(SearchQueryLog).filter(
            SearchQueryLog.created_at.between(start_date, end_date),
            SearchQueryLog.deleted_at.is_(None)
        )

        # Execution time metrics
        execution_stats = query.with_entities(
            func.avg(SearchQueryLog.execution_time_ms).label('avg'),
            func.min(SearchQueryLog.execution_time_ms).label('min'),
            func.max(SearchQueryLog.execution_time_ms).label('max'),
            func.percentile_cont(0.50).within_group(
                SearchQueryLog.execution_time_ms
            ).label('p50'),
            func.percentile_cont(0.95).within_group(
                SearchQueryLog.execution_time_ms
            ).label('p95'),
            func.percentile_cont(0.99).within_group(
                SearchQueryLog.execution_time_ms
            ).label('p99')
        ).first()

        # Cache performance
        total_queries = query.count()
        cache_hits = query.filter(SearchQueryLog.cache_hit == True).count()
        cache_hit_rate = (cache_hits / total_queries * 100) if total_queries > 0 else 0

        # Error rate
        with_errors = query.filter(SearchQueryLog.had_errors == True).count()
        error_rate = (with_errors / total_queries * 100) if total_queries > 0 else 0

        return {
            'execution_time': {
                'avg_ms': round(execution_stats.avg or 0, 2),
                'min_ms': execution_stats.min or 0,
                'max_ms': execution_stats.max or 0,
                'p50_ms': round(execution_stats.p50 or 0, 2),
                'p95_ms': round(execution_stats.p95 or 0, 2),
                'p99_ms': round(execution_stats.p99 or 0, 2)
            },
            'cache': {
                'total_queries': total_queries,
                'cache_hits': cache_hits,
                'cache_misses': total_queries - cache_hits,
                'hit_rate': round(cache_hit_rate, 2)
            },
            'errors': {
                'total_errors': with_errors,
                'error_rate': round(error_rate, 2)
            }
        }

    # ===== Update Operations =====

    def update_click_interaction(
        self,
        log_id: UUID,
        clicked_result_id: UUID,
        position: int,
        click_time_seconds: Optional[int] = None
    ) -> SearchQueryLog:
        """
        Update search log with click interaction.

        Args:
            log_id: Search query log ID
            clicked_result_id: ID of clicked hostel
            position: Position in results
            click_time_seconds: Time to click

        Returns:
            Updated SearchQueryLog
        """
        log = self.get_by_id(log_id)

        # Update clicked results
        if log.clicked_result_ids is None:
            log.clicked_result_ids = []
        if log.clicked_result_positions is None:
            log.clicked_result_positions = []

        log.clicked_result_ids.append(clicked_result_id)
        log.clicked_result_positions.append(position)

        # Update first click
        if log.first_click_position is None:
            log.first_click_position = position
            log.click_time_seconds = click_time_seconds

        log.has_clicks = True

        self.db.commit()
        self.db.refresh(log)

        return log

    def update_conversion(
        self,
        log_id: UUID,
        booking_id: Optional[UUID] = None,
        resulted_in_booking: bool = False,
        resulted_in_inquiry: bool = False
    ) -> SearchQueryLog:
        """
        Update search log with conversion information.

        Args:
            log_id: Search query log ID
            booking_id: Optional booking ID
            resulted_in_booking: Whether resulted in booking
            resulted_in_inquiry: Whether resulted in inquiry

        Returns:
            Updated SearchQueryLog
        """
        log = self.get_by_id(log_id)

        if booking_id:
            log.booking_id = booking_id
            log.resulted_in_booking = True
        
        if resulted_in_booking:
            log.resulted_in_booking = True
        
        if resulted_in_inquiry:
            log.resulted_in_inquiry = True

        self.db.commit()
        self.db.refresh(log)

        return log

    # ===== Helper Methods =====

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        from uuid import uuid4
        return f"search_session_{uuid4()}"

    def _get_grouped_statistics(
        self,
        query,
        group_by: str
    ) -> List[Dict[str, Any]]:
        """
        Get statistics grouped by time period.

        Args:
            query: Base SQLAlchemy query
            group_by: Grouping period (daily, weekly, monthly)

        Returns:
            List of grouped statistics
        """
        # Determine date truncation based on group_by
        if group_by == 'daily':
            date_group = func.date(SearchQueryLog.created_at)
        elif group_by == 'weekly':
            date_group = func.date_trunc('week', SearchQueryLog.created_at)
        elif group_by == 'monthly':
            date_group = func.date_trunc('month', SearchQueryLog.created_at)
        else:
            date_group = func.date(SearchQueryLog.created_at)

        results = query.with_entities(
            date_group.label('period'),
            func.count(SearchQueryLog.id).label('total_searches'),
            func.sum(
                case([(SearchQueryLog.zero_results == True, 1)], else_=0)
            ).label('zero_results'),
            func.sum(
                case([(SearchQueryLog.has_clicks == True, 1)], else_=0)
            ).label('with_clicks'),
            func.avg(SearchQueryLog.execution_time_ms).label('avg_execution_time')
        ).group_by(date_group).order_by(date_group).all()

        grouped_data = []
        for result in results:
            grouped_data.append({
                'period': result.period.isoformat() if hasattr(result.period, 'isoformat') else str(result.period),
                'total_searches': result.total_searches,
                'zero_results': result.zero_results,
                'with_clicks': result.with_clicks,
                'avg_execution_time_ms': round(result.avg_execution_time or 0, 2)
            })

        return grouped_data


class SearchSessionRepository(BaseRepository[SearchSession]):
    """
    Repository for search session tracking with journey analysis,
    conversion tracking, and behavior insights.
    """

    def __init__(self, db: Session):
        super().__init__(SearchSession, db)

    # ===== Core Operations =====

    def create_session(
        self,
        session_id: str,
        user_id: Optional[UUID] = None,
        visitor_id: Optional[UUID] = None,
        **kwargs
    ) -> SearchSession:
        """
        Create a new search session.

        Args:
            session_id: Unique session identifier
            user_id: Optional user ID
            visitor_id: Optional visitor ID
            **kwargs: Additional session data

        Returns:
            Created SearchSession
        """
        try:
            session = SearchSession(
                session_id=session_id,
                user_id=user_id,
                visitor_id=visitor_id,
                start_time=datetime.utcnow(),
                last_activity=datetime.utcnow(),
                is_active=True,
                **kwargs
            )

            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

            return session

        except Exception as e:
            self.db.rollback()
            raise ValidationException(f"Failed to create session: {str(e)}")

    def get_by_session_id(
        self,
        session_id: str,
        include_queries: bool = False
    ) -> Optional[SearchSession]:
        """
        Get session by session ID.

        Args:
            session_id: Session ID
            include_queries: Include related query logs

        Returns:
            SearchSession or None
        """
        query = self.db.query(SearchSession).filter(
            SearchSession.session_id == session_id
        )

        if include_queries:
            query = query.options(selectinload(SearchSession.query_logs))

        return query.first()

    def get_active_session(
        self,
        session_id: str
    ) -> Optional[SearchSession]:
        """Get active session by ID."""
        return self.db.query(SearchSession).filter(
            SearchSession.session_id == session_id,
            SearchSession.is_active == True
        ).first()

    def update_session_activity(
        self,
        session_id: str,
        total_searches: Optional[int] = None,
        total_clicks: Optional[int] = None,
        unique_hostels_clicked: Optional[int] = None
    ) -> SearchSession:
        """
        Update session activity metrics.

        Args:
            session_id: Session ID
            total_searches: Total search count
            total_clicks: Total click count
            unique_hostels_clicked: Unique hostels clicked

        Returns:
            Updated SearchSession
        """
        session = self.get_by_session_id(session_id)
        if not session:
            raise NotFoundException(f"Session {session_id} not found")

        session.last_activity = datetime.utcnow()

        if total_searches is not None:
            session.total_searches = total_searches
        if total_clicks is not None:
            session.total_clicks = total_clicks
        if unique_hostels_clicked is not None:
            session.unique_hostels_clicked = unique_hostels_clicked

        self.db.commit()
        self.db.refresh(session)

        return session

    def end_session(
        self,
        session_id: str
    ) -> SearchSession:
        """
        End a search session and calculate final metrics.

        Args:
            session_id: Session ID

        Returns:
            Updated SearchSession
        """
        session = self.get_by_session_id(session_id)
        if not session:
            raise NotFoundException(f"Session {session_id} not found")

        session.is_active = False
        session.end_time = datetime.utcnow()
        
        # Calculate duration
        if session.start_time:
            duration = session.end_time - session.start_time
            session.duration_seconds = int(duration.total_seconds())

        # Calculate bounce
        if session.total_searches == 1 and session.total_clicks == 0:
            session.bounce = True

        self.db.commit()
        self.db.refresh(session)

        return session

    # ===== Analytics Methods =====

    def get_user_sessions(
        self,
        user_id: UUID,
        limit: int = 20,
        include_active_only: bool = False
    ) -> List[SearchSession]:
        """
        Get search sessions for a user.

        Args:
            user_id: User ID
            limit: Maximum results
            include_active_only: Only active sessions

        Returns:
            List of search sessions
        """
        query = self.db.query(SearchSession).filter(
            SearchSession.user_id == user_id
        )

        if include_active_only:
            query = query.filter(SearchSession.is_active == True)

        return query.order_by(
            desc(SearchSession.start_time)
        ).limit(limit).all()

    def get_session_statistics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get session statistics for date range.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary of session statistics
        """
        query = self.db.query(SearchSession).filter(
            SearchSession.start_time.between(start_date, end_date)
        )

        total_sessions = query.count()
        bounced_sessions = query.filter(SearchSession.bounce == True).count()
        converted_sessions = query.filter(
            SearchSession.resulted_in_booking == True
        ).count()

        # Average metrics
        avg_searches = query.with_entities(
            func.avg(SearchSession.total_searches)
        ).scalar() or 0

        avg_clicks = query.with_entities(
            func.avg(SearchSession.total_clicks)
        ).scalar() or 0

        avg_duration = query.with_entities(
            func.avg(SearchSession.duration_seconds)
        ).scalar() or 0

        return {
            'total_sessions': total_sessions,
            'bounced_sessions': bounced_sessions,
            'bounce_rate': round(
                (bounced_sessions / total_sessions * 100) if total_sessions > 0 else 0,
                2
            ),
            'converted_sessions': converted_sessions,
            'conversion_rate': round(
                (converted_sessions / total_sessions * 100) if total_sessions > 0 else 0,
                2
            ),
            'avg_searches_per_session': round(avg_searches, 2),
            'avg_clicks_per_session': round(avg_clicks, 2),
            'avg_duration_seconds': round(avg_duration, 2)
        }

    def cleanup_inactive_sessions(
        self,
        inactive_hours: int = 24
    ) -> int:
        """
        Mark inactive sessions as ended.

        Args:
            inactive_hours: Hours of inactivity threshold

        Returns:
            Number of sessions cleaned up
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=inactive_hours)

        sessions = self.db.query(SearchSession).filter(
            SearchSession.is_active == True,
            SearchSession.last_activity < cutoff_time
        ).all()

        count = 0
        for session in sessions:
            self.end_session(session.session_id)
            count += 1

        return count


class SavedSearchRepository(BaseRepository[SavedSearch]):
    """
    Repository for saved search management with alert functionality,
    execution tracking, and user preference management.
    """

    def __init__(self, db: Session):
        super().__init__(SavedSearch, db)

    # ===== Core CRUD Operations =====

    def create_saved_search(
        self,
        user_id: UUID,
        name: str,
        search_criteria: Dict[str, Any],
        description: Optional[str] = None,
        is_alert_enabled: bool = False,
        alert_frequency: Optional[str] = None,
        alert_channels: Optional[List[str]] = None
    ) -> SavedSearch:
        """
        Create a new saved search.

        Args:
            user_id: User ID
            name: Search name
            search_criteria: Complete search criteria
            description: Optional description
            is_alert_enabled: Enable alerts
            alert_frequency: Alert frequency
            alert_channels: Alert delivery channels

        Returns:
            Created SavedSearch
        """
        try:
            # Extract quick access fields
            quick_fields = self._extract_quick_fields(search_criteria)

            saved_search = SavedSearch(
                user_id=user_id,
                name=name,
                description=description,
                search_criteria=search_criteria,
                is_alert_enabled=is_alert_enabled,
                alert_frequency=alert_frequency,
                alert_channels=alert_channels,
                **quick_fields
            )

            self.db.add(saved_search)
            self.db.commit()
            self.db.refresh(saved_search)

            return saved_search

        except Exception as e:
            self.db.rollback()
            raise ValidationException(f"Failed to create saved search: {str(e)}")

    def update_saved_search(
        self,
        search_id: UUID,
        **update_data
    ) -> SavedSearch:
        """
        Update saved search.

        Args:
            search_id: Saved search ID
            **update_data: Fields to update

        Returns:
            Updated SavedSearch
        """
        saved_search = self.get_by_id(search_id)
        if not saved_search:
            raise NotFoundException(f"Saved search {search_id} not found")

        # Update search criteria if provided
        if 'search_criteria' in update_data:
            quick_fields = self._extract_quick_fields(update_data['search_criteria'])
            update_data.update(quick_fields)

        for key, value in update_data.items():
            if hasattr(saved_search, key):
                setattr(saved_search, key, value)

        self.db.commit()
        self.db.refresh(saved_search)

        return saved_search

    # ===== Retrieval Methods =====

    def get_user_saved_searches(
        self,
        user_id: UUID,
        active_only: bool = True,
        include_favorites: bool = False
    ) -> List[SavedSearch]:
        """
        Get user's saved searches.

        Args:
            user_id: User ID
            active_only: Only active searches
            include_favorites: Prioritize favorites

        Returns:
            List of saved searches
        """
        query = self.db.query(SavedSearch).filter(
            SavedSearch.user_id == user_id,
            SavedSearch.deleted_at.is_(None)
        )

        if active_only:
            query = query.filter(SavedSearch.is_active == True)

        # Order by favorite, then display order
        if include_favorites:
            query = query.order_by(
                desc(SavedSearch.is_favorite),
                asc(SavedSearch.display_order),
                desc(SavedSearch.last_executed_at)
            )
        else:
            query = query.order_by(
                asc(SavedSearch.display_order),
                desc(SavedSearch.last_executed_at)
            )

        return query.all()

    def get_searches_for_alerts(
        self,
        alert_frequency: Optional[str] = None
    ) -> List[SavedSearch]:
        """
        Get saved searches that need alerts sent.

        Args:
            alert_frequency: Filter by alert frequency

        Returns:
            List of saved searches needing alerts
        """
        now = datetime.utcnow()

        query = self.db.query(SavedSearch).filter(
            SavedSearch.is_alert_enabled == True,
            SavedSearch.is_active == True,
            SavedSearch.deleted_at.is_(None),
            or_(
                SavedSearch.next_alert_scheduled.is_(None),
                SavedSearch.next_alert_scheduled <= now
            )
        )

        if alert_frequency:
            query = query.filter(SavedSearch.alert_frequency == alert_frequency)

        return query.all()

    # ===== Execution Tracking =====

    def record_execution(
        self,
        search_id: UUID,
        result_count: int
    ) -> SavedSearch:
        """
        Record saved search execution.

        Args:
            search_id: Saved search ID
            result_count: Number of results

        Returns:
            Updated SavedSearch
        """
        saved_search = self.get_by_id(search_id)
        if not saved_search:
            raise NotFoundException(f"Saved search {search_id} not found")

        saved_search.last_executed_at = datetime.utcnow()
        saved_search.execution_count += 1
        saved_search.last_result_count = result_count

        self.db.commit()
        self.db.refresh(saved_search)

        return saved_search

    def update_alert_status(
        self,
        search_id: UUID,
        alert_sent: bool = True
    ) -> SavedSearch:
        """
        Update alert status after sending.

        Args:
            search_id: Saved search ID
            alert_sent: Whether alert was sent

        Returns:
            Updated SavedSearch
        """
        saved_search = self.get_by_id(search_id)
        if not saved_search:
            raise NotFoundException(f"Saved search {search_id} not found")

        if alert_sent:
            saved_search.last_alert_sent = datetime.utcnow()
            saved_search.alert_count += 1

            # Calculate next alert time based on frequency
            if saved_search.alert_frequency:
                saved_search.next_alert_scheduled = self._calculate_next_alert(
                    saved_search.alert_frequency
                )

        self.db.commit()
        self.db.refresh(saved_search)

        return saved_search

    # ===== Toggle Operations =====

    def toggle_favorite(
        self,
        search_id: UUID
    ) -> SavedSearch:
        """Toggle favorite status."""
        saved_search = self.get_by_id(search_id)
        if not saved_search:
            raise NotFoundException(f"Saved search {search_id} not found")

        saved_search.is_favorite = not saved_search.is_favorite

        self.db.commit()
        self.db.refresh(saved_search)

        return saved_search

    def toggle_alerts(
        self,
        search_id: UUID
    ) -> SavedSearch:
        """Toggle alert status."""
        saved_search = self.get_by_id(search_id)
        if not saved_search:
            raise NotFoundException(f"Saved search {search_id} not found")

        saved_search.is_alert_enabled = not saved_search.is_alert_enabled

        # Set next alert time if enabling
        if saved_search.is_alert_enabled and saved_search.alert_frequency:
            saved_search.next_alert_scheduled = self._calculate_next_alert(
                saved_search.alert_frequency
            )

        self.db.commit()
        self.db.refresh(saved_search)

        return saved_search

    # ===== Helper Methods =====

    def _extract_quick_fields(
        self,
        search_criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract quick access fields from search criteria."""
        return {
            'query': search_criteria.get('query'),
            'city': search_criteria.get('city'),
            'state': search_criteria.get('state'),
            'hostel_type': search_criteria.get('hostel_type'),
            'min_price': search_criteria.get('min_price'),
            'max_price': search_criteria.get('max_price')
        }

    def _calculate_next_alert(
        self,
        frequency: str
    ) -> datetime:
        """Calculate next alert time based on frequency."""
        now = datetime.utcnow()

        if frequency == 'daily':
            return now + timedelta(days=1)
        elif frequency == 'weekly':
            return now + timedelta(weeks=1)
        elif frequency == 'instant':
            return now + timedelta(hours=1)  # Check hourly for instant
        else:
            return now + timedelta(days=1)  # Default to daily