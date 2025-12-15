# app/services/search/search_analytics_service.py
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Protocol

from app.schemas.search.search_analytics import (
    SearchAnalytics,
    SearchTermStats,
)
from app.schemas.common.filters import DateRangeFilter


class SearchEventStore(Protocol):
    """
    Abstract store for individual search events.

    Each event record is expected to include:
    - term: str
    - results_count: int
    - created_at: datetime
    """

    def save_event(
        self,
        *,
        term: str,
        results_count: int,
        created_at: datetime,
    ) -> None: ...

    def list_events(
        self,
        *,
        period_start: datetime,
        period_end: datetime,
    ) -> List[dict]: ...


class SearchAnalyticsService:
    """
    Record and compute analytics for search usage:

    - Record each search event (term + results_count)
    - Aggregate per-term statistics over a DateRangeFilter
    - Provide SearchAnalytics with top terms, zero-result terms, etc.
    """

    def __init__(self, store: SearchEventStore) -> None:
        self._store = store

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Recording
    # ------------------------------------------------------------------ #
    def record_search_event(self, term: str, results_count: int) -> None:
        """
        Record a single search event.
        """
        self._store.save_event(
            term=term.strip().lower(),
            results_count=results_count,
            created_at=self._now(),
        )

    # ------------------------------------------------------------------ #
    # Analytics
    # ------------------------------------------------------------------ #
    def get_analytics(self, period: DateRangeFilter) -> SearchAnalytics:
        if not (period.start_date and period.end_date):
            # If period not specified, default to "all time"
            period_start = datetime.min
            period_end = datetime.max
        else:
            period_start = datetime.combine(period.start_date, datetime.min.time())
            period_end = datetime.combine(period.end_date, datetime.max.time())

        events = self._store.list_events(
            period_start=period_start,
            period_end=period_end,
        )

        # Aggregate per term
        term_stats: Dict[str, Dict[str, object]] = defaultdict(
            lambda: {
                "count": 0,
                "sum_results": 0,
                "zero_results": 0,
                "last_at": datetime.min,
            }
        )

        total_searches = 0
        total_results_sum = 0
        zero_result_searches = 0

        for ev in events:
            term = (ev.get("term") or "").strip().lower()
            if not term:
                continue
            rc = int(ev.get("results_count", 0))
            ts: datetime = ev.get("created_at", datetime.min)

            total_searches += 1
            total_results_sum += rc
            if rc == 0:
                zero_result_searches += 1

            s = term_stats[term]
            s["count"] = int(s["count"]) + 1
            s["sum_results"] = int(s["sum_results"]) + rc
            if rc == 0:
                s["zero_results"] = int(s["zero_results"]) + 1
            if ts > s["last_at"]:
                s["last_at"] = ts

        unique_terms = len(term_stats)

        # Build SearchTermStats lists
        top_terms: List[SearchTermStats] = []
        zero_terms: List[SearchTermStats] = []

        for term, s in term_stats.items():
            count = int(s["count"])
            sum_results = int(s["sum_results"])
            zero_count = int(s["zero_results"])
            last_at: datetime = s["last_at"]
            avg_results = float(sum_results / count) if count > 0 else 0.0

            sts = SearchTermStats(
                term=term,
                search_count=count,
                avg_results=avg_results,
                zero_result_count=zero_count,
                last_searched_at=last_at,
            )
            top_terms.append(sts)
            if zero_count > 0:
                zero_terms.append(sts)

        # Sort by search_count descending
        top_terms.sort(key=lambda s: s.search_count, reverse=True)
        zero_terms.sort(key=lambda s: s.search_count, reverse=True)

        avg_results_per_search = (
            float(total_results_sum / total_searches) if total_searches > 0 else 0.0
        )

        return SearchAnalytics(
            period=period,
            total_searches=total_searches,
            unique_terms=unique_terms,
            zero_result_searches=zero_result_searches,
            top_terms=top_terms[:20],
            zero_result_terms=zero_terms[:20],
            avg_results_per_search=avg_results_per_search,
        )