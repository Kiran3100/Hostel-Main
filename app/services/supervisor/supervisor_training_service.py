"""
Supervisor Training Service

Suggests training/improvement plans based on performance data.
"""

from __future__ import annotations

from typing import Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.supervisor import SupervisorPerformanceRepository
from app.schemas.common import DateRangeFilter
from app.core.exceptions import ValidationException


class SupervisorTrainingService:
    """
    Higher-level, non-persistent service that uses performance data
    to suggest training modules or improvement plans.

    Does not currently persist training records; that can be added later
    by introducing dedicated training models + repositories.
    """

    def __init__(
        self,
        performance_repo: SupervisorPerformanceRepository,
    ) -> None:
        self.performance_repo = performance_repo

    def get_training_recommendations(
        self,
        db: Session,
        supervisor_id: UUID,
        period: DateRangeFilter,
    ) -> Dict[str, Any]:
        """
        Generate a simple rule-based training recommendation set
        based on performance metrics.
        """
        metrics = self.performance_repo.get_metrics(
            db=db,
            supervisor_id=supervisor_id,
            start_date=period.start_date,
            end_date=period.end_date,
        )
        if not metrics:
            raise ValidationException("No performance metrics available")

        # Very simplified heuristic examples:
        complaint_score = metrics.get("complaint_resolution_score", 0)
        attendance_score = metrics.get("attendance_score", 0)
        maintenance_score = metrics.get("maintenance_score", 0)
        communication_score = metrics.get("communication_score", 0)

        recommendations: list[Dict[str, Any]] = []

        if complaint_score < 70:
            recommendations.append(
                {
                    "area": "Complaint Handling",
                    "modules": [
                        "Effective Complaint Resolution Techniques",
                        "SLA Management & Prioritization",
                    ],
                    "priority": "high",
                }
            )

        if attendance_score < 70:
            recommendations.append(
                {
                    "area": "Attendance Management",
                    "modules": [
                        "Attendance Policy & Fairness",
                        "Using Attendance Tools Effectively",
                    ],
                    "priority": "medium",
                }
            )

        if maintenance_score < 70:
            recommendations.append(
                {
                    "area": "Maintenance Coordination",
                    "modules": [
                        "Preventive Maintenance Planning",
                        "Vendor Coordination & Follow-up",
                    ],
                    "priority": "medium",
                }
            )

        if communication_score < 70:
            recommendations.append(
                {
                    "area": "Communication & Leadership",
                    "modules": [
                        "Conflict Resolution",
                        "Team Communication Best Practices",
                    ],
                    "priority": "high",
                }
            )

        if not recommendations:
            recommendations.append(
                {
                    "area": "Advanced Leadership",
                    "modules": [
                        "Coaching & Mentoring",
                        "Data-Driven Decision Making",
                    ],
                    "priority": "low",
                }
            )

        return {
            "supervisor_id": str(supervisor_id),
            "period_start": period.start_date.isoformat(),
            "period_end": period.end_date.isoformat(),
            "recommendations": recommendations,
        }