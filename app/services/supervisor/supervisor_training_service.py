"""
Supervisor Training Service

Suggests training/improvement plans based on performance data with ML-ready analytics.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.supervisor import SupervisorPerformanceRepository
from app.schemas.common import DateRangeFilter
from app.core1.exceptions import ValidationException

logger = logging.getLogger(__name__)


class SupervisorTrainingService:
    """
    Higher-level, non-persistent service that uses performance data
    to suggest training modules or improvement plans.

    Does not currently persist training records; that can be added later
    by introducing dedicated training models + repositories.

    Responsibilities:
    - Analyze performance data
    - Generate training recommendations
    - Create learning paths
    - Track skill gaps
    - Suggest courses and modules

    Example:
        >>> service = SupervisorTrainingService(performance_repo)
        >>> recommendations = service.get_training_recommendations(
        ...     db, supervisor_id, period
        ... )
    """

    # Training priority thresholds
    HIGH_PRIORITY_THRESHOLD = 60
    MEDIUM_PRIORITY_THRESHOLD = 75

    def __init__(
        self,
        performance_repo: SupervisorPerformanceRepository,
    ) -> None:
        """
        Initialize the supervisor training service.

        Args:
            performance_repo: Repository for performance operations
        """
        if not performance_repo:
            raise ValueError("performance_repo cannot be None")
            
        self.performance_repo = performance_repo

    # -------------------------------------------------------------------------
    # Training Recommendations
    # -------------------------------------------------------------------------

    def get_training_recommendations(
        self,
        db: Session,
        supervisor_id: UUID,
        period: DateRangeFilter,
    ) -> Dict[str, Any]:
        """
        Generate a rule-based training recommendation set based on performance metrics.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            period: Date range filter for performance analysis

        Returns:
            Dict[str, Any]: Training recommendations with modules and priorities

        Raises:
            ValidationException: If validation fails or no metrics available

        Example:
            >>> period = DateRangeFilter(
            ...     start_date=datetime(2024, 1, 1).date(),
            ...     end_date=datetime(2024, 1, 31).date()
            ... )
            >>> recommendations = service.get_training_recommendations(
            ...     db, supervisor_id, period
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")
        
        if not period:
            raise ValidationException("Period filter is required")
        
        if not period.start_date or not period.end_date:
            raise ValidationException("Both start_date and end_date are required")

        try:
            logger.info(
                f"Generating training recommendations for supervisor: {supervisor_id}, "
                f"period: {period.start_date} to {period.end_date}"
            )
            
            metrics = self.performance_repo.get_metrics(
                db=db,
                supervisor_id=supervisor_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            
            if not metrics:
                logger.warning(
                    f"No performance metrics available for supervisor: {supervisor_id}"
                )
                raise ValidationException(
                    f"No performance metrics available for supervisor {supervisor_id}"
                )
            
            recommendations = self._analyze_performance_and_recommend(metrics)
            
            result = {
                "supervisor_id": str(supervisor_id),
                "period_start": period.start_date.isoformat(),
                "period_end": period.end_date.isoformat(),
                "analysis_date": datetime.utcnow().isoformat(),
                "overall_performance_score": self._calculate_overall_score(metrics),
                "recommendations": recommendations,
                "total_recommendations": len(recommendations),
                "high_priority_count": sum(
                    1 for r in recommendations if r["priority"] == "high"
                ),
                "medium_priority_count": sum(
                    1 for r in recommendations if r["priority"] == "medium"
                ),
                "low_priority_count": sum(
                    1 for r in recommendations if r["priority"] == "low"
                ),
            }
            
            logger.info(
                f"Generated {len(recommendations)} training recommendations "
                f"for supervisor: {supervisor_id}"
            )
            return result
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(
                f"Failed to generate training recommendations for {supervisor_id}: {str(e)}"
            )
            raise ValidationException(
                f"Failed to generate training recommendations: {str(e)}"
            )

    def _analyze_performance_and_recommend(
        self,
        metrics: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Analyze performance metrics and generate recommendations.

        Args:
            metrics: Performance metrics dictionary

        Returns:
            List[Dict[str, Any]]: List of training recommendations
        """
        recommendations: List[Dict[str, Any]] = []
        
        # Complaint handling analysis
        complaint_score = metrics.get("complaint_resolution_score", 100)
        if complaint_score < self.HIGH_PRIORITY_THRESHOLD:
            recommendations.append({
                "area": "Complaint Handling",
                "current_score": complaint_score,
                "target_score": 85,
                "modules": [
                    {
                        "name": "Effective Complaint Resolution Techniques",
                        "duration_hours": 4,
                        "type": "workshop",
                    },
                    {
                        "name": "SLA Management & Prioritization",
                        "duration_hours": 3,
                        "type": "online_course",
                    },
                    {
                        "name": "Customer Service Excellence",
                        "duration_hours": 6,
                        "type": "certification",
                    },
                ],
                "priority": "high",
                "estimated_improvement": 15,
            })
        elif complaint_score < self.MEDIUM_PRIORITY_THRESHOLD:
            recommendations.append({
                "area": "Complaint Handling",
                "current_score": complaint_score,
                "target_score": 85,
                "modules": [
                    {
                        "name": "Advanced Complaint Resolution",
                        "duration_hours": 2,
                        "type": "webinar",
                    },
                ],
                "priority": "medium",
                "estimated_improvement": 10,
            })
        
        # Attendance management analysis
        attendance_score = metrics.get("attendance_score", 100)
        if attendance_score < self.HIGH_PRIORITY_THRESHOLD:
            recommendations.append({
                "area": "Attendance Management",
                "current_score": attendance_score,
                "target_score": 90,
                "modules": [
                    {
                        "name": "Attendance Policy & Fairness",
                        "duration_hours": 3,
                        "type": "workshop",
                    },
                    {
                        "name": "Using Attendance Tools Effectively",
                        "duration_hours": 2,
                        "type": "hands_on_training",
                    },
                ],
                "priority": "high",
                "estimated_improvement": 20,
            })
        elif attendance_score < self.MEDIUM_PRIORITY_THRESHOLD:
            recommendations.append({
                "area": "Attendance Management",
                "current_score": attendance_score,
                "target_score": 90,
                "modules": [
                    {
                        "name": "Attendance Best Practices",
                        "duration_hours": 1.5,
                        "type": "online_course",
                    },
                ],
                "priority": "medium",
                "estimated_improvement": 12,
            })
        
        # Maintenance coordination analysis
        maintenance_score = metrics.get("maintenance_score", 100)
        if maintenance_score < self.HIGH_PRIORITY_THRESHOLD:
            recommendations.append({
                "area": "Maintenance Coordination",
                "current_score": maintenance_score,
                "target_score": 85,
                "modules": [
                    {
                        "name": "Preventive Maintenance Planning",
                        "duration_hours": 4,
                        "type": "workshop",
                    },
                    {
                        "name": "Vendor Coordination & Follow-up",
                        "duration_hours": 3,
                        "type": "workshop",
                    },
                    {
                        "name": "Facilities Management Fundamentals",
                        "duration_hours": 8,
                        "type": "certification",
                    },
                ],
                "priority": "high",
                "estimated_improvement": 18,
            })
        elif maintenance_score < self.MEDIUM_PRIORITY_THRESHOLD:
            recommendations.append({
                "area": "Maintenance Coordination",
                "current_score": maintenance_score,
                "target_score": 85,
                "modules": [
                    {
                        "name": "Maintenance Optimization Strategies",
                        "duration_hours": 2,
                        "type": "webinar",
                    },
                ],
                "priority": "medium",
                "estimated_improvement": 10,
            })
        
        # Communication & leadership analysis
        communication_score = metrics.get("communication_score", 100)
        if communication_score < self.HIGH_PRIORITY_THRESHOLD:
            recommendations.append({
                "area": "Communication & Leadership",
                "current_score": communication_score,
                "target_score": 88,
                "modules": [
                    {
                        "name": "Conflict Resolution",
                        "duration_hours": 4,
                        "type": "workshop",
                    },
                    {
                        "name": "Team Communication Best Practices",
                        "duration_hours": 3,
                        "type": "workshop",
                    },
                    {
                        "name": "Leadership Essentials",
                        "duration_hours": 12,
                        "type": "certification",
                    },
                ],
                "priority": "high",
                "estimated_improvement": 20,
            })
        elif communication_score < self.MEDIUM_PRIORITY_THRESHOLD:
            recommendations.append({
                "area": "Communication & Leadership",
                "current_score": communication_score,
                "target_score": 88,
                "modules": [
                    {
                        "name": "Effective Communication Skills",
                        "duration_hours": 2,
                        "type": "online_course",
                    },
                ],
                "priority": "medium",
                "estimated_improvement": 12,
            })
        
        # If no critical areas, suggest advanced training
        if not recommendations:
            recommendations.append({
                "area": "Advanced Leadership",
                "current_score": self._calculate_overall_score(metrics),
                "target_score": 95,
                "modules": [
                    {
                        "name": "Coaching & Mentoring",
                        "duration_hours": 6,
                        "type": "workshop",
                    },
                    {
                        "name": "Data-Driven Decision Making",
                        "duration_hours": 4,
                        "type": "online_course",
                    },
                    {
                        "name": "Strategic Management",
                        "duration_hours": 8,
                        "type": "certification",
                    },
                ],
                "priority": "low",
                "estimated_improvement": 5,
            })
        
        return recommendations

    def _calculate_overall_score(self, metrics: Dict[str, Any]) -> float:
        """
        Calculate overall performance score from metrics.

        Args:
            metrics: Performance metrics dictionary

        Returns:
            float: Overall score (0-100)
        """
        weights = {
            "complaint_resolution_score": 0.3,
            "attendance_score": 0.2,
            "maintenance_score": 0.2,
            "communication_score": 0.15,
            "leadership_score": 0.15,
        }
        
        total_score = 0.0
        total_weight = 0.0
        
        for metric_key, weight in weights.items():
            if metric_key in metrics and metrics[metric_key] is not None:
                total_score += metrics[metric_key] * weight
                total_weight += weight
        
        if total_weight > 0:
            return round(total_score / total_weight, 2)
        return 0.0

    # -------------------------------------------------------------------------
    # Learning Path Generation
    # -------------------------------------------------------------------------

    def generate_learning_path(
        self,
        db: Session,
        supervisor_id: UUID,
        period: DateRangeFilter,
        target_score: float = 85.0,
    ) -> Dict[str, Any]:
        """
        Generate a personalized learning path to achieve target performance.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            period: Date range filter for analysis
            target_score: Target overall performance score

        Returns:
            Dict[str, Any]: Learning path with milestones and timeline

        Raises:
            ValidationException: If validation fails

        Example:
            >>> path = service.generate_learning_path(
            ...     db, supervisor_id, period, target_score=90.0
            ... )
        """
        if not db:
            raise ValidationException("Database session is required")
        
        if not supervisor_id:
            raise ValidationException("Supervisor ID is required")
        
        if target_score < 0 or target_score > 100:
            raise ValidationException("Target score must be between 0 and 100")

        try:
            logger.info(
                f"Generating learning path for supervisor: {supervisor_id}, "
                f"target score: {target_score}"
            )
            
            recommendations = self.get_training_recommendations(db, supervisor_id, period)
            
            current_score = recommendations["overall_performance_score"]
            gap = max(0, target_score - current_score)
            
            # Sort recommendations by priority
            sorted_recommendations = sorted(
                recommendations["recommendations"],
                key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["priority"]]
            )
            
            # Build learning path
            learning_path = {
                "supervisor_id": str(supervisor_id),
                "current_score": current_score,
                "target_score": target_score,
                "score_gap": gap,
                "estimated_completion_weeks": self._estimate_completion_time(
                    sorted_recommendations
                ),
                "milestones": self._create_milestones(
                    sorted_recommendations, current_score, target_score
                ),
                "total_training_hours": self._calculate_total_hours(
                    sorted_recommendations
                ),
            }
            
            logger.info(
                f"Generated learning path for supervisor: {supervisor_id}, "
                f"estimated completion: {learning_path['estimated_completion_weeks']} weeks"
            )
            return learning_path
            
        except ValidationException:
            raise
        except Exception as e:
            logger.error(f"Failed to generate learning path: {str(e)}")
            raise ValidationException(f"Failed to generate learning path: {str(e)}")

    def _estimate_completion_time(
        self,
        recommendations: List[Dict[str, Any]],
    ) -> int:
        """
        Estimate completion time in weeks.

        Args:
            recommendations: List of training recommendations

        Returns:
            int: Estimated weeks to complete
        """
        total_hours = self._calculate_total_hours(recommendations)
        # Assuming 4 hours per week for training
        hours_per_week = 4
        return max(1, int(total_hours / hours_per_week))

    def _calculate_total_hours(
        self,
        recommendations: List[Dict[str, Any]],
    ) -> float:
        """
        Calculate total training hours.

        Args:
            recommendations: List of training recommendations

        Returns:
            float: Total hours
        """
        total_hours = 0.0
        for rec in recommendations:
            for module in rec.get("modules", []):
                total_hours += module.get("duration_hours", 0)
        return total_hours

    def _create_milestones(
        self,
        recommendations: List[Dict[str, Any]],
        current_score: float,
        target_score: float,
    ) -> List[Dict[str, Any]]:
        """
        Create learning milestones.

        Args:
            recommendations: List of training recommendations
            current_score: Current performance score
            target_score: Target performance score

        Returns:
            List[Dict[str, Any]]: List of milestones
        """
        milestones = []
        accumulated_improvement = 0.0
        week_counter = 0
        
        for rec in recommendations:
            improvement = rec.get("estimated_improvement", 0)
            accumulated_improvement += improvement
            week_counter += 2  # Assume 2 weeks per training area
            
            new_score = min(target_score, current_score + accumulated_improvement)
            
            milestones.append({
                "week": week_counter,
                "area": rec["area"],
                "modules_completed": len(rec.get("modules", [])),
                "expected_score": round(new_score, 2),
                "improvement_from_previous": improvement,
            })
        
        return milestones

    # -------------------------------------------------------------------------
    # Skill Gap Analysis
    # -------------------------------------------------------------------------

    def analyze_skill_gaps(
        self,
        db: Session,
        supervisor_id: UUID,
        period: DateRangeFilter,
    ) -> Dict[str, Any]:
        """
        Analyze skill gaps for a supervisor.

        Args:
            db: Database session
            supervisor_id: UUID of the supervisor
            period: Date range filter

        Returns:
            Dict[str, Any]: Skill gap analysis

        Example:
            >>> gaps = service.analyze_skill_gaps(db, supervisor_id, period)
        """
        if not db or not supervisor_id or not period:
            raise ValidationException("Required parameters missing")

        try:
            logger.info(f"Analyzing skill gaps for supervisor: {supervisor_id}")
            
            metrics = self.performance_repo.get_metrics(
                db=db,
                supervisor_id=supervisor_id,
                start_date=period.start_date,
                end_date=period.end_date,
            )
            
            if not metrics:
                raise ValidationException("No performance metrics available")
            
            skill_areas = {
                "complaint_handling": metrics.get("complaint_resolution_score", 0),
                "attendance_management": metrics.get("attendance_score", 0),
                "maintenance_coordination": metrics.get("maintenance_score", 0),
                "communication": metrics.get("communication_score", 0),
                "leadership": metrics.get("leadership_score", 0),
            }
            
            gaps = []
            for skill, score in skill_areas.items():
                if score < 85:  # Benchmark score
                    gaps.append({
                        "skill_area": skill,
                        "current_level": score,
                        "target_level": 85,
                        "gap_percentage": 85 - score,
                        "severity": self._calculate_gap_severity(score),
                    })
            
            # Sort by severity
            gaps.sort(key=lambda x: x["gap_percentage"], reverse=True)
            
            return {
                "supervisor_id": str(supervisor_id),
                "analysis_date": datetime.utcnow().isoformat(),
                "skill_gaps": gaps,
                "total_gaps": len(gaps),
                "critical_gaps": sum(1 for g in gaps if g["severity"] == "critical"),
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze skill gaps: {str(e)}")
            raise ValidationException(f"Failed to analyze skill gaps: {str(e)}")

    def _calculate_gap_severity(self, score: float) -> str:
        """
        Calculate gap severity based on score.

        Args:
            score: Performance score

        Returns:
            str: Severity level
        """
        if score < 60:
            return "critical"
        elif score < 75:
            return "high"
        elif score < 85:
            return "medium"
        return "low"