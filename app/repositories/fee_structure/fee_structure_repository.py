"""
Fee Structure Repository

Manages fee structure CRUD operations, versioning, approval workflows,
and complex queries for pricing management.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, case, exists, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.fee_structure.fee_structure import FeeStructure, FeeApproval
from app.models.base.enums import RoomType, FeeType, ChargeType
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.specifications import Specification
from app.core.exceptions import (
    NotFoundError,
    ValidationError,
    ConflictError,
)


class FeeStructureRepository(BaseRepository[FeeStructure]):
    """
    Fee Structure Repository
    
    Provides comprehensive fee structure management with versioning,
    validation, and complex querying capabilities.
    """
    
    def __init__(self, session: Session):
        super().__init__(FeeStructure, session)
    
    # ============================================================
    # Core CRUD Operations with Business Logic
    # ============================================================
    
    def create_fee_structure(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        fee_type: FeeType,
        amount: Decimal,
        security_deposit: Decimal,
        effective_from: Date,
        audit_context: Dict[str, Any],
        **kwargs
    ) -> FeeStructure:
        """
        Create new fee structure with validation and conflict checking.
        
        Args:
            hostel_id: Hostel identifier
            room_type: Room type enum
            fee_type: Fee type enum
            amount: Base fee amount
            security_deposit: Security deposit amount
            effective_from: Effective start date
            audit_context: Audit information
            **kwargs: Additional fee structure attributes
            
        Returns:
            Created FeeStructure instance
            
        Raises:
            ValidationError: If validation fails
            ConflictError: If overlapping active fee structure exists
        """
        # Validate amounts
        self._validate_amounts(amount, security_deposit, kwargs)
        
        # Check for overlapping fee structures
        self._check_for_overlaps(
            hostel_id=hostel_id,
            room_type=room_type,
            fee_type=fee_type,
            effective_from=effective_from,
            effective_to=kwargs.get('effective_to'),
            exclude_id=None
        )
        
        # Auto-deactivate previous fee structures
        self._deactivate_previous_structures(
            hostel_id=hostel_id,
            room_type=room_type,
            fee_type=fee_type,
            effective_from=effective_from
        )
        
        # Create fee structure
        fee_structure = FeeStructure(
            hostel_id=hostel_id,
            room_type=room_type,
            fee_type=fee_type,
            amount=amount,
            security_deposit=security_deposit,
            effective_from=effective_from,
            is_active=True,
            version=1,
            **kwargs
        )
        
        # Apply audit context
        self._apply_audit(fee_structure, audit_context)
        
        self.session.add(fee_structure)
        self.session.flush()
        
        return fee_structure
    
    def update_fee_structure(
        self,
        fee_structure_id: UUID,
        update_data: Dict[str, Any],
        audit_context: Dict[str, Any],
        create_new_version: bool = True
    ) -> FeeStructure:
        """
        Update fee structure with versioning support.
        
        Args:
            fee_structure_id: Fee structure to update
            update_data: Fields to update
            audit_context: Audit information
            create_new_version: Whether to create new version or update in-place
            
        Returns:
            Updated or new FeeStructure instance
            
        Raises:
            NotFoundError: If fee structure not found
            ValidationError: If validation fails
        """
        fee_structure = self.find_by_id(fee_structure_id)
        if not fee_structure:
            raise NotFoundError(f"Fee structure {fee_structure_id} not found")
        
        # Validate update data
        if 'amount' in update_data or 'security_deposit' in update_data:
            self._validate_amounts(
                update_data.get('amount', fee_structure.amount),
                update_data.get('security_deposit', fee_structure.security_deposit),
                update_data
            )
        
        if create_new_version:
            # Create new version
            new_version = self._create_new_version(fee_structure, update_data, audit_context)
            return new_version
        else:
            # Update in-place
            for key, value in update_data.items():
                if hasattr(fee_structure, key):
                    setattr(fee_structure, key, value)
            
            self._apply_audit(fee_structure, audit_context, is_update=True)
            self.session.flush()
            
            return fee_structure
    
    # ============================================================
    # Query Operations
    # ============================================================
    
    def find_by_hostel_and_room_type(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        fee_type: Optional[FeeType] = None,
        include_inactive: bool = False,
        as_of_date: Optional[Date] = None
    ) -> List[FeeStructure]:
        """
        Find fee structures for specific hostel and room type.
        
        Args:
            hostel_id: Hostel identifier
            room_type: Room type
            fee_type: Optional fee type filter
            include_inactive: Include inactive structures
            as_of_date: Find structures effective as of this date
            
        Returns:
            List of matching FeeStructure instances
        """
        query = self.session.query(FeeStructure).filter(
            FeeStructure.hostel_id == hostel_id,
            FeeStructure.room_type == room_type,
            FeeStructure.deleted_at.is_(None)
        )
        
        if fee_type:
            query = query.filter(FeeStructure.fee_type == fee_type)
        
        if not include_inactive:
            query = query.filter(FeeStructure.is_active == True)
        
        if as_of_date:
            query = query.filter(
                FeeStructure.effective_from <= as_of_date,
                or_(
                    FeeStructure.effective_to.is_(None),
                    FeeStructure.effective_to >= as_of_date
                )
            )
        
        return query.all()
    
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
        check_date = as_of_date or Date.today()
        
        return self.session.query(FeeStructure).filter(
            FeeStructure.hostel_id == hostel_id,
            FeeStructure.room_type == room_type,
            FeeStructure.fee_type == fee_type,
            FeeStructure.is_active == True,
            FeeStructure.effective_from <= check_date,
            or_(
                FeeStructure.effective_to.is_(None),
                FeeStructure.effective_to >= check_date
            ),
            FeeStructure.deleted_at.is_(None)
        ).order_by(
            FeeStructure.effective_from.desc(),
            FeeStructure.version.desc()
        ).first()
    
    def find_by_date_range(
        self,
        hostel_id: UUID,
        start_date: Date,
        end_date: Date,
        room_type: Optional[RoomType] = None,
        fee_type: Optional[FeeType] = None
    ) -> List[FeeStructure]:
        """
        Find fee structures effective within date range.
        
        Args:
            hostel_id: Hostel identifier
            start_date: Range start date
            end_date: Range end date
            room_type: Optional room type filter
            fee_type: Optional fee type filter
            
        Returns:
            List of FeeStructure instances
        """
        query = self.session.query(FeeStructure).filter(
            FeeStructure.hostel_id == hostel_id,
            FeeStructure.deleted_at.is_(None),
            # Overlaps with date range
            FeeStructure.effective_from <= end_date,
            or_(
                FeeStructure.effective_to.is_(None),
                FeeStructure.effective_to >= start_date
            )
        )
        
        if room_type:
            query = query.filter(FeeStructure.room_type == room_type)
        
        if fee_type:
            query = query.filter(FeeStructure.fee_type == fee_type)
        
        return query.order_by(
            FeeStructure.effective_from,
            FeeStructure.room_type
        ).all()
    
    def get_fee_structure_with_components(
        self,
        fee_structure_id: UUID
    ) -> Optional[FeeStructure]:
        """
        Get fee structure with all related components loaded.
        
        Args:
            fee_structure_id: Fee structure identifier
            
        Returns:
            FeeStructure with components or None
        """
        return self.session.query(FeeStructure).options(
            selectinload(FeeStructure.charge_components),
            selectinload(FeeStructure.approvals)
        ).filter(
            FeeStructure.id == fee_structure_id,
            FeeStructure.deleted_at.is_(None)
        ).first()
    
    def find_pending_approval(
        self,
        hostel_id: Optional[UUID] = None
    ) -> List[FeeStructure]:
        """
        Find fee structures pending approval.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of FeeStructure instances pending approval
        """
        subquery = self.session.query(FeeApproval.fee_structure_id).filter(
            FeeApproval.approval_status == 'approved'
        ).subquery()
        
        query = self.session.query(FeeStructure).filter(
            FeeStructure.deleted_at.is_(None),
            ~FeeStructure.id.in_(subquery)
        )
        
        if hostel_id:
            query = query.filter(FeeStructure.hostel_id == hostel_id)
        
        return query.order_by(FeeStructure.created_at.desc()).all()
    
    def get_version_history(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        fee_type: FeeType
    ) -> List[FeeStructure]:
        """
        Get complete version history for a fee structure configuration.
        
        Args:
            hostel_id: Hostel identifier
            room_type: Room type
            fee_type: Fee type
            
        Returns:
            List of all versions ordered by version number
        """
        return self.session.query(FeeStructure).filter(
            FeeStructure.hostel_id == hostel_id,
            FeeStructure.room_type == room_type,
            FeeStructure.fee_type == fee_type,
            FeeStructure.deleted_at.is_(None)
        ).order_by(FeeStructure.version.desc()).all()
    
    # ============================================================
    # Analytics and Reporting
    # ============================================================
    
    def get_fee_summary_by_hostel(
        self,
        hostel_id: UUID,
        as_of_date: Optional[Date] = None
    ) -> List[Dict[str, Any]]:
        """
        Get summary of current fee structures for a hostel.
        
        Args:
            hostel_id: Hostel identifier
            as_of_date: Date to check (defaults to today)
            
        Returns:
            List of fee summaries by room type
        """
        check_date = as_of_date or Date.today()
        
        results = self.session.query(
            FeeStructure.room_type,
            FeeStructure.fee_type,
            FeeStructure.amount,
            FeeStructure.security_deposit,
            FeeStructure.mess_charges_monthly,
            FeeStructure.includes_mess,
            FeeStructure.effective_from,
            FeeStructure.effective_to
        ).filter(
            FeeStructure.hostel_id == hostel_id,
            FeeStructure.is_active == True,
            FeeStructure.effective_from <= check_date,
            or_(
                FeeStructure.effective_to.is_(None),
                FeeStructure.effective_to >= check_date
            ),
            FeeStructure.deleted_at.is_(None)
        ).order_by(
            FeeStructure.room_type,
            FeeStructure.fee_type
        ).all()
        
        return [
            {
                'room_type': r.room_type.value,
                'fee_type': r.fee_type.value,
                'amount': float(r.amount),
                'security_deposit': float(r.security_deposit),
                'mess_charges_monthly': float(r.mess_charges_monthly),
                'includes_mess': r.includes_mess,
                'effective_from': r.effective_from.isoformat(),
                'effective_to': r.effective_to.isoformat() if r.effective_to else None
            }
            for r in results
        ]
    
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
            as_of_date: Date to check (defaults to today)
            
        Returns:
            List of pricing comparisons
        """
        check_date = as_of_date or Date.today()
        
        results = self.session.query(
            FeeStructure.hostel_id,
            FeeStructure.amount,
            FeeStructure.security_deposit,
            FeeStructure.mess_charges_monthly
        ).filter(
            FeeStructure.hostel_id.in_(hostel_ids),
            FeeStructure.room_type == room_type,
            FeeStructure.fee_type == fee_type,
            FeeStructure.is_active == True,
            FeeStructure.effective_from <= check_date,
            or_(
                FeeStructure.effective_to.is_(None),
                FeeStructure.effective_to >= check_date
            ),
            FeeStructure.deleted_at.is_(None)
        ).all()
        
        return [
            {
                'hostel_id': str(r.hostel_id),
                'amount': float(r.amount),
                'security_deposit': float(r.security_deposit),
                'mess_charges_monthly': float(r.mess_charges_monthly),
                'total_first_month': float(r.amount + r.security_deposit + r.mess_charges_monthly)
            }
            for r in results
        ]
    
    def calculate_average_pricing(
        self,
        hostel_id: Optional[UUID] = None,
        room_type: Optional[RoomType] = None,
        as_of_date: Optional[Date] = None
    ) -> Dict[str, Decimal]:
        """
        Calculate average pricing statistics.
        
        Args:
            hostel_id: Optional hostel filter
            room_type: Optional room type filter
            as_of_date: Date to check (defaults to today)
            
        Returns:
            Dictionary with average pricing metrics
        """
        check_date = as_of_date or Date.today()
        
        query = self.session.query(
            func.avg(FeeStructure.amount).label('avg_amount'),
            func.min(FeeStructure.amount).label('min_amount'),
            func.max(FeeStructure.amount).label('max_amount'),
            func.avg(FeeStructure.security_deposit).label('avg_deposit'),
            func.count(FeeStructure.id).label('count')
        ).filter(
            FeeStructure.is_active == True,
            FeeStructure.effective_from <= check_date,
            or_(
                FeeStructure.effective_to.is_(None),
                FeeStructure.effective_to >= check_date
            ),
            FeeStructure.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(FeeStructure.hostel_id == hostel_id)
        
        if room_type:
            query = query.filter(FeeStructure.room_type == room_type)
        
        result = query.first()
        
        return {
            'average_amount': result.avg_amount or Decimal('0'),
            'minimum_amount': result.min_amount or Decimal('0'),
            'maximum_amount': result.max_amount or Decimal('0'),
            'average_deposit': result.avg_deposit or Decimal('0'),
            'structure_count': result.count or 0
        }
    
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
        today = Date.today()
        future_date = Date.fromordinal(today.toordinal() + days_ahead)
        
        query = self.session.query(FeeStructure).filter(
            FeeStructure.effective_from > today,
            FeeStructure.effective_from <= future_date,
            FeeStructure.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(FeeStructure.hostel_id == hostel_id)
        
        return query.order_by(FeeStructure.effective_from).all()
    
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
        today = Date.today()
        future_date = Date.fromordinal(today.toordinal() + days_ahead)
        
        query = self.session.query(FeeStructure).filter(
            FeeStructure.effective_to.isnot(None),
            FeeStructure.effective_to > today,
            FeeStructure.effective_to <= future_date,
            FeeStructure.is_active == True,
            FeeStructure.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(FeeStructure.hostel_id == hostel_id)
        
        return query.order_by(FeeStructure.effective_to).all()
    
    # ============================================================
    # Bulk Operations
    # ============================================================
    
    def bulk_update_effective_dates(
        self,
        fee_structure_ids: List[UUID],
        new_effective_to: Date,
        audit_context: Dict[str, Any]
    ) -> int:
        """
        Bulk update effective_to dates for multiple fee structures.
        
        Args:
            fee_structure_ids: List of fee structure IDs
            new_effective_to: New effective_to date
            audit_context: Audit information
            
        Returns:
            Number of records updated
        """
        updated = self.session.query(FeeStructure).filter(
            FeeStructure.id.in_(fee_structure_ids),
            FeeStructure.deleted_at.is_(None)
        ).update(
            {
                'effective_to': new_effective_to,
                'updated_at': datetime.utcnow(),
                'updated_by': audit_context.get('user_id')
            },
            synchronize_session=False
        )
        
        self.session.flush()
        return updated
    
    def bulk_deactivate(
        self,
        hostel_id: UUID,
        room_type: Optional[RoomType] = None,
        before_date: Optional[Date] = None,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Bulk deactivate fee structures.
        
        Args:
            hostel_id: Hostel identifier
            room_type: Optional room type filter
            before_date: Deactivate structures effective before this date
            audit_context: Audit information
            
        Returns:
            Number of records deactivated
        """
        query = self.session.query(FeeStructure).filter(
            FeeStructure.hostel_id == hostel_id,
            FeeStructure.is_active == True,
            FeeStructure.deleted_at.is_(None)
        )
        
        if room_type:
            query = query.filter(FeeStructure.room_type == room_type)
        
        if before_date:
            query = query.filter(FeeStructure.effective_from < before_date)
        
        update_data = {
            'is_active': False,
            'updated_at': datetime.utcnow()
        }
        
        if audit_context:
            update_data['updated_by'] = audit_context.get('user_id')
        
        updated = query.update(update_data, synchronize_session=False)
        self.session.flush()
        
        return updated
    
    # ============================================================
    # Validation and Helper Methods
    # ============================================================
    
    def _validate_amounts(
        self,
        amount: Decimal,
        security_deposit: Decimal,
        additional_data: Dict[str, Any]
    ) -> None:
        """Validate fee amounts and related fields."""
        if amount < Decimal('500.00') or amount > Decimal('100000.00'):
            raise ValidationError(
                "Amount must be between 500.00 and 100000.00"
            )
        
        if security_deposit < Decimal('0'):
            raise ValidationError("Security deposit cannot be negative")
        
        if security_deposit > (amount * 3):
            raise ValidationError(
                "Security deposit cannot exceed 3 times the monthly amount"
            )
        
        mess_charges = additional_data.get('mess_charges_monthly', Decimal('0'))
        includes_mess = additional_data.get('includes_mess', False)
        
        if includes_mess and mess_charges > Decimal('0'):
            raise ValidationError(
                "Cannot have both includes_mess=True and mess_charges_monthly > 0"
            )
        
        if mess_charges > Decimal('10000.00'):
            raise ValidationError(
                "Mess charges cannot exceed 10000.00"
            )
    
    def _check_for_overlaps(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        fee_type: FeeType,
        effective_from: Date,
        effective_to: Optional[Date],
        exclude_id: Optional[UUID]
    ) -> None:
        """Check for overlapping fee structures."""
        query = self.session.query(FeeStructure).filter(
            FeeStructure.hostel_id == hostel_id,
            FeeStructure.room_type == room_type,
            FeeStructure.fee_type == fee_type,
            FeeStructure.is_active == True,
            FeeStructure.deleted_at.is_(None)
        )
        
        if exclude_id:
            query = query.filter(FeeStructure.id != exclude_id)
        
        # Check for date overlap
        if effective_to:
            query = query.filter(
                or_(
                    and_(
                        FeeStructure.effective_from <= effective_from,
                        or_(
                            FeeStructure.effective_to.is_(None),
                            FeeStructure.effective_to >= effective_from
                        )
                    ),
                    and_(
                        FeeStructure.effective_from <= effective_to,
                        or_(
                            FeeStructure.effective_to.is_(None),
                            FeeStructure.effective_to >= effective_to
                        )
                    ),
                    and_(
                        FeeStructure.effective_from >= effective_from,
                        FeeStructure.effective_from <= effective_to
                    )
                )
            )
        else:
            query = query.filter(
                or_(
                    FeeStructure.effective_to.is_(None),
                    FeeStructure.effective_to >= effective_from
                )
            )
        
        if query.first():
            raise ConflictError(
                f"Overlapping fee structure exists for {hostel_id}/{room_type.value}/{fee_type.value}"
            )
    
    def _deactivate_previous_structures(
        self,
        hostel_id: UUID,
        room_type: RoomType,
        fee_type: FeeType,
        effective_from: Date
    ) -> None:
        """Automatically deactivate previous fee structures."""
        previous_date = Date.fromordinal(effective_from.toordinal() - 1)
        
        self.session.query(FeeStructure).filter(
            FeeStructure.hostel_id == hostel_id,
            FeeStructure.room_type == room_type,
            FeeStructure.fee_type == fee_type,
            FeeStructure.is_active == True,
            FeeStructure.effective_to.is_(None),
            FeeStructure.deleted_at.is_(None)
        ).update(
            {
                'effective_to': previous_date,
                'updated_at': datetime.utcnow()
            },
            synchronize_session=False
        )
    
    def _create_new_version(
        self,
        original: FeeStructure,
        update_data: Dict[str, Any],
        audit_context: Dict[str, Any]
    ) -> FeeStructure:
        """Create a new version of fee structure."""
        # Set end date on original
        original.effective_to = update_data.get(
            'effective_from',
            Date.today()
        ) - Date.resolution
        original.is_active = False
        
        # Create new version
        new_version_data = {
            'hostel_id': original.hostel_id,
            'room_type': original.room_type,
            'fee_type': original.fee_type,
            'amount': original.amount,
            'security_deposit': original.security_deposit,
            'includes_mess': original.includes_mess,
            'mess_charges_monthly': original.mess_charges_monthly,
            'electricity_charges': original.electricity_charges,
            'electricity_fixed_amount': original.electricity_fixed_amount,
            'water_charges': original.water_charges,
            'water_fixed_amount': original.water_fixed_amount,
            'effective_from': update_data.get('effective_from', Date.today()),
            'is_active': True,
            'version': original.version + 1,
            'replaced_by_id': None,
            'description': original.description
        }
        
        # Apply updates
        new_version_data.update(update_data)
        
        new_version = FeeStructure(**new_version_data)
        self._apply_audit(new_version, audit_context)
        
        # Link versions
        original.replaced_by_id = new_version.id
        
        self.session.add(new_version)
        self.session.flush()
        
        return new_version
    
    def _apply_audit(
        self,
        entity: FeeStructure,
        audit_context: Dict[str, Any],
        is_update: bool = False
    ) -> None:
        """Apply audit information to entity."""
        user_id = audit_context.get('user_id')
        
        if is_update:
            entity.updated_by = user_id
            entity.updated_at = datetime.utcnow()
        else:
            entity.created_by = user_id
            entity.created_at = datetime.utcnow()