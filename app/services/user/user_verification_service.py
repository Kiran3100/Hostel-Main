# --- File: C:\Hostel-Main\app\services\user\user_verification_service.py ---
"""
User Verification Service - Email and phone verification management.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import secrets
import hashlib

from app.models.user import User
from app.repositories.user import UserRepository
from app.core.exceptions import (
    EntityNotFoundError,
    BusinessRuleViolationError,
    AuthenticationError
)


class UserVerificationService:
    """
    Service for user verification operations including email verification,
    phone verification, and OTP management.
    """

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        # TODO: Initialize email/SMS services
        # self.email_service = EmailService()
        # self.sms_service = SMSService()

    # ==================== Email Verification ====================

    def generate_email_verification_token(
        self,
        user_id: str,
        expiry_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Generate email verification token.
        
        Args:
            user_id: User ID
            expiry_hours: Token expiry in hours
            
        Returns:
            Token information
            
        Raises:
            EntityNotFoundError: If user not found
            BusinessRuleViolationError: If already verified
        """
        user = self.user_repo.get_by_id(user_id)
        
        if user.is_email_verified:
            raise BusinessRuleViolationError(
                "Email is already verified"
            )
        
        # Generate token
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        expiry = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
        
        # TODO: Store token in cache/database
        # cache.set(f"email_verify:{token_hash}", user_id, expiry)
        
        return {
            'user_id': user_id,
            'token': token,
            'token_hash': token_hash,
            'expires_at': expiry,
            'verification_url': f"/verify-email?token={token}"
        }

    def send_verification_email(
        self,
        user_id: str,
        resend: bool = False
    ) -> Dict[str, Any]:
        """
        Send email verification link.
        
        Args:
            user_id: User ID
            resend: Whether this is a resend
            
        Returns:
            Send status
        """
        user = self.user_repo.get_by_id(user_id)
        
        if user.is_email_verified and not resend:
            raise BusinessRuleViolationError(
                "Email is already verified"
            )
        
        # Generate token
        token_info = self.generate_email_verification_token(user_id)
        
        # TODO: Send email
        # self.email_service.send_verification_email(
        #     to=user.email,
        #     name=user.full_name,
        #     verification_url=token_info['verification_url']
        # )
        
        return {
            'status': 'sent',
            'email': user.email,
            'expires_at': token_info['expires_at']
        }

    def verify_email_with_token(
        self,
        token: str
    ) -> User:
        """
        Verify email using verification token.
        
        Args:
            token: Verification token
            
        Returns:
            Verified User
            
        Raises:
            AuthenticationError: If token is invalid or expired
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # TODO: Get user_id from cache
        # user_id = cache.get(f"email_verify:{token_hash}")
        # For now, raise error
        raise AuthenticationError("Invalid or expired verification token")
        
        # user = self.user_repo.get_by_id(user_id)
        # 
        # if user.is_email_verified:
        #     raise BusinessRuleViolationError("Email is already verified")
        # 
        # # Verify email
        # user = self.user_repo.verify_email(user_id)
        # 
        # # Delete token from cache
        # cache.delete(f"email_verify:{token_hash}")
        # 
        # return user

    def verify_email_directly(self, user_id: str) -> User:
        """
        Directly verify user email (admin operation).
        
        Args:
            user_id: User ID
            
        Returns:
            Verified User
        """
        return self.user_repo.verify_email(user_id)

    # ==================== Phone Verification ====================

    def generate_phone_otp(
        self,
        user_id: str,
        otp_length: int = 6,
        expiry_minutes: int = 10
    ) -> Dict[str, Any]:
        """
        Generate phone verification OTP.
        
        Args:
            user_id: User ID
            otp_length: OTP length
            expiry_minutes: OTP expiry in minutes
            
        Returns:
            OTP information
            
        Raises:
            EntityNotFoundError: If user not found
            BusinessRuleViolationError: If already verified
        """
        user = self.user_repo.get_by_id(user_id)
        
        if user.is_phone_verified:
            raise BusinessRuleViolationError(
                "Phone is already verified"
            )
        
        # Generate numeric OTP
        otp = ''.join([str(secrets.randbelow(10)) for _ in range(otp_length)])
        otp_hash = hashlib.sha256(otp.encode()).hexdigest()
        
        expiry = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)
        
        # TODO: Store OTP in cache
        # cache.set(f"phone_otp:{user_id}", otp_hash, expiry)
        
        return {
            'user_id': user_id,
            'otp': otp,  # In production, don't return this
            'otp_hash': otp_hash,
            'expires_at': expiry,
            'phone': user.phone
        }

    def send_phone_otp(
        self,
        user_id: str,
        resend: bool = False
    ) -> Dict[str, Any]:
        """
        Send phone verification OTP via SMS.
        
        Args:
            user_id: User ID
            resend: Whether this is a resend
            
        Returns:
            Send status
        """
        user = self.user_repo.get_by_id(user_id)
        
        if user.is_phone_verified and not resend:
            raise BusinessRuleViolationError(
                "Phone is already verified"
            )
        
        # Generate OTP
        otp_info = self.generate_phone_otp(user_id)
        
        # TODO: Send SMS
        # self.sms_service.send_otp(
        #     to=user.phone,
        #     otp=otp_info['otp']
        # )
        
        return {
            'status': 'sent',
            'phone': user.phone,
            'expires_at': otp_info['expires_at']
        }

    def verify_phone_with_otp(
        self,
        user_id: str,
        otp: str
    ) -> User:
        """
        Verify phone using OTP.
        
        Args:
            user_id: User ID
            otp: OTP code
            
        Returns:
            Verified User
            
        Raises:
            AuthenticationError: If OTP is invalid or expired
        """
        user = self.user_repo.get_by_id(user_id)
        
        if user.is_phone_verified:
            raise BusinessRuleViolationError("Phone is already verified")
        
        # TODO: Get stored OTP hash from cache
        # stored_otp_hash = cache.get(f"phone_otp:{user_id}")
        # 
        # if not stored_otp_hash:
        #     raise AuthenticationError("OTP expired or not found")
        # 
        # # Verify OTP
        # otp_hash = hashlib.sha256(otp.encode()).hexdigest()
        # 
        # if otp_hash != stored_otp_hash:
        #     raise AuthenticationError("Invalid OTP")
        # 
        # # Verify phone
        # user = self.user_repo.verify_phone(user_id)
        # 
        # # Delete OTP from cache
        # cache.delete(f"phone_otp:{user_id}")
        # 
        # return user
        
        raise AuthenticationError("OTP verification not implemented")

    def verify_phone_directly(self, user_id: str) -> User:
        """
        Directly verify user phone (admin operation).
        
        Args:
            user_id: User ID
            
        Returns:
            Verified User
        """
        return self.user_repo.verify_phone(user_id)

    # ==================== Verification Status ====================

    def get_verification_status(self, user_id: str) -> Dict[str, Any]:
        """
        Get user verification status.
        
        Args:
            user_id: User ID
            
        Returns:
            Verification status details
        """
        user = self.user_repo.get_by_id(user_id)
        
        return {
            'user_id': user.id,
            'email': user.email,
            'is_email_verified': user.is_email_verified,
            'email_verified_at': user.email_verified_at,
            'phone': user.phone,
            'is_phone_verified': user.is_phone_verified,
            'phone_verified_at': user.phone_verified_at,
            'is_fully_verified': user.is_verified
        }

    def check_verification_complete(self, user_id: str) -> bool:
        """
        Check if user has completed all verifications.
        
        Args:
            user_id: User ID
            
        Returns:
            True if fully verified
        """
        user = self.user_repo.get_by_id(user_id)
        return user.is_verified

    def require_verification(self, user_id: str) -> None:
        """
        Raise exception if user is not verified.
        
        Args:
            user_id: User ID
            
        Raises:
            BusinessRuleViolationError: If not verified
        """
        user = self.user_repo.get_by_id(user_id)
        
        if not user.is_verified:
            missing = []
            if not user.is_email_verified:
                missing.append('email')
            if not user.is_phone_verified:
                missing.append('phone')
            
            raise BusinessRuleViolationError(
                f"User verification required. Please verify: {', '.join(missing)}"
            )

    # ==================== Reverification ====================

    def require_email_reverification(self, user_id: str) -> User:
        """
        Unverify email and require reverification.
        
        Args:
            user_id: User ID
            
        Returns:
            Updated User
        """
        user = self.user_repo.get_by_id(user_id)
        
        return self.user_repo.update(user.id, {
            'is_email_verified': False,
            'email_verified_at': None
        })

    def require_phone_reverification(self, user_id: str) -> User:
        """
        Unverify phone and require reverification.
        
        Args:
            user_id: User ID
            
        Returns:
            Updated User
        """
        user = self.user_repo.get_by_id(user_id)
        
        return self.user_repo.update(user.id, {
            'is_phone_verified': False,
            'phone_verified_at': None
        })

    # ==================== Change Email/Phone ====================

    def initiate_email_change(
        self,
        user_id: str,
        new_email: str
    ) -> Dict[str, Any]:
        """
        Initiate email change process.
        
        Args:
            user_id: User ID
            new_email: New email address
            
        Returns:
            Change initiation details
            
        Raises:
            BusinessRuleViolationError: If email exists
        """
        # Check if new email already exists
        if self.user_repo.exists_by_email(new_email, exclude_user_id=user_id):
            raise BusinessRuleViolationError(
                f"Email {new_email} is already in use"
            )
        
        user = self.user_repo.get_by_id(user_id)
        
        # Generate verification token for new email
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        expiry = datetime.now(timezone.utc) + timedelta(hours=24)
        
        # TODO: Store change request in cache
        # cache.set(
        #     f"email_change:{token_hash}",
        #     {'user_id': user_id, 'new_email': new_email},
        #     expiry
        # )
        
        # TODO: Send verification email to new address
        # self.email_service.send_email_change_verification(
        #     to=new_email,
        #     name=user.full_name,
        #     verification_url=f"/confirm-email-change?token={token}"
        # )
        
        return {
            'status': 'initiated',
            'old_email': user.email,
            'new_email': new_email,
            'token': token,
            'expires_at': expiry
        }

    def confirm_email_change(
        self,
        token: str
    ) -> User:
        """
        Confirm email change with verification token.
        
        Args:
            token: Verification token
            
        Returns:
            Updated User
            
        Raises:
            AuthenticationError: If token invalid
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # TODO: Get change request from cache
        # change_data = cache.get(f"email_change:{token_hash}")
        # 
        # if not change_data:
        #     raise AuthenticationError("Invalid or expired token")
        # 
        # user_id = change_data['user_id']
        # new_email = change_data['new_email']
        # 
        # # Update email
        # user = self.user_repo.update(user_id, {
        #     'email': new_email,
        #     'is_email_verified': True,
        #     'email_verified_at': datetime.now(timezone.utc)
        # })
        # 
        # # Delete change request
        # cache.delete(f"email_change:{token_hash}")
        # 
        # return user
        
        raise AuthenticationError("Email change not implemented")

    def initiate_phone_change(
        self,
        user_id: str,
        new_phone: str
    ) -> Dict[str, Any]:
        """
        Initiate phone change process.
        
        Args:
            user_id: User ID
            new_phone: New phone number
            
        Returns:
            Change initiation details
            
        Raises:
            BusinessRuleViolationError: If phone exists
        """
        # Check if new phone already exists
        if self.user_repo.exists_by_phone(new_phone, exclude_user_id=user_id):
            raise BusinessRuleViolationError(
                f"Phone {new_phone} is already in use"
            )
        
        user = self.user_repo.get_by_id(user_id)
        
        # Generate OTP for new phone
        otp = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        otp_hash = hashlib.sha256(otp.encode()).hexdigest()
        
        expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
        
        # TODO: Store change request in cache
        # cache.set(
        #     f"phone_change:{user_id}",
        #     {'otp_hash': otp_hash, 'new_phone': new_phone},
        #     expiry
        # )
        
        # TODO: Send OTP to new phone
        # self.sms_service.send_otp(to=new_phone, otp=otp)
        
        return {
            'status': 'initiated',
            'old_phone': user.phone,
            'new_phone': new_phone,
            'otp': otp,  # Don't return in production
            'expires_at': expiry
        }

    def confirm_phone_change(
        self,
        user_id: str,
        otp: str
    ) -> User:
        """
        Confirm phone change with OTP.
        
        Args:
            user_id: User ID
            otp: OTP code
            
        Returns:
            Updated User
            
        Raises:
            AuthenticationError: If OTP invalid
        """
        # TODO: Get change request from cache
        # change_data = cache.get(f"phone_change:{user_id}")
        # 
        # if not change_data:
        #     raise AuthenticationError("OTP expired or not found")
        # 
        # # Verify OTP
        # otp_hash = hashlib.sha256(otp.encode()).hexdigest()
        # 
        # if otp_hash != change_data['otp_hash']:
        #     raise AuthenticationError("Invalid OTP")
        # 
        # new_phone = change_data['new_phone']
        # 
        # # Update phone
        # user = self.user_repo.update(user_id, {
        #     'phone': new_phone,
        #     'is_phone_verified': True,
        #     'phone_verified_at': datetime.now(timezone.utc)
        # })
        # 
        # # Delete change request
        # cache.delete(f"phone_change:{user_id}")
        # 
        # return user
        
        raise AuthenticationError("Phone change not implemented")

    # ==================== Verification Analytics ====================

    def get_unverified_users(
        self,
        verification_type: Optional[str] = None,
        older_than_days: Optional[int] = None
    ) -> List[User]:
        """
        Get users with pending verification.
        
        Args:
            verification_type: 'email', 'phone', or None for both
            older_than_days: Users registered more than X days ago
            
        Returns:
            List of unverified users
        """
        return self.user_repo.find_unverified_users(
            verification_type,
            older_than_days
        )

    def send_bulk_verification_reminders(
        self,
        older_than_days: int = 7
    ) -> Dict[str, int]:
        """
        Send verification reminders to unverified users.
        
        Args:
            older_than_days: Send to users registered more than X days ago
            
        Returns:
            Count of reminders sent
        """
        users = self.get_unverified_users(older_than_days=older_than_days)
        
        email_sent = 0
        sms_sent = 0
        
        for user in users:
            try:
                if not user.is_email_verified:
                    self.send_verification_email(user.id, resend=True)
                    email_sent += 1
                
                if not user.is_phone_verified:
                    self.send_phone_otp(user.id, resend=True)
                    sms_sent += 1
            except Exception:
                continue
        
        return {
            'email_reminders_sent': email_sent,
            'sms_reminders_sent': sms_sent,
            'total_users': len(users)
        }


