# --- File: C:\Hostel-Main\app\repositories\mess\mess_aggregate_repository.py ---

"""
Mess Aggregate Repository Module.

Provides high-level aggregate operations combining multiple
repositories for complex business operations and analytics.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models.mess.dietary_option import StudentDietaryPreference
from app.models.mess.meal_item import MealItem
from app.models.mess.menu_feedback import MenuFeedback, RatingsSummary
from app.models.mess.mess_menu import MessMenu
from app.models.student.student import Student
from app.repositories.mess.dietary_option_repository import (
    DietaryOptionRepository,
    StudentDietaryPreferenceRepository,
)
from app.repositories.mess.meal_item_repository import MealItemRepository
from app.repositories.mess.menu_feedback_repository import (
    MenuFeedbackRepository,
    RatingsSummaryRepository,
)
from app.repositories.mess.mess_menu_repository import MessMenuRepository
from app.repositories.mess.nutritional_info_repository import (
    NutritionalInfoRepository,
)


class MessAggregateRepository:
    """
    Aggregate repository for mess module.
    
    Provides high-level operations that combine multiple
    repositories for complex business logic and analytics.
    """

    def __init__(self, db_session: Session):
        """
        Initialize aggregate repository.
        
        Args:
            db_session: Database session
        """
        self.db_session = db_session
        
        # Initialize individual repositories
        self.menu_repo = MessMenuRepository(db_session)
        self.meal_item_repo = MealItemRepository(db_session)
        self.feedback_repo = MenuFeedbackRepository(db_session)
        self.ratings_summary_repo = RatingsSummaryRepository(db_session)
        self.dietary_option_repo = DietaryOptionRepository(db_session)
        self.student_pref_repo = StudentDietaryPreferenceRepository(db_session)
        self.nutritional_repo = NutritionalInfoRepository(db_session)

    async def get_hostel_dashboard_data(
        self,
        hostel_id: UUID,
        date_range: Optional[Tuple[date, date]] = None
    ) -> Dict[str, any]:
        """
        Get comprehensive dashboard data for hostel.
        
        Args:
            hostel_id: Hostel identifier
            date_range: Optional date range tuple (start, end)
            
        Returns:
            Dictionary with dashboard metrics
        """
        if not date_range:
            # Default to last 30 days
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
            date_range = (start_date, end_date)
            
        start_date, end_date = date_range
        
        # Get menu statistics
        menu_stats = await self.menu_repo.get_menu_statistics(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Get upcoming menus
        upcoming_menus = await self.menu_repo.get_upcoming_menus(
            hostel_id=hostel_id,
            days_ahead=7
        )
        
        # Get pending approvals
        pending_approvals = await self.menu_repo.find_pending_approval(hostel_id)
        
        # Get dietary distribution
        dietary_dist = await self.student_pref_repo.get_dietary_distribution(hostel_id)
        
        # Get recent feedback summary
        recent_summaries = await self.ratings_summary_repo.get_hostel_summaries(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date
        )
        
        avg_rating = sum(s.average_rating for s in recent_summaries) / len(recent_summaries) if recent_summaries else Decimal('0.0')
        
        return {
            'menu_statistics': menu_stats,
            'upcoming_menus_count': len(upcoming_menus),
            'pending_approvals_count': len(pending_approvals),
            'dietary_distribution': dietary_dist,
            'average_rating': float(avg_rating),
            'total_feedbacks': sum(s.total_feedbacks for s in recent_summaries),
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }

    async def create_complete_menu(
        self,
        hostel_id: UUID,
        menu_date: date,
        meal_items: Dict[str, List[str]],
        creator_id: UUID,
        is_special: bool = False,
        special_occasion: Optional[str] = None,
        auto_publish: bool = False
    ) -> MessMenu:
        """
        Create complete menu with all items.
        
        Args:
            hostel_id: Hostel identifier
            menu_date: Date for menu
            meal_items: Dictionary of meal type -> item names
            creator_id: User creating menu
            is_special: Whether this is a special menu
            special_occasion: Occasion name if special
            auto_publish: Whether to auto-publish
            
        Returns:
            Created MessMenu
        """
        # Check if menu already exists
        existing = await self.menu_repo.get_by_date(hostel_id, menu_date)
        if existing:
            raise ValueError(f"Menu already exists for {menu_date}")
            
        # Get dietary options for hostel
        dietary_options = await self.dietary_option_repo.get_by_hostel(hostel_id)
        
        menu_data = {
            'hostel_id': hostel_id,
            'menu_date': menu_date,
            'breakfast_items': meal_items.get('breakfast', []),
            'lunch_items': meal_items.get('lunch', []),
            'snacks_items': meal_items.get('snacks', []),
            'dinner_items': meal_items.get('dinner', []),
            'is_special_menu': is_special,
            'special_occasion': special_occasion if is_special else None,
        }
        
        # Set dietary availability based on hostel configuration
        if dietary_options:
            menu_data['vegetarian_available'] = dietary_options.vegetarian_menu
            menu_data['non_vegetarian_available'] = dietary_options.non_vegetarian_menu
            menu_data['vegan_available'] = dietary_options.vegan_menu
            menu_data['jain_available'] = dietary_options.jain_menu
            
        # Create menu
        menu = await self.menu_repo.create_menu(menu_data, creator_id)
        
        # Auto-publish if requested
        if auto_publish:
            await self.menu_repo.publish_menu(menu.id, creator_id)
            
        return menu

    async def get_student_recommended_menu(
        self,
        student_id: UUID,
        menu_date: date
    ) -> Dict[str, any]:
        """
        Get menu with items filtered/highlighted for student preferences.
        
        Args:
            student_id: Student identifier
            menu_date: Date of menu
            
        Returns:
            Dictionary with menu and recommendations
        """
        # Get student's hostel
        student_query = select(Student).where(Student.id == student_id)
        student_result = await self.db_session.execute(student_query)
        student = student_result.scalar_one_or_none()
        
        if not student:
            raise ValueError("Student not found")
            
        # Get menu
        menu = await self.menu_repo.get_by_date(student.hostel_id, menu_date)
        
        if not menu:
            return {
                'menu': None,
                'recommendations': {
                    'suitable_items': [],
                    'unsuitable_items': [],
                    'warnings': []
                }
            }
            
        # Get student preferences
        preferences = await self.student_pref_repo.get_with_relationships(student_id)
        
        if not preferences:
            return {
                'menu': menu,
                'recommendations': {
                    'suitable_items': [],
                    'unsuitable_items': [],
                    'warnings': []
                }
            }
            
        suitable_items = []
        unsuitable_items = []
        warnings = []
        
        # Check all menu items against preferences
        all_items = (
            menu.breakfast_items +
            menu.lunch_items +
            menu.snacks_items +
            menu.dinner_items
        )
        
        # Get allergen profile
        allergen_profile = preferences.allergen_profile
        
        for item_name in all_items:
            # Check against dietary restrictions
            if preferences.is_vegetarian and 'non-veg' in item_name.lower():
                unsuitable_items.append(item_name)
                continue
                
            if preferences.is_vegan and any(term in item_name.lower() for term in ['dairy', 'milk', 'cheese', 'paneer']):
                unsuitable_items.append(item_name)
                continue
                
            # Check against allergens
            if allergen_profile:
                allergen_warning = False
                for allergen in allergen_profile.all_allergens:
                    if allergen.lower() in item_name.lower():
                        warnings.append(f"{item_name} may contain {allergen}")
                        allergen_warning = True
                        break
                        
                if allergen_warning:
                    unsuitable_items.append(item_name)
                    continue
                    
            suitable_items.append(item_name)
            
        return {
            'menu': menu,
            'recommendations': {
                'suitable_items': suitable_items,
                'unsuitable_items': unsuitable_items,
                'warnings': warnings,
                'dietary_preference': preferences.primary_preference
            }
        }

    async def get_menu_performance_analysis(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date
    ) -> Dict[str, any]:
        """
        Comprehensive menu performance analysis.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Start of analysis period
            end_date: End of analysis period
            
        Returns:
            Dictionary with performance metrics
        """
        # Get all menus in period
        menus = await self.menu_repo.find_by_hostel(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
            published_only=True
        )
        
        # Get all ratings summaries
        summaries = await self.ratings_summary_repo.get_hostel_summaries(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Calculate overall metrics
        total_menus = len(menus)
        total_feedbacks = sum(s.total_feedbacks for s in summaries)
        
        if total_feedbacks > 0:
            avg_rating = sum(
                float(s.average_rating) * s.total_feedbacks
                for s in summaries
            ) / total_feedbacks
        else:
            avg_rating = 0.0
            
        # Get top and bottom performers
        if summaries:
            best_menu = max(summaries, key=lambda s: s.average_rating)
            worst_menu = min(summaries, key=lambda s: s.average_rating)
        else:
            best_menu = None
            worst_menu = None
            
        # Calculate satisfaction trends
        satisfaction_trend = []
        for summary in sorted(summaries, key=lambda s: s.menu_date):
            satisfaction_trend.append({
                'date': summary.menu_date.isoformat(),
                'rating': float(summary.average_rating),
                'satisfaction_pct': float(summary.satisfaction_percentage)
            })
            
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'totals': {
                'menus_published': total_menus,
                'total_feedbacks': total_feedbacks,
                'average_rating': round(avg_rating, 2)
            },
            'best_menu': {
                'date': best_menu.menu_date.isoformat() if best_menu else None,
                'rating': float(best_menu.average_rating) if best_menu else 0.0
            } if best_menu else None,
            'worst_menu': {
                'date': worst_menu.menu_date.isoformat() if worst_menu else None,
                'rating': float(worst_menu.average_rating) if worst_menu else 0.0
            } if worst_menu else None,
            'satisfaction_trend': satisfaction_trend
        }

    async def plan_weekly_menu(
        self,
        hostel_id: UUID,
        week_start: date,
        template_id: Optional[UUID] = None,
        planner_id: UUID = None
    ) -> List[MessMenu]:
        """
        Plan complete week of menus.
        
        Args:
            hostel_id: Hostel identifier
            week_start: Start date of week (Monday)
            template_id: Optional template to use
            planner_id: User planning menus
            
        Returns:
            List of created menus for the week
        """
        created_menus = []
        
        # Create menu for each day of week
        for i in range(7):
            menu_date = week_start + timedelta(days=i)
            
            # Check if menu already exists
            existing = await self.menu_repo.get_by_date(hostel_id, menu_date)
            if existing:
                created_menus.append(existing)
                continue
                
            # For now, create empty menu structure
            # In production, would use template or AI suggestions
            menu_data = {
                'hostel_id': hostel_id,
                'menu_date': menu_date,
                'breakfast_items': [],
                'lunch_items': [],
                'snacks_items': [],
                'dinner_items': []
            }
            
            menu = await self.menu_repo.create_menu(menu_data, planner_id)
            created_menus.append(menu)
            
        return created_menus

    async def get_dietary_compliance_report(
        self,
        hostel_id: UUID
    ) -> Dict[str, any]:
        """
        Get dietary compliance and coverage report.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            Dictionary with compliance metrics
        """
        # Get hostel dietary options
        dietary_options = await self.dietary_option_repo.get_by_hostel(hostel_id)
        
        # Get student dietary distribution
        dietary_dist = await self.student_pref_repo.get_dietary_distribution(hostel_id)
        
        # Get students with allergens
        students_with_allergens = await self.student_pref_repo.find_students_with_allergens(hostel_id)
        
        # Calculate coverage
        total_students_query = (
            select(func.count(Student.id))
            .where(Student.hostel_id == hostel_id)
        )
        total_result = await self.db_session.execute(total_students_query)
        total_students = total_result.scalar() or 0
        
        return {
            'hostel_dietary_options': {
                'vegetarian': dietary_options.vegetarian_menu if dietary_options else False,
                'non_vegetarian': dietary_options.non_vegetarian_menu if dietary_options else False,
                'vegan': dietary_options.vegan_menu if dietary_options else False,
                'jain': dietary_options.jain_menu if dietary_options else False,
                'gluten_free': dietary_options.gluten_free_options if dietary_options else False,
                'lactose_free': dietary_options.lactose_free_options if dietary_options else False
            },
            'student_distribution': dietary_dist,
            'total_students': total_students,
            'students_with_allergens': len(students_with_allergens),
            'allergen_coverage': {
                'tracked': len(students_with_allergens),
                'percentage': round(len(students_with_allergens) / total_students * 100, 2) if total_students > 0 else 0
            }
        }

    async def get_nutritional_summary(
        self,
        hostel_id: UUID,
        menu_date: date
    ) -> Dict[str, any]:
        """
        Get nutritional summary for a menu.
        
        Args:
            hostel_id: Hostel identifier
            menu_date: Date of menu
            
        Returns:
            Dictionary with nutritional data
        """
        menu = await self.menu_repo.get_by_date(hostel_id, menu_date)
        
        if not menu:
            return {
                'menu_date': menu_date.isoformat(),
                'available': False,
                'nutrition': None
            }
            
        # Get all menu items
        all_items = (
            menu.breakfast_items +
            menu.lunch_items +
            menu.snacks_items +
            menu.dinner_items
        )
        
        # For simplicity, assuming item names map to MealItem records
        # In production, would need proper item ID mapping
        
        return {
            'menu_date': menu_date.isoformat(),
            'available': True,
            'total_items': len(all_items),
            'meals': {
                'breakfast': len(menu.breakfast_items),
                'lunch': len(menu.lunch_items),
                'snacks': len(menu.snacks_items),
                'dinner': len(menu.dinner_items)
            }
        }