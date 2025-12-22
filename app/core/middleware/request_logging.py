import time
import json
import uuid
import logging
from typing import Dict, Any, Optional, Set
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from app.models.audit.audit_log import AuditLog
from app.config.database import get_db_session
import re

# Configure structured logging
logger = logging.getLogger(__name__)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """HTTP request/response logging middleware"""
    
    def __init__(self, app, log_body: bool = False, max_body_size: int = 1024):
        super().__init__(app)
        self.log_body = log_body
        self.max_body_size = max_body_size
        
        # Excluded paths from detailed logging
        self.excluded_paths = {
            '/health',
            '/metrics',
            '/docs',
            '/redoc',
            '/openapi.json'
        }
    
    async def dispatch(self, request: Request, call_next):
        # Generate correlation ID
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        
        # Skip detailed logging for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Start timing
        start_time = time.time()
        
        # Log request
        await self._log_request(request, correlation_id)
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log response
        await self._log_response(request, response, process_time, correlation_id)
        
        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        
        return response
    
    async def _log_request(self, request: Request, correlation_id: str):
        """Log incoming request details"""
        user_id = getattr(request.state, 'user_id', None)
        user_role = getattr(request.state, 'user_role', None)
        
        # Prepare request data
        request_data = {
            "correlation_id": correlation_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "user_id": user_id,
            "user_role": str(user_role) if user_role else None,
            "client_ip": request.client.host,
            "user_agent": request.headers.get('User-Agent'),
            "timestamp": time.time()
        }
        
        # Log request body if enabled
        if self.log_body and request.method in ['POST', 'PUT', 'PATCH']:
            body = await self._get_request_body(request)
            if body:
                request_data["body"] = body
        
        logger.info("HTTP Request", extra={"request_data": request_data})
    
    async def _log_response(
        self, 
        request: Request, 
        response: Response, 
        process_time: float,
        correlation_id: str
    ):
        """Log outgoing response details"""
        user_id = getattr(request.state, 'user_id', None)
        
        # Prepare response data
        response_data = {
            "correlation_id": correlation_id,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "process_time": process_time,
            "user_id": user_id,
            "timestamp": time.time()
        }
        
        # Log response body for errors if enabled
        if self.log_body and response.status_code >= 400:
            # Note: Response body logging requires special handling in FastAPI
            pass
        
        # Determine log level based on status code
        if response.status_code >= 500:
            logger.error("HTTP Response", extra={"response_data": response_data})
        elif response.status_code >= 400:
            logger.warning("HTTP Response", extra={"response_data": response_data})
        else:
            logger.info("HTTP Response", extra={"response_data": response_data})
    
    async def _get_request_body(self, request: Request) -> Optional[str]:
        """Safely get request body for logging"""
        try:
            body = await request.body()
            if len(body) > self.max_body_size:
                return f"<body too large: {len(body)} bytes>"
            
            # Try to decode as text
            try:
                return body.decode('utf-8')
            except UnicodeDecodeError:
                return f"<binary data: {len(body)} bytes>"
        except Exception:
            return None

class AuditTrailMiddleware(BaseHTTPMiddleware):
    """Audit trail generation middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        
        # Actions that should be audited
        self.audited_actions = {
            'POST': 'create',
            'PUT': 'update', 
            'PATCH': 'update',
            'DELETE': 'delete'
        }
        
        # Sensitive paths that always get audited
        self.always_audit_paths = {
            '/admin',
            '/payments',
            '/auth',
            '/users',
            '/students'
        }
    
    async def dispatch(self, request: Request, call_next):
        # Check if request should be audited
        should_audit = (
            request.method in self.audited_actions or
            any(request.url.path.startswith(path) for path in self.always_audit_paths)
        )
        
        if should_audit:
            # Capture request data for audit
            request.state.audit_data = await self._prepare_audit_data(request)
        
        response = await call_next(request)
        
        # Create audit log after successful request
        if should_audit and response.status_code < 400:
            await self._create_audit_log(request, response)
        
        return response
    
    async def _prepare_audit_data(self, request: Request) -> Dict[str, Any]:
        """Prepare data for audit logging"""
        user_id = getattr(request.state, 'user_id', None)
        correlation_id = getattr(request.state, 'correlation_id', None)
        
        return {
            "user_id": user_id,
            "correlation_id": correlation_id,
            "action": self.audited_actions.get(request.method, 'access'),
            "entity_type": self._extract_entity_type(request.url.path),
            "entity_id": self._extract_entity_id(request.url.path),
            "ip_address": request.client.host,
            "user_agent": request.headers.get('User-Agent'),
            "request_path": request.url.path,
            "request_method": request.method,
            "timestamp": time.time()
        }
    
    async def _create_audit_log(self, request: Request, response: Response):
        """Create audit log entry in database"""
        audit_data = getattr(request.state, 'audit_data', {})
        
        if audit_data.get('user_id'):  # Only audit authenticated actions
            db = next(get_db_session())
            try:
                audit_log = AuditLog(
                    user_id=audit_data['user_id'],
                    action=audit_data['action'],
                    entity_type=audit_data.get('entity_type'),
                    entity_id=audit_data.get('entity_id'),
                    ip_address=audit_data['ip_address'],
                    user_agent=audit_data['user_agent'],
                    request_path=audit_data['request_path'],
                    request_method=audit_data['request_method'],
                    response_status=response.status_code,
                    correlation_id=audit_data.get('correlation_id'),
                    timestamp=audit_data['timestamp']
                )
                
                db.add(audit_log)
                db.commit()
                
            except Exception as e:
                logger.error(f"Failed to create audit log: {str(e)}")
            finally:
                db.close()
    
    def _extract_entity_type(self, path: str) -> Optional[str]:
        """Extract entity type from URL path"""
        # Remove leading slash and split
        parts = path.strip('/').split('/')
        if parts:
            return parts[0]  # First part is usually the entity type
        return None
    
    def _extract_entity_id(self, path: str) -> Optional[str]:
        """Extract entity ID from URL path"""
        # Look for UUID or numeric ID patterns
        parts = path.strip('/').split('/')
        for part in parts:
            # Check for UUID pattern
            if len(part) == 36 and part.count('-') == 4:
                return part
            # Check for numeric ID
            if part.isdigit():
                return part
        return None

class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """Request performance monitoring middleware"""
    
    def __init__(self, app, slow_request_threshold: float = 1.0):
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        # Log slow requests
        if process_time > self.slow_request_threshold:
            logger.warning(
                f"Slow request detected: {request.method} {request.url.path} "
                f"took {process_time:.4f}s",
                extra={
                    "performance_data": {
                        "method": request.method,
                        "path": request.url.path,
                        "process_time": process_time,
                        "user_id": getattr(request.state, 'user_id', None),
                        "correlation_id": getattr(request.state, 'correlation_id', None)
                    }
                }
            )
        
        # Add performance metrics to response headers
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        
        return response

class SensitiveDataMaskingMiddleware(BaseHTTPMiddleware):
    """Sensitive data masking in logs middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        
        # Patterns for sensitive data
        self.sensitive_patterns = {
            'password': re.compile(r'"password"\s*:\s*"[^"]*"', re.IGNORECASE),
            'token': re.compile(r'"token"\s*:\s*"[^"]*"', re.IGNORECASE),
            'authorization': re.compile(r'"authorization"\s*:\s*"[^"]*"', re.IGNORECASE),
            'card_number': re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),
            'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        }
    
    def mask_sensitive_data(self, text: str) -> str:
        """Mask sensitive data in text"""
        masked_text = text
        
        for data_type, pattern in self.sensitive_patterns.items():
            if data_type == 'email':
                # Partial masking for emails
                def mask_email(match):
                    email = match.group(0)
                    local, domain = email.split('@')
                    masked_local = local[0] + '*' * (len(local) - 1)
                    return f"{masked_local}@{domain}"
                
                masked_text = pattern.sub(mask_email, masked_text)
            else:
                # Full masking for other sensitive data
                masked_text = pattern.sub(f'"{data_type}": "***MASKED***"', masked_text)
        
        return masked_text

class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """Request tracking and correlation middleware"""
    
    def __init__(self, app):
        super().__init__(app)
        self.request_tracker = {}
    
    async def dispatch(self, request: Request, call_next):
        correlation_id = getattr(request.state, 'correlation_id', str(uuid.uuid4()))
        
        # Track request start
        self.request_tracker[correlation_id] = {
            'start_time': time.time(),
            'method': request.method,
            'path': request.url.path,
            'user_id': getattr(request.state, 'user_id', None)
        }
        
        try:
            response = await call_next(request)
            
            # Track successful completion
            if correlation_id in self.request_tracker:
                track_data = self.request_tracker[correlation_id]
                track_data['end_time'] = time.time()
                track_data['status_code'] = response.status_code
                track_data['success'] = True
            
            return response
            
        except Exception as e:
            # Track failed request
            if correlation_id in self.request_tracker:
                track_data = self.request_tracker[correlation_id]
                track_data['end_time'] = time.time()
                track_data['error'] = str(e)
                track_data['success'] = False
            
            raise
        
        finally:
            # Cleanup old tracking data
            if correlation_id in self.request_tracker:
                del self.request_tracker[correlation_id]

class SlowQueryLoggingMiddleware(BaseHTTPMiddleware):
    """Slow database query logging middleware"""
    
    def __init__(self, app, slow_query_threshold: float = 0.5):
        super().__init__(app)
        self.slow_query_threshold = slow_query_threshold
    
    async def dispatch(self, request: Request, call_next):
        # This middleware works with database query monitoring
        # Implementation would integrate with SQLAlchemy events
        
        response = await call_next(request)
        
        # Check for slow queries in request state
        slow_queries = getattr(request.state, 'slow_queries', [])
        
        if slow_queries:
            correlation_id = getattr(request.state, 'correlation_id', None)
            logger.warning(
                f"Slow queries detected in request {correlation_id}",
                extra={
                    "slow_queries": slow_queries,
                    "request_path": request.url.path,
                    "user_id": getattr(request.state, 'user_id', None)
                }
            )
        
        return response