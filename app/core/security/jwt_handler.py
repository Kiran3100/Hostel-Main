import time
import hashlib
import secrets
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta
from jose import JWTError, jwt
from cryptography.fernet import Fernet

from app.config.security import SecurityConfig
from app.core.exceptions import TokenExpiredException, InvalidCredentialsException
from app.models.base.enums import UserRole
import logging

logger = logging.getLogger(__name__)

class JWTManager:
    """JWT token creation and validation manager"""
    
    def __init__(self, security_config: SecurityConfig = None):
        self.security_config = security_config or SecurityConfig()
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60  # 1 hour
        self.refresh_token_expire_days = 30    # 30 days
        self.secret_key = self.security_config.secret_key
        self.refresh_secret_key = self.security_config.refresh_secret_key
    
    def create_access_token(
        self, 
        data: Dict[str, Any], 
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access",
            "jti": secrets.token_urlsafe(32)  # JWT ID for tracking
        })
        
        # Add security claims
        to_encode.update({
            "iss": "hostel-management-system",  # Issuer
            "aud": "hostel-api",                # Audience
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        
        logger.info(f"Access token created for user: {data.get('sub')}")
        return encoded_jwt
    
    def create_refresh_token(
        self, 
        user_id: str, 
        device_id: Optional[str] = None
    ) -> str:
        """Create JWT refresh token"""
        to_encode = {
            "sub": user_id,
            "type": "refresh",
            "jti": secrets.token_urlsafe(32),
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(days=self.refresh_token_expire_days),
            "iss": "hostel-management-system",
            "aud": "hostel-api"
        }
        
        if device_id:
            to_encode["device_id"] = device_id
        
        encoded_jwt = jwt.encode(
            to_encode, 
            self.refresh_secret_key, 
            algorithm=self.algorithm
        )
        
        logger.info(f"Refresh token created for user: {user_id}")
        return encoded_jwt
    
    def decode_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """Decode and validate JWT token"""
        try:
            # Select appropriate secret based on token type
            secret_key = (
                self.refresh_secret_key if token_type == "refresh" 
                else self.secret_key
            )
            
            payload = jwt.decode(
                token, 
                secret_key, 
                algorithms=[self.algorithm],
                audience="hostel-api",
                issuer="hostel-management-system"
            )
            
            # Validate token type
            if payload.get("type") != token_type:
                raise InvalidCredentialsException("Invalid token type")
            
            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
                raise TokenExpiredException("Token has expired")
            
            return payload
            
        except JWTError as e:
            logger.warning(f"JWT decode error: {str(e)}")
            raise InvalidCredentialsException("Invalid token")
        except Exception as e:
            logger.error(f"Token decode error: {str(e)}")
            raise InvalidCredentialsException("Token validation failed")

class TokenGenerator:
    """JWT token generation utility"""
    
    def __init__(self, jwt_manager: JWTManager):
        self.jwt_manager = jwt_manager
    
    def generate_user_tokens(
        self, 
        user_id: str, 
        user_role: UserRole, 
        permissions: Optional[Dict] = None,
        device_id: Optional[str] = None,
        hostel_context: Optional[Dict] = None
    ) -> Dict[str, str]:
        """Generate both access and refresh tokens for user"""
        
        # Prepare access token payload
        access_payload = {
            "sub": user_id,
            "role": str(user_role),
            "permissions": permissions or {},
        }
        
        # Add hostel context if available
        if hostel_context:
            access_payload["hostel_context"] = hostel_context
        
        # Generate tokens
        access_token = self.jwt_manager.create_access_token(access_payload)
        refresh_token = self.jwt_manager.create_refresh_token(user_id, device_id)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.jwt_manager.access_token_expire_minutes * 60
        }
    
    def generate_service_token(
        self, 
        service_name: str, 
        permissions: List[str],
        expires_minutes: int = 60
    ) -> str:
        """Generate service-to-service authentication token"""
        payload = {
            "sub": service_name,
            "type": "service",
            "permissions": permissions,
            "service": True
        }
        
        expires_delta = timedelta(minutes=expires_minutes)
        return self.jwt_manager.create_access_token(payload, expires_delta)
    
    def generate_temporary_token(
        self, 
        user_id: str, 
        purpose: str,
        expires_minutes: int = 15,
        additional_claims: Optional[Dict] = None
    ) -> str:
        """Generate temporary token for specific purposes (password reset, email verification, etc.)"""
        payload = {
            "sub": user_id,
            "type": "temporary",
            "purpose": purpose,
            "temp": True
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        expires_delta = timedelta(minutes=expires_minutes)
        return self.jwt_manager.create_access_token(payload, expires_delta)

class TokenValidator:
    """JWT token validation utility"""
    
    def __init__(self, jwt_manager: JWTManager):
        self.jwt_manager = jwt_manager
        self.token_blacklist = set()  # In production, use Redis or database
    
    def validate_access_token(self, token: str) -> Dict[str, Any]:
        """Validate access token and return payload"""
        # Check if token is blacklisted
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        if token_hash in self.token_blacklist:
            raise InvalidCredentialsException("Token has been revoked")
        
        # Decode and validate
        payload = self.jwt_manager.decode_token(token, "access")
        
        # Additional validation checks
        self._validate_token_claims(payload)
        
        return payload
    
    def validate_refresh_token(self, token: str) -> Dict[str, Any]:
        """Validate refresh token and return payload"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        if token_hash in self.token_blacklist:
            raise InvalidCredentialsException("Refresh token has been revoked")
        
        payload = self.jwt_manager.decode_token(token, "refresh")
        return payload
    
    def validate_temporary_token(
        self, 
        token: str, 
        expected_purpose: str
    ) -> Dict[str, Any]:
        """Validate temporary token for specific purpose"""
        payload = self.jwt_manager.decode_token(token, "access")
        
        if payload.get("type") != "temporary":
            raise InvalidCredentialsException("Invalid token type")
        
        if payload.get("purpose") != expected_purpose:
            raise InvalidCredentialsException("Token purpose mismatch")
        
        return payload
    
    def _validate_token_claims(self, payload: Dict[str, Any]):
        """Validate token claims"""
        required_claims = ["sub", "iat", "exp", "jti"]
        
        for claim in required_claims:
            if claim not in payload:
                raise InvalidCredentialsException(f"Missing required claim: {claim}")
        
        # Validate user ID format
        user_id = payload.get("sub")
        if not user_id or len(user_id) < 10:
            raise InvalidCredentialsException("Invalid user ID in token")

class RefreshTokenManager:
    """Refresh token management utility"""
    
    def __init__(self, jwt_manager: JWTManager, token_validator: TokenValidator):
        self.jwt_manager = jwt_manager
        self.token_validator = token_validator
        self.refresh_token_store = {}  # In production, use database
    
    def refresh_access_token(
        self, 
        refresh_token: str, 
        current_access_token: Optional[str] = None
    ) -> Dict[str, str]:
        """Refresh access token using refresh token"""
        try:
            # Validate refresh token
            refresh_payload = self.token_validator.validate_refresh_token(refresh_token)
            user_id = refresh_payload["sub"]
            
            # Check if refresh token is stored (active)
            if not self._is_refresh_token_active(refresh_token):
                raise InvalidCredentialsException("Refresh token is not active")
            
            # Get user information (in production, query database)
            user_info = self._get_user_info(user_id)
            
            # Generate new access token
            access_payload = {
                "sub": user_id,
                "role": user_info["role"],
                "permissions": user_info.get("permissions", {})
            }
            
            new_access_token = self.jwt_manager.create_access_token(access_payload)
            
            # Optionally rotate refresh token
            new_refresh_token = None
            if self._should_rotate_refresh_token(refresh_payload):
                new_refresh_token = self.jwt_manager.create_refresh_token(
                    user_id, 
                    refresh_payload.get("device_id")
                )
                # Invalidate old refresh token
                self._invalidate_refresh_token(refresh_token)
                # Store new refresh token
                self._store_refresh_token(new_refresh_token, user_id)
            
            # Blacklist old access token if provided
            if current_access_token:
                self.token_validator.token_blacklist.add(
                    hashlib.sha256(current_access_token.encode()).hexdigest()
                )
            
            result = {
                "access_token": new_access_token,
                "token_type": "bearer",
                "expires_in": self.jwt_manager.access_token_expire_minutes * 60
            }
            
            if new_refresh_token:
                result["refresh_token"] = new_refresh_token
            
            logger.info(f"Access token refreshed for user: {user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            raise InvalidCredentialsException("Token refresh failed")
    
    def _is_refresh_token_active(self, refresh_token: str) -> bool:
        """Check if refresh token is active"""
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        return token_hash in self.refresh_token_store
    
    def _store_refresh_token(self, refresh_token: str, user_id: str):
        """Store refresh token"""
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        self.refresh_token_store[token_hash] = {
            "user_id": user_id,
            "created_at": time.time()
        }
    
    def _invalidate_refresh_token(self, refresh_token: str):
        """Invalidate refresh token"""
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        if token_hash in self.refresh_token_store:
            del self.refresh_token_store[token_hash]
    
    def _should_rotate_refresh_token(self, refresh_payload: Dict) -> bool:
        """Determine if refresh token should be rotated"""
        # Rotate if token is more than halfway through its lifetime
        exp = refresh_payload.get("exp")
        iat = refresh_payload.get("iat")
        
        if exp and iat:
            total_lifetime = exp - iat
            current_age = time.time() - iat
            return current_age > (total_lifetime * 0.5)
        
        return False
    
    def _get_user_info(self, user_id: str) -> Dict:
        """Get user information for token refresh"""
        # In production, this would query the database
        return {
            "role": "student",  # Default role
            "permissions": {}
        }

class TokenBlacklistManager:
    """Token blacklisting and revocation manager"""
    
    def __init__(self):
        self.blacklisted_tokens = set()
        self.cleanup_interval = 3600  # 1 hour
        self.last_cleanup = time.time()
    
    def blacklist_token(self, token: str, reason: str = "revoked"):
        """Add token to blacklist"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        self.blacklisted_tokens.add(token_hash)
        
        logger.info(f"Token blacklisted: {token_hash[:16]}... (reason: {reason})")
    
    def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted"""
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        return token_hash in self.blacklisted_tokens
    
    def revoke_user_tokens(self, user_id: str):
        """Revoke all tokens for a specific user"""
        # In production, this would query database for user's tokens
        # and add them all to blacklist
        logger.info(f"All tokens revoked for user: {user_id}")
    
    def cleanup_expired_tokens(self):
        """Clean up expired tokens from blacklist"""
        current_time = time.time()
        
        if current_time - self.last_cleanup > self.cleanup_interval:
            # In production, remove tokens that are already expired
            # from the blacklist to save memory
            self.last_cleanup = current_time
            logger.debug("Blacklist cleanup completed")

class ClaimsExtractor:
    """JWT claims extraction utility"""
    
    @staticmethod
    def extract_user_id(token_payload: Dict[str, Any]) -> str:
        """Extract user ID from token payload"""
        return token_payload.get("sub", "")
    
    @staticmethod
    def extract_user_role(token_payload: Dict[str, Any]) -> Optional[UserRole]:
        """Extract user role from token payload"""
        role_str = token_payload.get("role")
        if role_str:
            try:
                return UserRole(role_str)
            except ValueError:
                return None
        return None
    
    @staticmethod
    def extract_permissions(token_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract permissions from token payload"""
        return token_payload.get("permissions", {})
    
    @staticmethod
    def extract_hostel_context(token_payload: Dict[str, Any]) -> Optional[Dict]:
        """Extract hostel context from token payload"""
        return token_payload.get("hostel_context")
    
    @staticmethod
    def extract_device_id(token_payload: Dict[str, Any]) -> Optional[str]:
        """Extract device ID from token payload"""
        return token_payload.get("device_id")
    
    @staticmethod
    def extract_token_metadata(token_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract token metadata"""
        return {
            "jti": token_payload.get("jti"),
            "iat": token_payload.get("iat"),
            "exp": token_payload.get("exp"),
            "type": token_payload.get("type"),
            "iss": token_payload.get("iss"),
            "aud": token_payload.get("aud")
        }

class TokenRotationManager:
    """Token rotation and security manager"""
    
    def __init__(self, jwt_manager: JWTManager):
        self.jwt_manager = jwt_manager
        self.rotation_threshold_hours = 12  # Rotate tokens every 12 hours
    
    def should_rotate_token(self, token_payload: Dict[str, Any]) -> bool:
        """Check if token should be rotated"""
        iat = token_payload.get("iat")
        if not iat:
            return True
        
        # Convert to timestamp if needed
        if isinstance(iat, datetime):
            iat = iat.timestamp()
        
        hours_since_issued = (time.time() - iat) / 3600
        return hours_since_issued > self.rotation_threshold_hours
    
    def rotate_token(
        self, 
        current_token: str, 
        token_type: str = "access"
    ) -> str:
        """Rotate token with new expiration"""
        try:
            payload = self.jwt_manager.decode_token(current_token, token_type)
            
            # Create new payload with fresh timestamps
            new_payload = payload.copy()
            new_payload.pop("iat", None)
            new_payload.pop("exp", None)
            new_payload.pop("jti", None)
            
            # Generate new token
            if token_type == "access":
                return self.jwt_manager.create_access_token(new_payload)
            else:
                user_id = payload.get("sub")
                device_id = payload.get("device_id")
                return self.jwt_manager.create_refresh_token(user_id, device_id)
                
        except Exception as e:
            logger.error(f"Token rotation failed: {str(e)}")
            raise InvalidCredentialsException("Token rotation failed")