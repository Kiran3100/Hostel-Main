# app/services/common/security.py
"""
Security utilities for authentication and authorization.

Provides password hashing with bcrypt and JWT token management
with comprehensive validation and error handling.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional
from uuid import UUID
import hashlib

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.schemas.common.enums import UserRole

from .errors import AuthenticationError, ValidationError


# ------------------------------------------------------------------ #
# Configuration
# ------------------------------------------------------------------ #

_pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Configurable work factor
)


@dataclass(frozen=True)
class JWTSettings:
    """
    JWT configuration settings.

    Example:
        >>> jwt_settings = JWTSettings(
        ...     secret_key=settings.JWT_SECRET_KEY,
        ...     algorithm="HS256",
        ...     access_token_expires_minutes=60,
        ...     refresh_token_expires_days=30,
        ... )
    """
    secret_key: str
    algorithm: str = "HS256"
    access_token_expires_minutes: int = 60
    refresh_token_expires_days: int = 30
    issuer: Optional[str] = None
    audience: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate settings after initialization."""
        if not self.secret_key:
            raise ValueError("JWT secret_key cannot be empty")
        if self.access_token_expires_minutes <= 0:
            raise ValueError("access_token_expires_minutes must be positive")
        if self.refresh_token_expires_days <= 0:
            raise ValueError("refresh_token_expires_days must be positive")


# ------------------------------------------------------------------ #
# Password hashing
# ------------------------------------------------------------------ #

def _prepare_password_for_bcrypt(password: str) -> str:
    """
    Prepare a password for bcrypt by handling the 72-byte limit.
    
    For passwords that might exceed the limit, we use a SHA-256 hash
    which produces a fixed-length output that's well under the limit.
    
    Args:
        password: Original password
        
    Returns:
        Password suitable for bcrypt
    """
    # Check if password might exceed bcrypt's 72-byte limit when encoded
    if len(password.encode('utf-8')) > 71:
        # Use SHA-256 to get a fixed-length representation
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
    return password


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.

    Args:
        password: Plaintext password

    Returns:
        Hashed password string

    Raises:
        ValidationError: If password is empty

    Example:
        >>> hashed = hash_password("secure_password123")
    """
    if not password:
        raise ValidationError("Password cannot be empty", field="password")
    
    # Pre-process password to handle bcrypt's 72-byte limit
    safe_password = _prepare_password_for_bcrypt(password)
    
    return _pwd_context.hash(safe_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a stored hash.

    Args:
        plain_password: Plaintext password to verify
        hashed_password: Stored password hash

    Returns:
        True if password matches, False otherwise

    Example:
        >>> if verify_password(input_password, stored_hash):
        ...     # Password is correct
    """
    if not plain_password or not hashed_password:
        return False
    
    try:
        # Pre-process password the same way as during hashing
        safe_password = _prepare_password_for_bcrypt(plain_password)
        
        return _pwd_context.verify(safe_password, hashed_password)
    except Exception:
        # Handle any unexpected errors from passlib
        return False


def needs_rehash(hashed_password: str) -> bool:
    """
    Check if a password hash needs to be rehashed.

    This is useful when updating hashing parameters or deprecating schemes.

    Args:
        hashed_password: Stored password hash

    Returns:
        True if hash should be regenerated

    Example:
        >>> if needs_rehash(user.hashed_password):
        ...     user.hashed_password = hash_password(new_password)
    """
    try:
        return _pwd_context.needs_update(hashed_password)
    except Exception:
        return True


# ------------------------------------------------------------------ #
# JWT utilities
# ------------------------------------------------------------------ #

def _utcnow() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class TokenDecodeError(AuthenticationError):
    """Raised when JWT token decoding fails."""
    
    def __init__(self, message: str = "Invalid or expired token") -> None:
        super().__init__(message)


class TokenExpiredError(TokenDecodeError):
    """Raised when JWT token has expired."""
    
    def __init__(self) -> None:
        super().__init__("Token has expired")


class InvalidTokenTypeError(TokenDecodeError):
    """Raised when token type doesn't match expected type."""
    
    def __init__(self, expected: str, actual: Optional[str]) -> None:
        super().__init__(f"Expected {expected} token, got {actual}")
        self.expected = expected
        self.actual = actual


def create_access_token(
    *,
    subject: UUID,
    email: str,
    role: UserRole,
    jwt_settings: JWTSettings,
    additional_claims: Optional[dict[str, Any]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject: User ID
        email: User email
        role: User role
        jwt_settings: JWT configuration
        additional_claims: Optional extra claims to embed
        expires_delta: Custom expiry (overrides default)

    Returns:
        Encoded JWT token string

    Example:
        >>> token = create_access_token(
        ...     subject=user.id,
        ...     email=user.email,
        ...     role=user.role,
        ...     jwt_settings=settings,
        ... )
    """
    now = _utcnow()
    
    if expires_delta is None:
        expires_delta = timedelta(minutes=jwt_settings.access_token_expires_minutes)
    
    expire = now + expires_delta

    payload: dict[str, Any] = {
        "sub": str(subject),
        "user_id": str(subject),
        "email": email,
        "role": role.value,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }

    # Add optional claims
    if jwt_settings.issuer:
        payload["iss"] = jwt_settings.issuer
    if jwt_settings.audience:
        payload["aud"] = jwt_settings.audience
    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(
        payload,
        jwt_settings.secret_key,
        algorithm=jwt_settings.algorithm,
    )


def create_refresh_token(
    *,
    subject: UUID,
    jwt_settings: JWTSettings,
    additional_claims: Optional[dict[str, Any]] = None,
) -> str:
    """
    Create a signed JWT refresh token.

    Refresh tokens have minimal claims for security.

    Args:
        subject: User ID
        jwt_settings: JWT configuration
        additional_claims: Optional extra claims

    Returns:
        Encoded JWT refresh token string

    Example:
        >>> refresh = create_refresh_token(
        ...     subject=user.id,
        ...     jwt_settings=settings,
        ... )
    """
    now = _utcnow()
    expire = now + timedelta(days=jwt_settings.refresh_token_expires_days)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "user_id": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "refresh",
    }

    if jwt_settings.issuer:
        payload["iss"] = jwt_settings.issuer
    if jwt_settings.audience:
        payload["aud"] = jwt_settings.audience
    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(
        payload,
        jwt_settings.secret_key,
        algorithm=jwt_settings.algorithm,
    )


def decode_token(
    token: str,
    jwt_settings: JWTSettings,
    *,
    expected_type: Optional[Literal["access", "refresh"]] = None,
    verify_exp: bool = True,
) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string
        jwt_settings: JWT configuration
        expected_type: Expected token type ('access' or 'refresh')
        verify_exp: Whether to verify expiration

    Returns:
        Decoded token payload

    Raises:
        TokenDecodeError: If token is invalid
        TokenExpiredError: If token has expired
        InvalidTokenTypeError: If token type doesn't match expected

    Example:
        >>> payload = decode_token(
        ...     token,
        ...     jwt_settings,
        ...     expected_type="access",
        ... )
        >>> user_id = UUID(payload["user_id"])
    """
    try:
        options = {"verify_exp": verify_exp}
        
        payload = jwt.decode(
            token,
            jwt_settings.secret_key,
            algorithms=[jwt_settings.algorithm],
            options=options,
            issuer=jwt_settings.issuer,
            audience=jwt_settings.audience,
        )

        # Validate token type if specified
        if expected_type is not None:
            actual_type = payload.get("type")
            if actual_type != expected_type:
                raise InvalidTokenTypeError(expected_type, actual_type)

        return payload

    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except JWTError as exc:
        raise TokenDecodeError("Invalid or malformed token") from exc


def extract_user_id(token: str, jwt_settings: JWTSettings) -> UUID:
    """
    Extract user ID from a JWT token.

    Args:
        token: JWT token string
        jwt_settings: JWT configuration

    Returns:
        User ID as UUID

    Raises:
        TokenDecodeError: If token is invalid or missing user_id

    Example:
        >>> user_id = extract_user_id(token, jwt_settings)
    """
    payload = decode_token(token, jwt_settings)
    
    user_id_str = payload.get("user_id") or payload.get("sub")
    if not user_id_str:
        raise TokenDecodeError("Token missing user identifier")
    
    try:
        return UUID(user_id_str)
    except (ValueError, TypeError) as exc:
        raise TokenDecodeError("Invalid user ID format in token") from exc


def extract_user_role(token: str, jwt_settings: JWTSettings) -> UserRole:
    """
    Extract user role from a JWT token.

    Args:
        token: JWT token string
        jwt_settings: JWT configuration

    Returns:
        User role enum

    Raises:
        TokenDecodeError: If token is invalid or missing role

    Example:
        >>> role = extract_user_role(token, jwt_settings)
    """
    payload = decode_token(token, jwt_settings, expected_type="access")
    
    role_str = payload.get("role")
    if not role_str:
        raise TokenDecodeError("Token missing role claim")
    
    try:
        return UserRole(role_str)
    except ValueError as exc:
        raise TokenDecodeError(f"Invalid role in token: {role_str}") from exc


def verify_token_freshness(
    token: str,
    jwt_settings: JWTSettings,
    max_age_minutes: int,
) -> bool:
    """
    Check if a token is fresh (issued recently).

    Useful for sensitive operations requiring recent authentication.

    Args:
        token: JWT token string
        jwt_settings: JWT configuration
        max_age_minutes: Maximum age in minutes

    Returns:
        True if token is fresh

    Example:
        >>> if verify_token_freshness(token, jwt_settings, max_age_minutes=15):
        ...     # Allow sensitive operation
    """
    try:
        payload = decode_token(token, jwt_settings)
        iat = payload.get("iat")
        
        if not iat:
            return False
        
        issued_at = datetime.fromtimestamp(iat, tz=timezone.utc)
        age = _utcnow() - issued_at
        
        return age <= timedelta(minutes=max_age_minutes)
    
    except TokenDecodeError:
        return False