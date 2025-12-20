# --- File: C:\Hostel-Main\app\services\fee_structure\fee_calculation_service.py ---
"""
Fee Calculation Service

Business logic layer for fee calculations, estimates, and comprehensive
fee computations with discount application and tax calculations.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import json

from sqlalchemy.orm import Session

from app.models.fee_structure.fee_calculation import FeeCalculation
from app.models.fee_structure.fee_structure import FeeStructure
from app.models.fee_structure.charge_component import ChargeComponent
from app.models.base.enums import RoomType, FeeType
from app.repositories.fee_structure.fee_calculation_repository import (
    FeeCalculationRepository,
)
from app.repositories.fee_structure.fee_structure_repository import (
    FeeStructureRepository,
)
from app.repositories.fee_structure.charge_component_repository import (
    ChargeComponentRepository,
    DiscountConfigurationRepository,
)
from app.services.fee_structure.proration_service import ProrationService
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    BusinessLogicException,
)
from app.core.logging import logger


class FeeCalculationService:
    """
    Fee Calculation Service
    
    Provides comprehensive fee calculation functionality including
    estimates, bookings, student fees, renewals, and modifications.
    """
    
    def __init__(self, session: Session):
        """
        Initialize service with database session.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.calculation_repo = FeeCalculationRepository(session)
        self.fee_structure_repo = FeeStructureRepository(session)
        self.component_repo = ChargeComponentRepository(session)
        self.discount_repo = DiscountConfigurationRepository(session)
        self.proration_service = ProrationService(session)
    
    # ============================================================
    # Core Fee Calculation Operations
    # ============================================================
    
    def calculate_fee_estimate(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        fee_type: FeeType,
        stay_duration_months: int,
        move_in_date: Date,
        user_id: UUID,
        discount_code: Optional[str] = None,
        is_new_student: bool = False,
        include_components: bool = True,
        as_of_date: Optional[Date] = None
    ) -> Dict[str, Any]:
        """
        Calculate fee estimate for a prospective booking.
        
        Args:
            hostel_id: Hostel identifier
            room_type: Room type
            fee_type: Fee type
            stay_duration_months: Duration of stay in months
            move_in_date: Move-in date
            user_id: User requesting estimate
            discount_code: Optional discount code
            is_new_student: Whether student is new
            include_components: Include charge components
            as_of_date: Date to use for fee structure lookup
            
        Returns:
            Dictionary with comprehensive fee estimate
            
        Raises:
            NotFoundException: If fee structure not found
            ValidationException: If invalid parameters
        """
        logger.info(
            f"Calculating fee estimate for hostel {hostel_id}, "
            f"room_type={room_type.value}, duration={stay_duration_months} months"
        )
        
        # Validate inputs
        if stay_duration_months < 1:
            raise ValidationException("Stay duration must be at least 1 month")
        
        if move_in_date < Date.today():
            logger.warning(f"Move-in date {move_in_date} is in the past")
        
        # Get current fee structure
        fee_structure = self.fee_structure_repo.get_current_fee_structure(
            hostel_id=hostel_id,
            room_type=room_type,
            fee_type=fee_type,
            as_of_date=as_of_date or move_in_date
        )
        
        if not fee_structure:
            raise NotFoundException(
                f"No active fee structure found for {hostel_id}/{room_type.value}/{fee_type.value}"
            )
        
        # Calculate move-out date
        move_out_date = self._calculate_move_out_date(move_in_date, stay_duration_months)
        
        # Calculate base charges
        monthly_rent = fee_structure.amount
        security_deposit = fee_structure.security_deposit
        
        # Calculate mess charges
        mess_charges_total = self._calculate_mess_charges(
            fee_structure=fee_structure,
            stay_duration_months=stay_duration_months
        )
        
        # Estimate utility charges
        utility_charges_estimated = self._estimate_utility_charges(
            fee_structure=fee_structure,
            stay_duration_months=stay_duration_months
        )
        
        # Get and calculate components
        components_breakdown = []
        other_charges = Decimal('0.00')
        
        if include_components:
            components = self.component_repo.find_applicable_components(
                fee_structure_id=fee_structure.id,
                room_types=[room_type.value],
                check_date=move_in_date,
                include_optional=True
            )
            
            for component in components:
                comp_amount = self._calculate_component_amount(
                    component=component,
                    stay_duration_months=stay_duration_months
                )
                other_charges += comp_amount
                
                components_breakdown.append({
                    'id': str(component.id),
                    'name': component.component_name,
                    'type': component.component_type,
                    'amount': float(component.amount),
                    'total': float(comp_amount),
                    'is_recurring': component.is_recurring,
                    'is_mandatory': component.is_mandatory,
                    'is_taxable': component.is_taxable,
                    'tax_percentage': float(component.tax_percentage)
                })
        
        # Calculate subtotal
        subtotal = self._calculate_subtotal(
            monthly_rent=monthly_rent,
            stay_duration_months=stay_duration_months,
            security_deposit=security_deposit,
            mess_charges_total=mess_charges_total,
            utility_charges_estimated=utility_charges_estimated,
            other_charges=other_charges
        )
        
        # Apply discount if provided
        discount_applied = Decimal('0.00')
        discount_description = None
        discount_config_id = None
        
        if discount_code:
            discount_result = self._apply_discount_code(
                discount_code=discount_code,
                hostel_id=hostel_id,
                room_type=room_type.value,
                base_amount=subtotal,
                is_new_student=is_new_student,
                stay_months=stay_duration_months
            )
            
            if discount_result:
                discount_applied = discount_result['discount_amount']
                discount_description = discount_result['description']
                discount_config_id = discount_result['discount_id']
        
        # Calculate tax
        tax_percentage = Decimal('0.00')  # Can be configured
        tax_amount = self._calculate_tax(
            amount=subtotal - discount_applied,
            tax_percentage=tax_percentage
        )
        
        # Calculate totals
        total_payable = subtotal - discount_applied + tax_amount
        
        # Calculate first month and recurring
        first_month_total = monthly_rent + mess_charges_total/stay_duration_months + \
                           utility_charges_estimated/stay_duration_months + security_deposit
        monthly_recurring = monthly_rent + mess_charges_total/stay_duration_months + \
                          utility_charges_estimated/stay_duration_months
        
        # Generate payment schedule
        payment_schedule = self._generate_payment_schedule(
            monthly_recurring=monthly_recurring,
            stay_duration_months=stay_duration_months,
            first_month_total=first_month_total,
            move_in_date=move_in_date
        )
        
        # Create detailed breakdown
        charge_breakdown = {
            'base_charges': {
                'monthly_rent': float(monthly_rent),
                'security_deposit': float(security_deposit),
                'total_months': stay_duration_months
            },
            'recurring_charges': {
                'mess_charges_monthly': float(mess_charges_total / stay_duration_months),
                'mess_charges_total': float(mess_charges_total),
                'utility_charges_estimated_monthly': float(utility_charges_estimated / stay_duration_months),
                'utility_charges_total': float(utility_charges_estimated)
            },
            'components': components_breakdown,
            'discount': {
                'code': discount_code,
                'amount': float(discount_applied),
                'description': discount_description
            } if discount_applied > 0 else None,
            'tax': {
                'percentage': float(tax_percentage),
                'amount': float(tax_amount)
            }
        }
        
        estimate = {
            'calculation_type': 'estimate',
            'fee_structure_id': str(fee_structure.id),
            'hostel_id': str(hostel_id),
            'room_type': room_type.value,
            'fee_type': fee_type.value,
            'stay_duration_months': stay_duration_months,
            'move_in_date': move_in_date.isoformat(),
            'move_out_date': move_out_date.isoformat(),
            'monthly_rent': float(monthly_rent),
            'security_deposit': float(security_deposit),
            'mess_charges_total': float(mess_charges_total),
            'utility_charges_estimated': float(utility_charges_estimated),
            'other_charges': float(other_charges),
            'subtotal': float(subtotal),
            'discount_applied': float(discount_applied),
            'tax_amount': float(tax_amount),
            'total_payable': float(total_payable),
            'first_month_total': float(first_month_total),
            'monthly_recurring': float(monthly_recurring),
            'payment_schedule': payment_schedule,
            'charge_breakdown': charge_breakdown,
            'characteristics': {
                'includes_mess': fee_structure.includes_mess,
                'is_all_inclusive': fee_structure.is_all_inclusive,
                'has_variable_charges': fee_structure.has_variable_charges
            }
        }
        
        logger.info(f"Fee estimate calculated: total={total_payable}")
        
        return estimate
    
    def create_fee_calculation(
        self,
        fee_structure_id: UUID,
        calculation_type: str,
        room_type: RoomType,
        fee_type: FeeType,
        stay_duration_months: int,
        move_in_date: Date,
        user_id: UUID,
        student_id: Optional[UUID] = None,
        booking_id: Optional[UUID] = None,
        discount_code: Optional[str] = None,
        is_new_student: bool = False,
        move_out_date: Optional[Date] = None,
        save_calculation: bool = True
    ) -> FeeCalculation:
        """
        Create and save a fee calculation record.
        
        Args:
            fee_structure_id: Fee structure identifier
            calculation_type: Type (estimate, booking, student, renewal, modification)
            room_type: Room type
            fee_type: Fee type
            stay_duration_months: Duration in months
            move_in_date: Move-in date
            user_id: User creating calculation
            student_id: Optional student identifier
            booking_id: Optional booking identifier
            discount_code: Optional discount code
            is_new_student: Whether student is new
            move_out_date: Optional move-out date
            save_calculation: Whether to save to database
            
        Returns:
            Created FeeCalculation instance
            
        Raises:
            NotFoundException: If fee structure not found
            ValidationException: If validation fails
        """
        logger.info(
            f"Creating fee calculation: type={calculation_type}, "
            f"fee_structure={fee_structure_id}"
        )
        
        # Get fee structure
        fee_structure = self.fee_structure_repo.get_fee_structure_with_components(
            fee_structure_id
        )
        
        if not fee_structure:
            raise NotFoundException(f"Fee structure {fee_structure_id} not found")
        
        # Calculate move-out date if not provided
        if not move_out_date:
            move_out_date = self._calculate_move_out_date(move_in_date, stay_duration_months)
        
        # Calculate all charges
        monthly_rent = fee_structure.amount
        security_deposit = fee_structure.security_deposit
        
        mess_charges_total = self._calculate_mess_charges(
            fee_structure=fee_structure,
            stay_duration_months=stay_duration_months
        )
        
        utility_charges_estimated = self._estimate_utility_charges(
            fee_structure=fee_structure,
            stay_duration_months=stay_duration_months
        )
        
        # Calculate components
        other_charges = Decimal('0.00')
        if fee_structure.charge_components:
            for component in fee_structure.charge_components:
                if component.deleted_at is None:
                    comp_amount = self._calculate_component_amount(
                        component=component,
                        stay_duration_months=stay_duration_months
                    )
                    other_charges += comp_amount
        
        # Calculate subtotal
        subtotal = self._calculate_subtotal(
            monthly_rent=monthly_rent,
            stay_duration_months=stay_duration_months,
            security_deposit=security_deposit,
            mess_charges_total=mess_charges_total,
            utility_charges_estimated=utility_charges_estimated,
            other_charges=other_charges
        )
        
        # Apply discount
        discount_applied = Decimal('0.00')
        discount_description = None
        discount_config_id = None
        
        if discount_code:
            discount_result = self._apply_discount_code(
                discount_code=discount_code,
                hostel_id=fee_structure.hostel_id,
                room_type=room_type.value,
                base_amount=subtotal,
                is_new_student=is_new_student,
                stay_months=stay_duration_months
            )
            
            if discount_result:
                discount_applied = discount_result['discount_amount']
                discount_description = discount_result['description']
                discount_config_id = UUID(discount_result['discount_id'])
        
        # Calculate tax
        tax_percentage = Decimal('0.00')
        tax_amount = self._calculate_tax(
            amount=subtotal - discount_applied,
            tax_percentage=tax_percentage
        )
        
        # Calculate totals
        total_payable = subtotal - discount_applied + tax_amount
        first_month_total = monthly_rent + security_deposit
        monthly_recurring = monthly_rent + mess_charges_total/stay_duration_months
        
        # Generate payment schedule and breakdown
        payment_schedule = self._generate_payment_schedule(
            monthly_recurring=monthly_recurring,
            stay_duration_months=stay_duration_months,
            first_month_total=first_month_total,
            move_in_date=move_in_date
        )
        
        charge_breakdown = self._generate_charge_breakdown(
            fee_structure=fee_structure,
            monthly_rent=monthly_rent,
            security_deposit=security_deposit,
            mess_charges_total=mess_charges_total,
            utility_charges_estimated=utility_charges_estimated,
            other_charges=other_charges,
            discount_applied=discount_applied,
            tax_amount=tax_amount,
            stay_duration_months=stay_duration_months
        )
        
        # Prepare audit context
        audit_context = {
            'user_id': user_id,
            'action': 'create_fee_calculation',
            'timestamp': datetime.utcnow()
        }
        
        try:
            # Create calculation
            calculation = self.calculation_repo.create_fee_calculation(
                fee_structure_id=fee_structure_id,
                calculation_type=calculation_type,
                room_type=room_type,
                fee_type=fee_type,
                stay_duration_months=stay_duration_months,
                move_in_date=move_in_date,
                monthly_rent=monthly_rent,
                security_deposit=security_deposit,
                audit_context=audit_context,
                student_id=student_id,
                booking_id=booking_id,
                move_out_date=move_out_date,
                mess_charges_total=mess_charges_total,
                utility_charges_estimated=utility_charges_estimated,
                other_charges=other_charges,
                discount_applied=discount_applied,
                discount_description=discount_description,
                discount_config_id=discount_config_id,
                tax_amount=tax_amount,
                tax_percentage=tax_percentage,
                payment_schedule=payment_schedule,
                charge_breakdown=charge_breakdown
            )
            
            # Increment discount usage if applied
            if discount_config_id:
                self.discount_repo.increment_usage(discount_config_id)
            
            if save_calculation:
                self.session.commit()
                logger.info(f"Fee calculation created and saved: {calculation.id}")
            else:
                logger.info("Fee calculation created (not saved)")
            
            return calculation
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating fee calculation: {str(e)}")
            raise
    
    def calculate_prorated_fee(
        self,
        fee_structure_id: UUID,
        move_in_date: Date,
        move_out_date: Date,
        user_id: UUID,
        room_type: RoomType,
        fee_type: FeeType,
        student_id: Optional[UUID] = None,
        booking_id: Optional[UUID] = None
    ) -> FeeCalculation:
        """
        Calculate prorated fee for partial month stay.
        
        Args:
            fee_structure_id: Fee structure identifier
            move_in_date: Move-in date
            move_out_date: Move-out date
            user_id: User creating calculation
            room_type: Room type
            fee_type: Fee type
            student_id: Optional student identifier
            booking_id: Optional booking identifier
            
        Returns:
            FeeCalculation with prorated amounts
        """
        logger.info(f"Calculating prorated fee from {move_in_date} to {move_out_date}")
        
        # Calculate proration
        proration_result = self.proration_service.calculate_proration(
            fee_structure_id=fee_structure_id,
            start_date=move_in_date,
            end_date=move_out_date
        )
        
        # Get fee structure
        fee_structure = self.fee_structure_repo.find_by_id(fee_structure_id)
        if not fee_structure:
            raise NotFoundException(f"Fee structure {fee_structure_id} not found")
        
        # Prepare audit context
        audit_context = {
            'user_id': user_id,
            'action': 'create_prorated_calculation',
            'timestamp': datetime.utcnow()
        }
        
        try:
            # Create calculation with prorated amounts
            calculation = self.calculation_repo.create_fee_calculation(
                fee_structure_id=fee_structure_id,
                calculation_type='modification',
                room_type=room_type,
                fee_type=fee_type,
                stay_duration_months=1,  # Partial month
                move_in_date=move_in_date,
                monthly_rent=proration_result['prorated_rent'],
                security_deposit=fee_structure.security_deposit,
                audit_context=audit_context,
                student_id=student_id,
                booking_id=booking_id,
                move_out_date=move_out_date,
                is_prorated=True,
                proration_days=proration_result['actual_days'],
                proration_amount=proration_result['prorated_rent'],
                mess_charges_total=proration_result['prorated_mess_charges'],
                utility_charges_estimated=Decimal('0.00'),
                other_charges=Decimal('0.00'),
                discount_applied=Decimal('0.00'),
                tax_amount=Decimal('0.00'),
                tax_percentage=Decimal('0.00')
            )
            
            self.session.commit()
            
            logger.info(f"Prorated calculation created: {calculation.id}")
            return calculation
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating prorated calculation: {str(e)}")
            raise
    
    # ============================================================
    # Fee Calculation Retrieval
    # ============================================================
    
    def get_fee_calculation(
        self,
        calculation_id: UUID,
        include_details: bool = False
    ) -> FeeCalculation:
        """
        Get fee calculation by ID.
        
        Args:
            calculation_id: Calculation identifier
            include_details: Load related entities
            
        Returns:
            FeeCalculation instance
            
        Raises:
            NotFoundException: If not found
        """
        if include_details:
            calculation = self.calculation_repo.get_calculation_with_details(calculation_id)
        else:
            calculation = self.calculation_repo.find_by_id(calculation_id)
        
        if not calculation:
            raise NotFoundException(f"Fee calculation {calculation_id} not found")
        
        return calculation
    
    def get_student_calculations(
        self,
        student_id: UUID,
        calculation_type: Optional[str] = None,
        start_date: Optional[Date] = None,
        end_date: Optional[Date] = None
    ) -> List[FeeCalculation]:
        """Get all calculations for a student."""
        return self.calculation_repo.find_by_student(
            student_id=student_id,
            calculation_type=calculation_type,
            start_date=start_date,
            end_date=end_date
        )
    
    def get_booking_calculations(self, booking_id: UUID) -> List[FeeCalculation]:
        """Get all calculations for a booking."""
        return self.calculation_repo.find_by_booking(booking_id)
    
    def get_latest_calculation(
        self,
        student_id: Optional[UUID] = None,
        booking_id: Optional[UUID] = None
    ) -> Optional[FeeCalculation]:
        """Get most recent calculation."""
        return self.calculation_repo.get_latest_calculation(
            student_id=student_id,
            booking_id=booking_id
        )
    
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
            approved_by_id: User approving
            
        Returns:
            Approved FeeCalculation
        """
        try:
            calculation = self.calculation_repo.approve_calculation(
                calculation_id=calculation_id,
                approved_by_id=approved_by_id
            )
            
            self.session.commit()
            
            logger.info(f"Calculation {calculation_id} approved by {approved_by_id}")
            return calculation
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error approving calculation: {str(e)}")
            raise
    
    def bulk_approve_calculations(
        self,
        calculation_ids: List[UUID],
        approved_by_id: UUID
    ) -> int:
        """Bulk approve calculations."""
        try:
            approved = self.calculation_repo.bulk_approve_calculations(
                calculation_ids=calculation_ids,
                approved_by_id=approved_by_id
            )
            
            self.session.commit()
            
            logger.info(f"Bulk approved {approved} calculations")
            return approved
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error in bulk approve: {str(e)}")
            raise
    
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
        """Get calculation statistics."""
        return self.calculation_repo.get_calculation_statistics(
            fee_structure_id=fee_structure_id,
            calculation_type=calculation_type,
            start_date=start_date,
            end_date=end_date
        )
    
    def get_revenue_projection(
        self,
        fee_structure_id: UUID,
        months_ahead: int = 12
    ) -> Dict[str, Any]:
        """Get revenue projection based on calculations."""
        return self.calculation_repo.get_revenue_projection(
            fee_structure_id=fee_structure_id,
            months_ahead=months_ahead
        )
    
    def get_discount_impact_analysis(
        self,
        start_date: Optional[Date] = None,
        end_date: Optional[Date] = None
    ) -> Dict[str, Any]:
        """Analyze discount impact."""
        return self.calculation_repo.get_discount_impact_analysis(
            start_date=start_date,
            end_date=end_date
        )
    
    def get_calculation_trends(
        self,
        fee_structure_id: UUID,
        months: int = 6
    ) -> List[Dict[str, Any]]:
        """Get monthly calculation trends."""
        return self.calculation_repo.get_calculation_trends(
            fee_structure_id=fee_structure_id,
            months=months
        )
    
    # ============================================================
    # Helper Methods
    # ============================================================
    
    def _calculate_move_out_date(
        self,
        move_in_date: Date,
        stay_duration_months: int
    ) -> Date:
        """Calculate move-out date from move-in date and duration."""
        # Add months to move-in date
        year = move_in_date.year
        month = move_in_date.month + stay_duration_months
        
        # Handle year rollover
        while month > 12:
            month -= 12
            year += 1
        
        # Create move-out date (same day of month)
        try:
            move_out_date = Date(year, month, move_in_date.day)
        except ValueError:
            # Handle month-end edge cases (e.g., Jan 31 -> Feb 28/29)
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            move_out_date = Date(year, month, min(move_in_date.day, last_day))
        
        return move_out_date
    
    def _calculate_mess_charges(
        self,
        fee_structure: FeeStructure,
        stay_duration_months: int
    ) -> Decimal:
        """Calculate total mess charges."""
        if fee_structure.includes_mess:
            return Decimal('0.00')
        
        return (fee_structure.mess_charges_monthly * stay_duration_months).quantize(
            Decimal('0.01')
        )
    
    def _estimate_utility_charges(
        self,
        fee_structure: FeeStructure,
        stay_duration_months: int
    ) -> Decimal:
        """Estimate total utility charges."""
        from app.models.base.enums import ChargeType
        
        total = Decimal('0.00')
        
        # Electricity
        if fee_structure.electricity_charges == ChargeType.FIXED_MONTHLY:
            if fee_structure.electricity_fixed_amount:
                total += fee_structure.electricity_fixed_amount * stay_duration_months
        elif fee_structure.electricity_charges == ChargeType.ACTUAL:
            # Estimate (e.g., 500 per month)
            total += Decimal('500.00') * stay_duration_months
        
        # Water
        if fee_structure.water_charges == ChargeType.FIXED_MONTHLY:
            if fee_structure.water_fixed_amount:
                total += fee_structure.water_fixed_amount * stay_duration_months
        elif fee_structure.water_charges == ChargeType.ACTUAL:
            # Estimate (e.g., 200 per month)
            total += Decimal('200.00') * stay_duration_months
        
        return total.quantize(Decimal('0.01'))
    
    def _calculate_component_amount(
        self,
        component: ChargeComponent,
        stay_duration_months: int
    ) -> Decimal:
        """Calculate total amount for a component."""
        if component.is_recurring:
            return (component.amount * stay_duration_months).quantize(Decimal('0.01'))
        else:
            return component.amount.quantize(Decimal('0.01'))
    
    def _calculate_subtotal(
        self,
        monthly_rent: Decimal,
        stay_duration_months: int,
        security_deposit: Decimal,
        mess_charges_total: Decimal,
        utility_charges_estimated: Decimal,
        other_charges: Decimal
    ) -> Decimal:
        """Calculate subtotal before discount and tax."""
        subtotal = (
            (monthly_rent * stay_duration_months) +
            security_deposit +
            mess_charges_total +
            utility_charges_estimated +
            other_charges
        )
        
        return subtotal.quantize(Decimal('0.01'))
    
    def _apply_discount_code(
        self,
        discount_code: str,
        hostel_id: UUID,
        room_type: str,
        base_amount: Decimal,
        is_new_student: bool,
        stay_months: int
    ) -> Optional[Dict[str, Any]]:
        """Apply discount code and return result."""
        try:
            # Find discount
            discount = self.discount_repo.find_by_code(
                discount_code=discount_code,
                validate_active=True
            )
            
            if not discount:
                logger.warning(f"Discount code '{discount_code}' not found or inactive")
                return None
            
            # Validate applicability
            is_valid, error_message = self.discount_repo.validate_discount_applicability(
                discount_id=discount.id,
                hostel_id=hostel_id,
                room_type=room_type,
                is_new_student=is_new_student,
                stay_months=stay_months
            )
            
            if not is_valid:
                logger.warning(f"Discount not applicable: {error_message}")
                return None
            
            # Calculate discount amount
            discount_amount = self.discount_repo.calculate_discount_amount(
                discount_id=discount.id,
                base_amount=base_amount
            )
            
            return {
                'discount_id': str(discount.id),
                'discount_amount': discount_amount,
                'description': f"{discount.discount_name} - {discount_code}"
            }
            
        except Exception as e:
            logger.error(f"Error applying discount code: {str(e)}")
            return None
    
    def _calculate_tax(
        self,
        amount: Decimal,
        tax_percentage: Decimal
    ) -> Decimal:
        """Calculate tax amount."""
        if tax_percentage <= 0:
            return Decimal('0.00')
        
        return (amount * tax_percentage / 100).quantize(Decimal('0.01'))
    
    def _generate_payment_schedule(
        self,
        monthly_recurring: Decimal,
        stay_duration_months: int,
        first_month_total: Decimal,
        move_in_date: Date
    ) -> Dict[str, Any]:
        """Generate monthly payment schedule."""
        schedule = []
        current_date = move_in_date
        
        for month in range(stay_duration_months):
            payment_amount = first_month_total if month == 0 else monthly_recurring
            
            schedule.append({
                'month': month + 1,
                'due_date': current_date.isoformat(),
                'amount': float(payment_amount),
                'description': 'First month payment (includes deposit)' if month == 0 
                              else f'Month {month + 1} payment'
            })
            
            # Move to next month
            year = current_date.year
            month_num = current_date.month + 1
            if month_num > 12:
                month_num = 1
                year += 1
            
            try:
                current_date = Date(year, month_num, move_in_date.day)
            except ValueError:
                import calendar
                last_day = calendar.monthrange(year, month_num)[1]
                current_date = Date(year, month_num, min(move_in_date.day, last_day))
        
        return {
            'total_installments': stay_duration_months,
            'installments': schedule
        }
    
    def _generate_charge_breakdown(
        self,
        fee_structure: FeeStructure,
        monthly_rent: Decimal,
        security_deposit: Decimal,
        mess_charges_total: Decimal,
        utility_charges_estimated: Decimal,
        other_charges: Decimal,
        discount_applied: Decimal,
        tax_amount: Decimal,
        stay_duration_months: int
    ) -> Dict[str, Any]:
        """Generate detailed charge breakdown."""
        return {
            'base_charges': {
                'monthly_rent': float(monthly_rent),
                'total_rent': float(monthly_rent * stay_duration_months),
                'security_deposit': float(security_deposit)
            },
            'recurring_charges': {
                'mess_charges_total': float(mess_charges_total),
                'utility_charges_total': float(utility_charges_estimated),
                'includes_mess': fee_structure.includes_mess
            },
            'additional_charges': {
                'other_charges': float(other_charges)
            },
            'adjustments': {
                'discount_applied': float(discount_applied),
                'tax_amount': float(tax_amount)
            },
            'characteristics': {
                'is_all_inclusive': fee_structure.is_all_inclusive,
                'has_variable_charges': fee_structure.has_variable_charges
            }
        }