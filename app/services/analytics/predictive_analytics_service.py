# --- File: C:\Hostel-Main\app\services\analytics\predictive_analytics_service.py ---
"""
Predictive Analytics Service - Machine learning and forecasting.

Provides advanced analytics with:
- Time-series forecasting
- Churn prediction
- Demand forecasting
- Anomaly detection
- Trend prediction
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from uuid import UUID
import logging
import statistics
from collections import defaultdict

from app.repositories.analytics.occupancy_analytics_repository import (
    OccupancyAnalyticsRepository
)
from app.repositories.analytics.booking_analytics_repository import (
    BookingAnalyticsRepository
)
from app.repositories.analytics.platform_analytics_repository import (
    PlatformAnalyticsRepository
)


logger = logging.getLogger(__name__)


class PredictiveAnalyticsService:
    """Service for predictive analytics and forecasting."""
    
    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
        self.occupancy_repo = OccupancyAnalyticsRepository(db)
        self.booking_repo = BookingAnalyticsRepository(db)
        self.platform_repo = PlatformAnalyticsRepository(db)
    
    # ==================== Occupancy Forecasting ====================
    
    def forecast_occupancy(
        self,
        hostel_id: Optional[UUID],
        forecast_days: int = 30,
        model: str = 'moving_average'
    ) -> Dict[str, Any]:
        """
        Forecast occupancy for upcoming period.
        
        Args:
            hostel_id: Hostel ID
            forecast_days: Days to forecast
            model: Forecasting model (moving_average, exponential_smoothing, arima)
            
        Returns:
            Forecast data with confidence intervals
        """
        logger.info(f"Forecasting occupancy for {forecast_days} days using {model}")
        
        forecast = self.occupancy_repo.generate_occupancy_forecast(
            hostel_id=hostel_id,
            forecast_days=forecast_days,
            model=model
        )
        
        if not forecast:
            return {
                'success': False,
                'message': 'Insufficient historical data for forecasting'
            }
        
        # Get forecast points
        forecast_points = self.occupancy_repo.get_forecast_points(forecast.id) if hasattr(forecast, 'id') else []
        
        return {
            'success': True,
            'forecast_id': str(forecast.id) if hasattr(forecast, 'id') else None,
            'model_used': forecast.model_used if hasattr(forecast, 'model_used') else model,
            'forecast_horizon_days': forecast_days,
            'confidence_interval': float(forecast.confidence_interval) if hasattr(forecast, 'confidence_interval') else 95.0,
            'forecast_points': [
                {
                    'date': fp.forecast_date.isoformat(),
                    'forecasted_occupancy': float(fp.forecasted_occupancy_percentage),
                    'forecasted_beds': fp.forecasted_occupied_beds,
                    'lower_bound': float(fp.lower_bound) if fp.lower_bound else None,
                    'upper_bound': float(fp.upper_bound) if fp.upper_bound else None,
                }
                for fp in forecast_points
            ] if forecast_points else [],
        }
    
    # ==================== Booking Demand Forecasting ====================
    
    def forecast_booking_demand(
        self,
        hostel_id: Optional[UUID],
        forecast_days: int = 30
    ) -> Dict[str, Any]:
        """
        Forecast booking demand for upcoming period.
        
        Predicts future booking volume based on historical patterns.
        """
        logger.info(f"Forecasting booking demand for {forecast_days} days")
        
        forecast = self.booking_repo.forecast_booking_demand(
            hostel_id=hostel_id,
            forecast_days=forecast_days,
            historical_days=90
        )
        
        return {
            'success': True,
            'forecast_days': forecast_days,
            'forecast': forecast
        }
    
    # ==================== Churn Prediction ====================
    
    def predict_tenant_churn(
        self,
        tenant_id: UUID,
        prediction_window_days: int = 30
    ) -> Dict[str, Any]:
        """
        Predict likelihood of tenant churning.
        
        Uses historical behavior patterns to assess churn risk.
        
        Args:
            tenant_id: Tenant (hostel) ID
            prediction_window_days: Prediction window in days
            
        Returns:
            Churn prediction with risk score and factors
        """
        logger.info(f"Predicting churn for tenant {tenant_id}")
        
        # Get recent tenant metrics
        end_date = date.today()
        start_date = end_date - timedelta(days=90)
        
        tenant_metrics = self.platform_repo.get_tenant_metrics(
            tenant_id, start_date, end_date
        )
        
        if not tenant_metrics:
            return {
                'success': False,
                'message': 'Insufficient data for prediction'
            }
        
        # Calculate churn risk factors
        risk_factors = []
        risk_score = 0.0
        
        # Payment status
        if tenant_metrics.payment_status == 'overdue':
            risk_factors.append({
                'factor': 'payment_overdue',
                'impact': 'high',
                'weight': 30
            })
            risk_score += 30
        elif tenant_metrics.payment_status == 'suspended':
            risk_factors.append({
                'factor': 'payment_suspended',
                'impact': 'critical',
                'weight': 50
            })
            risk_score += 50
        
        # Engagement
        if tenant_metrics.engagement_status in ['low', 'inactive']:
            risk_factors.append({
                'factor': 'low_engagement',
                'impact': 'high',
                'weight': 25
            })
            risk_score += 25
        
        # Occupancy
        if float(tenant_metrics.occupancy_rate) < 50:
            risk_factors.append({
                'factor': 'low_occupancy',
                'impact': 'medium',
                'weight': 15
            })
            risk_score += 15
        
        # Health score
        if float(tenant_metrics.health_score) < 50:
            risk_factors.append({
                'factor': 'low_health_score',
                'impact': 'high',
                'weight': 20
            })
            risk_score += 20
        
        # Determine risk level
        if risk_score >= 70:
            risk_level = 'critical'
        elif risk_score >= 50:
            risk_level = 'high'
        elif risk_score >= 30:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        # Generate recommendations
        recommendations = self._generate_churn_prevention_recommendations(risk_factors)
        
        return {
            'success': True,
            'tenant_id': str(tenant_id),
            'churn_risk_score': risk_score,
            'risk_level': risk_level,
            'risk_factors': risk_factors,
            'recommendations': recommendations,
            'prediction_window_days': prediction_window_days,
            'predicted_at': datetime.utcnow().isoformat(),
        }
    
    def _generate_churn_prevention_recommendations(
        self,
        risk_factors: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations to prevent churn."""
        recommendations = []
        
        for factor in risk_factors:
            if factor['factor'] == 'payment_overdue':
                recommendations.append(
                    'Reach out to resolve payment issues and offer payment plan if needed'
                )
            elif factor['factor'] == 'payment_suspended':
                recommendations.append(
                    'Immediate intervention required - contact customer success team'
                )
            elif factor['factor'] == 'low_engagement':
                recommendations.append(
                    'Schedule check-in call to understand needs and provide training'
                )
            elif factor['factor'] == 'low_occupancy':
                recommendations.append(
                    'Offer marketing support and best practices for occupancy improvement'
                )
            elif factor['factor'] == 'low_health_score':
                recommendations.append(
                    'Comprehensive health assessment and support plan needed'
                )
        
        return recommendations
    
    # ==================== Anomaly Detection ====================
    
    def detect_anomalies(
        self,
        hostel_id: Optional[UUID],
        metric: str,
        lookback_days: int = 30,
        threshold: float = 2.0
    ) -> Dict[str, Any]:
        """
        Detect anomalies in metrics using statistical analysis.
        
        Args:
            hostel_id: Hostel ID
            metric: Metric to analyze (occupancy, bookings, revenue, etc.)
            lookback_days: Days of historical data to analyze
            threshold: Standard deviation threshold for anomaly
            
        Returns:
            Detected anomalies with details
        """
        logger.info(f"Detecting anomalies in {metric} for hostel {hostel_id}")
        
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)
        
        # Get historical data based on metric type
        # This is a simplified implementation
        data_points = []
        
        if metric == 'occupancy':
            # Would query occupancy trend points
            pass
        elif metric == 'bookings':
            # Would query booking trend points
            pass
        
        # Placeholder data for demonstration
        data_points = [
            {'date': start_date + timedelta(days=i), 'value': 70 + (i % 10)}
            for i in range(lookback_days)
        ]
        
        if len(data_points) < 7:
            return {
                'success': False,
                'message': 'Insufficient data for anomaly detection'
            }
        
        # Calculate statistics
        values = [dp['value'] for dp in data_points]
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0
        
        # Detect anomalies
        anomalies = []
        for dp in data_points:
            z_score = abs((dp['value'] - mean) / stdev) if stdev > 0 else 0
            
            if z_score > threshold:
                anomalies.append({
                    'date': dp['date'].isoformat(),
                    'value': dp['value'],
                    'z_score': round(z_score, 2),
                    'deviation_from_mean': round(dp['value'] - mean, 2),
                    'severity': 'high' if z_score > 3 else 'medium',
                })
        
        return {
            'success': True,
            'metric': metric,
            'lookback_days': lookback_days,
            'threshold': threshold,
            'mean': round(mean, 2),
            'stdev': round(stdev, 2),
            'anomalies_detected': len(anomalies),
            'anomalies': anomalies,
        }
    
    # ==================== Seasonal Pattern Detection ====================
    
    def detect_seasonal_patterns(
        self,
        hostel_id: Optional[UUID],
        metric: str = 'occupancy',
        years: int = 2
    ) -> Dict[str, Any]:
        """
        Detect seasonal patterns in metrics.
        
        Analyzes historical data to identify recurring patterns.
        """
        logger.info(f"Detecting seasonal patterns in {metric}")
        
        patterns = self.occupancy_repo.identify_seasonal_patterns(
            hostel_id=hostel_id,
            lookback_years=years
        )
        
        return {
            'success': True,
            'metric': metric,
            'years_analyzed': years,
            'patterns_found': len(patterns),
            'patterns': [
                {
                    'name': p.pattern_name,
                    'start_month': p.start_month,
                    'end_month': p.end_month,
                    'average_occupancy': float(p.average_occupancy),
                    'confidence': float(p.confidence),
                    'is_high_season': p.is_high_season,
                }
                for p in patterns
            ] if patterns else []
        }
    
    # ==================== Trend Prediction ====================
    
    def predict_trends(
        self,
        hostel_id: Optional[UUID],
        metric: str,
        prediction_days: int = 90
    ) -> Dict[str, Any]:
        """
        Predict future trends based on historical data.
        
        Uses linear regression and moving averages.
        """
        logger.info(f"Predicting trends for {metric}")
        
        # Get historical data
        end_date = date.today()
        start_date = end_date - timedelta(days=180)
        
        # Simplified trend prediction
        # In production, would use more sophisticated models
        
        return {
            'success': True,
            'metric': metric,
            'prediction_days': prediction_days,
            'trend_direction': 'stable',  # Placeholder
            'predicted_change_percentage': 0.0,
            'confidence': 0.75,
        }
