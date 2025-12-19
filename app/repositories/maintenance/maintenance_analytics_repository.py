# app/repositories/maintenance/maintenance_analytics_repository.py
"""
Maintenance Analytics Repository.

Comprehensive analytics and reporting for maintenance operations
with predictive insights and performance benchmarking.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, case, cast, desc, extract, func, or_, select, text
from sqlalchemy.orm import Session
from sqlalchemy.types import Date as DateType, Numeric

from app.models.maintenance import (
    MaintenanceAnalytic,
    CategoryPerformanceMetric,
    MaintenanceRequest,
    MaintenanceCompletion,
    MaintenanceCost,
    MaintenanceAssignment,
    VendorAssignment,
)
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.pagination import PaginationParams, PaginatedResult
from app.schemas.common.enums import MaintenanceCategory, MaintenanceStatus, Priority


class MaintenanceAnalyticsRepository(BaseRepository[MaintenanceAnalytic]):
    """
    Repository for maintenance analytics operations.
    
    Provides comprehensive analytics, KPI tracking, predictive insights,
    and performance benchmarking for maintenance operations.
    """
    
    def __init__(self, session: Session):
        """Initialize repository with session."""
        super().__init__(MaintenanceAnalytic, session)
    
    # ============================================================================
    # CREATE OPERATIONS
    # ============================================================================
    
    def create_analytics_record(
        self,
        hostel_id: UUID,
        period_type: str,
        period_start: date,
        period_end: date,
        period_label: str,
        **metrics
    ) -> MaintenanceAnalytic:
        """
        Create analytics record for period.
        
        Args:
            hostel_id: Hostel identifier
            period_type: Period type (daily, weekly, monthly, etc.)
            period_start: Period start date
            period_end: Period end date
            period_label: Period label
            **metrics: Analytics metrics
            
        Returns:
            Created analytics record
        """
        analytics_data = {
            "hostel_id": hostel_id,
            "period_type": period_type,
            "period_start": period_start,
            "period_end": period_end,
            "period_label": period_label,
            **metrics
        }
        
        analytics = self.create(analytics_data)
        
        # Calculate efficiency score
        analytics.calculate_efficiency_score()
        self.session.commit()
        self.session.refresh(analytics)
        
        return analytics
    
    def create_category_performance(
        self,
        hostel_id: UUID,
        category: str,
        period_start: date,
        period_end: date,
        **metrics
    ) -> CategoryPerformanceMetric:
        """
        Create category performance metric.
        
        Args:
            hostel_id: Hostel identifier
            category: Maintenance category
            period_start: Period start date
            period_end: Period end date
            **metrics: Performance metrics
            
        Returns:
            Created category performance metric
        """
        metric_data = {
            "hostel_id": hostel_id,
            "period_start": period_start,
            "period_end": period_end,
            "category": category,
            **metrics
        }
        
        metric = CategoryPerformanceMetric(**metric_data)
        self.session.add(metric)
        self.session.commit()
        self.session.refresh(metric)
        
        return metric
    
    # ============================================================================
    # READ OPERATIONS
    # ============================================================================
    
    def find_by_period(
        self,
        hostel_id: UUID,
        period_type: str,
        period_start: date,
        period_end: Optional[date] = None
    ) -> Optional[MaintenanceAnalytic]:
        """
        Find analytics for specific period.
        
        Args:
            hostel_id: Hostel identifier
            period_type: Period type
            period_start: Period start date
            period_end: Optional period end date
            
        Returns:
            Analytics record if exists
        """
        query = select(MaintenanceAnalytic).where(
            MaintenanceAnalytic.hostel_id == hostel_id,
            MaintenanceAnalytic.period_type == period_type,
            MaintenanceAnalytic.period_start == period_start
        )
        
        if period_end:
            query = query.where(MaintenanceAnalytic.period_end == period_end)
        
        return self.session.execute(query).scalar_one_or_none()
    
    def find_analytics_by_date_range(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        period_type: Optional[str] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[MaintenanceAnalytic]:
        """
        Find analytics records in date range.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Range start date
            end_date: Range end date
            period_type: Optional period type filter
            pagination: Pagination parameters
            
        Returns:
            Paginated analytics records
        """
        query = select(MaintenanceAnalytic).where(
            MaintenanceAnalytic.hostel_id == hostel_id,
            MaintenanceAnalytic.period_start >= start_date,
            MaintenanceAnalytic.period_end <= end_date
        )
        
        if period_type:
            query = query.where(MaintenanceAnalytic.period_type == period_type)
        
        query = query.order_by(MaintenanceAnalytic.period_start.desc())
        
        return self.paginate(query, pagination)
    
    def get_category_performance_for_period(
        self,
        hostel_id: UUID,
        period_start: date,
        period_end: date
    ) -> List[CategoryPerformanceMetric]:
        """
        Get category performance metrics for period.
        
        Args:
            hostel_id: Hostel identifier
            period_start: Period start date
            period_end: Period end date
            
        Returns:
            List of category performance metrics
        """
        query = select(CategoryPerformanceMetric).where(
            CategoryPerformanceMetric.hostel_id == hostel_id,
            CategoryPerformanceMetric.period_start == period_start,
            CategoryPerformanceMetric.period_end == period_end
        ).order_by(CategoryPerformanceMetric.total_cost.desc())
        
        return list(self.session.execute(query).scalars().all())
    
    # ============================================================================
    # ANALYTICS GENERATION
    # ============================================================================
    
    def generate_daily_analytics(
        self,
        hostel_id: UUID,
        target_date: date
    ) -> MaintenanceAnalytic:
        """
        Generate daily analytics for hostel.
        
        Args:
            hostel_id: Hostel identifier
            target_date: Target date
            
        Returns:
            Generated daily analytics
        """
        period_start = target_date
        period_end = target_date
        period_label = target_date.strftime("%Y-%m-%d")
        
        # Calculate metrics
        metrics = self._calculate_period_metrics(
            hostel_id,
            period_start,
            period_end
        )
        
        # Check if record exists
        existing = self.find_by_period(
            hostel_id,
            "daily",
            period_start,
            period_end
        )
        
        if existing:
            # Update existing record
            for key, value in metrics.items():
                setattr(existing, key, value)
            existing.calculate_efficiency_score()
            self.session.commit()
            self.session.refresh(existing)
            return existing
        
        # Create new record
        return self.create_analytics_record(
            hostel_id=hostel_id,
            period_type="daily",
            period_start=period_start,
            period_end=period_end,
            period_label=period_label,
            **metrics
        )
    
    def generate_monthly_analytics(
        self,
        hostel_id: UUID,
        year: int,
        month: int
    ) -> MaintenanceAnalytic:
        """
        Generate monthly analytics for hostel.
        
        Args:
            hostel_id: Hostel identifier
            year: Year
            month: Month
            
        Returns:
            Generated monthly analytics
        """
        from calendar import monthrange
        
        period_start = date(year, month, 1)
        last_day = monthrange(year, month)[1]
        period_end = date(year, month, last_day)
        period_label = period_start.strftime("%Y-%m")
        
        # Calculate metrics
        metrics = self._calculate_period_metrics(
            hostel_id,
            period_start,
            period_end
        )
        
        # Check if record exists
        existing = self.find_by_period(
            hostel_id,
            "monthly",
            period_start,
            period_end
        )
        
        if existing:
            # Update existing record
            for key, value in metrics.items():
                setattr(existing, key, value)
            existing.calculate_efficiency_score()
            self.session.commit()
            self.session.refresh(existing)
            return existing
        
        # Create new record
        analytics = self.create_analytics_record(
            hostel_id=hostel_id,
            period_type="monthly",
            period_start=period_start,
            period_end=period_end,
            period_label=period_label,
            **metrics
        )
        
        # Generate category performance metrics
        self._generate_category_metrics(
            hostel_id,
            period_start,
            period_end
        )
        
        return analytics
    
    def generate_quarterly_analytics(
        self,
        hostel_id: UUID,
        year: int,
        quarter: int
    ) -> MaintenanceAnalytic:
        """
        Generate quarterly analytics for hostel.
        
        Args:
            hostel_id: Hostel identifier
            year: Year
            quarter: Quarter (1-4)
            
        Returns:
            Generated quarterly analytics
        """
        from calendar import monthrange
        
        # Calculate quarter dates
        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 2
        
        period_start = date(year, start_month, 1)
        last_day = monthrange(year, end_month)[1]
        period_end = date(year, end_month, last_day)
        period_label = f"Q{quarter} {year}"
        
        # Calculate metrics
        metrics = self._calculate_period_metrics(
            hostel_id,
            period_start,
            period_end
        )
        
        # Check if record exists
        existing = self.find_by_period(
            hostel_id,
            "quarterly",
            period_start,
            period_end
        )
        
        if existing:
            # Update existing record
            for key, value in metrics.items():
                setattr(existing, key, value)
            existing.calculate_efficiency_score()
            self.session.commit()
            self.session.refresh(existing)
            return existing
        
        # Create new record
        return self.create_analytics_record(
            hostel_id=hostel_id,
            period_type="quarterly",
            period_start=period_start,
            period_end=period_end,
            period_label=period_label,
            **metrics
        )
    
    def generate_annual_analytics(
        self,
        hostel_id: UUID,
        year: int
    ) -> MaintenanceAnalytic:
        """
        Generate annual analytics for hostel.
        
        Args:
            hostel_id: Hostel identifier
            year: Year
            
        Returns:
            Generated annual analytics
        """
        period_start = date(year, 1, 1)
        period_end = date(year, 12, 31)
        period_label = str(year)
        
        # Calculate metrics
        metrics = self._calculate_period_metrics(
            hostel_id,
            period_start,
            period_end
        )
        
        # Check if record exists
        existing = self.find_by_period(
            hostel_id,
            "yearly",
            period_start,
            period_end
        )
        
        if existing:
            # Update existing record
            for key, value in metrics.items():
                setattr(existing, key, value)
            existing.calculate_efficiency_score()
            self.session.commit()
            self.session.refresh(existing)
            return existing
        
        # Create new record
        return self.create_analytics_record(
            hostel_id=hostel_id,
            period_type="yearly",
            period_start=period_start,
            period_end=period_end,
            period_label=period_label,
            **metrics
        )
    
    # ============================================================================
    # KPI CALCULATIONS
    # ============================================================================
    
    def calculate_kpis(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive KPIs for period.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Period start date
            end_date: Period end date
            
        Returns:
            Dictionary of KPIs
        """
        metrics = self._calculate_period_metrics(hostel_id, start_date, end_date)
        
        # Calculate additional KPIs
        kpis = {
            # Request KPIs
            "total_requests": metrics["total_requests"],
            "completed_requests": metrics["completed_requests"],
            "pending_requests": metrics["pending_requests"],
            "completion_rate": float(metrics["completion_rate"]),
            
            # Time KPIs
            "average_completion_time_days": float(metrics["average_completion_time_days"]),
            "median_completion_time_days": float(metrics.get("median_completion_time_days", 0)),
            "on_time_completion_rate": float(metrics["on_time_completion_rate"]),
            
            # Cost KPIs
            "total_cost": float(metrics["total_cost"]),
            "average_cost_per_request": float(metrics["average_cost_per_request"]),
            "cost_variance_percentage": float(metrics["cost_variance_percentage"]),
            "within_budget_rate": float(metrics["within_budget_rate"]),
            
            # Quality KPIs
            "quality_check_rate": float(metrics["quality_check_rate"]),
            "quality_pass_rate": float(metrics["quality_pass_rate"]),
            "average_quality_rating": float(metrics.get("average_quality_rating", 0)),
            "rework_rate": float(metrics["rework_rate"]),
            
            # Priority KPIs
            "critical_requests": metrics["critical_requests"],
            "urgent_requests": metrics["urgent_requests"],
            "high_requests": metrics["high_requests"],
            
            # Efficiency
            "efficiency_score": float(metrics.get("efficiency_score", 0)),
        }
        
        return kpis
    
    def calculate_mttr(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date,
        category: Optional[MaintenanceCategory] = None
    ) -> Optional[Decimal]:
        """
        Calculate Mean Time To Repair (MTTR).
        
        Args:
            hostel_id: Hostel identifier
            start_date: Period start date
            end_date: Period end date
            category: Optional category filter
            
        Returns:
            MTTR in hours, or None if no data
        """
        query = select(
            func.avg(
                extract('epoch', MaintenanceRequest.completed_at - MaintenanceRequest.created_at) / 3600
            ).label("mttr")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.status == MaintenanceStatus.COMPLETED,
            MaintenanceRequest.completed_at.isnot(None),
            MaintenanceRequest.created_at >= datetime.combine(start_date, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(end_date, datetime.max.time()),
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        if category:
            query = query.where(MaintenanceRequest.category == category)
        
        result = self.session.execute(query).scalar_one_or_none()
        
        return Decimal(str(result)) if result else None
    
    def calculate_mtbf(
        self,
        hostel_id: UUID,
        equipment_id: Optional[UUID] = None,
        days: int = 365
    ) -> Optional[Decimal]:
        """
        Calculate Mean Time Between Failures (MTBF).
        
        Args:
            hostel_id: Hostel identifier
            equipment_id: Optional equipment identifier
            days: Time period in days
            
        Returns:
            MTBF in hours, or None if insufficient data
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Count failures (maintenance requests)
        failure_query = select(
            func.count(MaintenanceRequest.id).label("failure_count")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.created_at >= datetime.combine(start_date, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(end_date, datetime.max.time()),
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        failure_count = self.session.execute(failure_query).scalar_one()
        
        if failure_count <= 1:
            return None
        
        # Calculate MTBF
        total_hours = days * 24
        mtbf = Decimal(str(total_hours)) / Decimal(str(failure_count - 1))
        
        return mtbf
    
    def calculate_first_time_fix_rate(
        self,
        hostel_id: UUID,
        start_date: date,
        end_date: date
    ) -> Decimal:
        """
        Calculate First Time Fix Rate (percentage of issues resolved on first visit).
        
        Args:
            hostel_id: Hostel identifier
            start_date: Period start date
            end_date: Period end date
            
        Returns:
            First time fix rate percentage
        """
        query = select(
            func.count(MaintenanceRequest.id).label("total"),
            func.sum(
                case(
                    (MaintenanceCompletion.follow_up_required == False, 1),
                    else_=0
                )
            ).label("first_time_fix")
        ).join(
            MaintenanceCompletion,
            MaintenanceRequest.id == MaintenanceCompletion.maintenance_request_id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.status == MaintenanceStatus.COMPLETED,
            MaintenanceRequest.completed_at >= datetime.combine(start_date, datetime.min.time()),
            MaintenanceRequest.completed_at <= datetime.combine(end_date, datetime.max.time()),
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        result = self.session.execute(query).first()
        
        if not result or result.total == 0:
            return Decimal("0.00")
        
        return round(
            Decimal(result.first_time_fix or 0) / Decimal(result.total) * 100,
            2
        )
    
    # ============================================================================
    # TREND ANALYSIS
    # ============================================================================
    
    def get_request_trends(
        self,
        hostel_id: UUID,
        months: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Get monthly request volume trends.
        
        Args:
            hostel_id: Hostel identifier
            months: Number of months to analyze
            
        Returns:
            Monthly trend data
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)
        
        query = select(
            func.date_trunc('month', MaintenanceRequest.created_at).label('month'),
            func.count(MaintenanceRequest.id).label("request_count"),
            func.sum(
                case(
                    (MaintenanceRequest.status == MaintenanceStatus.COMPLETED, 1),
                    else_=0
                )
            ).label("completed"),
            func.avg(
                case(
                    (
                        MaintenanceRequest.completed_at.isnot(None),
                        extract('epoch', MaintenanceRequest.completed_at - MaintenanceRequest.created_at) / 86400
                    ),
                    else_=None
                )
            ).label("avg_completion_days")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.created_at >= datetime.combine(start_date, datetime.min.time()),
            MaintenanceRequest.deleted_at.is_(None)
        ).group_by(
            'month'
        ).order_by(
            'month'
        )
        
        results = self.session.execute(query).all()
        
        trends = []
        for row in results:
            completion_rate = Decimal("0.00")
            if row.request_count > 0:
                completion_rate = round(
                    Decimal(row.completed or 0) / Decimal(row.request_count) * 100,
                    2
                )
            
            trends.append({
                "month": row.month.strftime("%Y-%m"),
                "request_count": row.request_count,
                "completed": row.completed or 0,
                "completion_rate": float(completion_rate),
                "avg_completion_days": float(row.avg_completion_days or 0)
            })
        
        return trends
    
    def get_cost_trends(
        self,
        hostel_id: UUID,
        months: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Get monthly cost trends.
        
        Args:
            hostel_id: Hostel identifier
            months: Number of months to analyze
            
        Returns:
            Monthly cost trend data
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)
        
        query = select(
            func.date_trunc('month', MaintenanceRequest.created_at).label('month'),
            func.count(MaintenanceCost.id).label("request_count"),
            func.sum(MaintenanceCost.actual_cost).label("total_cost"),
            func.avg(MaintenanceCost.actual_cost).label("avg_cost"),
            func.sum(MaintenanceCost.materials_cost).label("materials_total"),
            func.sum(MaintenanceCost.labor_cost).label("labor_total"),
            func.sum(MaintenanceCost.vendor_charges).label("vendor_total")
        ).join(
            MaintenanceRequest,
            MaintenanceCost.maintenance_request_id == MaintenanceRequest.id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceCost.actual_cost.isnot(None),
            MaintenanceRequest.created_at >= datetime.combine(start_date, datetime.min.time()),
            MaintenanceCost.deleted_at.is_(None)
        ).group_by(
            'month'
        ).order_by(
            'month'
        )
        
        results = self.session.execute(query).all()
        
        return [
            {
                "month": row.month.strftime("%Y-%m"),
                "request_count": row.request_count,
                "total_cost": float(row.total_cost or 0),
                "average_cost": float(row.avg_cost or 0),
                "materials_cost": float(row.materials_total or 0),
                "labor_cost": float(row.labor_total or 0),
                "vendor_cost": float(row.vendor_total or 0)
            }
            for row in results
        ]
    
    def identify_seasonal_patterns(
        self,
        hostel_id: UUID,
        years: int = 2
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Identify seasonal patterns in maintenance requests.
        
        Args:
            hostel_id: Hostel identifier
            years: Number of years to analyze
            
        Returns:
            Seasonal pattern analysis
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=years * 365)
        
        # Monthly patterns
        monthly_query = select(
            extract('month', MaintenanceRequest.created_at).label('month'),
            func.count(MaintenanceRequest.id).label("request_count"),
            func.avg(MaintenanceCost.actual_cost).label("avg_cost")
        ).outerjoin(
            MaintenanceCost,
            MaintenanceRequest.id == MaintenanceCost.maintenance_request_id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.created_at >= datetime.combine(start_date, datetime.min.time()),
            MaintenanceRequest.deleted_at.is_(None)
        ).group_by(
            'month'
        ).order_by(
            'month'
        )
        
        monthly_results = self.session.execute(monthly_query).all()
        
        # Quarterly patterns
        quarterly_query = select(
            extract('quarter', MaintenanceRequest.created_at).label('quarter'),
            func.count(MaintenanceRequest.id).label("request_count"),
            func.avg(MaintenanceCost.actual_cost).label("avg_cost")
        ).outerjoin(
            MaintenanceCost,
            MaintenanceRequest.id == MaintenanceCost.maintenance_request_id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.created_at >= datetime.combine(start_date, datetime.min.time()),
            MaintenanceRequest.deleted_at.is_(None)
        ).group_by(
            'quarter'
        ).order_by(
            'quarter'
        )
        
        quarterly_results = self.session.execute(quarterly_query).all()
        
        return {
            "monthly": [
                {
                    "month": int(row.month),
                    "request_count": row.request_count,
                    "average_cost": float(row.avg_cost or 0)
                }
                for row in monthly_results
            ],
            "quarterly": [
                {
                    "quarter": int(row.quarter),
                    "request_count": row.request_count,
                    "average_cost": float(row.avg_cost or 0)
                }
                for row in quarterly_results
            ]
        }
    
    # ============================================================================
    # PREDICTIVE ANALYTICS
    # ============================================================================
    
    def forecast_maintenance_demand(
        self,
        hostel_id: UUID,
        forecast_months: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Forecast maintenance demand for upcoming months.
        
        Uses simple moving average for forecasting.
        
        Args:
            hostel_id: Hostel identifier
            forecast_months: Number of months to forecast
            
        Returns:
            Forecasted demand data
        """
        # Get historical data (last 12 months)
        historical_data = self.get_request_trends(hostel_id, months=12)
        
        if len(historical_data) < 3:
            return []
        
        # Calculate simple moving average (last 3 months)
        recent_counts = [d["request_count"] for d in historical_data[-3:]]
        avg_requests = sum(recent_counts) / len(recent_counts)
        
        recent_costs = [d.get("avg_completion_days", 0) for d in historical_data[-3:]]
        avg_days = sum(recent_costs) / len(recent_costs) if recent_costs else 0
        
        # Generate forecast
        forecast = []
        current_date = date.today()
        
        for i in range(forecast_months):
            forecast_date = current_date + timedelta(days=(i + 1) * 30)
            forecast.append({
                "month": forecast_date.strftime("%Y-%m"),
                "forecasted_requests": round(avg_requests),
                "forecasted_avg_days": round(avg_days, 1),
                "confidence": "medium"  # Simple forecast has medium confidence
            })
        
        return forecast
    
    def predict_equipment_failure(
        self,
        hostel_id: UUID,
        equipment_category: str
    ) -> Dict[str, Any]:
        """
        Predict potential equipment failures based on maintenance history.
        
        Args:
            hostel_id: Hostel identifier
            equipment_category: Equipment category
            
        Returns:
            Failure prediction analysis
        """
        # Get maintenance frequency for category
        query = select(
            func.count(MaintenanceRequest.id).label("total_requests"),
            func.avg(
                extract('epoch', MaintenanceRequest.created_at - func.lag(MaintenanceRequest.created_at).over(
                    order_by=MaintenanceRequest.created_at
                )) / 86400
            ).label("avg_days_between_failures")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.category == MaintenanceCategory[equipment_category.upper()],
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        result = self.session.execute(query).first()
        
        if not result or result.total_requests < 2:
            return {
                "category": equipment_category,
                "prediction": "insufficient_data",
                "confidence": "low"
            }
        
        # Get last maintenance date
        last_maintenance_query = select(
            func.max(MaintenanceRequest.created_at).label("last_maintenance")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.category == MaintenanceCategory[equipment_category.upper()],
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        last_maintenance = self.session.execute(last_maintenance_query).scalar_one_or_none()
        
        if not last_maintenance:
            return {
                "category": equipment_category,
                "prediction": "no_data",
                "confidence": "low"
            }
        
        days_since_last = (datetime.now() - last_maintenance).days
        avg_days_between = result.avg_days_between_failures or 90
        
        # Calculate risk score
        risk_score = min(100, (days_since_last / avg_days_between) * 100)
        
        prediction = {
            "category": equipment_category,
            "days_since_last_maintenance": days_since_last,
            "average_days_between_failures": round(avg_days_between, 1),
            "risk_score": round(risk_score, 1),
            "prediction": "high_risk" if risk_score > 80 else "moderate_risk" if risk_score > 50 else "low_risk",
            "confidence": "high" if result.total_requests > 10 else "medium",
            "recommended_action": "schedule_preventive_maintenance" if risk_score > 70 else "monitor"
        }
        
        return prediction
    
    # ============================================================================
    # BENCHMARKING
    # ============================================================================
    
    def benchmark_against_industry(
        self,
        hostel_id: UUID
    ) -> Dict[str, Any]:
        """
        Benchmark hostel performance against industry standards.
        
        Args:
            hostel_id: Hostel identifier
            
        Returns:
            Benchmarking analysis
        """
        # Industry benchmarks (these would typically come from external data)
        industry_benchmarks = {
            "completion_rate": 85.0,
            "on_time_rate": 75.0,
            "mttr_hours": 48.0,
            "cost_per_request": 2000.0,
            "quality_pass_rate": 90.0
        }
        
        # Get current period KPIs
        end_date = date.today()
        start_date = end_date - timedelta(days=90)  # Last 90 days
        
        kpis = self.calculate_kpis(hostel_id, start_date, end_date)
        mttr = self.calculate_mttr(hostel_id, start_date, end_date)
        
        # Calculate variances
        benchmarks = {}
        
        if kpis["completion_rate"] > 0:
            benchmarks["completion_rate"] = {
                "hostel_value": kpis["completion_rate"],
                "industry_benchmark": industry_benchmarks["completion_rate"],
                "variance": kpis["completion_rate"] - industry_benchmarks["completion_rate"],
                "performance": "above" if kpis["completion_rate"] > industry_benchmarks["completion_rate"] else "below"
            }
        
        if kpis["on_time_completion_rate"] > 0:
            benchmarks["on_time_rate"] = {
                "hostel_value": kpis["on_time_completion_rate"],
                "industry_benchmark": industry_benchmarks["on_time_rate"],
                "variance": kpis["on_time_completion_rate"] - industry_benchmarks["on_time_rate"],
                "performance": "above" if kpis["on_time_completion_rate"] > industry_benchmarks["on_time_rate"] else "below"
            }
        
        if mttr:
            benchmarks["mttr"] = {
                "hostel_value": float(mttr),
                "industry_benchmark": industry_benchmarks["mttr_hours"],
                "variance": float(mttr) - industry_benchmarks["mttr_hours"],
                "performance": "below" if float(mttr) < industry_benchmarks["mttr_hours"] else "above"  # Lower is better
            }
        
        if kpis["average_cost_per_request"] > 0:
            benchmarks["cost_per_request"] = {
                "hostel_value": kpis["average_cost_per_request"],
                "industry_benchmark": industry_benchmarks["cost_per_request"],
                "variance": kpis["average_cost_per_request"] - industry_benchmarks["cost_per_request"],
                "performance": "below" if kpis["average_cost_per_request"] < industry_benchmarks["cost_per_request"] else "above"  # Lower is better
            }
        
        return benchmarks
    
    # ============================================================================
    # HELPER METHODS
    # ============================================================================
    
    def _calculate_period_metrics(
        self,
        hostel_id: UUID,
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive metrics for period.
        
        Args:
            hostel_id: Hostel identifier
            period_start: Period start date
            period_end: Period end date
            
        Returns:
            Dictionary of calculated metrics
        """
        # Request counts
        request_query = select(
            func.count(MaintenanceRequest.id).label("total"),
            func.sum(
                case(
                    (MaintenanceRequest.status == MaintenanceStatus.COMPLETED, 1),
                    else_=0
                )
            ).label("completed"),
            func.sum(
                case(
                    (MaintenanceRequest.status == MaintenanceStatus.PENDING, 1),
                    else_=0
                )
            ).label("pending"),
            func.sum(
                case(
                    (MaintenanceRequest.status == MaintenanceStatus.CANCELLED, 1),
                    else_=0
                )
            ).label("cancelled"),
            func.sum(
                case(
                    (MaintenanceRequest.priority == Priority.CRITICAL, 1),
                    else_=0
                )
            ).label("critical"),
            func.sum(
                case(
                    (MaintenanceRequest.priority == Priority.URGENT, 1),
                    else_=0
                )
            ).label("urgent"),
            func.sum(
                case(
                    (MaintenanceRequest.priority == Priority.HIGH, 1),
                    else_=0
                )
            ).label("high")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.created_at >= datetime.combine(period_start, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(period_end, datetime.max.time()),
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        request_result = self.session.execute(request_query).first()
        
        total_requests = request_result.total or 0
        completed_requests = request_result.completed or 0
        pending_requests = request_result.pending or 0
        cancelled_requests = request_result.cancelled or 0
        
        # Calculate completion rate
        completion_rate = Decimal("0.00")
        if total_requests > 0:
            completion_rate = round(
                Decimal(completed_requests) / Decimal(total_requests) * 100,
                2
            )
        
        # Time metrics
        time_query = select(
            func.avg(
                extract('epoch', MaintenanceRequest.completed_at - MaintenanceRequest.created_at) / 3600
            ).label("avg_hours"),
            func.percentile_cont(0.5).within_group(
                extract('epoch', MaintenanceRequest.completed_at - MaintenanceRequest.created_at) / 86400
            ).label("median_days"),
            func.sum(
                case(
                    (
                        and_(
                            MaintenanceRequest.completed_at.isnot(None),
                            MaintenanceRequest.deadline.isnot(None),
                            MaintenanceRequest.completed_at <= MaintenanceRequest.deadline
                        ),
                        1
                    ),
                    else_=0
                )
            ).label("on_time")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.status == MaintenanceStatus.COMPLETED,
            MaintenanceRequest.completed_at.isnot(None),
            MaintenanceRequest.created_at >= datetime.combine(period_start, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(period_end, datetime.max.time()),
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        time_result = self.session.execute(time_query).first()
        
        avg_hours = Decimal(str(time_result.avg_hours)) if time_result.avg_hours else Decimal("0.00")
        avg_days = avg_hours / 24 if avg_hours > 0 else Decimal("0.00")
        median_days = Decimal(str(time_result.median_days)) if time_result.median_days else Decimal("0.00")
        
        on_time_rate = Decimal("0.00")
        if completed_requests > 0:
            on_time_rate = round(
                Decimal(time_result.on_time or 0) / Decimal(completed_requests) * 100,
                2
            )
        
        # Cost metrics
        cost_query = select(
            func.sum(MaintenanceCost.actual_cost).label("total_cost"),
            func.avg(MaintenanceCost.actual_cost).label("avg_cost"),
            func.avg(MaintenanceCost.variance_percentage).label("avg_variance"),
            func.sum(
                case(
                    (MaintenanceCost.within_budget == True, 1),
                    else_=0
                )
            ).label("within_budget_count")
        ).join(
            MaintenanceRequest,
            MaintenanceCost.maintenance_request_id == MaintenanceRequest.id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceCost.actual_cost.isnot(None),
            MaintenanceRequest.created_at >= datetime.combine(period_start, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(period_end, datetime.max.time()),
            MaintenanceCost.deleted_at.is_(None)
        )
        
        cost_result = self.session.execute(cost_query).first()
        
        total_cost = Decimal(str(cost_result.total_cost)) if cost_result.total_cost else Decimal("0.00")
        avg_cost = Decimal(str(cost_result.avg_cost)) if cost_result.avg_cost else Decimal("0.00")
        cost_variance = Decimal(str(cost_result.avg_variance)) if cost_result.avg_variance else Decimal("0.00")
        
        within_budget_rate = Decimal("0.00")
        if completed_requests > 0:
            within_budget_rate = round(
                Decimal(cost_result.within_budget_count or 0) / Decimal(completed_requests) * 100,
                2
            )
        
        # Quality metrics
        quality_query = select(
            func.count(MaintenanceCompletion.id).label("total_completions"),
            func.sum(
                case(
                    (MaintenanceCompletion.quality_verified == True, 1),
                    else_=0
                )
            ).label("quality_checked"),
            func.avg(
                case(
                    (MaintenanceCompletion.quality_verified == True, MaintenanceCompletion.quality_rating),
                    else_=None
                )
            ).label("avg_quality_rating")
        ).join(
            MaintenanceRequest,
            MaintenanceCompletion.maintenance_request_id == MaintenanceRequest.id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.created_at >= datetime.combine(period_start, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(period_end, datetime.max.time()),
            MaintenanceCompletion.deleted_at.is_(None)
        )
        
        quality_result = self.session.execute(quality_query).first()
        
        quality_check_rate = Decimal("0.00")
        if quality_result.total_completions and quality_result.total_completions > 0:
            quality_check_rate = round(
                Decimal(quality_result.quality_checked or 0) / Decimal(quality_result.total_completions) * 100,
                2
            )
        
        # Simplified quality pass rate (assuming quality checked items passed)
        quality_pass_rate = quality_check_rate  # This could be more sophisticated
        
        # Rework rate calculation
        rework_query = select(
            func.sum(
                case(
                    (MaintenanceCompletion.follow_up_required == True, 1),
                    else_=0
                )
            ).label("rework_count")
        ).join(
            MaintenanceRequest,
            MaintenanceCompletion.maintenance_request_id == MaintenanceRequest.id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.created_at >= datetime.combine(period_start, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(period_end, datetime.max.time()),
            MaintenanceCompletion.deleted_at.is_(None)
        )
        
        rework_result = self.session.execute(rework_query).scalar_one_or_none()
        
        rework_rate = Decimal("0.00")
        if completed_requests > 0:
            rework_rate = round(
                Decimal(rework_result or 0) / Decimal(completed_requests) * 100,
                2
            )
        
        # Category and priority breakdowns
        category_query = select(
            MaintenanceRequest.category,
            func.count(MaintenanceRequest.id).label("count")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.created_at >= datetime.combine(period_start, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(period_end, datetime.max.time()),
            MaintenanceRequest.deleted_at.is_(None)
        ).group_by(
            MaintenanceRequest.category
        )
        
        category_results = self.session.execute(category_query).all()
        requests_by_category = {
            str(row.category.value): row.count
            for row in category_results
        }
        
        # Cost by category
        cost_by_category_query = select(
            MaintenanceRequest.category,
            func.sum(MaintenanceCost.actual_cost).label("total_cost")
        ).join(
            MaintenanceCost,
            MaintenanceRequest.id == MaintenanceCost.maintenance_request_id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceCost.actual_cost.isnot(None),
            MaintenanceRequest.created_at >= datetime.combine(period_start, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(period_end, datetime.max.time()),
            MaintenanceCost.deleted_at.is_(None)
        ).group_by(
            MaintenanceRequest.category
        )
        
        cost_category_results = self.session.execute(cost_by_category_query).all()
        cost_by_category = {
            str(row.category.value): float(row.total_cost)
            for row in cost_category_results
        }
        
        return {
            "total_requests": total_requests,
            "completed_requests": completed_requests,
            "pending_requests": pending_requests,
            "cancelled_requests": cancelled_requests,
            "completion_rate": completion_rate,
            "average_completion_time_hours": avg_hours,
            "average_completion_time_days": avg_days,
            "median_completion_time_days": median_days,
            "on_time_completion_rate": on_time_rate,
            "total_cost": total_cost,
            "average_cost_per_request": avg_cost,
            "cost_variance_percentage": cost_variance,
            "within_budget_rate": within_budget_rate,
            "quality_check_rate": quality_check_rate,
            "quality_pass_rate": quality_pass_rate,
            "average_quality_rating": Decimal(str(quality_result.avg_quality_rating)) if quality_result.avg_quality_rating else None,
            "rework_rate": rework_rate,
            "critical_requests": request_result.critical or 0,
            "urgent_requests": request_result.urgent or 0,
            "high_requests": request_result.high or 0,
            "requests_by_category": requests_by_category,
            "cost_by_category": cost_by_category,
            "efficiency_score": Decimal("0.00")  # Will be calculated by model
        }
    
    def _generate_category_metrics(
        self,
        hostel_id: UUID,
        period_start: date,
        period_end: date
    ) -> None:
        """
        Generate category performance metrics for period.
        
        Args:
            hostel_id: Hostel identifier
            period_start: Period start date
            period_end: Period end date
        """
        # Get all categories with requests in period
        category_query = select(
            MaintenanceRequest.category
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.created_at >= datetime.combine(period_start, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(period_end, datetime.max.time()),
            MaintenanceRequest.deleted_at.is_(None)
        ).distinct()
        
        categories = self.session.execute(category_query).scalars().all()
        
        for category in categories:
            # Calculate category-specific metrics
            category_metrics = self._calculate_category_metrics(
                hostel_id,
                category,
                period_start,
                period_end
            )
            
            # Create or update category performance metric
            self.create_category_performance(
                hostel_id=hostel_id,
                category=str(category.value),
                period_start=period_start,
                period_end=period_end,
                **category_metrics
            )
    
    def _calculate_category_metrics(
        self,
        hostel_id: UUID,
        category: MaintenanceCategory,
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Calculate metrics for specific category.
        
        Args:
            hostel_id: Hostel identifier
            category: Maintenance category
            period_start: Period start date
            period_end: Period end date
            
        Returns:
            Category metrics dictionary
        """
        # Request counts
        request_query = select(
            func.count(MaintenanceRequest.id).label("total"),
            func.sum(
                case(
                    (MaintenanceRequest.status == MaintenanceStatus.COMPLETED, 1),
                    else_=0
                )
            ).label("completed"),
            func.sum(
                case(
                    (MaintenanceRequest.status == MaintenanceStatus.PENDING, 1),
                    else_=0
                )
            ).label("pending"),
            func.sum(
                case(
                    (MaintenanceRequest.priority == Priority.HIGH, 1),
                    else_=0
                )
            ).label("high_priority"),
            func.sum(
                case(
                    (MaintenanceRequest.priority == Priority.URGENT, 1),
                    else_=0
                )
            ).label("urgent_priority")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.category == category,
            MaintenanceRequest.created_at >= datetime.combine(period_start, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(period_end, datetime.max.time()),
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        request_result = self.session.execute(request_query).first()
        
        # Cost metrics
        cost_query = select(
            func.sum(MaintenanceCost.actual_cost).label("total_cost"),
            func.avg(MaintenanceCost.actual_cost).label("avg_cost"),
            func.percentile_cont(0.5).within_group(
                MaintenanceCost.actual_cost
            ).label("median_cost")
        ).join(
            MaintenanceRequest,
            MaintenanceCost.maintenance_request_id == MaintenanceRequest.id
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.category == category,
            MaintenanceCost.actual_cost.isnot(None),
            MaintenanceRequest.created_at >= datetime.combine(period_start, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(period_end, datetime.max.time()),
            MaintenanceCost.deleted_at.is_(None)
        )
        
        cost_result = self.session.execute(cost_query).first()
        
        # Time metrics
        time_query = select(
            func.avg(
                extract('epoch', MaintenanceRequest.completed_at - MaintenanceRequest.created_at) / 3600
            ).label("avg_hours"),
            func.sum(
                case(
                    (
                        and_(
                            MaintenanceRequest.completed_at.isnot(None),
                            MaintenanceRequest.deadline.isnot(None),
                            MaintenanceRequest.completed_at <= MaintenanceRequest.deadline
                        ),
                        1
                    ),
                    else_=0
                )
            ).label("on_time")
        ).where(
            MaintenanceRequest.hostel_id == hostel_id,
            MaintenanceRequest.category == category,
            MaintenanceRequest.status == MaintenanceStatus.COMPLETED,
            MaintenanceRequest.created_at >= datetime.combine(period_start, datetime.min.time()),
            MaintenanceRequest.created_at <= datetime.combine(period_end, datetime.max.time()),
            MaintenanceRequest.deleted_at.is_(None)
        )
        
        time_result = self.session.execute(time_query).first()
        
        avg_hours = Decimal(str(time_result.avg_hours)) if time_result.avg_hours else Decimal("0.00")
        avg_days = avg_hours / 24 if avg_hours > 0 else Decimal("0.00")
        
        completed = request_result.completed or 0
        on_time_rate = Decimal("0.00")
        if completed > 0:
            on_time_rate = round(
                Decimal(time_result.on_time or 0) / Decimal(completed) * 100,
                2
            )
        
        return {
            "total_requests": request_result.total or 0,
            "completed_requests": completed,
            "pending_requests": request_result.pending or 0,
            "total_cost": Decimal(str(cost_result.total_cost)) if cost_result.total_cost else Decimal("0.00"),
            "average_cost": Decimal(str(cost_result.avg_cost)) if cost_result.avg_cost else Decimal("0.00"),
            "median_cost": Decimal(str(cost_result.median_cost)) if cost_result.median_cost else None,
            "average_completion_time_hours": avg_hours,
            "average_completion_time_days": avg_days,
            "on_time_completion_rate": on_time_rate,
            "high_priority_count": request_result.high_priority or 0,
            "urgent_priority_count": request_result.urgent_priority or 0,
            "category_performance_score": Decimal("0.00")  # Will be calculated
        }