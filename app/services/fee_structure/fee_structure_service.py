# --- File: C:\Hostel-Main\app\services\fee_structure\fee_structure_service.py ---
"""
Fee Structure Service

Business logic layer for fee structure management including creation,
updates, versioning, validation, and comprehensive fee operations.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.fee_structure.fee_structure import FeeStructure, FeeApproval
from app.models.base.enums import RoomType, FeeType, ChargeType
from app.repositories.fee_structure.fee_structure_repository import (
    FeeStructureRepository,
)
from app.repositories.fee_structure.charge_component_repository import (
    ChargeComponentRepository,
)
from app.repositories.fee_structure.fee_aggregate_repository import (
    FeeAggregateRepository,
)
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    ConflictException,
    BusinessLogicException,
)
from app.core.logging import logger


class FeeStructureService:
    """
    Fee Structure Service
    
    Provides high-level business operations for fee structure management
    including creation, updates, versioning, and comprehensive validation.
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
        self.aggregate_repo = FeeAggregateRepository(session)
    
    # ============================================================
    # Core Fee Structure Operations
    # ============================================================
    
    def create_fee_structure(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        fee_type: FeeType,
        amount: Decimal,
        security_deposit: Decimal,
        effective_from: Date,
        user_id: UUID,
        includes_mess: bool = False,
        mess_charges_monthly: Optional[Decimal] = None,
        electricity_charges: ChargeType = ChargeType.INCLUDED,
        electricity_fixed_amount: Optional[Decimal] = None,
        water_charges: ChargeType = ChargeType.INCLUDED,
        water_fixed_amount: Optional[Decimal] = None,
        effective_to: Optional[Date] = None,
        description: Optional[str] = None,
        requires_approval: bool = True
    ) -> FeeStructure:
        """
        Create a new fee structure with comprehensive validation.
        
        Args:
            hostel_id: Hostel identifier
            room_type: Room type enum
            fee_type: Fee type enum
            amount: Base monthly amount
            security_deposit: Security deposit amount
            effective_from: Effective start date
            user_id: User creating the structure
            includes_mess: Whether mess is included
            mess_charges_monthly: Monthly mess charges if not included
            electricity_charges: Electricity charge type
            electricity_fixed_amount: Fixed electricity amount if applicable
            water_charges: Water charge type
            water_fixed_amount: Fixed water amount if applicable
            effective_to: Optional effective end date
            description: Optional description
            requires_approval: Whether approval is required
            
        Returns:
            Created FeeStructure instance
            
        Raises:
            ValidationException: If validation fails
            ConflictException: If overlapping structure exists
        """
        logger.info(
            f"Creating fee structure for hostel {hostel_id}, "
            f"room_type={room_type.value}, fee_type={fee_type.value}"
        )
        
        # Validate business rules
        self._validate_fee_structure_creation(
            amount=amount,
            security_deposit=security_deposit,
            includes_mess=includes_mess,
            mess_charges_monthly=mess_charges_monthly,
            electricity_charges=electricity_charges,
            electricity_fixed_amount=electricity_fixed_amount,
            water_charges=water_charges,
            water_fixed_amount=water_fixed_amount,
            effective_from=effective_from,
            effective_to=effective_to
        )
        
        # Prepare audit context
        audit_context = {
            'user_id': user_id,
            'action': 'create_fee_structure',
            'timestamp': datetime.utcnow()
        }
        
        try:
            # Create fee structure
            fee_structure = self.fee_structure_repo.create_fee_structure(
                hostel_id=hostel_id,
                room_type=room_type,
                fee_type=fee_type,
                amount=amount,
                security_deposit=security_deposit,
                effective_from=effective_from,
                audit_context=audit_context,
                includes_mess=includes_mess,
                mess_charges_monthly=mess_charges_monthly or Decimal('0.00'),
                electricity_charges=electricity_charges,
                electricity_fixed_amount=electricity_fixed_amount,
                water_charges=water_charges,
                water_fixed_amount=water_fixed_amount,
                effective_to=effective_to,
                description=description,
                is_active=not requires_approval  # Inactive until approved if required
            )
            
            # Create approval record if required
            if requires_approval:
                self._create_approval_record(
                    fee_structure_id=fee_structure.id,
                    user_id=user_id,
                    previous_amount=None,
                    new_amount=amount,
                    change_summary="New fee structure created"
                )
            
            self.session.commit()
            
            logger.info(f"Fee structure created successfully: {fee_structure.id}")
            return fee_structure
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating fee structure: {str(e)}")
            raise
    
    def update_fee_structure(
        self,
        fee_structure_id: UUID,
        user_id: UUID,
        amount: Optional[Decimal] = None,
        security_deposit: Optional[Decimal] = None,
        mess_charges_monthly: Optional[Decimal] = None,
        includes_mess: Optional[bool] = None,
        electricity_charges: Optional[ChargeType] = None,
        electricity_fixed_amount: Optional[Decimal] = None,
        water_charges: Optional[ChargeType] = None,
        water_fixed_amount: Optional[Decimal] = None,
        effective_from: Optional[Date] = None,
        effective_to: Optional[Date] = None,
        description: Optional[str] = None,
        create_new_version: bool = True,
        requires_approval: bool = True
    ) -> FeeStructure:
        """
        Update existing fee structure with versioning support.
        
        Args:
            fee_structure_id: Fee structure to update
            user_id: User performing update
            amount: New amount (if changing)
            security_deposit: New security deposit (if changing)
            mess_charges_monthly: New mess charges (if changing)
            includes_mess: New includes_mess flag (if changing)
            electricity_charges: New electricity charge type (if changing)
            electricity_fixed_amount: New electricity amount (if changing)
            water_charges: New water charge type (if changing)
            water_fixed_amount: New water amount (if changing)
            effective_from: New effective_from date (if changing)
            effective_to: New effective_to date (if changing)
            description: New description (if changing)
            create_new_version: Whether to create new version or update in-place
            requires_approval: Whether approval is required
            
        Returns:
            Updated or new version of FeeStructure
            
        Raises:
            NotFoundException: If fee structure not found
            ValidationException: If validation fails
        """
        logger.info(f"Updating fee structure {fee_structure_id}")
        
        # Get existing fee structure
        existing = self.fee_structure_repo.find_by_id(fee_structure_id)
        if not existing:
            raise NotFoundException(f"Fee structure {fee_structure_id} not found")
        
        # Build update data
        update_data = {}
        if amount is not None:
            update_data['amount'] = amount
        if security_deposit is not None:
            update_data['security_deposit'] = security_deposit
        if mess_charges_monthly is not None:
            update_data['mess_charges_monthly'] = mess_charges_monthly
        if includes_mess is not None:
            update_data['includes_mess'] = includes_mess
        if electricity_charges is not None:
            update_data['electricity_charges'] = electricity_charges
        if electricity_fixed_amount is not None:
            update_data['electricity_fixed_amount'] = electricity_fixed_amount
        if water_charges is not None:
            update_data['water_charges'] = water_charges
        if water_fixed_amount is not None:
            update_data['water_fixed_amount'] = water_fixed_amount
        if effective_from is not None:
            update_data['effective_from'] = effective_from
        if effective_to is not None:
            update_data['effective_to'] = effective_to
        if description is not None:
            update_data['description'] = description
        
        # Validate update
        self._validate_fee_structure_update(existing, update_data)
        
        # Prepare audit context
        audit_context = {
            'user_id': user_id,
            'action': 'update_fee_structure',
            'timestamp': datetime.utcnow()
        }
        
        try:
            # Update fee structure
            updated = self.fee_structure_repo.update_fee_structure(
                fee_structure_id=fee_structure_id,
                update_data=update_data,
                audit_context=audit_context,
                create_new_version=create_new_version
            )
            
            # Create approval record if required
            if requires_approval:
                change_summary = self._generate_change_summary(existing, update_data)
                self._create_approval_record(
                    fee_structure_id=updated.id,
                    user_id=user_id,
                    previous_amount=existing.amount,
                    new_amount=update_data.get('amount', existing.amount),
                    change_summary=change_summary
                )
            
            self.session.commit()
            
            logger.info(f"Fee structure updated successfully: {updated.id}")
            return updated
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating fee structure: {str(e)}")
            raise
    
    def delete_fee_structure(
        self,
        fee_structure_id: UUID,
        user_id: UUID,
        hard_delete: bool = False
    ) -> bool:
        """
        Delete fee structure (soft or hard delete).
        
        Args:
            fee_structure_id: Fee structure to delete
            user_id: User performing deletion
            hard_delete: If True, permanently delete; otherwise soft delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            NotFoundException: If fee structure not found
            BusinessLogicException: If deletion not allowed
        """
        logger.info(f"Deleting fee structure {fee_structure_id}")
        
        # Get fee structure
        fee_structure = self.fee_structure_repo.find_by_id(fee_structure_id)
        if not fee_structure:
            raise NotFoundException(f"Fee structure {fee_structure_id} not found")
        
        # Check if deletion is allowed
        if not self._can_delete_fee_structure(fee_structure):
            raise BusinessLogicException(
                "Cannot delete fee structure with active bookings or calculations"
            )
        
        try:
            if hard_delete:
                self.session.delete(fee_structure)
            else:
                fee_structure.deleted_at = datetime.utcnow()
                fee_structure.deleted_by = user_id
                fee_structure.is_active = False
            
            self.session.commit()
            
            logger.info(f"Fee structure deleted successfully: {fee_structure_id}")
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error deleting fee structure: {str(e)}")
            raise
    
    # ============================================================
    # Fee Structure Retrieval
    # ============================================================
    
    def get_fee_structure(
        self,
        fee_structure_id: UUID,
        include_components: bool = False
    ) -> FeeStructure:
        """
        Get fee structure by ID.
        
        Args:
            fee_structure_id: Fee structure identifier
            include_components: Whether to load charge components
            
        Returns:
            FeeStructure instance
            
        Raises:
            NotFoundException: If not found
        """
        if include_components:
            fee_structure = self.fee_structure_repo.get_fee_structure_with_components(
                fee_structure_id
            )
        else:
            fee_structure = self.fee_structure_repo.find_by_id(fee_structure_id)
        
        if not fee_structure:
            raise NotFoundException(f"Fee structure {fee_structure_id} not found")
        
        return fee_structure
    
    def get_current_fee_structure(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        fee_type: FeeType,
        as_of_date: Optional[Date] = None
    ) -> Optional[FeeStructure]:
        """
        Get currently effective fee structure.
        
        Args:
            hostel_id: Hostel identifier
            room_type: Room type
            fee_type: Fee type
            as_of_date: Date to check (defaults to today)
            
        Returns:
            Current FeeStructure or None
        """
        return self.fee_structure_repo.get_current_fee_structure(
            hostel_id=hostel_id,
            room_type=room_type,
            fee_type=fee_type,
            as_of_date=as_of_date
        )
    
    def get_fee_structures_by_hostel(
        self,
        hostel_id: UUID,
        room_type: Optional[RoomType] = None,
        fee_type: Optional[FeeType] = None,
        include_inactive: bool = False,
        as_of_date: Optional[Date] = None
    ) -> List[FeeStructure]:
        """
        Get all fee structures for a hostel.
        
        Args:
            hostel_id: Hostel identifier
            room_type: Optional room type filter
            fee_type: Optional fee type filter
            include_inactive: Include inactive structures
            as_of_date: Find structures effective as of this date
            
        Returns:
            List of FeeStructure instances
        """
        if room_type:
            return self.fee_structure_repo.find_by_hostel_and_room_type(
                hostel_id=hostel_id,
                room_type=room_type,
                fee_type=fee_type,
                include_inactive=include_inactive,
                as_of_date=as_of_date
            )
        else:
            # Get all room types
            all_structures = []
            for rt in RoomType:
                structures = self.fee_structure_repo.find_by_hostel_and_room_type(
                    hostel_id=hostel_id,
                    room_type=rt,
                    fee_type=fee_type,
                    include_inactive=include_inactive,
                    as_of_date=as_of_date
                )
                all_structures.extend(structures)
            return all_structures
    
    def get_version_history(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        fee_type: FeeType
    ) -> List[FeeStructure]:
        """
        Get complete version history for a fee structure.
        
        Args:
            hostel_id: Hostel identifier
            room_type: Room type
            fee_type: Fee type
            
        Returns:
            List of all versions ordered by version number
        """
        return self.fee_structure_repo.get_version_history(
            hostel_id=hostel_id,
            room_type=room_type,
            fee_type=fee_type
        )
    
    # ============================================================
    # Fee Calculation and Estimation
    # ============================================================
    
    def calculate_total_fee(
        self,
        fee_structure_id: UUID,
        stay_duration_months: int,
        include_security_deposit: bool = True,
        include_components: bool = True,
        discount_percentage: Optional[Decimal] = None
    ) -> Dict[str, Any]:
        """
        Calculate total fee for a stay duration.
        
        Args:
            fee_structure_id: Fee structure identifier
            stay_duration_months: Number of months
            include_security_deposit: Include deposit in total
            include_components: Include charge components
            discount_percentage: Optional discount percentage
            
        Returns:
            Dictionary with fee breakdown
            
        Raises:
            NotFoundException: If fee structure not found
            ValidationException: If invalid duration
        """
        if stay_duration_months < 1:
            raise ValidationException("Stay duration must be at least 1 month")
        
        fee_structure = self.get_fee_structure(
            fee_structure_id,
            include_components=include_components
        )
        
        # Base monthly charges
        monthly_base = fee_structure.amount
        
        # Mess charges
        monthly_mess = Decimal('0.00')
        if not fee_structure.includes_mess:
            monthly_mess = fee_structure.mess_charges_monthly
        
        # Utility charges (if fixed)
        monthly_utilities = Decimal('0.00')
        if fee_structure.electricity_charges == ChargeType.FIXED_MONTHLY:
            monthly_utilities += fee_structure.electricity_fixed_amount or Decimal('0.00')
        if fee_structure.water_charges == ChargeType.FIXED_MONTHLY:
            monthly_utilities += fee_structure.water_fixed_amount or Decimal('0.00')
        
        # Total monthly recurring
        monthly_recurring = monthly_base + monthly_mess + monthly_utilities
        
        # Calculate components total if included
        components_total = Decimal('0.00')
        components_breakdown = []
        if include_components and fee_structure.charge_components:
            for component in fee_structure.charge_components:
                if component.deleted_at is None:
                    comp_amount = component.amount
                    if component.is_recurring:
                        comp_amount *= stay_duration_months
                    components_total += comp_amount
                    components_breakdown.append({
                        'id': str(component.id),
                        'name': component.component_name,
                        'type': component.component_type,
                        'amount': float(comp_amount),
                        'is_recurring': component.is_recurring
                    })
        
        # Calculate subtotal
        subtotal = (monthly_recurring * stay_duration_months) + components_total
        
        # Add security deposit if included
        if include_security_deposit:
            subtotal += fee_structure.security_deposit
        
        # Apply discount if provided
        discount_amount = Decimal('0.00')
        if discount_percentage and discount_percentage > 0:
            discount_amount = (subtotal * discount_percentage / 100).quantize(Decimal('0.01'))
        
        # Calculate final total
        total = subtotal - discount_amount
        
        # First month payment (includes deposit)
        first_month_total = monthly_recurring + components_total
        if include_security_deposit:
            first_month_total += fee_structure.security_deposit
        
        return {
            'fee_structure_id': str(fee_structure_id),
            'stay_duration_months': stay_duration_months,
            'breakdown': {
                'monthly_base_rent': float(monthly_base),
                'monthly_mess_charges': float(monthly_mess),
                'monthly_utilities': float(monthly_utilities),
                'monthly_recurring_total': float(monthly_recurring),
                'security_deposit': float(fee_structure.security_deposit) if include_security_deposit else 0,
                'components_total': float(components_total),
                'components_breakdown': components_breakdown
            },
            'totals': {
                'subtotal': float(subtotal),
                'discount_percentage': float(discount_percentage or 0),
                'discount_amount': float(discount_amount),
                'total': float(total),
                'first_month_payment': float(first_month_total),
                'subsequent_monthly_payment': float(monthly_recurring)
            },
            'characteristics': {
                'includes_mess': fee_structure.includes_mess,
                'is_all_inclusive': fee_structure.is_all_inclusive,
                'has_variable_charges': fee_structure.has_variable_charges
            }
        }
    
    def estimate_monthly_cost(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        fee_type: FeeType,
        as_of_date: Optional[Date] = None
    ) -> Dict[str, Any]:
        """
        Estimate monthly cost for a room type.
        
        Args:
            hostel_id: Hostel identifier
            room_type: Room type
            fee_type: Fee type
            as_of_date: Date to check (defaults to today)
            
        Returns:
            Dictionary with cost estimates
            
        Raises:
            NotFoundException: If no fee structure found
        """
        fee_structure = self.get_current_fee_structure(
            hostel_id=hostel_id,
            room_type=room_type,
            fee_type=fee_type,
            as_of_date=as_of_date
        )
        
        if not fee_structure:
            raise NotFoundException(
                f"No active fee structure found for {hostel_id}/{room_type.value}/{fee_type.value}"
            )
        
        # Calculate minimum and maximum monthly costs
        minimum_monthly = fee_structure.monthly_total_minimum
        
        # Maximum could include variable utilities (estimate)
        maximum_monthly = minimum_monthly
        if fee_structure.has_variable_charges:
            # Add estimated maximum for variable charges (rough estimate)
            if fee_structure.electricity_charges == ChargeType.ACTUAL:
                maximum_monthly += Decimal('1000.00')  # Estimate
            if fee_structure.water_charges == ChargeType.ACTUAL:
                maximum_monthly += Decimal('500.00')  # Estimate
        
        return {
            'hostel_id': str(hostel_id),
            'room_type': room_type.value,
            'fee_type': fee_type.value,
            'minimum_monthly_cost': float(minimum_monthly),
            'maximum_monthly_cost': float(maximum_monthly),
            'base_rent': float(fee_structure.amount),
            'security_deposit': float(fee_structure.security_deposit),
            'includes_mess': fee_structure.includes_mess,
            'mess_charges': float(fee_structure.mess_charges_monthly),
            'has_variable_charges': fee_structure.has_variable_charges,
            'is_all_inclusive': fee_structure.is_all_inclusive,
            'effective_from': fee_structure.effective_from.isoformat(),
            'effective_to': fee_structure.effective_to.isoformat() if fee_structure.effective_to else None
        }
    
    # ============================================================
    # Analytics and Reporting
    # ============================================================
    
    def get_hostel_fee_summary(
        self,
        hostel_id: UUID,
        as_of_date: Optional[Date] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive fee summary for a hostel.
        
        Args:
            hostel_id: Hostel identifier
            as_of_date: Date to check (defaults to today)
            
        Returns:
            Dictionary with comprehensive fee summary
        """
        return self.aggregate_repo.get_hostel_fee_summary(
            hostel_id=hostel_id,
            as_of_date=as_of_date
        )
    
    def get_pricing_analytics(
        self,
        hostel_ids: Optional[List[UUID]] = None,
        room_type: Optional[RoomType] = None,
        as_of_date: Optional[Date] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive pricing analytics.
        
        Args:
            hostel_ids: Optional list of hostel IDs
            room_type: Optional room type filter
            as_of_date: Date to check
            
        Returns:
            Dictionary with pricing analytics
        """
        return self.aggregate_repo.get_pricing_analytics(
            hostel_ids=hostel_ids,
            room_type=room_type,
            as_of_date=as_of_date
        )
    
    def compare_fee_structures(
        self,
        fee_structure_ids: List[UUID]
    ) -> List[Dict[str, Any]]:
        """
        Compare multiple fee structures.
        
        Args:
            fee_structure_ids: List of fee structure IDs
            
        Returns:
            List of fee structure comparisons
        """
        return self.aggregate_repo.compare_fee_structures(fee_structure_ids)
    
    def get_market_positioning(
        self,
        hostel_id: UUID,
        room_type: RoomType
    ) -> Dict[str, Any]:
        """
        Analyze market positioning for a hostel's room type.
        
        Args:
            hostel_id: Hostel identifier
            room_type: Room type to analyze
            
        Returns:
            Dictionary with market positioning analysis
        """
        return self.aggregate_repo.get_market_positioning(
            hostel_id=hostel_id,
            room_type=room_type
        )
    
    def get_pricing_comparison(
        self,
        hostel_ids: List[UUID],
        room_type: RoomType,
        fee_type: FeeType,
        as_of_date: Optional[Date] = None
    ) -> List[Dict[str, Any]]:
        """
        Compare pricing across multiple hostels.
        
        Args:
            hostel_ids: List of hostel identifiers
            room_type: Room type to compare
            fee_type: Fee type to compare
            as_of_date: Date to check
            
        Returns:
            List of pricing comparisons
        """
        return self.fee_structure_repo.get_pricing_comparison(
            hostel_ids=hostel_ids,
            room_type=room_type,
            fee_type=fee_type,
            as_of_date=as_of_date
        )
    
    def get_upcoming_changes(
        self,
        hostel_id: Optional[UUID] = None,
        days_ahead: int = 30
    ) -> List[FeeStructure]:
        """
        Get fee structures with upcoming effective dates.
        
        Args:
            hostel_id: Optional hostel filter
            days_ahead: Number of days to look ahead
            
        Returns:
            List of upcoming FeeStructure instances
        """
        return self.fee_structure_repo.get_upcoming_changes(
            hostel_id=hostel_id,
            days_ahead=days_ahead
        )
    
    def get_expiring_structures(
        self,
        hostel_id: Optional[UUID] = None,
        days_ahead: int = 30
    ) -> List[FeeStructure]:
        """
        Get fee structures expiring soon.
        
        Args:
            hostel_id: Optional hostel filter
            days_ahead: Number of days to look ahead
            
        Returns:
            List of expiring FeeStructure instances
        """
        return self.fee_structure_repo.get_expiring_structures(
            hostel_id=hostel_id,
            days_ahead=days_ahead
        )
    
    # ============================================================
    # Bulk Operations
    # ============================================================
    
    def bulk_update_effective_dates(
        self,
        fee_structure_ids: List[UUID],
        new_effective_to: Date,
        user_id: UUID
    ) -> int:
        """
        Bulk update effective_to dates.
        
        Args:
            fee_structure_ids: List of fee structure IDs
            new_effective_to: New effective_to date
            user_id: User performing update
            
        Returns:
            Number of records updated
        """
        audit_context = {
            'user_id': user_id,
            'action': 'bulk_update_effective_dates',
            'timestamp': datetime.utcnow()
        }
        
        try:
            updated = self.fee_structure_repo.bulk_update_effective_dates(
                fee_structure_ids=fee_structure_ids,
                new_effective_to=new_effective_to,
                audit_context=audit_context
            )
            self.session.commit()
            
            logger.info(f"Bulk updated {updated} fee structures")
            return updated
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error in bulk update: {str(e)}")
            raise
    
    def bulk_deactivate(
        self,
        hostel_id: UUID,
        user_id: UUID,
        room_type: Optional[RoomType] = None,
        before_date: Optional[Date] = None
    ) -> int:
        """
        Bulk deactivate fee structures.
        
        Args:
            hostel_id: Hostel identifier
            user_id: User performing deactivation
            room_type: Optional room type filter
            before_date: Deactivate structures effective before this date
            
        Returns:
            Number of records deactivated
        """
        audit_context = {
            'user_id': user_id,
            'action': 'bulk_deactivate',
            'timestamp': datetime.utcnow()
        }
        
        try:
            deactivated = self.fee_structure_repo.bulk_deactivate(
                hostel_id=hostel_id,
                room_type=room_type,
                before_date=before_date,
                audit_context=audit_context
            )
            self.session.commit()
            
            logger.info(f"Bulk deactivated {deactivated} fee structures")
            return deactivated
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error in bulk deactivate: {str(e)}")
            raise
    
    # ============================================================
    # Validation and Helper Methods
    # ============================================================
    
    def _validate_fee_structure_creation(
        self,
        amount: Decimal,
        security_deposit: Decimal,
        includes_mess: bool,
        mess_charges_monthly: Optional[Decimal],
        electricity_charges: ChargeType,
        electricity_fixed_amount: Optional[Decimal],
        water_charges: ChargeType,
        water_fixed_amount: Optional[Decimal],
        effective_from: Date,
        effective_to: Optional[Date]
    ) -> None:
        """Validate fee structure creation parameters."""
        # Amount validations
        if amount < Decimal('500.00') or amount > Decimal('100000.00'):
            raise ValidationException(
                "Amount must be between 500.00 and 100000.00"
            )
        
        if security_deposit < Decimal('0'):
            raise ValidationException("Security deposit cannot be negative")
        
        if security_deposit > (amount * 3):
            raise ValidationException(
                "Security deposit cannot exceed 3 times the monthly amount"
            )
        
        # Mess charges validation
        if includes_mess and mess_charges_monthly and mess_charges_monthly > 0:
            raise ValidationException(
                "Cannot have both includes_mess=True and positive mess_charges_monthly"
            )
        
        if mess_charges_monthly and mess_charges_monthly > Decimal('10000.00'):
            raise ValidationException("Mess charges cannot exceed 10000.00")
        
        # Utility charges validation
        if electricity_charges == ChargeType.FIXED_MONTHLY and not electricity_fixed_amount:
            raise ValidationException(
                "electricity_fixed_amount required when electricity_charges is FIXED_MONTHLY"
            )
        
        if water_charges == ChargeType.FIXED_MONTHLY and not water_fixed_amount:
            raise ValidationException(
                "water_fixed_amount required when water_charges is FIXED_MONTHLY"
            )
        
        # Date validation
        if effective_to and effective_to <= effective_from:
            raise ValidationException("effective_to must be after effective_from")
        
        if effective_from < Date.today():
            logger.warning(f"Creating fee structure with past effective_from date: {effective_from}")
    
    def _validate_fee_structure_update(
        self,
        existing: FeeStructure,
        update_data: Dict[str, Any]
    ) -> None:
        """Validate fee structure update."""
        # Get effective values
        amount = update_data.get('amount', existing.amount)
        security_deposit = update_data.get('security_deposit', existing.security_deposit)
        includes_mess = update_data.get('includes_mess', existing.includes_mess)
        mess_charges = update_data.get('mess_charges_monthly', existing.mess_charges_monthly)
        
        # Validate amounts
        if amount < Decimal('500.00') or amount > Decimal('100000.00'):
            raise ValidationException(
                "Amount must be between 500.00 and 100000.00"
            )
        
        if security_deposit > (amount * 3):
            raise ValidationException(
                "Security deposit cannot exceed 3 times the monthly amount"
            )
        
        # Validate mess charges
        if includes_mess and mess_charges > 0:
            raise ValidationException(
                "Cannot have both includes_mess=True and positive mess_charges_monthly"
            )
        
        # Validate date changes
        if 'effective_from' in update_data and 'effective_to' in update_data:
            if update_data['effective_to'] <= update_data['effective_from']:
                raise ValidationException("effective_to must be after effective_from")
    
    def _can_delete_fee_structure(self, fee_structure: FeeStructure) -> bool:
        """Check if fee structure can be deleted."""
        # Check if it has any calculations
        from app.repositories.fee_structure.fee_calculation_repository import (
            FeeCalculationRepository
        )
        calc_repo = FeeCalculationRepository(self.session)
        calculations = calc_repo.find_by_fee_structure(
            fee_structure_id=fee_structure.id,
            limit=1
        )
        
        if calculations:
            logger.warning(
                f"Cannot delete fee structure {fee_structure.id} - has calculations"
            )
            return False
        
        return True
    
    def _create_approval_record(
        self,
        fee_structure_id: UUID,
        user_id: UUID,
        previous_amount: Optional[Decimal],
        new_amount: Decimal,
        change_summary: str
    ) -> FeeApproval:
        """Create approval record for fee structure."""
        approval = FeeApproval(
            fee_structure_id=fee_structure_id,
            approval_status='pending',
            previous_amount=previous_amount,
            new_amount=new_amount,
            change_summary=change_summary,
            created_by=user_id,
            created_at=datetime.utcnow()
        )
        
        self.session.add(approval)
        return approval
    
    def _generate_change_summary(
        self,
        original: FeeStructure,
        updates: Dict[str, Any]
    ) -> str:
        """Generate human-readable change summary."""
        changes = []
        
        if 'amount' in updates and updates['amount'] != original.amount:
            changes.append(
                f"Amount: {original.amount} -> {updates['amount']}"
            )
        
        if 'security_deposit' in updates and updates['security_deposit'] != original.security_deposit:
            changes.append(
                f"Security Deposit: {original.security_deposit} -> {updates['security_deposit']}"
            )
        
        if 'mess_charges_monthly' in updates and updates['mess_charges_monthly'] != original.mess_charges_monthly:
            changes.append(
                f"Mess Charges: {original.mess_charges_monthly} -> {updates['mess_charges_monthly']}"
            )
        
        if 'includes_mess' in updates and updates['includes_mess'] != original.includes_mess:
            changes.append(
                f"Includes Mess: {original.includes_mess} -> {updates['includes_mess']}"
            )
        
        return "; ".join(changes) if changes else "Minor updates"