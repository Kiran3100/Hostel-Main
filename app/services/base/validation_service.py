"""
Comprehensive validation service for business rules and data validation.
"""

from typing import Any, Dict, List, Optional, Callable, Union
from datetime import date, datetime
from uuid import UUID
import re
from decimal import Decimal

from app.services.base.service_result import ServiceResult, ServiceError, ErrorCode, ErrorSeverity


class ValidationRule:
    """Base class for validation rules."""
    
    def __init__(self, error_message: Optional[str] = None):
        """
        Initialize validation rule.
        
        Args:
            error_message: Custom error message
        """
        self.error_message = error_message
    
    def validate(self, value: Any, field: str) -> Optional[ServiceResult]:
        """
        Validate a value.
        
        Args:
            value: Value to validate
            field: Field name
            
        Returns:
            ServiceResult with failure if invalid, None if valid
        """
        raise NotImplementedError


class ValidationService:
    """
    Comprehensive validation service with:
    - Field-level validation
    - Cross-field validation
    - Custom validation rules
    - Batch validation
    - Validation result aggregation
    """

    # -------------------------------------------------------------------------
    # Required Field Validation
    # -------------------------------------------------------------------------

    @staticmethod
    def require(
        value: Any,
        field: str,
        message: Optional[str] = None
    ) -> Optional[ServiceResult]:
        """
        Validate that a field has a value.
        
        Args:
            value: Value to check
            field: Field name
            message: Custom error message
            
        Returns:
            ServiceResult with failure if invalid, None if valid
        """
        is_empty = (
            value is None or
            (isinstance(value, str) and value.strip() == "") or
            (isinstance(value, (list, dict)) and len(value) == 0)
        )
        
        if is_empty:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.MISSING_REQUIRED_FIELD,
                    message=message or f"Field '{field}' is required",
                    severity=ErrorSeverity.WARNING,
                    field=field,
                )
            )
        return None

    @staticmethod
    def require_all(
        data: Dict[str, Any],
        required_fields: List[str],
    ) -> Optional[ServiceResult]:
        """
        Validate that all required fields are present.
        
        Args:
            data: Data dictionary to validate
            required_fields: List of required field names
            
        Returns:
            ServiceResult with failure if any required field is missing
        """
        missing_fields = []
        
        for field in required_fields:
            if ValidationService.require(data.get(field), field):
                missing_fields.append(field)
        
        if missing_fields:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.MISSING_REQUIRED_FIELD,
                    message=f"Required fields missing: {', '.join(missing_fields)}",
                    severity=ErrorSeverity.WARNING,
                    details={"missing_fields": missing_fields},
                )
            )
        return None

    # -------------------------------------------------------------------------
    # Type Validation
    # -------------------------------------------------------------------------

    @staticmethod
    def validate_type(
        value: Any,
        expected_type: type,
        field: str,
    ) -> Optional[ServiceResult]:
        """
        Validate value type.
        
        Args:
            value: Value to validate
            expected_type: Expected Python type
            field: Field name
            
        Returns:
            ServiceResult with failure if type mismatch
        """
        if value is not None and not isinstance(value, expected_type):
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Field '{field}' must be of type {expected_type.__name__}",
                    severity=ErrorSeverity.WARNING,
                    field=field,
                    details={
                        "expected_type": expected_type.__name__,
                        "actual_type": type(value).__name__,
                    }
                )
            )
        return None

    # -------------------------------------------------------------------------
    # Numeric Validation
    # -------------------------------------------------------------------------

    @staticmethod
    def ensure_positive_number(
        value: Any,
        field: str,
        allow_zero: bool = False,
    ) -> Optional[ServiceResult]:
        """
        Validate that a value is a positive number.
        
        Args:
            value: Value to validate
            field: Field name
            allow_zero: Whether to allow zero
            
        Returns:
            ServiceResult with failure if invalid
        """
        try:
            num = float(value)
            is_valid = num > 0 if not allow_zero else num >= 0
            
            if not is_valid:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=f"Field '{field}' must be a positive number" +
                                (" or zero" if allow_zero else ""),
                        severity=ErrorSeverity.WARNING,
                        field=field,
                    )
                )
        except (TypeError, ValueError):
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Field '{field}' must be a valid number",
                    severity=ErrorSeverity.WARNING,
                    field=field,
                )
            )
        return None

    @staticmethod
    def validate_range(
        value: Union[int, float, Decimal],
        field: str,
        min_value: Optional[Union[int, float, Decimal]] = None,
        max_value: Optional[Union[int, float, Decimal]] = None,
        inclusive: bool = True,
    ) -> Optional[ServiceResult]:
        """
        Validate that a value is within a range.
        
        Args:
            value: Value to validate
            field: Field name
            min_value: Minimum allowed value
            max_value: Maximum allowed value
            inclusive: Whether range is inclusive
            
        Returns:
            ServiceResult with failure if out of range
        """
        try:
            num = float(value)
            
            if min_value is not None:
                if inclusive and num < min_value:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"Field '{field}' must be >= {min_value}",
                            severity=ErrorSeverity.WARNING,
                            field=field,
                        )
                    )
                elif not inclusive and num <= min_value:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"Field '{field}' must be > {min_value}",
                            severity=ErrorSeverity.WARNING,
                            field=field,
                        )
                    )
            
            if max_value is not None:
                if inclusive and num > max_value:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"Field '{field}' must be <= {max_value}",
                            severity=ErrorSeverity.WARNING,
                            field=field,
                        )
                    )
                elif not inclusive and num >= max_value:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=f"Field '{field}' must be < {max_value}",
                            severity=ErrorSeverity.WARNING,
                            field=field,
                        )
                    )
                    
        except (TypeError, ValueError):
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Field '{field}' must be a valid number",
                    severity=ErrorSeverity.WARNING,
                    field=field,
                )
            )
        return None

    # -------------------------------------------------------------------------
    # Date/Time Validation
    # -------------------------------------------------------------------------

    @staticmethod
    def validate_date_range(
        start: Union[date, datetime],
        end: Union[date, datetime],
        allow_equal: bool = True,
        start_field: str = "start_date",
        end_field: str = "end_date",
    ) -> Optional[ServiceResult]:
        """
        Validate date range.
        
        Args:
            start: Start date/datetime
            end: End date/datetime
            allow_equal: Whether start can equal end
            start_field: Name of start field
            end_field: Name of end field
            
        Returns:
            ServiceResult with failure if invalid range
        """
        if start is None or end is None:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Start and end dates are required",
                    severity=ErrorSeverity.WARNING,
                )
            )
        
        if allow_equal and start > end:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"'{start_field}' must be on or before '{end_field}'",
                    severity=ErrorSeverity.WARNING,
                    details={
                        "start": str(start),
                        "end": str(end),
                    }
                )
            )
        
        if not allow_equal and start >= end:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"'{start_field}' must be before '{end_field}'",
                    severity=ErrorSeverity.WARNING,
                    details={
                        "start": str(start),
                        "end": str(end),
                    }
                )
            )
        
        return None

    @staticmethod
    def validate_future_date(
        date_value: Union[date, datetime],
        field: str,
        allow_today: bool = True,
    ) -> Optional[ServiceResult]:
        """
        Validate that a date is in the future.
        
        Args:
            date_value: Date to validate
            field: Field name
            allow_today: Whether to allow today's date
            
        Returns:
            ServiceResult with failure if not future date
        """
        today = datetime.now().date() if isinstance(date_value, date) else datetime.now()
        
        if allow_today and date_value < today:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Field '{field}' must be today or in the future",
                    severity=ErrorSeverity.WARNING,
                    field=field,
                )
            )
        elif not allow_today and date_value <= today:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Field '{field}' must be in the future",
                    severity=ErrorSeverity.WARNING,
                    field=field,
                )
            )
        
        return None

    # -------------------------------------------------------------------------
    # String Validation
    # -------------------------------------------------------------------------

    @staticmethod
    def validate_length(
        value: str,
        field: str,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
    ) -> Optional[ServiceResult]:
        """
        Validate string length.
        
        Args:
            value: String to validate
            field: Field name
            min_length: Minimum length
            max_length: Maximum length
            
        Returns:
            ServiceResult with failure if length invalid
        """
        if value is None:
            return None
        
        length = len(value)
        
        if min_length is not None and length < min_length:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Field '{field}' must be at least {min_length} characters",
                    severity=ErrorSeverity.WARNING,
                    field=field,
                )
            )
        
        if max_length is not None and length > max_length:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Field '{field}' must not exceed {max_length} characters",
                    severity=ErrorSeverity.WARNING,
                    field=field,
                )
            )
        
        return None

    @staticmethod
    def validate_pattern(
        value: str,
        field: str,
        pattern: str,
        message: Optional[str] = None,
    ) -> Optional[ServiceResult]:
        """
        Validate string against regex pattern.
        
        Args:
            value: String to validate
            field: Field name
            pattern: Regex pattern
            message: Custom error message
            
        Returns:
            ServiceResult with failure if pattern doesn't match
        """
        if value is None:
            return None
        
        if not re.match(pattern, value):
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=message or f"Field '{field}' has invalid format",
                    severity=ErrorSeverity.WARNING,
                    field=field,
                )
            )
        
        return None

    @staticmethod
    def validate_email(value: str, field: str = "email") -> Optional[ServiceResult]:
        """
        Validate email format.
        
        Args:
            value: Email to validate
            field: Field name
            
        Returns:
            ServiceResult with failure if invalid email
        """
        if value is None:
            return None
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return ValidationService.validate_pattern(
            value,
            field,
            email_pattern,
            f"Field '{field}' must be a valid email address"
        )

    @staticmethod
    def validate_phone(value: str, field: str = "phone") -> Optional[ServiceResult]:
        """
        Validate phone number format.
        
        Args:
            value: Phone number to validate
            field: Field name
            
        Returns:
            ServiceResult with failure if invalid phone
        """
        if value is None:
            return None
        
        # Simple phone validation - adjust pattern as needed
        phone_pattern = r'^\+?[1-9]\d{1,14}$'
        return ValidationService.validate_pattern(
            value,
            field,
            phone_pattern,
            f"Field '{field}' must be a valid phone number"
        )

    # -------------------------------------------------------------------------
    # Collection Validation
    # -------------------------------------------------------------------------

    @staticmethod
    def validate_choice(
        value: Any,
        field: str,
        choices: List[Any],
    ) -> Optional[ServiceResult]:
        """
        Validate that value is one of allowed choices.
        
        Args:
            value: Value to validate
            field: Field name
            choices: List of allowed values
            
        Returns:
            ServiceResult with failure if not in choices
        """
        if value not in choices:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Field '{field}' must be one of: {', '.join(map(str, choices))}",
                    severity=ErrorSeverity.WARNING,
                    field=field,
                    details={"allowed_values": choices},
                )
            )
        return None

    @staticmethod
    def validate_list_items(
        items: List[Any],
        field: str,
        validator: Callable[[Any, str], Optional[ServiceResult]],
    ) -> Optional[ServiceResult]:
        """
        Validate each item in a list.
        
        Args:
            items: List of items to validate
            field: Field name
            validator: Validation function for individual items
            
        Returns:
            ServiceResult with failure if any item is invalid
        """
        if not isinstance(items, list):
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Field '{field}' must be a list",
                    severity=ErrorSeverity.WARNING,
                    field=field,
                )
            )
        
        errors = []
        for i, item in enumerate(items):
            result = validator(item, f"{field}[{i}]")
            if result and not result.is_success:
                errors.append(result.error.message)
        
        if errors:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Validation errors in '{field}': {'; '.join(errors)}",
                    severity=ErrorSeverity.WARNING,
                    field=field,
                    details={"item_errors": errors},
                )
            )
        
        return None

    # -------------------------------------------------------------------------
    # Batch Validation
    # -------------------------------------------------------------------------

    @staticmethod
    def validate_all(
        validations: List[Optional[ServiceResult]]
    ) -> Optional[ServiceResult]:
        """
        Aggregate multiple validation results.
        
        Args:
            validations: List of validation results
            
        Returns:
            ServiceResult with all errors if any validation failed
        """
        errors = [v.error for v in validations if v and not v.is_success]
        
        if errors:
            all_messages = "; ".join(e.message for e in errors)
            all_fields = [e.field for e in errors if e.field]
            
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=f"Validation failed: {all_messages}",
                    severity=ErrorSeverity.WARNING,
                    details={
                        "error_count": len(errors),
                        "fields": all_fields,
                        "errors": [e.to_dict() for e in errors],
                    }
                )
            )
        
        return None