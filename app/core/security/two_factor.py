# File: C:\Hostel-Main\app\core\security\two_factor.py
"""
Two-Factor Authentication (TOTP) implementation.

Provides Time-based One-Time Password functionality using pyotp.
"""

import pyotp
import logging
from typing import Optional
from io import BytesIO
import qrcode

logger = logging.getLogger(__name__)


class TwoFactorAuthentication:
    """
    Handle TOTP-based two-factor authentication.
    
    Provides methods for:
    - Generating TOTP secrets
    - Creating provisioning URIs
    - Verifying TOTP codes
    - Generating QR codes
    """
    
    def __init__(self, issuer: str = "HostelMS"):
        """
        Initialize 2FA handler.
        
        Args:
            issuer: Application name for TOTP display
        """
        self.issuer = issuer
        logger.info(f"TwoFactorAuthentication initialized with issuer: {issuer}")
    
    def generate_secret(self) -> str:
        """
        Generate a random TOTP secret.
        
        Returns:
            Base32-encoded secret string
        """
        try:
            secret = pyotp.random_base32()
            logger.debug("Generated new TOTP secret")
            return secret
        except Exception as e:
            logger.error(f"Error generating TOTP secret: {e}")
            raise
    
    def build_otpauth_url(
        self,
        secret: str,
        account_name: str,
        issuer: Optional[str] = None,
    ) -> str:
        """
        Build provisioning URI for QR code generation.
        
        Args:
            secret: TOTP secret
            account_name: User's account identifier (email/username)
            issuer: Optional issuer name (defaults to instance issuer)
            
        Returns:
            otpauth:// URI string
        """
        try:
            totp = pyotp.TOTP(secret)
            issuer_name = issuer or self.issuer
            
            uri = totp.provisioning_uri(
                name=account_name,
                issuer_name=issuer_name
            )
            
            logger.debug(f"Built provisioning URI for account: {account_name}")
            return uri
            
        except Exception as e:
            logger.error(f"Error building provisioning URI: {e}")
            raise
    
    def verify_code(
        self,
        secret: str,
        code: str,
        valid_window: int = 1,
    ) -> bool:
        """
        Verify a TOTP code.
        
        Args:
            secret: TOTP secret
            code: 6-digit TOTP code to verify
            valid_window: Number of time steps to check (default: 1)
                         1 = 30 seconds before/after current time
            
        Returns:
            True if code is valid, False otherwise
        """
        try:
            # Clean the code (remove spaces, dashes)
            clean_code = code.replace(" ", "").replace("-", "")
            
            # Verify it's 6 digits
            if not clean_code.isdigit() or len(clean_code) != 6:
                logger.warning(f"Invalid TOTP code format: {code}")
                return False
            
            totp = pyotp.TOTP(secret)
            is_valid = totp.verify(clean_code, valid_window=valid_window)
            
            if is_valid:
                logger.debug("TOTP code verified successfully")
            else:
                logger.warning("TOTP code verification failed")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Error verifying TOTP code: {e}")
            return False
    
    def get_current_code(self, secret: str) -> str:
        """
        Get current TOTP code (for testing/debugging).
        
        Args:
            secret: TOTP secret
            
        Returns:
            Current 6-digit TOTP code
        """
        try:
            totp = pyotp.TOTP(secret)
            return totp.now()
        except Exception as e:
            logger.error(f"Error getting current TOTP code: {e}")
            raise
    
    def generate_qr_code(
        self,
        otpauth_url: str,
        size: int = 300,
    ) -> BytesIO:
        """
        Generate QR code image from provisioning URI.
        
        Args:
            otpauth_url: Provisioning URI
            size: QR code size in pixels
            
        Returns:
            BytesIO object containing PNG image
        """
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(otpauth_url)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Resize if needed
            if size != 300:
                img = img.resize((size, size))
            
            # Save to BytesIO
            img_io = BytesIO()
            img.save(img_io, 'PNG')
            img_io.seek(0)
            
            logger.debug(f"Generated QR code image ({size}x{size})")
            return img_io
            
        except Exception as e:
            logger.error(f"Error generating QR code: {e}")
            raise
    
    def get_time_remaining(self) -> int:
        """
        Get seconds remaining until next TOTP code.
        
        Returns:
            Seconds remaining in current 30-second window
        """
        try:
            import time
            return 30 - int(time.time() % 30)
        except Exception as e:
            logger.error(f"Error getting time remaining: {e}")
            return 0
    
    @staticmethod
    def is_valid_secret(secret: str) -> bool:
        """
        Validate if a string is a valid base32 secret.
        
        Args:
            secret: Secret string to validate
            
        Returns:
            True if valid base32, False otherwise
        """
        try:
            # Try to create TOTP instance
            pyotp.TOTP(secret)
            return True
        except Exception:
            return False