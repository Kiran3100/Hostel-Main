# app/services/common/errors.py
"""
Service-layer exceptions.

These exceptions are raised by service methods and should be caught
at the API layer to return appropriate HTTP responses.
"""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID


class ServiceError(Exception):
    """Base exception for all service-layer errors."""
    
    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(ServiceError):
    """Raised when a requested resource does not exist."""
    
    def __init__(
        self,
        resource_type: str,
        identifier: UUID | str | int,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        message = f"{resource_type} with identifier '{identifier}' not found"
        super().__init__(message, details)
        self.resource_type = resource_type
        self.identifier = identifier


class AlreadyExistsError(ServiceError):
    """Raised when attempting to create a resource that already exists."""
    
    def __init__(
        self,
        resource_type: str,
        field: str,
        value: Any,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        message = f"{resource_type} with {field}='{value}' already exists"
        super().__init__(message, details)
        self.resource_type = resource_type
        self.field = field
        self.value = value


class ValidationError(ServiceError):
    """Raised when business logic validation fails."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, details)
        self.field = field


class AuthenticationError(ServiceError):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message)


class AuthorizationError(ServiceError):
    """Raised when a user lacks permission for an action."""
    
    def __init__(
        self,
        message: str = "Authorization failed",
        required_permission: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, details)
        self.required_permission = required_permission


class ConflictError(ServiceError):
    """Raised when an operation conflicts with current state."""
    
    def __init__(
        self,
        message: str,
        conflicting_field: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, details)
        self.conflicting_field = conflicting_field


class BusinessRuleViolation(ServiceError):
    """Raised when a business rule is violated."""
    
    def __init__(
        self,
        rule_name: str,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, details)
        self.rule_name = rule_name