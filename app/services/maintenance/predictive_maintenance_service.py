"""
Predictive Maintenance Service

Uses historical analytics and pattern recognition to predict maintenance needs
and recommend preventive actions.

Features:
- Risk assessment for equipment and facilities
- Failure prediction based on historical patterns
- Preventive action recommendations
- Maintenance schedule optimization
- Cost optimization suggestions
- Asset health scoring
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceAnalyticsRepository
from app.schemas.common import DateRangeFilter
from app.core1.exceptions import ValidationException, BusinessLogicException
from app.core1.logging import logger


class PredictiveMaintenanceService:
    """
    High-level, rule-based predictive maintenance service.

    Uses historical data and heuristics to predict maintenance needs
    and optimize scheduling. Can be enhanced with ML models in the future.
    """

    # Risk scoring thresholds
    RISK_THRESHOLDS = {
        "low": 0,
        "medium": 40,
        "high": 60,
        "critical": 80,
    }

    # Weights for risk calculation
    RISK_WEIGHTS = {
        "avg_completion_time": 0.3,
        "overdue_rate": 0.3,
        "backlog_size": 0.2,
        "cost_trend": 0.1,
        "failure_frequency": 0.1,
    }

    def __init__(self, analytics_repo: MaintenanceAnalyticsRepository) -> None:
        """
        Initialize the predictive maintenance service.

        Args:
            analytics_repo: Repository for analytics data access
        """
        if not analytics_repo:
            raise ValueError("MaintenanceAnalyticsRepository is required")
        self.analytics_repo = analytics_repo

    # -------------------------------------------------------------------------
    # Risk Assessment
    # -------------------------------------------------------------------------

    def get_risk_assessment_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive risk assessment for maintenance operations.

        Analyzes multiple factors to determine overall maintenance risk level.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            period: Date range for analysis

        Returns:
            Dictionary with risk assessment and contributing factors

        Raises:
            ValidationException: If no data available
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        self._validate_date_range(period)

        try:
            logger.info(
                f"Performing risk assessment for hostel {hostel_id}"
            )

            # Get analytics data
            analytics = self.analytics_repo.get_analytics_for_hostel(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            
            if not analytics:
                raise ValidationException(
                    "No maintenance analytics available for risk assessment"
                )

            # Calculate risk factors
            risk_factors = self._calculate_risk_factors(analytics)

            # Calculate overall risk score
            risk_score = self._calculate_risk_score(risk_factors)

            # Determine risk level
            risk_level = self._determine_risk_level(risk_score)

            # Generate risk reasons
            reasons = self._identify_risk_reasons(risk_factors)

            # Generate recommendations
            recommendations = self._generate_risk_recommendations(
                risk_level,
                risk_factors
            )

            assessment = {
                "hostel_id": str(hostel_id),
                "period_start": period.start_date.isoformat(),
                "period_end": period.end_date.isoformat(),
                "risk_score": round(risk_score, 2),
                "risk_level": risk_level,
                "risk_factors": risk_factors,
                "contributing_reasons": reasons,
                "recommendations": recommendations,
                "assessed_at": datetime.utcnow().isoformat(),
            }

            logger.info(
                f"Risk assessment completed: {risk_level} level "
                f"(score: {risk_score:.1f})"
            )

            return assessment

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error performing risk assessment: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to perform risk assessment: {str(e)}"
            )

    def get_category_risk_assessment(
        self,
        db: Session,
        hostel_id: UUID,
        category: str,
        period: DateRangeFilter,
    ) -> Dict[str, Any]:
        """
        Assess risk for a specific maintenance category.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            category: Maintenance category
            period: Date range for analysis

        Returns:
            Dictionary with category-specific risk assessment
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")
        if not category:
            raise ValidationException("Category is required")

        try:
            # Get category breakdown
            breakdown = self.analytics_repo.get_category_breakdown(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )

            if not breakdown or "categories" not in breakdown:
                raise ValidationException(
                    f"No data available for category {category}"
                )

            # Find specific category data
            category_data = next(
                (c for c in breakdown["categories"] if c.get("category") == category),
                None
            )

            if not category_data:
                raise ValidationException(
                    f"No data found for category {category}"
                )

            # Calculate category-specific risk
            risk_score = self._calculate_category_risk(category_data)
            risk_level = self._determine_risk_level(risk_score)

            return {
                "hostel_id": str(hostel_id),
                "category": category,
                "period_start": period.start_date.isoformat(),
                "period_end": period.end_date.isoformat(),
                "risk_score": round(risk_score, 2),
                "risk_level": risk_level,
                "metrics": category_data,
                "recommendations": self._generate_category_recommendations(
                    category,
                    category_data,
                    risk_level
                ),
            }

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error assessing category risk: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to assess category risk: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Preventive Action Recommendations
    # -------------------------------------------------------------------------

    def recommend_preventive_actions(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Dict[str, Any]:
        """
        Generate preventive maintenance action recommendations.

        Analyzes patterns to suggest proactive measures that can
        reduce reactive maintenance needs.

        Args:
            db: Session,
            hostel_id: UUID of the hostel
            period: Date range for analysis

        Returns:
            Dictionary with preventive action recommendations
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        self._validate_date_range(period)

        try:
            logger.info(
                f"Generating preventive action recommendations for hostel {hostel_id}"
            )

            # Get category breakdown for analysis
            breakdown = self.analytics_repo.get_category_breakdown(
                db=db,
                hostel_id=hostel_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            
            if not breakdown or "categories" not in breakdown:
                raise ValidationException(
                    "No category data available for recommendations"
                )

            categories = breakdown.get("categories", [])
            recommendations: List[Dict[str, Any]] = []

            # Analyze each category
            for cat in categories:
                category_name = cat.get("category")
                total_requests = cat.get("total_requests", 0)
                avg_resolution = cat.get("avg_resolution_hours", 0)
                total_cost = cat.get("total_cost", 0)

                # Heuristic: High volume + slow resolution = need preventive focus
                if total_requests >= 10 and avg_resolution > 24:
                    recommendations.append({
                        "category": category_name,
                        "priority": "high",
                        "reason": "high_volume_and_slow_resolution",
                        "metrics": {
                            "request_count": total_requests,
                            "avg_resolution_hours": avg_resolution,
                            "total_cost": total_cost,
                        },
                        "recommended_actions": [
                            "implement_preventive_inspection_schedule",
                            "increase_spare_parts_inventory",
                            "provide_staff_training",
                            "review_vendor_performance",
                        ],
                        "expected_impact": "Reduce reactive requests by 30-40%",
                    })

                # Heuristic: High cost category
                elif total_cost > 10000:
                    recommendations.append({
                        "category": category_name,
                        "priority": "medium",
                        "reason": "high_cost_category",
                        "metrics": {
                            "request_count": total_requests,
                            "total_cost": total_cost,
                        },
                        "recommended_actions": [
                            "conduct_cost_analysis",
                            "negotiate_vendor_contracts",
                            "explore_alternative_solutions",
                            "implement_predictive_monitoring",
                        ],
                        "expected_impact": "Reduce costs by 15-25%",
                    })

                # Heuristic: Frequent but low complexity
                elif total_requests >= 15 and avg_resolution < 4:
                    recommendations.append({
                        "category": category_name,
                        "priority": "low",
                        "reason": "frequent_minor_issues",
                        "metrics": {
                            "request_count": total_requests,
                            "avg_resolution_hours": avg_resolution,
                        },
                        "recommended_actions": [
                            "create_self_service_guides",
                            "train_residents_on_prevention",
                            "automate_routine_tasks",
                        ],
                        "expected_impact": "Reduce request volume by 20-30%",
                    })

            # Sort by priority
            priority_order = {"high": 0, "medium": 1, "low": 2}
            recommendations.sort(
                key=lambda x: priority_order.get(x.get("priority", "low"), 3)
            )

            result = {
                "hostel_id": str(hostel_id),
                "period_start": period.start_date.isoformat(),
                "period_end": period.end_date.isoformat(),
                "total_recommendations": len(recommendations),
                "recommendations": recommendations,
                "summary": self._generate_recommendation_summary(recommendations),
                "generated_at": datetime.utcnow().isoformat(),
            }

            logger.info(
                f"Generated {len(recommendations)} preventive action recommendations"
            )

            return result

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error generating preventive recommendations: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to generate preventive recommendations: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Failure Prediction
    # -------------------------------------------------------------------------

    def predict_equipment_failures(
        self,
        db: Session,
        hostel_id: UUID,
        lookback_days: int = 90,
        lookahead_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Predict potential equipment failures based on historical patterns.

        Args:
            db: Database session
            hostel_id: UUID of the hostel
            lookback_days: Days of history to analyze
            lookahead_days: Days to predict ahead

        Returns:
            Dictionary with failure predictions
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        if lookback_days < 30:
            raise ValidationException("lookback_days must be at least 30")

        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=lookback_days)

            # Get historical analytics
            analytics = self.analytics_repo.get_analytics_for_hostel(
                db=db,
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
            )

            if not analytics:
                raise ValidationException("Insufficient historical data for prediction")

            # Simple pattern-based prediction
            predictions = self._analyze_failure_patterns(
                analytics,
                lookahead_days
            )

            return {
                "hostel_id": str(hostel_id),
                "analysis_period_days": lookback_days,
                "prediction_period_days": lookahead_days,
                "predictions": predictions,
                "confidence_level": "medium",  # Rule-based has medium confidence
                "recommendations": self._generate_failure_prevention_actions(predictions),
                "predicted_at": datetime.utcnow().isoformat(),
            }

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error predicting equipment failures: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to predict equipment failures: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Schedule Optimization
    # -------------------------------------------------------------------------

    def optimize_maintenance_schedule(
        self,
        db: Session,
        hostel_id: UUID,
    ) -> Dict[str, Any]:
        """
        Analyze current maintenance patterns and suggest schedule optimizations.

        Args:
            db: Database session
            hostel_id: UUID of the hostel

        Returns:
            Dictionary with schedule optimization suggestions
        """
        if not hostel_id:
            raise ValidationException("Hostel ID is required")

        try:
            # Analyze last 90 days
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=90)

            analytics = self.analytics_repo.get_analytics_for_hostel(
                db=db,
                hostel_id=hostel_id,
                start_date=start_date,
                end_date=end_date,
            )

            if not analytics:
                raise ValidationException("Insufficient data for schedule optimization")

            # Generate optimization suggestions
            optimizations = []

            # Check workload distribution
            if analytics.get("peak_request_day"):
                optimizations.append({
                    "type": "workload_balancing",
                    "finding": f"Peak requests on {analytics['peak_request_day']}",
                    "suggestion": "Schedule preventive maintenance on low-volume days",
                    "impact": "Reduce peak day overload by 20-30%",
                })

            # Check average resolution time
            avg_resolution = analytics.get("avg_completion_time_hours", 0)
            if avg_resolution > 48:
                optimizations.append({
                    "type": "efficiency_improvement",
                    "finding": f"Average resolution time: {avg_resolution:.1f} hours",
                    "suggestion": "Implement predictive parts stocking and staff scheduling",
                    "impact": "Reduce resolution time by 30-40%",
                })

            # Check backlog
            open_requests = analytics.get("open_requests", 0)
            if open_requests > 30:
                optimizations.append({
                    "type": "capacity_planning",
                    "finding": f"{open_requests} open requests in backlog",
                    "suggestion": "Increase staff capacity or vendor partnerships",
                    "impact": "Clear backlog within 2-3 weeks",
                })

            return {
                "hostel_id": str(hostel_id),
                "analysis_period": "last_90_days",
                "total_optimizations": len(optimizations),
                "optimizations": optimizations,
                "estimated_cost_savings": self._estimate_optimization_savings(
                    optimizations,
                    analytics
                ),
                "generated_at": datetime.utcnow().isoformat(),
            }

        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Error optimizing schedule: {str(e)}",
                exc_info=True
            )
            raise BusinessLogicException(
                f"Failed to optimize maintenance schedule: {str(e)}"
            )

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _validate_date_range(self, period: DateRangeFilter) -> None:
        """Validate date range parameters."""
        if not period.start_date or not period.end_date:
            raise ValidationException("Both start_date and end_date are required")

        if period.start_date > period.end_date:
            raise ValidationException("start_date must be before or equal to end_date")

    def _calculate_risk_factors(self, analytics: Dict[str, Any]) -> Dict[str, float]:
        """Calculate individual risk factors from analytics."""
        factors = {}

        # Completion time factor (normalize to 0-100)
        avg_completion = analytics.get("avg_completion_time_hours", 0)
        factors["avg_completion_time"] = min((avg_completion / 72) * 100, 100)

        # Overdue rate factor
        total_requests = analytics.get("total_requests", 1)
        overdue_requests = analytics.get("overdue_requests", 0)
        factors["overdue_rate"] = (overdue_requests / total_requests) * 100

        # Backlog size factor
        open_requests = analytics.get("open_requests", 0)
        factors["backlog_size"] = min((open_requests / 50) * 100, 100)

        # Cost trend factor (simplified)
        total_cost = analytics.get("total_cost", 0)
        factors["cost_trend"] = min((total_cost / 50000) * 100, 100)

        # Failure frequency (recurring issues)
        # Placeholder - would need more detailed data
        factors["failure_frequency"] = 0

        return factors

    def _calculate_risk_score(self, risk_factors: Dict[str, float]) -> float:
        """Calculate weighted overall risk score."""
        score = 0.0
        for factor, value in risk_factors.items():
            weight = self.RISK_WEIGHTS.get(factor, 0)
            score += value * weight
        return score

    def _determine_risk_level(self, risk_score: float) -> str:
        """Determine risk level from score."""
        if risk_score >= self.RISK_THRESHOLDS["critical"]:
            return "critical"
        elif risk_score >= self.RISK_THRESHOLDS["high"]:
            return "high"
        elif risk_score >= self.RISK_THRESHOLDS["medium"]:
            return "medium"
        else:
            return "low"

    def _identify_risk_reasons(
        self,
        risk_factors: Dict[str, float]
    ) -> List[str]:
        """Identify main contributors to risk."""
        reasons = []

        if risk_factors.get("avg_completion_time", 0) > 50:
            reasons.append("slow_completion_times")

        if risk_factors.get("overdue_rate", 0) > 20:
            reasons.append("many_overdue_requests")

        if risk_factors.get("backlog_size", 0) > 40:
            reasons.append("large_backlog")

        if risk_factors.get("cost_trend", 0) > 60:
            reasons.append("increasing_costs")

        if not reasons:
            reasons.append("low_risk_profile")

        return reasons

    def _generate_risk_recommendations(
        self,
        risk_level: str,
        risk_factors: Dict[str, float]
    ) -> List[str]:
        """Generate recommendations based on risk level."""
        recommendations = []

        if risk_level in ["critical", "high"]:
            recommendations.append("Conduct immediate capacity assessment")
            recommendations.append("Review and optimize staff allocation")

        if risk_factors.get("overdue_rate", 0) > 20:
            recommendations.append("Prioritize and expedite overdue requests")

        if risk_factors.get("avg_completion_time", 0) > 50:
            recommendations.append("Implement preventive maintenance schedules")
            recommendations.append("Review vendor response times")

        if risk_factors.get("backlog_size", 0) > 40:
            recommendations.append("Consider temporary staff augmentation")

        if not recommendations:
            recommendations.append("Maintain current operational practices")

        return recommendations

    def _calculate_category_risk(self, category_data: Dict[str, Any]) -> float:
        """Calculate risk score for a specific category."""
        total_requests = category_data.get("total_requests", 0)
        avg_resolution = category_data.get("avg_resolution_hours", 0)
        
        # Simple heuristic
        volume_score = min((total_requests / 30) * 50, 50)
        time_score = min((avg_resolution / 48) * 50, 50)
        
        return volume_score + time_score

    def _generate_category_recommendations(
        self,
        category: str,
        category_data: Dict[str, Any],
        risk_level: str,
    ) -> List[str]:
        """Generate category-specific recommendations."""
        recommendations = []

        if risk_level in ["critical", "high"]:
            recommendations.append(f"Increase focus on {category} maintenance")
            recommendations.append("Review vendor capabilities for this category")

        total_requests = category_data.get("total_requests", 0)
        if total_requests > 20:
            recommendations.append("Implement preventive checks to reduce volume")

        return recommendations

    def _generate_recommendation_summary(
        self,
        recommendations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate summary of recommendations."""
        high_priority = sum(1 for r in recommendations if r.get("priority") == "high")
        medium_priority = sum(1 for r in recommendations if r.get("priority") == "medium")
        
        return {
            "high_priority_count": high_priority,
            "medium_priority_count": medium_priority,
            "total_count": len(recommendations),
            "key_focus_areas": [
                r.get("category") for r in recommendations[:3]
            ],
        }

    def _analyze_failure_patterns(
        self,
        analytics: Dict[str, Any],
        lookahead_days: int,
    ) -> List[Dict[str, Any]]:
        """Analyze patterns to predict failures."""
        # Simplified pattern analysis
        # In production, this would use ML models
        
        predictions = []
        
        avg_completion = analytics.get("avg_completion_time_hours", 0)
        if avg_completion > 48:
            predictions.append({
                "equipment_type": "HVAC_systems",
                "probability": "medium",
                "predicted_timeframe": f"next_{lookahead_days}_days",
                "reasoning": "Increasing resolution times suggest degrading equipment",
            })

        return predictions

    def _generate_failure_prevention_actions(
        self,
        predictions: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate actions to prevent predicted failures."""
        actions = []
        
        for pred in predictions:
            actions.append(
                f"Schedule inspection of {pred.get('equipment_type')}"
            )
        
        if not actions:
            actions.append("Continue monitoring maintenance patterns")
        
        return actions

    def _estimate_optimization_savings(
        self,
        optimizations: List[Dict[str, Any]],
        analytics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Estimate cost savings from optimizations."""
        total_cost = analytics.get("total_cost", 0)
        
        # Conservative estimate: 15% savings
        estimated_savings = total_cost * 0.15
        
        return {
            "current_period_cost": total_cost,
            "estimated_monthly_savings": estimated_savings / 3,  # Assuming 90-day period
            "estimated_annual_savings": estimated_savings * 4,
            "confidence": "medium",
        }