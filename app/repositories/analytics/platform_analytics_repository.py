"""
Platform Analytics Repository for multi-tenant oversight.

Provides comprehensive platform-wide analytics with:
- Tenant performance tracking
- Growth metrics and trends
- Churn analysis and prediction
- System health monitoring
- Platform usage analytics
- Revenue aggregation
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import and_, or_, func, select, case, desc
from sqlalchemy.orm import Session, joinedload
from uuid import UUID

from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.models.analytics.platform_analytics import (
    TenantMetrics,
    PlatformMetrics,
    MonthlyMetric,
    GrowthMetrics,
    ChurnAnalysis,
    SystemHealthMetrics,
    PlatformUsageAnalytics,
    RevenueMetrics,
)


class PlatformAnalyticsRepository(BaseRepository):
    """Repository for platform-wide analytics operations."""
    
    def __init__(self, db: Session):
        super().__init__(db)
    
    # ==================== Tenant Metrics ====================
    
    def create_tenant_metrics(
        self,
        tenant_id: UUID,
        period_start: date,
        period_end: date,
        metrics_data: Dict[str, Any]
    ) -> TenantMetrics:
        """Create or update tenant performance metrics."""
        # Calculate health score
        health_score = self._calculate_tenant_health_score(metrics_data)
        metrics_data['health_score'] = health_score
        
        # Calculate churn risk
        churn_risk = self._calculate_churn_risk_score(metrics_data)
        metrics_data['churn_risk_score'] = churn_risk
        
        # Determine if at risk
        metrics_data['is_at_risk'] = float(churn_risk) > 70
        
        # Calculate revenue per bed
        if metrics_data.get('total_beds', 0) > 0:
            revenue_per_bed = (
                metrics_data.get('subscription_mrr', 0) / 
                metrics_data['total_beds']
            )
            metrics_data['revenue_per_bed'] = Decimal(str(round(revenue_per_bed, 2)))
        else:
            metrics_data['revenue_per_bed'] = Decimal('0.00')
        
        # Determine engagement status
        engagement_status = self._determine_engagement_status(metrics_data)
        metrics_data['engagement_status'] = engagement_status
        
        existing = self.db.query(TenantMetrics).filter(
            and_(
                TenantMetrics.tenant_id == tenant_id,
                TenantMetrics.period_start == period_start,
                TenantMetrics.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in metrics_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        metrics = TenantMetrics(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            **metrics_data
        )
        
        self.db.add(metrics)
        self.db.commit()
        self.db.refresh(metrics)
        
        return metrics
    
    def get_tenant_metrics(
        self,
        tenant_id: UUID,
        period_start: date,
        period_end: date
    ) -> Optional[TenantMetrics]:
        """Get tenant metrics for period."""
        return self.db.query(TenantMetrics).filter(
            and_(
                TenantMetrics.tenant_id == tenant_id,
                TenantMetrics.period_start == period_start,
                TenantMetrics.period_end == period_end
            )
        ).first()
    
    def get_all_tenant_metrics(
        self,
        period_start: date,
        period_end: date
    ) -> List[TenantMetrics]:
        """Get metrics for all tenants in period."""
        return self.db.query(TenantMetrics).filter(
            and_(
                TenantMetrics.period_start == period_start,
                TenantMetrics.period_end == period_end
            )
        ).all()
    
    def get_at_risk_tenants(
        self,
        period_start: date,
        period_end: date,
        risk_threshold: float = 70.0
    ) -> List[TenantMetrics]:
        """Get tenants at risk of churning."""
        return self.db.query(TenantMetrics).filter(
            and_(
                TenantMetrics.period_start == period_start,
                TenantMetrics.period_end == period_end,
                TenantMetrics.churn_risk_score >= risk_threshold
            )
        ).order_by(TenantMetrics.churn_risk_score.desc()).all()
    
    def _calculate_tenant_health_score(
        self,
        metrics_data: Dict[str, Any]
    ) -> Decimal:
        """
        Calculate tenant health score (0-100).
        
        Factors:
        - Occupancy rate: 30%
        - Active users ratio: 25%
        - Payment status: 25%
        - Engagement (DAU/MAU): 20%
        """
        score = 0.0
        
        # Occupancy rate
        occupancy = float(metrics_data.get('occupancy_rate', 0))
        score += (occupancy / 100) * 30
        
        # Active users ratio
        total_students = metrics_data.get('total_students', 0)
        active_students = metrics_data.get('active_students', 0)
        if total_students > 0:
            active_ratio = (active_students / total_students) * 100
            score += (active_ratio / 100) * 25
        
        # Payment status
        payment_status = metrics_data.get('payment_status', 'overdue')
        if payment_status == 'current':
            score += 25
        elif payment_status == 'overdue':
            score += 10
        else:  # suspended
            score += 0
        
        # Engagement (DAU/MAU ratio)
        dau = metrics_data.get('daily_active_users', 0)
        mau = metrics_data.get('monthly_active_users', 0)
        if mau > 0:
            engagement_ratio = (dau / mau) * 100
            score += min(engagement_ratio, 100) * 0.20
        
        return Decimal(str(round(score, 2)))
    
    def _calculate_churn_risk_score(
        self,
        metrics_data: Dict[str, Any]
    ) -> Decimal:
        """
        Calculate churn risk score (0-100, higher = more risk).
        
        Risk factors:
        - Payment issues: 30%
        - Low engagement: 25%
        - Low occupancy: 20%
        - Declining usage: 15%
        - Support tickets: 10%
        """
        risk_score = 0.0
        
        # Payment issues
        payment_status = metrics_data.get('payment_status', 'current')
        if payment_status == 'suspended':
            risk_score += 30
        elif payment_status == 'overdue':
            risk_score += 20
        
        # Low engagement
        engagement = metrics_data.get('engagement_status', 'low')
        if engagement == 'inactive':
            risk_score += 25
        elif engagement == 'low':
            risk_score += 20
        elif engagement == 'moderate':
            risk_score += 10
        
        # Low occupancy
        occupancy = float(metrics_data.get('occupancy_rate', 0))
        if occupancy < 50:
            risk_score += 20
        elif occupancy < 70:
            risk_score += 10
        
        # Declining usage (simplified - would compare to previous period)
        dau = metrics_data.get('daily_active_users', 0)
        if dau == 0:
            risk_score += 15
        elif dau < 5:
            risk_score += 10
        
        # Support load (placeholder)
        risk_score += 0  # Would factor in support ticket volume
        
        return Decimal(str(round(risk_score, 2)))
    
    def _determine_engagement_status(
        self,
        metrics_data: Dict[str, Any]
    ) -> str:
        """Determine tenant engagement status."""
        dau = metrics_data.get('daily_active_users', 0)
        mau = metrics_data.get('monthly_active_users', 0)
        
        if mau == 0:
            return 'inactive'
        
        engagement_ratio = (dau / mau) * 100
        
        if engagement_ratio >= 40:
            return 'highly_active'
        elif engagement_ratio >= 25:
            return 'active'
        elif engagement_ratio >= 15:
            return 'moderate'
        elif engagement_ratio >= 5:
            return 'low'
        else:
            return 'inactive'
    
    # ==================== Platform Metrics ====================
    
    def create_platform_metrics(
        self,
        period_start: date,
        period_end: date,
        metrics_data: Dict[str, Any]
    ) -> PlatformMetrics:
        """Create or update platform-wide metrics."""
        # Calculate activation rate
        total_hostels = metrics_data.get('total_hostels', 0)
        active_hostels = metrics_data.get('active_hostels', 0)
        
        if total_hostels > 0:
            activation_rate = Decimal(str((active_hostels / total_hostels) * 100))
        else:
            activation_rate = Decimal('0.00')
        
        metrics_data['activation_rate'] = activation_rate
        
        # Estimate trial conversion potential
        on_trial = metrics_data.get('hostels_on_trial', 0)
        # Assume 30% conversion rate
        trial_conversion_potential = int(on_trial * 0.3)
        metrics_data['trial_conversion_potential'] = trial_conversion_potential
        
        existing = self.db.query(PlatformMetrics).filter(
            and_(
                PlatformMetrics.period_start == period_start,
                PlatformMetrics.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in metrics_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        metrics = PlatformMetrics(
            period_start=period_start,
            period_end=period_end,
            **metrics_data
        )
        
        self.db.add(metrics)
        self.db.commit()
        self.db.refresh(metrics)
        
        return metrics
    
    def get_platform_metrics(
        self,
        period_start: date,
        period_end: date
    ) -> Optional[PlatformMetrics]:
        """Get platform metrics for period."""
        return self.db.query(PlatformMetrics).filter(
            and_(
                PlatformMetrics.period_start == period_start,
                PlatformMetrics.period_end == period_end
            )
        ).first()
    
    def get_platform_metrics_trend(
        self,
        start_date: date,
        end_date: date
    ) -> List[PlatformMetrics]:
        """Get platform metrics trend over time."""
        return self.db.query(PlatformMetrics).filter(
            and_(
                PlatformMetrics.period_start >= start_date,
                PlatformMetrics.period_end <= end_date
            )
        ).order_by(PlatformMetrics.period_start.asc()).all()
    
    # ==================== Growth Metrics ====================
    
    def create_growth_metrics(
        self,
        period_start: date,
        period_end: date,
        growth_data: Dict[str, Any]
    ) -> GrowthMetrics:
        """Create or update growth metrics."""
        # Calculate is_growing flag
        net_hostel_growth = growth_data.get('net_hostel_growth', 0)
        revenue_growth_rate = float(growth_data.get('revenue_growth_rate', 0))
        
        is_growing = (
            net_hostel_growth > 0 and 
            revenue_growth_rate > 0
        )
        growth_data['is_growing'] = is_growing
        
        # Calculate growth health score
        health_score = self._calculate_growth_health_score(growth_data)
        growth_data['growth_health_score'] = health_score
        
        existing = self.db.query(GrowthMetrics).filter(
            and_(
                GrowthMetrics.period_start == period_start,
                GrowthMetrics.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in growth_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        metrics = GrowthMetrics(
            period_start=period_start,
            period_end=period_end,
            **growth_data
        )
        
        self.db.add(metrics)
        self.db.commit()
        self.db.refresh(metrics)
        
        return metrics
    
    def get_growth_metrics(
        self,
        period_start: date,
        period_end: date
    ) -> Optional[GrowthMetrics]:
        """Get growth metrics for period."""
        return self.db.query(GrowthMetrics).filter(
            and_(
                GrowthMetrics.period_start == period_start,
                GrowthMetrics.period_end == period_end
            )
        ).first()
    
    def add_monthly_metrics(
        self,
        growth_metrics_id: UUID,
        monthly_data: List[Dict[str, Any]]
    ) -> List[MonthlyMetric]:
        """Add monthly metric data points."""
        created_metrics = []
        
        for data in monthly_data:
            existing = self.db.query(MonthlyMetric).filter(
                and_(
                    MonthlyMetric.growth_metrics_id == growth_metrics_id,
                    MonthlyMetric.metric_key == data['metric_key'],
                    MonthlyMetric.month == data['month']
                )
            ).first()
            
            if existing:
                existing.value = data['value']
                if 'label' in data:
                    existing.label = data['label']
                created_metrics.append(existing)
            else:
                metric = MonthlyMetric(
                    growth_metrics_id=growth_metrics_id,
                    **data
                )
                self.db.add(metric)
                created_metrics.append(metric)
        
        self.db.commit()
        for metric in created_metrics:
            self.db.refresh(metric)
        
        return created_metrics
    
    def _calculate_growth_health_score(
        self,
        growth_data: Dict[str, Any]
    ) -> Decimal:
        """
        Calculate growth health score (0-100).
        
        Factors:
        - Hostel growth rate: 30%
        - Revenue growth rate: 30%
        - User growth rate: 20%
        - MRR growth rate: 20%
        """
        score = 0.0
        
        # Hostel growth (normalize to 0-100)
        hostel_growth = float(growth_data.get('hostel_growth_rate', 0))
        score += min(max(hostel_growth, 0), 100) * 0.30
        
        # Revenue growth
        revenue_growth = float(growth_data.get('revenue_growth_rate', 0))
        score += min(max(revenue_growth, 0), 100) * 0.30
        
        # User growth
        user_growth = float(growth_data.get('user_growth_rate', 0))
        score += min(max(user_growth, 0), 100) * 0.20
        
        # MRR growth
        mrr_growth = float(growth_data.get('mrr_growth_rate', 0))
        score += min(max(mrr_growth, 0), 100) * 0.20
        
        return Decimal(str(round(score, 2)))
    
    # ==================== Churn Analysis ====================
    
    def create_churn_analysis(
        self,
        period_start: date,
        period_end: date,
        churn_data: Dict[str, Any]
    ) -> ChurnAnalysis:
        """Create or update churn analysis."""
        # Determine churn risk status
        churn_rate = float(churn_data.get('churn_rate', 0))
        
        if churn_rate < 2:
            risk_status = 'low'
        elif churn_rate < 5:
            risk_status = 'moderate'
        elif churn_rate < 10:
            risk_status = 'high'
        else:
            risk_status = 'critical'
        
        churn_data['churn_risk_status'] = risk_status
        
        # Identify top churn reason
        if churn_data.get('churn_reasons'):
            reasons = churn_data['churn_reasons']
            top_reason = max(reasons.items(), key=lambda x: x[1])[0]
            churn_data['top_churn_reason'] = top_reason
        
        existing = self.db.query(ChurnAnalysis).filter(
            and_(
                ChurnAnalysis.period_start == period_start,
                ChurnAnalysis.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in churn_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        analysis = ChurnAnalysis(
            period_start=period_start,
            period_end=period_end,
            **churn_data
        )
        
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        
        return analysis
    
    def get_churn_analysis(
        self,
        period_start: date,
        period_end: date
    ) -> Optional[ChurnAnalysis]:
        """Get churn analysis for period."""
        return self.db.query(ChurnAnalysis).filter(
            and_(
                ChurnAnalysis.period_start == period_start,
                ChurnAnalysis.period_end == period_end
            )
        ).first()
    
    # ==================== System Health ====================
    
    def create_system_health_metrics(
        self,
        period_start: date,
        period_end: date,
        health_data: Dict[str, Any]
    ) -> SystemHealthMetrics:
        """Create or update system health metrics."""
        # Determine health status
        uptime = float(health_data.get('uptime_percentage', 0))
        error_rate = float(health_data.get('error_rate_percentage', 0))
        avg_response = float(health_data.get('average_response_time_ms', 0))
        
        health_status = self._determine_system_health_status(
            uptime, error_rate, avg_response
        )
        health_data['health_status'] = health_status
        
        # Assign performance grade
        performance_grade = self._assign_system_performance_grade(health_data)
        health_data['performance_grade'] = performance_grade
        
        existing = self.db.query(SystemHealthMetrics).filter(
            and_(
                SystemHealthMetrics.period_start == period_start,
                SystemHealthMetrics.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in health_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        metrics = SystemHealthMetrics(
            period_start=period_start,
            period_end=period_end,
            **health_data
        )
        
        self.db.add(metrics)
        self.db.commit()
        self.db.refresh(metrics)
        
        return metrics
    
    def _determine_system_health_status(
        self,
        uptime: float,
        error_rate: float,
        avg_response_ms: float
    ) -> str:
        """Determine overall system health status."""
        if uptime >= 99.9 and error_rate < 0.1 and avg_response_ms < 200:
            return 'excellent'
        elif uptime >= 99.5 and error_rate < 0.5 and avg_response_ms < 500:
            return 'good'
        elif uptime >= 99.0 and error_rate < 1.0 and avg_response_ms < 1000:
            return 'fair'
        else:
            return 'poor'
    
    def _assign_system_performance_grade(
        self,
        health_data: Dict[str, Any]
    ) -> str:
        """Assign letter grade to system performance."""
        uptime = float(health_data.get('uptime_percentage', 0))
        
        if uptime >= 99.99:
            return 'A+'
        elif uptime >= 99.95:
            return 'A'
        elif uptime >= 99.9:
            return 'A-'
        elif uptime >= 99.5:
            return 'B+'
        elif uptime >= 99.0:
            return 'B'
        elif uptime >= 98.5:
            return 'B-'
        elif uptime >= 98.0:
            return 'C+'
        else:
            return 'C'
    
    # ==================== Platform Usage ====================
    
    def create_platform_usage_analytics(
        self,
        period_start: date,
        period_end: date,
        usage_data: Dict[str, Any]
    ) -> PlatformUsageAnalytics:
        """Create or update platform usage analytics."""
        # Identify most used module
        if usage_data.get('requests_by_module'):
            modules = usage_data['requests_by_module']
            most_used = max(modules.items(), key=lambda x: x[1])[0]
            usage_data['most_used_module'] = most_used
        
        # Determine platform health
        error_rate = float(usage_data.get('api_error_rate', 0))
        
        if error_rate < 0.1:
            health_indicator = 'healthy'
        elif error_rate < 0.5:
            health_indicator = 'stable'
        elif error_rate < 1.0:
            health_indicator = 'degraded'
        else:
            health_indicator = 'critical'
        
        usage_data['platform_health_indicator'] = health_indicator
        
        existing = self.db.query(PlatformUsageAnalytics).filter(
            and_(
                PlatformUsageAnalytics.period_start == period_start,
                PlatformUsageAnalytics.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in usage_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        analytics = PlatformUsageAnalytics(
            period_start=period_start,
            period_end=period_end,
            **usage_data
        )
        
        self.db.add(analytics)
        self.db.commit()
        self.db.refresh(analytics)
        
        return analytics
    
    # ==================== Revenue Metrics ====================
    
    def create_revenue_metrics(
        self,
        period_start: date,
        period_end: date,
        revenue_data: Dict[str, Any]
    ) -> RevenueMetrics:
        """Create or update platform revenue metrics."""
        # Calculate revenue diversity score
        diversity_score = self._calculate_revenue_diversity(revenue_data)
        revenue_data['revenue_diversity_score'] = diversity_score
        
        # Calculate net new MRR
        new_customer_rev = float(revenue_data.get('new_customer_revenue', 0))
        expansion_rev = float(revenue_data.get('expansion_revenue', 0))
        churned_rev = float(revenue_data.get('churned_revenue', 0))
        
        net_new_mrr = Decimal(str(new_customer_rev + expansion_rev - churned_rev))
        revenue_data['net_new_mrr'] = net_new_mrr
        
        existing = self.db.query(RevenueMetrics).filter(
            and_(
                RevenueMetrics.period_start == period_start,
                RevenueMetrics.period_end == period_end
            )
        ).first()
        
        if existing:
            for key, value in revenue_data.items():
                setattr(existing, key, value)
            
            existing.calculated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        
        metrics = RevenueMetrics(
            period_start=period_start,
            period_end=period_end,
            **revenue_data
        )
        
        self.db.add(metrics)
        self.db.commit()
        self.db.refresh(metrics)
        
        return metrics
    
    def _calculate_revenue_diversity(
        self,
        revenue_data: Dict[str, Any]
    ) -> Decimal:
        """
        Calculate revenue diversity score (0-100).
        
        Higher score = more diversified revenue sources.
        Uses Herfindahl-Hirschman Index (HHI) inverse.
        """
        total_revenue = float(revenue_data.get('total_revenue', 0))
        
        if total_revenue == 0:
            return Decimal('0.00')
        
        # Get revenue by plan
        revenue_by_plan = revenue_data.get('revenue_by_plan', {})
        
        if not revenue_by_plan:
            return Decimal('50.00')  # Default moderate diversity
        
        # Calculate HHI
        hhi = 0.0
        for plan_revenue in revenue_by_plan.values():
            market_share = float(plan_revenue) / total_revenue
            hhi += market_share ** 2
        
        # Convert HHI to diversity score (inverse relationship)
        # HHI ranges from 1/n to 1 (where n is number of plans)
        # Perfect diversity (equal split) = 1/n, monopoly = 1
        
        num_plans = len(revenue_by_plan)
        if num_plans == 0:
            return Decimal('0.00')
        
        perfect_diversity_hhi = 1 / num_plans
        
        # Normalize to 0-100 scale
        if hhi <= perfect_diversity_hhi:
            diversity_score = 100.0
        else:
            # Linear scale from perfect to monopoly
            diversity_score = (1 - hhi) / (1 - perfect_diversity_hhi) * 100
        
        return Decimal(str(round(max(0, min(100, diversity_score)), 2)))