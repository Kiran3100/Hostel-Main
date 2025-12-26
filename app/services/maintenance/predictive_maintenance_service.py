"""
Predictive Maintenance Service

Uses historical analytics to:
- Predict failure/maintenance risk for rooms/assets
- Recommend preventive schedules or priority adjustments
"""

from __future__ import annotations

from typing import Dict, Any, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.maintenance import MaintenanceAnalyticsRepository
from app.schemas.common import DateRangeFilter
from app.core.exceptions import ValidationException


class PredictiveMaintenanceService:
    """
    High-level, rule-based predictive maintenance service.

    This can later be replaced or augmented with an ML model.
    """

    def __init__(self, analytics_repo: MaintenanceAnalyticsRepository) -> None:
        self.analytics_repo = analytics_repo

    def get_risk_assessment_for_hostel(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Dict[str, Any]:
        """
        Build a simple risk assessment for maintenance across categories.
        """
        analytics = self.analytics_repo.get_analytics_for_hostel(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not analytics:
            raise ValidationException("No maintenance analytics available")

        # Basic heuristic:
        # - Higher average time to complete + high open backlog => higher risk
        avg_completion_time = analytics.get("avg_completion_time_hours", 0.0)
        open_requests = analytics.get("open_requests", 0)
        overdue_requests = analytics.get("overdue_requests", 0)

        risk_score = 0
        reasons: list[str] = []

        if avg_completion_time > 48:  # >2 days
            risk_score += 30
            reasons.append("slow_completion")
        if overdue_requests > 10:
            risk_score += 40
            reasons.append("many_overdue_requests")
        if open_requests > 30:
            risk_score += 30
            reasons.append("large_backlog")

        level = "low"
        if risk_score >= 80:
            level = "critical"
        elif risk_score >= 60:
            level = "high"
        elif risk_score >= 40:
            level = "medium"

        return {
            "hostel_id": str(hostel_id),
            "period_start": period.start_date.isoformat(),
            "period_end": period.end_date.isoformat(),
            "risk_score": risk_score,
            "risk_level": level,
            "reasons": reasons,
        }

    def recommend_preventive_actions(
        self,
        db: Session,
        hostel_id: UUID,
        period: DateRangeFilter,
    ) -> Dict[str, Any]:
        """
        Suggest simple preventive measures based on category breakdown.
        """
        breakdown = self.analytics_repo.get_category_breakdown(
            db=db,
            hostel_id=hostel_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not breakdown:
            raise ValidationException("No category breakdown available")

        categories = breakdown.get("categories", [])
        recommendations: list[dict[str, Any]] = []

        for cat in categories:
            # Example heuristic: if a category has high count and long avg resolution,
            # recommend more preventive checks/focus.
            if cat.get("total_requests", 0) >= 10 and cat.get("avg_resolution_hours", 0) > 24:
                recommendations.append(
                    {
                        "category": cat.get("category"),
                        "reason": "high_volume_and_slow_resolution",
                        "recommended_actions": [
                            "increase_preventive_checks",
                            "review_vendor_or_staff_capacity",
                            "stock_critical_spares",
                        ],
                    }
                )

        return {
            "hostel_id": str(hostel_id),
            "period_start": period.start_date.isoformat(),
            "period_end": period.end_date.isoformat(),
            "recommendations": recommendations,
        }