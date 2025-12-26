# app/services/mess/menu_planning_service.py
"""
Menu Planning Service

Orchestrates planning of daily/weekly/monthly menus and special menus.
"""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.mess import (
    MenuTemplateRepository,
    WeeklyMenuPlanRepository,
    MonthlyMenuPlanRepository,
    DailyMenuPlanRepository,
    SpecialOccasionMenuRepository,
    MenuSuggestionRepository,
)
from app.schemas.mess import (
    MenuTemplate,
    WeeklyMenuPlan,
    MonthlyMenuPlan,
    DailyMenuPlan,
    SpecialDayMenu,
    MenuPlanRequest,
    MenuSuggestion,
)
from app.core.exceptions import ValidationException


class MenuPlanningService:
    """
    High-level service for menu planning.

    Responsibilities:
    - Manage templates
    - Generate daily/weekly/monthly plans
    - Handle special occasion menus
    - Provide AI/system suggestions
    """

    def __init__(
        self,
        template_repo: MenuTemplateRepository,
        weekly_repo: WeeklyMenuPlanRepository,
        monthly_repo: MonthlyMenuPlanRepository,
        daily_repo: DailyMenuPlanRepository,
        special_repo: SpecialOccasionMenuRepository,
        suggestion_repo: MenuSuggestionRepository,
    ) -> None:
        self.template_repo = template_repo
        self.weekly_repo = weekly_repo
        self.monthly_repo = monthly_repo
        self.daily_repo = daily_repo
        self.special_repo = special_repo
        self.suggestion_repo = suggestion_repo

    # -------------------------------------------------------------------------
    # Templates
    # -------------------------------------------------------------------------

    def create_template(
        self,
        db: Session,
        hostel_id: UUID,
        template: MenuTemplate,
    ) -> MenuTemplate:
        payload = template.model_dump(exclude_none=True)
        payload["hostel_id"] = hostel_id
        obj = self.template_repo.create(db, payload)
        return MenuTemplate.model_validate(obj)

    def list_templates_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> List[MenuTemplate]:
        objs = self.template_repo.get_by_hostel_id(db, hostel_id)
        return [MenuTemplate.model_validate(o) for o in objs]

    # -------------------------------------------------------------------------
    # Plans
    # -------------------------------------------------------------------------

    def create_weekly_plan(
        self,
        db: Session,
        plan: WeeklyMenuPlan,
    ) -> WeeklyMenuPlan:
        obj = self.weekly_repo.create(db, plan.model_dump(exclude_none=True))
        return WeeklyMenuPlan.model_validate(obj)

    def create_monthly_plan(
        self,
        db: Session,
        plan: MonthlyMenuPlan,
    ) -> MonthlyMenuPlan:
        obj = self.monthly_repo.create(db, plan.model_dump(exclude_none=True))
        return MonthlyMenuPlan.model_validate(obj)

    def create_special_menu(
        self,
        db: Session,
        menu: SpecialDayMenu,
    ) -> SpecialDayMenu:
        obj = self.special_repo.create(db, menu.model_dump(exclude_none=True))
        return SpecialDayMenu.model_validate(obj)

    def generate_plan_from_request(
        self,
        db: Session,
        request: MenuPlanRequest,
    ) -> MonthlyMenuPlan:
        """
        Generate a monthly plan from a high-level plan request.

        Actual generation logic (variety, constraints, costs) is handled
        by the repository.
        """
        data = self.template_repo.generate_plan_from_request(
            db=db,
            request_data=request.model_dump(exclude_none=True),
        )
        return MonthlyMenuPlan.model_validate(data)

    # -------------------------------------------------------------------------
    # Suggestions
    # -------------------------------------------------------------------------

    def get_menu_suggestions(
        self,
        db: Session,
        hostel_id: UUID,
        suggestion_date,
    ) -> List[MenuSuggestion]:
        objs = self.suggestion_repo.get_suggestions_for_date(
            db=db,
            hostel_id=hostel_id,
            suggestion_date=suggestion_date,
        )
        return [MenuSuggestion.model_validate(o) for o in objs]