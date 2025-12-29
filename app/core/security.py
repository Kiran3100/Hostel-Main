"""
Security and Authentication Module

Comprehensive security utilities including password hashing, JWT token management,
permission validation, and security middleware.
"""

import secrets
import hashlib
import re
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from functools import wraps
from enum import Enum

import bcrypt
import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .config import settings
from .exceptions import (
    AuthenticationError,
    AuthorizationError,
    InvalidTokenError,
    TokenExpiredError,
    PermissionError
)
from .logging import get_logger

logger = get_logger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Security scheme
security = HTTPBearer()


class TokenType(str, Enum):
    """Token type enumeration"""
    ACCESS = "access"
    REFRESH = "refresh"
    RESET_PASSWORD = "reset_password"
    EMAIL_VERIFICATION = "email_verification"


class PermissionLevel(str, Enum):
    """Permission level enumeration"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class SecurityHeaders:
    """Security headers configuration"""
    
    @staticmethod
    def get_security_headers() -> Dict[str, str]:
        """Get recommended security headers"""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }


class PasswordValidator:
    """Password validation utilities"""
    
    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, Any]:
        """
        Validate password strength against security requirements.
        
        Args:
            password: Password to validate
            
        Returns:
            Dict containing validation result and details
        """
        result = {
            "is_valid": True,
            "score": 0,
            "errors": [],
            "suggestions": []
        }
        
        # Length check
        min_length = getattr(settings.security, 'PASSWORD_MIN_LENGTH', 8)
        if len(password) < min_length:
            result["is_valid"] = False
            result["errors"].append(f"Password must be at least {min_length} characters")
        else:
            result["score"] += 1
        
        # Uppercase check
        require_uppercase = getattr(settings.security, 'PASSWORD_REQUIRE_UPPERCASE', True)
        if require_uppercase and not re.search(r'[A-Z]', password):
            result["is_valid"] = False
            result["errors"].append("Password must contain at least one uppercase letter")
        elif re.search(r'[A-Z]', password):
            result["score"] += 1
        
        # Lowercase check
        require_lowercase = getattr(settings.security, 'PASSWORD_REQUIRE_LOWERCASE', True)
        if require_lowercase and not re.search(r'[a-z]', password):
            result["is_valid"] = False
            result["errors"].append("Password must contain at least one lowercase letter")
        elif re.search(r'[a-z]', password):
            result["score"] += 1
        
        # Number check
        require_numbers = getattr(settings.security, 'PASSWORD_REQUIRE_NUMBERS', True)
        if require_numbers and not re.search(r'\d', password):
            result["is_valid"] = False
            result["errors"].append("Password must contain at least one number")
        elif re.search(r'\d', password):
            result["score"] += 1
        
        # Special character check
        require_special = getattr(settings.security, 'PASSWORD_REQUIRE_SPECIAL', True)
        if require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            result["is_valid"] = False
            result["errors"].append("Password must contain at least one special character")
        elif re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            result["score"] += 1
        
        # Common patterns check
        common_patterns = [
            r'123456',
            r'password',
            r'qwerty',
            r'abc123'
        ]
        
        for pattern in common_patterns:
            if re.search(pattern, password.lower()):
                result["is_valid"] = False
                result["errors"].append("Password contains common patterns")
                break
        
        # Sequential characters
        if re.search(r'(.)\1{2,}', password):
            result["suggestions"].append("Avoid repeating characters")
        
        # Keyboard patterns
        keyboard_patterns = ['qwerty', 'asdfgh', 'zxcvbn', '123456', '098765']
        for pattern in keyboard_patterns:
            if pattern in password.lower():
                result["suggestions"].append("Avoid keyboard patterns")
                break
        
        return result
    
    @staticmethod
    def generate_secure_password(length: int = 16) -> str:
        """Generate a cryptographically secure password"""
        import string
        
        characters = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(secrets.choice(characters) for _ in range(length))
        
        # Ensure password meets requirements
        validation = PasswordValidator.validate_password_strength(password)
        if not validation["is_valid"]:
            return PasswordValidator.generate_secure_password(length)
        
        return password


class PasswordManager:
    """Password hashing and verification"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        try:
            return pwd_context.hash(password)
        except Exception as e:
            logger.error(f"Password hashing failed: {str(e)}")
            raise AuthenticationError("Password hashing failed")
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password to verify against
            
        Returns:
            True if password matches, False otherwise
        """
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error(f"Password verification failed: {str(e)}")
            return False
    
    @staticmethod
    def needs_update(hashed_password: str) -> bool:
        """Check if password hash needs updating"""
        return pwd_context.needs_update(hashed_password)


class TokenManager:
    """JWT token management utilities"""
    
    @staticmethod
    def create_token(
        data: Dict[str, Any],
        token_type: TokenType = TokenType.ACCESS,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT token with specified data and expiration.
        
        Args:
            data: Data to encode in token
            token_type: Type of token to create
            expires_delta: Custom expiration time
            
        Returns:
            Encoded JWT token
        """
        try:
            to_encode = data.copy()
            
            # Set expiration based on token type
            if expires_delta:
                expire = datetime.utcnow() + expires_delta
            elif token_type == TokenType.ACCESS:
                expire = datetime.utcnow() + timedelta(
                    minutes=getattr(settings.security, 'ACCESS_TOKEN_EXPIRE_MINUTES', 30)
                )
            elif token_type == TokenType.REFRESH:
                expire = datetime.utcnow() + timedelta(
                    days=getattr(settings.security, 'REFRESH_TOKEN_EXPIRE_DAYS', 7)
                )
            else:
                expire = datetime.utcnow() + timedelta(hours=24)  # Default 24 hours
            
            to_encode.update({
                "exp": expire,
                "iat": datetime.utcnow(),
                "type": token_type.value,
                "jti": secrets.token_urlsafe(16)  # JWT ID for revocation
            })
            
            secret_key = getattr(settings.security, 'SECRET_KEY', 'your-secret-key-here')
            algorithm = getattr(settings.security, 'ALGORITHM', 'HS256')
            
            encoded_jwt = jwt.encode(
                to_encode,
                secret_key,
                algorithm=algorithm
            )
            
            return encoded_jwt
            
        except Exception as e:
            logger.error(f"Token creation failed: {str(e)}")
            raise AuthenticationError("Token creation failed")
    
    @staticmethod
    def verify_token(
        token: str,
        expected_type: Optional[TokenType] = None
    ) -> Dict[str, Any]:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token to verify
            expected_type: Expected token type
            
        Returns:
            Decoded token payload
            
        Raises:
            InvalidTokenError: If token is invalid
            TokenExpiredError: If token has expired
        """
        try:
            secret_key = getattr(settings.security, 'SECRET_KEY', 'your-secret-key-here')
            algorithm = getattr(settings.security, 'ALGORITHM', 'HS256')
            
            payload = jwt.decode(
                token,
                secret_key,
                algorithms=[algorithm]
            )
            
            # Verify token type if specified
            if expected_type and payload.get("type") != expected_type.value:
                raise InvalidTokenError("Invalid token type")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError("Token has expired")
        except jwt.JWTError as e:
            logger.warning(f"Token verification failed: {str(e)}")
            raise InvalidTokenError("Invalid token")
    
    @staticmethod
    def refresh_token(refresh_token: str) -> str:
        """
        Create new access token from refresh token.
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New access token
        """
        try:
            payload = TokenManager.verify_token(refresh_token, TokenType.REFRESH)
            
            # Create new access token with user data
            user_data = {
                "sub": payload.get("sub"),
                "user_id": payload.get("user_id"),
                "role": payload.get("role")
            }
            
            return TokenManager.create_token(user_data, TokenType.ACCESS)
            
        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            raise InvalidTokenError("Token refresh failed")


class PermissionValidator:
    """Permission validation utilities"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def validate_permission(
        self,
        user_id: str,
        resource: str,
        action: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Validate user permission for specific resource and action.
        
        Args:
            user_id: User ID to check permissions for
            resource: Resource being accessed
            action: Action being performed
            context: Additional context for permission check
            
        Returns:
            True if user has permission, False otherwise
        """
        try:
            # Implementation would check against permission system
            # This is a placeholder for the actual permission logic
            
            # Get user roles and permissions
            user_permissions = await self._get_user_permissions(user_id)
            
            # Check direct permissions
            permission_key = f"{resource}:{action}"
            if permission_key in user_permissions:
                return True
            
            # Check role-based permissions
            user_roles = await self._get_user_roles(user_id)
            for role in user_roles:
                role_permissions = await self._get_role_permissions(role)
                if permission_key in role_permissions:
                    return await self._check_context_constraints(
                        role, permission_key, context
                    )
            
            return False
            
        except Exception as e:
            logger.error(f"Permission validation failed: {str(e)}")
            return False
    
    async def _get_user_permissions(self, user_id: str) -> List[str]:
        """Get direct user permissions"""
        # Implementation would query database
        return []
    
    async def _get_user_roles(self, user_id: str) -> List[str]:
        """Get user roles"""
        # Implementation would query database
        return []
    
    async def _get_role_permissions(self, role: str) -> List[str]:
        """Get permissions for a role"""
        # Implementation would query database
        return []
    
    async def _check_context_constraints(
        self,
        role: str,
        permission: str,
        context: Optional[Dict[str, Any]]
    ) -> bool:
        """Check context-specific constraints"""
        # Implementation would check constraints like hostel ownership, time restrictions, etc.
        return True


def require_permission(resource: str, action: str):
    """
    Decorator to require specific permission for endpoint access.
    
    Args:
        resource: Resource being accessed
        action: Action being performed
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract current user from kwargs
            current_user = kwargs.get('current_user')
            if not current_user:
                raise AuthorizationError("Authentication required")
            
            # Get database session
            db = kwargs.get('db')
            if not db:
                raise AuthenticationError("Database session not available")
            
            # Validate permission
            validator = PermissionValidator(db)
            has_permission = await validator.validate_permission(
                user_id=current_user.get('id'),
                resource=resource,
                action=action,
                context=kwargs.get('context')
            )
            
            if not has_permission:
                raise PermissionError(
                    f"Permission denied for {action} on {resource}",
                    required_permission=f"{resource}:{action}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


async def get_current_user_from_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = None  # Would be injected via dependency
) -> Dict[str, Any]:
    """
    Get current user from JWT token.
    
    Args:
        credentials: HTTP authorization credentials
        db: Database session
        
    Returns:
        Current user data
        
    Raises:
        AuthenticationError: If authentication fails
    """
    try:
        # Verify token
        payload = TokenManager.verify_token(credentials.credentials, TokenType.ACCESS)
        
        # Extract user information
        user_id = payload.get("sub")
        if not user_id:
            raise InvalidTokenError("Invalid token payload")
        
        # Get user from database (implementation would query actual user)
        # user = await get_user_by_id(db, user_id)
        # if not user:
        #     raise AuthenticationError("User not found")
        
        # For now, return payload data
        return {
            "id": user_id,
            "user_id": payload.get("user_id"),
            "role": payload.get("role"),
            "permissions": payload.get("permissions", []),
            "is_active": payload.get("is_active", True),
            "is_admin": payload.get("is_admin", False),
            "is_superuser": payload.get("is_superuser", False)
        }
        
    except (InvalidTokenError, TokenExpiredError):
        raise
    except Exception as e:
        logger.error(f"User authentication failed: {str(e)}")
        raise AuthenticationError("Authentication failed")


# Convenience functions and aliases for compatibility
def hash_password(password: str) -> str:
    """Convenience function for password hashing"""
    return PasswordManager.hash_password(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Convenience function for password verification"""
    return PasswordManager.verify_password(plain_password, hashed_password)


def create_access_token(data: Dict[str, Any]) -> str:
    """Convenience function for creating access token"""
    return TokenManager.create_token(data, TokenType.ACCESS)


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Convenience function for creating refresh token"""
    return TokenManager.create_token(data, TokenType.REFRESH)


# Aliases for dependencies.py compatibility
def verify_token(token: str) -> Dict[str, Any]:
    """Alias for TokenManager.verify_token for compatibility"""
    return TokenManager.verify_token(token, TokenType.ACCESS)


async def get_current_user(token: str, db: Session) -> Optional[Dict[str, Any]]:
    """Alias for get_current_user_from_token for compatibility"""
    try:
        # Create a mock credentials object
        class MockCredentials:
            def __init__(self, token: str):
                self.credentials = token
        
        credentials = MockCredentials(token)
        return await get_current_user_from_token(credentials, db)
    except Exception:
        return None


class SecurityMiddleware:
    """Security middleware for request processing"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        """Process request with security enhancements"""
        
        if scope["type"] == "http":
            # Add security headers
            enable_security_headers = getattr(settings.security, 'ENABLE_SECURITY_HEADERS', True)
            if enable_security_headers:
                # Implementation would add security headers to response
                pass
            
            # Log security events
            self._log_security_event(scope)
        
        await self.app(scope, receive, send)
    
    def _log_security_event(self, scope):
        """Log security-related events"""
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        # Log sensitive endpoints
        sensitive_patterns = ["/admin/", "/auth/", "/api/v1/admin/"]
        
        if any(pattern in path for pattern in sensitive_patterns):
            logger.info(f"Security: Access to sensitive endpoint", extra={
                "method": method,
                "path": path,
                "client": scope.get("client", ["unknown"])[0]
            })


# Export convenience functions and classes
__all__ = [
    "TokenType",
    "PermissionLevel",
    "SecurityHeaders",
    "PasswordValidator",
    "PasswordManager",
    "TokenManager",
    "PermissionValidator",
    "SecurityMiddleware",
    "require_permission",
    "get_current_user_from_token",
    "hash_password",
    "verify_password",
    "create_access_token",
    "create_refresh_token",
    "verify_token",
    "get_current_user"
]