# validation_service.py

from typing import Dict, List, Any, Optional, Type, Union, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod
import re
from datetime import datetime
import logging

@dataclass
class ValidationContext:
    """Context for validation execution"""
    entity_type: str
    entity_id: Optional[str]
    operation: str
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    user_id: Optional[str] = None

    @classmethod
    def create(
        cls,
        entity_type: str,
        data: Dict[str, Any],
        operation: str = "validate"
    ) -> 'ValidationContext':
        return cls(
            entity_type=entity_type,
            entity_id=None,
            operation=operation,
            data=data,
            metadata={}
        )

@dataclass
class ValidationResult:
    """Result of validation execution"""
    is_valid: bool
    errors: Dict[str, List[str]]
    warnings: Dict[str, List[str]]
    metadata: Dict[str, Any]

    @classmethod
    def success(cls) -> 'ValidationResult':
        return cls(
            is_valid=True,
            errors={},
            warnings={},
            metadata={}
        )

    @classmethod
    def failure(
        cls,
        errors: Dict[str, List[str]]
    ) -> 'ValidationResult':
        return cls(
            is_valid=False,
            errors=errors,
            warnings={},
            metadata={}
        )

    def add_error(self, field: str, message: str) -> None:
        """Add an error message"""
        if field not in self.errors:
            self.errors[field] = []
        self.errors[field].append(message)
        self.is_valid = False

    def add_warning(self, field: str, message: str) -> None:
        """Add a warning message"""
        if field not in self.warnings:
            self.warnings[field] = []
        self.warnings[field].append(message)

class ValidationRule(ABC):
    """Abstract base class for validation rules"""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def validate(
        self,
        value: Any,
        context: ValidationContext
    ) -> ValidationResult:
        """Validate a value"""
        pass

class RequiredFieldRule(ValidationRule):
    """Validates required fields"""

    async def validate(
        self,
        value: Any,
        context: ValidationContext
    ) -> ValidationResult:
        result = ValidationResult.success()
        if value is None or (isinstance(value, str) and not value.strip()):
            result.add_error(self.field, self.message or f"{self.field} is required")
        return result

class StringLengthRule(ValidationRule):
    """Validates string length"""

    def __init__(
        self,
        field: str,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        message: Optional[str] = None
    ):
        super().__init__(field, message or "Invalid string length")
        self.min_length = min_length
        self.max_length = max_length

    async def validate(
        self,
        value: Any,
        context: ValidationContext
    ) -> ValidationResult:
        result = ValidationResult.success()
        if not isinstance(value, str):
            result.add_error(self.field, f"{self.field} must be a string")
            return result

        if self.min_length and len(value) < self.min_length:
            result.add_error(
                self.field,
                f"{self.field} must be at least {self.min_length} characters"
            )

        if self.max_length and len(value) > self.max_length:
            result.add_error(
                self.field,
                f"{self.field} must be at most {self.max_length} characters"
            )

        return result

class RegexRule(ValidationRule):
    """Validates string pattern"""

    def __init__(
        self,
        field: str,
        pattern: str,
        message: Optional[str] = None
    ):
        super().__init__(field, message or f"Invalid format for {field}")
        self.pattern = re.compile(pattern)

    async def validate(
        self,
        value: Any,
        context: ValidationContext
    ) -> ValidationResult:
        result = ValidationResult.success()
        if not isinstance(value, str) or not self.pattern.match(value):
            result.add_error(self.field, self.message)
        return result

class RangeRule(ValidationRule):
    """Validates numeric range"""

    def __init__(
        self,
        field: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        message: Optional[str] = None
    ):
        super().__init__(field, message or "Value out of range")
        self.min_value = min_value
        self.max_value = max_value

    async def validate(
        self,
        value: Any,
        context: ValidationContext
    ) -> ValidationResult:
        result = ValidationResult.success()
        if not isinstance(value, (int, float)):
            result.add_error(self.field, f"{self.field} must be a number")
            return result

        if self.min_value is not None and value < self.min_value:
            result.add_error(
                self.field,
                f"{self.field} must be at least {self.min_value}"
            )

        if self.max_value is not None and value > self.max_value:
            result.add_error(
                self.field,
                f"{self.field} must be at most {self.max_value}"
            )

        return result

class CompositeValidator:
    """Combines multiple validation rules"""

    def __init__(self, rules: List[ValidationRule]):
        self.rules = rules
        self.logger = logging.getLogger(self.__class__.__name__)

    async def validate(
        self,
        data: Dict[str, Any],
        context: ValidationContext
    ) -> ValidationResult:
        """Validate data against all rules"""
        final_result = ValidationResult.success()

        for rule in self.rules:
            value = data.get(rule.field)
            result = await rule.validate(value, context)
            
            # Merge results
            for field, errors in result.errors.items():
                for error in errors:
                    final_result.add_error(field, error)
            
            for field, warnings in result.warnings.items():
                for warning in warnings:
                    final_result.add_warning(field, warning)

        return final_result

class ValidationChain:
    """Chains multiple validators in sequence"""

    def __init__(self):
        self.validators: List[CompositeValidator] = []
        self.logger = logging.getLogger(self.__class__.__name__)

    def add_validator(
        self,
        validator: CompositeValidator
    ) -> 'ValidationChain':
        """Add a validator to the chain"""
        self.validators.append(validator)
        return self

    async def validate(
        self,
        data: Dict[str, Any],
        context: ValidationContext
    ) -> ValidationResult:
        """Execute validation chain"""
        final_result = ValidationResult.success()

        for validator in self.validators:
            result = await validator.validate(data, context)
            
            # Stop on first failure if configured
            if not result.is_valid:
                return result

            # Merge results
            for field, errors in result.errors.items():
                for error in errors:
                    final_result.add_error(field, error)
            
            for field, warnings in result.warnings.items():
                for warning in warnings:
                    final_result.add_warning(field, warning)

        return final_result

class ValidationService:
    """Main validation service interface"""

    def __init__(self):
        self._validators: Dict[str, ValidationChain] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_validator(
        self,
        entity_type: str,
        validator: ValidationChain
    ) -> None:
        """Register a validator for an entity type"""
        self._validators[entity_type] = validator
        self.logger.info(f"Registered validator for {entity_type}")

    async def validate(
        self,
        entity_type: str,
        data: Dict[str, Any],
        operation: str = "validate"
    ) -> ValidationResult:
        """Validate data for an entity type"""
        validator = self._validators.get(entity_type)
        if not validator:
            self.logger.warning(f"No validator found for {entity_type}")
            return ValidationResult.success()

        context = ValidationContext.create(
            entity_type=entity_type,
            data=data,
            operation=operation
        )

        try:
            result = await validator.validate(data, context)
            self.logger.info(
                f"Validation completed for {entity_type}: "
                f"{'success' if result.is_valid else 'failure'}"
            )
            return result
        except Exception as e:
            self.logger.error(f"Validation error for {entity_type}: {str(e)}")
            return ValidationResult.failure(
                {"_general": [f"Validation error: {str(e)}"]}
            )

    def create_validator(
        self,
        rules: List[ValidationRule]
    ) -> CompositeValidator:
        """Create a composite validator from rules"""
        return CompositeValidator(rules)

    def create_chain(self) -> ValidationChain:
        """Create a new validation chain"""
        return ValidationChain()