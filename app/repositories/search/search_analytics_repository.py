"""
Search Analytics Repository

Comprehensive repository for search analytics, performance tracking,
trending analysis, and search optimization insights.
"""

from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import func, and_, or_, desc, asc, case, cast, extract, distinct
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.dialects.postgresql import insert

from app.models.search.search_analytics import (
    SearchTermStats,
    SearchMetrics,
    PopularSearchTerm,
    TrendingSearch,
    ZeroResultTerm,
    SearchAnalyticsReport
)
from app.repositories.base.base_repository import BaseRepository
from app.core1.exceptions import NotFoundException, ValidationException


class SearchTermStatsRepository(BaseRepository[SearchTermStats]):
    """
    Repository for search term statistics with trend analysis,
    performance tracking, and search optimization.
    """

    def __init__(self, db: Session):
        super().__init__(SearchTermStats, db)

    # ===== Core Operations =====

    def create_or_update_stats(
        self,
        term: str,
        normalized_term: str,
        period_start: date,
        period_end: date,
        period_type: str = "daily",
        stats_data: Optional[Dict[str, Any]] = None
    ) -> SearchTermStats:
        """
        Create or update search term statistics.

        Args:
            term: Original search term
            normalized_term: Normalized term
            period_start: Period start date
            period_end: Period end date
            period_type: Period type (daily, weekly, monthly)
            stats_data: Statistics data

        Returns:
            SearchTermStats instance
        """
        try:
            # Check if stats exist
            existing = self.db.query(SearchTermStats).filter(
                SearchTermStats.normalized_term == normalized_term,
                SearchTermStats.period_start == period_start,
                SearchTermStats.period_type == period_type
            ).first()

            if existing:
                # Update existing stats
                if stats_data:
                    for key, value in stats_data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                
                self.db.commit()
                self.db.refresh(existing)
                return existing
            else:
                # Create new stats
                import hashlib
                term_hash = hashlib.sha256(normalized_term.encode()).hexdigest()

                stats = SearchTermStats(
                    term=term,
                    normalized_term=normalized_term,
                    term_hash=term_hash,
                    period_start=period_start,
                    period_end=period_end,
                    period_type=period_type,
                    first_searched_at=datetime.utcnow(),
                    last_searched_at=datetime.utcnow(),
                    **(stats_data or {})
                )

                self.db.add(stats)
                self.db.commit()
                self.db.refresh(stats)

                return stats

        except Exception as e:
            self.db.rollback()
            raise ValidationException(f"Failed to create/update stats: {str(e)}")

    def get_term_stats(
        self,
        normalized_term: str,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None,
        period_type: str = "daily"
    ) -> List[SearchTermStats]:
        """
        Get statistics for a specific term.

        Args:
            normalized_term: Normalized search term
            period_start: Optional start date
            period_end: Optional end date
            period_type: Period type filter

        Returns:
            List of SearchTermStats
        """
        query = self.db.query(SearchTermStats).filter(
            SearchTermStats.normalized_term == normalized_term,
            SearchTermStats.period_type == period_type
        )

        if period_start:
            query = query.filter(SearchTermStats.period_start >= period_start)
        if period_end:
            query = query.filter(SearchTermStats.period_end <= period_end)

        return query.order_by(desc(SearchTermStats.period_start)).all()

    def get_trending_terms(
        self,
        period_start: date,
        period_type: str = "daily",
        limit: int = 20,
        min_growth_rate: Decimal = Decimal('10.0')
    ) -> List[SearchTermStats]:
        """
        Get trending search terms.

        Args:
            period_start: Period to analyze
            period_type: Period type
            limit: Maximum results
            min_growth_rate: Minimum growth rate percentage

        Returns:
            List of trending terms
        """
        return self.db.query(SearchTermStats).filter(
            SearchTermStats.period_start == period_start,
            SearchTermStats.period_type == period_type,
            SearchTermStats.trend_direction == 'rising',
            SearchTermStats.growth_rate >= min_growth_rate
        ).order_by(
            desc(SearchTermStats.velocity_score),
            desc(SearchTermStats.growth_rate)
        ).limit(limit).all()

    def get_top_performing_terms(
        self,
        period_start: date,
        period_end: date,
        period_type: str = "daily",
        metric: str = "search_count",
        limit: int = 50
    ) -> List[SearchTermStats]:
        """
        Get top performing terms by metric.

        Args:
            period_start: Start date
            period_end: End date
            period_type: Period type
            metric: Metric to sort by
            limit: Maximum results

        Returns:
            List of top performing terms
        """
        query = self.db.query(SearchTermStats).filter(
            SearchTermStats.period_start >= period_start,
            SearchTermStats.period_end <= period_end,
            SearchTermStats.period_type == period_type
        )

        # Order by specified metric
        if metric == "search_count":
            query = query.order_by(desc(SearchTermStats.search_count))
        elif metric == "click_through_rate":
            query = query.order_by(desc(SearchTermStats.click_through_rate))
        elif metric == "booking_conversion_rate":
            query = query.order_by(desc(SearchTermStats.booking_conversion_rate))
        elif metric == "unique_users":
            query = query.order_by(desc(SearchTermStats.unique_users))
        else:
            query = query.order_by(desc(SearchTermStats.search_count))

        return query.limit(limit).all()

    def get_poor_performing_terms(
        self,
        period_start: date,
        period_end: date,
        min_searches: int = 10,
        max_ctr: Decimal = Decimal('5.0')
    ) -> List[SearchTermStats]:
        """
        Get poorly performing terms for optimization.

        Args:
            period_start: Start date
            period_end: End date
            min_searches: Minimum search count
            max_ctr: Maximum CTR threshold

        Returns:
            List of poor performing terms
        """
        return self.db.query(SearchTermStats).filter(
            SearchTermStats.period_start >= period_start,
            SearchTermStats.period_end <= period_end,
            SearchTermStats.search_count >= min_searches,
            SearchTermStats.click_through_rate <= max_ctr
        ).order_by(
            asc(SearchTermStats.click_through_rate),
            desc(SearchTermStats.search_count)
        ).all()

    def calculate_term_trends(
        self,
        normalized_term: str,
        current_period: date,
        period_type: str = "daily"
    ) -> Dict[str, Any]:
        """
        Calculate trend metrics for a term.

        Args:
            normalized_term: Normalized term
            current_period: Current period date
            period_type: Period type

        Returns:
            Dictionary of trend metrics
        """
        # Get current and previous period stats
        current_stats = self.db.query(SearchTermStats).filter(
            SearchTermStats.normalized_term == normalized_term,
            SearchTermStats.period_start == current_period,
            SearchTermStats.period_type == period_type
        ).first()

        if not current_stats:
            return {}

        # Calculate previous period date
        if period_type == "daily":
            previous_period = current_period - timedelta(days=1)
        elif period_type == "weekly":
            previous_period = current_period - timedelta(weeks=1)
        elif period_type == "monthly":
            previous_period = current_period - timedelta(days=30)
        else:
            previous_period = current_period - timedelta(days=1)

        previous_stats = self.db.query(SearchTermStats).filter(
            SearchTermStats.normalized_term == normalized_term,
            SearchTermStats.period_start == previous_period,
            SearchTermStats.period_type == period_type
        ).first()

        if not previous_stats or previous_stats.search_count == 0:
            return {
                'current_count': current_stats.search_count,
                'previous_count': 0,
                'growth_rate': Decimal('0'),
                'trend_direction': 'new'
            }

        # Calculate metrics
        growth_rate = (
            (current_stats.search_count - previous_stats.search_count) /
            previous_stats.search_count * 100
        )

        trend_direction = 'stable'
        if growth_rate > 10:
            trend_direction = 'rising'
        elif growth_rate < -10:
            trend_direction = 'falling'

        return {
            'current_count': current_stats.search_count,
            'previous_count': previous_stats.search_count,
            'growth_rate': round(growth_rate, 2),
            'trend_direction': trend_direction,
            'velocity_score': self._calculate_velocity_score(
                current_stats.search_count,
                previous_stats.search_count
            )
        }

    def _calculate_velocity_score(
        self,
        current: int,
        previous: int
    ) -> Decimal:
        """Calculate velocity score for trending."""
        if previous == 0:
            return Decimal('0')
        
        growth = (current - previous) / previous
        acceleration = current - previous
        
        # Weighted score: growth rate + absolute acceleration
        velocity = (growth * 100) + (acceleration * 0.1)
        
        return Decimal(str(round(velocity, 4)))


class SearchMetricsRepository(BaseRepository[SearchMetrics]):
    """
    Repository for aggregated search metrics with performance tracking,
    quality monitoring, and optimization insights.
    """

    def __init__(self, db: Session):
        super().__init__(SearchMetrics, db)

    # ===== Core Operations =====

    def create_or_update_metrics(
        self,
        metric_date: date,
        period_type: str,
        period_start: datetime,
        period_end: datetime,
        metrics_data: Dict[str, Any],
        hostel_id: Optional[UUID] = None
    ) -> SearchMetrics:
        """
        Create or update search metrics.

        Args:
            metric_date: Metric date
            period_type: Period type
            period_start: Period start datetime
            period_end: Period end datetime
            metrics_data: Metrics data
            hostel_id: Optional hostel ID

        Returns:
            SearchMetrics instance
        """
        try:
            # Check existing
            existing = self.db.query(SearchMetrics).filter(
                SearchMetrics.metric_date == metric_date,
                SearchMetrics.period_type == period_type,
                SearchMetrics.hostel_id == hostel_id
            ).first()

            if existing:
                for key, value in metrics_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                
                self.db.commit()
                self.db.refresh(existing)
                return existing
            else:
                metrics = SearchMetrics(
                    metric_date=metric_date,
                    period_type=period_type,
                    period_start=period_start,
                    period_end=period_end,
                    hostel_id=hostel_id,
                    **metrics_data
                )

                self.db.add(metrics)
                self.db.commit()
                self.db.refresh(metrics)

                return metrics

        except Exception as e:
            self.db.rollback()
            raise ValidationException(f"Failed to create/update metrics: {str(e)}")

    def get_metrics(
        self,
        start_date: date,
        end_date: date,
        period_type: str = "daily",
        hostel_id: Optional[UUID] = None
    ) -> List[SearchMetrics]:
        """
        Get search metrics for date range.

        Args:
            start_date: Start date
            end_date: End date
            period_type: Period type
            hostel_id: Optional hostel filter

        Returns:
            List of SearchMetrics
        """
        query = self.db.query(SearchMetrics).filter(
            SearchMetrics.metric_date.between(start_date, end_date),
            SearchMetrics.period_type == period_type
        )

        if hostel_id:
            query = query.filter(SearchMetrics.hostel_id == hostel_id)
        else:
            query = query.filter(SearchMetrics.hostel_id.is_(None))

        return query.order_by(asc(SearchMetrics.metric_date)).all()

    def get_latest_metrics(
        self,
        period_type: str = "daily",
        hostel_id: Optional[UUID] = None
    ) -> Optional[SearchMetrics]:
        """Get most recent metrics."""
        query = self.db.query(SearchMetrics).filter(
            SearchMetrics.period_type == period_type
        )

        if hostel_id:
            query = query.filter(SearchMetrics.hostel_id == hostel_id)
        else:
            query = query.filter(SearchMetrics.hostel_id.is_(None))

        return query.order_by(desc(SearchMetrics.metric_date)).first()

    def get_aggregated_metrics(
        self,
        start_date: date,
        end_date: date,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated metrics across date range.

        Args:
            start_date: Start date
            end_date: End date
            hostel_id: Optional hostel filter

        Returns:
            Dictionary of aggregated metrics
        """
        query = self.db.query(SearchMetrics).filter(
            SearchMetrics.metric_date.between(start_date, end_date)
        )

        if hostel_id:
            query = query.filter(SearchMetrics.hostel_id == hostel_id)
        else:
            query = query.filter(SearchMetrics.hostel_id.is_(None))

        metrics = query.all()

        if not metrics:
            return {}

        # Aggregate
        total_searches = sum(m.total_searches for m in metrics)
        total_users = sum(m.unique_users for m in metrics)
        total_zero_results = sum(m.zero_result_searches for m in metrics)
        total_clicks = sum(m.total_clicks for m in metrics)
        total_bookings = sum(m.searches_resulting_in_bookings for m in metrics)

        avg_response_time = sum(
            m.avg_response_time_ms for m in metrics
        ) / len(metrics) if metrics else 0

        return {
            'total_searches': total_searches,
            'unique_users': total_users,
            'zero_result_searches': total_zero_results,
            'zero_result_rate': round(
                (total_zero_results / total_searches * 100) if total_searches > 0 else 0,
                2
            ),
            'total_clicks': total_clicks,
            'click_through_rate': round(
                (total_clicks / total_searches * 100) if total_searches > 0 else 0,
                2
            ),
            'searches_resulting_in_bookings': total_bookings,
            'booking_conversion_rate': round(
                (total_bookings / total_searches * 100) if total_searches > 0 else 0,
                2
            ),
            'avg_response_time_ms': round(avg_response_time, 2),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': (end_date - start_date).days + 1
            }
        }

    def compare_periods(
        self,
        current_start: date,
        current_end: date,
        previous_start: date,
        previous_end: date,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Compare metrics between two periods.

        Args:
            current_start: Current period start
            current_end: Current period end
            previous_start: Previous period start
            previous_end: Previous period end
            hostel_id: Optional hostel filter

        Returns:
            Comparison dictionary
        """
        current = self.get_aggregated_metrics(
            current_start, current_end, hostel_id
        )
        previous = self.get_aggregated_metrics(
            previous_start, previous_end, hostel_id
        )

        if not current or not previous:
            return {}

        def calculate_change(current_val, previous_val):
            if previous_val == 0:
                return 0
            return round(
                ((current_val - previous_val) / previous_val * 100),
                2
            )

        return {
            'current_period': current,
            'previous_period': previous,
            'changes': {
                'total_searches': {
                    'absolute': current['total_searches'] - previous['total_searches'],
                    'percentage': calculate_change(
                        current['total_searches'],
                        previous['total_searches']
                    )
                },
                'unique_users': {
                    'absolute': current['unique_users'] - previous['unique_users'],
                    'percentage': calculate_change(
                        current['unique_users'],
                        previous['unique_users']
                    )
                },
                'zero_result_rate': {
                    'absolute': current['zero_result_rate'] - previous['zero_result_rate'],
                    'percentage': calculate_change(
                        current['zero_result_rate'],
                        previous['zero_result_rate']
                    )
                },
                'click_through_rate': {
                    'absolute': current['click_through_rate'] - previous['click_through_rate'],
                    'percentage': calculate_change(
                        current['click_through_rate'],
                        previous['click_through_rate']
                    )
                },
                'booking_conversion_rate': {
                    'absolute': current['booking_conversion_rate'] - previous['booking_conversion_rate'],
                    'percentage': calculate_change(
                        current['booking_conversion_rate'],
                        previous['booking_conversion_rate']
                    )
                }
            }
        }


class PopularSearchTermRepository(BaseRepository[PopularSearchTerm]):
    """
    Repository for popular search terms with ranking,
    trending analysis, and display optimization.
    """

    def __init__(self, db: Session):
        super().__init__(PopularSearchTerm, db)

    def create_or_update_popular_term(
        self,
        term: str,
        normalized_term: str,
        period_start: date,
        period_end: date,
        rank: int,
        term_data: Dict[str, Any],
        period_type: str = "weekly"
    ) -> PopularSearchTerm:
        """Create or update popular search term."""
        try:
            existing = self.db.query(PopularSearchTerm).filter(
                PopularSearchTerm.normalized_term == normalized_term,
                PopularSearchTerm.period_start == period_start,
                PopularSearchTerm.period_type == period_type
            ).first()

            if existing:
                existing.rank = rank
                existing.previous_rank = existing.rank
                existing.rank_change = existing.previous_rank - rank if existing.previous_rank else 0
                
                for key, value in term_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                
                self.db.commit()
                self.db.refresh(existing)
                return existing
            else:
                popular_term = PopularSearchTerm(
                    term=term,
                    normalized_term=normalized_term,
                    rank=rank,
                    period_start=period_start,
                    period_end=period_end,
                    period_type=period_type,
                    **term_data
                )

                self.db.add(popular_term)
                self.db.commit()
                self.db.refresh(popular_term)

                return popular_term

        except Exception as e:
            self.db.rollback()
            raise ValidationException(f"Failed to create popular term: {str(e)}")

    def get_popular_terms(
        self,
        period_start: date,
        period_type: str = "weekly",
        limit: int = 20,
        city: Optional[str] = None,
        hostel_type: Optional[str] = None,
        active_only: bool = True
    ) -> List[PopularSearchTerm]:
        """Get popular search terms for period."""
        query = self.db.query(PopularSearchTerm).filter(
            PopularSearchTerm.period_start == period_start,
            PopularSearchTerm.period_type == period_type
        )

        if active_only:
            query = query.filter(PopularSearchTerm.is_active == True)

        if city:
            query = query.filter(PopularSearchTerm.city == city)

        if hostel_type:
            query = query.filter(PopularSearchTerm.hostel_type == hostel_type)

        return query.order_by(asc(PopularSearchTerm.rank)).limit(limit).all()

    def get_featured_terms(
        self,
        limit: int = 10
    ) -> List[PopularSearchTerm]:
        """Get featured popular terms."""
        return self.db.query(PopularSearchTerm).filter(
            PopularSearchTerm.is_featured == True,
            PopularSearchTerm.is_active == True
        ).order_by(asc(PopularSearchTerm.rank)).limit(limit).all()


class TrendingSearchRepository(BaseRepository[TrendingSearch]):
    """
    Repository for trending searches with velocity tracking,
    growth analysis, and trend classification.
    """

    def __init__(self, db: Session):
        super().__init__(TrendingSearch, db)

    def create_trending_search(
        self,
        term: str,
        normalized_term: str,
        current_period_start: date,
        current_period_end: date,
        previous_period_start: date,
        previous_period_end: date,
        trending_data: Dict[str, Any],
        period_type: str = "daily"
    ) -> TrendingSearch:
        """Create trending search entry."""
        try:
            trending = TrendingSearch(
                term=term,
                normalized_term=normalized_term,
                current_period_start=current_period_start,
                current_period_end=current_period_end,
                previous_period_start=previous_period_start,
                previous_period_end=previous_period_end,
                period_type=period_type,
                **trending_data
            )

            self.db.add(trending)
            self.db.commit()
            self.db.refresh(trending)

            return trending

        except Exception as e:
            self.db.rollback()
            raise ValidationException(f"Failed to create trending search: {str(e)}")

    def get_trending_searches(
        self,
        period_start: date,
        period_type: str = "daily",
        limit: int = 20,
        min_velocity: Decimal = Decimal('1.0'),
        trend_type: Optional[str] = None,
        active_only: bool = True
    ) -> List[TrendingSearch]:
        """Get trending searches for period."""
        query = self.db.query(TrendingSearch).filter(
            TrendingSearch.current_period_start == period_start,
            TrendingSearch.period_type == period_type,
            TrendingSearch.velocity_score >= min_velocity
        )

        if active_only:
            query = query.filter(TrendingSearch.is_active == True)

        if trend_type:
            query = query.filter(TrendingSearch.trend_type == trend_type)

        return query.order_by(
            desc(TrendingSearch.velocity_score),
            desc(TrendingSearch.growth_rate)
        ).limit(limit).all()


class ZeroResultTermRepository(BaseRepository[ZeroResultTerm]):
    """
    Repository for zero result terms with resolution tracking,
    intent analysis, and optimization recommendations.
    """

    def __init__(self, db: Session):
        super().__init__(ZeroResultTerm, db)

    def create_or_update_zero_result(
        self,
        term: str,
        normalized_term: str,
        term_data: Optional[Dict[str, Any]] = None
    ) -> ZeroResultTerm:
        """Create or update zero result term."""
        try:
            import hashlib
            term_hash = hashlib.sha256(normalized_term.encode()).hexdigest()

            existing = self.db.query(ZeroResultTerm).filter(
                ZeroResultTerm.term_hash == term_hash
            ).first()

            if existing:
                existing.search_count += 1
                existing.last_seen = datetime.utcnow()
                existing.days_active = (
                    datetime.utcnow() - existing.first_seen
                ).days

                if term_data:
                    for key, value in term_data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)

                # Recalculate priority score
                existing.priority_score = self._calculate_priority_score(existing)

                self.db.commit()
                self.db.refresh(existing)
                return existing
            else:
                zero_result = ZeroResultTerm(
                    term=term,
                    normalized_term=normalized_term,
                    term_hash=term_hash,
                    first_seen=datetime.utcnow(),
                    last_seen=datetime.utcnow(),
                    search_count=1,
                    **(term_data or {})
                )

                zero_result.priority_score = self._calculate_priority_score(zero_result)

                self.db.add(zero_result)
                self.db.commit()
                self.db.refresh(zero_result)

                return zero_result

        except Exception as e:
            self.db.rollback()
            raise ValidationException(f"Failed to create zero result term: {str(e)}")

    def get_unresolved_terms(
        self,
        limit: int = 100,
        min_priority: Decimal = Decimal('1.0'),
        order_by: str = "priority"
    ) -> List[ZeroResultTerm]:
        """Get unresolved zero result terms."""
        query = self.db.query(ZeroResultTerm).filter(
            ZeroResultTerm.resolution_status == 'unresolved',
            ZeroResultTerm.priority_score >= min_priority
        )

        if order_by == "priority":
            query = query.order_by(desc(ZeroResultTerm.priority_score))
        elif order_by == "frequency":
            query = query.order_by(desc(ZeroResultTerm.search_count))
        elif order_by == "recent":
            query = query.order_by(desc(ZeroResultTerm.last_seen))

        return query.limit(limit).all()

    def mark_resolved(
        self,
        term_id: UUID,
        resolution_type: str,
        resolved_by: UUID,
        notes: Optional[str] = None
    ) -> ZeroResultTerm:
        """Mark zero result term as resolved."""
        term = self.get_by_id(term_id)
        if not term:
            raise NotFoundException(f"Zero result term {term_id} not found")

        term.resolution_status = 'resolved'
        term.resolution_type = resolution_type
        term.resolved_at = datetime.utcnow()
        term.resolved_by = resolved_by
        term.resolution_notes = notes

        self.db.commit()
        self.db.refresh(term)

        return term

    def _calculate_priority_score(
        self,
        term: ZeroResultTerm
    ) -> Decimal:
        """Calculate priority score for zero result term."""
        # Factors: search count, unique users, recency, days active
        frequency_score = min(term.search_count * 10, 100)
        user_score = min(term.unique_users * 20, 100)
        recency_score = max(100 - term.days_active, 0)

        total_score = (
            frequency_score * 0.4 +
            user_score * 0.4 +
            recency_score * 0.2
        )

        return Decimal(str(round(total_score, 2)))


class SearchAnalyticsReportRepository(BaseRepository[SearchAnalyticsReport]):
    """
    Repository for pre-computed analytics reports with
    caching, versioning, and distribution.
    """

    def __init__(self, db: Session):
        super().__init__(SearchAnalyticsReport, db)

    def create_report(
        self,
        report_name: str,
        report_type: str,
        period_start: date,
        period_end: date,
        report_data: Dict[str, Any],
        hostel_id: Optional[UUID] = None
    ) -> SearchAnalyticsReport:
        """Create analytics report."""
        try:
            report = SearchAnalyticsReport(
                report_name=report_name,
                report_type=report_type,
                period_start=period_start,
                period_end=period_end,
                generated_at=datetime.utcnow(),
                hostel_id=hostel_id,
                **report_data
            )

            self.db.add(report)
            self.db.commit()
            self.db.refresh(report)

            return report

        except Exception as e:
            self.db.rollback()
            raise ValidationException(f"Failed to create report: {str(e)}")

    def get_latest_report(
        self,
        report_type: str,
        hostel_id: Optional[UUID] = None
    ) -> Optional[SearchAnalyticsReport]:
        """Get latest report of type."""
        query = self.db.query(SearchAnalyticsReport).filter(
            SearchAnalyticsReport.report_type == report_type
        )

        if hostel_id:
            query = query.filter(SearchAnalyticsReport.hostel_id == hostel_id)
        else:
            query = query.filter(SearchAnalyticsReport.hostel_id.is_(None))

        return query.order_by(
            desc(SearchAnalyticsReport.generated_at)
        ).first()

    def get_reports(
        self,
        start_date: date,
        end_date: date,
        report_type: Optional[str] = None,
        hostel_id: Optional[UUID] = None,
        published_only: bool = False
    ) -> List[SearchAnalyticsReport]:
        """Get reports for date range."""
        query = self.db.query(SearchAnalyticsReport).filter(
            SearchAnalyticsReport.period_start >= start_date,
            SearchAnalyticsReport.period_end <= end_date
        )

        if report_type:
            query = query.filter(SearchAnalyticsReport.report_type == report_type)

        if hostel_id:
            query = query.filter(SearchAnalyticsReport.hostel_id == hostel_id)

        if published_only:
            query = query.filter(SearchAnalyticsReport.is_published == True)

        return query.order_by(
            desc(SearchAnalyticsReport.generated_at)
        ).all()

    def publish_report(
        self,
        report_id: UUID
    ) -> SearchAnalyticsReport:
        """Publish report."""
        report = self.get_by_id(report_id)
        if not report:
            raise NotFoundException(f"Report {report_id} not found")

        report.is_published = True
        report.published_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(report)

        return report