# app/services/mess/nutritional_info_service.py
"""
Nutritional Info Service

Handles nutritional analysis for menu items and menus:
- Per-item nutritional info
- Aggregate nutritional reports
"""

from __future__ import annotations

from typing import List
from uuid import UUID
from datetime import date

from sqlalchemy.orm import Session

from app.repositories.mess import NutritionalInfoRepository
from app.schemas.mess import (
    NutritionalInfo,
    NutritionalReport,
)
from app.core.exceptions import ValidationException


class NutritionalInfoService:
    """
    High-level nutritional info service.
    """

    def __init__(self, nutrit_repo: NutritionalInfoRepository) -> None:
        self.nutrit_repo = nutrit_repo

    def get_nutritional_info_for_item(
        self,
        db: Session,
        meal_item_id: UUID,
    ) -> NutritionalInfo:
        obj = self.nutrit_repo.get_by_meal_item_id(db, meal_item_id)
        if not obj:
            raise ValidationException("Nutritional info not found for item")
        return NutritionalInfo.model_validate(obj)

    def get_nutritional_report_for_menu(
        self,
        db: Session,
        menu_id: UUID,
    ) -> NutritionalReport:
        data = self.nutrit_repo.build_report_for_menu(db, menu_id)
        if not data:
            raise ValidationException("No nutritional report available for this menu")
        return NutritionalReport.model_validate(data)

    def get_nutritional_report_for_period(
        self,
        db: Session,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> NutritionalReport:
        data = self.nutrit_repo.build_report_for_period(
            db=db,
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
        )
        if not data:
            raise ValidationException("No nutritional report available for this period")
        return NutritionalReport.model_validate(data)