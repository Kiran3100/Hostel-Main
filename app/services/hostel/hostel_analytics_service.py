# app/services/hostel/hostel_analytics_service.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Callable, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import HostelRepository
from app.repositories.content import ReviewRepository
from app.schemas.hostel import (
    HostelAnalytics,
    HostelOccupancyStats,
    HostelRevenueStats,
)
from app.schemas.hostel.hostel_analytics import (
    OccupancyAnalytics,
    OccupancyDataPoint,
    RevenueAnalytics,
    RevenueDataPoint,
    BookingAnalytics as HostelBookingAnalytics,
    BookingDataPoint,
    ComplaintAnalytics as HostelComplaintAnalytics,
    ReviewAnalytics,
)
from app.schemas.common.filters import DateRangeFilter
from app.services.analytics import (
    OccupancyAnalyticsService,
    FinancialAnalyticsService,
)
from app.services.common import UnitOfWork, errors


class HostelAnalyticsService:
    """
    High-level hostel analytics aggregator.

    Uses:
    - OccupancyAnalyticsService
    - FinancialAnalyticsService
    - BookingAnalyticsService
    - ComplaintAnalyticsService
    - ReviewRepository

    to build:
    - HostelAnalytics
    - HostelOccupancyStats
    - HostelRevenueStats
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self._occupancy_svc = OccupancyAnalyticsService(session_factory)
        self._financial_svc = FinancialAnalyticsService(session_factory)
        self._booking_svc = BookingAnalyticsService(session_factory)
        self._complaint_svc = ComplaintAnalyticsService(session_factory)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_review_repo(self, uow: UnitOfWork) -> ReviewRepository:
        return uow.get_repo(ReviewRepository)

    def _now(self) -> datetime:
        return datetime.utcnow()

    # ------------------------------------------------------------------ #
    # Main analytics
    # ------------------------------------------------------------------ #
    def get_hostel_analytics(
        self,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> HostelAnalytics:
        """
        Build a full HostelAnalytics object for the given hostel & period.
        """
        if not (period.start_date and period.end_date):
            raise errors.ValidationError(
                "Both start_date and end_date are required for hostel analytics"
            )

        with UnitOfWork(self._session_factory) as uow:
            hostel_repo = self._get_hostel_repo(uow)
            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")
            hostel_name = hostel.name

        # Occupancy
        occ_report = self._occupancy_svc.get_occupancy_report(hostel_id, period)
        occ_kpi = occ_report.kpi
        occ_trend: List[OccupancyDataPoint] = [
            OccupancyDataPoint(
                date=pt.date,
                occupancy_rate=pt.occupancy_percentage,
                occupied_beds=pt.occupied_beds,
                total_beds=pt.total_beds,
            )
            for pt in occ_report.daily_trend
        ]
        occupancy = OccupancyAnalytics(
            current_occupancy_rate=occ_kpi.current_occupancy_percentage,
            average_occupancy_rate=occ_kpi.average_occupancy_percentage,
            peak_occupancy_rate=occ_kpi.peak_occupancy_percentage,
            lowest_occupancy_rate=occ_kpi.low_occupancy_percentage,
            total_beds=occ_kpi.total_beds,
            occupied_beds=occ_kpi.occupied_beds,
            available_beds=occ_kpi.available_beds,
            occupancy_trend=occ_trend,
            predicted_occupancy_next_month=None,
        )

        # Financial
        fin_report = self._financial_svc.get_financial_report(
            scope_type="hostel",
            scope_id=hostel_id,
            period=period,
        )
        pnl = fin_report.pnl_report
        cashflow = fin_report.cashflow

        revenue_trend: List[RevenueDataPoint] = [
            RevenueDataPoint(
                date=pt.date,
                revenue=pt.inflow,
                collected=pt.inflow,
                pending=Decimal("0"),
            )
            for pt in cashflow.cashflow_timeseries
        ]

        revenue = RevenueAnalytics(
            total_revenue=pnl.revenue.total_revenue,
            rent_revenue=pnl.revenue.rent_revenue,
            mess_revenue=pnl.revenue.mess_revenue,
            other_revenue=pnl.revenue.other_revenue,
            total_collected=cashflow.inflows,
            total_pending=Decimal("0"),
            total_overdue=Decimal("0"),
            collection_rate=fin_report.collection_rate,
            revenue_trend=revenue_trend,
            revenue_vs_last_period=Decimal("0"),
            revenue_vs_last_year=None,
        )

        # Bookings
        booking_summary = self._booking_svc.get_analytics_for_hostel(hostel_id, period)
        kpi = booking_summary.kpi
        trend_points: List[BookingDataPoint] = [
            BookingDataPoint(
                date=pt.date,
                total_bookings=pt.total_bookings,
                approved=pt.confirmed,
                rejected=pt.rejected,
            )
            for pt in booking_summary.trend
        ]
        pending_bookings = (
            kpi.total_bookings
            - kpi.confirmed_bookings
            - kpi.cancelled_bookings
            - kpi.rejected_bookings
        )
        bookings = HostelBookingAnalytics(
            total_bookings=kpi.total_bookings,
            approved_bookings=kpi.confirmed_bookings,
            pending_bookings=pending_bookings,
            rejected_bookings=kpi.rejected_bookings,
            cancelled_bookings=kpi.cancelled_bookings,
            conversion_rate=kpi.booking_conversion_rate,
            cancellation_rate=kpi.cancellation_rate,
            booking_sources={s.value if hasattr(s, "value") else str(s): c for s, c in booking_summary.bookings_by_source.items()},
            booking_trend=trend_points,
        )

        # Complaints (using analytics ComplaintAnalyticsService from analytics package)
        comp_dashboard = self._complaint_svc.get_dashboard_for_hostel(
            hostel_id=hostel_id,
            period=period,
        )
        ckpi = comp_dashboard.kpi
        complaints = HostelComplaintAnalytics(
            total_complaints=ckpi.total_complaints,
            open_complaints=ckpi.open_complaints,
            resolved_complaints=ckpi.resolved_complaints,
            closed_complaints=ckpi.closed_complaints,
            average_resolution_time_hours=ckpi.average_resolution_time_hours,
            resolution_rate=Decimal("0") if ckpi.total_complaints == 0 else (Decimal(str(ckpi.resolved_complaints)) / Decimal(str(ckpi.total_complaints)) * 100),
            complaints_by_category={
                cat.category: cat.count for cat in comp_dashboard.by_category
            },
            complaints_by_priority=comp_dashboard.by_priority,
            sla_compliance_rate=ckpi.sla_compliance_rate,
        )

        # Reviews
        with UnitOfWork(self._session_factory) as uow2:
            review_repo = self._get_review_repo(uow2)
            agg = review_repo.get_aggregates_for_hostel(hostel_id)
            total_reviews = agg["total_reviews"]
            avg_rating = Decimal(str(agg["average_rating"]))

        reviews = ReviewAnalytics(
            total_reviews=total_reviews,
            average_rating=avg_rating,
            rating_distribution={},  # can be filled by a more detailed query later
            average_cleanliness_rating=None,
            average_food_quality_rating=None,
            average_staff_behavior_rating=None,
            average_security_rating=None,
            average_value_rating=None,
            rating_trend=[],
        )

        return HostelAnalytics(
            hostel_id=hostel_id,
            hostel_name=hostel_name,
            period_start=period.start_date,
            period_end=period.end_date,
            occupancy=occupancy,
            revenue=revenue,
            bookings=bookings,
            complaints=complaints,
            reviews=reviews,
            generated_at=self._now(),
        )

    # ------------------------------------------------------------------ #
    # Occupancy & revenue stats
    # ------------------------------------------------------------------ #
    def get_occupancy_stats(
        self,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> HostelOccupancyStats:
        occ_report = self._occupancy_svc.get_occupancy_report(hostel_id, period)
        kpi = occ_report.kpi

        return HostelOccupancyStats(
            hostel_id=hostel_id,
            total_rooms=0,  # not exposed by OccupancyReport; can be fetched from Hostel if needed
            total_beds=kpi.total_beds,
            occupied_beds=kpi.occupied_beds,
            available_beds=kpi.available_beds,
            occupancy_percentage=kpi.current_occupancy_percentage,
            occupancy_by_room_type=[
                # Map from OccupancyByRoomType entries
                {
                    "room_type": rt.room_type,
                    "total_beds": rt.total_beds,
                    "occupied_beds": rt.occupied_beds,
                    "available_beds": rt.total_beds - rt.occupied_beds,
                    "occupancy_percentage": rt.occupancy_percentage,
                }
                for rt in occ_report.by_room_type
            ],
            occupancy_history=[
                OccupancyDataPoint(
                    date=pt.date,
                    occupancy_rate=pt.occupancy_percentage,
                    occupied_beds=pt.occupied_beds,
                    total_beds=pt.total_beds,
                )
                for pt in occ_report.daily_trend
            ],
            projected_occupancy_30_days=None,
            projected_occupancy_90_days=None,
        )

    def get_revenue_stats(
        self,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> HostelRevenueStats:
        fin_report = self._financial_svc.get_financial_report(
            scope_type="hostel",
            scope_id=hostel_id,
            period=period,
        )
        pnl = fin_report.pnl_report
        cashflow = fin_report.cashflow

        monthly_revenue = [
            # Map CashflowPoint(s) by month if desired; for now aggregate as a single month
        ]

        return HostelRevenueStats(
            hostel_id=hostel_id,
            period=period,
            total_revenue=pnl.revenue.total_revenue,
            total_expenses=pnl.expenses.total_expenses,
            net_profit=pnl.net_profit,
            profit_margin=pnl.profit_margin_percentage,
            revenue_by_type=dict(pnl.revenue.revenue_by_payment_type),
            total_collected=cashflow.inflows,
            total_pending=Decimal("0"),
            total_overdue=Decimal("0"),
            collection_efficiency=fin_report.collection_rate,
            monthly_revenue=monthly_revenue,
            revenue_growth_mom=Decimal("0"),
            revenue_growth_yoy=None,
        )