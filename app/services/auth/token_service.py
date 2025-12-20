"""
Token Service
Handles JWT token generation, validation, refresh, and management.
"""

import jwt
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.auth import (
    SessionTokenRepository,
    RefreshTokenRepository,
    BlacklistedTokenRepository,
)
from app.core.exceptions import (
    InvalidTokenError,
    ExpiredTokenError,
    TokenRevokedError,
)


class TokenService:
    """
    Service for JWT token operations including generation, validation, and refresh.
    """

    def __init__(self, db: Session):
        self.db = db
        self.session_token_repo = SessionTokenRepository(db)
        self.refresh_token_repo = RefreshTokenRepository(db)
        self.blacklist_repo = BlacklistedTokenRepository(db)
        
        # Token configuration
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = settings.REFRESH_TOKEN_EXPIRE_DAYS

    # ==================== Token Generation ====================

    def create_access_token(
        self,
        user_id: UUID,
        session_id: UUID,
        scopes: Optional[list] = None,
        extra_claims: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create JWT access token.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            scopes: Token scopes/permissions
            extra_claims: Additional claims to include
            
        Returns:
            Dictionary with token and metadata
        """
        # Generate unique token ID
        jti = str(uuid4())
        
        # Calculate expiration
        expires_delta = timedelta(minutes=self.access_token_expire_minutes)
        expire = datetime.utcnow() + expires_delta
        
        # Build token payload
        payload = {
            "jti": jti,
            "sub": str(user_id),
            "session_id": str(session_id),
            "type": "access",
            "exp": expire,
            "iat": datetime.utcnow(),
            "scopes": scopes or [],
        }
        
        # Add extra claims
        if extra_claims:
            payload.update(extra_claims)
        
        # Encode token
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        # Store token in database
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        self.session_token_repo.create_token(
            session_id=session_id,
            jti=jti,
            token_hash=token_hash,
            expires_in_minutes=self.access_token_expire_minutes,
            scopes=scopes
        )
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": int(expires_delta.total_seconds()),
            "jti": jti
        }

    def create_refresh_token(
        self,
        user_id: UUID,
        session_id: UUID,
        family_id: Optional[str] = None,
        parent_token_id: Optional[UUID] = None,
        is_remember_me: bool = False
    ) -> Dict[str, Any]:
        """
        Create JWT refresh token with rotation support.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            family_id: Token family ID for rotation tracking
            parent_token_id: Parent token in rotation chain
            is_remember_me: Extended expiration flag
            
        Returns:
            Dictionary with token and metadata
        """
        # Generate unique token ID and family ID
        jti = str(uuid4())
        if not family_id:
            family_id = str(uuid4())
        
        # Calculate expiration
        expire_days = self.refresh_token_expire_days
        if is_remember_me:
            expire_days = 30  # Extended expiration for remember me
        
        expires_delta = timedelta(days=expire_days)
        expire = datetime.utcnow() + expires_delta
        
        # Build token payload
        payload = {
            "jti": jti,
            "sub": str(user_id),
            "session_id": str(session_id),
            "family_id": family_id,
            "type": "refresh",
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        
        # Encode token
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        # Store token in database
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        refresh_token = self.refresh_token_repo.create_token(
            session_id=session_id,
            jti=jti,
            token_hash=token_hash,
            family_id=family_id,
            expires_in_days=expire_days,
            parent_token_id=parent_token_id
        )
        
        return {
            "refresh_token": token,
            "expires_in": int(expires_delta.total_seconds()),
            "jti": jti,
            "family_id": family_id
        }

    def create_token_pair(
        self,
        user_id: UUID,
        session_id: UUID,
        scopes: Optional[list] = None,
        is_remember_me: bool = False
    ) -> Dict[str, Any]:
        """
        Create access and refresh token pair.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            scopes: Token scopes
            is_remember_me: Extended session flag
            
        Returns:
            Dictionary with both tokens
        """
        access_token_data = self.create_access_token(
            user_id=user_id,
            session_id=session_id,
            scopes=scopes
        )
        
        refresh_token_data = self.create_refresh_token(
            user_id=user_id,
            session_id=session_id,
            is_remember_me=is_remember_me
        )
        
        return {
            **access_token_data,
            **refresh_token_data
        }

    # ==================== Token Validation ====================

    def decode_token(
        self,
        token: str,
        verify_exp: bool = True
    ) -> Dict[str, Any]:
        """
        Decode and validate JWT token.
        
        Args:
            token: JWT token string
            verify_exp: Whether to verify expiration
            
        Returns:
            Decoded token payload
            
        Raises:
            InvalidTokenError: If token is invalid
            ExpiredTokenError: If token is expired
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": verify_exp}
            )
            return payload
            
        except jwt.ExpiredSignatureError:
            raise ExpiredTokenError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError(f"Invalid token: {str(e)}")

    def validate_access_token(self, token: str) -> Dict[str, Any]:
        """
        Validate access token and check blacklist.
        
        Args:
            token: Access token string
            
        Returns:
            Token payload if valid
            
        Raises:
            InvalidTokenError: If token is invalid
            ExpiredTokenError: If token is expired
            TokenRevokedError: If token is revoked
        """
        # Decode token
        payload = self.decode_token(token)
        
        # Verify token type
        if payload.get("type") != "access":
            raise InvalidTokenError("Invalid token type")
        
        jti = payload.get("jti")
        
        # Check if token is blacklisted
        if self.blacklist_repo.is_blacklisted(jti):
            raise TokenRevokedError("Token has been revoked")
        
        # Check if token exists and is valid in database
        if not self.session_token_repo.is_token_valid(jti):
            raise TokenRevokedError("Token is not valid")
        
        return payload

    def validate_refresh_token(self, token: str) -> Dict[str, Any]:
        """
        Validate refresh token and check for reuse.
        
        Args:
            token: Refresh token string
            
        Returns:
            Token payload if valid
            
        Raises:
            InvalidTokenError: If token is invalid
            ExpiredTokenError: If token is expired
            TokenRevokedError: If token is revoked or reused
        """
        # Decode token
        payload = self.decode_token(token)
        
        # Verify token type
        if payload.get("type") != "refresh":
            raise InvalidTokenError("Invalid token type")
        
        jti = payload.get("jti")
        
        # Check if token is blacklisted
        if self.blacklist_repo.is_blacklisted(jti):
            raise TokenRevokedError("Token has been revoked")
        
        # Check for token reuse (security breach)
        if self.refresh_token_repo.detect_token_reuse(jti):
            raise TokenRevokedError(
                "Token reuse detected. All tokens in this family have been revoked."
            )
        
        # Check if token is valid
        if not self.refresh_token_repo.is_token_valid(jti):
            raise TokenRevokedError("Token is not valid")
        
        return payload

    # ==================== Token Refresh ====================

    def refresh_tokens(
        self,
        refresh_token: str
    ) -> Dict[str, Any]:
        """
        Refresh access token using refresh token (with rotation).
        
        Args:
            refresh_token: Current refresh token
            
        Returns:
            New token pair
            
        Raises:
            InvalidTokenError: If refresh token is invalid
            TokenRevokedError: If token is revoked or reused
        """
        # Validate refresh token
        payload = self.validate_refresh_token(refresh_token)
        
        user_id = UUID(payload["sub"])
        session_id = UUID(payload["session_id"])
        family_id = payload["family_id"]
        jti = payload["jti"]
        
        # Mark current refresh token as used
        current_token = self.refresh_token_repo.use_token(jti)
        if not current_token:
            raise TokenRevokedError("Unable to use refresh token")
        
        # Create new access token
        access_token_data = self.create_access_token(
            user_id=user_id,
            session_id=session_id
        )
        
        # Create new refresh token (rotation)
        refresh_token_data = self.create_refresh_token(
            user_id=user_id,
            session_id=session_id,
            family_id=family_id,
            parent_token_id=current_token.id
        )
        
        return {
            **access_token_data,
            **refresh_token_data
        }

    # ==================== Token Revocation ====================

    def revoke_token(
        self,
        jti: str,
        token_type: str,
        user_id: Optional[UUID] = None,
        reason: str = "Token revoked",
        revoked_by_user_id: Optional[UUID] = None
    ) -> bool:
        """
        Revoke a specific token.
        
        Args:
            jti: JWT ID
            token_type: Token type (access/refresh)
            user_id: User identifier
            reason: Revocation reason
            revoked_by_user_id: Who revoked the token
            
        Returns:
            Success status
        """
        # Get token expiration
        if token_type == "access":
            token = self.session_token_repo.find_by_jti(jti)
        else:
            token = self.refresh_token_repo.find_by_jti(jti)
        
        if not token:
            return False
        
        # Add to blacklist
        self.blacklist_repo.blacklist_token(
            jti=jti,
            token_type=token_type,
            token_hash=token.token_hash,
            user_id=user_id,
            expires_at=token.expires_at,
            revocation_reason=reason,
            revoked_by_user_id=revoked_by_user_id
        )
        
        # Revoke in repository
        if token_type == "access":
            self.session_token_repo.revoke_token(jti, reason)
        else:
            # For refresh tokens, revoke the entire family
            refresh_token = self.refresh_token_repo.find_by_jti(jti)
            if refresh_token:
                self.refresh_token_repo.revoke_token_family(
                    refresh_token.family_id,
                    reason
                )
        
        return True

    def revoke_session_tokens(
        self,
        session_id: UUID,
        reason: str = "Session terminated"
    ) -> int:
        """
        Revoke all tokens for a session.
        
        Args:
            session_id: Session identifier
            reason: Revocation reason
            
        Returns:
            Number of tokens revoked
        """
        # Get all session tokens
        session_tokens = self.db.query(
            self.session_token_repo.model
        ).filter_by(session_id=session_id).all()
        
        refresh_tokens = self.db.query(
            self.refresh_token_repo.model
        ).filter_by(session_id=session_id).all()
        
        # Revoke each token
        for token in session_tokens:
            self.revoke_token(
                jti=token.jti,
                token_type="access",
                reason=reason
            )
        
        for token in refresh_tokens:
            self.revoke_token(
                jti=token.jti,
                token_type="refresh",
                reason=reason
            )
        
        return len(session_tokens) + len(refresh_tokens)

    def revoke_all_user_tokens(
        self,
        user_id: UUID,
        reason: str = "User requested token revocation"
    ) -> int:
        """
        Revoke all tokens for a user.
        
        Args:
            user_id: User identifier
            reason: Revocation reason
            
        Returns:
            Number of tokens revoked
        """
        from app.models.auth import UserSession
        
        # Get all user sessions
        sessions = self.db.query(UserSession).filter_by(
            user_id=user_id,
            is_active=True
        ).all()
        
        total_revoked = 0
        for session in sessions:
            total_revoked += self.revoke_session_tokens(session.id, reason)
        
        return total_revoked

    # ==================== Token Information ====================

    def get_token_info(self, token: str) -> Dict[str, Any]:
        """
        Get information about a token without full validation.
        
        Args:
            token: JWT token string
            
        Returns:
            Token information
        """
        try:
            # Decode without verification to get info
            payload = self.decode_token(token, verify_exp=False)
            
            jti = payload.get("jti")
            token_type = payload.get("type")
            
            # Check blacklist status
            is_blacklisted = self.blacklist_repo.is_blacklisted(jti)
            
            # Check expiration
            exp = payload.get("exp")
            is_expired = datetime.utcnow() > datetime.fromtimestamp(exp)
            
            return {
                "jti": jti,
                "type": token_type,
                "user_id": payload.get("sub"),
                "session_id": payload.get("session_id"),
                "issued_at": datetime.fromtimestamp(payload.get("iat")),
                "expires_at": datetime.fromtimestamp(exp),
                "is_expired": is_expired,
                "is_blacklisted": is_blacklisted,
                "scopes": payload.get("scopes", [])
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "valid": False
            }

    def verify_token_scopes(
        self,
        token: str,
        required_scopes: list
    ) -> bool:
        """
        Verify token has required scopes.
        
        Args:
            token: JWT token string
            required_scopes: List of required scopes
            
        Returns:
            True if token has all required scopes
        """
        try:
            payload = self.validate_access_token(token)
            token_scopes = set(payload.get("scopes", []))
            required = set(required_scopes)
            
            return required.issubset(token_scopes)
            
        except Exception:
            return False

    # ==================== Cleanup ====================

    def cleanup_expired_tokens(self, days_old: int = 7) -> Dict[str, int]:
        """
        Clean up expired tokens from database.
        
        Args:
            days_old: Remove tokens expired more than this many days ago
            
        Returns:
            Dictionary with cleanup counts
        """
        return {
            "access_tokens_cleaned": self.session_token_repo.cleanup_expired_tokens(days_old),
            "refresh_tokens_cleaned": self.refresh_token_repo.cleanup_expired_tokens(days_old),
            "blacklisted_tokens_cleaned": self.blacklist_repo.cleanup_expired_tokens(days_old)
        }