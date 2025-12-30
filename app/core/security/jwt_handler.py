"""
JWT token management utilities.

Handles JWT token creation, validation, and refresh operations.
"""

import jwt
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Union
from uuid import UUID
import secrets

logger = logging.getLogger(__name__)


class JWTManager:
    """
    JWT token manager for authentication.
    
    Handles creation, validation, and refresh of JWT tokens.
    Supports both access and refresh tokens with different expiration times.
    """
    
    DEFAULT_ALGORITHM = "HS256"
    DEFAULT_ACCESS_TOKEN_EXPIRE_HOURS = 1
    DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS = 7
    
    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: str = DEFAULT_ALGORITHM,
        access_token_expire_hours: int = DEFAULT_ACCESS_TOKEN_EXPIRE_HOURS,
        refresh_token_expire_days: int = DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS,
    ):
        """
        Initialize JWT manager.
        
        Args:
            secret_key: Secret key for signing tokens (auto-generated if None)
            algorithm: JWT algorithm (default: HS256)
            access_token_expire_hours: Access token expiration in hours
            refresh_token_expire_days: Refresh token expiration in days
        """
        self.secret_key = secret_key or self._generate_secret_key()
        self.algorithm = algorithm
        self.access_token_expire_hours = access_token_expire_hours
        self.refresh_token_expire_days = refresh_token_expire_days
        
        logger.info(
            f"JWT Manager initialized with algorithm {algorithm}, "
            f"access token expires in {access_token_expire_hours}h, "
            f"refresh token expires in {refresh_token_expire_days}d"
        )
    
    def create_access_token(
        self,
        user_id: Union[UUID, str],
        additional_claims: Optional[Dict[str, Any]] = None,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        Create JWT access token.
        
        Args:
            user_id: User identifier
            additional_claims: Additional claims to include
            expires_delta: Custom expiration time
            
        Returns:
            Encoded JWT token
        """
        now = datetime.now(timezone.utc)
        
        if expires_delta:
            expire = now + expires_delta
        else:
            expire = now + timedelta(hours=self.access_token_expire_hours)
        
        payload = {
            "user_id": str(user_id),
            "token_type": "access",
            "iat": now,
            "exp": expire,
            "jti": secrets.token_hex(16),  # Token ID for revocation
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        try:
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            logger.debug(f"Access token created for user {user_id}")
            return token
        except Exception as e:
            logger.error(f"Error creating access token: {e}")
            raise
    
    def create_refresh_token(
        self,
        user_id: Union[UUID, str],
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        Create JWT refresh token.
        
        Args:
            user_id: User identifier
            expires_delta: Custom expiration time
            
        Returns:
            Encoded JWT refresh token
        """
        now = datetime.now(timezone.utc)
        
        if expires_delta:
            expire = now + expires_delta
        else:
            expire = now + timedelta(days=self.refresh_token_expire_days)
        
        payload = {
            "user_id": str(user_id),
            "token_type": "refresh",
            "iat": now,
            "exp": expire,
            "jti": secrets.token_hex(16),
        }
        
        try:
            token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
            logger.debug(f"Refresh token created for user {user_id}")
            return token
        except Exception as e:
            logger.error(f"Error creating refresh token: {e}")
            raise
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token to verify
            
        Returns:
            Decoded token payload
            
        Raises:
            jwt.ExpiredSignatureError: If token is expired
            jwt.InvalidTokenError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            logger.debug(f"Token verified for user {payload.get('user_id')}")
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token verification failed: token expired")
            raise
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token verification failed: {e}")
            raise
    
    def decode_token_without_verification(self, token: str) -> Dict[str, Any]:
        """
        Decode token without verification (for debugging/inspection).
        
        Args:
            token: JWT token to decode
            
        Returns:
            Decoded payload (unverified)
        """
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except Exception as e:
            logger.error(f"Error decoding token: {e}")
            raise
    
    def refresh_access_token(self, refresh_token: str) -> str:
        """
        Create new access token from valid refresh token.
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New access token
            
        Raises:
            jwt.ExpiredSignatureError: If refresh token is expired
            jwt.InvalidTokenError: If refresh token is invalid
            ValueError: If token is not a refresh token
        """
        payload = self.verify_token(refresh_token)
        
        if payload.get("token_type") != "refresh":
            raise ValueError("Invalid token type for refresh operation")
        
        user_id = payload["user_id"]
        return self.create_access_token(user_id)
    
    def get_token_expiry(self, token: str) -> Optional[datetime]:
        """
        Get token expiration time.
        
        Args:
            token: JWT token
            
        Returns:
            Expiration datetime or None if invalid
        """
        try:
            payload = self.decode_token_without_verification(token)
            exp_timestamp = payload.get("exp")
            if exp_timestamp:
                return datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        except Exception:
            pass
        return None
    
    def is_token_expired(self, token: str) -> bool:
        """
        Check if token is expired.
        
        Args:
            token: JWT token to check
            
        Returns:
            True if expired, False otherwise
        """
        expiry = self.get_token_expiry(token)
        if expiry:
            return datetime.now(timezone.utc) >= expiry
        return True
    
    def get_user_id_from_token(self, token: str) -> Optional[str]:
        """
        Extract user ID from token without full verification.
        
        Args:
            token: JWT token
            
        Returns:
            User ID string or None if invalid
        """
        try:
            payload = self.decode_token_without_verification(token)
            return payload.get("user_id")
        except Exception:
            return None
    
    @staticmethod
    def _generate_secret_key() -> str:
        """Generate a secure random secret key."""
        return secrets.token_urlsafe(32)
    
    def create_token_pair(
        self,
        user_id: Union[UUID, str],
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Create both access and refresh tokens.
        
        Args:
            user_id: User identifier
            additional_claims: Additional claims for access token
            
        Returns:
            Dictionary with access_token and refresh_token
        """
        access_token = self.create_access_token(user_id, additional_claims)
        refresh_token = self.create_refresh_token(user_id)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }