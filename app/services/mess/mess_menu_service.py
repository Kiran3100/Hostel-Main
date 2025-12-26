# app/services/mess/mess_menu_service.py
"""
Mess Menu Service

Manages daily mess menus:
- CRUD operations
- Listing menus for a date/hostel
- Publishing/unpublishing
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID
from datetime import date

from sqlalchemy.orm import Session

from app.repositories.mess import MessMenuRepository
from app.schemas.mess import (
    MessMenu,
    MessMenuBase,
    MessMenuCreate,
    MessMenuUpdate,
    WeeklyMenu,
    DailyMenuSummary,
    TodayMenu,
)
from app.core.exceptions import ValidationException


class MessMenuService:
    """
    High-level service for mess menus.
    """

    def __init__(self, menu_repo: MessMenuRepository) -> None:
        self.menu_repo = menu_repo

    def create_menu(
        self,
        db: Session,
        data: MessMenuCreate,
    ) -> MessMenu:
        obj = self.menu_repo.create(db, data.model_dump(exclude_none=True))
        return MessMenu.model_validate(obj)

    def update_menu(
        self,
        db: Session,
        menu_id: UUID,
        data: MessMenuUpdate,
    ) -> MessMenu:
        menu = self.menu_repo.get_by_id(db, menu_id)
        if not menu:
            raise ValidationException("Menu not found")

        updated = self.menu_repo.update(
            db,
            menu,
            data=data.model_dump(exclude_none=True),
        )
        return MessMenu.model_validate(updated)

    def get_menu(
        self,
        db: Session,
        menu_id: UUID,
    ) -> MessMenu:
        menu = self.menu_repo.get_by_id(db, menu_id)
        if not menu:
            raise ValidationException("Menu not found")
        return MessMenu.model_validate(menu)

    def get_today_menu_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        target_date: Optional[date] = None,
    ) -> TodayMenu:
        data = self.menu_repo.get_today_menu(
            db=db,
            hostel_id=hostel_id,
            target_date=target_date,
        )
        if not data:
            raise ValidationException("No menu available for the selected date")
        return TodayMenu.model_validate(data)

    def get_weekly_menu_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        week_start: date,
    ) -> WeeklyMenu:
        data = self.menu_repo.get_weekly_menu(
            db=db,
            hostel_id=hostel_id,
            week_start=week_start,
        )
        if not data:
            raise ValidationException("No weekly menu found")
        return WeeklyMenu.model_validate(data)

    def list_daily_summaries_for_month(
        self,
        db: Session,
        hostel_id: UUID,
        year: int,
        month: int,
    ) -> List[DailyMenuSummary]:
        objs = self.menu_repo.get_daily_summaries_for_month(
            db=db,
            hostel_id=hostel_id,
            year=year,
            month=month,
        )
        return [DailyMenuSummary.model_validate(o) for o in objs]

    def publish_menu(
        self,
        db: Session,
        menu_id: UUID,
    ) -> MessMenu:
        menu = self.menu_repo.get_by_id(db, menu_id)
        if not menu:
            raise ValidationException("Menu not found")

        updated = self.menu_repo.publish(db, menu)
        return MessMenu.model_validate(updated)

    def unpublish_menu(
        self,
        db: Session,
        menu_id: UUID,
    ) -> MessMenu:
        menu = self.menu_repo.get_by_id(db, menu_id)
        if not menu:
            raise ValidationException("Menu not found")

        updated = self.menu_repo.unpublish(db, menu)
        return MessMenu.model_validate(updated)