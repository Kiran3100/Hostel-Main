# --- File: C:\Hostel-Main\app\repositories\mess\nutritional_info_repository.py ---

"""
Nutritional Information Repository Module.

Manages nutritional data, nutrient profiles, dietary values,
and nutritional reporting with comprehensive analytics.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import joinedload

from app.models.mess.nutritional_info import (
    DietaryValue,
    NutrientProfile,
    NutritionalInfo,
    NutritionalReport,
)
from app.repositories.base.base_repository import BaseRepository


class NutritionalInfoRepository(BaseRepository[NutritionalInfo]):
    """
    Repository for managing nutritional information.
    
    Handles detailed nutritional data for meal items with
    verification, validation, and analytics.
    """

    def __init__(self, db_session):
        """Initialize repository with NutritionalInfo model."""
        super().__init__(NutritionalInfo, db_session)

    async def get_by_meal_item(
        self,
        meal_item_id: UUID
    ) -> Optional[NutritionalInfo]:
        """
        Get nutritional info for meal item.
        
        Args:
            meal_item_id: MealItem identifier
            
        Returns:
            NutritionalInfo if found
        """
        query = select(NutritionalInfo).where(
            NutritionalInfo.meal_item_id == meal_item_id
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def get_with_profile(
        self,
        nutritional_info_id: UUID
    ) -> Optional[NutritionalInfo]:
        """
        Get nutritional info with nutrient profile.
        
        Args:
            nutritional_info_id: NutritionalInfo identifier
            
        Returns:
            NutritionalInfo with profile loaded
        """
        query = (
            select(NutritionalInfo)
            .where(NutritionalInfo.id == nutritional_info_id)
            .options(joinedload(NutritionalInfo.nutrient_profile))
        )
        
        result = await self.db_session.execute(query)
        return result.unique().scalar_one_or_none()

    async def find_high_protein_items(
        self,
        min_protein_g: Decimal = Decimal('20.0')
    ) -> List[NutritionalInfo]:
        """
        Find high-protein items.
        
        Args:
            min_protein_g: Minimum protein in grams
            
        Returns:
            List of high-protein items
        """
        query = (
            select(NutritionalInfo)
            .where(NutritionalInfo.protein_g >= min_protein_g)
            .order_by(desc(NutritionalInfo.protein_g))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_low_calorie_items(
        self,
        max_calories: int = 200
    ) -> List[NutritionalInfo]:
        """
        Find low-calorie items.
        
        Args:
            max_calories: Maximum calories per serving
            
        Returns:
            List of low-calorie items
        """
        query = (
            select(NutritionalInfo)
            .where(NutritionalInfo.calories.isnot(None))
            .where(NutritionalInfo.calories <= max_calories)
            .order_by(NutritionalInfo.calories)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_by_macronutrient_range(
        self,
        min_protein: Optional[Decimal] = None,
        max_protein: Optional[Decimal] = None,
        min_carbs: Optional[Decimal] = None,
        max_carbs: Optional[Decimal] = None,
        min_fat: Optional[Decimal] = None,
        max_fat: Optional[Decimal] = None
    ) -> List[NutritionalInfo]:
        """
        Find items within macronutrient ranges.
        
        Args:
            min_protein: Minimum protein (optional)
            max_protein: Maximum protein (optional)
            min_carbs: Minimum carbs (optional)
            max_carbs: Maximum carbs (optional)
            min_fat: Minimum fat (optional)
            max_fat: Maximum fat (optional)
            
        Returns:
            List of matching items
        """
        conditions = []
        
        if min_protein is not None:
            conditions.append(NutritionalInfo.protein_g >= min_protein)
        if max_protein is not None:
            conditions.append(NutritionalInfo.protein_g <= max_protein)
            
        if min_carbs is not None:
            conditions.append(NutritionalInfo.carbohydrates_g >= min_carbs)
        if max_carbs is not None:
            conditions.append(NutritionalInfo.carbohydrates_g <= max_carbs)
            
        if min_fat is not None:
            conditions.append(NutritionalInfo.total_fat_g >= min_fat)
        if max_fat is not None:
            conditions.append(NutritionalInfo.total_fat_g <= max_fat)
            
        query = select(NutritionalInfo)
        
        if conditions:
            query = query.where(and_(*conditions))
            
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_verified_nutritional_info(
        self,
        verified_only: bool = True
    ) -> List[NutritionalInfo]:
        """
        Find verified nutritional information.
        
        Args:
            verified_only: Only verified records
            
        Returns:
            List of verified nutritional info
        """
        conditions = []
        
        if verified_only:
            conditions.append(NutritionalInfo.is_verified == True)
            
        query = select(NutritionalInfo)
        
        if conditions:
            query = query.where(and_(*conditions))
            
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_by_data_source(
        self,
        data_source: str
    ) -> List[NutritionalInfo]:
        """
        Find nutritional info by data source.
        
        Args:
            data_source: Source of data (USDA, Lab Analysis, etc.)
            
        Returns:
            List of nutritional info from source
        """
        query = select(NutritionalInfo).where(
            NutritionalInfo.data_source == data_source
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def calculate_meal_nutrition(
        self,
        item_ids: List[UUID]
    ) -> Dict[str, any]:
        """
        Calculate total nutrition for meal items.
        
        Args:
            item_ids: List of meal item identifiers
            
        Returns:
            Dictionary of total nutritional values
        """
        query = (
            select(
                func.sum(NutritionalInfo.calories).label('total_calories'),
                func.sum(NutritionalInfo.protein_g).label('total_protein'),
                func.sum(NutritionalInfo.carbohydrates_g).label('total_carbs'),
                func.sum(NutritionalInfo.total_fat_g).label('total_fat'),
                func.sum(NutritionalInfo.dietary_fiber_g).label('total_fiber'),
                func.sum(NutritionalInfo.sodium_mg).label('total_sodium')
            )
            .where(NutritionalInfo.meal_item_id.in_(item_ids))
        )
        
        result = await self.db_session.execute(query)
        row = result.first()
        
        if not row:
            return {
                'total_calories': 0,
                'total_protein_g': 0,
                'total_carbs_g': 0,
                'total_fat_g': 0,
                'total_fiber_g': 0,
                'total_sodium_mg': 0
            }
            
        return {
            'total_calories': int(row.total_calories or 0),
            'total_protein_g': float(row.total_protein or 0),
            'total_carbs_g': float(row.total_carbs or 0),
            'total_fat_g': float(row.total_fat or 0),
            'total_fiber_g': float(row.total_fiber or 0),
            'total_sodium_mg': float(row.total_sodium or 0)
        }


class NutrientProfileRepository(BaseRepository[NutrientProfile]):
    """
    Repository for nutrient profiles.
    
    Manages calculated nutrient profiles with daily value
    percentages and dietary fit scores.
    """

    def __init__(self, db_session):
        """Initialize repository with NutrientProfile model."""
        super().__init__(NutrientProfile, db_session)

    async def get_by_nutritional_info(
        self,
        nutritional_info_id: UUID
    ) -> Optional[NutrientProfile]:
        """
        Get nutrient profile by nutritional info.
        
        Args:
            nutritional_info_id: NutritionalInfo identifier
            
        Returns:
            NutrientProfile if found
        """
        query = select(NutrientProfile).where(
            NutrientProfile.nutritional_info_id == nutritional_info_id
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def find_nutrient_dense_items(
        self,
        min_density_score: Decimal = Decimal('5.0')
    ) -> List[NutrientProfile]:
        """
        Find nutrient-dense items.
        
        Args:
            min_density_score: Minimum nutrient density score
            
        Returns:
            List of nutrient-dense profiles
        """
        query = (
            select(NutrientProfile)
            .where(NutrientProfile.is_nutrient_dense == True)
            .where(NutrientProfile.micronutrient_density_score >= min_density_score)
            .order_by(desc(NutrientProfile.micronutrient_density_score))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_by_nutrition_grade(
        self,
        grade: str
    ) -> List[NutrientProfile]:
        """
        Find items by nutrition grade.
        
        Args:
            grade: Nutrition grade (A+, A, B+, etc.)
            
        Returns:
            List of profiles with grade
        """
        query = (
            select(NutrientProfile)
            .where(NutrientProfile.nutrition_grade == grade)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_for_weight_loss(
        self,
        min_score: Decimal = Decimal('70.0')
    ) -> List[NutrientProfile]:
        """
        Find items suitable for weight loss.
        
        Args:
            min_score: Minimum weight loss score
            
        Returns:
            List of suitable profiles
        """
        query = (
            select(NutrientProfile)
            .where(NutrientProfile.weight_loss_score >= min_score)
            .order_by(desc(NutrientProfile.weight_loss_score))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_for_muscle_gain(
        self,
        min_score: Decimal = Decimal('70.0')
    ) -> List[NutrientProfile]:
        """
        Find items suitable for muscle gain.
        
        Args:
            min_score: Minimum muscle gain score
            
        Returns:
            List of suitable profiles
        """
        query = (
            select(NutrientProfile)
            .where(NutrientProfile.muscle_gain_score >= min_score)
            .order_by(desc(NutrientProfile.muscle_gain_score))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_heart_healthy_items(
        self,
        min_score: Decimal = Decimal('70.0')
    ) -> List[NutrientProfile]:
        """
        Find heart-healthy items.
        
        Args:
            min_score: Minimum heart health score
            
        Returns:
            List of heart-healthy profiles
        """
        query = (
            select(NutrientProfile)
            .where(NutrientProfile.heart_health_score >= min_score)
            .order_by(desc(NutrientProfile.heart_health_score))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())


class DietaryValueRepository(BaseRepository[DietaryValue]):
    """
    Repository for dietary values.
    
    Manages diet-specific suitability and compliance
    tracking for various dietary patterns.
    """

    def __init__(self, db_session):
        """Initialize repository with DietaryValue model."""
        super().__init__(DietaryValue, db_session)

    async def find_by_meal_item(
        self,
        meal_item_id: UUID
    ) -> List[DietaryValue]:
        """
        Get all dietary values for meal item.
        
        Args:
            meal_item_id: MealItem identifier
            
        Returns:
            List of dietary values
        """
        query = select(DietaryValue).where(
            DietaryValue.meal_item_id == meal_item_id
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_by_diet_type(
        self,
        meal_item_id: UUID,
        diet_type: str
    ) -> Optional[DietaryValue]:
        """
        Get dietary value for specific diet.
        
        Args:
            meal_item_id: MealItem identifier
            diet_type: Type of diet
            
        Returns:
            DietaryValue if found
        """
        query = (
            select(DietaryValue)
            .where(DietaryValue.meal_item_id == meal_item_id)
            .where(DietaryValue.diet_type == diet_type)
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def find_compliant_items(
        self,
        diet_type: str,
        min_score: Optional[Decimal] = None
    ) -> List[DietaryValue]:
        """
        Find items compliant with diet.
        
        Args:
            diet_type: Type of diet
            min_score: Minimum compliance score (optional)
            
        Returns:
            List of compliant dietary values
        """
        conditions = [
            DietaryValue.diet_type == diet_type,
            DietaryValue.is_compliant == True
        ]
        
        if min_score is not None:
            conditions.append(DietaryValue.compliance_score >= min_score)
            
        query = (
            select(DietaryValue)
            .where(and_(*conditions))
            .order_by(desc(DietaryValue.compliance_score))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_by_suitability(
        self,
        diet_type: str,
        suitability_rating: str
    ) -> List[DietaryValue]:
        """
        Find items by suitability rating.
        
        Args:
            diet_type: Type of diet
            suitability_rating: Suitability rating
            
        Returns:
            List of dietary values
        """
        query = (
            select(DietaryValue)
            .where(DietaryValue.diet_type == diet_type)
            .where(DietaryValue.suitability_rating == suitability_rating)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def find_keto_friendly_items(
        self,
        max_net_carbs: Decimal = Decimal('10.0')
    ) -> List[DietaryValue]:
        """
        Find keto-friendly items.
        
        Args:
            max_net_carbs: Maximum net carbs
            
        Returns:
            List of keto-friendly items
        """
        query = (
            select(DietaryValue)
            .where(DietaryValue.diet_type == 'keto')
            .where(DietaryValue.net_carbs_g <= max_net_carbs)
            .where(DietaryValue.is_compliant == True)
            .order_by(DietaryValue.net_carbs_g)
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())


class NutritionalReportRepository(BaseRepository[NutritionalReport]):
    """
    Repository for nutritional reports.
    
    Manages aggregated nutritional analysis for menus
    with recommendations and compliance tracking.
    """

    def __init__(self, db_session):
        """Initialize repository with NutritionalReport model."""
        super().__init__(NutritionalReport, db_session)

    async def find_by_hostel(
        self,
        hostel_id: UUID,
        report_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[NutritionalReport]:
        """
        Get nutritional reports for hostel.
        
        Args:
            hostel_id: Hostel identifier
            report_type: Report type filter (optional)
            start_date: Start date filter (optional)
            end_date: End date filter (optional)
            
        Returns:
            List of nutritional reports
        """
        conditions = [NutritionalReport.hostel_id == hostel_id]
        
        if report_type:
            conditions.append(NutritionalReport.report_type == report_type)
            
        if start_date:
            conditions.append(NutritionalReport.start_date >= start_date)
        if end_date:
            conditions.append(NutritionalReport.end_date <= end_date)
            
        query = (
            select(NutritionalReport)
            .where(and_(*conditions))
            .order_by(desc(NutritionalReport.end_date))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())

    async def get_latest_report(
        self,
        hostel_id: UUID,
        report_type: str = 'weekly_menu'
    ) -> Optional[NutritionalReport]:
        """
        Get latest report for hostel.
        
        Args:
            hostel_id: Hostel identifier
            report_type: Type of report
            
        Returns:
            Latest NutritionalReport
        """
        query = (
            select(NutritionalReport)
            .where(NutritionalReport.hostel_id == hostel_id)
            .where(NutritionalReport.report_type == report_type)
            .order_by(desc(NutritionalReport.end_date))
            .limit(1)
        )
        
        result = await self.db_session.execute(query)
        return result.scalar_one_or_none()

    async def generate_daily_report(
        self,
        hostel_id: UUID,
        report_date: date,
        menu_items: List[UUID]
    ) -> NutritionalReport:
        """
        Generate daily nutritional report.
        
        Args:
            hostel_id: Hostel identifier
            report_date: Date of report
            menu_items: List of menu item IDs
            
        Returns:
            Generated NutritionalReport
        """
        # Calculate totals from nutritional info
        nutrition_totals = await NutritionalInfoRepository(
            self.db_session
        ).calculate_meal_nutrition(menu_items)
        
        # Create report
        report = NutritionalReport(
            report_type='daily_menu',
            hostel_id=hostel_id,
            start_date=report_date,
            end_date=report_date,
            total_calories=nutrition_totals['total_calories'],
            average_daily_calories=nutrition_totals['total_calories'],
            total_protein_g=Decimal(str(nutrition_totals['total_protein_g'])),
            total_carbs_g=Decimal(str(nutrition_totals['total_carbs_g'])),
            total_fat_g=Decimal(str(nutrition_totals['total_fat_g'])),
            unique_items_count=len(menu_items),
            generated_at=datetime.utcnow()
        )
        
        # Calculate macro percentages
        total_macros = (
            nutrition_totals['total_protein_g'] +
            nutrition_totals['total_carbs_g'] +
            nutrition_totals['total_fat_g']
        )
        
        if total_macros > 0:
            report.protein_percent = Decimal(str(
                round((nutrition_totals['total_protein_g'] / total_macros) * 100, 2)
            ))
            report.carbs_percent = Decimal(str(
                round((nutrition_totals['total_carbs_g'] / total_macros) * 100, 2)
            ))
            report.fat_percent = Decimal(str(
                round((nutrition_totals['total_fat_g'] / total_macros) * 100, 2)
            ))
            
            # Check if balanced (rough guideline: 30% protein, 40% carbs, 30% fat)
            protein_pct = float(report.protein_percent)
            carbs_pct = float(report.carbs_percent)
            fat_pct = float(report.fat_percent)
            
            is_balanced = (
                20 <= protein_pct <= 40 and
                30 <= carbs_pct <= 50 and
                20 <= fat_pct <= 40
            )
            report.is_balanced = is_balanced
            
        self.db_session.add(report)
        await self.db_session.commit()
        await self.db_session.refresh(report)
        
        return report

    async def find_deficient_reports(
        self,
        hostel_id: UUID
    ) -> List[NutritionalReport]:
        """
        Find reports with nutrient deficiencies.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            List of reports with deficiencies
        """
        query = (
            select(NutritionalReport)
            .where(NutritionalReport.hostel_id == hostel_id)
            .where(NutritionalReport.meets_rda_requirements == False)
            .where(func.array_length(NutritionalReport.deficient_nutrients, 1) > 0)
            .order_by(desc(NutritionalReport.end_date))
        )
        
        result = await self.db_session.execute(query)
        return list(result.scalars().all())