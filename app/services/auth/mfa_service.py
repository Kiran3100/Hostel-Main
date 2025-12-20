"""
MFA Service
Multi-Factor Authentication management including TOTP, SMS, and backup codes.
"""

import pyotp
import qrcode
import io
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.auth import SecurityEventRepository
from app.services.auth.otp_service import OTPService
from app.schemas.common.enums import OTPType
from app.core.exceptions import (
    MFAError,
    InvalidMFACodeError,
    MFANotEnabledError,
)


class MFAService:
    """
    Service for Multi-Factor Authentication operations.
    """

    def __init__(self, db: Session):
        self.db = db
        self.security_event_repo = SecurityEventRepository(db)
        self.otp_service = OTPService(db)

    # ==================== TOTP (Time-based OTP) ====================

    def generate_totp_secret(self, user_email: str) -> Dict[str, Any]:
        """
        Generate TOTP secret for authenticator app.
        
        Args:
            user_email: User email for provisioning URI
            
        Returns:
            Dictionary with secret and QR code
        """
        # Generate secret
        secret = pyotp.random_base32()
        
        # Create provisioning URI
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user_email,
            issuer_name="YourAppName"  # Replace with your app name
        )
        
        # Generate QR code
        qr_code_data = self._generate_qr_code(provisioning_uri)
        
        return {
            "secret": secret,
            "provisioning_uri": provisioning_uri,
            "qr_code": qr_code_data,
            "manual_entry_key": secret
        }

    def _generate_qr_code(self, data: str) -> str:
        """Generate QR code as base64 image."""
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"

    def verify_totp_code(
        self,
        secret: str,
        code: str,
        window: int = 1
    ) -> bool:
        """
        Verify TOTP code.
        
        Args:
            secret: TOTP secret
            code: Code to verify
            window: Time window for verification (in 30-second intervals)
            
        Returns:
            True if code is valid
        """
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=window)

    def enable_totp_mfa(
        self,
        user_id: UUID,
        secret: str,
        verification_code: str,
        ip_address: str,
        user_agent: str
    ) -> Tuple[bool, Optional[List[str]]]:
        """
        Enable TOTP MFA for user after verification.
        
        Args:
            user_id: User identifier
            secret: TOTP secret
            verification_code: Code to verify setup
            ip_address: Request IP address
            user_agent: Request user agent
            
        Returns:
            Tuple of (success, backup_codes)
            
        Raises:
            InvalidMFACodeError: If verification code is invalid
        """
        # Verify the code
        if not self.verify_totp_code(secret, verification_code):
            raise InvalidMFACodeError("Invalid verification code")
        
        # Generate backup codes
        backup_codes = self._generate_backup_codes()
        
        # Save MFA settings to user
        # This needs to be implemented based on your User model
        self._save_user_mfa_settings(
            user_id=user_id,
            mfa_method="totp",
            mfa_secret=secret,
            backup_codes=self._hash_backup_codes(backup_codes)
        )
        
        # Record security event
        self.security_event_repo.record_event(
            event_type="mfa_enabled",
            severity="medium",
            description="TOTP MFA enabled",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={"mfa_method": "totp"}
        )
        
        return True, backup_codes

    def disable_totp_mfa(
        self,
        user_id: UUID,
        verification_code: str,
        ip_address: str,
        user_agent: str
    ) -> bool:
        """
        Disable TOTP MFA for user.
        
        Args:
            user_id: User identifier
            verification_code: Current MFA code for verification
            ip_address: Request IP address
            user_agent: Request user agent
            
        Returns:
            Success status
            
        Raises:
            InvalidMFACodeError: If verification code is invalid
        """
        # Get user's MFA secret
        mfa_secret = self._get_user_mfa_secret(user_id)
        
        if not mfa_secret:
            raise MFANotEnabledError("MFA is not enabled")
        
        # Verify the code
        if not self.verify_totp_code(mfa_secret, verification_code):
            raise InvalidMFACodeError("Invalid verification code")
        
        # Disable MFA
        self._save_user_mfa_settings(
            user_id=user_id,
            mfa_method=None,
            mfa_secret=None,
            backup_codes=None
        )
        
        # Record security event
        self.security_event_repo.record_event(
            event_type="mfa_disabled",
            severity="high",
            description="TOTP MFA disabled",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={"mfa_method": "totp"}
        )
        
        return True

    # ==================== SMS MFA ====================

    def send_sms_mfa_code(
        self,
        user_id: UUID,
        phone: str,
        ip_address: str,
        user_agent: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Send MFA code via SMS.
        
        Args:
            user_id: User identifier
            phone: Phone number
            ip_address: Request IP address
            user_agent: Request user agent
            
        Returns:
            Tuple of (success, error_message)
        """
        success, otp_code, error = self.otp_service.send_otp(
            user_id=user_id,
            identifier=phone,
            identifier_type="phone",
            otp_type=OTPType.TWO_FACTOR_AUTH,
            ip_address=ip_address,
            user_agent=user_agent,
            context={"purpose": "Two-Factor Authentication"}
        )
        
        if success:
            self.security_event_repo.record_event(
                event_type="sms_mfa_sent",
                severity="low",
                description="SMS MFA code sent",
                user_id=user_id,
                ip_address=ip_address
            )
        
        return success, error

    def verify_sms_mfa_code(
        self,
        user_id: UUID,
        phone: str,
        code: str,
        ip_address: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify SMS MFA code.
        
        Args:
            user_id: User identifier
            phone: Phone number
            code: MFA code
            ip_address: Request IP address
            
        Returns:
            Tuple of (success, error_message)
        """
        success, error = self.otp_service.verify_otp(
            identifier=phone,
            identifier_type="phone",
            otp_code=code,
            otp_type=OTPType.TWO_FACTOR_AUTH
        )
        
        if success:
            self.security_event_repo.record_event(
                event_type="sms_mfa_verified",
                severity="low",
                description="SMS MFA code verified",
                user_id=user_id,
                ip_address=ip_address
            )
        else:
            self.security_event_repo.record_event(
                event_type="sms_mfa_verification_failed",
                severity="medium",
                description="SMS MFA verification failed",
                user_id=user_id,
                ip_address=ip_address,
                risk_score=50
            )
        
        return success, error

    # ==================== Email MFA ====================

    def send_email_mfa_code(
        self,
        user_id: UUID,
        email: str,
        ip_address: str,
        user_agent: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Send MFA code via email.
        
        Args:
            user_id: User identifier
            email: Email address
            ip_address: Request IP address
            user_agent: Request user agent
            
        Returns:
            Tuple of (success, error_message)
        """
        success, otp_code, error = self.otp_service.send_otp(
            user_id=user_id,
            identifier=email,
            identifier_type="email",
            otp_type=OTPType.TWO_FACTOR_AUTH,
            ip_address=ip_address,
            user_agent=user_agent,
            context={"purpose": "Two-Factor Authentication"}
        )
        
        if success:
            self.security_event_repo.record_event(
                event_type="email_mfa_sent",
                severity="low",
                description="Email MFA code sent",
                user_id=user_id,
                ip_address=ip_address
            )
        
        return success, error

    def verify_email_mfa_code(
        self,
        user_id: UUID,
        email: str,
        code: str,
        ip_address: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify email MFA code.
        
        Args:
            user_id: User identifier
            email: Email address
            code: MFA code
            ip_address: Request IP address
            
        Returns:
            Tuple of (success, error_message)
        """
        success, error = self.otp_service.verify_otp(
            identifier=email,
            identifier_type="email",
            otp_code=code,
            otp_type=OTPType.TWO_FACTOR_AUTH
        )
        
        if success:
            self.security_event_repo.record_event(
                event_type="email_mfa_verified",
                severity="low",
                description="Email MFA code verified",
                user_id=user_id,
                ip_address=ip_address
            )
        else:
            self.security_event_repo.record_event(
                event_type="email_mfa_verification_failed",
                severity="medium",
                description="Email MFA verification failed",
                user_id=user_id,
                ip_address=ip_address,
                risk_score=50
            )
        
        return success, error

    # ==================== Backup Codes ====================

    def _generate_backup_codes(self, count: int = 10) -> List[str]:
        """Generate backup codes for MFA."""
        import secrets
        import string
        
        codes = []
        for _ in range(count):
            # Generate 8-character alphanumeric code
            code = ''.join(
                secrets.choice(string.ascii_uppercase + string.digits)
                for _ in range(8)
            )
            # Format as XXXX-XXXX
            formatted_code = f"{code[:4]}-{code[4:]}"
            codes.append(formatted_code)
        
        return codes

    def _hash_backup_codes(self, codes: List[str]) -> List[str]:
        """Hash backup codes for storage."""
        import hashlib
        
        return [
            hashlib.sha256(code.encode()).hexdigest()
            for code in codes
        ]

    def verify_backup_code(
        self,
        user_id: UUID,
        code: str,
        ip_address: str
    ) -> bool:
        """
        Verify and consume backup code.
        
        Args:
            user_id: User identifier
            code: Backup code to verify
            ip_address: Request IP address
            
        Returns:
            True if code is valid
        """
        import hashlib
        
        # Hash the provided code
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        
        # Get user's backup codes
        backup_codes = self._get_user_backup_codes(user_id)
        
        if not backup_codes:
            return False
        
        # Check if code matches any backup code
        if code_hash in backup_codes:
            # Remove used code
            backup_codes.remove(code_hash)
            self._save_user_backup_codes(user_id, backup_codes)
            
            # Record security event
            self.security_event_repo.record_event(
                event_type="backup_code_used",
                severity="medium",
                description="MFA backup code used",
                user_id=user_id,
                ip_address=ip_address,
                event_data={"remaining_codes": len(backup_codes)}
            )
            
            return True
        
        return False

    def regenerate_backup_codes(
        self,
        user_id: UUID,
        verification_code: str,
        ip_address: str,
        user_agent: str
    ) -> Tuple[bool, Optional[List[str]]]:
        """
        Regenerate backup codes.
        
        Args:
            user_id: User identifier
            verification_code: Current MFA code for verification
            ip_address: Request IP address
            user_agent: Request user agent
            
        Returns:
            Tuple of (success, new_backup_codes)
        """
        # Verify current MFA code
        mfa_secret = self._get_user_mfa_secret(user_id)
        
        if not mfa_secret:
            raise MFANotEnabledError("MFA is not enabled")
        
        if not self.verify_totp_code(mfa_secret, verification_code):
            raise InvalidMFACodeError("Invalid verification code")
        
        # Generate new backup codes
        backup_codes = self._generate_backup_codes()
        hashed_codes = self._hash_backup_codes(backup_codes)
        
        # Save new codes
        self._save_user_backup_codes(user_id, hashed_codes)
        
        # Record security event
        self.security_event_repo.record_event(
            event_type="backup_codes_regenerated",
            severity="medium",
            description="MFA backup codes regenerated",
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return True, backup_codes

    def get_remaining_backup_codes_count(self, user_id: UUID) -> int:
        """Get count of remaining backup codes."""
        backup_codes = self._get_user_backup_codes(user_id)
        return len(backup_codes) if backup_codes else 0

    # ==================== MFA Status ====================

    def get_mfa_status(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get MFA status for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with MFA status
        """
        # Get user MFA settings
        mfa_method = self._get_user_mfa_method(user_id)
        
        return {
            "mfa_enabled": mfa_method is not None,
            "mfa_method": mfa_method,
            "backup_codes_remaining": self.get_remaining_backup_codes_count(user_id),
            "mfa_methods_available": ["totp", "sms", "email"]
        }

    def require_mfa_for_action(
        self,
        user_id: UUID,
        action: str,
        risk_level: str = "high"
    ) -> bool:
        """
        Determine if MFA is required for an action.
        
        Args:
            user_id: User identifier
            action: Action being performed
            risk_level: Risk level of action (low, medium, high)
            
        Returns:
            True if MFA is required
        """
        # Get MFA status
        mfa_status = self.get_mfa_status(user_id)
        
        if not mfa_status["mfa_enabled"]:
            # MFA not enabled, check if it should be required
            return risk_level in ["high", "critical"]
        
        # MFA is enabled, require for medium and high risk actions
        return risk_level in ["medium", "high", "critical"]

    # ==================== Helper Methods ====================

    def _save_user_mfa_settings(
        self,
        user_id: UUID,
        mfa_method: Optional[str],
        mfa_secret: Optional[str],
        backup_codes: Optional[List[str]]
    ) -> None:
        """
        Save MFA settings to user.
        This is a placeholder - implement based on your User model.
        """
        from app.models.user import User
        
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            user.mfa_enabled = mfa_method is not None
            user.mfa_method = mfa_method
            user.mfa_secret = mfa_secret
            if backup_codes is not None:
                user.mfa_backup_codes = backup_codes
            self.db.commit()

    def _get_user_mfa_secret(self, user_id: UUID) -> Optional[str]:
        """Get user's MFA secret."""
        from app.models.user import User
        
        user = self.db.query(User).filter(User.id == user_id).first()
        return user.mfa_secret if user else None

    def _get_user_mfa_method(self, user_id: UUID) -> Optional[str]:
        """Get user's MFA method."""
        from app.models.user import User
        
        user = self.db.query(User).filter(User.id == user_id).first()
        return user.mfa_method if user and user.mfa_enabled else None

    def _get_user_backup_codes(self, user_id: UUID) -> Optional[List[str]]:
        """Get user's backup codes."""
        from app.models.user import User
        
        user = self.db.query(User).filter(User.id == user_id).first()
        return user.mfa_backup_codes if user else None

    def _save_user_backup_codes(
        self,
        user_id: UUID,
        backup_codes: List[str]
    ) -> None:
        """Save user's backup codes."""
        from app.models.user import User
        
        user = self.db.query(User).filter(User.id == user_id).first()
        if user:
            user.mfa_backup_codes = backup_codes
            self.db.commit()