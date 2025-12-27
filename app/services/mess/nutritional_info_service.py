# app/services/mess/nutritional_info_service.py
"""
Nutritional Info Service

Handles nutritional analysis for menu items and menus:
- Per-item nutritional information
- Aggregate nutritional reports
- Nutritional compliance checking
- Dietary goal tracking

Performance Optimizations:
- Cached nutritional calculations
- Efficient aggregation queries
- Batch nutritional analysis
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.repositories.mess import NutritionalInfoRepository
from app.schemas.mess import (
    NutritionalInfo,
    NutritionalReport,
)
from app.core1.exceptions import (
    ValidationException,
    NotFoundException,
)


class NutritionalInfoService:
    """
    High-level nutritional info service.
    
    This service manages:
    - Nutritional information for menu items
    - Aggregate nutritional reports
    - Compliance with dietary guidelines
    - Nutritional trend analysis
    """

    # Recommended Daily Allowances (RDA) - example values
    RDA_CALORIES = Decimal('2000')
    RDA_PROTEIN = Decimal('50')  # grams
    RDA_CARBS = Decimal('300')  # grams
    RDA_FATS = Decimal('65')  # grams
    RDA_FIBER = Decimal('25')  # grams

    def __init__(self, nutrit_repo: NutritionalInfoRepository) -> None:
        """
        Initialize the nutritional info service.
        
        Args:
            nutrit_repo: Repository for nutritional operations
        """
        self.nutrit_repo = nutrit_repo

    # -------------------------------------------------------------------------
    # Item-Level Nutritional Info
    # -------------------------------------------------------------------------

    def get_nutritional_info_for_item(
        self,
        db: Session,
        meal_item_id: UUID,
    ) -> NutritionalInfo:
        """
        Get nutritional information for a specific menu item.
        
        Args:
            db: Database session
            meal_item_id: Unique identifier of the menu item
            
        Returns:
            NutritionalInfo schema
            
        Raises:
            NotFoundException: If nutritional info not found
        """
        try:
            obj = self.nutrit_repo.get_by_meal_item_id(db, meal_item_id)
            
            if not obj:
                raise NotFoundException(
                    f"Nutritional info not found for item {meal_item_id}"
                )
            
            return NutritionalInfo.model_validate(obj)
            
        except NotFoundException:
            raise
        except Exception as e:
            raise ValidationException(
                f"Error retrieving nutritional info: {str(e)}"
            )

    def create_nutritional_info(
        self,
        db: Session,
        meal_item_id: UUID,
        info: NutritionalInfo,
    ) -> NutritionalInfo:
        """
        Create nutritional information for a menu item.
        
        Args:
            db: Database session
            meal_item_id: Unique identifier of the menu item
            info: NutritionalInfo schema with nutritional data
            
        Returns:
            Created NutritionalInfo schema
            
        Raises:
            ValidationException: If nutritional data is invalid
        """
        try:
            # Validate nutritional data
            self._validate_nutritional_info(info)
            
            payload = info.model_dump(exclude_none=True, exclude_unset=True)
            payload["meal_item_id"] = meal_item_id
            
            obj = self.nutrit_repo.create(db, payload)
            db.flush()
            
            return NutritionalInfo.model_validate(obj)
            
        except IntegrityError as e:
            db.rollback()
            raise ValidationException(
                f"Nutritional info already exists for this item: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error creating nutritional info: {str(e)}"
            )

    def update_nutritional_info(
        self,
        db: Session,
        meal_item_id: UUID,
        info: NutritionalInfo,
    ) -> NutritionalInfo:
        """
        Update nutritional information for a menu item.
        
        Args:
            db: Database session
            meal_item_id: Unique identifier of the menu item
            info: Updated NutritionalInfo schema
            
        Returns:
            Updated NutritionalInfo schema
        """
        try:
            existing = self.nutrit_repo.get_by_meal_item_id(db, meal_item_id)
            
            if not existing:
                raise NotFoundException(
                    f"Nutritional info not found for item {meal_item_id}"
                )
            
            self._validate_nutritional_info(info)
            
            payload = info.model_dump(exclude_none=True, exclude_unset=True)
            
            obj = self.nutrit_repo.update(db, existing, payload)
            db.flush()
            
            return NutritionalInfo.model_validate(obj)
            
        except NotFoundException:
            raise
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error updating nutritional info: {str(e)}"
            )

    def bulk_update_nutritional_info(
        self,
        db: Session,
        updates: Dict[UUID, NutritionalInfo],
    ) -> List[NutritionalInfo]:
        """
        Update nutritional information for multiple items at once.
        
        Args:
            db: Database session
            updates: Dictionary mapping meal_item_id to NutritionalInfo
            
        Returns:
            List of updated NutritionalInfo schemas
        """
        updated_items = []
        
        try:
            for meal_item_id, info in updates.items():
                try:
                    updated = self.update_nutritional_info(db, meal_item_id, info)
                    updated_items.append(updated)
                except (NotFoundException, ValidationException):
                    # Log and continue
                    continue
            
            return updated_items
            
        except Exception as e:
            db.rollback()
            raise ValidationException(
                f"Error in bulk updating nutritional info: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Menu-Level Nutritional Reports
    # -------------------------------------------------------------------------

    def get_nutritional_report_for_menu(
        self,
        db: Session,
        menu_id: UUID,
    ) -> NutritionalReport:
        """
        Get aggregate nutritional report for a complete menu.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            
        Returns:
            NutritionalReport schema with aggregated nutritional data
            
        Raises:
            NotFoundException: If no nutritional data available
        """
        try:
            data = self.nutrit_repo.build_report_for_menu(db, menu_id)
            
            if not data:
                raise NotFoundException(
                    f"No nutritional report available for menu {menu_id}"
                )
            
            # Enrich with RDA comparisons
            enriched_data = self._enrich_with_rda_comparison(data)
            
            return NutritionalReport.model_validate(enriched_data)
            
        except NotFoundException:
            raise
        except Exception as e:
            raise ValidationException(
                f"Error generating nutritional report for menu: {str(e)}"
            )

    def get_nutritional_report_for_period(
        self,
        db: Session,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
    ) -> NutritionalReport:
        """
        Get aggregate nutritional report for a time period.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            start_date: Start date of the period
            end_date: End date of the period
            
        Returns:
            NutritionalReport schema with period aggregation
            
        Raises:
            ValidationException: If date range is invalid
            NotFoundException: If no data available
        """
        try:
            # Validate date range
            self._validate_date_range(start_date, end_date)
            
            data = self.nutrit_repo.build_report_for_period(
                db=db,
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
            )
            
            if not data:
                raise NotFoundException(
                    f"No nutritional report available for period "
                    f"{start_date} to {end_date}"
                )
            
            # Calculate daily averages
            days = (end_date - start_date).days + 1
            averaged_data = self._calculate_daily_averages(data, days)
            
            # Enrich with RDA comparisons
            enriched_data = self._enrich_with_rda_comparison(averaged_data)
            
            return NutritionalReport.model_validate(enriched_data)
            
        except (ValidationException, NotFoundException):
            raise
        except Exception as e:
            raise ValidationException(
                f"Error generating nutritional report for period: {str(e)}"
            )

    def get_meal_type_breakdown(
        self,
        db: Session,
        menu_id: UUID,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get nutritional breakdown by meal type (breakfast, lunch, dinner).
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            
        Returns:
            Dictionary with nutritional data per meal type
        """
        try:
            breakdown = self.nutrit_repo.get_meal_type_breakdown(db, menu_id)
            
            result = {}
            for meal_type, nutrients in breakdown.items():
                result[meal_type] = {
                    "calories": float(nutrients.get("calories", 0)),
                    "protein": float(nutrients.get("protein", 0)),
                    "carbohydrates": float(nutrients.get("carbohydrates", 0)),
                    "fats": float(nutrients.get("fats", 0)),
                    "fiber": float(nutrients.get("fiber", 0)),
                    "rda_percentages": self._calculate_rda_percentages(nutrients),
                }
            
            return result
            
        except Exception as e:
            raise ValidationException(
                f"Error getting meal type breakdown: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Nutritional Analysis & Compliance
    # -------------------------------------------------------------------------

    def analyze_nutritional_balance(
        self,
        db: Session,
        menu_id: UUID,
    ) -> Dict[str, Any]:
        """
        Analyze the nutritional balance of a menu against guidelines.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            
        Returns:
            Dictionary with balance analysis
        """
        try:
            report = self.get_nutritional_report_for_menu(db, menu_id)
            
            analysis = {
                "menu_id": str(menu_id),
                "overall_score": 0.0,
                "macronutrient_balance": self._analyze_macronutrient_balance(report),
                "micronutrient_adequacy": self._analyze_micronutrient_adequacy(report),
                "calorie_distribution": self._analyze_calorie_distribution(report),
                "recommendations": [],
                "warnings": [],
            }
            
            # Calculate overall score
            analysis["overall_score"] = self._calculate_overall_nutritional_score(report)
            
            # Generate recommendations
            analysis["recommendations"] = self._generate_nutritional_recommendations(report)
            
            # Check for warnings
            analysis["warnings"] = self._check_nutritional_warnings(report)
            
            return analysis
            
        except Exception as e:
            raise ValidationException(
                f"Error analyzing nutritional balance: {str(e)}"
            )

    def check_dietary_compliance(
        self,
        db: Session,
        menu_id: UUID,
        dietary_requirements: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Check if a menu meets specific dietary requirements.
        
        Args:
            db: Database session
            menu_id: Unique identifier of the menu
            dietary_requirements: Dictionary with required nutritional targets
            
        Returns:
            Dictionary with compliance status
        """
        try:
            report = self.get_nutritional_report_for_menu(db, menu_id)
            
            compliance = {
                "menu_id": str(menu_id),
                "is_compliant": True,
                "requirements": dietary_requirements,
                "actual_values": {},
                "deviations": {},
                "compliance_percentage": 0.0,
            }
            
            total_requirements = 0
            met_requirements = 0
            
            for nutrient, requirement in dietary_requirements.items():
                actual = getattr(report, nutrient, 0)
                compliance["actual_values"][nutrient] = float(actual)
                
                # Calculate deviation
                if requirement.get("min") is not None:
                    min_val = Decimal(str(requirement["min"]))
                    if actual < min_val:
                        compliance["is_compliant"] = False
                        compliance["deviations"][nutrient] = {
                            "type": "below_minimum",
                            "required": float(min_val),
                            "actual": float(actual),
                            "deficit": float(min_val - actual),
                        }
                    else:
                        met_requirements += 1
                    total_requirements += 1
                
                if requirement.get("max") is not None:
                    max_val = Decimal(str(requirement["max"]))
                    if actual > max_val:
                        compliance["is_compliant"] = False
                        compliance["deviations"][nutrient] = {
                            "type": "above_maximum",
                            "required": float(max_val),
                            "actual": float(actual),
                            "excess": float(actual - max_val),
                        }
                    else:
                        met_requirements += 1
                    total_requirements += 1
            
            # Calculate compliance percentage
            if total_requirements > 0:
                compliance["compliance_percentage"] = (
                    met_requirements / total_requirements * 100
                )
            
            return compliance
            
        except Exception as e:
            raise ValidationException(
                f"Error checking dietary compliance: {str(e)}"
            )

    def get_nutritional_trends(
        self,
        db: Session,
        hostel_id: UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get nutritional trends over time.
        
        Args:
            db: Database session
            hostel_id: Unique identifier of the hostel
            days: Number of days to analyze
            
        Returns:
            Dictionary with trend data
        """
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            trends = self.nutrit_repo.get_nutritional_trends(
                db, hostel_id, start_date, end_date
            )
            
            return {
                "hostel_id": str(hostel_id),
                "period_days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "daily_trends": trends.get("daily_trends", []),
                "average_values": trends.get("averages", {}),
                "trend_direction": trends.get("direction", {}),
                "variability": trends.get("variability", {}),
            }
            
        except Exception as e:
            raise ValidationException(
                f"Error retrieving nutritional trends: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Comparative Analysis
    # -------------------------------------------------------------------------

    def compare_menus_nutritionally(
        self,
        db: Session,
        menu_ids: List[UUID],
    ) -> Dict[str, Any]:
        """
        Compare nutritional content across multiple menus.
        
        Args:
            db: Database session
            menu_ids: List of menu IDs to compare
            
        Returns:
            Dictionary with comparative analysis
        """
        try:
            if len(menu_ids) < 2:
                raise ValidationException(
                    "At least 2 menus required for comparison"
                )
            
            comparisons = []
            
            for menu_id in menu_ids:
                try:
                    report = self.get_nutritional_report_for_menu(db, menu_id)
                    comparisons.append({
                        "menu_id": str(menu_id),
                        "calories": float(getattr(report, 'total_calories', 0)),
                        "protein": float(getattr(report, 'total_protein', 0)),
                        "carbohydrates": float(getattr(report, 'total_carbohydrates', 0)),
                        "fats": float(getattr(report, 'total_fats', 0)),
                        "fiber": float(getattr(report, 'total_fiber', 0)),
                    })
                except NotFoundException:
                    continue
            
            if not comparisons:
                raise NotFoundException("No nutritional data available for comparison")
            
            # Calculate statistics
            nutrients = ["calories", "protein", "carbohydrates", "fats", "fiber"]
            stats = {}
            
            for nutrient in nutrients:
                values = [c[nutrient] for c in comparisons]
                stats[nutrient] = {
                    "min": min(values),
                    "max": max(values),
                    "average": sum(values) / len(values),
                    "range": max(values) - min(values),
                }
            
            return {
                "total_menus_compared": len(comparisons),
                "menus": comparisons,
                "statistics": stats,
                "best_balanced_menu": self._identify_best_balanced(comparisons),
            }
            
        except (ValidationException, NotFoundException):
            raise
        except Exception as e:
            raise ValidationException(
                f"Error comparing menus nutritionally: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Validation & Helper Methods
    # -------------------------------------------------------------------------

    def _validate_nutritional_info(self, info: NutritionalInfo) -> None:
        """
        Validate nutritional information data.
        
        Args:
            info: NutritionalInfo to validate
            
        Raises:
            ValidationException: If data is invalid
        """
        # Validate non-negative values
        numeric_fields = [
            'calories', 'protein', 'carbohydrates', 'fats', 'fiber',
            'sugar', 'sodium', 'cholesterol'
        ]
        
        for field in numeric_fields:
            value = getattr(info, field, None)
            if value is not None and value < 0:
                raise ValidationException(
                    f"{field} cannot be negative"
                )

    def _validate_date_range(self, start_date: date, end_date: date) -> None:
        """Validate date range for reports."""
        if start_date > end_date:
            raise ValidationException(
                "Start date must be before or equal to end date"
            )
        
        # Limit to reasonable range
        max_days = 365
        if (end_date - start_date).days > max_days:
            raise ValidationException(
                f"Date range cannot exceed {max_days} days"
            )

    def _enrich_with_rda_comparison(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich nutritional data with RDA percentage calculations."""
        enriched = data.copy()
        
        enriched["rda_percentages"] = {
            "calories": float(
                (Decimal(str(data.get("total_calories", 0))) / self.RDA_CALORIES) * 100
            ),
            "protein": float(
                (Decimal(str(data.get("total_protein", 0))) / self.RDA_PROTEIN) * 100
            ),
            "carbohydrates": float(
                (Decimal(str(data.get("total_carbohydrates", 0))) / self.RDA_CARBS) * 100
            ),
            "fats": float(
                (Decimal(str(data.get("total_fats", 0))) / self.RDA_FATS) * 100
            ),
            "fiber": float(
                (Decimal(str(data.get("total_fiber", 0))) / self.RDA_FIBER) * 100
            ),
        }
        
        return enriched

    def _calculate_daily_averages(
        self,
        data: Dict[str, Any],
        days: int,
    ) -> Dict[str, Any]:
        """Calculate daily averages from period data."""
        averaged = data.copy()
        
        if days > 0:
            numeric_fields = [
                "total_calories", "total_protein", "total_carbohydrates",
                "total_fats", "total_fiber"
            ]
            
            for field in numeric_fields:
                if field in averaged:
                    averaged[field] = Decimal(str(averaged[field])) / days
        
        return averaged

    def _calculate_rda_percentages(self, nutrients: Dict[str, Any]) -> Dict[str, float]:
        """Calculate RDA percentages for given nutrient values."""
        return {
            "calories": float(
                (Decimal(str(nutrients.get("calories", 0))) / self.RDA_CALORIES) * 100
            ),
            "protein": float(
                (Decimal(str(nutrients.get("protein", 0))) / self.RDA_PROTEIN) * 100
            ),
            "carbohydrates": float(
                (Decimal(str(nutrients.get("carbohydrates", 0))) / self.RDA_CARBS) * 100
            ),
            "fats": float(
                (Decimal(str(nutrients.get("fats", 0))) / self.RDA_FATS) * 100
            ),
        }

    def _analyze_macronutrient_balance(self, report: NutritionalReport) -> Dict[str, Any]:
        """Analyze macronutrient balance (protein, carbs, fats)."""
        total_calories = float(getattr(report, 'total_calories', 0))
        
        if total_calories == 0:
            return {
                "protein_percentage": 0,
                "carbs_percentage": 0,
                "fats_percentage": 0,
                "is_balanced": False,
            }
        
        # Calculate calorie contribution from each macronutrient
        protein_cals = float(getattr(report, 'total_protein', 0)) * 4
        carbs_cals = float(getattr(report, 'total_carbohydrates', 0)) * 4
        fats_cals = float(getattr(report, 'total_fats', 0)) * 9
        
        return {
            "protein_percentage": (protein_cals / total_calories) * 100,
            "carbs_percentage": (carbs_cals / total_calories) * 100,
            "fats_percentage": (fats_cals / total_calories) * 100,
            "is_balanced": self._check_macronutrient_balance(
                protein_cals, carbs_cals, fats_cals, total_calories
            ),
        }

    def _check_macronutrient_balance(
        self,
        protein_cals: float,
        carbs_cals: float,
        fats_cals: float,
        total_cals: float,
    ) -> bool:
        """Check if macronutrient distribution is balanced."""
        if total_cals == 0:
            return False
        
        protein_pct = (protein_cals / total_cals) * 100
        carbs_pct = (carbs_cals / total_cals) * 100
        fats_pct = (fats_cals / total_cals) * 100
        
        # Acceptable ranges: Protein 10-35%, Carbs 45-65%, Fats 20-35%
        return (
            10 <= protein_pct <= 35 and
            45 <= carbs_pct <= 65 and
            20 <= fats_pct <= 35
        )

    def _analyze_micronutrient_adequacy(self, report: NutritionalReport) -> Dict[str, Any]:
        """Analyze micronutrient adequacy."""
        # Placeholder - would include vitamins, minerals, etc.
        return {
            "adequate": [],
            "deficient": [],
            "excessive": [],
        }

    def _analyze_calorie_distribution(self, report: NutritionalReport) -> Dict[str, Any]:
        """Analyze calorie distribution across meals."""
        # Placeholder for meal-wise calorie distribution
        return {
            "breakfast_percentage": 0,
            "lunch_percentage": 0,
            "dinner_percentage": 0,
            "is_well_distributed": False,
        }

    def _calculate_overall_nutritional_score(self, report: NutritionalReport) -> float:
        """Calculate an overall nutritional score (0-100)."""
        # Placeholder scoring logic
        score = 75.0  # Base score
        
        # Adjust based on RDA compliance
        # This would be more sophisticated in production
        
        return min(100.0, max(0.0, score))

    def _generate_nutritional_recommendations(
        self,
        report: NutritionalReport,
    ) -> List[str]:
        """Generate nutritional recommendations based on the report."""
        recommendations = []
        
        # Check protein
        protein_pct = (
            float(getattr(report, 'total_protein', 0)) / float(self.RDA_PROTEIN)
        ) * 100
        
        if protein_pct < 80:
            recommendations.append("Increase protein content to meet daily requirements")
        
        # Check fiber
        fiber_pct = (
            float(getattr(report, 'total_fiber', 0)) / float(self.RDA_FIBER)
        ) * 100
        
        if fiber_pct < 80:
            recommendations.append("Add more fiber-rich foods like whole grains and vegetables")
        
        return recommendations

    def _check_nutritional_warnings(self, report: NutritionalReport) -> List[str]:
        """Check for nutritional warnings."""
        warnings = []
        
        # Check for excessive sodium
        sodium = float(getattr(report, 'total_sodium', 0))
        if sodium > 2300:  # mg
            warnings.append(f"Sodium content ({sodium}mg) exceeds recommended limit")
        
        # Check for excessive sugar
        sugar = float(getattr(report, 'total_sugar', 0))
        if sugar > 50:  # grams
            warnings.append(f"Sugar content ({sugar}g) is high")
        
        return warnings

    def _identify_best_balanced(self, comparisons: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Identify the best balanced menu from comparisons."""
        if not comparisons:
            return None
        
        # Simple heuristic: closest to RDA targets
        best_menu = None
        best_score = float('inf')
        
        for menu in comparisons:
            # Calculate deviation from RDA
            score = abs(menu["calories"] - float(self.RDA_CALORIES))
            score += abs(menu["protein"] - float(self.RDA_PROTEIN)) * 10
            score += abs(menu["carbohydrates"] - float(self.RDA_CARBS)) * 5
            score += abs(menu["fats"] - float(self.RDA_FATS)) * 10
            
            if score < best_score:
                best_score = score
                best_menu = menu
        
        return best_menu