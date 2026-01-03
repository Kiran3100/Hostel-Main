"""
MFA (TOTP) enrollment and verification service.

Provides Time-based One-Time Password (TOTP) functionality for
enhanced account security.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
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
from app.models.user.user import User
from app.core.security.two_factor import TwoFactorAuthentication

logger = logging.getLogger(__name__)


class MFAService(BaseService[User, UserRepository]):
    """
    Manage TOTP-based Multi-Factor Authentication for users.
    
    Features:
    - TOTP secret generation
    - QR code provisioning
    - Enrollment verification
    - Backup codes generation
    - MFA status management
    """

    # Configuration
    BACKUP_CODES_COUNT = 10
    BACKUP_CODE_LENGTH = 8

    def __init__(self, user_repository: UserRepository, db_session: Session):
        super().__init__(user_repository, db_session)
        self.tfa = TwoFactorAuthentication()

    # -------------------------------------------------------------------------
    # Enrollment Flow
    # -------------------------------------------------------------------------

    def enroll(
        self,
        user_id: UUID,
        issuer: str = "HostelMS",
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Initiate MFA enrollment by generating TOTP secret and QR code URL.
        
        Args:
            user_id: User identifier
            issuer: Application name for TOTP app display
            
        Returns:
            ServiceResult with secret and QR code provisioning URL
        """
        try:
            # Fetch user
            user = self.repository.get_by_id(user_id)
            if not user:
                logger.warning(f"MFA enrollment attempt for non-existent user: {user_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="User not found",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            if not user.is_active:
                logger.warning(f"MFA enrollment attempt for inactive user: {user_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.FORBIDDEN,
                        message="Account is inactive",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Check if MFA already enabled
            if user.mfa_enabled and user.mfa_secret:
                logger.info(f"MFA re-enrollment for user: {user_id}")

            # Generate TOTP secret
            secret = self.tfa.generate_secret()
            
            # Build provisioning URL for QR code
            account_name = user.email or f"user_{user.id}"
            otpauth_url = self.tfa.build_otpauth_url(
                secret=secret,
                account_name=account_name,
                issuer=issuer,
            )

            # Store temporary secret (pending verification)
            self.repository.update(user_id, {
                "mfa_temp_secret": secret,
                "mfa_enabled": False,  # Not enabled until verified
            })
            self.db.commit()

            logger.info(f"MFA enrollment initiated for user: {user_id}")
            return ServiceResult.success(
                {
                    "secret": secret,
                    "otpauth_url": otpauth_url,
                    "issuer": issuer,
                    "account_name": account_name,
                },
                message="MFA enrollment initiated. Scan QR code with authenticator app.",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during MFA enrollment: {str(e)}")
            return self._handle_exception(e, "enroll mfa", user_id)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during MFA enrollment: {str(e)}")
            return self._handle_exception(e, "enroll mfa", user_id)

    def verify_enrollment(
        self,
        user_id: UUID,
        code: str,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Verify TOTP code to complete MFA enrollment.
        
        Args:
            user_id: User identifier
            code: TOTP code from authenticator app
            
        Returns:
            ServiceResult with backup codes and confirmation
        """
        try:
            # Fetch user
            user = self.repository.get_by_id(user_id)
            if not user or not user.mfa_temp_secret:
                logger.warning(
                    f"MFA verification attempt without enrollment: {user_id}"
                )
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.VALIDATION_ERROR,
                        message="No MFA enrollment in progress",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Verify TOTP code
            if not self.tfa.verify_code(user.mfa_temp_secret, code):
                logger.warning(f"Invalid MFA code during enrollment: {user_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Invalid verification code",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Generate backup codes
            backup_codes = self._generate_backup_codes()
            backup_codes_hashed = [
                self._hash_backup_code(code) for code in backup_codes
            ]

            # Activate MFA
            self.repository.update(user_id, {
                "mfa_secret": user.mfa_temp_secret,
                "mfa_enabled": True,
                "mfa_temp_secret": None,
                "mfa_backup_codes": backup_codes_hashed,
                "mfa_enabled_at": datetime.utcnow(),
            })
            self.db.commit()

            logger.info(f"MFA successfully enabled for user: {user_id}")
            return ServiceResult.success(
                {
                    "backup_codes": backup_codes,
                    "enabled_at": datetime.utcnow().isoformat(),
                },
                message="MFA enabled successfully. Save your backup codes securely.",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during MFA verification: {str(e)}")
            return self._handle_exception(e, "verify mfa enrollment", user_id)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during MFA verification: {str(e)}")
            return self._handle_exception(e, "verify mfa enrollment", user_id)

    # -------------------------------------------------------------------------
    # MFA Management
    # -------------------------------------------------------------------------

    def disable(
        self,
        user_id: UUID,
        verification_code: Optional[str] = None,
    ) -> ServiceResult[bool]:
        """
        Disable MFA for user (requires verification).
        
        Args:
            user_id: User identifier
            verification_code: TOTP or backup code for verification
            
        Returns:
            ServiceResult with success status
        """
        try:
            user = self.repository.get_by_id(user_id)
            if not user:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="User not found",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            if not user.mfa_enabled:
                logger.info(f"MFA disable attempt when not enabled: {user_id}")
                return ServiceResult.success(
                    True,
                    message="MFA is not enabled",
                )

            # Verify code before disabling (security measure)
            if verification_code:
                is_valid = self._verify_mfa_code(user, verification_code)
                if not is_valid:
                    logger.warning(f"Invalid code for MFA disable: {user_id}")
                    return ServiceResult.failure(
                        ServiceError(
                            code=ErrorCode.UNAUTHORIZED,
                            message="Invalid verification code",
                            severity=ErrorSeverity.WARNING,
                        )
                    )

            # Disable MFA
            self.repository.update(user_id, {
                "mfa_enabled": False,
                "mfa_secret": None,
                "mfa_backup_codes": None,
                "mfa_disabled_at": datetime.utcnow(),
            })
            self.db.commit()

            logger.info(f"MFA disabled for user: {user_id}")
            return ServiceResult.success(
                True,
                message="MFA disabled successfully",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during MFA disable: {str(e)}")
            return self._handle_exception(e, "disable mfa", user_id)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during MFA disable: {str(e)}")
            return self._handle_exception(e, "disable mfa", user_id)

    # -------------------------------------------------------------------------
    # Login Verification
    # -------------------------------------------------------------------------

    def verify_login_code(
        self,
        user_id: UUID,
        code: str,
    ) -> ServiceResult[bool]:
        """
        Verify MFA code during login flow.
        
        Args:
            user_id: User identifier
            code: TOTP or backup code
            
        Returns:
            ServiceResult with verification status
        """
        try:
            user = self.repository.get_by_id(user_id)
            if not user:
                logger.warning(f"MFA verification for non-existent user: {user_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="User not found",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            if not user.mfa_enabled or not user.mfa_secret:
                logger.warning(f"MFA verification when not enabled: {user_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="MFA is not enabled for this account",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Verify code (TOTP or backup)
            is_valid = self._verify_mfa_code(user, code)
            
            if not is_valid:
                logger.warning(f"Invalid MFA code during login: {user_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Invalid verification code",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Update last verified timestamp
            self.repository.update(user_id, {
                "mfa_last_verified_at": datetime.utcnow(),
            })
            self.db.commit()

            logger.info(f"MFA verification successful for user: {user_id}")
            return ServiceResult.success(
                True,
                message="MFA verification successful",
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error during MFA verification: {str(e)}")
            return self._handle_exception(e, "verify mfa login code", user_id)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during MFA verification: {str(e)}")
            return self._handle_exception(e, "verify mfa login code", user_id)

    # -------------------------------------------------------------------------
    # Backup Codes Management
    # -------------------------------------------------------------------------

    def regenerate_backup_codes(
        self,
        user_id: UUID,
        verification_code: str,
    ) -> ServiceResult[List[str]]:
        """
        Regenerate backup codes for user.
        
        Args:
            user_id: User identifier
            verification_code: Current TOTP code for verification
            
        Returns:
            ServiceResult with new backup codes
        """
        try:
            user = self.repository.get_by_id(user_id)
            if not user or not user.mfa_enabled:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.FORBIDDEN,
                        message="MFA is not enabled",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Verify TOTP code
            if not self.tfa.verify_code(user.mfa_secret, verification_code):
                logger.warning(f"Invalid code for backup regeneration: {user_id}")
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.UNAUTHORIZED,
                        message="Invalid verification code",
                        severity=ErrorSeverity.WARNING,
                    )
                )

            # Generate new backup codes
            backup_codes = self._generate_backup_codes()
            backup_codes_hashed = [
                self._hash_backup_code(code) for code in backup_codes
            ]

            self.repository.update(user_id, {
                "mfa_backup_codes": backup_codes_hashed,
            })
            self.db.commit()

            logger.info(f"Backup codes regenerated for user: {user_id}")
            return ServiceResult.success(
                backup_codes,
                message="Backup codes regenerated successfully",
            )

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error regenerating backup codes: {str(e)}")
            return self._handle_exception(e, "regenerate backup codes", user_id)

    # -------------------------------------------------------------------------
    # Private Helper Methods
    # -------------------------------------------------------------------------

    def _verify_mfa_code(self, user: User, code: str) -> bool:
        """
        Verify TOTP or backup code.
        
        Args:
            user: User object
            code: Code to verify
            
        Returns:
            True if code is valid
        """
        # Try TOTP verification first
        if self.tfa.verify_code(user.mfa_secret, code):
            return True

        # Try backup codes
        if user.mfa_backup_codes:
            code_hash = self._hash_backup_code(code)
            if code_hash in user.mfa_backup_codes:
                # Remove used backup code
                updated_codes = [
                    c for c in user.mfa_backup_codes if c != code_hash
                ]
                self.repository.update(user.id, {
                    "mfa_backup_codes": updated_codes,
                })
                logger.info(f"Backup code used for user: {user.id}")
                return True

        return False

    def _generate_backup_codes(self) -> List[str]:
        """Generate random backup codes."""
        import secrets
        import string
        
        codes = []
        for _ in range(self.BACKUP_CODES_COUNT):
            code = ''.join(
                secrets.choice(string.ascii_uppercase + string.digits)
                for _ in range(self.BACKUP_CODE_LENGTH)
            )
            # Format as XXXX-XXXX for readability
            formatted = f"{code[:4]}-{code[4:]}"
            codes.append(formatted)
        
        return codes

    def _hash_backup_code(self, code: str) -> str:
        """Hash backup code for secure storage."""
        import hashlib
        # Remove formatting
        clean_code = code.replace("-", "").upper()
        return hashlib.sha256(clean_code.encode()).hexdigest()


from datetime import datetime  # Add missing import