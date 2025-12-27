# --- File: C:\Hostel-Main\app\repositories\fee_structure\charge_component_repository.py ---
"""
Charge Component Repository

Manages charge components, charge rules, and discount configurations
with advanced querying, validation, business logic, and analytics capabilities.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
import json

from sqlalchemy import and_, or_, func, case, select, desc, asc
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.fee_structure.charge_component import (
    ChargeComponent,
    ChargeRule,
    DiscountConfiguration,
)
from app.repositories.base.base_repository import BaseRepository
from app.core1.exceptions import (
    NotFoundException,
    ValidationException,
    ConflictException,
)


class ChargeComponentRepository(BaseRepository[ChargeComponent]):
    """
    Charge Component Repository
    
    Manages individual charge components within fee structures,
    including component lifecycle, rules, calculations, and analytics.
    """
    
    def __init__(self, session: Session):
        super().__init__(ChargeComponent, session)
    
    # ============================================================
    # Core CRUD Operations
    # ============================================================
    
    def create_charge_component(
        self,
        fee_structure_id: UUID,
        component_name: str,
        component_type: str,
        amount: Decimal,
        audit_context: Dict[str, Any],
        **kwargs
    ) -> ChargeComponent:
        """
        Create a new charge component with validation.
        
        Args:
            fee_structure_id: Parent fee structure ID
            component_name: Name of the component
            component_type: Type of charge (rent, deposit, mess, etc.)
            amount: Component amount
            audit_context: Audit information (user_id, ip_address, etc.)
            **kwargs: Additional component attributes
            
        Returns:
            Created ChargeComponent instance
            
        Raises:
            ValidationException: If validation fails
            ConflictException: If duplicate component name exists
        """
        # Validate component data
        self._validate_component(component_type, amount, kwargs)
        
        # Check for duplicate component names within same fee structure
        self._check_duplicate_component(fee_structure_id, component_name, None)
        
        # Set defaults
        component_data = {
            'fee_structure_id': fee_structure_id,
            'component_name': component_name,
            'component_type': component_type,
            'amount': amount,
            'is_mandatory': kwargs.pop('is_mandatory', True),
            'is_refundable': kwargs.pop('is_refundable', False),
            'is_recurring': kwargs.pop('is_recurring', True),
            'calculation_method': kwargs.pop('calculation_method', 'fixed'),
            'is_taxable': kwargs.pop('is_taxable', False),
            'tax_percentage': kwargs.pop('tax_percentage', Decimal('0.00')),
            'display_order': kwargs.pop('display_order', 0),
            'is_visible_to_student': kwargs.pop('is_visible_to_student', True),
            'proration_allowed': kwargs.pop('proration_allowed', False),
        }
        
        # Add remaining kwargs
        component_data.update(kwargs)
        
        component = ChargeComponent(**component_data)
        
        self._apply_audit(component, audit_context)
        self.session.add(component)
        self.session.flush()
        
        return component
    
    def update_charge_component(
        self,
        component_id: UUID,
        update_data: Dict[str, Any],
        audit_context: Dict[str, Any]
    ) -> ChargeComponent:
        """
        Update an existing charge component.
        
        Args:
            component_id: Component identifier
            update_data: Fields to update
            audit_context: Audit information
            
        Returns:
            Updated ChargeComponent instance
            
        Raises:
            NotFoundException: If component not found
            ValidationException: If validation fails
            ConflictException: If duplicate name
        """
        component = self.find_by_id(component_id)
        if not component:
            raise NotFoundException(f"Charge component {component_id} not found")
        
        # Validate updates
        if 'amount' in update_data or 'component_type' in update_data:
            self._validate_component(
                update_data.get('component_type', component.component_type),
                update_data.get('amount', component.amount),
                update_data
            )
        
        # Check for duplicate names if name is being changed
        if 'component_name' in update_data and update_data['component_name'] != component.component_name:
            self._check_duplicate_component(
                component.fee_structure_id,
                update_data['component_name'],
                component_id
            )
        
        # Apply updates
        for key, value in update_data.items():
            if hasattr(component, key) and key not in ['id', 'created_at', 'created_by']:
                setattr(component, key, value)
        
        self._apply_audit(component, audit_context, is_update=True)
        self.session.flush()
        
        return component
    
    def delete_charge_component(
        self,
        component_id: UUID,
        audit_context: Dict[str, Any],
        hard_delete: bool = False
    ) -> bool:
        """
        Delete a charge component (soft or hard delete).
        
        Args:
            component_id: Component identifier
            audit_context: Audit information
            hard_delete: If True, permanently delete; otherwise soft delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            NotFoundException: If component not found
        """
        component = self.find_by_id(component_id)
        if not component:
            raise NotFoundException(f"Charge component {component_id} not found")
        
        if hard_delete:
            self.session.delete(component)
        else:
            component.deleted_at = datetime.utcnow()
            component.deleted_by = audit_context.get('user_id')
        
        self.session.flush()
        return True
    
    # ============================================================
    # Query Operations - Basic
    # ============================================================
    
    def find_by_fee_structure(
        self,
        fee_structure_id: UUID,
        component_type: Optional[str] = None,
        is_mandatory: Optional[bool] = None,
        is_recurring: Optional[bool] = None,
        include_deleted: bool = False,
        order_by_display: bool = True
    ) -> List[ChargeComponent]:
        """
        Find all charge components for a fee structure.
        
        Args:
            fee_structure_id: Fee structure identifier
            component_type: Optional component type filter
            is_mandatory: Optional mandatory filter
            is_recurring: Optional recurring filter
            include_deleted: Include soft-deleted components
            order_by_display: Order by display_order
            
        Returns:
            List of ChargeComponent instances
        """
        query = self.session.query(ChargeComponent).filter(
            ChargeComponent.fee_structure_id == fee_structure_id
        )
        
        if not include_deleted:
            query = query.filter(ChargeComponent.deleted_at.is_(None))
        
        if component_type:
            query = query.filter(ChargeComponent.component_type == component_type)
        
        if is_mandatory is not None:
            query = query.filter(ChargeComponent.is_mandatory == is_mandatory)
        
        if is_recurring is not None:
            query = query.filter(ChargeComponent.is_recurring == is_recurring)
        
        if order_by_display:
            query = query.order_by(ChargeComponent.display_order.asc())
        
        return query.all()
    
    def find_by_type(
        self,
        component_type: str,
        fee_structure_ids: Optional[List[UUID]] = None,
        as_of_date: Optional[Date] = None,
        is_active_only: bool = True
    ) -> List[ChargeComponent]:
        """
        Find charge components by type across fee structures.
        
        Args:
            component_type: Component type to search
            fee_structure_ids: Optional list of fee structure IDs
            as_of_date: Find components applicable as of this date
            is_active_only: Only return active components
            
        Returns:
            List of ChargeComponent instances
        """
        query = self.session.query(ChargeComponent).filter(
            ChargeComponent.component_type == component_type,
            ChargeComponent.deleted_at.is_(None)
        )
        
        if fee_structure_ids:
            query = query.filter(ChargeComponent.fee_structure_id.in_(fee_structure_ids))
        
        if as_of_date:
            query = query.filter(
                or_(
                    ChargeComponent.applies_from_date.is_(None),
                    ChargeComponent.applies_from_date <= as_of_date
                ),
                or_(
                    ChargeComponent.applies_to_date.is_(None),
                    ChargeComponent.applies_to_date >= as_of_date
                )
            )
        
        return query.order_by(ChargeComponent.component_name).all()
    
    def find_by_id_with_relations(
        self,
        component_id: UUID
    ) -> Optional[ChargeComponent]:
        """
        Get charge component with all related entities loaded.
        
        Args:
            component_id: Component identifier
            
        Returns:
            ChargeComponent with relations or None
        """
        return self.session.query(ChargeComponent).options(
            selectinload(ChargeComponent.charge_rules),
            joinedload(ChargeComponent.fee_structure)
        ).filter(
            ChargeComponent.id == component_id,
            ChargeComponent.deleted_at.is_(None)
        ).first()
    
    def get_component_with_rules(
        self,
        component_id: UUID,
        active_rules_only: bool = True
    ) -> Optional[ChargeComponent]:
        """
        Get charge component with associated rules.
        
        Args:
            component_id: Component identifier
            active_rules_only: Only load active rules
            
        Returns:
            ChargeComponent with rules loaded or None
        """
        query = self.session.query(ChargeComponent).options(
            selectinload(ChargeComponent.charge_rules)
        ).filter(
            ChargeComponent.id == component_id,
            ChargeComponent.deleted_at.is_(None)
        )
        
        component = query.first()
        
        if component and active_rules_only:
            component.charge_rules = [r for r in component.charge_rules if r.is_active]
        
        return component
    
    # ============================================================
    # Query Operations - Advanced
    # ============================================================
    
    def find_applicable_components(
        self,
        fee_structure_id: UUID,
        room_types: Optional[List[str]] = None,
        check_date: Optional[Date] = None,
        include_optional: bool = True
    ) -> List[ChargeComponent]:
        """
        Find components applicable to specific room types and date.
        
        Args:
            fee_structure_id: Fee structure identifier
            room_types: List of room types to check
            check_date: Date to check applicability
            include_optional: Include non-mandatory components
            
        Returns:
            List of applicable ChargeComponent instances
        """
        check_date = check_date or Date.today()
        
        query = self.session.query(ChargeComponent).filter(
            ChargeComponent.fee_structure_id == fee_structure_id,
            ChargeComponent.deleted_at.is_(None),
            or_(
                ChargeComponent.applies_from_date.is_(None),
                ChargeComponent.applies_from_date <= check_date
            ),
            or_(
                ChargeComponent.applies_to_date.is_(None),
                ChargeComponent.applies_to_date >= check_date
            )
        )
        
        # Filter by mandatory if specified
        if not include_optional:
            query = query.filter(ChargeComponent.is_mandatory == True)
        
        # Filter by room types
        if room_types:
            conditions = [ChargeComponent.applies_to_room_types.is_(None)]
            for room_type in room_types:
                conditions.append(ChargeComponent.applies_to_room_types.like(f'%{room_type}%'))
            query = query.filter(or_(*conditions))
        
        return query.order_by(ChargeComponent.display_order).all()
    
    def find_taxable_components(
        self,
        fee_structure_id: UUID,
        min_tax_rate: Optional[Decimal] = None
    ) -> List[ChargeComponent]:
        """
        Find all taxable components for a fee structure.
        
        Args:
            fee_structure_id: Fee structure identifier
            min_tax_rate: Optional minimum tax rate filter
            
        Returns:
            List of taxable ChargeComponent instances
        """
        query = self.session.query(ChargeComponent).filter(
            ChargeComponent.fee_structure_id == fee_structure_id,
            ChargeComponent.is_taxable == True,
            ChargeComponent.deleted_at.is_(None)
        )
        
        if min_tax_rate:
            query = query.filter(ChargeComponent.tax_percentage >= min_tax_rate)
        
        return query.order_by(ChargeComponent.display_order).all()
    
    def find_recurring_components(
        self,
        fee_structure_id: UUID,
        visible_only: bool = True
    ) -> List[ChargeComponent]:
        """
        Find all recurring charge components.
        
        Args:
            fee_structure_id: Fee structure identifier
            visible_only: Only return components visible to students
            
        Returns:
            List of recurring ChargeComponent instances
        """
        query = self.session.query(ChargeComponent).filter(
            ChargeComponent.fee_structure_id == fee_structure_id,
            ChargeComponent.is_recurring == True,
            ChargeComponent.deleted_at.is_(None)
        )
        
        if visible_only:
            query = query.filter(ChargeComponent.is_visible_to_student == True)
        
        return query.order_by(ChargeComponent.display_order).all()
    
    def find_refundable_components(
        self,
        fee_structure_id: UUID,
        min_amount: Optional[Decimal] = None
    ) -> List[ChargeComponent]:
        """
        Find all refundable charge components.
        
        Args:
            fee_structure_id: Fee structure identifier
            min_amount: Optional minimum amount filter
            
        Returns:
            List of refundable ChargeComponent instances
        """
        query = self.session.query(ChargeComponent).filter(
            ChargeComponent.fee_structure_id == fee_structure_id,
            ChargeComponent.is_refundable == True,
            ChargeComponent.deleted_at.is_(None)
        )
        
        if min_amount:
            query = query.filter(ChargeComponent.amount >= min_amount)
        
        return query.order_by(ChargeComponent.display_order).all()
    
    def find_one_time_components(
        self,
        fee_structure_id: UUID
    ) -> List[ChargeComponent]:
        """
        Find all one-time (non-recurring) charge components.
        
        Args:
            fee_structure_id: Fee structure identifier
            
        Returns:
            List of one-time ChargeComponent instances
        """
        return self.session.query(ChargeComponent).filter(
            ChargeComponent.fee_structure_id == fee_structure_id,
            ChargeComponent.is_recurring == False,
            ChargeComponent.deleted_at.is_(None)
        ).order_by(ChargeComponent.display_order).all()
    
    def find_variable_components(
        self,
        fee_structure_id: UUID
    ) -> List[ChargeComponent]:
        """
        Find components with variable calculation method.
        
        Args:
            fee_structure_id: Fee structure identifier
            
        Returns:
            List of variable ChargeComponent instances
        """
        return self.session.query(ChargeComponent).filter(
            ChargeComponent.fee_structure_id == fee_structure_id,
            ChargeComponent.calculation_method.in_(['variable', 'percentage', 'tiered', 'actual']),
            ChargeComponent.deleted_at.is_(None)
        ).order_by(ChargeComponent.display_order).all()
    
    def find_proratable_components(
        self,
        fee_structure_id: UUID
    ) -> List[ChargeComponent]:
        """
        Find components that allow proration.
        
        Args:
            fee_structure_id: Fee structure identifier
            
        Returns:
            List of proratable ChargeComponent instances
        """
        return self.session.query(ChargeComponent).filter(
            ChargeComponent.fee_structure_id == fee_structure_id,
            ChargeComponent.proration_allowed == True,
            ChargeComponent.deleted_at.is_(None)
        ).order_by(ChargeComponent.display_order).all()
    
    def find_by_calculation_method(
        self,
        calculation_method: str,
        fee_structure_ids: Optional[List[UUID]] = None
    ) -> List[ChargeComponent]:
        """
        Find components by calculation method.
        
        Args:
            calculation_method: Calculation method to filter
            fee_structure_ids: Optional fee structure filter
            
        Returns:
            List of ChargeComponent instances
        """
        query = self.session.query(ChargeComponent).filter(
            ChargeComponent.calculation_method == calculation_method,
            ChargeComponent.deleted_at.is_(None)
        )
        
        if fee_structure_ids:
            query = query.filter(ChargeComponent.fee_structure_id.in_(fee_structure_ids))
        
        return query.all()
    
    def find_expiring_components(
        self,
        days_ahead: int = 30
    ) -> List[ChargeComponent]:
        """
        Find components expiring within specified days.
        
        Args:
            days_ahead: Number of days to look ahead
            
        Returns:
            List of expiring ChargeComponent instances
        """
        today = Date.today()
        future_date = Date.fromordinal(today.toordinal() + days_ahead)
        
        return self.session.query(ChargeComponent).filter(
            ChargeComponent.applies_to_date.isnot(None),
            ChargeComponent.applies_to_date > today,
            ChargeComponent.applies_to_date <= future_date,
            ChargeComponent.deleted_at.is_(None)
        ).order_by(ChargeComponent.applies_to_date).all()
    
    # ============================================================
    # Calculation and Analytics
    # ============================================================
    
    def calculate_total_components(
        self,
        fee_structure_id: UUID,
        include_tax: bool = True,
        component_types: Optional[List[str]] = None,
        mandatory_only: bool = False,
        recurring_only: bool = False
    ) -> Decimal:
        """
        Calculate total of components with various filters.
        
        Args:
            fee_structure_id: Fee structure identifier
            include_tax: Whether to include tax in calculation
            component_types: Optional list of component types to include
            mandatory_only: Only include mandatory components
            recurring_only: Only include recurring components
            
        Returns:
            Total amount as Decimal
        """
        query = self.session.query(
            func.sum(ChargeComponent.amount).label('total_amount'),
            func.sum(ChargeComponent.amount * ChargeComponent.tax_percentage / 100).label('total_tax')
        ).filter(
            ChargeComponent.fee_structure_id == fee_structure_id,
            ChargeComponent.deleted_at.is_(None)
        )
        
        if component_types:
            query = query.filter(ChargeComponent.component_type.in_(component_types))
        
        if mandatory_only:
            query = query.filter(ChargeComponent.is_mandatory == True)
        
        if recurring_only:
            query = query.filter(ChargeComponent.is_recurring == True)
        
        result = query.first()
        
        total = result.total_amount or Decimal('0.00')
        
        if include_tax:
            total += (result.total_tax or Decimal('0.00'))
        
        return total.quantize(Decimal('0.01'))
    
    def calculate_monthly_recurring_total(
        self,
        fee_structure_id: UUID,
        include_tax: bool = True
    ) -> Decimal:
        """
        Calculate total monthly recurring charges.
        
        Args:
            fee_structure_id: Fee structure identifier
            include_tax: Include tax in calculation
            
        Returns:
            Monthly recurring total as Decimal
        """
        return self.calculate_total_components(
            fee_structure_id=fee_structure_id,
            include_tax=include_tax,
            recurring_only=True
        )
    
    def calculate_one_time_total(
        self,
        fee_structure_id: UUID,
        include_tax: bool = True
    ) -> Decimal:
        """
        Calculate total one-time charges.
        
        Args:
            fee_structure_id: Fee structure identifier
            include_tax: Include tax in calculation
            
        Returns:
            One-time total as Decimal
        """
        query = self.session.query(
            func.sum(ChargeComponent.amount).label('total_amount'),
            func.sum(ChargeComponent.amount * ChargeComponent.tax_percentage / 100).label('total_tax')
        ).filter(
            ChargeComponent.fee_structure_id == fee_structure_id,
            ChargeComponent.is_recurring == False,
            ChargeComponent.deleted_at.is_(None)
        )
        
        result = query.first()
        
        total = result.total_amount or Decimal('0.00')
        
        if include_tax:
            total += (result.total_tax or Decimal('0.00'))
        
        return total.quantize(Decimal('0.01'))
    
    def calculate_tax_breakdown(
        self,
        fee_structure_id: UUID
    ) -> Dict[str, Any]:
        """
        Calculate detailed tax breakdown.
        
        Args:
            fee_structure_id: Fee structure identifier
            
        Returns:
            Dictionary with tax breakdown
        """
        components = self.find_taxable_components(fee_structure_id)
        
        tax_breakdown = {
            'total_taxable_components': len(components),
            'total_base_amount': Decimal('0.00'),
            'total_tax_amount': Decimal('0.00'),
            'by_tax_rate': {},
            'by_component_type': {}
        }
        
        for component in components:
            base_amount = component.amount
            tax_amount = component.tax_amount
            tax_rate = str(component.tax_percentage)
            comp_type = component.component_type
            
            # Accumulate totals
            tax_breakdown['total_base_amount'] += base_amount
            tax_breakdown['total_tax_amount'] += tax_amount
            
            # Group by tax rate
            if tax_rate not in tax_breakdown['by_tax_rate']:
                tax_breakdown['by_tax_rate'][tax_rate] = {
                    'count': 0,
                    'base_amount': Decimal('0.00'),
                    'tax_amount': Decimal('0.00')
                }
            tax_breakdown['by_tax_rate'][tax_rate]['count'] += 1
            tax_breakdown['by_tax_rate'][tax_rate]['base_amount'] += base_amount
            tax_breakdown['by_tax_rate'][tax_rate]['tax_amount'] += tax_amount
            
            # Group by component type
            if comp_type not in tax_breakdown['by_component_type']:
                tax_breakdown['by_component_type'][comp_type] = {
                    'count': 0,
                    'base_amount': Decimal('0.00'),
                    'tax_amount': Decimal('0.00')
                }
            tax_breakdown['by_component_type'][comp_type]['count'] += 1
            tax_breakdown['by_component_type'][comp_type]['base_amount'] += base_amount
            tax_breakdown['by_component_type'][comp_type]['tax_amount'] += tax_amount
        
        # Convert Decimals to float for JSON serialization
        tax_breakdown['total_base_amount'] = float(tax_breakdown['total_base_amount'])
        tax_breakdown['total_tax_amount'] = float(tax_breakdown['total_tax_amount'])
        
        for rate_data in tax_breakdown['by_tax_rate'].values():
            rate_data['base_amount'] = float(rate_data['base_amount'])
            rate_data['tax_amount'] = float(rate_data['tax_amount'])
        
        for type_data in tax_breakdown['by_component_type'].values():
            type_data['base_amount'] = float(type_data['base_amount'])
            type_data['tax_amount'] = float(type_data['tax_amount'])
        
        return tax_breakdown
    
    def get_component_breakdown(
        self,
        fee_structure_id: UUID,
        include_hidden: bool = False
    ) -> Dict[str, Any]:
        """
        Get detailed breakdown of all components.
        
        Args:
            fee_structure_id: Fee structure identifier
            include_hidden: Include components not visible to students
            
        Returns:
            Dictionary with component breakdown
        """
        query = self.session.query(ChargeComponent).filter(
            ChargeComponent.fee_structure_id == fee_structure_id,
            ChargeComponent.deleted_at.is_(None)
        )
        
        if not include_hidden:
            query = query.filter(ChargeComponent.is_visible_to_student == True)
        
        components = query.all()
        
        breakdown = {
            'total_components': len(components),
            'mandatory_count': sum(1 for c in components if c.is_mandatory),
            'optional_count': sum(1 for c in components if not c.is_mandatory),
            'recurring_count': sum(1 for c in components if c.is_recurring),
            'one_time_count': sum(1 for c in components if not c.is_recurring),
            'taxable_count': sum(1 for c in components if c.is_taxable),
            'refundable_count': sum(1 for c in components if c.is_refundable),
            'proratable_count': sum(1 for c in components if c.proration_allowed),
            'total_amount': sum(c.amount for c in components),
            'total_tax': sum(c.tax_amount for c in components),
            'total_with_tax': sum(c.total_amount_with_tax for c in components),
            'by_type': {},
            'by_calculation_method': {},
            'by_mandatory_status': {
                'mandatory': {'count': 0, 'total_amount': Decimal('0.00')},
                'optional': {'count': 0, 'total_amount': Decimal('0.00')}
            },
            'by_recurring_status': {
                'recurring': {'count': 0, 'total_amount': Decimal('0.00')},
                'one_time': {'count': 0, 'total_amount': Decimal('0.00')}
            }
        }
        
        # Group by type
        for component in components:
            comp_type = component.component_type
            if comp_type not in breakdown['by_type']:
                breakdown['by_type'][comp_type] = {
                    'count': 0,
                    'total_amount': Decimal('0.00'),
                    'taxable_count': 0,
                    'mandatory_count': 0
                }
            breakdown['by_type'][comp_type]['count'] += 1
            breakdown['by_type'][comp_type]['total_amount'] += component.amount
            if component.is_taxable:
                breakdown['by_type'][comp_type]['taxable_count'] += 1
            if component.is_mandatory:
                breakdown['by_type'][comp_type]['mandatory_count'] += 1
        
        # Group by calculation method
        for component in components:
            method = component.calculation_method
            if method not in breakdown['by_calculation_method']:
                breakdown['by_calculation_method'][method] = {
                    'count': 0,
                    'total_amount': Decimal('0.00')
                }
            breakdown['by_calculation_method'][method]['count'] += 1
            breakdown['by_calculation_method'][method]['total_amount'] += component.amount
        
        # Group by mandatory status
        for component in components:
            key = 'mandatory' if component.is_mandatory else 'optional'
            breakdown['by_mandatory_status'][key]['count'] += 1
            breakdown['by_mandatory_status'][key]['total_amount'] += component.amount
        
        # Group by recurring status
        for component in components:
            key = 'recurring' if component.is_recurring else 'one_time'
            breakdown['by_recurring_status'][key]['count'] += 1
            breakdown['by_recurring_status'][key]['total_amount'] += component.amount
        
        # Convert Decimals to float
        breakdown['total_amount'] = float(breakdown['total_amount'])
        breakdown['total_tax'] = float(breakdown['total_tax'])
        breakdown['total_with_tax'] = float(breakdown['total_with_tax'])
        
        for type_data in breakdown['by_type'].values():
            type_data['total_amount'] = float(type_data['total_amount'])
        
        for method_data in breakdown['by_calculation_method'].values():
            method_data['total_amount'] = float(method_data['total_amount'])
        
        for status_data in breakdown['by_mandatory_status'].values():
            status_data['total_amount'] = float(status_data['total_amount'])
        
        for status_data in breakdown['by_recurring_status'].values():
            status_data['total_amount'] = float(status_data['total_amount'])
        
        return breakdown
    
    def get_component_statistics(
        self,
        component_type: str,
        fee_structure_ids: Optional[List[UUID]] = None
    ) -> Dict[str, Any]:
        """
        Get statistical information about components of a specific type.
        
        Args:
            component_type: Component type to analyze
            fee_structure_ids: Optional list of fee structure IDs
            
        Returns:
            Dictionary with statistical data
        """
        query = self.session.query(
            func.count(ChargeComponent.id).label('count'),
            func.avg(ChargeComponent.amount).label('avg_amount'),
            func.min(ChargeComponent.amount).label('min_amount'),
            func.max(ChargeComponent.amount).label('max_amount'),
            func.sum(ChargeComponent.amount).label('total_amount'),
            func.avg(ChargeComponent.tax_percentage).label('avg_tax_rate'),
            func.sum(case(
                (ChargeComponent.is_mandatory == True, 1),
                else_=0
            )).label('mandatory_count'),
            func.sum(case(
                (ChargeComponent.is_recurring == True, 1),
                else_=0
            )).label('recurring_count'),
            func.sum(case(
                (ChargeComponent.is_taxable == True, 1),
                else_=0
            )).label('taxable_count')
        ).filter(
            ChargeComponent.component_type == component_type,
            ChargeComponent.deleted_at.is_(None)
        )
        
        if fee_structure_ids:
            query = query.filter(ChargeComponent.fee_structure_id.in_(fee_structure_ids))
        
        result = query.first()
        
        total_count = result.count or 0
        
        return {
            'component_type': component_type,
            'count': total_count,
            'average_amount': float(result.avg_amount or 0),
            'minimum_amount': float(result.min_amount or 0),
            'maximum_amount': float(result.max_amount or 0),
            'total_amount': float(result.total_amount or 0),
            'average_tax_rate': float(result.avg_tax_rate or 0),
            'mandatory_count': result.mandatory_count or 0,
            'mandatory_percentage': (result.mandatory_count / total_count * 100) if total_count else 0,
            'recurring_count': result.recurring_count or 0,
            'recurring_percentage': (result.recurring_count / total_count * 100) if total_count else 0,
            'taxable_count': result.taxable_count or 0,
            'taxable_percentage': (result.taxable_count / total_count * 100) if total_count else 0
        }
    
    def compare_component_costs(
        self,
        component_type: str,
        fee_structure_ids: List[UUID]
    ) -> List[Dict[str, Any]]:
        """
        Compare costs of same component type across fee structures.
        
        Args:
            component_type: Component type to compare
            fee_structure_ids: Fee structure IDs to compare
            
        Returns:
            List of comparison data
        """
        results = self.session.query(
            ChargeComponent.fee_structure_id,
            ChargeComponent.amount,
            ChargeComponent.tax_percentage,
            ChargeComponent.is_mandatory,
            ChargeComponent.is_recurring
        ).filter(
            ChargeComponent.component_type == component_type,
            ChargeComponent.fee_structure_id.in_(fee_structure_ids),
            ChargeComponent.deleted_at.is_(None)
        ).all()
        
        return [
            {
                'fee_structure_id': str(r.fee_structure_id),
                'amount': float(r.amount),
                'tax_percentage': float(r.tax_percentage),
                'amount_with_tax': float(r.amount * (1 + r.tax_percentage / 100)),
                'is_mandatory': r.is_mandatory,
                'is_recurring': r.is_recurring
            }
            for r in results
        ]
    
    # ============================================================
    # Bulk Operations
    # ============================================================
    
    def bulk_create_components(
        self,
        fee_structure_id: UUID,
        components_data: List[Dict[str, Any]],
        audit_context: Dict[str, Any]
    ) -> List[ChargeComponent]:
        """
        Create multiple charge components in bulk.
        
        Args:
            fee_structure_id: Parent fee structure ID
            components_data: List of component data dictionaries
            audit_context: Audit information
            
        Returns:
            List of created ChargeComponent instances
            
        Raises:
            ValidationException: If any component fails validation
        """
        created_components = []
        
        for idx, comp_data in enumerate(components_data):
            # Validate each component
            self._validate_component(
                comp_data.get('component_type'),
                comp_data.get('amount'),
                comp_data
            )
            
            component = ChargeComponent(
                fee_structure_id=fee_structure_id,
                component_name=comp_data['component_name'],
                component_type=comp_data['component_type'],
                amount=comp_data['amount'],
                display_order=comp_data.get('display_order', idx),
                is_mandatory=comp_data.get('is_mandatory', True),
                is_refundable=comp_data.get('is_refundable', False),
                is_recurring=comp_data.get('is_recurring', True),
                calculation_method=comp_data.get('calculation_method', 'fixed'),
                is_taxable=comp_data.get('is_taxable', False),
                tax_percentage=comp_data.get('tax_percentage', Decimal('0.00')),
                is_visible_to_student=comp_data.get('is_visible_to_student', True),
                proration_allowed=comp_data.get('proration_allowed', False),
                description=comp_data.get('description'),
                calculation_basis=comp_data.get('calculation_basis'),
                applies_to_room_types=comp_data.get('applies_to_room_types'),
                applies_from_date=comp_data.get('applies_from_date'),
                applies_to_date=comp_data.get('applies_to_date')
            )
            
            self._apply_audit(component, audit_context)
            created_components.append(component)
        
        self.session.bulk_save_objects(created_components, return_defaults=True)
        self.session.flush()
        
        return created_components
    
    def bulk_update_amounts(
        self,
        component_ids: List[UUID],
        amount_updates: Dict[UUID, Decimal],
        audit_context: Dict[str, Any]
    ) -> int:
        """
        Bulk update amounts for multiple components.
        
        Args:
            component_ids: List of component IDs
            amount_updates: Dictionary mapping component_id to new amount
            audit_context: Audit information
            
        Returns:
            Number of components updated
        """
        updated = 0
        
        for component_id, new_amount in amount_updates.items():
            if component_id in component_ids:
                result = self.session.query(ChargeComponent).filter(
                    ChargeComponent.id == component_id,
                    ChargeComponent.deleted_at.is_(None)
                ).update(
                    {
                        'amount': new_amount,
                        'updated_at': datetime.utcnow(),
                        'updated_by': audit_context.get('user_id')
                    },
                    synchronize_session=False
                )
                updated += result
        
        self.session.flush()
        return updated
    
    def bulk_update_display_order(
        self,
        component_orders: Dict[UUID, int],
        audit_context: Dict[str, Any]
    ) -> int:
        """
        Bulk update display order for components.
        
        Args:
            component_orders: Dictionary mapping component_id to display_order
            audit_context: Audit information
            
        Returns:
            Number of components updated
        """
        updated = 0
        
        for component_id, display_order in component_orders.items():
            result = self.session.query(ChargeComponent).filter(
                ChargeComponent.id == component_id,
                ChargeComponent.deleted_at.is_(None)
            ).update(
                {
                    'display_order': display_order,
                    'updated_at': datetime.utcnow(),
                    'updated_by': audit_context.get('user_id')
                },
                synchronize_session=False
            )
            updated += result
        
        self.session.flush()
        return updated
    
    def bulk_update_tax_rates(
        self,
        component_ids: List[UUID],
        tax_percentage: Decimal,
        audit_context: Dict[str, Any]
    ) -> int:
        """
        Bulk update tax rates for multiple components.
        
        Args:
            component_ids: List of component IDs
            tax_percentage: New tax percentage
            audit_context: Audit information
            
        Returns:
            Number of components updated
        """
        if tax_percentage < Decimal('0') or tax_percentage > Decimal('100'):
            raise ValidationException("Tax percentage must be between 0 and 100")
        
        updated = self.session.query(ChargeComponent).filter(
            ChargeComponent.id.in_(component_ids),
            ChargeComponent.deleted_at.is_(None)
        ).update(
            {
                'tax_percentage': tax_percentage,
                'is_taxable': tax_percentage > Decimal('0'),
                'updated_at': datetime.utcnow(),
                'updated_by': audit_context.get('user_id')
            },
            synchronize_session=False
        )
        
        self.session.flush()
        return updated
    
    def clone_components_to_structure(
        self,
        source_fee_structure_id: UUID,
        target_fee_structure_id: UUID,
        audit_context: Dict[str, Any],
        include_rules: bool = False
    ) -> List[ChargeComponent]:
        """
        Clone all components from one fee structure to another.
        
        Args:
            source_fee_structure_id: Source fee structure ID
            target_fee_structure_id: Target fee structure ID
            audit_context: Audit information
            include_rules: Also clone associated charge rules
            
        Returns:
            List of cloned ChargeComponent instances
        """
        source_components = self.find_by_fee_structure(source_fee_structure_id)
        
        cloned_components = []
        for source in source_components:
            cloned = ChargeComponent(
                fee_structure_id=target_fee_structure_id,
                component_name=source.component_name,
                component_type=source.component_type,
                amount=source.amount,
                is_mandatory=source.is_mandatory,
                is_refundable=source.is_refundable,
                is_recurring=source.is_recurring,
                calculation_method=source.calculation_method,
                calculation_basis=source.calculation_basis,
                proration_allowed=source.proration_allowed,
                is_taxable=source.is_taxable,
                tax_percentage=source.tax_percentage,
                description=source.description,
                display_order=source.display_order,
                is_visible_to_student=source.is_visible_to_student,
                applies_to_room_types=source.applies_to_room_types,
                applies_from_date=source.applies_from_date,
                applies_to_date=source.applies_to_date
            )
            self._apply_audit(cloned, audit_context)
            cloned_components.append(cloned)
        
        self.session.bulk_save_objects(cloned_components, return_defaults=True)
        self.session.flush()
        
        # Clone rules if requested
        if include_rules:
            for original, cloned in zip(source_components, cloned_components):
                if original.charge_rules:
                    for rule in original.charge_rules:
                        cloned_rule = ChargeRule(
                            charge_component_id=cloned.id,
                            rule_name=rule.rule_name,
                            rule_type=rule.rule_type,
                            rule_condition=rule.rule_condition,
                            rule_action=rule.rule_action,
                            priority=rule.priority,
                            is_active=rule.is_active
                        )
                        self.session.add(cloned_rule)
            self.session.flush()
        
        return cloned_components
    
    def reorder_components(
        self,
        fee_structure_id: UUID,
        component_id_order: List[UUID],
        audit_context: Dict[str, Any]
    ) -> int:
        """
        Reorder components based on provided list.
        
        Args:
            fee_structure_id: Fee structure identifier
            component_id_order: Ordered list of component IDs
            audit_context: Audit information
            
        Returns:
            Number of components reordered
        """
        order_map = {comp_id: idx for idx, comp_id in enumerate(component_id_order)}
        return self.bulk_update_display_order(order_map, audit_context)
    
    # ============================================================
    # Search and Filtering
    # ============================================================
    
    def search_components(
        self,
        search_term: str,
        fee_structure_ids: Optional[List[UUID]] = None,
        component_types: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[ChargeComponent]:
        """
        Search components by name or description.
        
        Args:
            search_term: Term to search for
            fee_structure_ids: Optional fee structure filter
            component_types: Optional component type filter
            limit: Maximum results to return
            
        Returns:
            List of matching ChargeComponent instances
        """
        search_pattern = f"%{search_term}%"
        
        query = self.session.query(ChargeComponent).filter(
            or_(
                ChargeComponent.component_name.ilike(search_pattern),
                ChargeComponent.description.ilike(search_pattern)
            ),
            ChargeComponent.deleted_at.is_(None)
        )
        
        if fee_structure_ids:
            query = query.filter(ChargeComponent.fee_structure_id.in_(fee_structure_ids))
        
        if component_types:
            query = query.filter(ChargeComponent.component_type.in_(component_types))
        
        return query.limit(limit).all()
    
    def filter_components(
        self,
        filters: Dict[str, Any]
    ) -> List[ChargeComponent]:
        """
        Filter components based on dynamic criteria.
        
        Args:
            filters: Dictionary of filter criteria
            
        Returns:
            List of filtered ChargeComponent instances
        """
        query = self.session.query(ChargeComponent).filter(
            ChargeComponent.deleted_at.is_(None)
        )
        
        if 'fee_structure_id' in filters:
            query = query.filter(ChargeComponent.fee_structure_id == filters['fee_structure_id'])
        
        if 'component_type' in filters:
            query = query.filter(ChargeComponent.component_type == filters['component_type'])
        
        if 'is_mandatory' in filters:
            query = query.filter(ChargeComponent.is_mandatory == filters['is_mandatory'])
        
        if 'is_recurring' in filters:
            query = query.filter(ChargeComponent.is_recurring == filters['is_recurring'])
        
        if 'is_taxable' in filters:
            query = query.filter(ChargeComponent.is_taxable == filters['is_taxable'])
        
        if 'is_refundable' in filters:
            query = query.filter(ChargeComponent.is_refundable == filters['is_refundable'])
        
        if 'min_amount' in filters:
            query = query.filter(ChargeComponent.amount >= filters['min_amount'])
        
        if 'max_amount' in filters:
            query = query.filter(ChargeComponent.amount <= filters['max_amount'])
        
        if 'calculation_method' in filters:
            query = query.filter(ChargeComponent.calculation_method == filters['calculation_method'])
        
        if 'proration_allowed' in filters:
            query = query.filter(ChargeComponent.proration_allowed == filters['proration_allowed'])
        
        return query.order_by(ChargeComponent.display_order).all()
    
    # ============================================================
    # Validation Helpers
    # ============================================================
    
    def _validate_component(
        self,
        component_type: str,
        amount: Decimal,
        additional_data: Dict[str, Any]
    ) -> None:
        """
validate component data."""
        valid_types = ['rent', 'deposit', 'mess', 'electricity', 'water', 'maintenance', 'amenity', 'other']
        if component_type not in valid_types:
            raise ValidationException(f"Invalid component_type. Must be one of: {', '.join(valid_types)}")
        
        if amount < Decimal('0'):
            raise ValidationException("Component amount cannot be negative")
        
        tax_percentage = additional_data.get('tax_percentage', Decimal('0'))
        if tax_percentage < Decimal('0') or tax_percentage > Decimal('100'):
            raise ValidationException("Tax percentage must be between 0 and 100")
        
        calculation_method = additional_data.get('calculation_method', 'fixed')
        valid_methods = ['fixed', 'variable', 'percentage', 'tiered', 'actual']
        if calculation_method not in valid_methods:
            raise ValidationException(
                f"Invalid calculation_method. Must be one of: {', '.join(valid_methods)}"
            )
        
        # Validate date range if provided
        applies_from = additional_data.get('applies_from_date')
        applies_to = additional_data.get('applies_to_date')
        if applies_from and applies_to and applies_to <= applies_from:
            raise ValidationException("applies_to_date must be after applies_from_date")
    
    def _check_duplicate_component(
        self,
        fee_structure_id: UUID,
        component_name: str,
        exclude_id: Optional[UUID]
    ) -> None:
        """Check for duplicate component names in the same fee structure."""
        query = self.session.query(ChargeComponent).filter(
            ChargeComponent.fee_structure_id == fee_structure_id,
            ChargeComponent.component_name == component_name,
            ChargeComponent.deleted_at.is_(None)
        )
        
        if exclude_id:
            query = query.filter(ChargeComponent.id != exclude_id)
        
        if query.first():
            raise ConflictException(
                f"Component with name '{component_name}' already exists in this fee structure"
            )
    
    def _apply_audit(
        self,
        entity: ChargeComponent,
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


class ChargeRuleRepository(BaseRepository[ChargeRule]):
    """
    Charge Rule Repository
    
    Manages business rules associated with charge components including
    discounts, surcharges, waivers, proration, and conditional logic.
    """
    
    def __init__(self, session: Session):
        super().__init__(ChargeRule, session)
    
    # ============================================================
    # Core CRUD Operations
    # ============================================================
    
    def create_charge_rule(
        self,
        charge_component_id: UUID,
        rule_name: str,
        rule_type: str,
        rule_condition: str,
        rule_action: str,
        audit_context: Dict[str, Any],
        **kwargs
    ) -> ChargeRule:
        """
        Create a new charge rule.
        
        Args:
            charge_component_id: Parent component ID
            rule_name: Name of the rule
            rule_type: Type of rule (discount, surcharge, waiver, etc.)
            rule_condition: Condition expression (JSON or string)
            rule_action: Action expression (JSON or string)
            audit_context: Audit information
            **kwargs: Additional rule attributes
            
        Returns:
            Created ChargeRule instance
            
        Raises:
            ValidationException: If validation fails
        """
        self._validate_rule(rule_type, rule_condition, rule_action)
        
        rule = ChargeRule(
            charge_component_id=charge_component_id,
            rule_name=rule_name,
            rule_type=rule_type,
            rule_condition=rule_condition,
            rule_action=rule_action,
            priority=kwargs.pop('priority', 0),
            is_active=kwargs.pop('is_active', True),
            **kwargs
        )
        
        self._apply_audit(rule, audit_context)
        self.session.add(rule)
        self.session.flush()
        
        return rule
    
    def update_charge_rule(
        self,
        rule_id: UUID,
        update_data: Dict[str, Any],
        audit_context: Dict[str, Any]
    ) -> ChargeRule:
        """
        Update an existing charge rule.
        
        Args:
            rule_id: Rule identifier
            update_data: Fields to update
            audit_context: Audit information
            
        Returns:
            Updated ChargeRule instance
        """
        rule = self.find_by_id(rule_id)
        if not rule:
            raise NotFoundException(f"Charge rule {rule_id} not found")
        
        # Validate if rule type, condition, or action is being updated
        if any(k in update_data for k in ['rule_type', 'rule_condition', 'rule_action']):
            self._validate_rule(
                update_data.get('rule_type', rule.rule_type),
                update_data.get('rule_condition', rule.rule_condition),
                update_data.get('rule_action', rule.rule_action)
            )
        
        # Apply updates
        for key, value in update_data.items():
            if hasattr(rule, key) and key not in ['id', 'created_at']:
                setattr(rule, key, value)
        
        self._apply_audit(rule, audit_context, is_update=True)
        self.session.flush()
        
        return rule
    
    def activate_rule(
        self,
        rule_id: UUID,
        audit_context: Dict[str, Any]
    ) -> ChargeRule:
        """
        Activate a charge rule.
        
        Args:
            rule_id: Rule identifier
            audit_context: Audit information
            
        Returns:
            Activated ChargeRule instance
        """
        return self.update_charge_rule(
            rule_id,
            {'is_active': True},
            audit_context
        )
    
    def deactivate_rule(
        self,
        rule_id: UUID,
        audit_context: Dict[str, Any]
    ) -> ChargeRule:
        """
        Deactivate a charge rule.
        
        Args:
            rule_id: Rule identifier
            audit_context: Audit information
            
        Returns:
            Deactivated ChargeRule instance
        """
        return self.update_charge_rule(
            rule_id,
            {'is_active': False},
            audit_context
        )
    
    # ============================================================
    # Query Operations
    # ============================================================
    
    def find_by_component(
        self,
        charge_component_id: UUID,
        rule_type: Optional[str] = None,
        is_active: Optional[bool] = True
    ) -> List[ChargeRule]:
        """
        Find rules for a specific charge component.
        
        Args:
            charge_component_id: Component identifier
            rule_type: Optional rule type filter
            is_active: Filter by active status (None for all)
            
        Returns:
            List of ChargeRule instances ordered by priority
        """
        query = self.session.query(ChargeRule).filter(
            ChargeRule.charge_component_id == charge_component_id
        )
        
        if rule_type:
            query = query.filter(ChargeRule.rule_type == rule_type)
        
        if is_active is not None:
            query = query.filter(ChargeRule.is_active == is_active)
        
        return query.order_by(ChargeRule.priority.desc()).all()
    
    def find_by_type(
        self,
        rule_type: str,
        is_active: bool = True,
        component_ids: Optional[List[UUID]] = None
    ) -> List[ChargeRule]:
        """
        Find all rules of a specific type.
        
        Args:
            rule_type: Rule type to search
            is_active: Filter by active status
            component_ids: Optional component filter
            
        Returns:
            List of ChargeRule instances
        """
        query = self.session.query(ChargeRule).filter(
            ChargeRule.rule_type == rule_type
        )
        
        if is_active:
            query = query.filter(ChargeRule.is_active == True)
        
        if component_ids:
            query = query.filter(ChargeRule.charge_component_id.in_(component_ids))
        
        return query.order_by(ChargeRule.priority.desc()).all()
    
    def get_highest_priority_rules(
        self,
        charge_component_id: UUID,
        limit: int = 5,
        is_active: bool = True
    ) -> List[ChargeRule]:
        """
        Get highest priority rules for a component.
        
        Args:
            charge_component_id: Component identifier
            limit: Maximum number of rules to return
            is_active: Only return active rules
            
        Returns:
            List of highest priority ChargeRule instances
        """
        query = self.session.query(ChargeRule).filter(
            ChargeRule.charge_component_id == charge_component_id
        )
        
        if is_active:
            query = query.filter(ChargeRule.is_active == True)
        
        return query.order_by(ChargeRule.priority.desc()).limit(limit).all()
    
    def find_discount_rules(
        self,
        component_ids: Optional[List[UUID]] = None,
        is_active: bool = True
    ) -> List[ChargeRule]:
        """
        Find all discount rules.
        
        Args:
            component_ids: Optional component filter
            is_active: Filter by active status
            
        Returns:
            List of discount ChargeRule instances
        """
        return self.find_by_type('discount', is_active, component_ids)
    
    def find_surcharge_rules(
        self,
        component_ids: Optional[List[UUID]] = None,
        is_active: bool = True
    ) -> List[ChargeRule]:
        """
        Find all surcharge rules.
        
        Args:
            component_ids: Optional component filter
            is_active: Filter by active status
            
        Returns:
            List of surcharge ChargeRule instances
        """
        return self.find_by_type('surcharge', is_active, component_ids)
    
    def find_waiver_rules(
        self,
        component_ids: Optional[List[UUID]] = None,
        is_active: bool = True
    ) -> List[ChargeRule]:
        """
        Find all waiver rules.
        
        Args:
            component_ids: Optional component filter
            is_active: Filter by active status
            
        Returns:
            List of waiver ChargeRule instances
        """
        return self.find_by_type('waiver', is_active, component_ids)
    
    def find_proration_rules(
        self,
        component_ids: Optional[List[UUID]] = None,
        is_active: bool = True
    ) -> List[ChargeRule]:
        """
        Find all proration rules.
        
        Args:
            component_ids: Optional component filter
            is_active: Filter by active status
            
        Returns:
            List of proration ChargeRule instances
        """
        return self.find_by_type('proration', is_active, component_ids)
    
    def find_conditional_rules(
        self,
        component_ids: Optional[List[UUID]] = None,
        is_active: bool = True
    ) -> List[ChargeRule]:
        """
        Find all conditional rules.
        
        Args:
            component_ids: Optional component filter
            is_active: Filter by active status
            
        Returns:
            List of conditional ChargeRule instances
        """
        return self.find_by_type('conditional', is_active, component_ids)
    
    # ============================================================
    # Analytics
    # ============================================================
    
    def get_rule_statistics(
        self,
        charge_component_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Get statistics on charge rules.
        
        Args:
            charge_component_id: Optional component filter
            
        Returns:
            Dictionary with rule statistics
        """
        query = self.session.query(
            func.count(ChargeRule.id).label('total_rules'),
            func.sum(case((ChargeRule.is_active == True, 1), else_=0)).label('active_rules'),
            func.sum(case((ChargeRule.rule_type == 'discount', 1), else_=0)).label('discount_rules'),
            func.sum(case((ChargeRule.rule_type == 'surcharge', 1), else_=0)).label('surcharge_rules'),
            func.sum(case((ChargeRule.rule_type == 'waiver', 1), else_=0)).label('waiver_rules'),
            func.sum(case((ChargeRule.rule_type == 'proration', 1), else_=0)).label('proration_rules'),
            func.sum(case((ChargeRule.rule_type == 'conditional', 1), else_=0)).label('conditional_rules'),
            func.avg(ChargeRule.priority).label('avg_priority')
        )
        
        if charge_component_id:
            query = query.filter(ChargeRule.charge_component_id == charge_component_id)
        
        result = query.first()
        
        total = result.total_rules or 0
        
        return {
            'total_rules': total,
            'active_rules': result.active_rules or 0,
            'inactive_rules': total - (result.active_rules or 0),
            'active_percentage': (result.active_rules / total * 100) if total else 0,
            'by_type': {
                'discount': result.discount_rules or 0,
                'surcharge': result.surcharge_rules or 0,
                'waiver': result.waiver_rules or 0,
                'proration': result.proration_rules or 0,
                'conditional': result.conditional_rules or 0
            },
            'average_priority': float(result.avg_priority or 0)
        }
    
    # ============================================================
    # Bulk Operations
    # ============================================================
    
    def bulk_activate_rules(
        self,
        rule_ids: List[UUID],
        audit_context: Dict[str, Any]
    ) -> int:
        """
        Bulk activate multiple rules.
        
        Args:
            rule_ids: List of rule IDs
            audit_context: Audit information
            
        Returns:
            Number of rules activated
        """
        updated = self.session.query(ChargeRule).filter(
            ChargeRule.id.in_(rule_ids)
        ).update(
            {
                'is_active': True,
                'updated_at': datetime.utcnow(),
                'updated_by': audit_context.get('user_id')
            },
            synchronize_session=False
        )
        
        self.session.flush()
        return updated
    
    def bulk_deactivate_rules(
        self,
        rule_ids: List[UUID],
        audit_context: Dict[str, Any]
    ) -> int:
        """
        Bulk deactivate multiple rules.
        
        Args:
            rule_ids: List of rule IDs
            audit_context: Audit information
            
        Returns:
            Number of rules deactivated
        """
        updated = self.session.query(ChargeRule).filter(
            ChargeRule.id.in_(rule_ids)
        ).update(
            {
                'is_active': False,
                'updated_at': datetime.utcnow(),
                'updated_by': audit_context.get('user_id')
            },
            synchronize_session=False
        )
        
        self.session.flush()
        return updated
    
    def bulk_update_priority(
        self,
        priority_updates: Dict[UUID, int],
        audit_context: Dict[str, Any]
    ) -> int:
        """
        Bulk update priorities for rules.
        
        Args:
            priority_updates: Dictionary mapping rule_id to priority
            audit_context: Audit information
            
        Returns:
            Number of rules updated
        """
        updated = 0
        
        for rule_id, priority in priority_updates.items():
            result = self.session.query(ChargeRule).filter(
                ChargeRule.id == rule_id
            ).update(
                {
                    'priority': priority,
                    'updated_at': datetime.utcnow(),
                    'updated_by': audit_context.get('user_id')
                },
                synchronize_session=False
            )
            updated += result
        
        self.session.flush()
        return updated
    
    # ============================================================
    # Validation Helpers
    # ============================================================
    
    def _validate_rule(
        self,
        rule_type: str,
        rule_condition: str,
        rule_action: str
    ) -> None:
        """Validate rule data."""
        valid_types = ['discount', 'surcharge', 'waiver', 'proration', 'conditional']
        if rule_type not in valid_types:
            raise ValidationException(
                f"Invalid rule_type. Must be one of: {', '.join(valid_types)}"
            )
        
        # Validate JSON if it appears to be JSON
        if rule_condition.strip().startswith('{'):
            try:
                json.loads(rule_condition)
            except json.JSONDecodeError:
                raise ValidationException("rule_condition must be valid JSON")
        
        if rule_action.strip().startswith('{'):
            try:
                json.loads(rule_action)
            except json.JSONDecodeError:
                raise ValidationException("rule_action must be valid JSON")
    
    def _apply_audit(
        self,
        entity: ChargeRule,
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


class DiscountConfigurationRepository(BaseRepository[DiscountConfiguration]):
    """
    Discount Configuration Repository
    
    Manages discount configurations with validation, usage tracking,
    applicability checking, and comprehensive analytics.
    """
    
    def __init__(self, session: Session):
        super().__init__(DiscountConfiguration, session)
    
    # ============================================================
    # Core CRUD Operations
    # ============================================================
    
    def create_discount(
        self,
        discount_name: str,
        discount_type: str,
        applies_to: str,
        audit_context: Dict[str, Any],
        **kwargs
    ) -> DiscountConfiguration:
        """
        Create a new discount configuration.
        
        Args:
            discount_name: Name of the discount
            discount_type: Type of discount (percentage, fixed_amount, waiver)
            applies_to: What the discount applies to
            audit_context: Audit information
            **kwargs: Additional discount attributes
            
        Returns:
            Created DiscountConfiguration instance
            
        Raises:
            ValidationException: If validation fails
            ConflictException: If duplicate code
        """
        # Validate discount configuration
        self._validate_discount(discount_type, applies_to, kwargs)
        
        # Check for duplicate discount codes
        if 'discount_code' in kwargs and kwargs['discount_code']:
            self._check_duplicate_code(kwargs['discount_code'], None)
        
        discount = DiscountConfiguration(
            discount_name=discount_name,
            discount_type=discount_type,
            applies_to=applies_to,
            is_active=kwargs.pop('is_active', True),
            current_usage_count=0,
            **kwargs
        )
        
        self._apply_audit(discount, audit_context)
        self.session.add(discount)
        self.session.flush()
        
        return discount
    
    def update_discount(
        self,
        discount_id: UUID,
        update_data: Dict[str, Any],
        audit_context: Dict[str, Any]
    ) -> DiscountConfiguration:
        """
        Update an existing discount configuration.
        
        Args:
            discount_id: Discount identifier
            update_data: Fields to update
            audit_context: Audit information
            
        Returns:
            Updated DiscountConfiguration instance
            
        Raises:
            NotFoundException: If discount not found
            ValidationException: If validation fails
        """
        discount = self.find_by_id(discount_id)
        if not discount:
            raise NotFoundException(f"Discount configuration {discount_id} not found")
        
        # Validate updates
        self._validate_discount(
            update_data.get('discount_type', discount.discount_type),
            update_data.get('applies_to', discount.applies_to),
            update_data
        )
        
        # Check for duplicate codes if code is being changed
        if 'discount_code' in update_data and update_data['discount_code'] != discount.discount_code:
            self._check_duplicate_code(update_data['discount_code'], discount_id)
        
        # Apply updates
        for key, value in update_data.items():
            if hasattr(discount, key) and key not in ['id', 'created_at', 'current_usage_count']:
                setattr(discount, key, value)
        
        self._apply_audit(discount, audit_context, is_update=True)
        self.session.flush()
        
        return discount
    
    def activate_discount(
        self,
        discount_id: UUID,
        audit_context: Dict[str, Any]
    ) -> DiscountConfiguration:
        """
        Activate a discount.
        
        Args:
            discount_id: Discount identifier
            audit_context: Audit information
            
        Returns:
            Activated DiscountConfiguration
        """
        return self.update_discount(
            discount_id,
            {'is_active': True},
            audit_context
        )
    
    def deactivate_discount(
        self,
        discount_id: UUID,
        audit_context: Dict[str, Any]
    ) -> DiscountConfiguration:
        """
        Deactivate a discount.
        
        Args:
            discount_id: Discount identifier
            audit_context: Audit information
            
        Returns:
            Deactivated DiscountConfiguration
        """
        return self.update_discount(
            discount_id,
            {'is_active': False},
            audit_context
        )
    
    # ============================================================
    # Query Operations
    # ============================================================
    
    def find_active_discounts(
        self,
        applies_to: Optional[str] = None,
        hostel_id: Optional[UUID] = None,
        room_type: Optional[str] = None,
        as_of_date: Optional[Date] = None,
        new_students_only: Optional[bool] = None
    ) -> List[DiscountConfiguration]:
        """
        Find active discounts with comprehensive filters.
        
        Args:
            applies_to: What the discount applies to
            hostel_id: Optional hostel filter
            room_type: Optional room type filter
            as_of_date: Date to check validity
            new_students_only: Filter for new student discounts
            
        Returns:
            List of active DiscountConfiguration instances
        """
        check_date = as_of_date or Date.today()
        
        query = self.session.query(DiscountConfiguration).filter(
            DiscountConfiguration.is_active == True,
            DiscountConfiguration.deleted_at.is_(None),
            or_(
                DiscountConfiguration.valid_from.is_(None),
                DiscountConfiguration.valid_from <= check_date
            ),
            or_(
                DiscountConfiguration.valid_to.is_(None),
                DiscountConfiguration.valid_to >= check_date
            )
        )
        
        if applies_to:
            query = query.filter(DiscountConfiguration.applies_to == applies_to)
        
        if hostel_id:
            query = query.filter(
                or_(
                    DiscountConfiguration.hostel_ids.is_(None),
                    DiscountConfiguration.hostel_ids.like(f'%{hostel_id}%')
                )
            )
        
        if room_type:
            query = query.filter(
                or_(
                    DiscountConfiguration.room_types.is_(None),
                    DiscountConfiguration.room_types.like(f'%{room_type}%')
                )
            )
        
        if new_students_only is not None:
            query = query.filter(DiscountConfiguration.valid_for_new_students_only == new_students_only)
        
        # Filter by usage limit
        query = query.filter(
            or_(
                DiscountConfiguration.max_usage_count.is_(None),
                DiscountConfiguration.current_usage_count < DiscountConfiguration.max_usage_count
            )
        )
        
        return query.order_by(DiscountConfiguration.discount_name).all()
    
    def find_by_code(
        self,
        discount_code: str,
        validate_active: bool = True,
        check_date: Optional[Date] = None
    ) -> Optional[DiscountConfiguration]:
        """
        Find discount by code with validation.
        
        Args:
            discount_code: Discount code to search
            validate_active: Whether to check if discount is currently active
            check_date: Date to validate against
            
        Returns:
            DiscountConfiguration instance or None
        """
        query = self.session.query(DiscountConfiguration).filter(
            DiscountConfiguration.discount_code == discount_code,
            DiscountConfiguration.deleted_at.is_(None)
        )
        
        if validate_active:
            today = check_date or Date.today()
            query = query.filter(
                DiscountConfiguration.is_active == True,
                or_(
                    DiscountConfiguration.valid_from.is_(None),
                    DiscountConfiguration.valid_from <= today
                ),
                or_(
                    DiscountConfiguration.valid_to.is_(None),
                    DiscountConfiguration.valid_to >= today
                ),
                or_(
                    DiscountConfiguration.max_usage_count.is_(None),
                    DiscountConfiguration.current_usage_count < DiscountConfiguration.max_usage_count
                )
            )
        
        return query.first()
    
    def find_expiring_soon(
        self,
        days_ahead: int = 7,
        hostel_id: Optional[UUID] = None
    ) -> List[DiscountConfiguration]:
        """
        Find discounts expiring within specified days.
        
        Args:
            days_ahead: Number of days to look ahead
            hostel_id: Optional hostel filter
            
        Returns:
            List of expiring DiscountConfiguration instances
        """
        today = Date.today()
        future_date = Date.fromordinal(today.toordinal() + days_ahead)
        
        query = self.session.query(DiscountConfiguration).filter(
            DiscountConfiguration.is_active == True,
            DiscountConfiguration.valid_to.isnot(None),
            DiscountConfiguration.valid_to > today,
            DiscountConfiguration.valid_to <= future_date,
            DiscountConfiguration.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(
                or_(
                    DiscountConfiguration.hostel_ids.is_(None),
                    DiscountConfiguration.hostel_ids.like(f'%{hostel_id}%')
                )
            )
        
        return query.order_by(DiscountConfiguration.valid_to).all()
    
    def find_by_hostel(
        self,
        hostel_id: UUID,
        include_inactive: bool = False,
        as_of_date: Optional[Date] = None
    ) -> List[DiscountConfiguration]:
        """
        Find all discounts applicable to a specific hostel.
        
        Args:
            hostel_id: Hostel identifier
            include_inactive: Include inactive discounts
            as_of_date: Date to check validity
            
        Returns:
            List of DiscountConfiguration instances
        """
        query = self.session.query(DiscountConfiguration).filter(
            or_(
                DiscountConfiguration.hostel_ids.is_(None),
                DiscountConfiguration.hostel_ids.like(f'%{hostel_id}%')
            ),
            DiscountConfiguration.deleted_at.is_(None)
        )
        
        if not include_inactive:
            query = query.filter(DiscountConfiguration.is_active == True)
            
            if as_of_date:
                query = query.filter(
                    or_(
                        DiscountConfiguration.valid_from.is_(None),
                        DiscountConfiguration.valid_from <= as_of_date
                    ),
                    or_(
                        DiscountConfiguration.valid_to.is_(None),
                        DiscountConfiguration.valid_to >= as_of_date
                    )
                )
        
        return query.order_by(DiscountConfiguration.discount_name).all()
    
    def find_nearly_exhausted(
        self,
        threshold_percentage: float = 0.9,
        include_unlimited: bool = False
    ) -> List[DiscountConfiguration]:
        """
        Find discounts nearly exhausted (used close to max limit).
        
        Args:
            threshold_percentage: Threshold percentage (0.0 to 1.0)
            include_unlimited: Include discounts with no usage limit
            
        Returns:
            List of nearly exhausted DiscountConfiguration instances
        """
        query = self.session.query(DiscountConfiguration).filter(
            DiscountConfiguration.is_active == True,
            DiscountConfiguration.deleted_at.is_(None)
        )
        
        if not include_unlimited:
            query = query.filter(DiscountConfiguration.max_usage_count.isnot(None))
        
        query = query.filter(
            DiscountConfiguration.current_usage_count >= (
                DiscountConfiguration.max_usage_count * threshold_percentage
            )
        )
        
        return query.order_by(
            (DiscountConfiguration.current_usage_count / DiscountConfiguration.max_usage_count).desc()
        ).all()
    
    def find_by_type(
        self,
        discount_type: str,
        is_active: bool = True
    ) -> List[DiscountConfiguration]:
        """
        Find discounts by type.
        
        Args:
            discount_type: Type of discount
            is_active: Filter by active status
            
        Returns:
            List of DiscountConfiguration instances
        """
        query = self.session.query(DiscountConfiguration).filter(
            DiscountConfiguration.discount_type == discount_type,
            DiscountConfiguration.deleted_at.is_(None)
        )
        
        if is_active:
            query = query.filter(DiscountConfiguration.is_active == True)
        
        return query.all()
    
    def find_for_new_students(
        self,
        hostel_id: Optional[UUID] = None,
        room_type: Optional[str] = None,
        as_of_date: Optional[Date] = None
    ) -> List[DiscountConfiguration]:
        """
        Find discounts applicable to new students.
        
        Args:
            hostel_id: Optional hostel filter
            room_type: Optional room type filter
            as_of_date: Date to check validity
            
        Returns:
            List of DiscountConfiguration instances for new students
        """
        return self.find_active_discounts(
            hostel_id=hostel_id,
            room_type=room_type,
            as_of_date=as_of_date,
            new_students_only=True
        )
    
    # ============================================================
    # Usage Tracking
    # ============================================================
    
    def increment_usage(
        self,
        discount_id: UUID
    ) -> DiscountConfiguration:
        """
        Increment usage count for a discount.
        
        Args:
            discount_id: Discount identifier
            
        Returns:
            Updated DiscountConfiguration instance
            
        Raises:
            NotFoundException: If discount not found
            ValidationException: If max usage exceeded
        """
        discount = self.find_by_id(discount_id)
        if not discount:
            raise NotFoundException(f"Discount {discount_id} not found")
        
        if discount.max_usage_count and discount.current_usage_count >= discount.max_usage_count:
            raise ValidationException("Discount has reached maximum usage limit")
        
        discount.current_usage_count += 1
        discount.updated_at = datetime.utcnow()
        
        self.session.flush()
        return discount
    
    def decrement_usage(
        self,
        discount_id: UUID
    ) -> DiscountConfiguration:
        """
        Decrement usage count for a discount (e.g., on cancellation).
        
        Args:
            discount_id: Discount identifier
            
        Returns:
            Updated DiscountConfiguration instance
            
        Raises:
            NotFoundException: If discount not found
        """
        discount = self.find_by_id(discount_id)
        if not discount:
            raise NotFoundException(f"Discount {discount_id} not found")
        
        if discount.current_usage_count > 0:
            discount.current_usage_count -= 1
            discount.updated_at = datetime.utcnow()
            self.session.flush()
        
        return discount
    
    def reset_usage_count(
        self,
        discount_id: UUID,
        audit_context: Dict[str, Any]
    ) -> DiscountConfiguration:
        """
        Reset usage count to zero.
        
        Args:
            discount_id: Discount identifier
            audit_context: Audit information
            
        Returns:
            Updated DiscountConfiguration instance
        """
        return self.update_discount(
            discount_id,
            {'current_usage_count': 0},
            audit_context
        )
    
    def get_usage_statistics(
        self,
        discount_id: UUID
    ) -> Dict[str, Any]:
        """
        Get detailed usage statistics for a discount.
        
        Args:
            discount_id: Discount identifier
            
        Returns:
            Dictionary with usage statistics
            
        Raises:
            NotFoundException: If discount not found
        """
        discount = self.find_by_id(discount_id)
        if not discount:
            raise NotFoundException(f"Discount {discount_id} not found")
        
        usage_percentage = None
        if discount.max_usage_count:
            usage_percentage = (
                discount.current_usage_count / discount.max_usage_count * 100
            )
        
        days_until_expiry = None
        if discount.valid_to:
            days_until_expiry = (discount.valid_to - Date.today()).days
        
        return {
            'discount_id': str(discount.id),
            'discount_name': discount.discount_name,
            'discount_code': discount.discount_code,
            'current_usage': discount.current_usage_count,
            'max_usage': discount.max_usage_count,
            'remaining_usage': discount.remaining_usage_count,
            'usage_percentage': float(usage_percentage) if usage_percentage else None,
            'is_exhausted': discount.max_usage_count and 
                          discount.current_usage_count >= discount.max_usage_count,
            'is_active': discount.is_active,
            'is_currently_valid': discount.is_currently_valid,
            'valid_from': discount.valid_from.isoformat() if discount.valid_from else None,
            'valid_to': discount.valid_to.isoformat() if discount.valid_to else None,
            'days_until_expiry': days_until_expiry
        }
    
    # ============================================================
    # Validation and Applicability
    # ============================================================
    
    def validate_discount_applicability(
        self,
        discount_id: UUID,
        hostel_id: UUID,
        room_type: str,
        is_new_student: bool = False,
        stay_months: Optional[int] = None,
        check_date: Optional[Date] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Comprehensive validation of discount applicability.
        
        Args:
            discount_id: Discount identifier
            hostel_id: Hostel identifier
            room_type: Room type
            is_new_student: Whether student is new
            stay_months: Length of stay in months
            check_date: Date to validate against
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        discount = self.find_by_id(discount_id)
        if not discount:
            return False, "Discount not found"
        
        check_date = check_date or Date.today()
        
        # Check if discount is active
        if not discount.is_active:
            return False, "Discount is not active"
        
        # Check date validity
        if discount.valid_from and check_date < discount.valid_from:
            return False, f"Discount not valid until {discount.valid_from.isoformat()}"
        
        if discount.valid_to and check_date > discount.valid_to:
            return False, f"Discount expired on {discount.valid_to.isoformat()}"
        
        # Check usage limit
        if discount.max_usage_count and discount.current_usage_count >= discount.max_usage_count:
            return False, "Discount has reached maximum usage limit"
        
        # Check hostel applicability
        if discount.hostel_ids:
            if str(hostel_id) not in discount.hostel_ids:
                return False, "Discount not applicable to this hostel"
        
        # Check room type applicability
        if discount.room_types:
            if room_type not in discount.room_types:
                return False, "Discount not applicable to this room type"
        
        # Check new student requirement
        if discount.valid_for_new_students_only and not is_new_student:
            return False, "Discount only valid for new students"
        
        # Check minimum stay requirement
        if discount.minimum_stay_months and stay_months:
            if stay_months < discount.minimum_stay_months:
                return False, f"Minimum stay of {discount.minimum_stay_months} months required"
        
        return True, None
    
    def calculate_discount_amount(
        self,
        discount_id: UUID,
        base_amount: Decimal
    ) -> Decimal:
        """
        Calculate discount amount based on configuration.
        
        Args:
            discount_id: Discount identifier
            base_amount: Base amount to apply discount to
            
        Returns:
            Calculated discount amount
            
        Raises:
            NotFoundException: If discount not found
        """
        discount = self.find_by_id(discount_id)
        if not discount:
            raise NotFoundException(f"Discount {discount_id} not found")
        
        if discount.discount_type == 'percentage':
            return (base_amount * discount.discount_percentage / 100).quantize(Decimal('0.01'))
        elif discount.discount_type == 'fixed_amount':
            return min(discount.discount_amount, base_amount)
        elif discount.discount_type == 'waiver':
            return base_amount
        
        return Decimal('0.00')
    
    def get_best_applicable_discount(
        self,
        hostel_id: UUID,
        room_type: str,
        base_amount: Decimal,
        is_new_student: bool = False,
        stay_months: Optional[int] = None,
        check_date: Optional[Date] = None
    ) -> Optional[Tuple[DiscountConfiguration, Decimal]]:
        """
        Find the best applicable discount for given criteria.
        
        Args:
            hostel_id: Hostel identifier
            room_type: Room type
            base_amount: Base amount to calculate discount
            is_new_student: Whether student is new
            stay_months: Length of stay
            check_date: Date to check
            
        Returns:
            Tuple of (DiscountConfiguration, discount_amount) or None
        """
        applicable_discounts = self.find_active_discounts(
            hostel_id=hostel_id,
            room_type=room_type,
            as_of_date=check_date,
            new_students_only=is_new_student if is_new_student else None
        )
        
        best_discount = None
        best_amount = Decimal('0.00')
        
        for discount in applicable_discounts:
            # Validate applicability
            is_valid, _ = self.validate_discount_applicability(
                discount.id,
                hostel_id,
                room_type,
                is_new_student,
                stay_months,
                check_date
            )
            
            if is_valid:
                discount_amount = self.calculate_discount_amount(discount.id, base_amount)
                if discount_amount > best_amount:
                    best_amount = discount_amount
                    best_discount = discount
        
        if best_discount:
            return (best_discount, best_amount)
        
        return None
    
    # ============================================================
    # Analytics
    # ============================================================
    
    def get_discount_analytics(
        self,
        start_date: Optional[Date] = None,
        end_date: Optional[Date] = None,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive discount analytics.
        
        Args:
            start_date: Optional start date for analysis
            end_date: Optional end date for analysis
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary with discount analytics
        """
        query = self.session.query(
            func.count(DiscountConfiguration.id).label('total_discounts'),
            func.sum(case(
                (DiscountConfiguration.is_active == True, 1),
                else_=0
            )).label('active_discounts'),
            func.sum(DiscountConfiguration.current_usage_count).label('total_usage'),
            func.avg(DiscountConfiguration.current_usage_count).label('avg_usage'),
            func.avg(DiscountConfiguration.discount_percentage).label('avg_percentage'),
            func.avg(DiscountConfiguration.discount_amount).label('avg_fixed_amount'),
            func.sum(case(
                (DiscountConfiguration.discount_type == 'percentage', 1),
                else_=0
            )).label('percentage_based'),
            func.sum(case(
                (DiscountConfiguration.discount_type == 'fixed_amount', 1),
                else_=0
            )).label('fixed_amount_based'),
            func.sum(case(
                (DiscountConfiguration.discount_type == 'waiver', 1),
                else_=0
            )).label('waiver_based'),
            func.sum(case(
                (DiscountConfiguration.valid_for_new_students_only == True, 1),
                else_=0
            )).label('new_student_only')
        ).filter(
            DiscountConfiguration.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(
                or_(
                    DiscountConfiguration.hostel_ids.is_(None),
                    DiscountConfiguration.hostel_ids.like(f'%{hostel_id}%')
                )
            )
        
        if start_date:
            query = query.filter(
                or_(
                    DiscountConfiguration.valid_from.is_(None),
                    DiscountConfiguration.valid_from >= start_date
                )
            )
        
        if end_date:
            query = query.filter(
                or_(
                    DiscountConfiguration.valid_to.is_(None),
                    DiscountConfiguration.valid_to <= end_date
                )
            )
        
        result = query.first()
        
        total = result.total_discounts or 0
        
        return {
            'total_discounts': total,
            'active_discounts': result.active_discounts or 0,
            'inactive_discounts': total - (result.active_discounts or 0),
            'active_percentage': (result.active_discounts / total * 100) if total else 0,
            'total_usage': result.total_usage or 0,
            'average_usage': float(result.avg_usage or 0),
            'average_discount_percentage': float(result.avg_percentage or 0),
            'average_fixed_amount': float(result.avg_fixed_amount or 0),
            'by_type': {
                'percentage': result.percentage_based or 0,
                'fixed_amount': result.fixed_amount_based or 0,
                'waiver': result.waiver_based or 0
            },
            'new_student_only_count': result.new_student_only or 0,
            'period': {
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None
            }
        }
    
    def get_discount_performance(
        self,
        discount_id: UUID
    ) -> Dict[str, Any]:
        """
        Get performance metrics for a specific discount.
        
        Args:
            discount_id: Discount identifier
            
        Returns:
            Dictionary with performance metrics
        """
        discount = self.find_by_id(discount_id)
        if not discount:
            raise NotFoundException(f"Discount {discount_id} not found")
        
        usage_stats = self.get_usage_statistics(discount_id)
        
        days_active = None
        if discount.valid_from:
            days_active = (Date.today() - discount.valid_from).days
        
        usage_rate = None
        if discount.max_usage_count and days_active:
            usage_rate = discount.current_usage_count / days_active
        
        return {
            **usage_stats,
            'days_active': days_active,
            'daily_usage_rate': float(usage_rate) if usage_rate else None,
            'discount_type': discount.discount_type,
            'applies_to': discount.applies_to,
            'value': {
                'percentage': float(discount.discount_percentage) if discount.discount_percentage else None,
                'fixed_amount': float(discount.discount_amount) if discount.discount_amount else None
            }
        }
    
    def compare_discount_effectiveness(
        self,
        discount_ids: List[UUID]
    ) -> List[Dict[str, Any]]:
        """
        Compare effectiveness of multiple discounts.
        
        Args:
            discount_ids: List of discount IDs to compare
            
        Returns:
            List of comparison data
        """
        comparisons = []
        
        for discount_id in discount_ids:
            try:
                performance = self.get_discount_performance(discount_id)
                comparisons.append(performance)
            except NotFoundException:
                continue
        
        # Sort by usage count descending
        comparisons.sort(key=lambda x: x['current_usage'], reverse=True)
        
        return comparisons
    
    # ============================================================
    # Bulk Operations
    # ============================================================
    
    def bulk_activate_discounts(
        self,
        discount_ids: List[UUID],
        audit_context: Dict[str, Any]
    ) -> int:
        """
        Bulk activate multiple discounts.
        
        Args:
            discount_ids: List of discount IDs
            audit_context: Audit information
            
        Returns:
            Number of discounts activated
        """
        updated = self.session.query(DiscountConfiguration).filter(
            DiscountConfiguration.id.in_(discount_ids),
            DiscountConfiguration.deleted_at.is_(None)
        ).update(
            {
                'is_active': True,
                'updated_at': datetime.utcnow(),
                'updated_by': audit_context.get('user_id')
            },
            synchronize_session=False
        )
        
        self.session.flush()
        return updated
    
    def bulk_deactivate_discounts(
        self,
        discount_ids: List[UUID],
        audit_context: Dict[str, Any]
    ) -> int:
        """
        Bulk deactivate multiple discounts.
        
        Args:
            discount_ids: List of discount IDs
            audit_context: Audit information
            
        Returns:
            Number of discounts deactivated
        """
        updated = self.session.query(DiscountConfiguration).filter(
            DiscountConfiguration.id.in_(discount_ids),
            DiscountConfiguration.deleted_at.is_(None)
        ).update(
            {
                'is_active': False,
                'updated_at': datetime.utcnow(),
                'updated_by': audit_context.get('user_id')
            },
            synchronize_session=False
        )
        
        self.session.flush()
        return updated
    
    def expire_discounts(
        self,
        expiry_date: Optional[Date] = None,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Expire discounts that have passed their valid_to date.
        
        Args:
            expiry_date: Date to check (defaults to today)
            audit_context: Optional audit information
            
        Returns:
            Number of discounts expired
        """
        check_date = expiry_date or Date.today()
        
        update_data = {
            'is_active': False,
            'updated_at': datetime.utcnow()
        }
        
        if audit_context:
            update_data['updated_by'] = audit_context.get('user_id')
        
        expired = self.session.query(DiscountConfiguration).filter(
            DiscountConfiguration.is_active == True,
            DiscountConfiguration.valid_to.isnot(None),
            DiscountConfiguration.valid_to < check_date,
            DiscountConfiguration.deleted_at.is_(None)
        ).update(update_data, synchronize_session=False)
        
        self.session.flush()
        return expired
    
    # ============================================================
    # Validation Helpers
    # ============================================================
    
    def _validate_discount(
        self,
        discount_type: str,
        applies_to: str,
        data: Dict[str, Any]
    ) -> None:
        """Validate discount configuration."""
        valid_types = ['percentage', 'fixed_amount', 'waiver']
        if discount_type not in valid_types:
            raise ValidationException(
                f"Invalid discount_type. Must be one of: {', '.join(valid_types)}"
            )
        
        valid_applies_to = ['base_rent', 'mess_charges', 'total', 'security_deposit']
        if applies_to not in valid_applies_to:
            raise ValidationException(
                f"Invalid applies_to. Must be one of: {', '.join(valid_applies_to)}"
            )
        
        # Validate discount value
        discount_percentage = data.get('discount_percentage')
        discount_amount = data.get('discount_amount')
        
        if discount_type == 'percentage':
            if not discount_percentage:
                raise ValidationException("discount_percentage required for percentage type")
            if discount_percentage < Decimal('0') or discount_percentage > Decimal('100'):
                raise ValidationException("discount_percentage must be between 0 and 100")
            if discount_amount:
                raise ValidationException("Cannot specify both discount_percentage and discount_amount")
        
        elif discount_type == 'fixed_amount':
            if not discount_amount:
                raise ValidationException("discount_amount required for fixed_amount type")
            if discount_amount < Decimal('0'):
                raise ValidationException("discount_amount cannot be negative")
            if discount_percentage:
                raise ValidationException("Cannot specify both discount_percentage and discount_amount")
        
        # Validate date range
        valid_from = data.get('valid_from')
        valid_to = data.get('valid_to')
        if valid_from and valid_to and valid_to <= valid_from:
            raise ValidationException("valid_to must be after valid_from")
        
        # Validate usage limits
        max_usage = data.get('max_usage_count')
        if max_usage is not None and max_usage <= 0:
            raise ValidationException("max_usage_count must be positive")
        
        # Validate minimum stay
        min_stay = data.get('minimum_stay_months')
        if min_stay is not None and min_stay < 1:
            raise ValidationException("minimum_stay_months must be at least 1")
    
    def _check_duplicate_code(
        self,
        discount_code: str,
        exclude_id: Optional[UUID]
    ) -> None:
        """Check for duplicate discount codes."""
        query = self.session.query(DiscountConfiguration).filter(
            DiscountConfiguration.discount_code == discount_code,
            DiscountConfiguration.deleted_at.is_(None)
        )
        
        if exclude_id:
            query = query.filter(DiscountConfiguration.id != exclude_id)
        
        if query.first():
            raise ConflictException(f"Discount code '{discount_code}' already exists")
    
    def _apply_audit(
        self,
        entity: DiscountConfiguration,
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