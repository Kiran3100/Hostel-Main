# app/repositories/supervisor/supervisor_performance_repository.py
"""
Supervisor Performance Repository - Performance tracking and evaluation.

Handles comprehensive performance management with reviews, goals,
metrics tracking, and peer comparison for supervisor development.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import and_, or_, func, desc
from sqlalchemy.orm import Session, joinedload

from app.models.supervisor.supervisor_performance import (
    SupervisorPerformance,
    PerformanceReview,
    PerformanceGoal,
    PerformanceMetric,
    PeerComparison,
)
from app.models.supervisor.supervisor import Supervisor
from app.repositories.base.base_repository import BaseRepository
from app.core1.exceptions import (
    ResourceNotFoundError,
    BusinessLogicError,
    ValidationError,
)
from app.core1.logging import logger


class SupervisorPerformanceRepository(BaseRepository[SupervisorPerformance]):
    """
    Supervisor performance repository for tracking and evaluation.
    
    Manages performance records, reviews, goals, metrics,
    and peer comparisons for continuous improvement.
    """
    
    def __init__(self, db: Session):
        """Initialize performance repository."""
        super().__init__(SupervisorPerformance, db)
        self.db = db
    
    # ==================== Performance Records ====================
    
    def create_performance_record(
        self,
        supervisor_id: str,
        hostel_id: str,
        period_start: date,
        period_end: date,
        period_type: str = "monthly",
        **performance_data
    ) -> SupervisorPerformance:
        """
        Create comprehensive performance record.
        
        Args:
            supervisor_id: Supervisor ID
            hostel_id: Hostel ID
            period_start: Performance period start
            period_end: Performance period end
            period_type: Period type (weekly, monthly, quarterly, annual)
            **performance_data: Performance metrics
            
        Returns:
            Created performance record
        """
        try:
            # Check for existing record
            existing = self.db.query(SupervisorPerformance).filter(
                and_(
                    SupervisorPerformance.supervisor_id == supervisor_id,
                    SupervisorPerformance.hostel_id == hostel_id,
                    SupervisorPerformance.period_start == period_start,
                    SupervisorPerformance.period_end == period_end,
                    SupervisorPerformance.period_type == period_type
                )
            ).first()
            
            if existing:
                raise BusinessLogicError(
                    f"Performance record already exists for this period"
                )
            
            # Calculate overall performance score and grade
            score = self._calculate_overall_score(performance_data)
            grade = self._calculate_grade(score)
            
            performance = SupervisorPerformance(
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                period_start=period_start,
                period_end=period_end,
                period_type=period_type,
                overall_performance_score=score,
                performance_grade=grade,
                **performance_data
            )
            
            self.db.add(performance)
            self.db.commit()
            self.db.refresh(performance)
            
            logger.info(
                f"Created performance record for supervisor {supervisor_id} "
                f"({period_type}: {period_start} to {period_end})"
            )
            
            return performance
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating performance record: {str(e)}")
            raise
    
    def update_performance_record(
        self,
        record_id: str,
        performance_data: Dict[str, Any]
    ) -> SupervisorPerformance:
        """Update performance record with new data."""
        record = self.db.query(SupervisorPerformance).filter(
            SupervisorPerformance.id == record_id
        ).first()
        
        if not record:
            raise ResourceNotFoundError(f"Performance record {record_id} not found")
        
        # Update fields
        for key, value in performance_data.items():
            if hasattr(record, key):
                setattr(record, key, value)
        
        # Recalculate overall score and grade
        record.overall_performance_score = self._calculate_overall_score(
            self._get_performance_dict(record)
        )
        record.performance_grade = self._calculate_grade(
            record.overall_performance_score
        )
        
        self.db.commit()
        self.db.refresh(record)
        
        return record
    
    def get_performance_records(
        self,
        supervisor_id: Optional[str] = None,
        hostel_id: Optional[str] = None,
        period_type: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        min_grade: Optional[str] = None,
        limit: int = 50
    ) -> List[SupervisorPerformance]:
        """
        Get performance records with filters.
        
        Args:
            supervisor_id: Filter by supervisor
            hostel_id: Filter by hostel
            period_type: Filter by period type
            start_date: Filter by period start
            end_date: Filter by period end
            min_grade: Minimum grade filter
            limit: Maximum results
            
        Returns:
            List of performance records
        """
        query = self.db.query(SupervisorPerformance)
        
        if supervisor_id:
            query = query.filter(
                SupervisorPerformance.supervisor_id == supervisor_id
            )
        
        if hostel_id:
            query = query.filter(
                SupervisorPerformance.hostel_id == hostel_id
            )
        
        if period_type:
            query = query.filter(
                SupervisorPerformance.period_type == period_type
            )
        
        if start_date:
            query = query.filter(
                SupervisorPerformance.period_start >= start_date
            )
        
        if end_date:
            query = query.filter(
                SupervisorPerformance.period_end <= end_date
            )
        
        if min_grade:
            # Filter by grade (A+, A, B+, B, C, D)
            grade_order = {'A+': 6, 'A': 5, 'B+': 4, 'B': 3, 'C': 2, 'D': 1}
            min_level = grade_order.get(min_grade, 0)
            
            query = query.filter(
                SupervisorPerformance.performance_grade.in_([
                    g for g, level in grade_order.items() if level >= min_level
                ])
            )
        
        return query.options(
            joinedload(SupervisorPerformance.supervisor)
        ).order_by(
            SupervisorPerformance.period_end.desc()
        ).limit(limit).all()
    
    def get_latest_performance(
        self,
        supervisor_id: str,
        period_type: str = "monthly"
    ) -> Optional[SupervisorPerformance]:
        """Get latest performance record for supervisor."""
        return self.db.query(SupervisorPerformance).filter(
            and_(
                SupervisorPerformance.supervisor_id == supervisor_id,
                SupervisorPerformance.period_type == period_type
            )
        ).order_by(
            SupervisorPerformance.period_end.desc()
        ).first()
    
    def calculate_period_performance(
        self,
        supervisor_id: str,
        hostel_id: str,
        period_start: date,
        period_end: date,
        period_type: str = "monthly"
    ) -> SupervisorPerformance:
        """
        Calculate performance metrics for period.
        
        This would integrate with various modules to calculate actual metrics.
        For now, providing structure for implementation.
        """
        # TODO: Integrate with actual modules
        # - Complaint module for complaint metrics
        # - Attendance module for attendance metrics
        # - Maintenance module for maintenance metrics
        # - Communication module for announcement metrics
        
        # Placeholder data
        performance_data = {
            'complaints_handled': 0,
            'complaints_resolved': 0,
            'complaint_resolution_rate': Decimal('0.00'),
            'average_resolution_time_hours': Decimal('0.00'),
            'sla_compliance_rate': Decimal('100.00'),
            'attendance_records_created': 0,
            'attendance_accuracy': Decimal('100.00'),
            'maintenance_requests_created': 0,
            'maintenance_completed': 0,
            'performance_trend': 'stable'
        }
        
        return self.create_performance_record(
            supervisor_id=supervisor_id,
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            period_type=period_type,
            **performance_data
        )
    
    def _calculate_overall_score(
        self,
        performance_data: Dict[str, Any]
    ) -> Decimal:
        """Calculate overall performance score (0-100)."""
        # Weighted scoring
        weights = {
            'complaint_resolution_rate': 0.25,
            'sla_compliance_rate': 0.20,
            'attendance_accuracy': 0.15,
            'maintenance_completion_rate': 0.15,
            'student_feedback_score': 0.15,
            'response_consistency_score': 0.10
        }
        
        total_score = Decimal('0.00')
        total_weight = Decimal('0.00')
        
        for metric, weight in weights.items():
            value = performance_data.get(metric)
            if value is not None:
                if metric == 'student_feedback_score':
                    # Convert 0-5 scale to 0-100
                    value = (Decimal(str(value)) / Decimal('5.0')) * Decimal('100.0')
                
                total_score += Decimal(str(value)) * Decimal(str(weight))
                total_weight += Decimal(str(weight))
        
        if total_weight > 0:
            return round(total_score / total_weight, 2)
        
        return Decimal('0.00')
    
    def _calculate_grade(
        self,
        score: Decimal
    ) -> str:
        """Calculate performance grade from score."""
        if score >= 95:
            return 'A+'
        elif score >= 85:
            return 'A'
        elif score >= 80:
            return 'B+'
        elif score >= 70:
            return 'B'
        elif score >= 60:
            return 'C'
        else:
            return 'D'
    
    def _get_performance_dict(
        self,
        record: SupervisorPerformance
    ) -> Dict[str, Any]:
        """Convert performance record to dictionary."""
        return {
            'complaint_resolution_rate': record.complaint_resolution_rate,
            'sla_compliance_rate': record.sla_compliance_rate,
            'attendance_accuracy': record.attendance_accuracy,
            'maintenance_completion_rate': record.maintenance_completion_rate,
            'student_feedback_score': record.student_feedback_score,
            'response_consistency_score': record.response_consistency_score
        }
    
    # ==================== Performance Reviews ====================
    
    def create_performance_review(
        self,
        supervisor_id: str,
        review_period_start: date,
        review_period_end: date,
        review_date: date,
        reviewed_by: str,
        complaint_handling_rating: Decimal,
        attendance_management_rating: Decimal,
        maintenance_management_rating: Decimal,
        communication_rating: Decimal,
        professionalism_rating: Decimal,
        reliability_rating: Decimal,
        initiative_rating: Decimal,
        strengths: str,
        areas_for_improvement: str,
        goals_for_next_period: str,
        admin_comments: Optional[str] = None,
        action_items: Optional[Dict] = None,
        training_recommendations: Optional[Dict] = None
    ) -> PerformanceReview:
        """
        Create formal performance review.
        
        Args:
            supervisor_id: Supervisor being reviewed
            review_period_start: Review period start
            review_period_end: Review period end
            review_date: Review date
            reviewed_by: Admin conducting review
            complaint_handling_rating: Rating (1-5)
            attendance_management_rating: Rating (1-5)
            maintenance_management_rating: Rating (1-5)
            communication_rating: Rating (1-5)
            professionalism_rating: Rating (1-5)
            reliability_rating: Rating (1-5)
            initiative_rating: Rating (1-5)
            strengths: Supervisor strengths
            areas_for_improvement: Areas to improve
            goals_for_next_period: Goals for next period
            admin_comments: Additional comments
            action_items: Specific action items
            training_recommendations: Training recommendations
            
        Returns:
            Created review
        """
        # Calculate overall rating
        ratings = [
            complaint_handling_rating,
            attendance_management_rating,
            maintenance_management_rating,
            communication_rating,
            professionalism_rating,
            reliability_rating,
            initiative_rating
        ]
        overall_rating = sum(ratings) / len(ratings)
        
        review = PerformanceReview(
            supervisor_id=supervisor_id,
            review_period_start=review_period_start,
            review_period_end=review_period_end,
            review_date=review_date,
            reviewed_by=reviewed_by,
            complaint_handling_rating=complaint_handling_rating,
            attendance_management_rating=attendance_management_rating,
            maintenance_management_rating=maintenance_management_rating,
            communication_rating=communication_rating,
            professionalism_rating=professionalism_rating,
            reliability_rating=reliability_rating,
            initiative_rating=initiative_rating,
            overall_rating=overall_rating,
            strengths=strengths,
            areas_for_improvement=areas_for_improvement,
            goals_for_next_period=goals_for_next_period,
            admin_comments=admin_comments,
            action_items=action_items or {},
            training_recommendations=training_recommendations or {}
        )
        
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        
        logger.info(f"Created performance review for supervisor {supervisor_id}")
        return review
    
    def get_performance_reviews(
        self,
        supervisor_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        acknowledged_only: bool = False,
        limit: int = 20
    ) -> List[PerformanceReview]:
        """Get performance reviews with filters."""
        query = self.db.query(PerformanceReview)
        
        if supervisor_id:
            query = query.filter(
                PerformanceReview.supervisor_id == supervisor_id
            )
        
        if start_date:
            query = query.filter(
                PerformanceReview.review_date >= start_date
            )
        
        if end_date:
            query = query.filter(
                PerformanceReview.review_date <= end_date
            )
        
        if acknowledged_only:
            query = query.filter(
                PerformanceReview.acknowledged == True
            )
        
        return query.options(
            joinedload(PerformanceReview.supervisor),
            joinedload(PerformanceReview.reviewer)
        ).order_by(
            PerformanceReview.review_date.desc()
        ).limit(limit).all()
    
    def acknowledge_review(
        self,
        review_id: str,
        supervisor_comments: Optional[str] = None
    ) -> PerformanceReview:
        """Acknowledge performance review."""
        review = self.db.query(PerformanceReview).filter(
            PerformanceReview.id == review_id
        ).first()
        
        if not review:
            raise ResourceNotFoundError(f"Review {review_id} not found")
        
        review.acknowledged = True
        review.acknowledged_at = datetime.utcnow()
        if supervisor_comments:
            review.supervisor_comments = supervisor_comments
        
        self.db.commit()
        self.db.refresh(review)
        
        return review
    
    # ==================== Performance Goals ====================
    
    def create_performance_goal(
        self,
        supervisor_id: str,
        goal_name: str,
        goal_description: str,
        metric_name: str,
        target_value: Decimal,
        start_date: date,
        end_date: date,
        current_value: Optional[Decimal] = None,
        priority: str = "medium",
        category: str = "general",
        measurement_frequency: str = "weekly"
    ) -> PerformanceGoal:
        """
        Create SMART performance goal.
        
        Args:
            supervisor_id: Supervisor ID
            goal_name: Goal name
            goal_description: Detailed description
            metric_name: Metric to measure
            target_value: Target value to achieve
            start_date: Goal start date
            end_date: Target completion date
            current_value: Current baseline value
            priority: Priority (low, medium, high, critical)
            category: Goal category
            measurement_frequency: Measurement frequency
            
        Returns:
            Created goal
        """
        goal = PerformanceGoal(
            supervisor_id=supervisor_id,
            goal_name=goal_name,
            goal_description=goal_description,
            metric_name=metric_name,
            target_value=target_value,
            current_value=current_value,
            start_date=start_date,
            end_date=end_date,
            priority=priority,
            category=category,
            measurement_frequency=measurement_frequency
        )
        
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)
        
        logger.info(f"Created performance goal for supervisor {supervisor_id}")
        return goal
    
    def update_goal_progress(
        self,
        goal_id: str,
        progress_percentage: Decimal,
        notes: Optional[str] = None
    ) -> PerformanceGoal:
        """Update goal progress."""
        goal = self.db.query(PerformanceGoal).filter(
            PerformanceGoal.id == goal_id
        ).first()
        
        if not goal:
            raise ResourceNotFoundError(f"Goal {goal_id} not found")
        
        goal.progress_percentage = progress_percentage
        goal.last_updated = datetime.utcnow()
        
        if notes:
            goal.notes = notes
        
        # Update status based on progress
        if progress_percentage >= 100:
            goal.status = "completed"
            if not goal.completed:
                goal.completed = True
                goal.completed_at = datetime.utcnow()
                goal.achievement_percentage = progress_percentage
        elif progress_percentage >= 75:
            goal.status = "on_track"
        elif progress_percentage >= 50:
            goal.status = "at_risk"
        else:
            goal.status = "behind"
        
        self.db.commit()
        self.db.refresh(goal)
        
        return goal
    
    def complete_goal(
        self,
        goal_id: str,
        achievement_percentage: Decimal,
        notes: Optional[str] = None
    ) -> PerformanceGoal:
        """Mark goal as completed."""
        goal = self.db.query(PerformanceGoal).filter(
            PerformanceGoal.id == goal_id
        ).first()
        
        if not goal:
            raise ResourceNotFoundError(f"Goal {goal_id} not found")
        
        goal.completed = True
        goal.completed_at = datetime.utcnow()
        goal.achievement_percentage = achievement_percentage
        goal.progress_percentage = Decimal('100.00')
        goal.status = "completed"
        
        if notes:
            goal.notes = notes
        
        self.db.commit()
        self.db.refresh(goal)
        
        return goal
    
    def get_active_goals(
        self,
        supervisor_id: str,
        category: Optional[str] = None,
        priority: Optional[str] = None
    ) -> List[PerformanceGoal]:
        """Get active goals for supervisor."""
        query = self.db.query(PerformanceGoal).filter(
            and_(
                PerformanceGoal.supervisor_id == supervisor_id,
                PerformanceGoal.completed == False,
                PerformanceGoal.end_date >= date.today()
            )
        )
        
        if category:
            query = query.filter(PerformanceGoal.category == category)
        
        if priority:
            query = query.filter(PerformanceGoal.priority == priority)
        
        return query.order_by(
            PerformanceGoal.priority.desc(),
            PerformanceGoal.end_date
        ).all()
    
    def get_overdue_goals(
        self,
        supervisor_id: Optional[str] = None
    ) -> List[PerformanceGoal]:
        """Get overdue goals."""
        query = self.db.query(PerformanceGoal).filter(
            and_(
                PerformanceGoal.completed == False,
                PerformanceGoal.end_date < date.today()
            )
        )
        
        if supervisor_id:
            query = query.filter(
                PerformanceGoal.supervisor_id == supervisor_id
            )
        
        return query.order_by(
            PerformanceGoal.end_date
        ).all()
    
    # ==================== Performance Metrics ====================
    
    def record_performance_metric(
        self,
        supervisor_id: str,
        metric_date: date,
        metric_name: str,
        metric_value: Decimal,
        metric_unit: str = "count",
        category: str = "general",
        period_type: str = "daily",
        target_value: Optional[Decimal] = None,
        metadata: Optional[Dict] = None
    ) -> PerformanceMetric:
        """
        Record performance metric for time-series tracking.
        
        Args:
            supervisor_id: Supervisor ID
            metric_date: Metric date
            metric_name: Metric name
            metric_value: Metric value
            metric_unit: Metric unit
            category: Metric category
            period_type: Period type
            target_value: Target value
            metadata: Additional metadata
            
        Returns:
            Created metric
        """
        # Calculate variance if target provided
        variance = None
        variance_percentage = None
        
        if target_value is not None:
            variance = metric_value - target_value
            if target_value != 0:
                variance_percentage = (variance / target_value) * Decimal('100.0')
        
        # Determine trend (would compare with previous values)
        trend = self._calculate_metric_trend(
            supervisor_id,
            metric_name,
            metric_date,
            metric_value
        )
        
        metric = PerformanceMetric(
            supervisor_id=supervisor_id,
            metric_date=metric_date,
            metric_name=metric_name,
            metric_value=metric_value,
            metric_unit=metric_unit,
            category=category,
            period_type=period_type,
            target_value=target_value,
            variance=variance,
            variance_percentage=variance_percentage,
            trend=trend,
            metadata=metadata or {}
        )
        
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        
        return metric
    
    def get_performance_metrics(
        self,
        supervisor_id: Optional[str] = None,
        metric_name: Optional[str] = None,
        category: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 100
    ) -> List[PerformanceMetric]:
        """Get performance metrics with filters."""
        query = self.db.query(PerformanceMetric)
        
        if supervisor_id:
            query = query.filter(
                PerformanceMetric.supervisor_id == supervisor_id
            )
        
        if metric_name:
            query = query.filter(
                PerformanceMetric.metric_name == metric_name
            )
        
        if category:
            query = query.filter(
                PerformanceMetric.category == category
            )
        
        if start_date:
            query = query.filter(
                PerformanceMetric.metric_date >= start_date
            )
        
        if end_date:
            query = query.filter(
                PerformanceMetric.metric_date <= end_date
            )
        
        return query.order_by(
            PerformanceMetric.metric_date.desc()
        ).limit(limit).all()
    
    def _calculate_metric_trend(
        self,
        supervisor_id: str,
        metric_name: str,
        current_date: date,
        current_value: Decimal
    ) -> Optional[str]:
        """Calculate trend based on historical values."""
        # Get previous value
        previous = self.db.query(PerformanceMetric).filter(
            and_(
                PerformanceMetric.supervisor_id == supervisor_id,
                PerformanceMetric.metric_name == metric_name,
                PerformanceMetric.metric_date < current_date
            )
        ).order_by(
            PerformanceMetric.metric_date.desc()
        ).first()
        
        if not previous:
            return None
        
        # Compare values
        if current_value > previous.metric_value * Decimal('1.05'):
            return "improving"
        elif current_value < previous.metric_value * Decimal('0.95'):
            return "declining"
        else:
            return "stable"
    
    # ==================== Peer Comparison ====================
    
    def create_peer_comparison(
        self,
        supervisor_id: str,
        comparison_date: date,
        period_type: str,
        total_supervisors: int,
        rank: int,
        supervisor_score: Decimal,
        peer_average_score: Decimal,
        peer_median_score: Decimal,
        top_performer_score: Decimal,
        metric_comparisons: Dict,
        performance_tier: str
    ) -> PeerComparison:
        """Create peer comparison record."""
        percentile = ((total_supervisors - rank + 1) / total_supervisors) * Decimal('100.0')
        gap_to_average = supervisor_score - peer_average_score
        gap_to_top = supervisor_score - top_performer_score
        
        comparison = PeerComparison(
            supervisor_id=supervisor_id,
            comparison_date=comparison_date,
            period_type=period_type,
            total_supervisors=total_supervisors,
            rank=rank,
            percentile=percentile,
            supervisor_score=supervisor_score,
            peer_average_score=peer_average_score,
            peer_median_score=peer_median_score,
            top_performer_score=top_performer_score,
            gap_to_average=gap_to_average,
            gap_to_top=gap_to_top,
            metric_comparisons=metric_comparisons,
            performance_tier=performance_tier
        )
        
        self.db.add(comparison)
        self.db.commit()
        self.db.refresh(comparison)
        
        return comparison
    
    def calculate_peer_comparisons(
        self,
        hostel_id: str,
        comparison_date: date,
        period_type: str = "monthly"
    ) -> List[PeerComparison]:
        """
        Calculate peer comparisons for all supervisors in hostel.
        
        Args:
            hostel_id: Hostel ID
            comparison_date: Comparison date
            period_type: Period type
            
        Returns:
            List of peer comparisons
        """
        # Get all performance records for the period
        period_start = comparison_date - timedelta(days=30)  # Adjust based on period_type
        
        performances = self.db.query(SupervisorPerformance).filter(
            and_(
                SupervisorPerformance.hostel_id == hostel_id,
                SupervisorPerformance.period_type == period_type,
                SupervisorPerformance.period_end >= period_start,
                SupervisorPerformance.period_end <= comparison_date
            )
        ).all()
        
        if not performances:
            return []
        
        # Calculate statistics
        scores = [p.overall_performance_score for p in performances]
        total_supervisors = len(scores)
        peer_average = sum(scores) / total_supervisors
        peer_median = sorted(scores)[total_supervisors // 2]
        top_score = max(scores)
        
        # Rank supervisors
        ranked_performances = sorted(
            performances,
            key=lambda p: p.overall_performance_score,
            reverse=True
        )
        
        comparisons = []
        
        for rank, perf in enumerate(ranked_performances, start=1):
            # Determine performance tier
            if rank <= total_supervisors * 0.1:
                tier = "top_performer"
            elif rank <= total_supervisors * 0.3:
                tier = "high_performer"
            elif rank <= total_supervisors * 0.7:
                tier = "average"
            else:
                tier = "below_average"
            
            # Build metric comparisons
            metric_comparisons = {
                'complaint_resolution_rate': float(perf.complaint_resolution_rate),
                'sla_compliance_rate': float(perf.sla_compliance_rate),
                'attendance_accuracy': float(perf.attendance_accuracy)
            }
            
            comparison = self.create_peer_comparison(
                supervisor_id=perf.supervisor_id,
                comparison_date=comparison_date,
                period_type=period_type,
                total_supervisors=total_supervisors,
                rank=rank,
                supervisor_score=perf.overall_performance_score,
                peer_average_score=peer_average,
                peer_median_score=peer_median,
                top_performer_score=top_score,
                metric_comparisons=metric_comparisons,
                performance_tier=tier
            )
            
            comparisons.append(comparison)
        
        return comparisons
    
    def get_peer_comparisons(
        self,
        supervisor_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        performance_tier: Optional[str] = None,
        limit: int = 20
    ) -> List[PeerComparison]:
        """Get peer comparisons with filters."""
        query = self.db.query(PeerComparison)
        
        if supervisor_id:
            query = query.filter(
                PeerComparison.supervisor_id == supervisor_id
            )
        
        if start_date:
            query = query.filter(
                PeerComparison.comparison_date >= start_date
            )
        
        if end_date:
            query = query.filter(
                PeerComparison.comparison_date <= end_date
            )
        
        if performance_tier:
            query = query.filter(
                PeerComparison.performance_tier == performance_tier
            )
        
        return query.order_by(
            PeerComparison.comparison_date.desc()
        ).limit(limit).all()
    
    # ==================== Analytics ====================
    
    def get_performance_statistics(
        self,
        hostel_id: Optional[str] = None,
        period_type: str = "monthly"
    ) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        query = self.db.query(SupervisorPerformance).filter(
            SupervisorPerformance.period_type == period_type
        )
        
        if hostel_id:
            query = query.filter(
                SupervisorPerformance.hostel_id == hostel_id
            )
        
        records = query.all()
        
        if not records:
            return {'total_records': 0}
        
        scores = [r.overall_performance_score for r in records]
        
        return {
            'total_records': len(records),
            'average_score': round(sum(scores) / len(scores), 2),
            'median_score': sorted(scores)[len(scores) // 2],
            'highest_score': max(scores),
            'lowest_score': min(scores),
            'grade_distribution': self._calculate_grade_distribution(records)
        }
    
    def _calculate_grade_distribution(
        self,
        records: List[SupervisorPerformance]
    ) -> Dict[str, int]:
        """Calculate distribution of performance grades."""
        distribution = {'A+': 0, 'A': 0, 'B+': 0, 'B': 0, 'C': 0, 'D': 0}
        
        for record in records:
            if record.performance_grade in distribution:
                distribution[record.performance_grade] += 1
        
        return distribution