import time
import hashlib
from typing import Optional
from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from app.core.security.jwt_handler import JWTManager
from app.core.exceptions import AuthenticationException, TokenExpiredException
from app.models.user.user import User
from app.models.auth.user_session import UserSession
from app.models.auth.token_blacklist import BlacklistedToken
from app.config.database import get_db_session
import logging

logger = logging.getLogger(__name__)

class JWTAuthenticationMiddleware(BaseHTTPMiddleware):
    """JWT token validation middleware"""
    
    def __init__(self, app, jwt_manager: JWTManager):
        super().__init__(app)
        self.jwt_manager = jwt_manager
        # Routes that don't require authentication
        self.excluded_paths = {
            "/auth/login",
            "/auth/register",
            "/auth/password/reset",
            "/auth/otp/generate",
            "/auth/social",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health"
        }
    
    async def dispatch(self, request: Request, call_next):
        # Skip authentication for excluded paths
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            return await call_next(request)
        
        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authorization header"
            )
        
        token = auth_header.split(" ")[1]
        
        try:
            # Validate JWT token
            payload = self.jwt_manager.decode_token(token)
            user_id = payload.get("sub")
            
            # Check if token is blacklisted
            db = next(get_db_session())
            try:
                blacklisted = db.query(BlacklistedToken).filter(
                    BlacklistedToken.token_hash == hashlib.sha256(token.encode()).hexdigest()
                ).first()
                
                if blacklisted:
                    raise TokenExpiredException("Token has been revoked")
                
                # Set user context in request state
                request.state.user_id = user_id
                request.state.token = token
                request.state.token_payload = payload
                
            finally:
                db.close()
            
            response = await call_next(request)
            return response
            
        except Exception as e:
            logger.error(f"JWT authentication failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )

class SessionAuthenticationMiddleware(BaseHTTPMiddleware):
    """Session-based authentication middleware"""
    
    def __init__(self, app, session_timeout: int = 3600):
        super().__init__(app)
        self.session_timeout = session_timeout
    
    async def dispatch(self, request: Request, call_next):
        session_id = request.cookies.get("session_id")
        
        if session_id:
            db = next(get_db_session())
            try:
                session = db.query(UserSession).filter(
                    UserSession.session_id == session_id,
                    UserSession.is_active == True
                ).first()
                
                if session:
                    # Check session expiry
                    if time.time() - session.last_activity.timestamp() > self.session_timeout:
                        # Expire session
                        session.is_active = False
                        db.commit()
                        request.state.session_expired = True
                    else:
                        # Update last activity
                        session.last_activity = time.time()
                        db.commit()
                        request.state.user_id = session.user_id
                        request.state.session_id = session_id
                
            finally:
                db.close()
        
        response = await call_next(request)
        return response

class TokenValidationMiddleware(BaseHTTPMiddleware):
    """Token validation and refresh middleware"""
    
    def __init__(self, app, jwt_manager: JWTManager, refresh_threshold: int = 300):
        super().__init__(app)
        self.jwt_manager = jwt_manager
        self.refresh_threshold = refresh_threshold  # 5 minutes before expiry
    
    async def dispatch(self, request: Request, call_next):
        token = getattr(request.state, 'token', None)
        
        if token:
            try:
                payload = self.jwt_manager.decode_token(token)
                exp = payload.get('exp')
                
                # Check if token needs refresh
                if exp and (exp - time.time()) < self.refresh_threshold:
                    # Generate new token
                    new_token = self.jwt_manager.create_access_token(
                        data={"sub": payload.get('sub')}
                    )
                    request.state.new_token = new_token
                
            except Exception:
                pass
        
        response = await call_next(request)
        
        # Add new token to response headers if available
        new_token = getattr(request.state, 'new_token', None)
        if new_token:
            response.headers["X-New-Token"] = new_token
        
        return response

class DeviceTrackingMiddleware(BaseHTTPMiddleware):
    """Device fingerprinting and tracking middleware"""
    
    async def dispatch(self, request: Request, call_next):
        # Extract device information
        user_agent = request.headers.get("User-Agent", "")
        ip_address = request.client.host
        
        # Create device fingerprint
        device_fingerprint = hashlib.md5(
            f"{user_agent}:{ip_address}".encode()
        ).hexdigest()
        
        request.state.device_fingerprint = device_fingerprint
        request.state.ip_address = ip_address
        request.state.user_agent = user_agent
        
        response = await call_next(request)
        return response

class LoginAttemptMiddleware(BaseHTTPMiddleware):
    """Failed login attempt tracking middleware"""
    
    def __init__(self, app, max_attempts: int = 5, lockout_duration: int = 900):
        super().__init__(app)
        self.max_attempts = max_attempts
        self.lockout_duration = lockout_duration  # 15 minutes
        self.login_paths = {"/auth/login"}
    
    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.login_paths and request.method == "POST":
            ip_address = request.client.host
            
            # Check if IP is locked out (implementation depends on cache/database)
            # This is a simplified version
            request.state.login_attempt_check = True
        
        response = await call_next(request)
        
        # Track failed login attempts
        if (hasattr(request.state, 'login_attempt_check') and 
            response.status_code == 401):
            # Record failed attempt (implementation depends on storage)
            logger.warning(f"Failed login attempt from {request.client.host}")
        
        return response

class SecurityEventMiddleware(BaseHTTPMiddleware):
    """Security event logging middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.security_events = {
            "multiple_login_failures",
            "suspicious_activity",
            "token_manipulation",
            "unusual_access_pattern"
        }
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        try:
            response = await call_next(request)
            
            # Log security events
            if hasattr(request.state, 'security_event'):
                event = request.state.security_event
                logger.warning(f"Security event: {event} from {request.client.host}")
                
                # Additional security event handling
                await self._handle_security_event(event, request)
            
            return response
            
        except Exception as e:
            # Log security-related exceptions
            if isinstance(e, (AuthenticationException, TokenExpiredException)):
                logger.warning(f"Security exception: {str(e)} from {request.client.host}")
            
            raise
    
    async def _handle_security_event(self, event: str, request: Request):
        """Handle specific security events"""
        if event == "multiple_login_failures":
            # Implement IP blocking logic
            pass
        elif event == "token_manipulation":
            # Implement token invalidation logic
            pass
        elif event == "suspicious_activity":
            # Implement user account flagging
            pass