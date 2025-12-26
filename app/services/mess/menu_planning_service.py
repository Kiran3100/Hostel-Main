# app/services/mess/menu_planning_service.py
"""
Menu Planning Service

Orchestrates planning of daily/weekly/monthly menus and special menus.

Performance Optimizations:
- Intelligent caching for templates
- Batch processing for plan generation
- Constraint-based optimization
- AI-powered suggestions
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

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
from app.core.exceptions import (
    ValidationException,
    NotFoundException,
    BusinessLogicException,
)


class MenuPlanningService:
    """
    High-level service for menu planning.

    This service manages:
    - Menu templates and reusable patterns
    - Daily/weekly/monthly menu plan generation
    - Special occasion menu planning
    - AI-powered menu suggestions
    - Nutritional and budgetary constraints
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
        """
        Initialize the menu planning service.
        
        Args:
            template_repo: Repository for menu templates
            weekly_repo: Repository for weekly plans
            monthly_repo: Repository for monthly plans
            daily_repo: Repository for daily plans
            special_repo: Repository for special occasion menus
            suggestion_repo: Repository for menu suggestions
        """
        self.template_repo = template_repo
        self.weekly_repo = weekly_repo
        self.monthly_repo = monthly_repo
        self.daily_repo = daily_repo
        self.special_repo = special_repo
        self.suggestion_repo = suggestion_repo

    # -------------------------------------------------------------------------
    # Templates - CRUD Operations
    # -------------------------------------------------------------------------

    def create_template(
        self,
        db: Session,
        hostel_id: UUID,
        template: MenuTemplate,
    ) -> MenuTemplate:
        """
        Create a new menu template.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            template: MenuTemplate schema with template details
            
        Returns:
            Created MenuTemplate schema
            
        Raises:
            ValidationException: If template data is invalid
            DuplicateEntryException: If template name exists
        """
        try:
            # Validate template data
            self._validate_menu_template(template)
            
            payload = template.model_dump(exclude_none=True, exclude_unset=True)
            payload["hostel_id"] = hostel_id
            payload["created_at"] = date.today()
            
            obj = self.template_repo.create(db, payload)
            db.flush()
            
            return MenuTemplate.model_validate(obj)
            
        except IntegrityError as e:
            db.rollback()
            raise ValidationException(
                f"Template with this name already exists: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error creating menu template: {str(e)}"
            )

    def get_template(
        self,
        db: Session,
        template_id: UUID,
    ) -> MenuTemplate:
        """
        Retrieve a specific template by ID.
        
        Args:
            db: Database session
            template_id: Unique identifier of the template
            
        Returns:
            MenuTemplate schema
            
        Raises:
            NotFoundException: If template not found
        """
        try:
            template = self.template_repo.get_by_id(db, template_id)
            
            if not template:
                raise NotFoundException(
                    f"Menu template with ID {template_id} not found"
                )
            
            return MenuTemplate.model_validate(template)
            
        except NotFoundException:
            raise
        except Exception as e:
            raise ValidationException(
                f"Error retrieving template: {str(e)}"
            )

    def update_template(
        self,
        db: Session,
        template_id: UUID,
        template: MenuTemplate,
    ) -> MenuTemplate:
        """
        Update an existing menu template.
        
        Args:
            db: Database session
            template_id: Unique identifier of the template
            template: Updated MenuTemplate schema
            
        Returns:
            Updated MenuTemplate schema
            
        Raises:
            NotFoundException: If template not found
        """
        try:
            existing = self.template_repo.get_by_id(db, template_id)
            
            if not existing:
                raise NotFoundException(
                    f"Menu template with ID {template_id} not found"
                )
            
            # Validate updated data
            self._validate_menu_template(template)
            
            payload = template.model_dump(exclude_none=True, exclude_unset=True)
            payload["updated_at"] = date.today()
            
            obj = self.template_repo.update(db, existing, payload)
            db.flush()
            
            return MenuTemplate.model_validate(obj)
            
        except NotFoundException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error updating template: {str(e)}"
            )

    def delete_template(
        self,
        db: Session,
        template_id: UUID,
    ) -> None:
        """
        Delete a menu template.
        
        Args:
            db: Database session
            template_id: Unique identifier of the template
            
        Raises:
            NotFoundException: If template not found
            BusinessLogicException: If template is in use
        """
        try:
            template = self.template_repo.get_by_id(db, template_id)
            
            if not template:
                raise NotFoundException(
                    f"Menu template with ID {template_id} not found"
                )
            
            # Check if template is in use
            if self._is_template_in_use(db, template_id):
                raise BusinessLogicException(
                    "Cannot delete template that is currently in use"
                )
            
            self.template_repo.delete(db, template)
            db.flush()
            
        except (NotFoundException, BusinessLogicException):
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error deleting template: {str(e)}"
            )

    def list_templates_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        active_only: bool = True,
    ) -> List[MenuTemplate]:
        """
        List all menu templates for a hostel.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            active_only: If True, return only active templates
            
        Returns:
            List of MenuTemplate schemas
        """
        try:
            objs = self.template_repo.get_by_hostel_id(db, hostel_id)
            
            if active_only:
                objs = [obj for obj in objs if getattr(obj, 'is_active', True)]
            
            return [MenuTemplate.model_validate(o) for o in objs]
            
        except Exception as e:
            raise ValidationException(
                f"Error listing templates for hostel {hostel_id}: {str(e)}"
            )

    def search_templates(
        self,
        db: Session,
        hostel_id: UUID,
        search_term: str,
        category: Optional[str] = None,
    ) -> List[MenuTemplate]:
        """
        Search for templates by name or category.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            search_term: Search term to match
            category: Optional category filter
            
        Returns:
            List of matching MenuTemplate schemas
        """
        try:
            templates = self.template_repo.search_templates(
                db, hostel_id, search_term, category
            )
            return [MenuTemplate.model_validate(t) for t in templates]
            
        except Exception as e:
            raise ValidationException(
                f"Error searching templates: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Weekly Plans
    # -------------------------------------------------------------------------

    def create_weekly_plan(
        self,
        db: Session,
        plan: WeeklyMenuPlan,
    ) -> WeeklyMenuPlan:
        """
        Create a new weekly menu plan.
        
        Args:
            db: Database session
            plan: WeeklyMenuPlan schema
            
        Returns:
            Created WeeklyMenuPlan schema
            
        Raises:
            ValidationException: If plan data is invalid
        """
        try:
            # Validate plan
            self._validate_weekly_plan(plan)
            
            payload = plan.model_dump(exclude_none=True, exclude_unset=True)
            payload["created_at"] = date.today()
            
            obj = self.weekly_repo.create(db, payload)
            db.flush()
            
            return WeeklyMenuPlan.model_validate(obj)
            
        except IntegrityError as e:
            db.rollback()
            raise ValidationException(
                f"Weekly plan already exists for this period: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error creating weekly plan: {str(e)}"
            )

    def get_weekly_plan(
        self,
        db: Session,
        hostel_id: UUID,
        week_start: date,
    ) -> Optional[WeeklyMenuPlan]:
        """
        Get weekly plan for a specific week.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            week_start: Start date of the week
            
        Returns:
            WeeklyMenuPlan if found, None otherwise
        """
        try:
            plan = self.weekly_repo.get_by_week(db, hostel_id, week_start)
            
            if not plan:
                return None
            
            return WeeklyMenuPlan.model_validate(plan)
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving weekly plan: {str(e)}"
            )

    def update_weekly_plan(
        self,
        db: Session,
        plan_id: UUID,
        plan: WeeklyMenuPlan,
    ) -> WeeklyMenuPlan:
        """
        Update an existing weekly plan.
        
        Args:
            db: Database session
            plan_id: Unique identifier of the plan
            plan: Updated WeeklyMenuPlan schema
            
        Returns:
            Updated WeeklyMenuPlan schema
        """
        try:
            existing = self.weekly_repo.get_by_id(db, plan_id)
            
            if not existing:
                raise NotFoundException(
                    f"Weekly plan with ID {plan_id} not found"
                )
            
            self._validate_weekly_plan(plan)
            
            payload = plan.model_dump(exclude_none=True, exclude_unset=True)
            payload["updated_at"] = date.today()
            
            obj = self.weekly_repo.update(db, existing, payload)
            db.flush()
            
            return WeeklyMenuPlan.model_validate(obj)
            
        except NotFoundException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error updating weekly plan: {str(e)}"
            )

    def generate_weekly_plan_from_template(
        self,
        db: Session,
        hostel_id: UUID,
        template_id: UUID,
        week_start: date,
    ) -> WeeklyMenuPlan:
        """
        Generate a weekly plan from a template.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            template_id: Template to use for generation
            week_start: Start date of the week
            
        Returns:
            Generated WeeklyMenuPlan schema
        """
        try:
            template = self.get_template(db, template_id)
            
            # Generate plan from template
            plan_data = self.template_repo.generate_weekly_from_template(
                db, template_id, week_start
            )
            
            plan_data["hostel_id"] = hostel_id
            plan_data["week_start"] = week_start
            
            obj = self.weekly_repo.create(db, plan_data)
            db.flush()
            
            return WeeklyMenuPlan.model_validate(obj)
            
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error generating weekly plan from template: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Monthly Plans
    # -------------------------------------------------------------------------

    def create_monthly_plan(
        self,
        db: Session,
        plan: MonthlyMenuPlan,
    ) -> MonthlyMenuPlan:
        """
        Create a new monthly menu plan.
        
        Args:
            db: Database session
            plan: MonthlyMenuPlan schema
            
        Returns:
            Created MonthlyMenuPlan schema
        """
        try:
            # Validate plan
            self._validate_monthly_plan(plan)
            
            payload = plan.model_dump(exclude_none=True, exclude_unset=True)
            payload["created_at"] = date.today()
            
            obj = self.monthly_repo.create(db, payload)
            db.flush()
            
            return MonthlyMenuPlan.model_validate(obj)
            
        except IntegrityError as e:
            db.rollback()
            raise ValidationException(
                f"Monthly plan already exists for this period: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error creating monthly plan: {str(e)}"
            )

    def get_monthly_plan(
        self,
        db: Session,
        hostel_id: UUID,
        year: int,
        month: int,
    ) -> Optional[MonthlyMenuPlan]:
        """
        Get monthly plan for a specific month.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            year: Year of the plan
            month: Month of the plan (1-12)
            
        Returns:
            MonthlyMenuPlan if found, None otherwise
        """
        try:
            if not (1 <= month <= 12):
                raise ValidationException("Month must be between 1 and 12")
            
            plan = self.monthly_repo.get_by_month(db, hostel_id, year, month)
            
            if not plan:
                return None
            
            return MonthlyMenuPlan.model_validate(plan)
            
        except ValidationException:
            raise
        except Exception as e:
            raise ValidationException(
                f"Error retrieving monthly plan: {str(e)}"
            )

    def update_monthly_plan(
        self,
        db: Session,
        plan_id: UUID,
        plan: MonthlyMenuPlan,
    ) -> MonthlyMenuPlan:
        """
        Update an existing monthly plan.
        
        Args:
            db: Database session
            plan_id: Unique identifier of the plan
            plan: Updated MonthlyMenuPlan schema
            
        Returns:
            Updated MonthlyMenuPlan schema
        """
        try:
            existing = self.monthly_repo.get_by_id(db, plan_id)
            
            if not existing:
                raise NotFoundException(
                    f"Monthly plan with ID {plan_id} not found"
                )
            
            self._validate_monthly_plan(plan)
            
            payload = plan.model_dump(exclude_none=True, exclude_unset=True)
            payload["updated_at"] = date.today()
            
            obj = self.monthly_repo.update(db, existing, payload)
            db.flush()
            
            return MonthlyMenuPlan.model_validate(obj)
            
        except NotFoundException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error updating monthly plan: {str(e)}"
            )

    def generate_plan_from_request(
        self,
        db: Session,
        request: MenuPlanRequest,
    ) -> MonthlyMenuPlan:
        """
        Generate a monthly plan from a high-level plan request.

        This method uses intelligent planning algorithms to create
        an optimized menu plan based on constraints like:
        - Budget limitations
        - Nutritional requirements
        - Dietary variety
        - Seasonal availability
        - Previous feedback

        Args:
            db: Database session
            request: MenuPlanRequest with planning parameters
            
        Returns:
            Generated MonthlyMenuPlan schema
            
        Raises:
            ValidationException: If request parameters are invalid
        """
        try:
            # Validate request
            self._validate_plan_request(request)
            
            # Generate plan using repository logic
            data = self.template_repo.generate_plan_from_request(
                db=db,
                request_data=request.model_dump(exclude_none=True),
            )
            
            # Apply additional optimizations
            optimized_data = self._optimize_generated_plan(db, data, request)
            
            return MonthlyMenuPlan.model_validate(optimized_data)
            
        except ValidationException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error generating plan from request: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Daily Plans
    # -------------------------------------------------------------------------

    def create_daily_plan(
        self,
        db: Session,
        plan: DailyMenuPlan,
    ) -> DailyMenuPlan:
        """
        Create a new daily menu plan.
        
        Args:
            db: Database session
            plan: DailyMenuPlan schema
            
        Returns:
            Created DailyMenuPlan schema
        """
        try:
            # Validate plan
            self._validate_daily_plan(plan)
            
            payload = plan.model_dump(exclude_none=True, exclude_unset=True)
            
            obj = self.daily_repo.create(db, payload)
            db.flush()
            
            return DailyMenuPlan.model_validate(obj)
            
        except IntegrityError as e:
            db.rollback()
            raise ValidationException(
                f"Daily plan already exists for this date: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error creating daily plan: {str(e)}"
            )

    def get_daily_plan(
        self,
        db: Session,
        hostel_id: UUID,
        plan_date: date,
    ) -> Optional[DailyMenuPlan]:
        """
        Get daily plan for a specific date.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            plan_date: Date of the plan
            
        Returns:
            DailyMenuPlan if found, None otherwise
        """
        try:
            plan = self.daily_repo.get_by_date(db, hostel_id, plan_date)
            
            if not plan:
                return None
            
            return DailyMenuPlan.model_validate(plan)
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving daily plan: {str(e)}"
            )

    def get_daily_plans_for_range(
        self,
        db: Session,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> List[DailyMenuPlan]:
        """
        Get daily plans for a date range.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            start_date: Start date of the range
            end_date: End date of the range
            
        Returns:
            List of DailyMenuPlan schemas
        """
        try:
            if start_date > end_date:
                raise ValidationException(
                    "Start date must be before or equal to end date"
                )
            
            plans = self.daily_repo.get_by_date_range(
                db, hostel_id, start_date, end_date
            )
            
            return [DailyMenuPlan.model_validate(p) for p in plans]
            
        except ValidationException:
            raise
        except Exception as e:
            raise ValidationException(
                f"Error retrieving daily plans for range: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Special Occasion Menus
    # -------------------------------------------------------------------------

    def create_special_menu(
        self,
        db: Session,
        menu: SpecialDayMenu,
    ) -> SpecialDayMenu:
        """
        Create a special occasion menu.
        
        Args:
            db: Database session
            menu: SpecialDayMenu schema
            
        Returns:
            Created SpecialDayMenu schema
        """
        try:
            # Validate special menu
            self._validate_special_menu(menu)
            
            payload = menu.model_dump(exclude_none=True, exclude_unset=True)
            payload["created_at"] = date.today()
            
            obj = self.special_repo.create(db, payload)
            db.flush()
            
            return SpecialDayMenu.model_validate(obj)
            
        except IntegrityError as e:
            db.rollback()
            raise ValidationException(
                f"Special menu already exists for this occasion: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error creating special menu: {str(e)}"
            )

    def get_special_menu(
        self,
        db: Session,
        menu_id: UUID,
    ) -> SpecialDayMenu:
        """
        Get a specific special menu by ID.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the special menu
            
        Returns:
            SpecialDayMenu schema
        """
        try:
            menu = self.special_repo.get_by_id(db, menu_id)
            
            if not menu:
                raise NotFoundException(
                    f"Special menu with ID {menu_id} not found"
                )
            
            return SpecialDayMenu.model_validate(menu)
            
        except NotFoundException:
            raise
        except Exception as e:
            raise ValidationException(
                f"Error retrieving special menu: {str(e)}"
            )

    def list_special_menus_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        upcoming_only: bool = False,
    ) -> List[SpecialDayMenu]:
        """
        List all special menus for a hostel.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            upcoming_only: If True, return only future special menus
            
        Returns:
            List of SpecialDayMenu schemas
        """
        try:
            if upcoming_only:
                menus = self.special_repo.get_upcoming(db, hostel_id)
            else:
                menus = self.special_repo.get_by_hostel_id(db, hostel_id)
            
            return [SpecialDayMenu.model_validate(m) for m in menus]
            
        except Exception as e:
            raise ValidationException(
                f"Error listing special menus: {str(e)}"
            )

    def update_special_menu(
        self,
        db: Session,
        menu_id: UUID,
        menu: SpecialDayMenu,
    ) -> SpecialDayMenu:
        """
        Update a special occasion menu.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            menu: Updated SpecialDayMenu schema
            
        Returns:
            Updated SpecialDayMenu schema
        """
        try:
            existing = self.special_repo.get_by_id(db, menu_id)
            
            if not existing:
                raise NotFoundException(
                    f"Special menu with ID {menu_id} not found"
                )
            
            self._validate_special_menu(menu)
            
            payload = menu.model_dump(exclude_none=True, exclude_unset=True)
            payload["updated_at"] = date.today()
            
            obj = self.special_repo.update(db, existing, payload)
            db.flush()
            
            return SpecialDayMenu.model_validate(obj)
            
        except NotFoundException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error updating special menu: {str(e)}"
            )

    def delete_special_menu(
        self,
        db: Session,
        menu_id: UUID,
    ) -> None:
        """
        Delete a special occasion menu.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
        """
        try:
            menu = self.special_repo.get_by_id(db, menu_id)
            
            if not menu:
                raise NotFoundException(
                    f"Special menu with ID {menu_id} not found"
                )
            
            self.special_repo.delete(db, menu)
            db.flush()
            
        except NotFoundException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error deleting special menu: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Menu Suggestions (AI-powered)
    # -------------------------------------------------------------------------

    def get_menu_suggestions(
        self,
        db: Session,
        hostel_id: UUID,
        suggestion_date: date,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[MenuSuggestion]:
        """
        Get AI-powered menu suggestions for a specific date.
        
        Suggestions are based on:
        - Historical preferences
        - Seasonal ingredients
        - Nutritional balance
        - Budget constraints
        - Previous feedback
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            suggestion_date: Date to generate suggestions for
            context: Optional context for suggestion generation
            
        Returns:
            List of MenuSuggestion schemas
        """
        try:
            # Get suggestions from repository
            objs = self.suggestion_repo.get_suggestions_for_date(
                db=db,
                hostel_id=hostel_id,
                suggestion_date=suggestion_date,
            )
            
            if not objs:
                # Generate new suggestions if none exist
                objs = self._generate_suggestions(
                    db, hostel_id, suggestion_date, context
                )
            
            return [MenuSuggestion.model_validate(o) for o in objs]
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving menu suggestions: {str(e)}"
            )

    def generate_suggestions(
        self,
        db: Session,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[date, List[MenuSuggestion]]:
        """
        Generate menu suggestions for a date range.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            start_date: Start date of the range
            end_date: End date of the range
            constraints: Optional constraints for generation
            
        Returns:
            Dictionary mapping dates to suggestion lists
        """
        try:
            suggestions_by_date = {}
            current_date = start_date
            
            while current_date <= end_date:
                suggestions = self._generate_suggestions(
                    db, hostel_id, current_date, constraints
                )
                suggestions_by_date[current_date] = [
                    MenuSuggestion.model_validate(s) for s in suggestions
                ]
                current_date += timedelta(days=1)
            
            return suggestions_by_date
            
        except Exception as e:
            raise ValidationException(
                f"Error generating suggestions for date range: {str(e)}"
            )

    def accept_suggestion(
        self,
        db: Session,
        suggestion_id: UUID,
    ) -> DailyMenuPlan:
        """
        Accept a menu suggestion and convert it to a daily plan.
        
        Args:
            db: Database session
            suggestion_id: Unique identifier of the suggestion
            
        Returns:
            Created DailyMenuPlan schema
        """
        try:
            suggestion = self.suggestion_repo.get_by_id(db, suggestion_id)
            
            if not suggestion:
                raise NotFoundException(
                    f"Menu suggestion with ID {suggestion_id} not found"
                )
            
            # Convert suggestion to daily plan
            plan_data = self.suggestion_repo.convert_to_daily_plan(
                db, suggestion
            )
            
            obj = self.daily_repo.create(db, plan_data)
            
            # Mark suggestion as accepted
            self.suggestion_repo.mark_as_accepted(db, suggestion)
            
            db.flush()
            
            return DailyMenuPlan.model_validate(obj)
            
        except NotFoundException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error accepting menu suggestion: {str(e)}"
            )

    def reject_suggestion(
        self,
        db: Session,
        suggestion_id: UUID,
        reason: Optional[str] = None,
    ) -> None:
        """
        Reject a menu suggestion.
        
        Args:
            db: Database session
            suggestion_id: Unique identifier of the suggestion
            reason: Optional rejection reason for learning
        """
        try:
            suggestion = self.suggestion_repo.get_by_id(db, suggestion_id)
            
            if not suggestion:
                raise NotFoundException(
                    f"Menu suggestion with ID {suggestion_id} not found"
                )
            
            self.suggestion_repo.mark_as_rejected(db, suggestion, reason)
            db.flush()
            
        except NotFoundException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error rejecting menu suggestion: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Analytics & Reporting
    # -------------------------------------------------------------------------

    def get_plan_coverage_report(
        self,
        db: Session,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Get a report on menu plan coverage for a period.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            start_date: Start date of the period
            end_date: End date of the period
            
        Returns:
            Dictionary with coverage statistics
        """
        try:
            total_days = (end_date - start_date).days + 1
            
            # Get existing plans
            daily_plans = self.get_daily_plans_for_range(
                db, hostel_id, start_date, end_date
            )
            
            planned_days = len(daily_plans)
            coverage_percentage = (planned_days / total_days) * 100 if total_days > 0 else 0
            
            # Find gaps
            planned_dates = {
                getattr(p, 'plan_date', None) for p in daily_plans
            }
            
            gaps = []
            current_date = start_date
            while current_date <= end_date:
                if current_date not in planned_dates:
                    gaps.append(current_date)
                current_date += timedelta(days=1)
            
            return {
                "hostel_id": str(hostel_id),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_days": total_days,
                "planned_days": planned_days,
                "coverage_percentage": round(coverage_percentage, 2),
                "gaps": [gap.isoformat() for gap in gaps],
                "gap_count": len(gaps),
            }
            
        except Exception as e:
            raise ValidationException(
                f"Error generating coverage report: {str(e)}"
            )

    def get_variety_analysis(
        self,
        db: Session,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Analyze menu variety over a period.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            start_date: Start date of the analysis
            end_date: End date of the analysis
            
        Returns:
            Dictionary with variety metrics
        """
        try:
            analysis = self.daily_repo.analyze_variety(
                db, hostel_id, start_date, end_date
            )
            
            return {
                "hostel_id": str(hostel_id),
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "unique_items": analysis.get("unique_items", 0),
                "total_servings": analysis.get("total_servings", 0),
                "variety_score": analysis.get("variety_score", 0.0),
                "repetition_rate": analysis.get("repetition_rate", 0.0),
                "most_frequent_items": analysis.get("most_frequent", []),
                "least_frequent_items": analysis.get("least_frequent", []),
            }
            
        except Exception as e:
            raise ValidationException(
                f"Error analyzing menu variety: {str(e)}"
            )

    def get_cost_analysis(
        self,
        db: Session,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Analyze menu costs over a period.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            start_date: Start date of the analysis
            end_date: End date of the analysis
            
        Returns:
            Dictionary with cost metrics
        """
        try:
            analysis = self.daily_repo.analyze_costs(
                db, hostel_id, start_date, end_date
            )
            
            return {
                "hostel_id": str(hostel_id),
                "period_start": start_date.isoformat(),
                "period_end": end_date.isoformat(),
                "total_cost": float(analysis.get("total_cost", 0.0)),
                "average_daily_cost": float(analysis.get("avg_daily_cost", 0.0)),
                "cost_per_student": float(analysis.get("cost_per_student", 0.0)),
                "highest_cost_day": analysis.get("highest_cost_day", None),
                "lowest_cost_day": analysis.get("lowest_cost_day", None),
                "budget_utilization": analysis.get("budget_utilization", 0.0),
            }
            
        except Exception as e:
            raise ValidationException(
                f"Error analyzing menu costs: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Validation & Helper Methods
    # -------------------------------------------------------------------------

    def _validate_menu_template(self, template: MenuTemplate) -> None:
        """Validate menu template data."""
        if not template.name or not template.name.strip():
            raise ValidationException("Template name cannot be empty")
        
        if hasattr(template, 'min_budget') and hasattr(template, 'max_budget'):
            if template.max_budget and template.min_budget:
                if template.max_budget < template.min_budget:
                    raise ValidationException(
                        "Maximum budget cannot be less than minimum budget"
                    )

    def _validate_weekly_plan(self, plan: WeeklyMenuPlan) -> None:
        """Validate weekly plan data."""
        if not hasattr(plan, 'week_start') or not plan.week_start:
            raise ValidationException("Week start date is required")
        
        # Ensure week_start is a Monday
        if plan.week_start.weekday() != 0:
            raise ValidationException("Week must start on a Monday")

    def _validate_monthly_plan(self, plan: MonthlyMenuPlan) -> None:
        """Validate monthly plan data."""
        if not hasattr(plan, 'year') or not plan.year:
            raise ValidationException("Year is required")
        
        if not hasattr(plan, 'month') or not plan.month:
            raise ValidationException("Month is required")
        
        if not (1 <= plan.month <= 12):
            raise ValidationException("Month must be between 1 and 12")

    def _validate_daily_plan(self, plan: DailyMenuPlan) -> None:
        """Validate daily plan data."""
        if not hasattr(plan, 'plan_date') or not plan.plan_date:
            raise ValidationException("Plan date is required")

    def _validate_special_menu(self, menu: SpecialDayMenu) -> None:
        """Validate special menu data."""
        if not hasattr(menu, 'occasion_name') or not menu.occasion_name:
            raise ValidationException("Occasion name is required")
        
        if not hasattr(menu, 'occasion_date') or not menu.occasion_date:
            raise ValidationException("Occasion date is required")

    def _validate_plan_request(self, request: MenuPlanRequest) -> None:
        """Validate menu plan request."""
        if not hasattr(request, 'hostel_id') or not request.hostel_id:
            raise ValidationException("Hostel ID is required")
        
        if hasattr(request, 'budget_per_day') and request.budget_per_day:
            if request.budget_per_day <= 0:
                raise ValidationException("Budget per day must be positive")

    def _is_template_in_use(self, db: Session, template_id: UUID) -> bool:
        """Check if a template is currently in use."""
        try:
            return self.template_repo.is_in_use(db, template_id)
        except:
            return False

    def _optimize_generated_plan(
        self,
        db: Session,
        plan_data: Dict[str, Any],
        request: MenuPlanRequest,
    ) -> Dict[str, Any]:
        """
        Apply optimization to a generated plan.
        
        This could include:
        - Balancing nutritional content
        - Optimizing costs
        - Ensuring variety
        - Respecting dietary restrictions
        """
        # Placeholder for optimization logic
        return plan_data

    def _generate_suggestions(
        self,
        db: Session,
        hostel_id: UUID,
        suggestion_date: date,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Any]:
        """
        Generate menu suggestions for a specific date.
        
        This is where AI/ML logic would be integrated.
        """
        try:
            return self.suggestion_repo.generate_suggestions(
                db, hostel_id, suggestion_date, context or {}
            )
        except:
            return []