# app/services/mess/mess_menu_service.py
from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.content import MessMenuRepository
from app.repositories.core import HostelRepository
from app.schemas.common.filters import DateRangeFilter
from app.schemas.mess import (
    MessMenuCreate,
    MessMenuUpdate,
    MenuResponse,
    MenuDetail,
    WeeklyMenu,
    MonthlyMenu,
)
from app.schemas.mess.mess_menu_response import DailyMenuSummary, TodayMenu
from app.services.common import UnitOfWork, errors


class MessMenuService:
    """
    Core Mess Menu service:

    - Create / update menus
    - Get single menu detail
    - Get menu for a specific date (Today view)
    - Weekly and monthly calendar-style views
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _get_menu_repo(self, uow: UnitOfWork) -> MessMenuRepository:
        return uow.get_repo(MessMenuRepository)

    def _get_hostel_repo(self, uow: UnitOfWork) -> HostelRepository:
        return uow.get_repo(HostelRepository)

    # ------------------------------------------------------------------ #
    # Mapping helpers
    # ------------------------------------------------------------------ #
    def _to_menu_response(self, m, *, hostel_name: str) -> MenuResponse:
        """
        Lightweight summary used in list views.
        """
        average_rating = getattr(m, "average_rating", None)
        if average_rating is None:
            average_rating = Decimal("0")

        is_published = bool(getattr(m, "is_published", True))

        return MenuResponse(
            id=m.id,
            created_at=m.created_at,
            updated_at=m.updated_at,
            hostel_id=m.hostel_id,
            hostel_name=hostel_name,
            menu_date=m.menu_date,
            day_of_week=m.day_of_week,
            breakfast_items=m.breakfast_items or [],
            lunch_items=m.lunch_items or [],
            snacks_items=m.snacks_items or [],
            dinner_items=m.dinner_items or [],
            is_special_menu=m.is_special_menu,
            special_occasion=m.special_occasion,
            is_published=is_published,
            average_rating=average_rating,
        )

    def _to_detail(self, m, *, hostel_name: str) -> MenuDetail:
        """
        Full detail view for a menu.

        NOTE:
        - Some metadata (created_by, approved_by, ratings) are not present
          on the MessMenu model in this codebase; we provide safe defaults.
        """
        from datetime import datetime

        created_by_id = getattr(m, "created_by_id", None) or UUID(int=0)
        created_by_name = getattr(m, "created_by_name", "") or ""

        approved_by = getattr(m, "approved_by_id", None)
        approved_by_name = getattr(m, "approved_by_name", None)
        approved_at = getattr(m, "approved_at", None)
        if approved_at is not None and not isinstance(approved_at, datetime):
            approved_at = None

        is_published = bool(getattr(m, "is_published", True))
        published_at = getattr(m, "published_at", None)
        if published_at is not None and not isinstance(published_at, datetime):
            published_at = None

        average_rating = getattr(m, "average_rating", None)
        if average_rating is None:
            average_rating = Decimal("0")
        total_feedback_count = getattr(m, "total_feedback_count", None) or 0

        return MenuDetail(
            id=m.id,
            created_at=m.created_at,
            updated_at=m.updated_at,
            hostel_id=m.hostel_id,
            hostel_name=hostel_name,
            menu_date=m.menu_date,
            day_of_week=m.day_of_week,
            breakfast_items=m.breakfast_items or [],
            breakfast_time=m.breakfast_time,
            lunch_items=m.lunch_items or [],
            lunch_time=m.lunch_time,
            snacks_items=m.snacks_items or [],
            snacks_time=m.snacks_time,
            dinner_items=m.dinner_items or [],
            dinner_time=m.dinner_time,
            vegetarian_available=m.vegetarian_available,
            non_vegetarian_available=m.non_vegetarian_available,
            vegan_available=m.vegan_available,
            jain_available=m.jain_available,
            is_special_menu=m.is_special_menu,
            special_occasion=m.special_occasion,
            created_by=created_by_id,
            created_by_name=created_by_name,
            approved_by=approved_by,
            approved_by_name=approved_by_name,
            approved_at=approved_at,
            is_published=is_published,
            published_at=published_at,
            average_rating=average_rating,
            total_feedback_count=total_feedback_count,
        )

    # ------------------------------------------------------------------ #
    # Core CRUD
    # ------------------------------------------------------------------ #
    def create_menu(self, data: MessMenuCreate) -> MenuDetail:
        """
        Create a new mess menu for a hostel.
        """
        with UnitOfWork(self._session_factory) as uow:
            menu_repo = self._get_menu_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            hostel = hostel_repo.get(data.hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {data.hostel_id} not found")

            payload = {
                "hostel_id": data.hostel_id,
                "menu_date": data.menu_date,
                "day_of_week": data.day_of_week,
                "breakfast_items": data.breakfast_items or [],
                "lunch_items": data.lunch_items or [],
                "snacks_items": data.snacks_items or [],
                "dinner_items": data.dinner_items or [],
                "breakfast_time": data.breakfast_time,
                "lunch_time": data.lunch_time,
                "snacks_time": data.snacks_time,
                "dinner_time": data.dinner_time,
                "is_special_menu": data.is_special_menu,
                "special_occasion": data.special_occasion,
                "vegetarian_available": data.vegetarian_available,
                "non_vegetarian_available": data.non_vegetarian_available,
                "vegan_available": data.vegan_available,
                "jain_available": data.jain_available,
            }
            m = menu_repo.create(payload)  # type: ignore[arg-type]
            uow.commit()

            return self._to_detail(m, hostel_name=hostel.name)

    def update_menu(self, menu_id: UUID, data: MessMenuUpdate) -> MenuDetail:
        """
        Update an existing mess menu (mutable fields only).
        """
        with UnitOfWork(self._session_factory) as uow:
            menu_repo = self._get_menu_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            m = menu_repo.get(menu_id)
            if m is None:
                raise errors.NotFoundError(f"MessMenu {menu_id} not found")

            update_data = data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(m, field):
                    setattr(m, field, value)

            uow.session.flush()  # type: ignore[union-attr]
            uow.commit()

            hostel = hostel_repo.get(m.hostel_id)
            hostel_name = hostel.name if hostel else ""
            return self._to_detail(m, hostel_name=hostel_name)

    def get_menu(self, menu_id: UUID) -> MenuDetail:
        """
        Fetch a single menu by ID.
        """
        with UnitOfWork(self._session_factory) as uow:
            menu_repo = self._get_menu_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            m = menu_repo.get(menu_id)
            if m is None:
                raise errors.NotFoundError(f"MessMenu {menu_id} not found")

            hostel = hostel_repo.get(m.hostel_id)
            hostel_name = hostel.name if hostel else ""
            return self._to_detail(m, hostel_name=hostel_name)

    # ------------------------------------------------------------------ #
    # Date-based access
    # ------------------------------------------------------------------ #
    def get_menu_for_date(self, hostel_id: UUID, menu_date: date) -> MenuDetail:
        """
        Fetch the menu (if any) for a given hostel and date.
        """
        with UnitOfWork(self._session_factory) as uow:
            menu_repo = self._get_menu_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            menus = menu_repo.get_for_date(hostel_id, menu_date)
            if not menus:
                raise errors.NotFoundError(
                    f"No mess menu found for hostel {hostel_id} on {menu_date}"
                )
            m = menus[0]

            hostel = hostel_repo.get(hostel_id)
            hostel_name = hostel.name if hostel else ""
            return self._to_detail(m, hostel_name=hostel_name)

    def get_today_menu(self, hostel_id: UUID, day: Optional[date] = None) -> TodayMenu:
        """
        Return a TodayMenu view for the given hostel and date (default: today).
        """
        from datetime import date as _date

        target_date = day or _date.today()
        detail = self.get_menu_for_date(hostel_id, target_date)

        def _fmt_time(t) -> str:
            return t.strftime("%H:%M") if t else ""

        return TodayMenu(
            hostel_id=detail.hostel_id,
            hostel_name=detail.hostel_name,
            date=detail.menu_date,
            day_of_week=detail.day_of_week,
            breakfast=detail.breakfast_items,
            breakfast_time=_fmt_time(detail.breakfast_time),
            lunch=detail.lunch_items,
            lunch_time=_fmt_time(detail.lunch_time),
            snacks=detail.snacks_items,
            snacks_time=_fmt_time(detail.snacks_time),
            dinner=detail.dinner_items,
            dinner_time=_fmt_time(detail.dinner_time),
            is_special=detail.is_special_menu,
            special_occasion=detail.special_occasion,
            dietary_note=None,
        )

    # ------------------------------------------------------------------ #
    # Weekly / monthly calendars
    # ------------------------------------------------------------------ #
    def get_weekly_menu(
        self,
        hostel_id: UUID,
        week_start_date: date,
    ) -> WeeklyMenu:
        """
        Build a WeeklyMenu for [week_start_date, week_start_date+6].
        """
        week_end_date = week_start_date + timedelta(days=6)  # type: ignore[name-defined]

        from datetime import timedelta  # local import to avoid top-of-file clutter

        with UnitOfWork(self._session_factory) as uow:
            menu_repo = self._get_menu_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            menus = menu_repo.get_range(hostel_id, week_start_date, week_end_date)

        summaries: List[DailyMenuSummary] = []
        for m in sorted(menus, key=lambda x: x.menu_date):
            summaries.append(
                DailyMenuSummary(
                    menu_id=m.id,
                    date=m.menu_date,
                    day_of_week=m.day_of_week,
                    breakfast=m.breakfast_items or [],
                    lunch=m.lunch_items or [],
                    dinner=m.dinner_items or [],
                    is_special=m.is_special_menu,
                    average_rating=None,  # can be filled via feedback analytics
                )
            )

        return WeeklyMenu(
            hostel_id=hostel_id,
            hostel_name=hostel.name,
            week_start_date=week_start_date,
            week_end_date=week_end_date,
            menus=summaries,
        )

    def get_monthly_menu(self, hostel_id: UUID, month: str) -> MonthlyMenu:
        """
        Build a MonthlyMenu calendar for the given month (YYYY-MM).
        """
        try:
            year, m = map(int, month.split("-"))
        except ValueError:
            raise errors.ValidationError("month must be in 'YYYY-MM' format")

        start = date(year, m, 1)
        end = date(year, m, monthrange(year, m)[1])

        with UnitOfWork(self._session_factory) as uow:
            menu_repo = self._get_menu_repo(uow)
            hostel_repo = self._get_hostel_repo(uow)

            hostel = hostel_repo.get(hostel_id)
            if hostel is None:
                raise errors.NotFoundError(f"Hostel {hostel_id} not found")

            menus = menu_repo.get_range(hostel_id, start, end)

        menus_by_date: Dict[str, DailyMenuSummary] = {}
        total_rating = Decimal("0")
        rating_count = 0
        special_days = 0

        for m in menus:
            key = m.menu_date.isoformat()
            avg_rating: Optional[Decimal] = getattr(m, "average_rating", None)
            if avg_rating is not None:
                total_rating += avg_rating
                rating_count += 1
            if m.is_special_menu:
                special_days += 1

            menus_by_date[key] = DailyMenuSummary(
                menu_id=m.id,
                date=m.menu_date,
                day_of_week=m.day_of_week,
                breakfast=m.breakfast_items or [],
                lunch=m.lunch_items or [],
                dinner=m.dinner_items or [],
                is_special=m.is_special_menu,
                average_rating=avg_rating,
            )

        total_days = len(menus_by_date)
        average_rating = (
            total_rating / Decimal(str(rating_count)) if rating_count > 0 else Decimal("0")
        )

        return MonthlyMenu(
            hostel_id=hostel_id,
            hostel_name=hostel.name,
            month=month,
            menus_by_date=menus_by_date,
            total_days=total_days,
            special_days=special_days,
            average_rating=average_rating,
        )