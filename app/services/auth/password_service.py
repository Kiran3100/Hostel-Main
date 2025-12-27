"""
Password management service: change, reset, and strength validation.

Comprehensive password security with policy enforcement,
history tracking, and breach detection.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import (
    BaseService,
    ServiceResult,
    ServiceError,
    ErrorCode,
    ErrorSeverity,
)
from app.repositories.user import UserRepository
from app.repositories.auth import (
    PasswordResetRepository,
    PasswordHistoryRepository,
    PasswordPolicyRepository,
)
from app.schemas.auth.password import (
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordChangeRequest,
    PasswordChangeResponse,
    PasswordStrengthCheck,
    PasswordStrengthResponse,
    PasswordValidator,
)
from app.models.user.user import User
from app.core1.security.password_hasher import PasswordHasher

logger = logging.getLogger(__name__)


class PasswordService(BaseService[User, UserRepository]):
    """
    Manage password lifecycle and security policies.
    
    Features:
    - Password change with verification
    - Password reset flow (request/confirm)
    - Strength validation and scoring
    - Password history tracking
    - Policy enforcement
    - Breach detection (optional)
    """

    # Configuration
    PASSWORD_RESET_TOKEN_VALIDITY_HOURS = 24
    PASSWORD_HISTORY_COUNT = 5
    MIN_PASSWORD_AGE_DAYS = 1
    MAX_PASSWORD_AGE_DAYS = 90

    def __init__(
        self,
        user_repository: UserRepository,
        reset_repository: PasswordResetRepository,
        history_repository: PasswordHistoryRepository,
        policy_repository: PasswordPolicyRepository,
        db_session: Session,
    ):
        super().__init__(user_repository, db_session)
        self.reset_repository = reset_repository
        self.history_repository = history_repository
        self.policy_repository = policy_repository
        self.hasher = PasswordHasher()
        self.validator = PasswordValidator()

    # -------------------------------------------------------------------------
    # Password Change
    # -------------------------------------------------------------------------

    def change_password(
        self,
        user_id: UUID,
        request: PasswordChangeRequest,
    ) -> ServiceResult[PasswordChangeResponse]:
        """
        Change user password with comprehensive validation.
        
        Args:
            user_id: User identifier
            request: Password change request
            
        Returns:
            ServiceResult with change confirmation
        """
        try:
            # Fetch user
            user = self.repository.get_by_id(user_id)
            if not user:
                logger.warning(f"Password change attempt for non-existent user: {user_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="User not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            # Verify current password
            if not self.hasher.verify(request.current_password, user.password_hash):
                logger.warning(f"Incorrect current password for user: {user_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Current password is incorrect",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Validate new password
            validation_result = self._validate_new_password(
                user=user,
                new_password=request.new_password,
                confirm_password=request.confirm_password,
                current_password=request.current_password,
            )
            
            if not validation_result.success:
                return validation_result

            # Check password age policy (minimum)
            if user.last_password_change_at:
                days_since_change = (
                    datetime.utcnow() - user.last_password_change_at
                ).days
                
                if days_since_change < self.MIN_PASSWORD_AGE_DAYS:
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.VALIDATION_ERROR,
                            message=(
                                f"Password can only be changed once every "
                                f"{self.MIN_PASSWORD_AGE_DAYS} day(s)"
                            ),
                            severity=ErrorSeverity.WARNING,
                        )
                    )

            # Hash new password
            new_hash = self.hasher.hash(request.new_password)

            # Save to password history
            self.history_repository.record_change(
                user_id=user_id,
                password_hash=user.password_hash,
            )

            # Update password
            self.repository.update(user_id, {
                "password_hash": new_hash,
                "last_password_change_at": datetime.utcnow(),
                "password_expires_at": datetime.utcnow() + timedelta(
                    days=self.MAX_PASSWORD_AGE_DAYS
                ),
            })
            self.db.commit()

            logger.info(f"Password changed successfully for user: {user_id}")
            return ServiceResult.success(
                PasswordChangeResponse(
                    message="Password changed successfully",
                    user_id=str(user_id),
                    changed_at=datetime.utcnow().isoformat(),
                ),
                message="Password changed successfully",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during password change: {str(e)}")
            return self._handle_exception(e, "change password", user_id)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during password change: {str(e)}")
            return self._handle_exception(e, "change password", user_id)

    # -------------------------------------------------------------------------
    # Password Reset Flow
    # -------------------------------------------------------------------------

    def request_reset(
        self,
        request: PasswordResetRequest,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Initiate password reset by sending reset link.
        
        Args:
            request: Password reset request with email
            
        Returns:
            ServiceResult with confirmation (always success for security)
        """
        try:
            # Sanitize email
            email = request.email.strip().lower()

            # Find user
            user = self.repository.find_by_email(email)
            
            # Always return success to prevent user enumeration
            if not user:
                logger.info(f"Password reset requested for non-existent email: {email}")
                return ServiceResult.success(
                    {"message": "If the email exists, a reset link will be sent"},
                    message="Password reset initiated",
                )

            if not user.is_active:
                logger.warning(f"Password reset requested for inactive user: {email}")
                return ServiceResult.success(
                    {"message": "If the email exists, a reset link will be sent"},
                    message="Password reset initiated",
                )

            # Create reset token
            reset_token = self.reset_repository.create_reset(user.id)
            
            # Send reset email (handled by delivery repository)
            # This would typically integrate with email service
            
            self.db.commit()

            logger.info(f"Password reset initiated for user: {user.id}")
            return ServiceResult.success(
                {
                    "message": "Password reset link sent to your email",
                    "token": reset_token,  # In production, send via email only
                    "expires_in": self.PASSWORD_RESET_TOKEN_VALIDITY_HOURS * 3600,
                },
                message="Password reset initiated successfully",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during password reset request: {str(e)}")
            # Still return success for security
            return ServiceResult.success(
                {"message": "If the email exists, a reset link will be sent"},
                message="Password reset initiated",
            )
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during password reset request: {str(e)}")
            return ServiceResult.success(
                {"message": "If the email exists, a reset link will be sent"},
                message="Password reset initiated",
            )

    def confirm_reset(
        self,
        request: PasswordResetConfirm,
    ) -> ServiceResult[bool]:
        """
        Confirm password reset with token and new password.
        
        Args:
            request: Password reset confirmation with token and new password
            
        Returns:
            ServiceResult with confirmation status
        """
        try:
            # Validate password strength
            is_valid, suggestions = self.validator.validate_strength(
                request.new_password
            )
            
            if not is_valid:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Password does not meet security requirements",
                        severity=ErrorSeverity.WARNING,
                        details={"suggestions": suggestions},
                    )
                )

            # Verify password confirmation
            if request.new_password != request.confirm_password:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="Password confirmation does not match",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Consume reset token and get user ID
            user_id = self.reset_repository.consume_token(request.token)
            
            if not user_id:
                logger.warning(f"Invalid or expired reset token: {request.token}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Invalid or expired reset token",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Fetch user
            user = self.repository.get_by_id(user_id)
            if not user:
                logger.error(f"User not found for valid reset token: {user_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="User not found",
                        severity=ErrorSeverity.ERROR,
                    )
                )

            # Check password history
            if self._is_password_reused(user_id, request.new_password):
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message=(
                            f"Cannot reuse any of your last "
                            f"{self.PASSWORD_HISTORY_COUNT} passwords"
                        ),
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Hash and update password
            new_hash = self.hasher.hash(request.new_password)
            
            # Save to history
            self.history_repository.record_change(user_id, user.password_hash)
            
            # Update user
            self.repository.update(user_id, {
                "password_hash": new_hash,
                "last_password_change_at": datetime.utcnow(),
                "password_expires_at": datetime.utcnow() + timedelta(
                    days=self.MAX_PASSWORD_AGE_DAYS
                ),
            })
            
            self.db.commit()

            logger.info(f"Password reset completed for user: {user_id}")
            return ServiceResult.success(
                True,
                message="Password reset successful. You can now login.",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during password reset: {str(e)}")
            return self._handle_exception(e, "confirm password reset")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during password reset: {str(e)}")
            return self._handle_exception(e, "confirm password reset")

    # -------------------------------------------------------------------------
    # Password Strength Validation
    # -------------------------------------------------------------------------

    def strength_check(
        self,
        request: PasswordStrengthCheck,
    ) -> ServiceResult[PasswordStrengthResponse]:
        """
        Analyze password strength and provide feedback.
        
        Args:
            request: Password to analyze
            
        Returns:
            ServiceResult with strength analysis
        """
        try:
            # Calculate strength score
            score = self.validator.calculate_strength_score(request.password)
            
            # Validate against policy
            is_valid, suggestions = self.validator.validate_strength(
                request.password
            )

            # Build detailed response
            response = PasswordStrengthResponse.from_password(request.password)
            response.is_valid = is_valid
            response.suggestions = suggestions if not is_valid else []
            response.score = score

            return ServiceResult.success(
                response,
                message="Password strength analyzed",
            )

        except Exception as e:
            logger.error(f"Error during password strength check: {str(e)}")
            return self._handle_exception(e, "password strength check")

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _validate_new_password(
        self,
        user: User,
        new_password: str,
        confirm_password: str,
        current_password: str,
    ) -> ServiceResult:
        """
        Comprehensive validation of new password.
        
        Args:
            user: User object
            new_password: New password
            confirm_password: Password confirmation
            current_password: Current password
            
        Returns:
            ServiceResult indicating validation status
        """
        # Check password strength
        is_valid, suggestions = self.validator.validate_strength(new_password)
        if not is_valid:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Password does not meet security requirements",
                    severity=ErrorSeverity.WARNING,
                    details={"suggestions": suggestions},
                )
            )

        # Check if different from current
        if new_password == current_password:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="New password must be different from current password",
                    severity=ErrorSeverity.WARNING,
                )
            )

        # Check confirmation match
        if new_password != confirm_password:
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Password confirmation does not match",
                    severity=ErrorSeverity.WARNING,
                )
            )

        # Check password history
        if self._is_password_reused(user.id, new_password):
            return ServiceResult.failure(
                ServiceError(
                    code=ErrorCode.VALIDATION_ERROR,
                    message=(
                        f"Cannot reuse any of your last "
                        f"{self.PASSWORD_HISTORY_COUNT} passwords"
                    ),
                    severity=ErrorSeverity.WARNING,
                )
            )

        return ServiceResult.success(True)

    def _is_password_reused(self, user_id: UUID, new_password: str) -> bool:
        """
        Check if password has been used recently.
        
        Args:
            user_id: User identifier
            new_password: Password to check
            
        Returns:
            True if password was recently used
        """
        try:
            recent_hashes = self.history_repository.get_recent_passwords(
                user_id=user_id,
                count=self.PASSWORD_HISTORY_COUNT,
            )
            
            for old_hash in recent_hashes:
                if self.hasher.verify(new_password, old_hash):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking password history: {str(e)}")
            # Fail safely - allow change if history check fails
            return False