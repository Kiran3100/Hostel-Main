"""
Charge Component Service

Manages charge components, rules, and discount configurations for fee structures.
Provides comprehensive CRUD operations with validation and business logic.

Components:
- Charge Components: Individual fee items (e.g., room rent, utilities)
- Charge Rules: Calculation rules for components (e.g., per day, per month)
- Discount Configurations: Discount rules and conditions

Author: Senior Prompt Engineer
Version: 2.0.0
"""

from typing import Optional, List, Tuple
from uuid import UUID
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.fee_structure import ChargeComponentRepository
from app.models.fee_structure.charge_component import (
    ChargeComponent as ChargeComponentModel,
    ChargeRule as ChargeRuleModel,
    DiscountConfiguration as DiscountConfigurationModel,
)
from app.schemas.fee_structure.charge_component import (
    ChargeComponentCreate,
    ChargeComponentUpdate,
    ChargeRuleCreate,
    ChargeRuleUpdate,
    DiscountConfigurationCreate,
    DiscountConfigurationUpdate,
)
from app.core1.logging import get_logger


class ChargeComponentService(BaseService[ChargeComponentModel, ChargeComponentRepository]):
    """
    Service for managing charge components and related entities.
    
    Handles:
    - Charge component lifecycle (CRUD)
    - Charge rule management
    - Discount configuration management
    - Validation and business logic enforcement
    """

    # Valid component types
    VALID_COMPONENT_TYPES = {
        "room_rent",
        "utilities",
        "maintenance",
        "security_deposit",
        "admission_fee",
        "laundry",
        "food",
        "other"
    }

    # Valid calculation methods for rules
    VALID_CALCULATION_METHODS = {
        "fixed",
        "per_day",
        "per_month",
        "percentage",
        "tiered"
    }

    # Valid discount types
    VALID_DISCOUNT_TYPES = {
        "percentage",
        "fixed_amount",
        "conditional"
    }

    def __init__(self, repository: ChargeComponentRepository, db_session: Session):
        """
        Initialize charge component service.

        Args:
            repository: Charge component repository instance
            db_session: SQLAlchemy database session
        """
        super().__init__(repository, db_session)
        self._logger = get_logger(self.__class__.__name__)

    # ==================== Charge Component Operations ====================

    def create_component(
        self,
        request: ChargeComponentCreate,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[ChargeComponentModel]:
        """
        Create a new charge component with validation.

        Args:
            request: Component creation request
            created_by: UUID of user creating the component

        Returns:
            ServiceResult containing created component or error
        """
        try:
            # Validate component data
            validation_result = self._validate_component_data(request)
            if not validation_result.success:
                return validation_result

            # Check for duplicate components in same structure
            if self._component_exists(request.structure_id, request.name):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.DUPLICATE_ENTRY,
                        message=f"Component '{request.name}' already exists in this structure",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "structure_id": str(request.structure_id),
                            "component_name": request.name
                        }
                    )
                )

            component = self.repository.create_component(request, created_by=created_by)
            self.db.commit()
            self.db.refresh(component)

            self._logger.info(
                "Charge component created",
                extra={
                    "component_id": str(component.id),
                    "structure_id": str(request.structure_id),
                    "name": request.name,
                    "created_by": str(created_by) if created_by else None,
                }
            )

            return ServiceResult.success(
                component,
                message="Charge component created successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            self._logger.error(
                "Database integrity error creating component",
                exc_info=True,
                extra={"error": str(e)}
            )
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DUPLICATE_ENTRY,
                    message="Component violates database constraints",
                    severity=ErrorSeverity.ERROR,
                    details={"database_error": str(e)}
                )
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "create charge component")

    def update_component(
        self,
        component_id: UUID,
        request: ChargeComponentUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[ChargeComponentModel]:
        """
        Update an existing charge component.

        Args:
            component_id: UUID of component to update
            request: Update request data
            updated_by: UUID of user performing update

        Returns:
            ServiceResult containing updated component or error
        """
        try:
            # Verify component exists
            existing = self.repository.get_by_id(component_id)
            if not existing:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Charge component not found: {component_id}",
                        severity=ErrorSeverity.ERROR,
                        details={"component_id": str(component_id)}
                    )
                )

            # Validate update data
            if request.amount is not None and request.amount < 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Component amount cannot be negative",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            component = self.repository.update_component(
                component_id,
                request,
                updated_by=updated_by
            )
            self.db.commit()
            self.db.refresh(component)

            self._logger.info(
                "Charge component updated",
                extra={
                    "component_id": str(component_id),
                    "updated_by": str(updated_by) if updated_by else None,
                }
            )

            return ServiceResult.success(
                component,
                message="Charge component updated successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DUPLICATE_ENTRY,
                    message="Update violates database constraints",
                    severity=ErrorSeverity.ERROR,
                    details={"database_error": str(e)}
                )
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update charge component", component_id)

    def delete_component(
        self,
        component_id: UUID,
        force: bool = False,
    ) -> ServiceResult[bool]:
        """
        Delete a charge component.

        Args:
            component_id: UUID of component to delete
            force: If True, delete even if component has dependencies

        Returns:
            ServiceResult indicating success or failure
        """
        try:
            # Check if component exists
            existing = self.repository.get_by_id(component_id)
            if not existing:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Charge component not found: {component_id}",
                        severity=ErrorSeverity.ERROR,
                        details={"component_id": str(component_id)}
                    )
                )

            # Check for dependencies unless force delete
            if not force and self._component_has_dependencies(component_id):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.INVALID_STATE,
                        message="Cannot delete component with active dependencies",
                        severity=ErrorSeverity.WARNING,
                        details={
                            "component_id": str(component_id),
                            "suggestion": "Use force=True to override or remove dependencies first"
                        }
                    )
                )

            self.repository.delete_component(component_id)
            self.db.commit()

            self._logger.info(
                "Charge component deleted",
                extra={
                    "component_id": str(component_id),
                    "force": force,
                }
            )

            return ServiceResult.success(
                True,
                message="Charge component deleted successfully"
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "delete charge component", component_id)

    def list_components(
        self,
        structure_id: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        room_type: Optional[str] = None,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 50,
    ) -> ServiceResult[Tuple[List[ChargeComponentModel], int]]:
        """
        List charge components with filtering.

        Args:
            structure_id: Filter by fee structure
            hostel_id: Filter by hostel
            room_type: Filter by room type
            active_only: If True, return only active components
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            ServiceResult containing list of components and total count
        """
        try:
            # Validate pagination
            page = max(1, page)
            page_size = min(max(1, page_size), 100)

            components = self.repository.list_components(
                structure_id=structure_id,
                hostel_id=hostel_id,
                room_type=room_type,
                active_only=active_only,
                page=page,
                page_size=page_size,
            )

            total_count = len(components)
            total_pages = (total_count + page_size - 1) // page_size

            return ServiceResult.success(
                (components, total_count),
                metadata={
                    "count": len(components),
                    "total": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                }
            )

        except Exception as e:
            return self._handle_exception(e, "list charge components")

    # ==================== Charge Rule Operations ====================

    def create_rule(
        self,
        request: ChargeRuleCreate,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[ChargeRuleModel]:
        """
        Create a new charge rule.

        Args:
            request: Rule creation request
            created_by: UUID of user creating the rule

        Returns:
            ServiceResult containing created rule or error
        """
        try:
            # Validate rule data
            validation_result = self._validate_rule_data(request)
            if not validation_result.success:
                return validation_result

            rule = self.repository.create_rule(request, created_by=created_by)
            self.db.commit()
            self.db.refresh(rule)

            self._logger.info(
                "Charge rule created",
                extra={
                    "rule_id": str(rule.id),
                    "component_id": str(request.component_id),
                    "created_by": str(created_by) if created_by else None,
                }
            )

            return ServiceResult.success(
                rule,
                message="Charge rule created successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DUPLICATE_ENTRY,
                    message="Rule violates database constraints",
                    severity=ErrorSeverity.ERROR,
                    details={"database_error": str(e)}
                )
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "create charge rule")

    def update_rule(
        self,
        rule_id: UUID,
        request: ChargeRuleUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[ChargeRuleModel]:
        """
        Update an existing charge rule.

        Args:
            rule_id: UUID of rule to update
            request: Update request data
            updated_by: UUID of user performing update

        Returns:
            ServiceResult containing updated rule or error
        """
        try:
            # Verify rule exists
            existing = self.repository.get_rule_by_id(rule_id)
            if not existing:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Charge rule not found: {rule_id}",
                        severity=ErrorSeverity.ERROR,
                        details={"rule_id": str(rule_id)}
                    )
                )

            rule = self.repository.update_rule(rule_id, request, updated_by=updated_by)
            self.db.commit()
            self.db.refresh(rule)

            self._logger.info(
                "Charge rule updated",
                extra={
                    "rule_id": str(rule_id),
                    "updated_by": str(updated_by) if updated_by else None,
                }
            )

            return ServiceResult.success(
                rule,
                message="Charge rule updated successfully"
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update charge rule", rule_id)

    def delete_rule(
        self,
        rule_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Delete a charge rule.

        Args:
            rule_id: UUID of rule to delete

        Returns:
            ServiceResult indicating success or failure
        """
        try:
            existing = self.repository.get_rule_by_id(rule_id)
            if not existing:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Charge rule not found: {rule_id}",
                        severity=ErrorSeverity.ERROR,
                        details={"rule_id": str(rule_id)}
                    )
                )

            self.repository.delete_rule(rule_id)
            self.db.commit()

            self._logger.info(
                "Charge rule deleted",
                extra={"rule_id": str(rule_id)}
            )

            return ServiceResult.success(
                True,
                message="Charge rule deleted successfully"
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "delete charge rule", rule_id)

    def list_rules(
        self,
        component_id: Optional[UUID] = None,
        structure_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> ServiceResult[Tuple[List[ChargeRuleModel], int]]:
        """
        List charge rules with filtering.

        Args:
            component_id: Filter by component
            structure_id: Filter by fee structure
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            ServiceResult containing list of rules and total count
        """
        try:
            page = max(1, page)
            page_size = min(max(1, page_size), 100)

            rules = self.repository.list_rules(
                component_id=component_id,
                structure_id=structure_id,
                page=page,
                page_size=page_size,
            )

            total_count = len(rules)
            total_pages = (total_count + page_size - 1) // page_size

            return ServiceResult.success(
                (rules, total_count),
                metadata={
                    "count": len(rules),
                    "total": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                }
            )

        except Exception as e:
            return self._handle_exception(e, "list charge rules")

    # ==================== Discount Configuration Operations ====================

    def create_discount(
        self,
        request: DiscountConfigurationCreate,
        created_by: Optional[UUID] = None,
    ) -> ServiceResult[DiscountConfigurationModel]:
        """
        Create a new discount configuration.

        Args:
            request: Discount creation request
            created_by: UUID of user creating the discount

        Returns:
            ServiceResult containing created discount or error
        """
        try:
            # Validate discount data
            validation_result = self._validate_discount_data(request)
            if not validation_result.success:
                return validation_result

            discount = self.repository.create_discount_config(request, created_by=created_by)
            self.db.commit()
            self.db.refresh(discount)

            self._logger.info(
                "Discount configuration created",
                extra={
                    "discount_id": str(discount.id),
                    "structure_id": str(request.structure_id) if hasattr(request, 'structure_id') else None,
                    "created_by": str(created_by) if created_by else None,
                }
            )

            return ServiceResult.success(
                discount,
                message="Discount configuration created successfully"
            )

        except IntegrityError as e:
            self.db.rollback()
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.DUPLICATE_ENTRY,
                    message="Discount violates database constraints",
                    severity=ErrorSeverity.ERROR,
                    details={"database_error": str(e)}
                )
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "create discount configuration")

    def update_discount(
        self,
        discount_id: UUID,
        request: DiscountConfigurationUpdate,
        updated_by: Optional[UUID] = None,
    ) -> ServiceResult[DiscountConfigurationModel]:
        """
        Update an existing discount configuration.

        Args:
            discount_id: UUID of discount to update
            request: Update request data
            updated_by: UUID of user performing update

        Returns:
            ServiceResult containing updated discount or error
        """
        try:
            existing = self.repository.get_discount_by_id(discount_id)
            if not existing:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Discount configuration not found: {discount_id}",
                        severity=ErrorSeverity.ERROR,
                        details={"discount_id": str(discount_id)}
                    )
                )

            discount = self.repository.update_discount_config(
                discount_id,
                request,
                updated_by=updated_by
            )
            self.db.commit()
            self.db.refresh(discount)

            self._logger.info(
                "Discount configuration updated",
                extra={
                    "discount_id": str(discount_id),
                    "updated_by": str(updated_by) if updated_by else None,
                }
            )

            return ServiceResult.success(
                discount,
                message="Discount configuration updated successfully"
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "update discount configuration", discount_id)

    def delete_discount(
        self,
        discount_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Delete a discount configuration.

        Args:
            discount_id: UUID of discount to delete

        Returns:
            ServiceResult indicating success or failure
        """
        try:
            existing = self.repository.get_discount_by_id(discount_id)
            if not existing:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message=f"Discount configuration not found: {discount_id}",
                        severity=ErrorSeverity.ERROR,
                        details={"discount_id": str(discount_id)}
                    )
                )

            self.repository.delete_discount_config(discount_id)
            self.db.commit()

            self._logger.info(
                "Discount configuration deleted",
                extra={"discount_id": str(discount_id)}
            )

            return ServiceResult.success(
                True,
                message="Discount configuration deleted successfully"
            )

        except Exception as e:
            self.db.rollback()
            return self._handle_exception(e, "delete discount configuration", discount_id)

    def list_discounts(
        self,
        structure_id: Optional[UUID] = None,
        component_id: Optional[UUID] = None,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 50,
    ) -> ServiceResult[Tuple[List[DiscountConfigurationModel], int]]:
        """
        List discount configurations with filtering.

        Args:
            structure_id: Filter by fee structure
            component_id: Filter by component
            active_only: If True, return only active discounts
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            ServiceResult containing list of discounts and total count
        """
        try:
            page = max(1, page)
            page_size = min(max(1, page_size), 100)

            discounts = self.repository.list_discounts(
                structure_id=structure_id,
                component_id=component_id,
                active_only=active_only,
                page=page,
                page_size=page_size,
            )

            total_count = len(discounts)
            total_pages = (total_count + page_size - 1) // page_size

            return ServiceResult.success(
                (discounts, total_count),
                metadata={
                    "count": len(discounts),
                    "total": total_count,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                }
            )

        except Exception as e:
            return self._handle_exception(e, "list discount configurations")

    # ==================== Private Helper Methods ====================

    def _validate_component_data(
        self,
        request: ChargeComponentCreate,
    ) -> ServiceResult[None]:
        """Validate charge component creation data."""
        # Validate component type
        if hasattr(request, 'component_type') and request.component_type:
            if request.component_type not in self.VALID_COMPONENT_TYPES:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid component type: {request.component_type}",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "provided": request.component_type,
                            "valid_types": list(self.VALID_COMPONENT_TYPES)
                        }
                    )
                )

        # Validate amount
        if hasattr(request, 'amount') and request.amount is not None:
            if request.amount < 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Component amount cannot be negative",
                        severity=ErrorSeverity.ERROR,
                    )
                )

        # Validate name
        if not request.name or not request.name.strip():
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Component name is required",
                    severity=ErrorSeverity.ERROR,
                )
            )

        return ServiceResult.success(None)

    def _validate_rule_data(
        self,
        request: ChargeRuleCreate,
    ) -> ServiceResult[None]:
        """Validate charge rule creation data."""
        # Validate calculation method
        if hasattr(request, 'calculation_method') and request.calculation_method:
            if request.calculation_method not in self.VALID_CALCULATION_METHODS:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid calculation method: {request.calculation_method}",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "provided": request.calculation_method,
                            "valid_methods": list(self.VALID_CALCULATION_METHODS)
                        }
                    )
                )

        return ServiceResult.success(None)

    def _validate_discount_data(
        self,
        request: DiscountConfigurationCreate,
    ) -> ServiceResult[None]:
        """Validate discount configuration creation data."""
        # Validate discount type
        if hasattr(request, 'discount_type') and request.discount_type:
            if request.discount_type not in self.VALID_DISCOUNT_TYPES:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Invalid discount type: {request.discount_type}",
                        severity=ErrorSeverity.ERROR,
                        details={
                            "provided": request.discount_type,
                            "valid_types": list(self.VALID_DISCOUNT_TYPES)
                        }
                    )
                )

        # Validate discount value
        if hasattr(request, 'discount_value') and request.discount_value is not None:
            if request.discount_value < 0:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Discount value cannot be negative",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            # For percentage discounts, validate range
            if hasattr(request, 'discount_type') and request.discount_type == 'percentage':
                if request.discount_value > 100:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message="Percentage discount cannot exceed 100%",
                            severity=ErrorSeverity.ERROR,
                            details={"provided_value": request.discount_value}
                        )
                    )

        return ServiceResult.success(None)

    def _component_exists(
        self,
        structure_id: UUID,
        component_name: str,
    ) -> bool:
        """Check if a component with the same name exists in the structure."""
        # This should query the repository
        # Placeholder implementation
        return False

    def _component_has_dependencies(self, component_id: UUID) -> bool:
        """Check if component has active dependencies."""
        # Check for:
        # - Active rules using this component
        # - Active calculations using this component
        # Placeholder implementation
        return False