# --- File: C:\Hostel-Main\app\repositories\mess\menu_planning_repository.py ---

"""
Menu Planning Repository Module.

Manages menu templates, weekly/monthly plans, special occasions,
AI suggestions, and planning rules with strategic insights.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from app.models.mess.menu_planning import (
    DailyMenuPlan,
    MenuPlanningRule,
    MenuSuggestion,
    MenuTemplate,
    MonthlyMenuPlan,
    SeasonalMenu,
    SpecialOccasionMenu,
    WeeklyMenuPlan,
)
from app.repositories.base.base_repository import BaseRepository


class MenuTemplateRepository(BaseRepository[MenuTemplate]):
    """
    Repository for managing menu templates.
    
    Handles reusable menu patterns with seasonal applicability
    and performance tracking.
    """

    def __init__(self, db_session):
        """Initialize repository with MenuTemplate model."""
        super().__init__(MenuTemplate, db_session)

    async def find_by_hostel(
        self,
        hostel_id: UUID,
        active_only: bool = True,
        include_deleted: bool = False
    ) -> List[MenuTemplate]:
        """
        Get templates for a hostel.
        
        Args:
            hostel_id: Hostel identifier
            active_only: Only active templates
            include_deleted: Include soft-deleted templates
            
        Returns:
            List of menu templates
        """
        conditions = [MenuTemplate.hostel_id == hostel_id]
        
        if active_only:
            conditions.append(MenuTemplate.is_active == True)
            
        if not include_deleted:
            conditions.append(MenuTemplate.deleted_at.is_(None))
            
        query = select(MenuTemplate).where(and_(*conditions))
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_global_templates(
        self,
        active_only: bool = True
    ) -> List[MenuTemplate]:
        """
        Get global/shared templates.
        
        Args:
            active_only: Only active templates
            
        Returns:
            List of global templates
        """
        conditions = [
            MenuTemplate.hostel_id.is_(None),
            MenuTemplate.is_public == True
        ]
        
        if active_only:
            conditions.append(MenuTemplate.is_active == True)
            
        conditions.append(MenuTemplate.deleted_at.is_(None))
        
        query = select(MenuTemplate).where(and_(*conditions))
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_by_type(
        self,
        hostel_id: Optional[UUID],
        template_type: str,
        active_only: bool = True
    ) -> List[MenuTemplate]:
        """
        Find templates by type.
        
        Args:
            hostel_id: Hostel identifier (None for global)
            template_type: Type of template
            active_only: Only active templates
            
        Returns:
            List of matching templates
        """
        conditions = [MenuTemplate.template_type == template_type]
        
        if hostel_id:
            conditions.append(
                or_(
                    MenuTemplate.hostel_id == hostel_id,
                    and_(
                        MenuTemplate.hostel_id.is_(None),
                        MenuTemplate.is_public == True
                    )
                )
            )
        else:
            conditions.append(MenuTemplate.hostel_id.is_(None))
            
        if active_only:
            conditions.append(MenuTemplate.is_active == True)
            
        conditions.append(MenuTemplate.deleted_at.is_(None))
        
        query = select(MenuTemplate).where(and_(*conditions))
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_seasonal_templates(
        self,
        hostel_id: Optional[UUID],
        season: Optional[str] = None,
        month: Optional[str] = None
    ) -> List[MenuTemplate]:
        """
        Find templates for specific season or month.
        
        Args:
            hostel_id: Hostel identifier (None for global)
            season: Season name (optional)
            month: Month name (optional)
            
        Returns:
            List of seasonal templates
        """
        conditions = [
            MenuTemplate.is_active == True,
            MenuTemplate.deleted_at.is_(None)
        ]
        
        if hostel_id:
            conditions.append(
                or_(
                    MenuTemplate.hostel_id == hostel_id,
                    and_(
                        MenuTemplate.hostel_id.is_(None),
                        MenuTemplate.is_public == True
                    )
                )
            )
            
        if season:
            conditions.append(
                or_(
                    MenuTemplate.applicable_season == season,
                    MenuTemplate.applicable_season == 'all'
                )
            )
            
        if month:
            conditions.append(
                or_(
                    MenuTemplate.applicable_months.any(month),
                    func.array_length(MenuTemplate.applicable_months, 1).is_(None)
                )
            )
            
        query = select(MenuTemplate).where(and_(*conditions))
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_most_used_templates(
        self,
        hostel_id: Optional[UUID] = None,
        limit: int = 10
    ) -> List[MenuTemplate]:
        """
        Get most frequently used templates.
        
        Args:
            hostel_id: Hostel identifier (optional)
            limit: Maximum number of results
            
        Returns:
            List of popular templates
        """
        conditions = [
            MenuTemplate.is_active == True,
            MenuTemplate.deleted_at.is_(None)
        ]
        
        if hostel_id:
            conditions.append(MenuTemplate.hostel_id == hostel_id)
            
        query = (
            select(MenuTemplate)
            .where(and_(*conditions))
            .order_by(desc(MenuTemplate.usage_count))
            .limit(limit)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_top_rated_templates(
        self,
        hostel_id: Optional[UUID] = None,
        min_ratings: int = 3,
        limit: int = 10
    ) -> List[MenuTemplate]:
        """
        Get highest rated templates.
        
        Args:
            hostel_id: Hostel identifier (optional)
            min_ratings: Minimum number of ratings
            limit: Maximum number of results
            
        Returns:
            List of top-rated templates
        """
        conditions = [
            MenuTemplate.is_active == True,
            MenuTemplate.deleted_at.is_(None),
            MenuTemplate.total_ratings >= min_ratings
        ]
        
        if hostel_id:
            conditions.append(MenuTemplate.hostel_id == hostel_id)
            
        query = (
            select(MenuTemplate)
            .where(and_(*conditions))
            .order_by(desc(MenuTemplate.average_rating))
            .limit(limit)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def record_usage(
        self,
        template_id: UUID
    ) -> Optional[MenuTemplate]:
        """
        Record template usage.
        
        Args:
            template_id: Template identifier
            
        Returns:
            Updated MenuTemplate
        """
        template = await self.get_by_id(template_id)
        if not template:
            return None
            
        template.usage_count += 1
        template.last_used_date = date.today()
        
        await self.db_session.commit()
        await self.db_session.refresh(template)
        
        return template


class WeeklyMenuPlanRepository(BaseRepository[WeeklyMenuPlan]):
    """
    Repository for weekly menu plans.
    
    Manages week-long menu planning with template integration
    and approval tracking.
    """

    def __init__(self, db_session):
        """Initialize repository with WeeklyMenuPlan model."""
        super().__init__(WeeklyMenuPlan, db_session)

    async def find_by_hostel(
        self,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_deleted: bool = False
    ) -> List[WeeklyMenuPlan]:
        """
        Get weekly plans for hostel.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Start date filter (optional)
            end_date: End date filter (optional)
            include_deleted: Include soft-deleted plans
            
        Returns:
            List of weekly plans
        """
        conditions = [WeeklyMenuPlan.hostel_id == hostel_id]
        
        if start_date:
            conditions.append(WeeklyMenuPlan.week_start_date >= start_date)
        if end_date:
            conditions.append(WeeklyMenuPlan.week_end_date <= end_date)
            
        if not include_deleted:
            conditions.append(WeeklyMenuPlan.deleted_at.is_(None))
            
        query = (
            select(WeeklyMenuPlan)
            .where(and_(*conditions))
            .order_by(desc(WeeklyMenuPlan.week_start_date))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_by_week(
        self,
        hostel_id: UUID,
        year: int,
        week_number: int
    ) -> Optional[WeeklyMenuPlan]:
        """
        Get plan for specific week.
        
        Args:
            hostel_id: Hostel identifier
            year: Year
            week_number: Week number (1-53)
            
        Returns:
            WeeklyMenuPlan if found
        """
        query = (
            select(WeeklyMenuPlan)
            .where(WeeklyMenuPlan.hostel_id == hostel_id)
            .where(WeeklyMenuPlan.year == year)
            .where(WeeklyMenuPlan.week_number == week_number)
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_current_week_plan(
        self,
        hostel_id: UUID
    ) -> Optional[WeeklyMenuPlan]:
        """
        Get plan for current week.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            Current week's plan if found
        """
        today = date.today()
        year, week_num, _ = today.isocalendar()
        
        return await self.get_by_week(hostel_id, year, week_num)

    async def get_with_daily_plans(
        self,
        plan_id: UUID
    ) -> Optional[WeeklyMenuPlan]:
        """
        Get plan with daily plans loaded.
        
        Args:
            plan_id: WeeklyMenuPlan identifier
            
        Returns:
            Plan with daily plans
        """
        query = (
            select(WeeklyMenuPlan)
            .where(WeeklyMenuPlan.id == plan_id)
            .options(selectinload(WeeklyMenuPlan.daily_plans))
        )
        
        result = await self.db_session.execute(query)
        return result.unique().scalar_one_or_none()

    async def create_from_template(
        self,
        hostel_id: UUID,
        template_id: UUID,
        week_start: date,
        week_end: date,
        creator_id: UUID
    ) -> WeeklyMenuPlan:
        """
        Create weekly plan from template.
        
        Args:
            hostel_id: Hostel identifier
            template_id: Template to use
            week_start: Week start date
            week_end: Week end date
            creator_id: User creating plan
            
        Returns:
            Created WeeklyMenuPlan
        """
        year, week_num, _ = week_start.isocalendar()
        
        plan = WeeklyMenuPlan(
            hostel_id=hostel_id,
            template_id=template_id,
            week_start_date=week_start,
            week_end_date=week_end,
            week_number=week_num,
            year=year,
            created_by=creator_id,
            created_from_template=True
        )
        
        self.db_session.add(plan)
        await self.db_session.commit()
        await self.db_session.refresh(plan)
        
        # Record template usage
        await MenuTemplateRepository(self.db_session).record_usage(template_id)
        
        return plan

    async def approve_plan(
        self,
        plan_id: UUID,
        approver_id: UUID
    ) -> Optional[WeeklyMenuPlan]:
        """
        Approve weekly plan.
        
        Args:
            plan_id: Plan identifier
            approver_id: User approving
            
        Returns:
            Updated WeeklyMenuPlan
        """
        plan = await self.get_by_id(plan_id)
        if not plan:
            return None
            
        plan.is_approved = True
        plan.approved_by = approver_id
        plan.approved_at = datetime.utcnow()
        
        await self.db_session.commit()
        await self.db_session.refresh(plan)
        
        return plan

    async def finalize_plan(
        self,
        plan_id: UUID
    ) -> Optional[WeeklyMenuPlan]:
        """
        Finalize weekly plan for execution.
        
        Args:
            plan_id: Plan identifier
            
        Returns:
            Updated WeeklyMenuPlan
        """
        plan = await self.get_by_id(plan_id)
        if not plan:
            return None
            
        plan.is_finalized = True
        plan.finalized_at = datetime.utcnow()
        
        await self.db_session.commit()
        await self.db_session.refresh(plan)
        
        return plan


class MonthlyMenuPlanRepository(BaseRepository[MonthlyMenuPlan]):
    """
    Repository for monthly menu plans.
    
    Manages month-long planning with budget tracking and
    special occasion integration.
    """

    def __init__(self, db_session):
        """Initialize repository with MonthlyMenuPlan model."""
        super().__init__(MonthlyMenuPlan, db_session)

    async def find_by_hostel(
        self,
        hostel_id: UUID,
        year: Optional[int] = None,
        include_deleted: bool = False
    ) -> List[MonthlyMenuPlan]:
        """
        Get monthly plans for hostel.
        
        Args:
            hostel_id: Hostel identifier
            year: Year filter (optional)
            include_deleted: Include soft-deleted plans
            
        Returns:
            List of monthly plans
        """
        conditions = [MonthlyMenuPlan.hostel_id == hostel_id]
        
        if year:
            conditions.append(MonthlyMenuPlan.year == year)
            
        if not include_deleted:
            conditions.append(MonthlyMenuPlan.deleted_at.is_(None))
            
        query = (
            select(MonthlyMenuPlan)
            .where(and_(*conditions))
            .order_by(desc(MonthlyMenuPlan.year), desc(MonthlyMenuPlan.month))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_by_month(
        self,
        hostel_id: UUID,
        month: str
    ) -> Optional[MonthlyMenuPlan]:
        """
        Get plan for specific month.
        
        Args:
            hostel_id: Hostel identifier
            month: Month in YYYY-MM format
            
        Returns:
            MonthlyMenuPlan if found
        """
        query = (
            select(MonthlyMenuPlan)
            .where(MonthlyMenuPlan.hostel_id == hostel_id)
            .where(MonthlyMenuPlan.month == month)
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_current_month_plan(
        self,
        hostel_id: UUID
    ) -> Optional[MonthlyMenuPlan]:
        """
        Get plan for current month.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            Current month's plan if found
        """
        today = date.today()
        month_str = today.strftime('%Y-%m')
        
        return await self.get_by_month(hostel_id, month_str)

    async def get_with_details(
        self,
        plan_id: UUID
    ) -> Optional[MonthlyMenuPlan]:
        """
        Get plan with daily plans and special occasions.
        
        Args:
            plan_id: Plan identifier
            
        Returns:
            Plan with relationships loaded
        """
        query = (
            select(MonthlyMenuPlan)
            .where(MonthlyMenuPlan.id == plan_id)
            .options(
                selectinload(MonthlyMenuPlan.daily_plans),
                selectinload(MonthlyMenuPlan.special_occasions)
            )
        )
        
        result = await self.db_session.execute(query)
        return result.unique().scalar_one_or_none()


class DailyMenuPlanRepository(BaseRepository[DailyMenuPlan]):
    """
    Repository for daily menu plans.
    
    Manages individual day plans within weekly/monthly
    planning context.
    """

    def __init__(self, db_session):
        """Initialize repository with DailyMenuPlan model."""
        super().__init__(DailyMenuPlan, db_session)

    async def find_by_date(
        self,
        hostel_id: UUID,
        plan_date: date
    ) -> Optional[DailyMenuPlan]:
        """
        Get daily plan for specific date.
        
        Args:
            hostel_id: Hostel identifier
            plan_date: Date to find
            
        Returns:
            DailyMenuPlan if found
        """
        # Find through weekly or monthly plan
        query = (
            select(DailyMenuPlan)
            .join(WeeklyMenuPlan, isouter=True)
            .join(MonthlyMenuPlan, isouter=True)
            .where(DailyMenuPlan.plan_date == plan_date)
            .where(
                or_(
                    WeeklyMenuPlan.hostel_id == hostel_id,
                    MonthlyMenuPlan.hostel_id == hostel_id
                )
            )
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def find_by_week(
        self,
        weekly_plan_id: UUID
    ) -> List[DailyMenuPlan]:
        """
        Get all daily plans for a week.
        
        Args:
            weekly_plan_id: WeeklyMenuPlan identifier
            
        Returns:
            List of daily plans
        """
        query = (
            select(DailyMenuPlan)
            .where(DailyMenuPlan.weekly_plan_id == weekly_plan_id)
            .order_by(DailyMenuPlan.plan_date)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def approve_daily_plan(
        self,
        plan_id: UUID
    ) -> Optional[DailyMenuPlan]:
        """
        Approve daily plan.
        
        Args:
            plan_id: DailyMenuPlan identifier
            
        Returns:
            Updated DailyMenuPlan
        """
        plan = await self.get_by_id(plan_id)
        if not plan:
            return None
            
        plan.is_approved = True
        
        await self.db_session.commit()
        await self.db_session.refresh(plan)
        
        return plan


class SpecialOccasionMenuRepository(BaseRepository[SpecialOccasionMenu]):
    """
    Repository for special occasion menus.
    
    Manages enhanced menus for festivals, celebrations,
    and special events.
    """

    def __init__(self, db_session):
        """Initialize repository with SpecialOccasionMenu model."""
        super().__init__(SpecialOccasionMenu, db_session)

    async def find_by_hostel(
        self,
        hostel_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_deleted: bool = False
    ) -> List[SpecialOccasionMenu]:
        """
        Get special occasion menus for hostel.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Start date filter (optional)
            end_date: End date filter (optional)
            include_deleted: Include soft-deleted menus
            
        Returns:
            List of special occasion menus
        """
        conditions = [SpecialOccasionMenu.hostel_id == hostel_id]
        
        if start_date:
            conditions.append(SpecialOccasionMenu.occasion_date >= start_date)
        if end_date:
            conditions.append(SpecialOccasionMenu.occasion_date <= end_date)
            
        if not include_deleted:
            conditions.append(SpecialOccasionMenu.deleted_at.is_(None))
            
        query = (
            select(SpecialOccasionMenu)
            .where(and_(*conditions))
            .order_by(SpecialOccasionMenu.occasion_date)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_upcoming_occasions(
        self,
        hostel_id: UUID,
        days_ahead: int = 30
    ) -> List[SpecialOccasionMenu]:
        """
        Get upcoming special occasions.
        
        Args:
            hostel_id: Hostel identifier
            days_ahead: Number of days to look ahead
            
        Returns:
            List of upcoming occasions
        """
        today = date.today()
        future_date = today + timedelta(days=days_ahead)
        
        return await self.find_by_hostel(
            hostel_id=hostel_id,
            start_date=today,
            end_date=future_date
        )

    async def find_by_type(
        self,
        hostel_id: UUID,
        occasion_type: str
    ) -> List[SpecialOccasionMenu]:
        """
        Find occasions by type.
        
        Args:
            hostel_id: Hostel identifier
            occasion_type: Type of occasion
            
        Returns:
            List of matching occasions
        """
        query = (
            select(SpecialOccasionMenu)
            .where(SpecialOccasionMenu.hostel_id == hostel_id)
            .where(SpecialOccasionMenu.occasion_type == occasion_type)
            .where(SpecialOccasionMenu.deleted_at.is_(None))
            .order_by(SpecialOccasionMenu.occasion_date)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())


class MenuSuggestionRepository(BaseRepository[MenuSuggestion]):
    """
    Repository for AI-generated menu suggestions.
    
    Manages intelligent menu recommendations with
    scoring and acceptance tracking.
    """

    def __init__(self, db_session):
        """Initialize repository with MenuSuggestion model."""
        super().__init__(MenuSuggestion, db_session)

    async def find_by_hostel(
        self,
        hostel_id: UUID,
        suggestion_date: Optional[date] = None
    ) -> List[MenuSuggestion]:
        """
        Get suggestions for hostel.
        
        Args:
            hostel_id: Hostel identifier
            suggestion_date: Specific date (optional)
            
        Returns:
            List of suggestions
        """
        conditions = [MenuSuggestion.hostel_id == hostel_id]
        
        if suggestion_date:
            conditions.append(MenuSuggestion.suggestion_date == suggestion_date)
            
        query = (
            select(MenuSuggestion)
            .where(and_(*conditions))
            .order_by(desc(MenuSuggestion.overall_score))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_top_suggestions(
        self,
        hostel_id: UUID,
        suggestion_date: date,
        limit: int = 5
    ) -> List[MenuSuggestion]:
        """
        Get top-scored suggestions.
        
        Args:
            hostel_id: Hostel identifier
            suggestion_date: Date for suggestions
            limit: Maximum number of results
            
        Returns:
            List of top suggestions
        """
        query = (
            select(MenuSuggestion)
            .where(MenuSuggestion.hostel_id == hostel_id)
            .where(MenuSuggestion.suggestion_date == suggestion_date)
            .where(MenuSuggestion.is_dismissed == False)
            .order_by(desc(MenuSuggestion.overall_score))
            .limit(limit)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def accept_suggestion(
        self,
        suggestion_id: UUID,
        accepter_id: UUID
    ) -> Optional[MenuSuggestion]:
        """
        Accept a suggestion.
        
        Args:
            suggestion_id: Suggestion identifier
            accepter_id: User accepting
            
        Returns:
            Updated MenuSuggestion
        """
        suggestion = await self.get_by_id(suggestion_id)
        if not suggestion:
            return None
            
        suggestion.is_accepted = True
        suggestion.accepted_by = accepter_id
        suggestion.accepted_at = datetime.utcnow()
        
        await self.db_session.commit()
        await self.db_session.refresh(suggestion)
        
        return suggestion

    async def dismiss_suggestion(
        self,
        suggestion_id: UUID,
        reason: Optional[str] = None
    ) -> Optional[MenuSuggestion]:
        """
        Dismiss a suggestion.
        
        Args:
            suggestion_id: Suggestion identifier
            reason: Dismissal reason (optional)
            
        Returns:
            Updated MenuSuggestion
        """
        suggestion = await self.get_by_id(suggestion_id)
        if not suggestion:
            return None
            
        suggestion.is_dismissed = True
        suggestion.dismissal_reason = reason
        
        await self.db_session.commit()
        await self.db_session.refresh(suggestion)
        
        return suggestion


class MenuPlanningRuleRepository(BaseRepository[MenuPlanningRule]):
    """
    Repository for menu planning rules.
    
    Manages business rules for automated menu planning
    with constraint validation.
    """

    def __init__(self, db_session):
        """Initialize repository with MenuPlanningRule model."""
        super().__init__(MenuPlanningRule, db_session)

    async def get_active_rules(
        self,
        hostel_id: Optional[UUID] = None,
        rule_type: Optional[str] = None
    ) -> List[MenuPlanningRule]:
        """
        Get active planning rules.
        
        Args:
            hostel_id: Hostel identifier (None for global)
            rule_type: Rule type filter (optional)
            
        Returns:
            List of active rules
        """
        conditions = [
            MenuPlanningRule.is_active == True,
            MenuPlanningRule.deleted_at.is_(None)
        ]
        
        if hostel_id:
            conditions.append(
                or_(
                    MenuPlanningRule.hostel_id == hostel_id,
                    MenuPlanningRule.hostel_id.is_(None)
                )
            )
        else:
            conditions.append(MenuPlanningRule.hostel_id.is_(None))
            
        if rule_type:
            conditions.append(MenuPlanningRule.rule_type == rule_type)
            
        query = (
            select(MenuPlanningRule)
            .where(and_(*conditions))
            .order_by(desc(MenuPlanningRule.priority))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def validate_menu_against_rules(
        self,
        hostel_id: UUID,
        menu_data: Dict
    ) -> Tuple[bool, List[str]]:
        """
        Validate menu against active rules.
        
        Args:
            hostel_id: Hostel identifier
            menu_data: Menu data to validate
            
        Returns:
            Tuple of (is_valid, list of violations)
        """
        rules = await self.get_active_rules(hostel_id=hostel_id)
        
        violations = []
        
        for rule in rules:
            # Check variety rules
            if rule.min_days_between_repeat:
                # Would need historical data check
                pass
                
            # Check budget rules
            if rule.max_cost_per_person_per_day:
                cost = menu_data.get('estimated_cost_per_person', 0)
                if cost > rule.max_cost_per_person_per_day:
                    violations.append(
                        f"Cost exceeds maximum: {cost} > {rule.max_cost_per_person_per_day}"
                    )
                    
            # Check nutritional rules
            if rule.min_daily_calories:
                calories = menu_data.get('total_calories', 0)
                if calories < rule.min_daily_calories:
                    violations.append(
                        f"Calories below minimum: {calories} < {rule.min_daily_calories}"
                    )
                    
            # Add more rule checks based on rule configuration
            
        is_valid = len(violations) == 0
        
        return is_valid, violations


class SeasonalMenuRepository(BaseRepository[SeasonalMenu]):
    """
    Repository for seasonal menu configurations.
    
    Manages season-specific menu preferences and
    recommendations.
    """

    def __init__(self, db_session):
        """Initialize repository with SeasonalMenu model."""
        super().__init__(SeasonalMenu, db_session)

    async def get_by_hostel_and_season(
        self,
        hostel_id: UUID,
        season: str
    ) -> Optional[SeasonalMenu]:
        """
        Get seasonal menu configuration.
        
        Args:
            hostel_id: Hostel identifier
            season: Season name
            
        Returns:
            SeasonalMenu if found
        """
        query = (
            select(SeasonalMenu)
            .where(SeasonalMenu.hostel_id == hostel_id)
            .where(SeasonalMenu.season == season)
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_current_season_menu(
        self,
        hostel_id: UUID
    ) -> Optional[SeasonalMenu]:
        """
        Get menu for current season.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            Current season's menu configuration
        """
        current_month = datetime.now().month
        
        query = (
            select(SeasonalMenu)
            .where(SeasonalMenu.hostel_id == hostel_id)
            .where(SeasonalMenu.is_active == True)
            .where(SeasonalMenu.season_start_month <= current_month)
            .where(SeasonalMenu.season_end_month >= current_month)
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_all_seasons(
        self,
        hostel_id: UUID
    ) -> List[SeasonalMenu]:
        """
        Get all seasonal configurations.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            List of all seasonal menus
        """
        query = (
            select(SeasonalMenu)
            .where(SeasonalMenu.hostel_id == hostel_id)
            .order_by(SeasonalMenu.season_start_month)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())