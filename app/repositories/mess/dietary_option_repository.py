"""
Dietary Option Repository Module.

Manages dietary preferences, allergen profiles, restrictions, and meal
customizations with advanced querying and analytics capabilities.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from app.models.mess.dietary_option import (
    AllergenProfile,
    DietaryOption,
    DietaryRestriction,
    MealCustomization,
    StudentDietaryPreference,
)
from app.models.student.student import Student
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.specifications import Specification


class DietaryOptionRepository(BaseRepository[DietaryOption]):
    """
    Repository for managing hostel-level dietary options.
    
    Provides operations for configuring dietary menus, customization
    settings, and allergen management at the hostel level.
    """

    def __init__(self, db_session):
        """Initialize repository with DietaryOption model."""
        super().__init__(DietaryOption, db_session)

    async def get_by_hostel(
        self,
        hostel_id: UUID,
        include_inactive: bool = False
    ) -> Optional[DietaryOption]:
        """
        Get dietary options for a specific hostel.
        
        Args:
            hostel_id: Hostel identifier
            include_inactive: Include soft-deleted records
            
        Returns:
            DietaryOption if found, None otherwise
        """
        query = select(DietaryOption).where(
            DietaryOption.hostel_id == hostel_id
        )
        
        if not include_inactive:
            query = query.where(DietaryOption.deleted_at.is_(None))
            
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_with_hostel_details(
        self,
        hostel_id: UUID
    ) -> Optional[DietaryOption]:
        """
        Get dietary options with hostel relationship loaded.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            DietaryOption with hostel relationship
        """
        query = (
            select(DietaryOption)
            .where(DietaryOption.hostel_id == hostel_id)
            .options(joinedload(DietaryOption.hostel))
        )
        
        result = await self.db_session.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_hostels_with_dietary_support(
        self,
        dietary_type: str
    ) -> List[UUID]:
        """
        Get hostels offering specific dietary options.
        
        Args:
            dietary_type: Type of dietary option
                         (vegetarian, vegan, jain, gluten_free, etc.)
            
        Returns:
            List of hostel IDs offering the dietary option
        """
        dietary_field_map = {
            'vegetarian': DietaryOption.vegetarian_menu,
            'non_vegetarian': DietaryOption.non_vegetarian_menu,
            'vegan': DietaryOption.vegan_menu,
            'jain': DietaryOption.jain_menu,
            'gluten_free': DietaryOption.gluten_free_options,
            'lactose_free': DietaryOption.lactose_free_options,
            'halal': DietaryOption.halal_options,
            'kosher': DietaryOption.kosher_options,
        }
        
        field = dietary_field_map.get(dietary_type.lower())
        if not field:
            return []
            
        query = (
            select(DietaryOption.hostel_id)
            .where(field == True)
            .where(DietaryOption.deleted_at.is_(None))
        )
        
        result = await self.db_session.execute(query)
        return [row[0] for row in result.all()]

    async def get_customization_settings(
        self,
        hostel_id: UUID
    ) -> Dict[str, any]:
        """
        Get meal customization settings for hostel.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            Dictionary of customization settings
        """
        dietary_option = await self.get_by_hostel(hostel_id)
        
        if not dietary_option:
            return {}
            
        return {
            'allow_meal_customization': dietary_option.allow_meal_customization,
            'allow_special_requests': dietary_option.allow_special_requests,
            'advance_notice_days': dietary_option.advance_notice_required_days,
            'max_requests_per_month': dietary_option.max_special_requests_per_month,
            'allow_portion_selection': dietary_option.allow_portion_selection,
            'portion_sizes': dietary_option.portion_sizes_available,
            'flexible_timings': dietary_option.flexible_meal_timings,
            'allow_meal_skipping': dietary_option.allow_meal_skipping,
            'meal_credit_system': dietary_option.meal_credit_system,
        }

    async def update_allergen_settings(
        self,
        hostel_id: UUID,
        settings: Dict[str, bool]
    ) -> Optional[DietaryOption]:
        """
        Update allergen management settings.
        
        Args:
            hostel_id: Hostel identifier
            settings: Allergen settings to update
            
        Returns:
            Updated DietaryOption
        """
        dietary_option = await self.get_by_hostel(hostel_id)
        
        if not dietary_option:
            return None
            
        # Update allergen settings
        if 'display_warnings' in settings:
            dietary_option.display_allergen_warnings = settings['display_warnings']
        if 'mandatory_declaration' in settings:
            dietary_option.mandatory_allergen_declaration = settings['mandatory_declaration']
        if 'cross_contamination_warning' in settings:
            dietary_option.allergen_cross_contamination_warning = settings['cross_contamination_warning']
            
        await self.db_session.commit()
        await self.db_session.refresh(dietary_option)
        
        return dietary_option

    async def get_hostels_with_features(
        self,
        features: List[str]
    ) -> List[UUID]:
        """
        Get hostels with specific dietary features enabled.
        
        Args:
            features: List of feature names to check
            
        Returns:
            List of hostel IDs with all features enabled
        """
        conditions = []
        
        feature_map = {
            'customization': DietaryOption.allow_meal_customization,
            'special_requests': DietaryOption.allow_special_requests,
            'portion_control': DietaryOption.allow_portion_selection,
            'flexible_timing': DietaryOption.flexible_meal_timings,
            'waste_tracking': DietaryOption.track_food_waste,
            'diet_plans': DietaryOption.diet_plan_support,
            'nutritionist': DietaryOption.nutritionist_consultation_available,
        }
        
        for feature in features:
            field = feature_map.get(feature.lower())
            if field:
                conditions.append(field == True)
                
        if not conditions:
            return []
            
        query = (
            select(DietaryOption.hostel_id)
            .where(and_(*conditions))
            .where(DietaryOption.deleted_at.is_(None))
        )
        
        result = await self.db_session.execute(query)
        return [row[0] for row in result.all()]


class StudentDietaryPreferenceRepository(BaseRepository[StudentDietaryPreference]):
    """
    Repository for managing student dietary preferences.
    
    Handles individual student preferences, restrictions, and
    meal customization requirements.
    """

    def __init__(self, db_session):
        """Initialize repository with StudentDietaryPreference model."""
        super().__init__(StudentDietaryPreference, db_session)

    async def get_by_student(
        self,
        student_id: UUID,
        include_deleted: bool = False
    ) -> Optional[StudentDietaryPreference]:
        """
        Get dietary preferences for a student.
        
        Args:
            student_id: Student identifier
            include_deleted: Include soft-deleted records
            
        Returns:
            StudentDietaryPreference if found
        """
        query = select(StudentDietaryPreference).where(
            StudentDietaryPreference.student_id == student_id
        )
        
        if not include_deleted:
            query = query.where(StudentDietaryPreference.deleted_at.is_(None))
            
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_with_relationships(
        self,
        student_id: UUID
    ) -> Optional[StudentDietaryPreference]:
        """
        Get preferences with all relationships loaded.
        
        Args:
            student_id: Student identifier
            
        Returns:
            StudentDietaryPreference with relationships
        """
        query = (
            select(StudentDietaryPreference)
            .where(StudentDietaryPreference.student_id == student_id)
            .options(
                joinedload(StudentDietaryPreference.student),
                joinedload(StudentDietaryPreference.allergen_profile),
                selectinload(StudentDietaryPreference.dietary_restrictions)
            )
        )
        
        result = await self.db_session.execute(query)
        return result.unique().scalar_one_or_none()

    async def find_by_preference_type(
        self,
        hostel_id: UUID,
        preference_type: str,
        verified_only: bool = False
    ) -> List[StudentDietaryPreference]:
        """
        Find students with specific dietary preference.
        
        Args:
            hostel_id: Hostel identifier
            preference_type: Type of dietary preference
            verified_only: Only return verified preferences
            
        Returns:
            List of matching preferences
        """
        query = (
            select(StudentDietaryPreference)
            .join(Student)
            .where(Student.hostel_id == hostel_id)
            .where(StudentDietaryPreference.primary_preference == preference_type)
            .where(StudentDietaryPreference.deleted_at.is_(None))
        )
        
        if verified_only:
            query = query.where(StudentDietaryPreference.is_verified == True)
            
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_dietary_distribution(
        self,
        hostel_id: UUID
    ) -> Dict[str, int]:
        """
        Get distribution of dietary preferences in hostel.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            Dictionary mapping preference types to counts
        """
        query = (
            select(
                StudentDietaryPreference.primary_preference,
                func.count(StudentDietaryPreference.id)
            )
            .join(Student)
            .where(Student.hostel_id == hostel_id)
            .where(StudentDietaryPreference.deleted_at.is_(None))
            .group_by(StudentDietaryPreference.primary_preference)
        )
        
        result = await self.db_session.execute(query)
        return {row[0]: row[1] for row in result.all()}

    async def find_students_with_allergens(
        self,
        hostel_id: UUID,
        allergen_type: Optional[str] = None
    ) -> List[StudentDietaryPreference]:
        """
        Find students with allergen profiles.
        
        Args:
            hostel_id: Hostel identifier
            allergen_type: Specific allergen to filter (optional)
            
        Returns:
            List of preferences with allergen profiles
        """
        query = (
            select(StudentDietaryPreference)
            .join(Student)
            .join(AllergenProfile)
            .where(Student.hostel_id == hostel_id)
            .where(StudentDietaryPreference.deleted_at.is_(None))
            .options(joinedload(StudentDietaryPreference.allergen_profile))
        )
        
        result = await self.db_session.execute(query)
        preferences = list(result.unique().scalars().all())
        
        # Filter by specific allergen if provided
        if allergen_type and preferences:
            filtered = []
            for pref in preferences:
                if pref.allergen_profile:
                    allergen_field = f"{allergen_type}_allergy"
                    if hasattr(pref.allergen_profile, allergen_field):
                        severity = getattr(pref.allergen_profile, allergen_field)
                        if severity and severity != 'none':
                            filtered.append(pref)
            return filtered
            
        return preferences

    async def get_unverified_preferences(
        self,
        hostel_id: UUID,
        days_old: Optional[int] = None
    ) -> List[StudentDietaryPreference]:
        """
        Get unverified dietary preferences.
        
        Args:
            hostel_id: Hostel identifier
            days_old: Only preferences older than N days
            
        Returns:
            List of unverified preferences
        """
        query = (
            select(StudentDietaryPreference)
            .join(Student)
            .where(Student.hostel_id == hostel_id)
            .where(StudentDietaryPreference.is_verified == False)
            .where(StudentDietaryPreference.deleted_at.is_(None))
        )
        
        if days_old:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            query = query.where(StudentDietaryPreference.created_at <= cutoff_date)
            
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_by_meal_timing_preference(
        self,
        hostel_id: UUID,
        meal_type: str,
        time_range: tuple[str, str]
    ) -> List[StudentDietaryPreference]:
        """
        Find students with specific meal timing preferences.
        
        Args:
            hostel_id: Hostel identifier
            meal_type: Type of meal (breakfast, lunch, dinner)
            time_range: Tuple of (start_time, end_time) in HH:MM format
            
        Returns:
            List of matching preferences
        """
        timing_field_map = {
            'breakfast': StudentDietaryPreference.preferred_breakfast_time,
            'lunch': StudentDietaryPreference.preferred_lunch_time,
            'dinner': StudentDietaryPreference.preferred_dinner_time,
        }
        
        field = timing_field_map.get(meal_type.lower())
        if not field:
            return []
            
        start_time, end_time = time_range
        
        query = (
            select(StudentDietaryPreference)
            .join(Student)
            .where(Student.hostel_id == hostel_id)
            .where(field.between(start_time, end_time))
            .where(StudentDietaryPreference.deleted_at.is_(None))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_students_on_diet_plans(
        self,
        hostel_id: UUID,
        plan_type: Optional[str] = None,
        active_only: bool = True
    ) -> List[StudentDietaryPreference]:
        """
        Get students following diet plans.
        
        Args:
            hostel_id: Hostel identifier
            plan_type: Specific plan type to filter
            active_only: Only active diet plans
            
        Returns:
            List of preferences with diet plans
        """
        query = (
            select(StudentDietaryPreference)
            .join(Student)
            .where(Student.hostel_id == hostel_id)
            .where(StudentDietaryPreference.on_diet_plan == True)
            .where(StudentDietaryPreference.deleted_at.is_(None))
        )
        
        if plan_type:
            query = query.where(StudentDietaryPreference.diet_plan_type == plan_type)
            
        if active_only:
            today = date.today()
            query = query.where(
                or_(
                    StudentDietaryPreference.diet_plan_end_date.is_(None),
                    StudentDietaryPreference.diet_plan_end_date >= today
                )
            )
            
        result = await self.db_session.execute(query)
        return list(result.scalars().all())


class AllergenProfileRepository(BaseRepository[AllergenProfile]):
    """
    Repository for managing student allergen profiles.
    
    Handles allergen tracking, severity management, and
    emergency information for student safety.
    """

    def __init__(self, db_session):
        """Initialize repository with AllergenProfile model."""
        super().__init__(AllergenProfile, db_session)

    async def get_by_preference(
        self,
        preference_id: UUID
    ) -> Optional[AllergenProfile]:
        """
        Get allergen profile by dietary preference.
        
        Args:
            preference_id: StudentDietaryPreference ID
            
        Returns:
            AllergenProfile if found
        """
        query = select(AllergenProfile).where(
            AllergenProfile.student_preference_id == preference_id
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def find_severe_allergies(
        self,
        hostel_id: UUID,
        allergen_type: Optional[str] = None
    ) -> List[AllergenProfile]:
        """
        Find students with severe or life-threatening allergies.
        
        Args:
            hostel_id: Hostel identifier
            allergen_type: Specific allergen type (optional)
            
        Returns:
            List of allergen profiles with severe allergies
        """
        query = (
            select(AllergenProfile)
            .join(StudentDietaryPreference)
            .join(Student)
            .where(Student.hostel_id == hostel_id)
            .options(joinedload(AllergenProfile.student_preference))
        )
        
        result = await self.db_session.execute(query)
        profiles = list(result.unique().scalars().all())
        
        # Filter by severity
        severe_profiles = []
        for profile in profiles:
            if allergen_type:
                allergen_field = f"{allergen_type}_allergy"
                if hasattr(profile, allergen_field):
                    severity = getattr(profile, allergen_field)
                    if severity in ['severe', 'life_threatening']:
                        severe_profiles.append(profile)
            else:
                # Check all allergens
                if profile.severe_allergens:
                    severe_profiles.append(profile)
                    
        return severe_profiles

    async def get_students_with_epipen(
        self,
        hostel_id: UUID
    ) -> List[AllergenProfile]:
        """
        Get students who carry EpiPens.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            List of allergen profiles with EpiPen
        """
        query = (
            select(AllergenProfile)
            .join(StudentDietaryPreference)
            .join(Student)
            .where(Student.hostel_id == hostel_id)
            .where(AllergenProfile.has_epipen == True)
            .options(joinedload(AllergenProfile.student_preference))
        )
        
        result = await self.db_session.execute(query)
        return list(result.unique().scalars().all())

    async def find_by_allergen(
        self,
        hostel_id: UUID,
        allergen_name: str,
        min_severity: str = 'mild'
    ) -> List[AllergenProfile]:
        """
        Find students allergic to specific allergen.
        
        Args:
            hostel_id: Hostel identifier
            allergen_name: Name of allergen
            min_severity: Minimum severity level
            
        Returns:
            List of affected allergen profiles
        """
        severity_order = ['trace', 'mild', 'moderate', 'severe', 'life_threatening']
        min_index = severity_order.index(min_severity) if min_severity in severity_order else 0
        
        query = (
            select(AllergenProfile)
            .join(StudentDietaryPreference)
            .join(Student)
            .where(Student.hostel_id == hostel_id)
        )
        
        result = await self.db_session.execute(query)
        profiles = list(result.scalars().all())
        
        # Filter by allergen and severity
        filtered = []
        allergen_field = f"{allergen_name.lower()}_allergy"
        
        for profile in profiles:
            if hasattr(profile, allergen_field):
                severity = getattr(profile, allergen_field)
                if severity and severity in severity_order:
                    if severity_order.index(severity) >= min_index:
                        filtered.append(profile)
                        
        return filtered

    async def get_unverified_profiles(
        self,
        hostel_id: UUID
    ) -> List[AllergenProfile]:
        """
        Get allergen profiles pending verification.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            List of unverified profiles
        """
        query = (
            select(AllergenProfile)
            .join(StudentDietaryPreference)
            .join(Student)
            .where(Student.hostel_id == hostel_id)
            .where(
                or_(
                    AllergenProfile.is_verified == False,
                    AllergenProfile.verified_by_medical_staff == False
                )
            )
            .options(joinedload(AllergenProfile.student_preference))
        )
        
        result = await self.db_session.execute(query)
        return list(result.unique().scalars().all())

    async def get_cross_contamination_sensitive(
        self,
        hostel_id: UUID
    ) -> List[AllergenProfile]:
        """
        Get students sensitive to cross-contamination.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            List of profiles requiring separate preparation
        """
        query = (
            select(AllergenProfile)
            .join(StudentDietaryPreference)
            .join(Student)
            .where(Student.hostel_id == hostel_id)
            .where(
                or_(
                    AllergenProfile.cross_contamination_sensitive == True,
                    AllergenProfile.requires_separate_preparation == True
                )
            )
            .options(joinedload(AllergenProfile.student_preference))
        )
        
        result = await self.db_session.execute(query)
        return list(result.unique().scalars().all())


class DietaryRestrictionRepository(BaseRepository[DietaryRestriction]):
    """
    Repository for managing dietary restrictions.
    
    Handles medical, religious, and personal dietary restrictions
    with compliance tracking and validation.
    """

    def __init__(self, db_session):
        """Initialize repository with DietaryRestriction model."""
        super().__init__(DietaryRestriction, db_session)

    async def find_by_preference(
        self,
        preference_id: UUID,
        active_only: bool = True
    ) -> List[DietaryRestriction]:
        """
        Get restrictions for a dietary preference.
        
        Args:
            preference_id: StudentDietaryPreference ID
            active_only: Only active restrictions
            
        Returns:
            List of dietary restrictions
        """
        query = (
            select(DietaryRestriction)
            .where(DietaryRestriction.student_preference_id == preference_id)
            .where(DietaryRestriction.deleted_at.is_(None))
        )
        
        if active_only:
            query = query.where(DietaryRestriction.is_active == True)
            
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_by_type(
        self,
        hostel_id: UUID,
        restriction_type: str,
        severity: Optional[str] = None
    ) -> List[DietaryRestriction]:
        """
        Find restrictions by type and severity.
        
        Args:
            hostel_id: Hostel identifier
            restriction_type: Type of restriction
            severity: Severity level (optional)
            
        Returns:
            List of matching restrictions
        """
        query = (
            select(DietaryRestriction)
            .join(StudentDietaryPreference)
            .join(Student)
            .where(Student.hostel_id == hostel_id)
            .where(DietaryRestriction.restriction_type == restriction_type)
            .where(DietaryRestriction.deleted_at.is_(None))
        )
        
        if severity:
            query = query.where(DietaryRestriction.severity == severity)
            
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_medical_restrictions(
        self,
        hostel_id: UUID,
        verified_only: bool = True
    ) -> List[DietaryRestriction]:
        """
        Find medical dietary restrictions.
        
        Args:
            hostel_id: Hostel identifier
            verified_only: Only medically verified restrictions
            
        Returns:
            List of medical restrictions
        """
        query = (
            select(DietaryRestriction)
            .join(StudentDietaryPreference)
            .join(Student)
            .where(Student.hostel_id == hostel_id)
            .where(DietaryRestriction.restriction_type == 'medical')
            .where(DietaryRestriction.deleted_at.is_(None))
        )
        
        if verified_only:
            query = query.where(DietaryRestriction.is_medically_verified == True)
            
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_expiring_restrictions(
        self,
        hostel_id: UUID,
        days_ahead: int = 30
    ) -> List[DietaryRestriction]:
        """
        Find restrictions expiring soon.
        
        Args:
            hostel_id: Hostel identifier
            days_ahead: Number of days to look ahead
            
        Returns:
            List of expiring restrictions
        """
        from datetime import timedelta
        
        future_date = date.today() + timedelta(days=days_ahead)
        
        query = (
            select(DietaryRestriction)
            .join(StudentDietaryPreference)
            .join(Student)
            .where(Student.hostel_id == hostel_id)
            .where(DietaryRestriction.is_permanent == False)
            .where(DietaryRestriction.end_date.isnot(None))
            .where(DietaryRestriction.end_date <= future_date)
            .where(DietaryRestriction.deleted_at.is_(None))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_mandatory_restrictions(
        self,
        hostel_id: UUID
    ) -> List[DietaryRestriction]:
        """
        Get mandatory compliance restrictions.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            List of mandatory restrictions
        """
        query = (
            select(DietaryRestriction)
            .join(StudentDietaryPreference)
            .join(Student)
            .where(Student.hostel_id == hostel_id)
            .where(DietaryRestriction.compliance_required == True)
            .where(DietaryRestriction.deleted_at.is_(None))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())


class MealCustomizationRepository(BaseRepository[MealCustomization]):
    """
    Repository for managing meal customization requests.
    
    Handles student meal customization requests with approval
    workflow, fulfillment tracking, and analytics.
    """

    def __init__(self, db_session):
        """Initialize repository with MealCustomization model."""
        super().__init__(MealCustomization, db_session)

    async def find_by_student(
        self,
        student_id: UUID,
        meal_date: Optional[date] = None,
        status: Optional[str] = None
    ) -> List[MealCustomization]:
        """
        Find customizations for a student.
        
        Args:
            student_id: Student identifier
            meal_date: Specific meal date (optional)
            status: Filter by status (optional)
            
        Returns:
            List of meal customizations
        """
        query = (
            select(MealCustomization)
            .where(MealCustomization.student_id == student_id)
        )
        
        if meal_date:
            query = query.where(MealCustomization.meal_date == meal_date)
            
        if status:
            query = query.where(MealCustomization.status == status)
            
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_pending_approvals(
        self,
        hostel_id: Optional[UUID] = None,
        meal_date: Optional[date] = None
    ) -> List[MealCustomization]:
        """
        Find customizations pending approval.
        
        Args:
            hostel_id: Hostel identifier (optional)
            meal_date: Specific meal date (optional)
            
        Returns:
            List of pending customizations
        """
        query = (
            select(MealCustomization)
            .join(Student)
            .where(MealCustomization.status == 'pending')
            .where(MealCustomization.requires_approval == True)
        )
        
        if hostel_id:
            query = query.where(Student.hostel_id == hostel_id)
            
        if meal_date:
            query = query.where(MealCustomization.meal_date == meal_date)
            
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_by_menu(
        self,
        menu_id: UUID,
        status: Optional[str] = None
    ) -> List[MealCustomization]:
        """
        Find customizations for a specific menu.
        
        Args:
            menu_id: Menu identifier
            status: Filter by status (optional)
            
        Returns:
            List of customizations
        """
        query = (
            select(MealCustomization)
            .where(MealCustomization.menu_id == menu_id)
        )
        
        if status:
            query = query.where(MealCustomization.status == status)
            
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_customization_statistics(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date
    ) -> Dict[str, any]:
        """
        Get customization statistics for a period.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Start of period
            end_date: End of period
            
        Returns:
            Dictionary of statistics
        """
        query = (
            select(
                MealCustomization.status,
                func.count(MealCustomization.id),
                func.avg(MealCustomization.additional_cost)
            )
            .join(Student)
            .where(Student.hostel_id == hostel_id)
            .where(MealCustomization.meal_date.between(start_date, end_date))
            .group_by(MealCustomization.status)
        )
        
        result = await self.db_session.execute(query)
        rows = result.all()
        
        stats = {
            'by_status': {},
            'total_requests': 0,
            'average_cost': Decimal('0.00')
        }
        
        total_cost = Decimal('0.00')
        total_count = 0
        
        for status, count, avg_cost in rows:
            stats['by_status'][status] = {
                'count': count,
                'average_cost': avg_cost or Decimal('0.00')
            }
            stats['total_requests'] += count
            if avg_cost:
                total_cost += avg_cost * count
                total_count += count
                
        if total_count > 0:
            stats['average_cost'] = total_cost / total_count
            
        return stats

    async def find_unfulfilled_customizations(
        self,
        hostel_id: UUID,
        meal_date: date
    ) -> List[MealCustomization]:
        """
        Find approved but unfulfilled customizations.
        
        Args:
            hostel_id: Hostel identifier
            meal_date: Meal date
            
        Returns:
            List of unfulfilled customizations
        """
        query = (
            select(MealCustomization)
            .join(Student)
            .where(Student.hostel_id == hostel_id)
            .where(MealCustomization.meal_date == meal_date)
            .where(MealCustomization.is_approved == True)
            .where(MealCustomization.is_fulfilled == False)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_most_requested_items(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        limit: int = 10
    ) -> List[Dict[str, any]]:
        """
        Get most frequently requested customization items.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Start of period
            end_date: End of period
            limit: Maximum number of results
            
        Returns:
            List of items with request counts
        """
        # This would require unnesting the requested_items array
        # Implementation depends on PostgreSQL array functions
        # Simplified version:
        
        query = (
            select(MealCustomization)
            .join(Student)
            .where(Student.hostel_id == hostel_id)
            .where(MealCustomization.meal_date.between(start_date, end_date))
            .where(MealCustomization.status == 'approved')
        )
        
        result = await self.db_session.execute(query)
        customizations = list(result.scalars().all())
        
        # Count item frequencies
        item_counts = {}
        for customization in customizations:
            for item in customization.requested_items:
                item_counts[item] = item_counts.get(item, 0) + 1
                
        # Sort and limit
        sorted_items = sorted(
            item_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        return [
            {'item': item, 'count': count}
            for item, count in sorted_items
        ]