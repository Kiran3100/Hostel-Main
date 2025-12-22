"""
Security settings for the hostel management system.
Provides configuration for JWT, encryption, and other security features.
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet
import secrets
import hashlib
import base64

from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)

class SecurityConfig:
    """Security configuration and utility methods"""
    
    def __init__(self):
        # JWT configuration
        self.secret_key = settings.JWT_SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS
        
        # Password hashing
        self.pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto",
            bcrypt__rounds=settings.PASSWORD_BCRYPT_ROUNDS
        )
        
        # Encryption
        self.encryption_key = self._derive_encryption_key(settings.ENCRYPTION_KEY)
        self.fernet = Fernet(self.encryption_key)
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def decode_token(self, token: str) -> Dict[str, Any]:
        """Decode and validate JWT token"""
        return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash password"""
        return self.pwd_context.hash(password)
    
    def generate_password(self, length: int = 12) -> str:
        """Generate secure random password"""
        # Generate secure random string
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+"
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        
        # Ensure password meets requirements
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()-_=+" for c in password)
        
        # Regenerate if requirements not met
        if not (has_upper and has_lower and has_digit and has_special):
            return self.generate_password(length)
        
        return password
    
    def encrypt_data(self, data: Union[str, bytes]) -> str:
        """Encrypt data using Fernet symmetric encryption"""
        if isinstance(data, str):
            data = data.encode()
        
        encrypted = self.fernet.encrypt(data)
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt data using Fernet symmetric encryption"""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data)
            decrypted = self.fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption error: {str(e)}")
            raise ValueError("Decryption failed")
    
    def generate_token(self, length: int = 32) -> str:
        """Generate secure random token"""
        return secrets.token_urlsafe(length)
    
    def hash_string(self, string: str) -> str:
        """Create SHA-256 hash of string"""
        return hashlib.sha256(string.encode()).hexdigest()
    
    def _derive_encryption_key(self, key: str) -> bytes:
        """Derive Fernet key from string"""
        key_bytes = key.encode()
        
        # If key is not 32 bytes, hash it to get 32 bytes
        if len(key_bytes) != 32:
            key_bytes = hashlib.sha256(key_bytes).digest()
        
        # Encode in URL-safe base64 format
        return base64.urlsafe_b64encode(key_bytes)

class PasswordPolicy:
    """Password policy enforcement"""
    
    def __init__(self):
        self.min_length = 8
        self.require_uppercase = True
        self.require_lowercase = True
        self.require_digit = True
        self.require_special = True
        self.max_reuse_count = 5
        self.max_age_days = 90
    
    def validate_password(self, password: str) -> Dict[str, Any]:
        """Validate password against policy"""
        errors = []
        
        # Check length
        if len(password) < self.min_length:
            errors.append(f"Password must be at least {self.min_length} characters long")
        
        # Check character requirements
        if self.require_uppercase and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if self.require_lowercase and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if self.require_digit and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")
        
        if self.require_special and not any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?/`~" for c in password):
            errors.append("Password must contain at least one special character")
        
        # Check common passwords (simplified version)
        common_passwords = {"password", "123456", "qwerty", "admin", "welcome"}
        if password.lower() in common_passwords:
            errors.append("Password is too common")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "score": self._calculate_strength_score(password)
        }
    
    def _calculate_strength_score(self, password: str) -> int:
        """Calculate password strength score (0-100)"""
        score = 0
        
        # Length score (up to 40 points)
        length_score = min(len(password) * 4, 40)
        score += length_score
        
        # Character variety (up to 40 points)
        if any(c.islower() for c in password):
            score += 10
        if any(c.isupper() for c in password):
            score += 10
        if any(c.isdigit() for c in password):
            score += 10
        if any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?/`~" for c in password):
            score += 10
        
        # Bonus for mixed character types (up to 20 points)
        char_types = sum([
            any(c.islower() for c in password),
            any(c.isupper() for c in password),
            any(c.isdigit() for c in password),
            any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?/`~" for c in password)
        ])
        
        score += char_types * 5
        
        return min(score, 100)

class TwoFactorAuthentication:
    """Two-factor authentication utilities"""
    
    def __init__(self, security_config: SecurityConfig):
        self.security_config = security_config
    
    def generate_totp_secret(self) -> str:
        """Generate TOTP secret"""
        import pyotp
        return pyotp.random_base32()
    
    def get_totp_uri(self, secret: str, username: str, issuer: str = "HostelManagement") -> str:
        """Get TOTP URI for QR code generation"""
        import pyotp
        return pyotp.totp.TOTP(secret).provisioning_uri(
            name=username,
            issuer_name=issuer
        )
    
    def verify_totp(self, secret: str, token: str) -> bool:
        """Verify TOTP token"""
        import pyotp
        return pyotp.TOTP(secret).verify(token)
    
    def generate_recovery_codes(self, count: int = 10) -> List[str]:
        """Generate recovery codes"""
        codes = []
        for _ in range(count):
            # Format: XXXX-XXXX-XXXX
            code = "-".join([
                "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(4))
                for _ in range(3)
            ])
            codes.append(code)
        
        return codes
    
    def hash_recovery_codes(self, codes: List[str]) -> List[str]:
        """Hash recovery codes for storage"""
        return [self.security_config.hash_string(code) for code in codes]
    
    def verify_recovery_code(self, plain_code: str, hashed_codes: List[str]) -> bool:
        """Verify a recovery code"""
        code_hash = self.security_config.hash_string(plain_code)
        return code_hash in hashed_codes

class SecurityHeaders:
    """Security HTTP headers management"""
    
    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """Get security headers for HTTP responses"""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache"
        }
    
    @staticmethod
    def get_cors_headers() -> Dict[str, str]:
        """Get CORS headers based on configuration"""
        origins = ','.join(settings.CORS_ORIGINS)
        
        return {
            "Access-Control-Allow-Origin": origins if origins != "*" else "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Hostel-ID, X-Tenant-ID"
        }

# Create global security instance
security_config = SecurityConfig()
password_policy = PasswordPolicy()
two_factor_auth = TwoFactorAuthentication(security_config)