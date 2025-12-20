# --- File: C:\Hostel-Main\app\services\fee_structure\proration_service.py ---
"""
Proration Service

Business logic layer for fee proration calculations including
partial month stays, mid-month changes, and refund calculations.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import calendar

from sqlalchemy.orm import Session

from app.models.fee_structure.fee_structure import FeeStructure
from app.models.fee_structure.charge_component import ChargeComponent
from app.repositories.fee_structure.fee_structure_repository import (
    FeeStructureRepository,
)
from app.repositories.fee_structure.charge_component_repository import (
    ChargeComponentRepository,
)
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    BusinessLogicException,
)
from app.core.logging import logger


class ProrationService:
    """
    Proration Service
    
    Provides proration calculations for partial period stays,
    early terminations, and mid-period changes.
    """
    
    def __init__(self, session: Session):
        """
        Initialize service with database session.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.fee_structure_repo = FeeStructureRepository(session)
        self.component_repo = ChargeComponentRepository(session)
    
    # ============================================================
    # Core Proration Operations
    # ============================================================
    
    def calculate_proration(
        self,
        fee_structure_id: UUID,
        start_date: Date,
        end_date: Date,
        proration_method: str = "daily"
    ) -> Dict[str, Any]:
        """
        Calculate prorated fees for a partial period.
        
        Args:
            fee_structure_id: Fee structure identifier
            start_date: Start date of partial period
            end_date: End date of partial period
            proration_method: Method (daily, weekly, monthly)
            
        Returns:
            Dictionary with proration details
            
        Raises:
            NotFoundException: If fee structure not found
            ValidationException: If invalid date range
        """
        logger.info(f"Calculating proration from {start_date} to {end_date}")
        
        # Validate dates
        if end_date <= start_date:
            raise ValidationException("End date must be after start date")
        
        # Get fee structure
        fee_structure = self.fee_structure_repo.get_fee_structure_with_components(
            fee_structure_id
        )
        
        if not fee_structure:
            raise NotFoundException(f"Fee structure {fee_structure_id} not found")
        
        # Calculate days
        actual_days = (end_date - start_date).days + 1  # Include both start and end
        month_days = calendar.monthrange(start_date.year, start_date.month)[1]
        
        # Calculate proration factor
        if proration_method == "daily":
            proration_factor = Decimal(str(actual_days)) / Decimal(str(month_days))
        elif proration_method == "weekly":
            actual_weeks = Decimal(str(actual_days)) / Decimal('7')
            month_weeks = Decimal(str(month_days)) / Decimal('7')
            proration_factor = actual_weeks / month_weeks
        else:  # monthly - no proration
            proration_factor = Decimal('1.00')
        
        # Prorate base rent
        prorated_rent = (fee_structure.amount * proration_factor).quantize(Decimal('0.01'))
        
        # Prorate mess charges if not included
        prorated_mess_charges = Decimal('0.00')
        if not fee_structure.includes_mess:
            prorated_mess_charges = (
                fee_structure.mess_charges_monthly * proration_factor
            ).quantize(Decimal('0.01'))
        
        # Prorate utility charges if fixed
        prorated_utility_charges = Decimal('0.00')
        from app.models.base.enums import ChargeType
        
        if fee_structure.electricity_charges == ChargeType.FIXED_MONTHLY:
            if fee_structure.electricity_fixed_amount:
                prorated_utility_charges += (
                    fee_structure.electricity_fixed_amount * proration_factor
                ).quantize(Decimal('0.01'))
        
        if fee_structure.water_charges == ChargeType.FIXED_MONTHLY:
            if fee_structure.water_fixed_amount:
                prorated_utility_charges += (
                    fee_structure.water_fixed_amount * proration_factor
                ).quantize(Decimal('0.01'))
        
        # Prorate components if they allow proration
        prorated_components = []
        total_component_proration = Decimal('0.00')
        
        if fee_structure.charge_components:
            for component in fee_structure.charge_components:
                if component.deleted_at is None and component.proration_allowed:
                    if component.is_recurring:
                        prorated_amount = (
                            component.amount * proration_factor
                        ).quantize(Decimal('0.01'))
                    else:
                        # One-time charges - full amount or none
                        prorated_amount = component.amount
                    
                    total_component_proration += prorated_amount
                    
                    prorated_components.append({
                        'component_id': str(component.id),
                        'component_name': component.component_name,
                        'original_amount': float(component.amount),
                        'prorated_amount': float(prorated_amount),
                        'is_recurring': component.is_recurring
                    })
        
        # Calculate totals
        total_prorated = (
            prorated_rent + 
            prorated_mess_charges + 
            prorated_utility_charges + 
            total_component_proration
        )
        
        # Security deposit is not prorated
        security_deposit = fee_structure.security_deposit
        
        return {
            'fee_structure_id': str(fee_structure_id),
            'proration_method': proration_method,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'actual_days': actual_days,
                'month_days': month_days,
                'proration_factor': float(proration_factor)
            },
            'prorated_charges': {
                'base_rent': {
                    'original': float(fee_structure.amount),
                    'prorated': float(prorated_rent)
                },
                'mess_charges': {
                    'original': float(fee_structure.mess_charges_monthly),
                    'prorated': float(prorated_mess_charges)
                },
                'utility_charges': {
                    'prorated': float(prorated_utility_charges)
                },
                'components': prorated_components,
                'total_components': float(total_component_proration)
            },
            'totals': {
                'total_prorated': float(total_prorated),
                'security_deposit': float(security_deposit),
                'total_with_deposit': float(total_prorated + security_deposit)
            },
            'original_monthly_total': float(
                fee_structure.amount + 
                fee_structure.mess_charges_monthly
            ),
            'savings': float(
                (fee_structure.amount + fee_structure.mess_charges_monthly) - 
                total_prorated
            )
        }
    
    def calculate_early_termination_refund(
        self,
        fee_structure_id: UUID,
        original_move_in_date: Date,
        original_move_out_date: Date,
        actual_move_out_date: Date,
        paid_amount: Decimal,
        security_deposit_paid: Decimal
    ) -> Dict[str, Any]:
        """
        Calculate refund for early termination.
        
        Args:
            fee_structure_id: Fee structure identifier
            original_move_in_date: Original move-in date
            original_move_out_date: Original planned move-out date
            actual_move_out_date: Actual early move-out date
            paid_amount: Total amount already paid
            security_deposit_paid: Security deposit paid
            
        Returns:
            Dictionary with refund calculation
            
        Raises:
            ValidationException: If dates invalid
        """
        logger.info(f"Calculating early termination refund")
        
        # Validate dates
        if actual_move_out_date >= original_move_out_date:
            raise ValidationException(
                "Actual move-out date must be before original move-out date for early termination"
            )
        
        if actual_move_out_date <= original_move_in_date:
            raise ValidationException(
                "Actual move-out date must be after move-in date"
            )
        
        # Get fee structure
        fee_structure = self.fee_structure_repo.get_fee_structure_with_components(
            fee_structure_id
        )
        
        if not fee_structure:
            raise NotFoundException(f"Fee structure {fee_structure_id} not found")
        
        # Calculate original duration and actual duration
        original_days = (original_move_out_date - original_move_in_date).days + 1
        actual_days = (actual_move_out_date - original_move_in_date).days + 1
        unused_days = original_days - actual_days
        
        # Calculate what should have been paid for actual duration
        actual_proration = self.calculate_proration(
            fee_structure_id=fee_structure_id,
            start_date=original_move_in_date,
            end_date=actual_move_out_date,
            proration_method="daily"
        )
        
        amount_should_have_paid = Decimal(str(
            actual_proration['totals']['total_prorated']
        ))
        
        # Calculate refundable components
        refundable_components = []
        total_refundable_components = Decimal('0.00')
        
        if fee_structure.charge_components:
            for component in fee_structure.charge_components:
                if component.deleted_at is None and component.is_refundable:
                    refundable_components.append({
                        'component_id': str(component.id),
                        'component_name': component.component_name,
                        'amount': float(component.amount)
                    })
                    total_refundable_components += component.amount
        
        # Calculate base refund (excluding deposit)
        base_refund = paid_amount - amount_should_have_paid - security_deposit_paid
        
        # Add refundable components
        total_refund_before_deposit = base_refund + total_refundable_components
        
        # Security deposit refund (full amount minus any deductions)
        security_deposit_refund = security_deposit_paid  # Full refund by default
        
        # Total refund
        total_refund = total_refund_before_deposit + security_deposit_refund
        
        # Apply early termination penalty if applicable
        penalty_percentage = self._get_early_termination_penalty(
            fee_structure_id=fee_structure_id,
            days_remaining=unused_days
        )
        
        penalty_amount = (total_refund_before_deposit * penalty_percentage / 100).quantize(
            Decimal('0.01')
        )
        
        final_refund = total_refund - penalty_amount
        
        return {
            'fee_structure_id': str(fee_structure_id),
            'termination_details': {
                'original_move_in_date': original_move_in_date.isoformat(),
                'original_move_out_date': original_move_out_date.isoformat(),
                'actual_move_out_date': actual_move_out_date.isoformat(),
                'original_days': original_days,
                'actual_days': actual_days,
                'unused_days': unused_days
            },
            'payment_details': {
                'total_paid': float(paid_amount),
                'security_deposit_paid': float(security_deposit_paid),
                'amount_for_actual_stay': float(amount_should_have_paid)
            },
            'refund_calculation': {
                'base_refund': float(base_refund),
                'refundable_components': refundable_components,
                'total_refundable_components': float(total_refundable_components),
                'security_deposit_refund': float(security_deposit_refund),
                'total_before_penalty': float(total_refund),
                'penalty_percentage': float(penalty_percentage),
                'penalty_amount': float(penalty_amount),
                'final_refund': float(final_refund)
            },
            'refund_breakdown': {
                'unused_rent_refund': float(base_refund),
                'component_refunds': float(total_refundable_components),
                'security_deposit': float(security_deposit_refund),
                'penalty_deduction': float(penalty_amount),
                'net_refund': float(final_refund)
            }
        }
    
    def calculate_mid_period_change_adjustment(
        self,
        original_fee_structure_id: UUID,
        new_fee_structure_id: UUID,
        change_date: Date,
        period_start_date: Date,
        period_end_date: Date
    ) -> Dict[str, Any]:
        """
        Calculate adjustment for mid-period fee structure change.
        
        Args:
            original_fee_structure_id: Original fee structure
            new_fee_structure_id: New fee structure
            change_date: Date of change
            period_start_date: Start of billing period
            period_end_date: End of billing period
            
        Returns:
            Dictionary with adjustment calculation
            
        Raises:
            ValidationException: If dates invalid
        """
        logger.info(f"Calculating mid-period change adjustment")
        
        # Validate dates
        if change_date < period_start_date or change_date > period_end_date:
            raise ValidationException(
                "Change date must be within the billing period"
            )
        
        # Calculate proration for original fee structure (start to change date)
        original_proration = self.calculate_proration(
            fee_structure_id=original_fee_structure_id,
            start_date=period_start_date,
            end_date=change_date,
            proration_method="daily"
        )
        
        # Calculate proration for new fee structure (change date to end)
        new_proration = self.calculate_proration(
            fee_structure_id=new_fee_structure_id,
            start_date=change_date,
            end_date=period_end_date,
            proration_method="daily"
        )
        
        # Calculate adjustment amount
        original_amount = Decimal(str(original_proration['totals']['total_prorated']))
        new_amount = Decimal(str(new_proration['totals']['total_prorated']))
        total_amount = original_amount + new_amount
        
        # Get original full month amount
        original_fs = self.fee_structure_repo.find_by_id(original_fee_structure_id)
        original_monthly = original_fs.amount if original_fs else Decimal('0.00')
        
        adjustment = total_amount - original_monthly
        
        return {
            'change_details': {
                'change_date': change_date.isoformat(),
                'period_start_date': period_start_date.isoformat(),
                'period_end_date': period_end_date.isoformat()
            },
            'original_fee_structure': {
                'id': str(original_fee_structure_id),
                'days': original_proration['period']['actual_days'],
                'prorated_amount': float(original_amount)
            },
            'new_fee_structure': {
                'id': str(new_fee_structure_id),
                'days': new_proration['period']['actual_days'],
                'prorated_amount': float(new_amount)
            },
            'adjustment': {
                'original_monthly_amount': float(original_monthly),
                'total_prorated_amount': float(total_amount),
                'adjustment_amount': float(adjustment),
                'adjustment_type': 'credit' if adjustment < 0 else 'charge'
            }
        }
    
    def calculate_partial_month_refund(
        self,
        fee_structure_id: UUID,
        month_start_date: Date,
        vacate_date: Date,
        monthly_amount_paid: Decimal
    ) -> Dict[str, Any]:
        """
        Calculate refund for partial month stay.
        
        Args:
            fee_structure_id: Fee structure identifier
            month_start_date: Start of the month
            vacate_date: Date of vacating
            monthly_amount_paid: Monthly amount already paid
            
        Returns:
            Dictionary with refund calculation
        """
        logger.info(f"Calculating partial month refund for vacate date {vacate_date}")
        
        # Calculate proration for days stayed
        proration = self.calculate_proration(
            fee_structure_id=fee_structure_id,
            start_date=month_start_date,
            end_date=vacate_date,
            proration_method="daily"
        )
        
        amount_for_days_stayed = Decimal(str(proration['totals']['total_prorated']))
        refund_amount = (monthly_amount_paid - amount_for_days_stayed).quantize(
            Decimal('0.01')
        )
        
        return {
            'fee_structure_id': str(fee_structure_id),
            'period': {
                'month_start_date': month_start_date.isoformat(),
                'vacate_date': vacate_date.isoformat(),
                'days_stayed': proration['period']['actual_days'],
                'month_days': proration['period']['month_days']
            },
            'amounts': {
                'monthly_amount_paid': float(monthly_amount_paid),
                'amount_for_days_stayed': float(amount_for_days_stayed),
                'refund_amount': float(refund_amount)
            },
            'refund_percentage': float(
                (refund_amount / monthly_amount_paid * 100) if monthly_amount_paid > 0 else 0
            )
        }
    
    # ============================================================
    # Component-Level Proration
    # ============================================================
    
    def prorate_component(
        self,
        component_id: UUID,
        start_date: Date,
        end_date: Date
    ) -> Dict[str, Any]:
        """
        Prorate a specific charge component.
        
        Args:
            component_id: Component identifier
            start_date: Start date
            end_date: End date
            
        Returns:
            Dictionary with component proration
            
        Raises:
            NotFoundException: If component not found
            BusinessLogicException: If component doesn't allow proration
        """
        component = self.component_repo.find_by_id(component_id)
        
        if not component:
            raise NotFoundException(f"Charge component {component_id} not found")
        
        if not component.proration_allowed:
            raise BusinessLogicException(
                f"Component '{component.component_name}' does not allow proration"
            )
        
        # Calculate days
        actual_days = (end_date - start_date).days + 1
        month_days = calendar.monthrange(start_date.year, start_date.month)[1]
        proration_factor = Decimal(str(actual_days)) / Decimal(str(month_days))
        
        # Calculate prorated amount
        if component.is_recurring:
            prorated_amount = (component.amount * proration_factor).quantize(Decimal('0.01'))
        else:
            # One-time charges - full amount
            prorated_amount = component.amount
        
        # Calculate tax if applicable
        tax_amount = Decimal('0.00')
        if component.is_taxable:
            tax_amount = (prorated_amount * component.tax_percentage / 100).quantize(
                Decimal('0.01')
            )
        
        total_with_tax = prorated_amount + tax_amount
        
        return {
            'component_id': str(component_id),
            'component_name': component.component_name,
            'component_type': component.component_type,
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'actual_days': actual_days,
                'month_days': month_days,
                'proration_factor': float(proration_factor)
            },
            'amounts': {
                'original_amount': float(component.amount),
                'prorated_amount': float(prorated_amount),
                'tax_amount': float(tax_amount),
                'total_with_tax': float(total_with_tax)
            },
            'component_details': {
                'is_recurring': component.is_recurring,
                'is_taxable': component.is_taxable,
                'tax_percentage': float(component.tax_percentage),
                'is_refundable': component.is_refundable
            }
        }
    
    def get_proratable_components(
        self,
        fee_structure_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get all components that allow proration.
        
        Args:
            fee_structure_id: Fee structure identifier
            
        Returns:
            List of proratable components
        """
        components = self.component_repo.find_proratable_components(fee_structure_id)
        
        return [
            {
                'component_id': str(c.id),
                'component_name': c.component_name,
                'component_type': c.component_type,
                'amount': float(c.amount),
                'is_recurring': c.is_recurring,
                'is_taxable': c.is_taxable,
                'is_refundable': c.is_refundable
            }
            for c in components
        ]
    
    # ============================================================
    # Proration Rules and Policies
    # ============================================================
    
    def get_proration_policy(
        self,
        fee_structure_id: UUID
    ) -> Dict[str, Any]:
        """
        Get proration policy for a fee structure.
        
        Args:
            fee_structure_id: Fee structure identifier
            
        Returns:
            Dictionary with proration policy
        """
        fee_structure = self.fee_structure_repo.get_fee_structure_with_components(
            fee_structure_id
        )
        
        if not fee_structure:
            raise NotFoundException(f"Fee structure {fee_structure_id} not found")
        
        # Count proratable components
        proratable_count = 0
        if fee_structure.charge_components:
            proratable_count = sum(
                1 for c in fee_structure.charge_components 
                if c.proration_allowed and c.deleted_at is None
            )
        
        return {
            'fee_structure_id': str(fee_structure_id),
            'proration_enabled': True,  # Can be configured per fee structure
            'proration_method': 'daily',  # Default method
            'minimum_days_for_charge': 1,  # Minimum days to charge
            'refund_policy': {
                'allows_partial_refund': True,
                'refund_processing_days': 7,
                'minimum_refund_amount': 100.00
            },
            'component_policy': {
                'total_components': len(fee_structure.charge_components or []),
                'proratable_components': proratable_count,
                'non_proratable_components': len(fee_structure.charge_components or []) - proratable_count
            },
            'early_termination': {
                'allowed': True,
                'notice_period_days': 30,
                'penalty_structure': 'tiered'  # tiered, fixed, percentage
            }
        }
    
    def validate_proration_eligibility(
        self,
        fee_structure_id: UUID,
        start_date: Date,
        end_date: Date
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if proration is eligible for given dates.
        
        Args:
            fee_structure_id: Fee structure identifier
            start_date: Start date
            end_date: End date
            
        Returns:
            Tuple of (is_eligible, reason)
        """
        # Check date validity
        if end_date <= start_date:
            return False, "End date must be after start date"
        
        # Check if dates are within same month
        if start_date.month != end_date.month or start_date.year != end_date.year:
            return False, "Proration only applicable within the same month"
        
        # Check minimum stay
        days = (end_date - start_date).days + 1
        if days < 1:
            return False, "Minimum stay of 1 day required for proration"
        
        # Get fee structure
        fee_structure = self.fee_structure_repo.find_by_id(fee_structure_id)
        if not fee_structure:
            return False, "Fee structure not found"
        
        # Check if fee structure is active
        if not fee_structure.is_active:
            return False, "Fee structure is not active"
        
        return True, None
    
    # ============================================================
    # Helper Methods
    # ============================================================
    
    def _get_early_termination_penalty(
        self,
        fee_structure_id: UUID,
        days_remaining: int
    ) -> Decimal:
        """
        Calculate early termination penalty percentage.
        
        This can be customized based on business rules.
        Current implementation uses tiered approach:
        - > 60 days: 25% penalty
        - 30-60 days: 15% penalty
        - < 30 days: 5% penalty
        """
        if days_remaining > 60:
            return Decimal('25.00')
        elif days_remaining > 30:
            return Decimal('15.00')
        else:
            return Decimal('5.00')
    
    def _calculate_proration_factor(
        self,
        start_date: Date,
        end_date: Date,
        method: str = "daily"
    ) -> Decimal:
        """Calculate proration factor based on method."""
        actual_days = (end_date - start_date).days + 1
        
        if method == "daily":
            month_days = calendar.monthrange(start_date.year, start_date.month)[1]
            return Decimal(str(actual_days)) / Decimal(str(month_days))
        
        elif method == "weekly":
            actual_weeks = Decimal(str(actual_days)) / Decimal('7')
            month_days = calendar.monthrange(start_date.year, start_date.month)[1]
            month_weeks = Decimal(str(month_days)) / Decimal('7')
            return actual_weeks / month_weeks
        
        else:  # monthly
            return Decimal('1.00')
    
    def calculate_notice_period_charges(
        self,
        fee_structure_id: UUID,
        notice_given_date: Date,
        intended_vacate_date: Date,
        required_notice_days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate charges for notice period violation.
        
        Args:
            fee_structure_id: Fee structure identifier
            notice_given_date: Date when notice was given
            intended_vacate_date: Intended date of vacating
            required_notice_days: Required notice period in days
            
        Returns:
            Dictionary with notice period charge calculation
        """
        # Calculate actual notice days
        actual_notice_days = (intended_vacate_date - notice_given_date).days
        
        if actual_notice_days >= required_notice_days:
            return {
                'notice_compliant': True,
                'actual_notice_days': actual_notice_days,
                'required_notice_days': required_notice_days,
                'shortfall_days': 0,
                'penalty_charge': 0.00,
                'message': 'Notice period requirement met'
            }
        
        # Calculate shortfall
        shortfall_days = required_notice_days - actual_notice_days
        
        # Get fee structure
        fee_structure = self.fee_structure_repo.find_by_id(fee_structure_id)
        if not fee_structure:
            raise NotFoundException(f"Fee structure {fee_structure_id} not found")
        
        # Calculate daily rent
        month_days = 30  # Standard month for calculation
        daily_rent = (fee_structure.amount / Decimal(str(month_days))).quantize(
            Decimal('0.01')
        )
        
        # Penalty is daily rent for shortfall days
        penalty_charge = (daily_rent * Decimal(str(shortfall_days))).quantize(
            Decimal('0.01')
        )
        
        return {
            'notice_compliant': False,
            'actual_notice_days': actual_notice_days,
            'required_notice_days': required_notice_days,
            'shortfall_days': shortfall_days,
            'daily_rent': float(daily_rent),
            'penalty_charge': float(penalty_charge),
            'message': f'Notice period shortfall of {shortfall_days} days'
        }