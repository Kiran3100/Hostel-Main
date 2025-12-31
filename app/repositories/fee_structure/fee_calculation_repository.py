# --- File: C:\Hostel-Main\app\repositories\fee_structure\fee_calculation_repository.py ---
"""
Fee Calculation Repository

Manages fee calculations, estimates, and projections with comprehensive
calculation logic and historical tracking.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
import typing
from uuid import UUID

from sqlalchemy import and_, or_, func, case, select, desc
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.fee_structure.fee_calculation import FeeCalculation, FeeProjection
from app.models.base.enums import RoomType, FeeType
from app.repositories.base.base_repository import BaseRepository
from app.core.exceptions import NotFoundError, ValidationError

class FeeCalculationRepository(BaseRepository[FeeCalculation]):
    """
    Fee Calculation Repository
    
    Manages fee calculations with comprehensive querying,
    analytics, and historical tracking capabilities.
    """
    
    def __init__(self, session: Session):
        super().__init__(FeeCalculation, session)
    
    # ============================================================
    # Core CRUD Operations
    # ============================================================
    
    def create_fee_calculation(
        self,
        fee_structure_id: UUID,
        calculation_type: str,
        room_type: RoomType,
        fee_type: FeeType,
        stay_duration_months: int,
        move_in_date: Date,
        monthly_rent: Decimal,
        security_deposit: Decimal,
        audit_context: Dict[str, Any],
        **kwargs
    ) -> FeeCalculation:
        """
        Create a new fee calculation.
        
        Args:
            fee_structure_id: Fee structure identifier
            calculation_type: Type of calculation
            room_type: Room type
            fee_type: Fee type
            stay_duration_months: Duration in months
            move_in_date: Move-in date
            monthly_rent: Monthly rent amount
            security_deposit: Security deposit amount
            audit_context: Audit information
            **kwargs: Additional calculation attributes
            
        Returns:
            Created FeeCalculation instance
        """
        self._validate_calculation(
            calculation_type,
            stay_duration_months,
            monthly_rent,
            security_deposit,
            kwargs
        )
        
        # Calculate totals
        subtotal, total_payable, first_month_total, monthly_recurring = self._calculate_totals(
            monthly_rent=monthly_rent,
            security_deposit=security_deposit,
            stay_duration_months=stay_duration_months,
            mess_charges=kwargs.get('mess_charges_total', Decimal('0')),
            utility_charges=kwargs.get('utility_charges_estimated', Decimal('0')),
            other_charges=kwargs.get('other_charges', Decimal('0')),
            discount=kwargs.get('discount_applied', Decimal('0')),
            tax_percentage=kwargs.get('tax_percentage', Decimal('0'))
        )
        
        calculation = FeeCalculation(
            fee_structure_id=fee_structure_id,
            calculation_type=calculation_type,
            room_type=room_type,
            fee_type=fee_type,
            stay_duration_months=stay_duration_months,
            move_in_date=move_in_date,
            monthly_rent=monthly_rent,
            security_deposit=security_deposit,
            subtotal=subtotal,
            total_payable=total_payable,
            first_month_total=first_month_total,
            monthly_recurring=monthly_recurring,
            calculation_date=Date.today(),
            **kwargs
        )
        
        self._apply_audit(calculation, audit_context)
        self.session.add(calculation)
        self.session.flush()
        
        return calculation
    
    # ============================================================
    # Query Operations
    # ============================================================
    
    def find_by_student(
        self,
        student_id: UUID,
        calculation_type: Optional[str] = None,
        start_date: Optional[Date] = None,
        end_date: Optional[Date] = None
    ) -> List[FeeCalculation]:
        """
        Find all fee calculations for a student.
        
        Args:
            student_id: Student identifier
            calculation_type: Optional calculation type filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List of FeeCalculation instances
        """
        query = self.session.query(FeeCalculation).filter(
            FeeCalculation.student_id == student_id
        )
        
        if calculation_type:
            query = query.filter(FeeCalculation.calculation_type == calculation_type)
        
        if start_date:
            query = query.filter(FeeCalculation.calculation_date >= start_date)
        
        if end_date:
            query = query.filter(FeeCalculation.calculation_date <= end_date)
        
        return query.order_by(FeeCalculation.calculation_date.desc()).all()
    
    def find_by_booking(
        self,
        booking_id: UUID
    ) -> List[FeeCalculation]:
        """
        Find all fee calculations for a booking.
        
        Args:
            booking_id: Booking identifier
            
        Returns:
            List of FeeCalculation instances
        """
        return self.session.query(FeeCalculation).filter(
            FeeCalculation.booking_id == booking_id
        ).order_by(FeeCalculation.calculation_date.desc()).all()
    
    def find_by_fee_structure(
        self,
        fee_structure_id: UUID,
        calculation_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[FeeCalculation]:
        """
        Find calculations for a specific fee structure.
        
        Args:
            fee_structure_id: Fee structure identifier
            calculation_type: Optional calculation type filter
            limit: Optional result limit
            
        Returns:
            List of FeeCalculation instances
        """
        query = self.session.query(FeeCalculation).filter(
            FeeCalculation.fee_structure_id == fee_structure_id
        )
        
        if calculation_type:
            query = query.filter(FeeCalculation.calculation_type == calculation_type)
        
        query = query.order_by(FeeCalculation.calculation_date.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_latest_calculation(
        self,
        student_id: Optional[UUID] = None,
        booking_id: Optional[UUID] = None
    ) -> Optional[FeeCalculation]:
        """
        Get the most recent calculation for a student or booking.
        
        Args:
            student_id: Optional student identifier
            booking_id: Optional booking identifier
            
        Returns:
            Latest FeeCalculation instance or None
        """
        query = self.session.query(FeeCalculation)
        
        if student_id:
            query = query.filter(FeeCalculation.student_id == student_id)
        elif booking_id:
            query = query.filter(FeeCalculation.booking_id == booking_id)
        else:
            return None
        
        return query.order_by(FeeCalculation.calculation_date.desc()).first()
    
    def find_pending_approval(
        self,
        fee_structure_id: Optional[UUID] = None
    ) -> List[FeeCalculation]:
        """
        Find calculations pending approval.
        
        Args:
            fee_structure_id: Optional fee structure filter
            
        Returns:
            List of pending FeeCalculation instances
        """
        query = self.session.query(FeeCalculation).filter(
            FeeCalculation.is_approved == False
        )
        
        if fee_structure_id:
            query = query.filter(FeeCalculation.fee_structure_id == fee_structure_id)
        
        return query.order_by(FeeCalculation.calculation_date.desc()).all()
    
    def find_approved_calculations(
        self,
        start_date: Optional[Date] = None,
        end_date: Optional[Date] = None,
        approved_by_id: Optional[UUID] = None
    ) -> List[FeeCalculation]:
        """
        Find approved calculations within date range.
        
        Args:
            start_date: Optional start date
            end_date: Optional end date
            approved_by_id: Optional approver filter
            
        Returns:
            List of approved FeeCalculation instances
        """
        query = self.session.query(FeeCalculation).filter(
            FeeCalculation.is_approved == True
        )
        
        if start_date:
            query = query.filter(FeeCalculation.approved_at >= start_date)
        
        if end_date:
            query = query.filter(FeeCalculation.approved_at <= end_date)
        
        if approved_by_id:
            query = query.filter(FeeCalculation.approved_by_id == approved_by_id)
        
        return query.order_by(FeeCalculation.approved_at.desc()).all()
    
    def find_prorated_calculations(
        self,
        fee_structure_id: Optional[UUID] = None
    ) -> List[FeeCalculation]:
        """
        Find all prorated fee calculations.
        
        Args:
            fee_structure_id: Optional fee structure filter
            
        Returns:
            List of prorated FeeCalculation instances
        """
        query = self.session.query(FeeCalculation).filter(
            FeeCalculation.is_prorated == True
        )
        
        if fee_structure_id:
            query = query.filter(FeeCalculation.fee_structure_id == fee_structure_id)
        
        return query.order_by(FeeCalculation.calculation_date.desc()).all()
    
    def get_calculation_with_details(
        self,
        calculation_id: UUID
    ) -> Optional[FeeCalculation]:
        """
        Get calculation with all related entities loaded.
        
        Args:
            calculation_id: Calculation identifier
            
        Returns:
            FeeCalculation with related data or None
        """
        return self.session.query(FeeCalculation).options(
            joinedload(FeeCalculation.fee_structure),
            joinedload(FeeCalculation.student),
            joinedload(FeeCalculation.booking),
            joinedload(FeeCalculation.discount_config)
        ).filter(
            FeeCalculation.id == calculation_id
        ).first()
    
    # ============================================================
    # Approval Operations
    # ============================================================
    
    def approve_calculation(
        self,
        calculation_id: UUID,
        approved_by_id: UUID
    ) -> FeeCalculation:
        """
        Approve a fee calculation.
        
        Args:
            calculation_id: Calculation identifier
            approved_by_id: User approving the calculation
            
        Returns:
            Approved FeeCalculation instance
        """
        calculation = self.find_by_id(calculation_id)
        if not calculation:
            raise NotFoundException(f"Fee calculation {calculation_id} not found")
        
        calculation.is_approved = True
        calculation.approved_by_id = approved_by_id
        calculation.approved_at = datetime.utcnow()
        calculation.updated_at = datetime.utcnow()
        
        self.session.flush()
        return calculation
    
    def bulk_approve_calculations(
        self,
        calculation_ids: List[UUID],
        approved_by_id: UUID
    ) -> int:
        """
        Bulk approve multiple calculations.
        
        Args:
            calculation_ids: List of calculation IDs
            approved_by_id: User approving the calculations
            
        Returns:
            Number of calculations approved
        """
        approved = self.session.query(FeeCalculation).filter(
            FeeCalculation.id.in_(calculation_ids),
            FeeCalculation.is_approved == False
        ).update(
            {
                'is_approved': True,
                'approved_by_id': approved_by_id,
                'approved_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            },
            synchronize_session=False
        )
        
        self.session.flush()
        return approved
    
    # ============================================================
    # Analytics and Reporting
    # ============================================================
    
    def get_calculation_statistics(
        self,
        fee_structure_id: Optional[UUID] = None,
        calculation_type: Optional[str] = None,
        start_date: Optional[Date] = None,
        end_date: Optional[Date] = None
    ) -> Dict[str, Any]:
        """
        Get statistical summary of calculations.
        
        Args:
            fee_structure_id: Optional fee structure filter
            calculation_type: Optional calculation type filter
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            Dictionary with calculation statistics
        """
        query = self.session.query(
            func.count(FeeCalculation.id).label('total_calculations'),
            func.avg(FeeCalculation.total_payable).label('avg_total'),
            func.min(FeeCalculation.total_payable).label('min_total'),
            func.max(FeeCalculation.total_payable).label('max_total'),
            func.sum(FeeCalculation.total_payable).label('sum_total'),
            func.avg(FeeCalculation.discount_applied).label('avg_discount'),
            func.sum(FeeCalculation.discount_applied).label('total_discount'),
            func.sum(case(
                (FeeCalculation.is_approved == True, 1),
                else_=0
            )).label('approved_count'),
            func.sum(case(
                (FeeCalculation.is_prorated == True, 1),
                else_=0
            )).label('prorated_count')
        )
        
        if fee_structure_id:
            query = query.filter(FeeCalculation.fee_structure_id == fee_structure_id)
        
        if calculation_type:
            query = query.filter(FeeCalculation.calculation_type == calculation_type)
        
        if start_date:
            query = query.filter(FeeCalculation.calculation_date >= start_date)
        
        if end_date:
            query = query.filter(FeeCalculation.calculation_date <= end_date)
        
        result = query.first()
        
        return {
            'total_calculations': result.total_calculations or 0,
            'average_total': float(result.avg_total or 0),
            'minimum_total': float(result.min_total or 0),
            'maximum_total': float(result.max_total or 0),
            'sum_total': float(result.sum_total or 0),
            'average_discount': float(result.avg_discount or 0),
            'total_discount': float(result.total_discount or 0),
            'approved_count': result.approved_count or 0,
            'prorated_count': result.prorated_count or 0,
            'approval_rate': (result.approved_count / result.total_calculations * 100) 
                           if result.total_calculations else 0
        }
    
    def get_revenue_projection(
        self,
        fee_structure_id: UUID,
        months_ahead: int = 12
    ) -> Dict[str, Any]:
        """
        Calculate revenue projection based on calculations.
        
        Args:
            fee_structure_id: Fee structure identifier
            months_ahead: Number of months to project
            
        Returns:
            Dictionary with revenue projections
        """
        # Get recent calculations
        recent = self.session.query(
            func.avg(FeeCalculation.monthly_recurring).label('avg_monthly'),
            func.count(FeeCalculation.id).label('calc_count')
        ).filter(
            FeeCalculation.fee_structure_id == fee_structure_id,
            FeeCalculation.calculation_date >= Date.fromordinal(
                Date.today().toordinal() - 90
            )  # Last 90 days
        ).first()
        
        avg_monthly = float(recent.avg_monthly or 0)
        
        return {
            'fee_structure_id': str(fee_structure_id),
            'projection_months': months_ahead,
            'average_monthly_recurring': avg_monthly,
            'projected_monthly_revenue': avg_monthly * (recent.calc_count or 0),
            'projected_total_revenue': avg_monthly * (recent.calc_count or 0) * months_ahead,
            'calculation_sample_size': recent.calc_count or 0
        }
    
    def get_discount_impact_analysis(
        self,
        start_date: Optional[Date] = None,
        end_date: Optional[Date] = None
    ) -> Dict[str, Any]:
        """
        Analyze impact of discounts on calculations.
        
        Args:
            start_date: Optional start date
            end_date: Optional end date
            
        Returns:
            Dictionary with discount impact analysis
        """
        query = self.session.query(
            func.count(FeeCalculation.id).label('total_calculations'),
            func.sum(case(
                (FeeCalculation.discount_applied > 0, 1),
                else_=0
            )).label('calculations_with_discount'),
            func.sum(FeeCalculation.discount_applied).label('total_discount'),
            func.sum(FeeCalculation.subtotal).label('total_before_discount'),
            func.avg(FeeCalculation.discount_applied).label('avg_discount')
        )
        
        if start_date:
            query = query.filter(FeeCalculation.calculation_date >= start_date)
        
        if end_date:
            query = query.filter(FeeCalculation.calculation_date <= end_date)
        
        result = query.first()
        
        total_calc = result.total_calculations or 0
        calc_with_discount = result.calculations_with_discount or 0
        total_discount = float(result.total_discount or 0)
        total_before = float(result.total_before_discount or 0)
        
        return {
            'total_calculations': total_calc,
            'calculations_with_discount': calc_with_discount,
            'discount_usage_rate': (calc_with_discount / total_calc * 100) if total_calc else 0,
            'total_discount_given': total_discount,
            'average_discount': float(result.avg_discount or 0),
            'discount_percentage_of_revenue': (total_discount / total_before * 100) if total_before else 0,
            'total_revenue_before_discount': total_before,
            'total_revenue_after_discount': total_before - total_discount
        }
    
    def get_calculation_trends(
        self,
        fee_structure_id: UUID,
        months: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Get monthly calculation trends.
        
        Args:
            fee_structure_id: Fee structure identifier
            months: Number of months to analyze
            
        Returns:
            List of monthly trend data
        """
        start_date = Date.fromordinal(
            Date.today().toordinal() - (months * 30)
        )
        
        results = self.session.query(
            func.date_trunc('month', FeeCalculation.calculation_date).label('month'),
            func.count(FeeCalculation.id).label('count'),
            func.avg(FeeCalculation.total_payable).label('avg_total'),
            func.sum(FeeCalculation.total_payable).label('sum_total')
        ).filter(
            FeeCalculation.fee_structure_id == fee_structure_id,
            FeeCalculation.calculation_date >= start_date
        ).group_by(
            func.date_trunc('month', FeeCalculation.calculation_date)
        ).order_by(
            func.date_trunc('month', FeeCalculation.calculation_date)
        ).all()
        
        return [
            {
                'month': r.month.isoformat() if r.month else None,
                'calculation_count': r.count,
                'average_total': float(r.avg_total or 0),
                'total_revenue': float(r.sum_total or 0)
            }
            for r in results
        ]
    
    # ============================================================
    # Calculation Helpers
    # ============================================================
    
    def _calculate_totals(
        self,
        monthly_rent: Decimal,
        security_deposit: Decimal,
        stay_duration_months: int,
        mess_charges: Decimal,
        utility_charges: Decimal,
        other_charges: Decimal,
        discount: Decimal,
        tax_percentage: Decimal
    ) -> typing.Tuple[Decimal, Decimal, Decimal, Decimal]:
        """
        Calculate total amounts for fee calculation.
        
        Returns:
            Tuple of (subtotal, total_payable, first_month_total, monthly_recurring)
        """
        # Monthly recurring charges
        monthly_recurring = monthly_rent + mess_charges + utility_charges
        
        # Total for stay duration
        total_for_duration = monthly_recurring * stay_duration_months
        
        # Subtotal before discount and tax
        subtotal = total_for_duration + security_deposit + other_charges
        
        # Apply discount
        amount_after_discount = subtotal - discount
        
        # Calculate tax
        tax_amount = (amount_after_discount * tax_percentage / 100).quantize(Decimal('0.01'))
        
        # Total payable
        total_payable = (amount_after_discount + tax_amount).quantize(Decimal('0.01'))
        
        # First month total (includes security deposit and one-time charges)
        first_month_total = (
            monthly_recurring + security_deposit + other_charges - discount + tax_amount
        ).quantize(Decimal('0.01'))
        
        return (
            subtotal.quantize(Decimal('0.01')),
            total_payable,
            first_month_total,
            monthly_recurring.quantize(Decimal('0.01'))
        )
    
    def _validate_calculation(
        self,
        calculation_type: str,
        stay_duration_months: int,
        monthly_rent: Decimal,
        security_deposit: Decimal,
        data: Dict[str, Any]
    ) -> None:
        """Validate calculation data."""
        valid_types = ['estimate', 'booking', 'student', 'renewal', 'modification']
        if calculation_type not in valid_types:
            raise ValidationException(
                f"Invalid calculation_type. Must be one of: {', '.join(valid_types)}"
            )
        
        if stay_duration_months < 1:
            raise ValidationException("stay_duration_months must be at least 1")
        
        if monthly_rent < Decimal('0'):
            raise ValidationException("monthly_rent cannot be negative")
        
        if security_deposit < Decimal('0'):
            raise ValidationException("security_deposit cannot be negative")
        
        move_in = data.get('move_in_date')
        move_out = data.get('move_out_date')
        if move_in and move_out and move_out <= move_in:
            raise ValidationException("move_out_date must be after move_in_date")
    
    def _apply_audit(
        self,
        entity: FeeCalculation,
        audit_context: Dict[str, Any],
        is_update: bool = False
    ) -> None:
        """Apply audit information to entity."""
        user_id = audit_context.get('user_id')
        
        if is_update:
            entity.updated_by = user_id
            entity.updated_at = datetime.utcnow()
        else:
            entity.calculated_by_id = user_id
            entity.created_at = datetime.utcnow()


class FeeProjectionRepository(BaseRepository[FeeProjection]):
    """
    Fee Projection Repository
    
    Manages fee projections and forecasting for future periods.
    """
    
    def __init__(self, session: Session):
        super().__init__(FeeProjection, session)
    
    # ============================================================
    # Core CRUD Operations
    # ============================================================
    
    def create_projection(
        self,
        fee_structure_id: UUID,
        projection_date: Date,
        projection_period_months: int,
        projected_revenue: Decimal,
        projected_occupancy: Decimal,
        projected_bookings: int,
        projection_model: str,
        audit_context: Dict[str, Any],
        **kwargs
    ) -> FeeProjection:
        """
        Create a new fee projection.
        
        Args:
            fee_structure_id: Fee structure identifier
            projection_date: Date of projection
            projection_period_months: Projection period
            projected_revenue: Projected revenue amount
            projected_occupancy: Projected occupancy percentage
            projected_bookings: Projected number of bookings
            projection_model: Model used for projection
            audit_context: Audit information
            **kwargs: Additional projection attributes
            
        Returns:
            Created FeeProjection instance
        """
        self._validate_projection(
            projection_period_months,
            projected_revenue,
            projected_occupancy,
            projected_bookings,
            kwargs
        )
        
        projection = FeeProjection(
            fee_structure_id=fee_structure_id,
            projection_date=projection_date,
            projection_period_months=projection_period_months,
            projected_revenue=projected_revenue,
            projected_occupancy=projected_occupancy,
            projected_bookings=projected_bookings,
            projection_model=projection_model,
            **kwargs
        )
        
        self._apply_audit(projection, audit_context)
        self.session.add(projection)
        self.session.flush()
        
        return projection
    
    # ============================================================
    # Query Operations
    # ============================================================
    
    def find_by_fee_structure(
        self,
        fee_structure_id: UUID,
        start_date: Optional[Date] = None,
        end_date: Optional[Date] = None
    ) -> List[FeeProjection]:
        """
        Find projections for a fee structure.
        
        Args:
            fee_structure_id: Fee structure identifier
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List of FeeProjection instances
        """
        query = self.session.query(FeeProjection).filter(
            FeeProjection.fee_structure_id == fee_structure_id
        )
        
        if start_date:
            query = query.filter(FeeProjection.projection_date >= start_date)
        
        if end_date:
            query = query.filter(FeeProjection.projection_date <= end_date)
        
        return query.order_by(FeeProjection.projection_date.desc()).all()
    
    def get_latest_projection(
        self,
        fee_structure_id: UUID
    ) -> Optional[FeeProjection]:
        """
        Get most recent projection for a fee structure.
        
        Args:
            fee_structure_id: Fee structure identifier
            
        Returns:
            Latest FeeProjection instance or None
        """
        return self.session.query(FeeProjection).filter(
            FeeProjection.fee_structure_id == fee_structure_id
        ).order_by(FeeProjection.projection_date.desc()).first()
    
    def find_by_period(
        self,
        projection_period_months: int,
        start_date: Optional[Date] = None
    ) -> List[FeeProjection]:
        """
        Find projections by period length.
        
        Args:
            projection_period_months: Period in months
            start_date: Optional start date filter
            
        Returns:
            List of FeeProjection instances
        """
        query = self.session.query(FeeProjection).filter(
            FeeProjection.projection_period_months == projection_period_months
        )
        
        if start_date:
            query = query.filter(FeeProjection.projection_date >= start_date)
        
        return query.order_by(FeeProjection.projection_date.desc()).all()
    
    # ============================================================
    # Analytics
    # ============================================================
    
    def get_projection_accuracy(
        self,
        fee_structure_id: UUID,
        actual_revenue: Decimal,
        actual_occupancy: Decimal,
        projection_date: Date
    ) -> Dict[str, Any]:
        """
        Calculate accuracy of projections vs actuals.
        
        Args:
            fee_structure_id: Fee structure identifier
            actual_revenue: Actual revenue achieved
            actual_occupancy: Actual occupancy achieved
            projection_date: Date to compare
            
        Returns:
            Dictionary with accuracy metrics
        """
        projection = self.session.query(FeeProjection).filter(
            FeeProjection.fee_structure_id == fee_structure_id,
            FeeProjection.projection_date == projection_date
        ).first()
        
        if not projection:
            return {'error': 'No projection found for comparison'}
        
        revenue_variance = float(actual_revenue - projection.projected_revenue)
        revenue_variance_pct = (revenue_variance / float(projection.projected_revenue) * 100) \
                             if projection.projected_revenue > 0 else 0
        
        occupancy_variance = float(actual_occupancy - projection.projected_occupancy)
        
        return {
            'projection_date': projection_date.isoformat(),
            'projected_revenue': float(projection.projected_revenue),
            'actual_revenue': float(actual_revenue),
            'revenue_variance': revenue_variance,
            'revenue_variance_percentage': revenue_variance_pct,
            'projected_occupancy': float(projection.projected_occupancy),
            'actual_occupancy': float(actual_occupancy),
            'occupancy_variance': occupancy_variance,
            'projection_model': projection.projection_model,
            'confidence_level': float(projection.confidence_level) if projection.confidence_level else None
        }
    
    # ============================================================
    # Validation Helpers
    # ============================================================
    
    def _validate_projection(
        self,
        projection_period_months: int,
        projected_revenue: Decimal,
        projected_occupancy: Decimal,
        projected_bookings: int,
        data: Dict[str, Any]
    ) -> None:
        """Validate projection data."""
        if projection_period_months < 1:
            raise ValidationException("projection_period_months must be at least 1")
        
        if projected_revenue < Decimal('0'):
            raise ValidationException("projected_revenue cannot be negative")
        
        if projected_occupancy < Decimal('0') or projected_occupancy > Decimal('100'):
            raise ValidationException("projected_occupancy must be between 0 and 100")
        
        if projected_bookings < 0:
            raise ValidationException("projected_bookings cannot be negative")
        
        confidence = data.get('confidence_level')
        if confidence is not None:
            if confidence < Decimal('0') or confidence > Decimal('100'):
                raise ValidationException("confidence_level must be between 0 and 100")
    
    def _apply_audit(
        self,
        entity: FeeProjection,
        audit_context: Dict[str, Any]
    ) -> None:
        """Apply audit information to entity."""
        entity.created_at = datetime.utcnow()