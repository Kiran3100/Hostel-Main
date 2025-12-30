"""
Authentication utilities and standalone functions.
"""

import logging
import re
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import jwt
from datetime import datetime, timezone, timedelta

from .jwt_handler import JWTManager
from .password_hasher import PasswordHasher

logger = logging.getLogger(__name__)

# Initialize JWT manager and password hasher (will be configured after settings import)
jwt_manager = None
password_hasher = None


def _get_jwt_manager() -> JWTManager:
    """Get or create JWT manager with current settings"""
    global jwt_manager
    if jwt_manager is None:
        try:
            from ..config import settings
            jwt_manager = JWTManager(
                secret_key=settings.security.SECRET_KEY,
                algorithm=settings.security.ALGORITHM,
                access_token_expire_hours=settings.security.ACCESS_TOKEN_EXPIRE_MINUTES / 60,  # Convert minutes to hours
                refresh_token_expire_days=settings.security.REFRESH_TOKEN_EXPIRE_DAYS
            )
        except ImportError:
            logger.warning("Could not import settings, using default JWT manager")
            jwt_manager = JWTManager()
    return jwt_manager


def _get_password_hasher() -> PasswordHasher:
    """Get or create password hasher"""
    global password_hasher
    if password_hasher is None:
        password_hasher = PasswordHasher()
    return password_hasher


def sanitize_device_id(device_id: str) -> Optional[str]:
    """
    Sanitize device ID for security and consistency.
    
    Args:
        device_id: Raw device identifier
        
    Returns:
        Sanitized device ID or None if invalid
    """
    if not device_id or not isinstance(device_id, str):
        return None
    
    try:
        # Remove whitespace and convert to lowercase
        sanitized = device_id.strip().lower()
        
        # Remove any non-alphanumeric characters except hyphens and underscores
        sanitized = re.sub(r'[^a-z0-9\-_]', '', sanitized)
        
        # Ensure reasonable length (prevent extremely long device IDs)
        if len(sanitized) > 100 or len(sanitized) < 3:
            logger.warning(f"Invalid device ID length: {len(sanitized)}")
            return None
        
        # Prevent SQL injection patterns and suspicious content
        suspicious_patterns = [
            'script', 'select', 'insert', 'update', 'delete', 'drop',
            'union', 'exec', 'javascript', '<', '>', '"', "'"
        ]
        
        sanitized_lower = sanitized.lower()
        for pattern in suspicious_patterns:
            if pattern in sanitized_lower:
                logger.warning(f"Suspicious pattern detected in device ID: {pattern}")
                return None
        
        # Ensure it starts with alphanumeric character
        if not sanitized or not (sanitized[0].isalnum()):
            logger.warning(f"Device ID must start with alphanumeric character")
            return None
        
        return sanitized
        
    except Exception as e:
        logger.error(f"Error sanitizing device ID: {e}")
        return None


def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify JWT token and return payload.
    
    Args:
        token: JWT token to verify
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        manager = _get_jwt_manager()
        payload = manager.verify_token(token)
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token verification failed: token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected error during token verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(token: str, db: Session) -> Optional[Dict[str, Any]]:
    """
    Get current user from token.
    
    Args:
        token: JWT token
        db: Database session
        
    Returns:
        User data or None if invalid
    """
    try:
        payload = verify_token(token)
        user_id = payload.get("user_id")
        
        if not user_id:
            return None
        
        # TODO: In a real implementation, you would fetch the user from database
        # Example database query:
        # from app.models.user import User
        # user = db.query(User).filter(User.id == user_id).first()
        # if not user or not user.is_active:
        #     return None
        # 
        # return {
        #     "id": str(user.id),
        #     "username": user.username,
        #     "email": user.email,
        #     "is_active": user.is_active,
        #     "is_admin": user.is_admin,
        #     "is_superuser": user.is_superuser,
        #     "is_verified": user.is_verified,
        #     "roles": [role.name for role in user.roles],
        #     "permissions": [perm.name for perm in user.permissions],
        #     "last_login": user.last_login.isoformat() if user.last_login else None,
        #     "hostel_id": user.hostel_id,
        #     "tenant_id": user.tenant_id,
        # }
        
        # For now, return mock user data based on token payload
        user_data = {
            "id": user_id,
            "token_type": payload.get("token_type"),
            "token_jti": payload.get("jti"),
            "iat": payload.get("iat"),
            "exp": payload.get("exp"),
            "is_active": True,  # You'd check this in the database
            "is_admin": False,  # You'd check this in the database
            "is_superuser": False,  # You'd check this in the database
            "is_verified": True,  # You'd check this in the database
            "roles": ["user"],  # You'd fetch from database
            "permissions": [],  # You'd fetch from database
            "email": f"user{user_id}@example.com",  # You'd fetch from database
            "username": f"user_{user_id}",  # You'd fetch from database
            "last_login": datetime.now(timezone.utc).isoformat(),
            "hostel_id": "main",  # You'd fetch from database
            "tenant_id": "main",  # You'd fetch from database
            "accessible_tenants": ["main"],  # You'd fetch from database
        }
        
        # Add any additional claims from the token
        additional_claims = {k: v for k, v in payload.items() 
                           if k not in ["user_id", "token_type", "iat", "exp", "jti"]}
        user_data.update(additional_claims)
        
        return user_data
        
    except HTTPException:
        # Re-raise HTTP exceptions (from verify_token)
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        return None


def create_access_token(user_id: str, additional_claims: Optional[Dict[str, Any]] = None) -> str:
    """
    Create access token for user.
    
    Args:
        user_id: User identifier
        additional_claims: Additional claims to include
        
    Returns:
        JWT access token
    """
    manager = _get_jwt_manager()
    
    # Convert minutes to hours for the JWTManager
    try:
        from ..config import settings
        expires_delta = timedelta(minutes=settings.security.ACCESS_TOKEN_EXPIRE_MINUTES)
    except ImportError:
        expires_delta = timedelta(minutes=30)  # Default to 30 minutes
    
    return manager.create_access_token(user_id, additional_claims, expires_delta)


def create_refresh_token(user_id: str) -> str:
    """
    Create refresh token for user.
    
    Args:
        user_id: User identifier
        
    Returns:
        JWT refresh token
    """
    manager = _get_jwt_manager()
    
    try:
        from ..config import settings
        expires_delta = timedelta(days=settings.security.REFRESH_TOKEN_EXPIRE_DAYS)
    except ImportError:
        expires_delta = timedelta(days=7)  # Default to 7 days
    
    return manager.create_refresh_token(user_id, expires_delta)


def create_token_pair(user_id: str, additional_claims: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """
    Create both access and refresh tokens.
    
    Args:
        user_id: User identifier
        additional_claims: Additional claims for access token
        
    Returns:
        Dictionary with access_token and refresh_token
    """
    access_token = create_access_token(user_id, additional_claims)
    refresh_token = create_refresh_token(user_id)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


def hash_password(password: str) -> str:
    """
    Hash a password.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    hasher = _get_password_hasher()
    return hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        password: Plain text password
        hashed_password: Hashed password
        
    Returns:
        True if password matches, False otherwise
    """
    hasher = _get_password_hasher()
    return hasher.verify(password, hashed_password)


def validate_password_requirements(password: str) -> Dict[str, Any]:
    """
    Validate password against security requirements.
    
    Args:
        password: Plain text password to validate
        
    Returns:
        Dict with validation results
    """
    try:
        from ..config import settings
        sec_settings = settings.security
    except ImportError:
        # Default requirements if settings not available
        sec_settings = type('obj', (object,), {
            'PASSWORD_MIN_LENGTH': 8,
            'PASSWORD_REQUIRE_UPPERCASE': True,
            'PASSWORD_REQUIRE_LOWERCASE': True,
            'PASSWORD_REQUIRE_NUMBERS': True,
            'PASSWORD_REQUIRE_SPECIAL': True,
        })()
    
    errors = []
    
    # Check minimum length
    if len(password) < sec_settings.PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {sec_settings.PASSWORD_MIN_LENGTH} characters long")
    
    # Check uppercase requirement
    if sec_settings.PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")
    
    # Check lowercase requirement
    if sec_settings.PASSWORD_REQUIRE_LOWERCASE and not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")
    
    # Check numbers requirement
    if sec_settings.PASSWORD_REQUIRE_NUMBERS and not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one number")
    
    # Check special characters requirement
    if sec_settings.PASSWORD_REQUIRE_SPECIAL:
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            errors.append("Password must contain at least one special character")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "requirements": {
            "min_length": sec_settings.PASSWORD_MIN_LENGTH,
            "require_uppercase": sec_settings.PASSWORD_REQUIRE_UPPERCASE,
            "require_lowercase": sec_settings.PASSWORD_REQUIRE_LOWERCASE,
            "require_numbers": sec_settings.PASSWORD_REQUIRE_NUMBERS,
            "require_special": sec_settings.PASSWORD_REQUIRE_SPECIAL,
        }
    }


def authenticate_user(username: str, password: str, db: Session) -> Optional[Dict[str, Any]]:
    """
    Authenticate user with username and password.
    
    Args:
        username: Username or email
        password: Plain text password
        db: Database session
        
    Returns:
        User data if authentication successful, None otherwise
    """
    try:
        # TODO: In a real implementation, you would:
        # 1. Query the database for the user by username/email
        # 2. Verify the password against the stored hash
        # 3. Check if account is locked due to failed attempts
        # 4. Update last login time
        # 5. Return user data if authentication succeeds
        
        # Example database query:
        # from app.models.user import User
        # from sqlalchemy import or_
        # 
        # user = db.query(User).filter(
        #     or_(User.username == username, User.email == username)
        # ).first()
        # 
        # if not user:
        #     logger.warning(f"Authentication failed: user not found - {username}")
        #     return None
        #     
        # if not user.is_active:
        #     logger.warning(f"Authentication failed: user inactive - {username}")
        #     return None
        #     
        # if user.is_locked and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        #     logger.warning(f"Authentication failed: user locked - {username}")
        #     return None
        #     
        # if not verify_password(password, user.hashed_password):
        #     logger.warning(f"Authentication failed: invalid password - {username}")
        #     # Increment failed attempts
        #     user.failed_login_attempts += 1
        #     if user.failed_login_attempts >= settings.security.MAX_LOGIN_ATTEMPTS:
        #         user.is_locked = True
        #         user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=settings.security.LOCKOUT_DURATION_MINUTES)
        #     db.commit()
        #     return None
        #     
        # # Reset failed attempts on successful login
        # user.failed_login_attempts = 0
        # user.is_locked = False
        # user.locked_until = None
        # user.last_login = datetime.now(timezone.utc)
        # db.commit()
        #     
        # return {
        #     "id": str(user.id),
        #     "username": user.username,
        #     "email": user.email,
        #     "is_active": user.is_active,
        #     "is_admin": user.is_admin,
        #     "is_superuser": user.is_superuser,
        #     "is_verified": user.is_verified,
        #     "roles": [role.name for role in user.roles],
        #     "permissions": [perm.name for perm in user.permissions],
        #     "last_login": user.last_login.isoformat(),
        #     "hostel_id": user.hostel_id,
        #     "tenant_id": user.tenant_id,
        # }
        
        # For now, return mock data for demonstration
        logger.warning("Using mock authentication - implement database lookup in production")
        
        # Mock authentication (remove this in production)
        if username == "admin" and password == "admin123":
            return {
                "id": "admin_user_id",
                "username": "admin",
                "email": "admin@example.com",
                "is_active": True,
                "is_admin": True,
                "is_superuser": True,
                "is_verified": True,
                "roles": ["admin", "superuser"],
                "permissions": ["*"],
                "hostel_id": "main",
                "tenant_id": "main",
                "accessible_tenants": ["main", "hostel_a", "hostel_b"],
                "last_login": datetime.now(timezone.utc).isoformat()
            }
        elif username == "warden" and password == "warden123":
            return {
                "id": "warden_user_id",
                "username": "warden",
                "email": "warden@example.com",
                "is_active": True,
                "is_admin": False,
                "is_superuser": False,
                "is_verified": True,
                "roles": ["warden", "supervisor"],
                "permissions": ["manage_rooms", "manage_students", "view_reports"],
                "hostel_id": "main",
                "tenant_id": "main",
                "accessible_tenants": ["main"],
                "last_login": datetime.now(timezone.utc).isoformat()
            }
        elif username == "student" and password == "student123":
            return {
                "id": "student_user_id",
                "username": "student",
                "email": "student@example.com",
                "is_active": True,
                "is_admin": False,
                "is_superuser": False,
                "is_verified": True,
                "roles": ["student"],
                "permissions": ["view_profile", "submit_maintenance_request"],
                "hostel_id": "main",
                "tenant_id": "main",
                "accessible_tenants": ["main"],
                "last_login": datetime.now(timezone.utc).isoformat()
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error during authentication: {e}")
        return None


def refresh_access_token(refresh_token: str) -> str:
    """
    Create new access token from refresh token.
    
    Args:
        refresh_token: Valid refresh token
        
    Returns:
        New access token
        
    Raises:
        HTTPException: If refresh token is invalid
    """
    try:
        manager = _get_jwt_manager()
        return manager.refresh_access_token(refresh_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


def get_user_id_from_token(token: str) -> Optional[str]:
    """
    Extract user ID from token without full verification.
    
    Args:
        token: JWT token
        
    Returns:
        User ID or None if invalid
    """
    manager = _get_jwt_manager()
    return manager.get_user_id_from_token(token)


def is_token_expired(token: str) -> bool:
    """
    Check if token is expired.
    
    Args:
        token: JWT token
        
    Returns:
        True if expired, False otherwise
    """
    manager = _get_jwt_manager()
    return manager.is_token_expired(token)


def get_token_expiry(token: str) -> Optional[datetime]:
    """
    Get token expiration time.
    
    Args:
        token: JWT token
        
    Returns:
        Expiration datetime or None if invalid
    """
    manager = _get_jwt_manager()
    return manager.get_token_expiry(token)


def create_password_reset_token(user_id: str) -> str:
    """
    Create a password reset token.
    
    Args:
        user_id: User identifier
        
    Returns:
        Password reset token
    """
    manager = _get_jwt_manager()
    # Create a short-lived token for password reset (15 minutes)
    expires_delta = timedelta(minutes=15)
    additional_claims = {"token_purpose": "password_reset"}
    return manager.create_access_token(user_id, additional_claims, expires_delta)


def verify_password_reset_token(token: str) -> Optional[str]:
    """
    Verify password reset token and return user ID.
    
    Args:
        token: Password reset token
        
    Returns:
        User ID if token is valid, None otherwise
    """
    try:
        payload = verify_token(token)
        if payload.get("token_purpose") != "password_reset":
            return None
        return payload.get("user_id")
    except HTTPException:
        return None


def create_email_verification_token(user_id: str, email: str) -> str:
    """
    Create an email verification token.
    
    Args:
        user_id: User identifier
        email: Email to verify
        
    Returns:
        Email verification token
    """
    manager = _get_jwt_manager()
    # Create a token that expires in 24 hours
    expires_delta = timedelta(hours=24)
    additional_claims = {
        "token_purpose": "email_verification",
        "email": email
    }
    return manager.create_access_token(user_id, additional_claims, expires_delta)


def verify_email_verification_token(token: str) -> Optional[Dict[str, str]]:
    """
    Verify email verification token.
    
    Args:
        token: Email verification token
        
    Returns:
        Dict with user_id and email if token is valid, None otherwise
    """
    try:
        payload = verify_token(token)
        if payload.get("token_purpose") != "email_verification":
            return None
        return {
            "user_id": payload.get("user_id"),
            "email": payload.get("email")
        }
    except HTTPException:
        return None