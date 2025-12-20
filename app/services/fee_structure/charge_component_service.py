# --- File: C:\Hostel-Main\app\services\fee_structure\charge_component_service.py ---
"""
Charge Component Service

Business logic layer for managing charge components, charge rules,
and discount configurations with comprehensive validation and analytics.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.fee_structure.charge_component import (
    ChargeComponent,
    ChargeRule,
    DiscountConfiguration,
)
from app.repositories.fee_structure.charge_component_repository import (
    ChargeComponentRepository,
    ChargeRuleRepository,
    DiscountConfigurationRepository,
)
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    ConflictException,
    BusinessLogicException,
)
from app.core.logging import logger


class ChargeComponentService:
    """
    Charge Component Service
    
    Manages individual charge components within fee structures including
    creation, updates, validation, and component-level calculations.
    """
    
    def __init__(self, session: Session):
        """
        Initialize service with database session.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.component_repo = ChargeComponentRepository(session)
        self.rule_repo = ChargeRuleRepository(session)
    
    # ============================================================
    # Core Charge Component Operations
    # ============================================================
    
    def create_charge_component(
        self,
        fee_structure_id: UUID,
        component_name: str,
        component_type: str,
        amount: Decimal,
        user_id: UUID,
        is_mandatory: bool = True,
        is_refundable: bool = False,
        is_recurring: bool = True,
        calculation_method: str = "fixed",
        calculation_basis: Optional[str] = None,
        proration_allowed: bool = False,
        is_taxable: bool = False,
        tax_percentage: Decimal = Decimal('0.00'),
        description: Optional[str] = None,
        display_order: int = 0,
        is_visible_to_student: bool = True,
        applies_to_room_types: Optional[str] = None,
        applies_from_date: Optional[Date] = None,
        applies_to_date: Optional[Date] = None
    ) -> ChargeComponent:
        """
        Create a new charge component.
        
        Args:
            fee_structure_id: Parent fee structure ID
            component_name: Name of the component
            component_type: Type (rent, deposit, mess, electricity, water, maintenance, amenity, other)
            amount: Component amount
            user_id: User creating the component
            is_mandatory: Whether component is mandatory
            is_refundable: Whether component is refundable
            is_recurring: Whether component recurs monthly
            calculation_method: Calculation method (fixed, variable, percentage, tiered, actual)
            calculation_basis: Basis for calculation if applicable
            proration_allowed: Whether proration is allowed
            is_taxable: Whether component is taxable
            tax_percentage: Tax percentage if taxable
            description: Component description
            display_order: Display order
            is_visible_to_student: Whether visible to students
            applies_to_room_types: Comma-separated room types
            applies_from_date: Start date of applicability
            applies_to_date: End date of applicability
            
        Returns:
            Created ChargeComponent instance
            
        Raises:
            ValidationException: If validation fails
            ConflictException: If duplicate component exists
        """
        logger.info(
            f"Creating charge component '{component_name}' for fee structure {fee_structure_id}"
        )
        
        # Validate component type and method
        self._validate_component_type(component_type)
        self._validate_calculation_method(calculation_method, calculation_basis)
        
        # Validate tax settings
        if is_taxable and (tax_percentage < Decimal('0') or tax_percentage > Decimal('100')):
            raise ValidationException("Tax percentage must be between 0 and 100")
        
        # Prepare audit context
        audit_context = {
            'user_id': user_id,
            'action': 'create_charge_component',
            'timestamp': datetime.utcnow()
        }
        
        try:
            component = self.component_repo.create_charge_component(
                fee_structure_id=fee_structure_id,
                component_name=component_name,
                component_type=component_type,
                amount=amount,
                audit_context=audit_context,
                is_mandatory=is_mandatory,
                is_refundable=is_refundable,
                is_recurring=is_recurring,
                calculation_method=calculation_method,
                calculation_basis=calculation_basis,
                proration_allowed=proration_allowed,
                is_taxable=is_taxable,
                tax_percentage=tax_percentage,
                description=description,
                display_order=display_order,
                is_visible_to_student=is_visible_to_student,
                applies_to_room_types=applies_to_room_types,
                applies_from_date=applies_from_date,
                applies_to_date=applies_to_date
            )
            
            self.session.commit()
            
            logger.info(f"Charge component created successfully: {component.id}")
            return component
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating charge component: {str(e)}")
            raise
    
    def update_charge_component(
        self,
        component_id: UUID,
        user_id: UUID,
        component_name: Optional[str] = None,
        amount: Optional[Decimal] = None,
        is_mandatory: Optional[bool] = None,
        is_refundable: Optional[bool] = None,
        is_recurring: Optional[bool] = None,
        calculation_method: Optional[str] = None,
        calculation_basis: Optional[str] = None,
        proration_allowed: Optional[bool] = None,
        is_taxable: Optional[bool] = None,
        tax_percentage: Optional[Decimal] = None,
        description: Optional[str] = None,
        display_order: Optional[int] = None,
        is_visible_to_student: Optional[bool] = None,
        applies_to_room_types: Optional[str] = None,
        applies_from_date: Optional[Date] = None,
        applies_to_date: Optional[Date] = None
    ) -> ChargeComponent:
        """
        Update existing charge component.
        
        Args:
            component_id: Component identifier
            user_id: User performing update
            (other parameters same as create, all optional)
            
        Returns:
            Updated ChargeComponent instance
            
        Raises:
            NotFoundException: If component not found
            ValidationException: If validation fails
        """
        logger.info(f"Updating charge component {component_id}")
        
        # Build update data
        update_data = {}
        if component_name is not None:
            update_data['component_name'] = component_name
        if amount is not None:
            update_data['amount'] = amount
        if is_mandatory is not None:
            update_data['is_mandatory'] = is_mandatory
        if is_refundable is not None:
            update_data['is_refundable'] = is_refundable
        if is_recurring is not None:
            update_data['is_recurring'] = is_recurring
        if calculation_method is not None:
            update_data['calculation_method'] = calculation_method
        if calculation_basis is not None:
            update_data['calculation_basis'] = calculation_basis
        if proration_allowed is not None:
            update_data['proration_allowed'] = proration_allowed
        if is_taxable is not None:
            update_data['is_taxable'] = is_taxable
        if tax_percentage is not None:
            update_data['tax_percentage'] = tax_percentage
        if description is not None:
            update_data['description'] = description
        if display_order is not None:
            update_data['display_order'] = display_order
        if is_visible_to_student is not None:
            update_data['is_visible_to_student'] = is_visible_to_student
        if applies_to_room_types is not None:
            update_data['applies_to_room_types'] = applies_to_room_types
        if applies_from_date is not None:
            update_data['applies_from_date'] = applies_from_date
        if applies_to_date is not None:
            update_data['applies_to_date'] = applies_to_date
        
        # Prepare audit context
        audit_context = {
            'user_id': user_id,
            'action': 'update_charge_component',
            'timestamp': datetime.utcnow()
        }
        
        try:
            component = self.component_repo.update_charge_component(
                component_id=component_id,
                update_data=update_data,
                audit_context=audit_context
            )
            
            self.session.commit()
            
            logger.info(f"Charge component updated successfully: {component.id}")
            return component
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating charge component: {str(e)}")
            raise
    
    def delete_charge_component(
        self,
        component_id: UUID,
        user_id: UUID,
        hard_delete: bool = False
    ) -> bool:
        """
        Delete charge component.
        
        Args:
            component_id: Component identifier
            user_id: User performing deletion
            hard_delete: Whether to permanently delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            NotFoundException: If component not found
        """
        logger.info(f"Deleting charge component {component_id}")
        
        audit_context = {
            'user_id': user_id,
            'action': 'delete_charge_component',
            'timestamp': datetime.utcnow()
        }
        
        try:
            result = self.component_repo.delete_charge_component(
                component_id=component_id,
                audit_context=audit_context,
                hard_delete=hard_delete
            )
            
            self.session.commit()
            
            logger.info(f"Charge component deleted successfully: {component_id}")
            return result
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error deleting charge component: {str(e)}")
            raise
    
    # ============================================================
    # Charge Component Retrieval
    # ============================================================
    
    def get_charge_component(
        self,
        component_id: UUID,
        include_rules: bool = False
    ) -> ChargeComponent:
        """
        Get charge component by ID.
        
        Args:
            component_id: Component identifier
            include_rules: Whether to load charge rules
            
        Returns:
            ChargeComponent instance
            
        Raises:
            NotFoundException: If not found
        """
        if include_rules:
            component = self.component_repo.get_component_with_rules(component_id)
        else:
            component = self.component_repo.find_by_id(component_id)
        
        if not component:
            raise NotFoundException(f"Charge component {component_id} not found")
        
        return component
    
    def get_components_by_fee_structure(
        self,
        fee_structure_id: UUID,
        component_type: Optional[str] = None,
        is_mandatory: Optional[bool] = None,
        is_recurring: Optional[bool] = None,
        include_deleted: bool = False
    ) -> List[ChargeComponent]:
        """
        Get all charge components for a fee structure.
        
        Args:
            fee_structure_id: Fee structure identifier
            component_type: Optional component type filter
            is_mandatory: Optional mandatory filter
            is_recurring: Optional recurring filter
            include_deleted: Include soft-deleted components
            
        Returns:
            List of ChargeComponent instances
        """
        return self.component_repo.find_by_fee_structure(
            fee_structure_id=fee_structure_id,
            component_type=component_type,
            is_mandatory=is_mandatory,
            is_recurring=is_recurring,
            include_deleted=include_deleted
        )
    
    def get_applicable_components(
        self,
        fee_structure_id: UUID,
        room_types: Optional[List[str]] = None,
        check_date: Optional[Date] = None,
        include_optional: bool = True
    ) -> List[ChargeComponent]:
        """
        Get components applicable to specific criteria.
        
        Args:
            fee_structure_id: Fee structure identifier
            room_types: List of room types to check
            check_date: Date to check applicability
            include_optional: Include non-mandatory components
            
        Returns:
            List of applicable ChargeComponent instances
        """
        return self.component_repo.find_applicable_components(
            fee_structure_id=fee_structure_id,
            room_types=room_types,
            check_date=check_date,
            include_optional=include_optional
        )
    
    # ============================================================
    # Component Calculations
    # ============================================================
    
    def calculate_component_total(
        self,
        fee_structure_id: UUID,
        include_tax: bool = True,
        component_types: Optional[List[str]] = None,
        mandatory_only: bool = False,
        recurring_only: bool = False
    ) -> Decimal:
        """
        Calculate total of components.
        
        Args:
            fee_structure_id: Fee structure identifier
            include_tax: Include tax in calculation
            component_types: Optional component type filter
            mandatory_only: Only mandatory components
            recurring_only: Only recurring components
            
        Returns:
            Total amount
        """
        return self.component_repo.calculate_total_components(
            fee_structure_id=fee_structure_id,
            include_tax=include_tax,
            component_types=component_types,
            mandatory_only=mandatory_only,
            recurring_only=recurring_only
        )
    
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
            Monthly recurring total
        """
        return self.component_repo.calculate_monthly_recurring_total(
            fee_structure_id=fee_structure_id,
            include_tax=include_tax
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
            One-time total
        """
        return self.component_repo.calculate_one_time_total(
            fee_structure_id=fee_structure_id,
            include_tax=include_tax
        )
    
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
        return self.component_repo.get_component_breakdown(
            fee_structure_id=fee_structure_id,
            include_hidden=include_hidden
        )
    
    def get_tax_breakdown(
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
        return self.component_repo.calculate_tax_breakdown(fee_structure_id)
    
    # ============================================================
    # Bulk Operations
    # ============================================================
    
    def bulk_create_components(
        self,
        fee_structure_id: UUID,
        components_data: List[Dict[str, Any]],
        user_id: UUID
    ) -> List[ChargeComponent]:
        """
        Create multiple components in bulk.
        
        Args:
            fee_structure_id: Parent fee structure ID
            components_data: List of component data
            user_id: User creating components
            
        Returns:
            List of created ChargeComponent instances
        """
        logger.info(f"Bulk creating {len(components_data)} components")
        
        audit_context = {
            'user_id': user_id,
            'action': 'bulk_create_components',
            'timestamp': datetime.utcnow()
        }
        
        try:
            components = self.component_repo.bulk_create_components(
                fee_structure_id=fee_structure_id,
                components_data=components_data,
                audit_context=audit_context
            )
            
            self.session.commit()
            
            logger.info(f"Bulk created {len(components)} components successfully")
            return components
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error in bulk create: {str(e)}")
            raise
    
    def bulk_update_amounts(
        self,
        component_ids: List[UUID],
        amount_updates: Dict[UUID, Decimal],
        user_id: UUID
    ) -> int:
        """
        Bulk update amounts for components.
        
        Args:
            component_ids: List of component IDs
            amount_updates: Map of component_id to new amount
            user_id: User performing update
            
        Returns:
            Number of components updated
        """
        audit_context = {
            'user_id': user_id,
            'action': 'bulk_update_amounts',
            'timestamp': datetime.utcnow()
        }
        
        try:
            updated = self.component_repo.bulk_update_amounts(
                component_ids=component_ids,
                amount_updates=amount_updates,
                audit_context=audit_context
            )
            
            self.session.commit()
            
            logger.info(f"Bulk updated {updated} component amounts")
            return updated
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error in bulk update amounts: {str(e)}")
            raise
    
    def reorder_components(
        self,
        fee_structure_id: UUID,
        component_id_order: List[UUID],
        user_id: UUID
    ) -> int:
        """
        Reorder components.
        
        Args:
            fee_structure_id: Fee structure identifier
            component_id_order: Ordered list of component IDs
            user_id: User performing reorder
            
        Returns:
            Number of components reordered
        """
        audit_context = {
            'user_id': user_id,
            'action': 'reorder_components',
            'timestamp': datetime.utcnow()
        }
        
        try:
            reordered = self.component_repo.reorder_components(
                fee_structure_id=fee_structure_id,
                component_id_order=component_id_order,
                audit_context=audit_context
            )
            
            self.session.commit()
            
            logger.info(f"Reordered {reordered} components")
            return reordered
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error reordering components: {str(e)}")
            raise
    
    def clone_components_to_structure(
        self,
        source_fee_structure_id: UUID,
        target_fee_structure_id: UUID,
        user_id: UUID,
        include_rules: bool = False
    ) -> List[ChargeComponent]:
        """
        Clone components from one fee structure to another.
        
        Args:
            source_fee_structure_id: Source fee structure
            target_fee_structure_id: Target fee structure
            user_id: User performing clone
            include_rules: Also clone charge rules
            
        Returns:
            List of cloned ChargeComponent instances
        """
        logger.info(
            f"Cloning components from {source_fee_structure_id} to {target_fee_structure_id}"
        )
        
        audit_context = {
            'user_id': user_id,
            'action': 'clone_components',
            'timestamp': datetime.utcnow()
        }
        
        try:
            cloned = self.component_repo.clone_components_to_structure(
                source_fee_structure_id=source_fee_structure_id,
                target_fee_structure_id=target_fee_structure_id,
                audit_context=audit_context,
                include_rules=include_rules
            )
            
            self.session.commit()
            
            logger.info(f"Cloned {len(cloned)} components successfully")
            return cloned
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error cloning components: {str(e)}")
            raise
    
    # ============================================================
    # Analytics
    # ============================================================
    
    def get_component_statistics(
        self,
        component_type: str,
        fee_structure_ids: Optional[List[UUID]] = None
    ) -> Dict[str, Any]:
        """
        Get statistical information about components.
        
        Args:
            component_type: Component type to analyze
            fee_structure_ids: Optional fee structure filter
            
        Returns:
            Dictionary with statistics
        """
        return self.component_repo.get_component_statistics(
            component_type=component_type,
            fee_structure_ids=fee_structure_ids
        )
    
    def compare_component_costs(
        self,
        component_type: str,
        fee_structure_ids: List[UUID]
    ) -> List[Dict[str, Any]]:
        """
        Compare costs of same component type across fee structures.
        
        Args:
            component_type: Component type to compare
            fee_structure_ids: Fee structures to compare
            
        Returns:
            List of comparison data
        """
        return self.component_repo.compare_component_costs(
            component_type=component_type,
            fee_structure_ids=fee_structure_ids
        )
    
    # ============================================================
    # Validation Helpers
    # ============================================================
    
    def _validate_component_type(self, component_type: str) -> None:
        """Validate component type."""
        valid_types = ['rent', 'deposit', 'mess', 'electricity', 'water', 
                      'maintenance', 'amenity', 'other']
        if component_type not in valid_types:
            raise ValidationException(
                f"Invalid component_type. Must be one of: {', '.join(valid_types)}"
            )
    
    def _validate_calculation_method(
        self,
        calculation_method: str,
        calculation_basis: Optional[str]
    ) -> None:
        """Validate calculation method."""
        valid_methods = ['fixed', 'variable', 'percentage', 'tiered', 'actual']
        if calculation_method not in valid_methods:
            raise ValidationException(
                f"Invalid calculation_method. Must be one of: {', '.join(valid_methods)}"
            )
        
        # Some methods require calculation_basis
        if calculation_method in ['percentage', 'tiered'] and not calculation_basis:
            raise ValidationException(
                f"calculation_basis required for {calculation_method} method"
            )


class ChargeRuleService:
    """
    Charge Rule Service
    
    Manages business rules associated with charge components.
    """
    
    def __init__(self, session: Session):
        """
        Initialize service with database session.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.rule_repo = ChargeRuleRepository(session)
    
    # ============================================================
    # Core Charge Rule Operations
    # ============================================================
    
    def create_charge_rule(
        self,
        charge_component_id: UUID,
        rule_name: str,
        rule_type: str,
        rule_condition: str,
        rule_action: str,
        user_id: UUID,
        priority: int = 0,
        is_active: bool = True
    ) -> ChargeRule:
        """
        Create a new charge rule.
        
        Args:
            charge_component_id: Parent component ID
            rule_name: Name of the rule
            rule_type: Type (discount, surcharge, waiver, proration, conditional)
            rule_condition: Condition expression (JSON or string)
            rule_action: Action expression (JSON or string)
            user_id: User creating the rule
            priority: Rule priority (higher = executed first)
            is_active: Whether rule is active
            
        Returns:
            Created ChargeRule instance
            
        Raises:
            ValidationException: If validation fails
        """
        logger.info(f"Creating charge rule '{rule_name}' for component {charge_component_id}")
        
        self._validate_rule_type(rule_type)
        
        audit_context = {
            'user_id': user_id,
            'action': 'create_charge_rule',
            'timestamp': datetime.utcnow()
        }
        
        try:
            rule = self.rule_repo.create_charge_rule(
                charge_component_id=charge_component_id,
                rule_name=rule_name,
                rule_type=rule_type,
                rule_condition=rule_condition,
                rule_action=rule_action,
                audit_context=audit_context,
                priority=priority,
                is_active=is_active
            )
            
            self.session.commit()
            
            logger.info(f"Charge rule created successfully: {rule.id}")
            return rule
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating charge rule: {str(e)}")
            raise
    
    def update_charge_rule(
        self,
        rule_id: UUID,
        user_id: UUID,
        rule_name: Optional[str] = None,
        rule_type: Optional[str] = None,
        rule_condition: Optional[str] = None,
        rule_action: Optional[str] = None,
        priority: Optional[int] = None,
        is_active: Optional[bool] = None
    ) -> ChargeRule:
        """
        Update existing charge rule.
        
        Args:
            rule_id: Rule identifier
            user_id: User performing update
            (other parameters same as create, all optional)
            
        Returns:
            Updated ChargeRule instance
        """
        update_data = {}
        if rule_name is not None:
            update_data['rule_name'] = rule_name
        if rule_type is not None:
            update_data['rule_type'] = rule_type
        if rule_condition is not None:
            update_data['rule_condition'] = rule_condition
        if rule_action is not None:
            update_data['rule_action'] = rule_action
        if priority is not None:
            update_data['priority'] = priority
        if is_active is not None:
            update_data['is_active'] = is_active
        
        audit_context = {
            'user_id': user_id,
            'action': 'update_charge_rule',
            'timestamp': datetime.utcnow()
        }
        
        try:
            rule = self.rule_repo.update_charge_rule(
                rule_id=rule_id,
                update_data=update_data,
                audit_context=audit_context
            )
            
            self.session.commit()
            return rule
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating charge rule: {str(e)}")
            raise
    
    def activate_rule(self, rule_id: UUID, user_id: UUID) -> ChargeRule:
        """Activate a charge rule."""
        audit_context = {'user_id': user_id, 'timestamp': datetime.utcnow()}
        
        try:
            rule = self.rule_repo.activate_rule(rule_id, audit_context)
            self.session.commit()
            return rule
        except Exception as e:
            self.session.rollback()
            raise
    
    def deactivate_rule(self, rule_id: UUID, user_id: UUID) -> ChargeRule:
        """Deactivate a charge rule."""
        audit_context = {'user_id': user_id, 'timestamp': datetime.utcnow()}
        
        try:
            rule = self.rule_repo.deactivate_rule(rule_id, audit_context)
            self.session.commit()
            return rule
        except Exception as e:
            self.session.rollback()
            raise
    
    # ============================================================
    # Retrieval Operations
    # ============================================================
    
    def get_rules_by_component(
        self,
        charge_component_id: UUID,
        rule_type: Optional[str] = None,
        is_active: Optional[bool] = True
    ) -> List[ChargeRule]:
        """Get rules for a component."""
        return self.rule_repo.find_by_component(
            charge_component_id=charge_component_id,
            rule_type=rule_type,
            is_active=is_active
        )
    
    def get_discount_rules(
        self,
        component_ids: Optional[List[UUID]] = None,
        is_active: bool = True
    ) -> List[ChargeRule]:
        """Get all discount rules."""
        return self.rule_repo.find_discount_rules(
            component_ids=component_ids,
            is_active=is_active
        )
    
    # ============================================================
    # Bulk Operations
    # ============================================================
    
    def bulk_activate_rules(
        self,
        rule_ids: List[UUID],
        user_id: UUID
    ) -> int:
        """Bulk activate rules."""
        audit_context = {'user_id': user_id, 'timestamp': datetime.utcnow()}
        
        try:
            activated = self.rule_repo.bulk_activate_rules(rule_ids, audit_context)
            self.session.commit()
            return activated
        except Exception as e:
            self.session.rollback()
            raise
    
    def bulk_update_priority(
        self,
        priority_updates: Dict[UUID, int],
        user_id: UUID
    ) -> int:
        """Bulk update rule priorities."""
        audit_context = {'user_id': user_id, 'timestamp': datetime.utcnow()}
        
        try:
            updated = self.rule_repo.bulk_update_priority(priority_updates, audit_context)
            self.session.commit()
            return updated
        except Exception as e:
            self.session.rollback()
            raise
    
    # ============================================================
    # Analytics
    # ============================================================
    
    def get_rule_statistics(
        self,
        charge_component_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get rule statistics."""
        return self.rule_repo.get_rule_statistics(charge_component_id)
    
    # ============================================================
    # Validation
    # ============================================================
    
    def _validate_rule_type(self, rule_type: str) -> None:
        """Validate rule type."""
        valid_types = ['discount', 'surcharge', 'waiver', 'proration', 'conditional']
        if rule_type not in valid_types:
            raise ValidationException(
                f"Invalid rule_type. Must be one of: {', '.join(valid_types)}"
            )


class DiscountConfigurationService:
    """
    Discount Configuration Service
    
    Manages discount configurations with validation, usage tracking,
    and applicability checking.
    """
    
    def __init__(self, session: Session):
        """
        Initialize service with database session.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
        self.discount_repo = DiscountConfigurationRepository(session)
    
    # ============================================================
    # Core Discount Operations
    # ============================================================
    
    def create_discount(
        self,
        discount_name: str,
        discount_type: str,
        applies_to: str,
        user_id: UUID,
        discount_code: Optional[str] = None,
        discount_percentage: Optional[Decimal] = None,
        discount_amount: Optional[Decimal] = None,
        hostel_ids: Optional[str] = None,
        room_types: Optional[str] = None,
        minimum_stay_months: Optional[int] = None,
        valid_for_new_students_only: bool = False,
        max_usage_count: Optional[int] = None,
        valid_from: Optional[Date] = None,
        valid_to: Optional[Date] = None,
        is_active: bool = True,
        description: Optional[str] = None,
        terms_and_conditions: Optional[str] = None
    ) -> DiscountConfiguration:
        """
        Create a new discount configuration.
        
        Args:
            discount_name: Name of the discount
            discount_type: Type (percentage, fixed_amount, waiver)
            applies_to: What discount applies to (base_rent, mess_charges, total, security_deposit)
            user_id: User creating the discount
            discount_code: Optional unique discount code
            discount_percentage: Percentage discount (for percentage type)
            discount_amount: Fixed amount discount (for fixed_amount type)
            hostel_ids: Comma-separated hostel IDs or NULL for all
            room_types: Comma-separated room types or NULL for all
            minimum_stay_months: Minimum stay requirement
            valid_for_new_students_only: Only for new students
            max_usage_count: Maximum times discount can be used
            valid_from: Start date of validity
            valid_to: End date of validity
            is_active: Whether discount is active
            description: Discount description
            terms_and_conditions: Terms and conditions
            
        Returns:
            Created DiscountConfiguration instance
            
        Raises:
            ValidationException: If validation fails
            ConflictException: If duplicate code
        """
        logger.info(f"Creating discount '{discount_name}'")
        
        # Validate discount configuration
        self._validate_discount_type(discount_type)
        self._validate_applies_to(applies_to)
        self._validate_discount_value(discount_type, discount_percentage, discount_amount)
        
        audit_context = {
            'user_id': user_id,
            'action': 'create_discount',
            'timestamp': datetime.utcnow()
        }
        
        try:
            discount = self.discount_repo.create_discount(
                discount_name=discount_name,
                discount_type=discount_type,
                applies_to=applies_to,
                audit_context=audit_context,
                discount_code=discount_code,
                discount_percentage=discount_percentage,
                discount_amount=discount_amount,
                hostel_ids=hostel_ids,
                room_types=room_types,
                minimum_stay_months=minimum_stay_months,
                valid_for_new_students_only=valid_for_new_students_only,
                max_usage_count=max_usage_count,
                valid_from=valid_from,
                valid_to=valid_to,
                is_active=is_active,
                description=description,
                terms_and_conditions=terms_and_conditions
            )
            
            self.session.commit()
            
            logger.info(f"Discount created successfully: {discount.id}")
            return discount
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating discount: {str(e)}")
            raise
    
    def update_discount(
        self,
        discount_id: UUID,
        user_id: UUID,
        **kwargs
    ) -> DiscountConfiguration:
        """Update existing discount configuration."""
        audit_context = {
            'user_id': user_id,
            'action': 'update_discount',
            'timestamp': datetime.utcnow()
        }
        
        try:
            discount = self.discount_repo.update_discount(
                discount_id=discount_id,
                update_data=kwargs,
                audit_context=audit_context
            )
            
            self.session.commit()
            return discount
            
        except Exception as e:
            self.session.rollback()
            raise
    
    def activate_discount(self, discount_id: UUID, user_id: UUID) -> DiscountConfiguration:
        """Activate a discount."""
        audit_context = {'user_id': user_id, 'timestamp': datetime.utcnow()}
        
        try:
            discount = self.discount_repo.activate_discount(discount_id, audit_context)
            self.session.commit()
            return discount
        except Exception as e:
            self.session.rollback()
            raise
    
    def deactivate_discount(self, discount_id: UUID, user_id: UUID) -> DiscountConfiguration:
        """Deactivate a discount."""
        audit_context = {'user_id': user_id, 'timestamp': datetime.utcnow()}
        
        try:
            discount = self.discount_repo.deactivate_discount(discount_id, audit_context)
            self.session.commit()
            return discount
        except Exception as e:
            self.session.rollback()
            raise
    
    # ============================================================
    # Discount Retrieval and Search
    # ============================================================
    
    def get_discount(self, discount_id: UUID) -> DiscountConfiguration:
        """Get discount by ID."""
        discount = self.discount_repo.find_by_id(discount_id)
        if not discount:
            raise NotFoundException(f"Discount {discount_id} not found")
        return discount
    
    def find_active_discounts(
        self,
        applies_to: Optional[str] = None,
        hostel_id: Optional[UUID] = None,
        room_type: Optional[str] = None,
        as_of_date: Optional[Date] = None,
        new_students_only: Optional[bool] = None
    ) -> List[DiscountConfiguration]:
        """Find active discounts."""
        return self.discount_repo.find_active_discounts(
            applies_to=applies_to,
            hostel_id=hostel_id,
            room_type=room_type,
            as_of_date=as_of_date,
            new_students_only=new_students_only
        )
    
    def find_by_code(
        self,
        discount_code: str,
        validate_active: bool = True,
        check_date: Optional[Date] = None
    ) -> Optional[DiscountConfiguration]:
        """Find discount by code."""
        return self.discount_repo.find_by_code(
            discount_code=discount_code,
            validate_active=validate_active,
            check_date=check_date
        )
    
    # ============================================================
    # Discount Application and Validation
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
        Validate if discount is applicable.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        return self.discount_repo.validate_discount_applicability(
            discount_id=discount_id,
            hostel_id=hostel_id,
            room_type=room_type,
            is_new_student=is_new_student,
            stay_months=stay_months,
            check_date=check_date
        )
    
    def calculate_discount_amount(
        self,
        discount_id: UUID,
        base_amount: Decimal
    ) -> Decimal:
        """Calculate discount amount."""
        return self.discount_repo.calculate_discount_amount(
            discount_id=discount_id,
            base_amount=base_amount
        )
    
    def get_best_applicable_discount(
        self,
        hostel_id: UUID,
        room_type: str,
        base_amount: Decimal,
        is_new_student: bool = False,
        stay_months: Optional[int] = None,
        check_date: Optional[Date] = None
    ) -> Optional[Tuple[DiscountConfiguration, Decimal]]:
        """Find best applicable discount."""
        return self.discount_repo.get_best_applicable_discount(
            hostel_id=hostel_id,
            room_type=room_type,
            base_amount=base_amount,
            is_new_student=is_new_student,
            stay_months=stay_months,
            check_date=check_date
        )
    
    def apply_discount_code(
        self,
        discount_code: str,
        hostel_id: UUID,
        room_type: str,
        base_amount: Decimal,
        is_new_student: bool = False,
        stay_months: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Apply a discount code and return result.
        
        Returns:
            Dictionary with discount details and amount
            
        Raises:
            NotFoundException: If code not found
            ValidationException: If discount not applicable
        """
        # Find discount by code
        discount = self.find_by_code(discount_code, validate_active=True)
        
        if not discount:
            raise NotFoundException(f"Discount code '{discount_code}' not found or inactive")
        
        # Validate applicability
        is_valid, error_message = self.validate_discount_applicability(
            discount_id=discount.id,
            hostel_id=hostel_id,
            room_type=room_type,
            is_new_student=is_new_student,
            stay_months=stay_months
        )
        
        if not is_valid:
            raise ValidationException(f"Discount not applicable: {error_message}")
        
        # Calculate discount amount
        discount_amount = self.calculate_discount_amount(discount.id, base_amount)
        
        return {
            'discount_id': str(discount.id),
            'discount_name': discount.discount_name,
            'discount_code': discount.discount_code,
            'discount_type': discount.discount_type,
            'applies_to': discount.applies_to,
            'base_amount': float(base_amount),
            'discount_amount': float(discount_amount),
            'final_amount': float(base_amount - discount_amount),
            'discount_percentage': float(discount_amount / base_amount * 100) if base_amount > 0 else 0,
            'description': discount.description,
            'terms_and_conditions': discount.terms_and_conditions
        }
    
    # ============================================================
    # Usage Tracking
    # ============================================================
    
    def increment_usage(self, discount_id: UUID) -> DiscountConfiguration:
        """Increment usage count."""
        try:
            discount = self.discount_repo.increment_usage(discount_id)
            self.session.commit()
            logger.info(f"Incremented usage for discount {discount_id}")
            return discount
        except Exception as e:
            self.session.rollback()
            raise
    
    def decrement_usage(self, discount_id: UUID) -> DiscountConfiguration:
        """Decrement usage count (e.g., on cancellation)."""
        try:
            discount = self.discount_repo.decrement_usage(discount_id)
            self.session.commit()
            logger.info(f"Decremented usage for discount {discount_id}")
            return discount
        except Exception as e:
            self.session.rollback()
            raise
    
    def get_usage_statistics(self, discount_id: UUID) -> Dict[str, Any]:
        """Get usage statistics for a discount."""
        return self.discount_repo.get_usage_statistics(discount_id)
    
    # ============================================================
    # Analytics
    # ============================================================
    
    def get_discount_analytics(
        self,
        start_date: Optional[Date] = None,
        end_date: Optional[Date] = None,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get discount analytics."""
        return self.discount_repo.get_discount_analytics(
            start_date=start_date,
            end_date=end_date,
            hostel_id=hostel_id
        )
    
    def get_discount_performance(self, discount_id: UUID) -> Dict[str, Any]:
        """Get performance metrics for a discount."""
        return self.discount_repo.get_discount_performance(discount_id)
    
    def compare_discount_effectiveness(
        self,
        discount_ids: List[UUID]
    ) -> List[Dict[str, Any]]:
        """Compare effectiveness of multiple discounts."""
        return self.discount_repo.compare_discount_effectiveness(discount_ids)
    
    # ============================================================
    # Bulk Operations
    # ============================================================
    
    def expire_discounts(
        self,
        expiry_date: Optional[Date] = None,
        user_id: Optional[UUID] = None
    ) -> int:
        """Expire discounts past their valid_to date."""
        audit_context = None
        if user_id:
            audit_context = {'user_id': user_id, 'timestamp': datetime.utcnow()}
        
        try:
            expired = self.discount_repo.expire_discounts(
                expiry_date=expiry_date,
                audit_context=audit_context
            )
            self.session.commit()
            logger.info(f"Expired {expired} discounts")
            return expired
        except Exception as e:
            self.session.rollback()
            raise
    
    # ============================================================
    # Validation Helpers
    # ============================================================
    
    def _validate_discount_type(self, discount_type: str) -> None:
        """Validate discount type."""
        valid_types = ['percentage', 'fixed_amount', 'waiver']
        if discount_type not in valid_types:
            raise ValidationException(
                f"Invalid discount_type. Must be one of: {', '.join(valid_types)}"
            )
    
    def _validate_applies_to(self, applies_to: str) -> None:
        """Validate applies_to field."""
        valid_applies = ['base_rent', 'mess_charges', 'total', 'security_deposit']
        if applies_to not in valid_applies:
            raise ValidationException(
                f"Invalid applies_to. Must be one of: {', '.join(valid_applies)}"
            )
    
    def _validate_discount_value(
        self,
        discount_type: str,
        discount_percentage: Optional[Decimal],
        discount_amount: Optional[Decimal]
    ) -> None:
        """Validate discount value based on type."""
        if discount_type == 'percentage':
            if not discount_percentage:
                raise ValidationException(
                    "discount_percentage required for percentage type"
                )
            if discount_percentage < Decimal('0') or discount_percentage > Decimal('100'):
                raise ValidationException(
                    "discount_percentage must be between 0 and 100"
                )
            if discount_amount:
                raise ValidationException(
                    "Cannot specify both discount_percentage and discount_amount"
                )
        
        elif discount_type == 'fixed_amount':
            if not discount_amount:
                raise ValidationException(
                    "discount_amount required for fixed_amount type"
                )
            if discount_amount < Decimal('0'):
                raise ValidationException("discount_amount cannot be negative")
            if discount_percentage:
                raise ValidationException(
                    "Cannot specify both discount_percentage and discount_amount"
                )