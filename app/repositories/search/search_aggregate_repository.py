"""
Search Aggregate Repository

Centralized repository for cross-functional search operations,
aggregated analytics, and unified search management.
"""

from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.search.search_query_log_repository import (
    SearchQueryLogRepository,
    SearchSessionRepository,
    SavedSearchRepository
)
from app.repositories.search.search_analytics_repository import (
    SearchTermStatsRepository,
    SearchMetricsRepository,
    PopularSearchTermRepository,
    TrendingSearchRepository,
    ZeroResultTermRepository,
    SearchAnalyticsReportRepository
)
from app.repositories.search.search_autocomplete_repository import (
    AutocompleteSuggestionRepository,
    AutocompleteQueryLogRepository,
    SuggestionSourceRepository,
    PopularSearchSuggestionRepository,
    SuggestionPerformanceRepository
)


class SearchAggregateRepository:
    """
    Aggregate repository providing unified access to all search-related
    repositories with cross-functional operations and analytics.
    """

    def __init__(self, db: Session):
        self.db = db
        
        # Query logging repositories
        self.query_log = SearchQueryLogRepository(db)
        self.session = SearchSessionRepository(db)
        self.saved_search = SavedSearchRepository(db)
        
        # Analytics repositories
        self.term_stats = SearchTermStatsRepository(db)
        self.metrics = SearchMetricsRepository(db)
        self.popular_terms = PopularSearchTermRepository(db)
        self.trending = TrendingSearchRepository(db)
        self.zero_results = ZeroResultTermRepository(db)
        self.reports = SearchAnalyticsReportRepository(db)
        
        # Autocomplete repositories
        self.suggestions = AutocompleteSuggestionRepository(db)
        self.autocomplete_log = AutocompleteQueryLogRepository(db)
        self.suggestion_sources = SuggestionSourceRepository(db)
        self.popular_suggestions = PopularSearchSuggestionRepository(db)
        self.suggestion_performance = SuggestionPerformanceRepository(db)

    # ===== Unified Analytics =====

    def get_complete_search_dashboard(
        self,
        start_date: date,
        end_date: date,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Get complete search dashboard with all metrics.

        Args:
            start_date: Start date
            end_date: End date
            hostel_id: Optional hostel filter

        Returns:
            Complete dashboard dictionary
        """
        # Query statistics
        query_stats = self.query_log.get_search_statistics(
            datetime.combine(start_date, datetime.min.time()),
            datetime.combine(end_date, datetime.max.time())
        )

        # Session statistics
        session_stats = self.session.get_session_statistics(
            datetime.combine(start_date, datetime.min.time()),
            datetime.combine(end_date, datetime.max.time())
        )

        # Metrics
        metrics = self.metrics.get_aggregated_metrics(
            start_date, end_date, hostel_id
        )

        # Popular terms
        popular = self.query_log.get_popular_search_terms(
            datetime.combine(start_date, datetime.min.time()),
            datetime.combine(end_date, datetime.max.time()),
            limit=10
        )

        # Filter usage
        filter_usage = self.query_log.get_search_filters_usage(
            datetime.combine(start_date, datetime.min.time()),
            datetime.combine(end_date, datetime.max.time())
        )

        # Performance metrics
        performance = self.query_log.get_performance_metrics(
            datetime.combine(start_date, datetime.min.time()),
            datetime.combine(end_date, datetime.max.time())
        )

        # Autocomplete analytics
        autocomplete_analytics = self.autocomplete_log.get_query_analytics(
            datetime.combine(start_date, datetime.min.time()),
            datetime.combine(end_date, datetime.max.time())
        )

        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'query_statistics': query_stats,
            'session_statistics': session_stats,
            'aggregated_metrics': metrics,
            'popular_terms': popular,
            'filter_usage': filter_usage,
            'performance': performance,
            'autocomplete': autocomplete_analytics
        }

    def get_search_health_metrics(self) -> Dict[str, Any]:
        """
        Get overall search health metrics.

        Returns:
            Health metrics dictionary
        """
        # Last 7 days metrics
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=7)

        recent_metrics = self.metrics.get_aggregated_metrics(start_date, end_date)

        # Zero result terms
        unresolved_zero_results = self.zero_results.get_unresolved_terms(limit=10)

        # Recent performance
        recent_performance = self.query_log.get_performance_metrics(
            datetime.combine(start_date, datetime.min.time()),
            datetime.combine(end_date, datetime.max.time())
        )

        # Calculate health score
        health_score = self._calculate_health_score(
            recent_metrics,
            len(unresolved_zero_results),
            recent_performance
        )

        return {
            'health_score': health_score,
            'recent_metrics': recent_metrics,
            'zero_result_issues': len(unresolved_zero_results),
            'performance': recent_performance,
            'recommendations': self._generate_health_recommendations(
                recent_metrics,
                unresolved_zero_results,
                recent_performance
            )
        }

    # ===== Cross-Functional Operations =====

    def process_search_event(
        self,
        query_data: Dict[str, Any],
        user_id: Optional[UUID] = None,
        visitor_id: Optional[UUID] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process complete search event including logging and analytics.

        Args:
            query_data: Search query data
            user_id: Optional user ID
            visitor_id: Optional visitor ID
            session_id: Optional session ID

        Returns:
            Processing result dictionary
        """
        # Create query log
        query_log = self.query_log.create_query_log(
            query_data,
            user_id=user_id,
            visitor_id=visitor_id,
            session_id=session_id
        )

        # Update or create session
        if session_id:
            session = self.session.get_by_session_id(session_id)
            if session:
                self.session.update_session_activity(
                    session_id,
                    total_searches=session.total_searches + 1
                )
            else:
                self.session.create_session(
                    session_id=session_id,
                    user_id=user_id,
                    visitor_id=visitor_id,
                    total_searches=1
                )

        # Update term stats if query exists
        if query_data.get('normalized_query'):
            today = datetime.utcnow().date()
            self.term_stats.create_or_update_stats(
                term=query_data.get('query', ''),
                normalized_term=query_data['normalized_query'],
                period_start=today,
                period_end=today,
                period_type='daily',
                stats_data={
                    'search_count': 1,
                    'zero_result_count': 1 if query_data.get('results_count', 0) == 0 else 0
                }
            )

        # Track zero results
        if query_data.get('results_count', 0) == 0 and query_data.get('normalized_query'):
            self.zero_results.create_or_update_zero_result(
                term=query_data.get('query', ''),
                normalized_term=query_data['normalized_query']
            )

        return {
            'query_log_id': query_log.id,
            'session_id': session_id,
            'logged_at': query_log.created_at.isoformat()
        }

    def process_autocomplete_event(
        self,
        prefix: str,
        suggestions_returned: List[UUID],
        execution_time_ms: int,
        selected_suggestion_id: Optional[UUID] = None,
        selected_position: Optional[int] = None,
        user_id: Optional[UUID] = None,
        visitor_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Process autocomplete event with logging and metrics update.

        Args:
            prefix: Search prefix
            suggestions_returned: List of suggestion IDs returned
            execution_time_ms: Execution time
            selected_suggestion_id: Selected suggestion
            selected_position: Position of selection
            user_id: Optional user ID
            visitor_id: Optional visitor ID

        Returns:
            Processing result
        """
        # Log autocomplete query
        log = self.autocomplete_log.log_query(
            prefix=prefix,
            suggestions_returned=len(suggestions_returned),
            execution_time_ms=execution_time_ms,
            user_id=user_id,
            visitor_id=visitor_id,
            selected_suggestion_id=selected_suggestion_id,
            selected_position=selected_position
        )

        # Update suggestion metrics for each shown suggestion
        for idx, suggestion_id in enumerate(suggestions_returned):
            was_selected = (suggestion_id == selected_suggestion_id)
            self.suggestions.update_usage_metrics(
                suggestion_id,
                was_selected=was_selected,
                position_shown=idx + 1
            )

        return {
            'log_id': log.id,
            'suggestions_updated': len(suggestions_returned)
        }

    # ===== Optimization Methods =====

    def generate_search_optimization_report(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate comprehensive search optimization report.

        Args:
            days: Days to analyze

        Returns:
            Optimization report
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Poor performing terms
        poor_terms = self.term_stats.get_poor_performing_terms(
            start_date.date(),
            end_date.date()
        )

        # Zero result terms
        zero_result_terms = self.zero_results.get_unresolved_terms(limit=50)

        # Low performing suggestions
        # (Would need to implement this in suggestion repository)

        # Performance bottlenecks
        slow_queries = self.db.query(self.query_log.model).filter(
            self.query_log.model.created_at.between(start_date, end_date),
            self.query_log.model.execution_time_ms > 1000
        ).count()

        return {
            'analysis_period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'days': days
            },
            'poor_performing_terms': [
                {
                    'term': term.term,
                    'searches': term.search_count,
                    'ctr': float(term.click_through_rate)
                }
                for term in poor_terms[:10]
            ],
            'zero_result_issues': [
                {
                    'term': term.term,
                    'count': term.search_count,
                    'priority': float(term.priority_score)
                }
                for term in zero_result_terms[:10]
            ],
            'performance_issues': {
                'slow_queries_count': slow_queries,
                'threshold_ms': 1000
            },
            'recommendations': self._generate_optimization_recommendations(
                poor_terms,
                zero_result_terms,
                slow_queries
            )
        }

    # ===== Helper Methods =====

    def _calculate_health_score(
        self,
        metrics: Dict[str, Any],
        zero_result_count: int,
        performance: Dict[str, Any]
    ) -> int:
        """Calculate search health score (0-100)."""
        score = 100

        # Deduct for high zero result rate
        if metrics.get('zero_result_rate', 0) > 10:
            score -= min(metrics['zero_result_rate'], 30)

        # Deduct for low CTR
        if metrics.get('click_through_rate', 0) < 20:
            score -= (20 - metrics['click_through_rate'])

        # Deduct for unresolved zero results
        score -= min(zero_result_count * 2, 20)

        # Deduct for slow performance
        avg_time = performance.get('execution_time', {}).get('avg_ms', 0)
        if avg_time > 500:
            score -= min((avg_time - 500) / 50, 20)

        return max(0, min(100, int(score)))

    def _generate_health_recommendations(
        self,
        metrics: Dict[str, Any],
        zero_results: List,
        performance: Dict[str, Any]
    ) -> List[str]:
        """Generate health improvement recommendations."""
        recommendations = []

        # Zero result rate
        if metrics.get('zero_result_rate', 0) > 10:
            recommendations.append(
                f"High zero result rate ({metrics['zero_result_rate']}%). "
                "Review and resolve zero result terms."
            )

        # Click through rate
        if metrics.get('click_through_rate', 0) < 20:
            recommendations.append(
                f"Low click-through rate ({metrics['click_through_rate']}%). "
                "Improve result relevance and ranking."
            )

        # Zero result terms
        if len(zero_results) > 10:
            recommendations.append(
                f"{len(zero_results)} unresolved zero result terms. "
                "Add content or synonyms for common searches."
            )

        # Performance
        avg_time = performance.get('execution_time', {}).get('avg_ms', 0)
        if avg_time > 500:
            recommendations.append(
                f"Average response time is {avg_time}ms. "
                "Optimize queries and add caching."
            )

        return recommendations

    def _generate_optimization_recommendations(
        self,
        poor_terms: List,
        zero_results: List,
        slow_queries: int
    ) -> List[Dict[str, str]]:
        """Generate detailed optimization recommendations."""
        recommendations = []

        if poor_terms:
            recommendations.append({
                'category': 'Result Relevance',
                'priority': 'High',
                'recommendation': (
                    f"Improve ranking for {len(poor_terms)} poor-performing terms. "
                    "Review result ordering and relevance scoring."
                ),
                'impact': 'Increase CTR by 10-20%'
            })

        if zero_results:
            recommendations.append({
                'category': 'Content Coverage',
                'priority': 'High',
                'recommendation': (
                    f"Address {len(zero_results)} zero-result searches. "
                    "Add content, synonyms, or better matching."
                ),
                'impact': 'Reduce zero results by 30-50%'
            })

        if slow_queries > 100:
            recommendations.append({
                'category': 'Performance',
                'priority': 'Medium',
                'recommendation': (
                    f"{slow_queries} slow queries detected. "
                    "Add database indexes and implement caching."
                ),
                'impact': 'Reduce response time by 40-60%'
            })

        return recommendations