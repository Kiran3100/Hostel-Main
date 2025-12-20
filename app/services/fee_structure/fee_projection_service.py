# --- File: C:\Hostel-Main\app\services\fee_structure\fee_projection_service.py ---
"""
Fee Projection Service

Business logic layer for fee projections and revenue forecasting.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.fee_structure.fee_calculation import FeeProjection
from app.repositories.fee_structure.fee_calculation_repository import (
    FeeProjectionRepository,
)
from app.repositories.fee_structure.fee_structure_repository import (
    FeeStructureRepository,
)
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
)
from app.core.logging import logger


class FeeProjectionService:
    """
    Fee Projection Service
    
    Provides revenue forecasting and projection capabilities.
    """
    
    def __init__(self, session: Session):
        """
        Initialize service with database session.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.projection_repo = FeeProjectionRepository(session)
        self.fee_structure_repo = FeeStructureRepository(session)
    
    # ============================================================
    # Core Projection Operations
    # ============================================================
    
    def create_projection(
        self,
        fee_structure_id: UUID,
        projection_period_months: int,
        user_id: UUID,
        projected_occupancy: Decimal,
        projected_bookings: int,
        projection_model: str = "linear",
        confidence_level: Optional[Decimal] = None,
        projection_data: Optional[Dict[str, Any]] = None
    ) -> FeeProjection:
        """
        Create a new fee projection.
        
        Args:
            fee_structure_id: Fee structure identifier
            projection_period_months: Projection period in months
            user_id: User creating projection
            projected_occupancy: Projected occupancy percentage
            projected_bookings: Projected number of bookings
            projection_model: Model used (linear, exponential, seasonal, ml)
            confidence_level: Confidence level percentage
            projection_data: Additional projection data
            
        Returns:
            Created FeeProjection instance
            
        Raises:
            NotFoundException: If fee structure not found
            ValidationException: If validation fails
        """
        logger.info(
            f"Creating projection for fee structure {fee_structure_id}, "
            f"period={projection_period_months} months"
        )
        
        # Get fee structure
        fee_structure = self.fee_structure_repo.find_by_id(fee_structure_id)
        if not fee_structure:
            raise NotFoundException(f"Fee structure {fee_structure_id} not found")
        
        # Calculate projected revenue
        projected_revenue = self._calculate_projected_revenue(
            fee_structure=fee_structure,
            projection_period_months=projection_period_months,
            projected_occupancy=projected_occupancy,
            projected_bookings=projected_bookings
        )
        
        # Prepare audit context
        audit_context = {
            'user_id': user_id,
            'action': 'create_projection',
            'timestamp': datetime.utcnow()
        }
        
        try:
            projection = self.projection_repo.create_projection(
                fee_structure_id=fee_structure_id,
                projection_date=Date.today(),
                projection_period_months=projection_period_months,
                projected_revenue=projected_revenue,
                projected_occupancy=projected_occupancy,
                projected_bookings=projected_bookings,
                projection_model=projection_model,
                audit_context=audit_context,
                confidence_level=confidence_level,
                projection_data=projection_data
            )
            
            self.session.commit()
            
            logger.info(f"Projection created: {projection.id}")
            return projection
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating projection: {str(e)}")
            raise
    
    def generate_revenue_forecast(
        self,
        fee_structure_id: UUID,
        months_ahead: int,
        user_id: UUID,
        historical_months: int = 6,
        growth_rate: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Generate revenue forecast based on historical data.
        
        Args:
            fee_structure_id: Fee structure identifier
            months_ahead: Number of months to forecast
            user_id: User generating forecast
            historical_months: Months of historical data to use
            growth_rate: Optional fixed growth rate
            
        Returns:
            Dictionary with forecast data
        """
        logger.info(f"Generating revenue forecast for {months_ahead} months")
        
        # Get fee structure
        fee_structure = self.fee_structure_repo.find_by_id(fee_structure_id)
        if not fee_structure:
            raise NotFoundException(f"Fee structure {fee_structure_id} not found")
        
        # Get historical data
        from app.repositories.fee_structure.fee_calculation_repository import (
            FeeCalculationRepository
        )
        calc_repo = FeeCalculationRepository(self.session)
        
        historical_start = Date.fromordinal(
            Date.today().toordinal() - (historical_months * 30)
        )
        
        stats = calc_repo.get_calculation_statistics(
            fee_structure_id=fee_structure_id,
            start_date=historical_start
        )
        
        # Calculate growth rate if not provided
        if growth_rate is None:
            growth_rate = self._estimate_growth_rate(
                fee_structure_id=fee_structure_id,
                historical_months=historical_months
            )
        
        # Generate monthly forecasts
        monthly_forecasts = []
        base_revenue = Decimal(str(stats.get('sum_total', 0))) / historical_months
        
        for month in range(1, months_ahead + 1):
            projected = base_revenue * ((1 + growth_rate / 100) ** month)
            
            monthly_forecasts.append({
                'month': month,
                'projected_revenue': float(projected),
                'confidence_level': float(max(Decimal('50.00'), 
                                            Decimal('95.00') - (month * Decimal('5.00'))))
            })
        
        total_projected = sum(f['projected_revenue'] for f in monthly_forecasts)
        
        forecast = {
            'fee_structure_id': str(fee_structure_id),
            'forecast_period_months': months_ahead,
            'historical_period_months': historical_months,
            'base_monthly_revenue': float(base_revenue),
            'growth_rate_percentage': float(growth_rate),
            'total_projected_revenue': total_projected,
            'monthly_forecasts': monthly_forecasts,
            'assumptions': {
                'based_on_historical_avg': True,
                'includes_seasonality': False,
                'confidence_decreases_over_time': True
            }
        }
        
        logger.info(f"Forecast generated: total={total_projected}")
        
        return forecast
    
    def create_seasonal_projection(
        self,
        fee_structure_id: UUID,
        projection_period_months: int,
        user_id: UUID,
        seasonal_factors: Dict[int, Decimal]
    ) -> FeeProjection:
        """
        Create projection with seasonal adjustments.
        
        Args:
            fee_structure_id: Fee structure identifier
            projection_period_months: Projection period
            user_id: User creating projection
            seasonal_factors: Month-to-factor mapping (1-12: factor)
            
        Returns:
            Created FeeProjection with seasonal data
        """
        logger.info("Creating seasonal projection")
        
        # Get base projection data
        from app.repositories.fee_structure.fee_calculation_repository import (
            FeeCalculationRepository
        )
        calc_repo = FeeCalculationRepository(self.session)
        
        base_stats = calc_repo.get_calculation_statistics(
            fee_structure_id=fee_structure_id
        )
        
        # Calculate seasonal adjusted revenue
        base_monthly = Decimal(str(base_stats.get('average_total', 0)))
        seasonal_adjusted = Decimal('0.00')
        
        current_month = Date.today().month
        for month_offset in range(projection_period_months):
            month = ((current_month + month_offset - 1) % 12) + 1
            factor = seasonal_factors.get(month, Decimal('1.00'))
            seasonal_adjusted += base_monthly * factor
        
        # Create projection with seasonal data
        projection_data = {
            'seasonal_factors': {str(k): float(v) for k, v in seasonal_factors.items()},
            'base_monthly_revenue': float(base_monthly),
            'seasonal_adjusted_total': float(seasonal_adjusted)
        }
        
        return self.create_projection(
            fee_structure_id=fee_structure_id,
            projection_period_months=projection_period_months,
            user_id=user_id,
            projected_occupancy=Decimal('80.00'),  # Estimated
            projected_bookings=int(base_stats.get('total_calculations', 0)),
            projection_model='seasonal',
            projection_data=projection_data
        )
    
    # ============================================================
    # Projection Retrieval
    # ============================================================
    
    def get_projection(self, projection_id: UUID) -> FeeProjection:
        """Get projection by ID."""
        projection = self.projection_repo.find_by_id(projection_id)
        if not projection:
            raise NotFoundException(f"Projection {projection_id} not found")
        return projection
    
    def get_projections_by_fee_structure(
        self,
        fee_structure_id: UUID,
        start_date: Optional[Date] = None,
        end_date: Optional[Date] = None
    ) -> List[FeeProjection]:
        """Get all projections for a fee structure."""
        return self.projection_repo.find_by_fee_structure(
            fee_structure_id=fee_structure_id,
            start_date=start_date,
            end_date=end_date
        )
    
    def get_latest_projection(
        self,
        fee_structure_id: UUID
    ) -> Optional[FeeProjection]:
        """Get most recent projection."""
        return self.projection_repo.get_latest_projection(fee_structure_id)
    
    # ============================================================
    # Analytics and Comparison
    # ============================================================
    
    def compare_projection_vs_actual(
        self,
        projection_id: UUID,
        actual_revenue: Decimal,
        actual_occupancy: Decimal
    ) -> Dict[str, Any]:
        """
        Compare projection with actual results.
        
        Args:
            projection_id: Projection identifier
            actual_revenue: Actual revenue achieved
            actual_occupancy: Actual occupancy achieved
            
        Returns:
            Dictionary with comparison metrics
        """
        projection = self.get_projection(projection_id)
        
        return self.projection_repo.get_projection_accuracy(
            fee_structure_id=projection.fee_structure_id,
            actual_revenue=actual_revenue,
            actual_occupancy=actual_occupancy,
            projection_date=projection.projection_date
        )
    
    def analyze_projection_trends(
        self,
        fee_structure_id: UUID,
        months: int = 12
    ) -> Dict[str, Any]:
        """
        Analyze projection trends over time.
        
        Args:
            fee_structure_id: Fee structure identifier
            months: Number of months to analyze
            
        Returns:
            Dictionary with trend analysis
        """
        start_date = Date.fromordinal(Date.today().toordinal() - (months * 30))
        
        projections = self.projection_repo.find_by_fee_structure(
            fee_structure_id=fee_structure_id,
            start_date=start_date
        )
        
        if not projections:
            return {
                'error': 'No projections found for analysis'
            }
        
        # Calculate trends
        revenues = [float(p.projected_revenue) for p in projections]
        occupancies = [float(p.projected_occupancy) for p in projections]
        
        return {
            'fee_structure_id': str(fee_structure_id),
            'period_months': months,
            'projection_count': len(projections),
            'revenue_trend': {
                'average': sum(revenues) / len(revenues),
                'minimum': min(revenues),
                'maximum': max(revenues),
                'trend': 'increasing' if revenues[-1] > revenues[0] else 'decreasing'
            },
            'occupancy_trend': {
                'average': sum(occupancies) / len(occupancies),
                'minimum': min(occupancies),
                'maximum': max(occupancies),
                'trend': 'increasing' if occupancies[-1] > occupancies[0] else 'decreasing'
            }
        }
    
    # ============================================================
    # Helper Methods
    # ============================================================
    
    def _calculate_projected_revenue(
        self,
        fee_structure: Any,
        projection_period_months: int,
        projected_occupancy: Decimal,
        projected_bookings: int
    ) -> Decimal:
        """Calculate projected revenue."""
        # Simple calculation: bookings * average fee * months * occupancy factor
        avg_monthly_fee = fee_structure.amount
        
        projected_revenue = (
            avg_monthly_fee * 
            projected_bookings * 
            projection_period_months * 
            (projected_occupancy / 100)
        )
        
        return projected_revenue.quantize(Decimal('0.01'))
    
    def _estimate_growth_rate(
        self,
        fee_structure_id: UUID,
        historical_months: int
    ) -> Decimal:
        """Estimate growth rate from historical data."""
        from app.repositories.fee_structure.fee_calculation_repository import (
            FeeCalculationRepository
        )
        calc_repo = FeeCalculationRepository(self.session)
        
        trends = calc_repo.get_calculation_trends(
            fee_structure_id=fee_structure_id,
            months=historical_months
        )
        
        if len(trends) < 2:
            return Decimal('0.00')  # No growth data
        
        # Calculate simple growth rate
        first_month_revenue = Decimal(str(trends[0]['total_revenue']))
        last_month_revenue = Decimal(str(trends[-1]['total_revenue']))
        
        if first_month_revenue == 0:
            return Decimal('0.00')
        
        growth = ((last_month_revenue - first_month_revenue) / first_month_revenue * 100)
        growth_per_month = growth / len(trends)
        
        return growth_per_month.quantize(Decimal('0.01'))