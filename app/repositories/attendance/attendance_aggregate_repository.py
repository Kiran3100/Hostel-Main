# --- File: app/repositories/attendance/attendance_aggregate_repository.py ---
"""
Attendance aggregate repository for complex queries and analytics.

Provides advanced aggregation, cross-entity queries, and comprehensive
analytics operations for attendance data.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, case, distinct, extract
from sqlalchemy.orm import Session, joinedload

from app.models.attendance.attendance_record import AttendanceRecord
from app.models.attendance.attendance_policy import (
    AttendancePolicy,
    PolicyViolation,
    PolicyException,
)
from app.models.attendance.attendance_alert import AttendanceAlert, AlertConfiguration
from app.models.attendance.attendance_report import AttendanceSummary, AttendanceTrend
from app.models.base.enums import AttendanceStatus
from app.repositories.base.base_repository import BaseRepository


class AttendanceAggregateRepository:
    """
    Repository for attendance aggregate operations and analytics.
    """

    def __init__(self, session: Session):
        """
        Initialize repository with database session.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session

    # ==================== Dashboard Analytics ====================

    def get_hostel_dashboard_data(
        self,
        hostel_id: UUID,
        reference_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data for hostel.

        Args:
            hostel_id: Hostel identifier
            reference_date: Reference date (defaults to today)

        Returns:
            Dictionary with dashboard metrics
        """
        if reference_date is None:
            reference_date = date.today()

        # Today's attendance
        today_records = self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.hostel_id == hostel_id,
                AttendanceRecord.attendance_date == reference_date,
            )
        ).all()

        total_marked = len(today_records)
        present_today = sum(1 for r in today_records if r.status == AttendanceStatus.PRESENT)
        absent_today = sum(1 for r in today_records if r.status == AttendanceStatus.ABSENT)
        late_today = sum(1 for r in today_records if r.is_late)

        # This month's statistics
        month_start = reference_date.replace(day=1)
        month_end = reference_date

        month_records = self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.hostel_id == hostel_id,
                AttendanceRecord.attendance_date >= month_start,
                AttendanceRecord.attendance_date <= month_end,
            )
        ).all()

        # Calculate monthly average
        monthly_avg = 0.0
        if month_records:
            present_count = sum(1 for r in month_records if r.status == AttendanceStatus.PRESENT)
            monthly_avg = (present_count / len(month_records)) * 100

        # Active alerts
        active_alerts = self.session.query(AttendanceAlert).filter(
            and_(
                AttendanceAlert.hostel_id == hostel_id,
                AttendanceAlert.resolved == False,
            )
        ).count()

        critical_alerts = self.session.query(AttendanceAlert).filter(
            and_(
                AttendanceAlert.hostel_id == hostel_id,
                AttendanceAlert.severity == "critical",
                AttendanceAlert.resolved == False,
            )
        ).count()

        # Unresolved violations
        unresolved_violations = self.session.query(PolicyViolation).join(
            AttendancePolicy
        ).filter(
            and_(
                AttendancePolicy.hostel_id == hostel_id,
                PolicyViolation.resolved == False,
            )
        ).count()

        return {
            "today": {
                "date": reference_date,
                "total_marked": total_marked,
                "present": present_today,
                "absent": absent_today,
                "late": late_today,
                "attendance_percentage": round(
                    (present_today / total_marked * 100) if total_marked > 0 else 0,
                    2,
                ),
            },
            "this_month": {
                "period_start": month_start,
                "period_end": month_end,
                "average_attendance": round(monthly_avg, 2),
                "total_records": len(month_records),
            },
            "alerts": {
                "active": active_alerts,
                "critical": critical_alerts,
            },
            "violations": {
                "unresolved": unresolved_violations,
            },
        }

    def get_student_dashboard_data(
        self,
        student_id: UUID,
        reference_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data for student.

        Args:
            student_id: Student identifier
            reference_date: Reference date (defaults to today)

        Returns:
            Dictionary with student metrics
        """
        if reference_date is None:
            reference_date = date.today()

        # Current month summary
        month_start = reference_date.replace(day=1)
        
        summary = self.session.query(AttendanceSummary).filter(
            and_(
                AttendanceSummary.student_id == student_id,
                AttendanceSummary.period_type == "monthly",
                AttendanceSummary.period_start == month_start,
            )
        ).first()

        # Recent attendance (last 7 days)
        week_ago = reference_date - timedelta(days=6)
        recent_records = self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.attendance_date >= week_ago,
                AttendanceRecord.attendance_date <= reference_date,
            )
        ).order_by(AttendanceRecord.attendance_date.desc()).all()

        # Active alerts for student
        active_alerts = self.session.query(AttendanceAlert).filter(
            and_(
                AttendanceAlert.student_id == student_id,
                AttendanceAlert.resolved == False,
            )
        ).count()

        # Active policy exceptions
        active_exceptions = self.session.query(PolicyException).filter(
            and_(
                PolicyException.student_id == student_id,
                PolicyException.is_active == True,
                PolicyException.is_approved == True,
                PolicyException.revoked == False,
                PolicyException.valid_from <= reference_date,
                PolicyException.valid_until >= reference_date,
            )
        ).count()

        summary_data = {}
        if summary:
            summary_data = {
                "attendance_percentage": float(summary.attendance_percentage),
                "total_present": summary.total_present,
                "total_absent": summary.total_absent,
                "total_late": summary.total_late,
                "current_streak": summary.current_present_streak,
                "status": summary.attendance_status,
                "meets_requirement": summary.meets_minimum_requirement,
            }

        return {
            "current_month": summary_data,
            "recent_attendance": [
                {
                    "date": r.attendance_date,
                    "status": r.status.value,
                    "is_late": r.is_late,
                    "late_minutes": r.late_minutes,
                }
                for r in recent_records
            ],
            "alerts": {
                "active": active_alerts,
            },
            "exceptions": {
                "active": active_exceptions,
            },
        }

    # ==================== Attendance Patterns ====================

    def analyze_weekly_pattern(
        self,
        student_id: UUID,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Analyze attendance pattern by day of week.

        Args:
            student_id: Student identifier
            start_date: Analysis start date
            end_date: Analysis end date

        Returns:
            Dictionary with weekly pattern analysis
        """
        records = self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.attendance_date >= start_date,
                AttendanceRecord.attendance_date <= end_date,
            )
        ).all()

        # Group by day of week (0=Monday, 6=Sunday)
        day_stats = {i: {"total": 0, "present": 0, "absent": 0, "late": 0} for i in range(7)}
        
        for record in records:
            day_of_week = record.attendance_date.weekday()
            day_stats[day_of_week]["total"] += 1
            
            if record.status == AttendanceStatus.PRESENT:
                day_stats[day_of_week]["present"] += 1
            elif record.status == AttendanceStatus.ABSENT:
                day_stats[day_of_week]["absent"] += 1
            
            if record.is_late:
                day_stats[day_of_week]["late"] += 1

        # Calculate percentages
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        pattern = {}
        
        for day, stats in day_stats.items():
            if stats["total"] > 0:
                pattern[day_names[day]] = {
                    "total_days": stats["total"],
                    "attendance_rate": round((stats["present"] / stats["total"]) * 100, 2),
                    "late_rate": round((stats["late"] / stats["total"]) * 100, 2),
                    "most_problematic": stats["absent"] > stats["total"] * 0.3,
                }
            else:
                pattern[day_names[day]] = {
                    "total_days": 0,
                    "attendance_rate": 0,
                    "late_rate": 0,
                    "most_problematic": False,
                }

        return pattern

    def detect_absence_patterns(
        self,
        hostel_id: UUID,
        lookback_days: int = 90,
    ) -> List[Dict[str, Any]]:
        """
        Detect patterns in absences across hostel.

        Args:
            hostel_id: Hostel identifier
            lookback_days: Days to look back

        Returns:
            List of detected patterns
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)

        # Get absence records
        absences = self.session.query(
            AttendanceRecord.attendance_date,
            func.count(AttendanceRecord.id).label("absence_count"),
        ).filter(
            and_(
                AttendanceRecord.hostel_id == hostel_id,
                AttendanceRecord.status == AttendanceStatus.ABSENT,
                AttendanceRecord.attendance_date >= start_date,
                AttendanceRecord.attendance_date <= end_date,
            )
        ).group_by(AttendanceRecord.attendance_date).all()

        # Calculate average and threshold
        if not absences:
            return []

        avg_absences = sum(a.absence_count for a in absences) / len(absences)
        threshold = avg_absences * 1.5  # 50% above average

        # Find spike days
        patterns = []
        for absence in absences:
            if absence.absence_count > threshold:
                patterns.append({
                    "date": absence.attendance_date,
                    "day_of_week": absence.attendance_date.strftime("%A"),
                    "absence_count": absence.absence_count,
                    "average": round(avg_absences, 2),
                    "deviation": round(absence.absence_count - avg_absences, 2),
                    "pattern_type": "spike",
                })

        return sorted(patterns, key=lambda x: x["deviation"], reverse=True)

    # ==================== Comparative Analytics ====================

    def compare_student_cohorts(
        self,
        hostel_id: UUID,
        cohort_criteria: Dict[str, Any],
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """
        Compare attendance across student cohorts.

        Args:
            hostel_id: Hostel identifier
            cohort_criteria: Criteria for cohort grouping
            period_start: Period start date
            period_end: Period end date

        Returns:
            Dictionary with cohort comparison
        """
        # This is a simplified example - in practice, you'd join with
        # student table and group by cohort criteria
        
        summaries = self.session.query(AttendanceSummary).filter(
            and_(
                AttendanceSummary.hostel_id == hostel_id,
                AttendanceSummary.period_start == period_start,
                AttendanceSummary.period_end == period_end,
            )
        ).all()

        if not summaries:
            return {}

        # Group by status
        status_groups = {}
        for summary in summaries:
            status = summary.attendance_status
            if status not in status_groups:
                status_groups[status] = []
            status_groups[status].append(summary)

        # Calculate statistics per group
        comparison = {}
        for status, group in status_groups.items():
            avg_attendance = sum(s.attendance_percentage for s in group) / len(group)
            avg_late = sum(s.total_late for s in group) / len(group)
            
            comparison[status] = {
                "count": len(group),
                "average_attendance": float(round(avg_attendance, 2)),
                "average_late_entries": round(avg_late, 2),
                "meets_requirement_count": sum(1 for s in group if s.meets_minimum_requirement),
            }

        return comparison

    def get_trend_comparison(
        self,
        hostel_id: UUID,
        trend_type: str,
        periods: int = 6,
    ) -> List[Dict[str, Any]]:
        """
        Get trend comparison over multiple periods.

        Args:
            hostel_id: Hostel identifier
            trend_type: Trend type
            periods: Number of periods to compare

        Returns:
            List of period comparisons
        """
        trends = self.session.query(AttendanceTrend).filter(
            and_(
                AttendanceTrend.hostel_id == hostel_id,
                AttendanceTrend.trend_type == trend_type,
                AttendanceTrend.student_id.is_(None),
            )
        ).order_by(AttendanceTrend.period_start.desc()).limit(periods).all()

        comparison = []
        for trend in reversed(trends):
            comparison.append({
                "period": trend.period_identifier,
                "start_date": trend.period_start,
                "end_date": trend.period_end,
                "average_attendance": float(trend.average_attendance),
                "trend_direction": trend.trend_direction,
                "change_percentage": float(trend.change_percentage) if trend.change_percentage else 0,
                "average_present": float(trend.average_present),
                "average_absent": float(trend.average_absent),
                "average_late": float(trend.average_late),
                "anomaly_detected": trend.anomaly_detected,
            })

        return comparison

    # ==================== Risk Assessment ====================

    def identify_at_risk_students(
        self,
        hostel_id: UUID,
        risk_threshold: Decimal = Decimal("75.00"),
    ) -> List[Dict[str, Any]]:
        """
        Identify students at risk of failing attendance requirements.

        Args:
            hostel_id: Hostel identifier
            risk_threshold: Attendance percentage threshold

        Returns:
            List of at-risk students with details
        """
        current_month_start = date.today().replace(day=1)

        summaries = self.session.query(AttendanceSummary).filter(
            and_(
                AttendanceSummary.hostel_id == hostel_id,
                AttendanceSummary.period_start == current_month_start,
                AttendanceSummary.attendance_percentage < risk_threshold,
            )
        ).options(joinedload(AttendanceSummary.student)).all()

        at_risk = []
        for summary in summaries:
            # Get recent violations
            violations = self.session.query(PolicyViolation).filter(
                and_(
                    PolicyViolation.student_id == summary.student_id,
                    PolicyViolation.resolved == False,
                )
            ).count()

            # Get active alerts
            alerts = self.session.query(AttendanceAlert).filter(
                and_(
                    AttendanceAlert.student_id == summary.student_id,
                    AttendanceAlert.resolved == False,
                )
            ).count()

            risk_score = self._calculate_risk_score(summary, violations, alerts)

            at_risk.append({
                "student_id": summary.student_id,
                "attendance_percentage": float(summary.attendance_percentage),
                "consecutive_absences": summary.current_absent_streak,
                "total_late": summary.total_late,
                "unresolved_violations": violations,
                "active_alerts": alerts,
                "risk_score": risk_score,
                "risk_level": self._get_risk_level(risk_score),
                "status": summary.attendance_status,
            })

        return sorted(at_risk, key=lambda x: x["risk_score"], reverse=True)

    def _calculate_risk_score(
        self,
        summary: AttendanceSummary,
        violations: int,
        alerts: int,
    ) -> float:
        """Calculate risk score for student."""
        score = 0.0

        # Attendance percentage (0-40 points)
        attendance_score = (100 - float(summary.attendance_percentage)) * 0.4
        score += attendance_score

        # Consecutive absences (0-20 points)
        absence_score = min(summary.current_absent_streak * 5, 20)
        score += absence_score

        # Late entries (0-15 points)
        late_score = min(summary.total_late * 1.5, 15)
        score += late_score

        # Violations (0-15 points)
        violation_score = min(violations * 5, 15)
        score += violation_score

        # Active alerts (0-10 points)
        alert_score = min(alerts * 2.5, 10)
        score += alert_score

        return round(score, 2)

    def _get_risk_level(self, risk_score: float) -> str:
        """Get risk level from risk score."""
        if risk_score >= 70:
            return "critical"
        elif risk_score >= 50:
            return "high"
        elif risk_score >= 30:
            return "medium"
        else:
            return "low"

    # ==================== Performance Metrics ====================

    def get_performance_metrics(
        self,
        hostel_id: UUID,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """
        Get comprehensive performance metrics.

        Args:
            hostel_id: Hostel identifier
            period_start: Period start date
            period_end: Period end date

        Returns:
            Dictionary with performance metrics
        """
        # Overall attendance
        records = self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.hostel_id == hostel_id,
                AttendanceRecord.attendance_date >= period_start,
                AttendanceRecord.attendance_date <= period_end,
            )
        ).all()

        total_records = len(records)
        if total_records == 0:
            return {}

        present_count = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        absent_count = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        late_count = sum(1 for r in records if r.is_late)
        
        # Summaries
        summaries = self.session.query(AttendanceSummary).filter(
            and_(
                AttendanceSummary.hostel_id == hostel_id,
                AttendanceSummary.period_start >= period_start,
                AttendanceSummary.period_end <= period_end,
            )
        ).all()

        avg_percentage = 0.0
        if summaries:
            avg_percentage = sum(s.attendance_percentage for s in summaries) / len(summaries)

        # Policy compliance
        policy = self.session.query(AttendancePolicy).filter(
            AttendancePolicy.hostel_id == hostel_id
        ).first()

        compliance_rate = 0.0
        if policy and summaries:
            compliant = sum(
                1 for s in summaries 
                if s.attendance_percentage >= policy.minimum_attendance_percentage
            )
            compliance_rate = (compliant / len(summaries)) * 100

        return {
            "overall": {
                "total_records": total_records,
                "present_count": present_count,
                "absent_count": absent_count,
                "late_count": late_count,
                "attendance_rate": round((present_count / total_records) * 100, 2),
                "late_rate": round((late_count / total_records) * 100, 2),
            },
            "student_performance": {
                "total_students": len(summaries),
                "average_attendance": float(round(avg_percentage, 2)),
                "compliance_rate": round(compliance_rate, 2),
            },
            "policy": {
                "minimum_required": float(policy.minimum_attendance_percentage) if policy else 0,
                "compliant_students": sum(1 for s in summaries if s.meets_minimum_requirement),
                "non_compliant_students": sum(1 for s in summaries if not s.meets_minimum_requirement),
            },
        }

    # ==================== Forecasting ====================

    def forecast_attendance(
        self,
        student_id: UUID,
        forecast_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Forecast future attendance based on historical patterns.

        Args:
            student_id: Student identifier
            forecast_days: Number of days to forecast

        Returns:
            Dictionary with forecast data
        """
        # Get last 90 days of data
        end_date = date.today()
        start_date = end_date - timedelta(days=90)

        records = self.session.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.attendance_date >= start_date,
                AttendanceRecord.attendance_date <= end_date,
            )
        ).order_by(AttendanceRecord.attendance_date.asc()).all()

        if not records:
            return {
                "forecast_available": False,
                "message": "Insufficient historical data",
            }

        # Simple forecasting based on recent trend
        total_days = len(records)
        present_days = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        current_rate = (present_days / total_days) * 100

        # Calculate trend (last 30 days vs previous 60 days)
        recent_30 = records[-30:] if len(records) >= 30 else records
        previous_60 = records[-90:-30] if len(records) >= 90 else records[:-30]

        recent_rate = (
            sum(1 for r in recent_30 if r.status == AttendanceStatus.PRESENT) / len(recent_30) * 100
        ) if recent_30 else 0

        previous_rate = (
            sum(1 for r in previous_60 if r.status == AttendanceStatus.PRESENT) / len(previous_60) * 100
        ) if previous_60 else 0

        trend = recent_rate - previous_rate

        # Forecast
        forecasted_rate = current_rate + (trend * (forecast_days / 30))
        forecasted_rate = max(0, min(100, forecasted_rate))  # Clamp between 0-100

        confidence = 0.7 if len(records) >= 60 else 0.5

        return {
            "forecast_available": True,
            "current_attendance_rate": round(current_rate, 2),
            "forecasted_attendance_rate": round(forecasted_rate, 2),
            "trend": "improving" if trend > 0 else "declining" if trend < 0 else "stable",
            "trend_magnitude": round(abs(trend), 2),
            "confidence_score": confidence,
            "forecast_period_days": forecast_days,
            "based_on_days": total_days,
        }


