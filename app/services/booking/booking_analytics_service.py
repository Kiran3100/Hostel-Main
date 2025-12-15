# app/services/booking/booking_analytics_service.py
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, List, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.transactions import BookingRepository
from app.schemas.analytics.booking_analytics import (
    BookingAnalyticsSummary,
    BookingKPI,
    BookingTrendPoint,
    BookingFunnel,
    CancellationAnalytics,
)
from app.schemas.common.enums import BookingStatus, BookingSource
from app.schemas.common.filters import DateRangeFilter
from app.services.common import UnitOfWork


class BookingAnalyticsService:
    """
    Booking analytics based on txn_booking.

    - KPI (counts, rates)
    - Trend by day
    - Funnel approximation
    - Cancellation analytics
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_repo(self, uow: UnitOfWork) -> BookingRepository:
        return uow.get_repo(BookingRepository)

    def get_analytics_for_hostel(
        self,
        hostel_id: Optional[UUID],
        period: DateRangeFilter,
    ) -> BookingAnalyticsSummary:
        with UnitOfWork(self._session_factory) as uow:
            repo = self._get_repo(uow)
            filters: dict = {}
            if hostel_id:
                filters["hostel_id"] = hostel_id
            bookings = repo.get_multi(
                skip=0,
                limit=None,  # type: ignore[arg-type]
                filters=filters or None,
            )

        start = period.start_date or date.min
        end = period.end_date or date.max

        filtered = []
        for b in bookings:
            d = b.booking_date.date()
            if d < start or d > end:
                continue
            filtered.append(b)

        total = len(filtered)
        confirmed = 0
        cancelled = 0
        rejected = 0
        total_revenue = Decimal("0")

        trend_by_date: Dict[str, Dict[str, Decimal | int]] = {}
        cancellations_by_reason: Dict[str, int] = {}
        cancellations_by_status: Dict[BookingStatus, int] = {}
        bookings_by_source: Dict[BookingSource, int] = {}

        for b in filtered:
            if b.booking_status == BookingStatus.CONFIRMED:
                confirmed += 1
            if b.booking_status == BookingStatus.CANCELLED:
                cancelled += 1
            if b.booking_status == BookingStatus.REJECTED:
                rejected += 1

            total_revenue += b.total_amount or Decimal("0")

            day = b.booking_date.date().isoformat()
            bucket = trend_by_date.setdefault(
                day,
                {"total": 0, "confirmed": 0, "cancelled": 0, "rejected": 0, "revenue": Decimal("0")},
            )
            bucket["total"] = int(bucket["total"]) + 1
            if b.booking_status == BookingStatus.CONFIRMED:
                bucket["confirmed"] = int(bucket["confirmed"]) + 1
            if b.booking_status == BookingStatus.CANCELLED:
                bucket["cancelled"] = int(bucket["cancelled"]) + 1
            if b.booking_status == BookingStatus.REJECTED:
                bucket["rejected"] = int(bucket["rejected"]) + 1
            bucket["revenue"] = bucket["revenue"] + b.total_amount

            bookings_by_source[b.source] = bookings_by_source.get(b.source, 0) + 1

        trend_points: List[BookingTrendPoint] = []
        for d, vals in sorted(trend_by_date.items()):
            trend_points.append(
                BookingTrendPoint(
                    date=date.fromisoformat(d),
                    total_bookings=int(vals["total"]),
                    confirmed=int(vals["confirmed"]),
                    cancelled=int(vals["cancelled"]),
                    rejected=int(vals["rejected"]),
                    revenue_for_day=vals["revenue"],
                )
            )

        kpi = BookingKPI(
            hostel_id=hostel_id,
            hostel_name=None,
            total_bookings=total,
            confirmed_bookings=confirmed,
            cancelled_bookings=cancelled,
            rejected_bookings=rejected,
            booking_conversion_rate=Decimal(str(confirmed / total * 100)) if total > 0 else Decimal("0"),
            cancellation_rate=Decimal(str(cancelled / total * 100)) if total > 0 else Decimal("0"),
            average_lead_time_days=Decimal("0"),
        )

        funnel = BookingFunnel(
            period=period,
            generated_at=None,
            hostel_page_views=0,
            booking_form_starts=0,
            booking_submissions=total,
            bookings_confirmed=confirmed,
            view_to_start_rate=Decimal("0"),
            start_to_submit_rate=Decimal("0"),
            submit_to_confirm_rate=Decimal(str(confirmed / total * 100)) if total > 0 else Decimal("0"),
            view_to_confirm_rate=Decimal("0"),
        )

        cancellations = CancellationAnalytics(
            period=period,
            total_cancellations=cancelled,
            cancellation_rate=Decimal(str(cancelled / total * 100)) if total > 0 else Decimal("0"),
            cancellations_by_reason=cancellations_by_reason,
            cancellations_by_status=cancellations_by_status,
            average_time_before_check_in_cancelled_days=Decimal("0"),
        )

        conversion_rate_by_source: Dict[BookingSource, Decimal] = {}
        for src, count in bookings_by_source.items():
            if count > 0:
                src_confirmed = sum(
                    1 for b in filtered if b.source == src and b.booking_status == BookingStatus.CONFIRMED
                )
                conversion_rate_by_source[src] = Decimal(str(src_confirmed / count * 100))
            else:
                conversion_rate_by_source[src] = Decimal("0")

        return BookingAnalyticsSummary(
            hostel_id=hostel_id,
            hostel_name=None,
            period=period,
            generated_at=None,
            kpi=kpi,
            trend=trend_points,
            funnel=funnel,
            cancellations=cancellations,
            bookings_by_source=bookings_by_source,
            conversion_rate_by_source=conversion_rate_by_source,
        )