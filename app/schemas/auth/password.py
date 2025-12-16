# --- File: app/schemas/auth/password.py ---
"""
Password management schemas with robust validation.
Pydantic v2 compliant.
"""

import re
from typing import List, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "PasswordChangeRequest",
    "PasswordChangeResponse",
    "PasswordStrengthCheck",
    "PasswordStrengthResponse",
    "PasswordValidator",
]


class PasswordValidator:
    """
    Centralized password validation logic.
    
    Provides reusable validation methods for password strength.
    """

    SPECIAL_CHARS = r"!@#$%^&*()_+\-=\[\]{}|;:,.<>?"
    MIN_LENGTH = 8
    MAX_LENGTH = 128

    @classmethod
    def validate_strength(cls, password: str) -> tuple[bool, List[str]]:
        """
        Validate password strength and return issues.
        
        Args:
            password: Password to validate
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues: List[str] = []

        if len(password) < cls.MIN_LENGTH:
            issues.append(f"Password must be at least {cls.MIN_LENGTH} characters long")

        if not any(char.isdigit() for char in password):
            issues.append("Password must contain at least one digit")

        if not any(char.isupper() for char in password):
            issues.append("Password must contain at least one uppercase letter")

        if not any(char.islower() for char in password):
            issues.append("Password must contain at least one lowercase letter")

        if not re.search(f"[{re.escape(cls.SPECIAL_CHARS)}]", password):
            issues.append(
                "Password must contain at least one special character "
                f"({cls.SPECIAL_CHARS})"
            )

        return len(issues) == 0, issues

    @classmethod
    def calculate_strength_score(cls, password: str) -> int:
        """
        Calculate password strength score (0-5).
        
        Args:
            password: Password to evaluate
            
        Returns:
            Strength score from 0 (very weak) to 5 (very strong)
        """
        score = 0

        # Length score
        if len(password) >= 8:
            score += 1
        if len(password) >= 12:
            score += 1

        # Character diversity
        if any(char.islower() for char in password):
            score += 1
        if any(char.isupper() for char in password):
            score += 1
        if any(char.isdigit() for char in password):
            score += 1
        if re.search(f"[{re.escape(cls.SPECIAL_CHARS)}]", password):
            score += 1

        # Cap at 5
        return min(score, 5)


class PasswordResetRequest(BaseCreateSchema):
    """
    Password reset request (forgot password flow).
    
    Initiates password reset process via email.
    """

    email: str = Field(
        ...,
        description="User email address",
        examples=["user@example.com"],
    )

    @field_validator("email", mode="after")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        """Validate email format and normalize."""
        v = v.strip().lower()
        if not v:
            raise ValueError("Email cannot be empty")
        # Basic email validation
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v


class PasswordResetConfirm(BaseCreateSchema):
    """
    Confirm password reset with token and new password.
    
    Completes the password reset process.
    """

    token: str = Field(
        ...,
        min_length=1,
        description="Password reset token from email",
    )
    new_password: str = Field(
        ...,
        min_length=PasswordValidator.MIN_LENGTH,
        max_length=PasswordValidator.MAX_LENGTH,
        description="New password",
    )
    confirm_password: str = Field(
        ...,
        description="Confirm new password",
    )

    @field_validator("new_password", mode="after")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password strength requirements."""
        is_valid, issues = PasswordValidator.validate_strength(v)
        if not is_valid:
            raise ValueError("; ".join(issues))
        return v

    @model_validator(mode="after")
    def validate_passwords_match(self):
        """Ensure new_password and confirm_password match."""
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class PasswordChangeRequest(BaseCreateSchema):
    """
    Change password for authenticated user.
    
    Requires current password for security verification.
    """

    current_password: str = Field(
        ...,
        description="Current password for verification",
    )
    new_password: str = Field(
        ...,
        min_length=PasswordValidator.MIN_LENGTH,
        max_length=PasswordValidator.MAX_LENGTH,
        description="New password",
    )
    confirm_password: str = Field(
        ...,
        description="Confirm new password",
    )

    @field_validator("new_password", mode="after")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password strength requirements."""
        is_valid, issues = PasswordValidator.validate_strength(v)
        if not is_valid:
            raise ValueError("; ".join(issues))
        return v

    @model_validator(mode="after")
    def validate_password_requirements(self):
        """
        Validate password change requirements.
        
        Ensures:
        - New password matches confirmation
        - New password differs from current password
        """
        if self.new_password != self.confirm_password:
            raise ValueError("New password and confirmation do not match")

        if self.new_password == self.current_password:
            raise ValueError(
                "New password must be different from current password"
            )

        return self


class PasswordChangeResponse(BaseSchema):
    """Password change success response."""

    message: str = Field(
        ...,
        description="Success message",
        examples=["Password changed successfully"],
    )
    user_id: UUID = Field(
        ...,
        description="User ID",
    )


class PasswordStrengthCheck(BaseCreateSchema):
    """
    Check password strength without saving.
    
    Useful for real-time password strength indicators.
    """

    password: str = Field(
        ...,
        min_length=1,
        max_length=PasswordValidator.MAX_LENGTH,
        description="Password to evaluate",
    )


class PasswordStrengthResponse(BaseSchema):
    """
    Password strength evaluation response.
    
    Provides detailed strength analysis and suggestions.
    """

    score: int = Field(
        ...,
        ge=0,
        le=5,
        description="Strength score: 0 (very weak) to 5 (very strong)",
    )
    strength: str = Field(
        ...,
        description="Strength label",
        examples=["weak", "medium", "strong", "very_strong"],
    )
    has_minimum_length: bool = Field(
        ...,
        description=f"Has minimum {PasswordValidator.MIN_LENGTH} characters",
    )
    has_uppercase: bool = Field(
        ...,
        description="Contains uppercase letter",
    )
    has_lowercase: bool = Field(
        ...,
        description="Contains lowercase letter",
    )
    has_digit: bool = Field(
        ...,
        description="Contains digit",
    )
    has_special_char: bool = Field(
        ...,
        description="Contains special character",
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Suggestions for improvement",
    )

    @classmethod
    def from_password(cls, password: str):
        """
        Create response from password analysis.
        
        Args:
            password: Password to analyze
            
        Returns:
            PasswordStrengthResponse with complete analysis
        """
        score = PasswordValidator.calculate_strength_score(password)
        is_valid, issues = PasswordValidator.validate_strength(password)

        # Determine strength label
        if score <= 1:
            strength = "very_weak"
        elif score == 2:
            strength = "weak"
        elif score == 3:
            strength = "medium"
        elif score == 4:
            strength = "strong"
        else:
            strength = "very_strong"

        return cls(
            score=score,
            strength=strength,
            has_minimum_length=len(password) >= PasswordValidator.MIN_LENGTH,
            has_uppercase=any(c.isupper() for c in password),
            has_lowercase=any(c.islower() for c in password),
            has_digit=any(c.isdigit() for c in password),
            has_special_char=bool(
                re.search(
                    f"[{re.escape(PasswordValidator.SPECIAL_CHARS)}]",
                    password,
                )
            ),
            suggestions=issues if not is_valid else [],
        )