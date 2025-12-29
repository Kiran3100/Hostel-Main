"""
Search Autocomplete Repository

Comprehensive repository for autocomplete suggestions, query logging,
source management, and performance tracking.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import func, and_, or_, desc, asc, case
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.dialects.postgresql import insert

from app.models.search.search_autocomplete import (
    AutocompleteSuggestion,
    AutocompleteQueryLog,
    SuggestionSource,
    PopularSearchSuggestion,
    SuggestionPerformance
)
from app.repositories.base.base_repository import BaseRepository
from app.core.exceptions import NotFoundException, ValidationException


class AutocompleteSuggestionRepository(BaseRepository[AutocompleteSuggestion]):
    """
    Repository for autocomplete suggestions with scoring,
    personalization, and performance optimization.
    """

    def __init__(self, db: Session):
        super().__init__(AutocompleteSuggestion, db)

    # ===== Core CRUD Operations =====

    def create_suggestion(
        self,
        value: str,
        label: str,
        suggestion_type: str,
        source: str = "manual",
        **suggestion_data
    ) -> AutocompleteSuggestion:
        """
        Create autocomplete suggestion.

        Args:
            value: Suggestion value
            label: Display label
            suggestion_type: Type of suggestion
            source: Source of suggestion
            **suggestion_data: Additional data

        Returns:
            Created AutocompleteSuggestion
        """
        try:
            # Normalize value
            normalized_value = value.lower().strip()

            # Calculate base score
            base_score = suggestion_data.get('base_score', Decimal('1.0'))

            suggestion = AutocompleteSuggestion(
                value=value,
                label=label,
                normalized_value=normalized_value,
                suggestion_type=suggestion_type,
                source=source,
                base_score=base_score,
                score=base_score,
                **suggestion_data
            )

            self.db.add(suggestion)
            self.db.commit()
            self.db.refresh(suggestion)

            return suggestion

        except Exception as e:
            self.db.rollback()
            raise ValidationException(f"Failed to create suggestion: {str(e)}")

    def bulk_create_suggestions(
        self,
        suggestions: List[Dict[str, Any]],
        batch_size: int = 1000
    ) -> int:
        """
        Bulk create suggestions.

        Args:
            suggestions: List of suggestion dictionaries
            batch_size: Batch size for insertion

        Returns:
            Number of suggestions created
        """
        try:
            count = 0
            for i in range(0, len(suggestions), batch_size):
                batch = suggestions[i:i + batch_size]
                
                stmt = insert(AutocompleteSuggestion).values(batch)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['normalized_value', 'suggestion_type'],
                    set_=dict(
                        label=stmt.excluded.label,
                        score=stmt.excluded.score,
                        updated_at=datetime.utcnow()
                    )
                )
                
                result = self.db.execute(stmt)
                count += result.rowcount
                self.db.commit()

            return count

        except Exception as e:
            self.db.rollback()
            raise ValidationException(f"Bulk insert failed: {str(e)}")

    # ===== Query Methods =====

    def search_suggestions(
        self,
        prefix: str,
        suggestion_types: Optional[List[str]] = None,
        limit: int = 10,
        include_inactive: bool = False,
        user_location: Optional[Tuple[Decimal, Decimal]] = None
    ) -> List[AutocompleteSuggestion]:
        """
        Search autocomplete suggestions by prefix.

        Args:
            prefix: Search prefix
            suggestion_types: Filter by types
            limit: Maximum results
            include_inactive: Include inactive suggestions
            user_location: User coordinates for location boosting

        Returns:
            List of matching suggestions
        """
        normalized_prefix = prefix.lower().strip()

        query = self.db.query(AutocompleteSuggestion).filter(
            AutocompleteSuggestion.normalized_value.startswith(normalized_prefix)
        )

        if not include_inactive:
            query = query.filter(
                AutocompleteSuggestion.is_active == True,
                AutocompleteSuggestion.deleted_at.is_(None)
            )

        if suggestion_types:
            query = query.filter(
                AutocompleteSuggestion.suggestion_type.in_(suggestion_types)
            )

        # Order by score (with potential location boosting)
        query = query.order_by(
            desc(AutocompleteSuggestion.is_featured),
            desc(AutocompleteSuggestion.score),
            asc(AutocompleteSuggestion.normalized_value)
        )

        return query.limit(limit).all()

    def get_by_value_and_type(
        self,
        value: str,
        suggestion_type: str
    ) -> Optional[AutocompleteSuggestion]:
        """Get suggestion by value and type."""
        normalized_value = value.lower().strip()

        return self.db.query(AutocompleteSuggestion).filter(
            AutocompleteSuggestion.normalized_value == normalized_value,
            AutocompleteSuggestion.suggestion_type == suggestion_type,
            AutocompleteSuggestion.deleted_at.is_(None)
        ).first()

    def get_featured_suggestions(
        self,
        suggestion_type: Optional[str] = None,
        limit: int = 10
    ) -> List[AutocompleteSuggestion]:
        """Get featured suggestions."""
        query = self.db.query(AutocompleteSuggestion).filter(
            AutocompleteSuggestion.is_featured == True,
            AutocompleteSuggestion.is_active == True,
            AutocompleteSuggestion.deleted_at.is_(None)
        )

        if suggestion_type:
            query = query.filter(
                AutocompleteSuggestion.suggestion_type == suggestion_type
            )

        return query.order_by(
            desc(AutocompleteSuggestion.score)
        ).limit(limit).all()

    def get_top_suggestions(
        self,
        suggestion_type: Optional[str] = None,
        limit: int = 20,
        min_selection_count: int = 5
    ) -> List[AutocompleteSuggestion]:
        """Get top performing suggestions."""
        query = self.db.query(AutocompleteSuggestion).filter(
            AutocompleteSuggestion.is_active == True,
            AutocompleteSuggestion.selection_count >= min_selection_count,
            AutocompleteSuggestion.deleted_at.is_(None)
        )

        if suggestion_type:
            query = query.filter(
                AutocompleteSuggestion.suggestion_type == suggestion_type
            )

        return query.order_by(
            desc(AutocompleteSuggestion.selection_rate),
            desc(AutocompleteSuggestion.selection_count)
        ).limit(limit).all()

    # ===== Update Operations =====

    def update_usage_metrics(
        self,
        suggestion_id: UUID,
        was_selected: bool = False,
        position_shown: Optional[int] = None
    ) -> AutocompleteSuggestion:
        """
        Update suggestion usage metrics.

        Args:
            suggestion_id: Suggestion ID
            was_selected: Whether suggestion was selected
            position_shown: Position in results

        Returns:
            Updated suggestion
        """
        suggestion = self.get_by_id(suggestion_id)
        if not suggestion:
            raise NotFoundException(f"Suggestion {suggestion_id} not found")

        # Update impression count
        suggestion.impression_count += 1
        suggestion.usage_count += 1
        suggestion.last_used = datetime.utcnow()

        # Update selection metrics
        if was_selected:
            suggestion.selection_count += 1

        # Calculate selection rate
        if suggestion.impression_count > 0:
            suggestion.selection_rate = Decimal(
                str(round(
                    suggestion.selection_count / suggestion.impression_count * 100,
                    2
                ))
            )

        # Update average position
        if position_shown is not None:
            if suggestion.avg_position_shown is None:
                suggestion.avg_position_shown = Decimal(str(position_shown))
            else:
                # Moving average
                suggestion.avg_position_shown = (
                    suggestion.avg_position_shown * Decimal('0.9') +
                    Decimal(str(position_shown)) * Decimal('0.1')
                )

        # Recalculate score
        suggestion.score = self._calculate_suggestion_score(suggestion)

        self.db.commit()
        self.db.refresh(suggestion)

        return suggestion

    def update_score(
        self,
        suggestion_id: UUID,
        base_score: Optional[Decimal] = None,
        popularity_boost: Optional[Decimal] = None,
        recency_boost: Optional[Decimal] = None
    ) -> AutocompleteSuggestion:
        """Update suggestion scoring components."""
        suggestion = self.get_by_id(suggestion_id)
        if not suggestion:
            raise NotFoundException(f"Suggestion {suggestion_id} not found")

        if base_score is not None:
            suggestion.base_score = base_score
        if popularity_boost is not None:
            suggestion.popularity_boost = popularity_boost
        if recency_boost is not None:
            suggestion.recency_boost = recency_boost

        # Recalculate total score
        suggestion.score = (
            suggestion.base_score +
            suggestion.popularity_boost +
            suggestion.recency_boost
        )

        self.db.commit()
        self.db.refresh(suggestion)

        return suggestion

    def toggle_featured(
        self,
        suggestion_id: UUID
    ) -> AutocompleteSuggestion:
        """Toggle featured status."""
        suggestion = self.get_by_id(suggestion_id)
        if not suggestion:
            raise NotFoundException(f"Suggestion {suggestion_id} not found")

        suggestion.is_featured = not suggestion.is_featured

        self.db.commit()
        self.db.refresh(suggestion)

        return suggestion

    # ===== Maintenance Operations =====

    def recalculate_all_scores(self) -> int:
        """Recalculate scores for all active suggestions."""
        suggestions = self.db.query(AutocompleteSuggestion).filter(
            AutocompleteSuggestion.is_active == True,
            AutocompleteSuggestion.deleted_at.is_(None)
        ).all()

        count = 0
        for suggestion in suggestions:
            suggestion.score = self._calculate_suggestion_score(suggestion)
            count += 1

        self.db.commit()
        return count

    def cleanup_low_performing(
        self,
        min_impressions: int = 100,
        max_selection_rate: Decimal = Decimal('1.0')
    ) -> int:
        """Deactivate low-performing suggestions."""
        suggestions = self.db.query(AutocompleteSuggestion).filter(
            AutocompleteSuggestion.is_active == True,
            AutocompleteSuggestion.impression_count >= min_impressions,
            AutocompleteSuggestion.selection_rate <= max_selection_rate,
            AutocompleteSuggestion.deleted_at.is_(None)
        ).all()

        count = 0
        for suggestion in suggestions:
            suggestion.is_active = False
            count += 1

        self.db.commit()
        return count

    # ===== Helper Methods =====

    def _calculate_suggestion_score(
        self,
        suggestion: AutocompleteSuggestion
    ) -> Decimal:
        """Calculate comprehensive suggestion score."""
        # Base score
        score = suggestion.base_score

        # Popularity boost (based on selection rate and count)
        if suggestion.selection_count > 0:
            popularity = min(
                suggestion.selection_count * Decimal('0.1'),
                Decimal('10.0')
            )
            score += popularity

        # Selection rate boost
        if suggestion.selection_rate > 0:
            score += suggestion.selection_rate * Decimal('0.1')

        # Recency boost
        if suggestion.last_used:
            days_since_use = (datetime.utcnow() - suggestion.last_used).days
            recency = max(Decimal('1.0') - Decimal(str(days_since_use)) * Decimal('0.01'), Decimal('0'))
            score += recency

        # Featured boost
        if suggestion.is_featured:
            score += Decimal('5.0')

        return round(score, 4)


class AutocompleteQueryLogRepository(BaseRepository[AutocompleteQueryLog]):
    """
    Repository for autocomplete query logging with analytics
    and performance tracking.
    """

    def __init__(self, db: Session):
        super().__init__(AutocompleteQueryLog, db)

    def log_query(
        self,
        prefix: str,
        suggestions_returned: int,
        execution_time_ms: int,
        user_id: Optional[UUID] = None,
        visitor_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
        selected_suggestion_id: Optional[UUID] = None,
        selected_position: Optional[int] = None,
        **query_data
    ) -> AutocompleteQueryLog:
        """Log autocomplete query."""
        try:
            normalized_prefix = prefix.lower().strip()

            log = AutocompleteQueryLog(
                prefix=prefix,
                normalized_prefix=normalized_prefix,
                prefix_length=len(prefix),
                suggestions_returned=suggestions_returned,
                execution_time_ms=execution_time_ms,
                user_id=user_id,
                visitor_id=visitor_id,
                session_id=session_id,
                selected_suggestion_id=selected_suggestion_id,
                selected_position=selected_position,
                **query_data
            )

            self.db.add(log)
            self.db.commit()
            self.db.refresh(log)

            return log

        except Exception as e:
            self.db.rollback()
            raise ValidationException(f"Failed to log query: {str(e)}")

    def get_query_analytics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get autocomplete query analytics."""
        query = self.db.query(AutocompleteQueryLog).filter(
            AutocompleteQueryLog.created_at.between(start_date, end_date)
        )

        total_queries = query.count()
        
        # Performance metrics
        avg_execution_time = query.with_entities(
            func.avg(AutocompleteQueryLog.execution_time_ms)
        ).scalar() or 0

        avg_suggestions = query.with_entities(
            func.avg(AutocompleteQueryLog.suggestions_returned)
        ).scalar() or 0

        # Cache performance
        cache_hits = query.filter(
            AutocompleteQueryLog.cache_hit == True
        ).count()

        # Selection metrics
        with_selection = query.filter(
            AutocompleteQueryLog.selected_suggestion_id.isnot(None)
        ).count()

        # Conversion to search
        converted_to_search = query.filter(
            AutocompleteQueryLog.resulted_in_search == True
        ).count()

        return {
            'total_queries': total_queries,
            'avg_execution_time_ms': round(avg_execution_time, 2),
            'avg_suggestions_returned': round(avg_suggestions, 2),
            'cache_hit_rate': round(
                (cache_hits / total_queries * 100) if total_queries > 0 else 0,
                2
            ),
            'selection_rate': round(
                (with_selection / total_queries * 100) if total_queries > 0 else 0,
                2
            ),
            'search_conversion_rate': round(
                (converted_to_search / total_queries * 100) if total_queries > 0 else 0,
                2
            )
        }


class SuggestionSourceRepository(BaseRepository[SuggestionSource]):
    """
    Repository for managing autocomplete suggestion sources
    with sync scheduling and performance tracking.
    """

    def __init__(self, db: Session):
        super().__init__(SuggestionSource, db)

    def get_sources_for_sync(self) -> List[SuggestionSource]:
        """Get sources that need synchronization."""
        now = datetime.utcnow()

        return self.db.query(SuggestionSource).filter(
            SuggestionSource.is_active == True,
            SuggestionSource.auto_sync == True,
            or_(
                SuggestionSource.next_sync.is_(None),
                SuggestionSource.next_sync <= now
            )
        ).all()

    def update_sync_status(
        self,
        source_id: UUID,
        status: str,
        duration_seconds: Optional[int] = None,
        error: Optional[str] = None,
        suggestions_synced: Optional[int] = None
    ) -> SuggestionSource:
        """Update source sync status."""
        source = self.get_by_id(source_id)
        if not source:
            raise NotFoundException(f"Source {source_id} not found")

        source.last_sync = datetime.utcnow()
        source.last_sync_status = status
        source.last_sync_error = error

        if duration_seconds is not None:
            source.last_sync_duration_seconds = duration_seconds
            
            # Update average
            if source.avg_sync_time_seconds is None:
                source.avg_sync_time_seconds = Decimal(str(duration_seconds))
            else:
                source.avg_sync_time_seconds = (
                    source.avg_sync_time_seconds * Decimal('0.9') +
                    Decimal(str(duration_seconds)) * Decimal('0.1')
                )

        if suggestions_synced is not None:
            source.total_suggestions = suggestions_synced

        # Schedule next sync
        if source.auto_sync and source.sync_frequency_minutes:
            source.next_sync = datetime.utcnow() + timedelta(
                minutes=source.sync_frequency_minutes
            )

        self.db.commit()
        self.db.refresh(source)

        return source


class PopularSearchSuggestionRepository(BaseRepository[PopularSearchSuggestion]):
    """
    Repository for popular search suggestions shown in
    autocomplete fallback scenarios.
    """

    def __init__(self, db: Session):
        super().__init__(PopularSearchSuggestion, db)

    def get_current_popular(
        self,
        limit: int = 10,
        city: Optional[str] = None,
        hostel_type: Optional[str] = None
    ) -> List[PopularSearchSuggestion]:
        """Get current popular suggestions."""
        now = datetime.utcnow().date()

        query = self.db.query(PopularSearchSuggestion).filter(
            PopularSearchSuggestion.is_active == True,
            PopularSearchSuggestion.period_start <= now,
            PopularSearchSuggestion.period_end >= now
        )

        if city:
            query = query.filter(PopularSearchSuggestion.city == city)

        if hostel_type:
            query = query.filter(PopularSearchSuggestion.hostel_type == hostel_type)

        return query.order_by(asc(PopularSearchSuggestion.rank)).limit(limit).all()


class SuggestionPerformanceRepository(BaseRepository[SuggestionPerformance]):
    """
    Repository for tracking suggestion performance metrics
    over time for optimization.
    """

    def __init__(self, db: Session):
        super().__init__(SuggestionPerformance, db)

    def record_performance(
        self,
        suggestion_id: UUID,
        metric_date: date,
        performance_data: Dict[str, Any],
        period_type: str = "daily"
    ) -> SuggestionPerformance:
        """Record performance metrics for suggestion."""
        try:
            existing = self.db.query(SuggestionPerformance).filter(
                SuggestionPerformance.suggestion_id == suggestion_id,
                SuggestionPerformance.metric_date == metric_date,
                SuggestionPerformance.period_type == period_type
            ).first()

            if existing:
                for key, value in performance_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
                
                self.db.commit()
                self.db.refresh(existing)
                return existing
            else:
                perf = SuggestionPerformance(
                    suggestion_id=suggestion_id,
                    metric_date=metric_date,
                    period_type=period_type,
                    **performance_data
                )

                self.db.add(perf)
                self.db.commit()
                self.db.refresh(perf)

                return perf

        except Exception as e:
            self.db.rollback()
            raise ValidationException(f"Failed to record performance: {str(e)}")

    def get_suggestion_performance_trend(
        self,
        suggestion_id: UUID,
        days: int = 30
    ) -> List[SuggestionPerformance]:
        """Get performance trend for suggestion."""
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days)

        return self.db.query(SuggestionPerformance).filter(
            SuggestionPerformance.suggestion_id == suggestion_id,
            SuggestionPerformance.metric_date.between(start_date, end_date)
        ).order_by(asc(SuggestionPerformance.metric_date)).all()