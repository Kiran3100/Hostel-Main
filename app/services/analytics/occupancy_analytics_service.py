# app/services/analytics/occupancy_analytics_service.py
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.core import HostelRepository, RoomRepository, StudentRepository
from app.schemas.analytics.occupancy_analytics import (
    OccupancyReport,
    OccupancyKPI,
    OccupancyTrendPoint,
    ForecastData,
    ForecastPoint,
    OccupancyByRoomType,
)
from app.schemas.common.enums import RoomType
from app.schemas.common.filters import DateRangeFilter
from app.services.common import UnitOfWork


class OccupancyAnalyticsService:
    """
    Occupancy analytics based on core_hostel, core_room, core_student:

    - Daily occupancy trend for a hostel
    - Breakdown by room type
    - Simple KPI metrics
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    def _get_room_repo(self, uow: UnitOfWork) -> RoomRepository:
        return uow.get_repo(RoomRepository)

    def _get_student_repo(self, uow: UnitOfWork) -> StudentRepository:
        return uow.get_repo(StudentRepository)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_occupancy_report(
        self,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> OccupancyReport:
        with UnitOfWork(self._session_factory) as uow:
            hostel_repo = self._get_hostel_repo(uow)
            room_repo = self._get_room_repo(uow)
            student_repo = self._get_student_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise ValueError(f"Hostel {hostel_id} not found")

            rooms = room_repo.list_for_hostel(hostel_id=hostel_id, only_available=False, room_type=None)
            students = student_repo.list_for_hostel(hostel_id, status=None)

        start = period.start_date or date.today()
        end = period.end_date or start

        # Current capacity & occupancy from hostel snapshot
        total_beds = hostel.total_beds or 0
        occupied_beds = hostel.occupied_beds or 0
        available_beds = max(0, total_beds - occupied_beds)
        current_occ_pct = (
            Decimal(str(occupied_beds / total_beds * 100)) if total_beds > 0 else Decimal("0")
        )

        # Daily trend: compute occupancy from student stay dates
        daily_trend: List[OccupancyTrendPoint] = []
        agg_occupied = 0
        peak_occ_pct = Decimal("0")
        low_occ_pct = None

        cur = start
        while cur <= end:
            occ = self._occupied_beds_for_day(cur, students)
            pct = Decimal(str(occ / total_beds * 100)) if total_beds > 0 else Decimal("0")

            daily_trend.append(
                OccupancyTrendPoint(
                    date=cur,
                    occupancy_percentage=pct,
                    occupied_beds=occ,
                    total_beds=total_beds,
                )
            )
            agg_occupied += occ
            peak_occ_pct = max(peak_occ_pct, pct)
            if low_occ_pct is None or pct < low_occ_pct:
                low_occ_pct = pct
            cur += timedelta(days=1)

        days = (end - start).days + 1
        avg_occ_pct = (
            Decimal(str(agg_occupied / days / total_beds * 100)) if days > 0 and total_beds > 0 else Decimal("0")
        )
        low_occ_pct = low_occ_pct or Decimal("0")

        kpi = OccupancyKPI(
            hostel_id=hostel_id,
            hostel_name=hostel.name,
            current_occupancy_percentage=current_occ_pct,
            average_occupancy_percentage=avg_occ_pct,
            peak_occupancy_percentage=peak_occ_pct,
            low_occupancy_percentage=low_occ_pct,
            total_beds=total_beds,
            occupied_beds=occupied_beds,
            available_beds=available_beds,
        )

        # By room type
        by_room_type: List[OccupancyByRoomType] = []
        room_type_totals: Dict[RoomType, int] = {}
        room_type_occupied: Dict[RoomType, int] = {}

        # Count beds per room type from Room.total_beds
        for r in rooms:
            rt = r.room_type
            room_type_totals[rt] = room_type_totals.get(rt, 0) + (r.total_beds or 0)

        # Count occupied per room type from current students
        room_id_to_type: Dict[UUID, RoomType] = {r.id: r.room_type for r in rooms}
        for s in students:
            if s.room_id and s.room_id in room_id_to_type:
                rt = room_id_to_type[s.room_id]
                room_type_occupied[rt] = room_type_occupied.get(rt, 0) + 1

        for rt, total_rt_beds in room_type_totals.items():
            occ_rt = room_type_occupied.get(rt, 0)
            pct_rt = (
                Decimal(str(occ_rt / total_rt_beds * 100)) if total_rt_beds > 0 else Decimal("0")
            )
            by_room_type.append(
                OccupancyByRoomType(
                    room_type=rt.value if hasattr(rt, "value") else str(rt),
                    total_beds=total_rt_beds,
                    occupied_beds=occ_rt,
                    occupancy_percentage=pct_rt,
                )
            )

        # By floor is optional; leaving empty dict for now
        report = OccupancyReport(
            hostel_id=hostel_id,
            hostel_name=hostel.name,
            period=DateRangeFilter(start_date=start, end_date=end),
            generated_at=datetime.utcnow(),
            kpi=kpi,
            daily_trend=daily_trend,
            by_room_type=by_room_type,
            by_floor={},
            forecast=None,  # can be added later
        )
        return report

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _occupied_beds_for_day(self, day: date, students: List[Any]) -> int:  # type: ignore[valid-type]
        """
        Count students whose stay includes the given day.
        """
        count = 0
        for s in students:
            # check_in_date <= day <= (actual_checkout_date or expected_checkout_date or "forever")
            cin = s.check_in_date
            if not cin:
                continue
            if cin > day:
                continue
            cout = s.actual_checkout_date or s.expected_checkout_date
            if cout and day > cout:
                continue
            count += 1
        return count