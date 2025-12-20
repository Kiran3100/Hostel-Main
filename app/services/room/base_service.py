# app/services/room/base_service.py
"""
Base service class with common functionality.
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger(__name__)


class BaseService:
    """
    Base service class providing common functionality.
    
    Features:
    - Transaction management
    - Error handling
    - Logging
    - Response formatting
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.logger = logger
    
    def success_response(
        self,
        data: Any,
        message: str = "Operation successful"
    ) -> Dict[str, Any]:
        """
        Format successful response.
        
        Args:
            data: Response data
            message: Success message
            
        Returns:
            Formatted response dictionary
        """
        return {
            'success': True,
            'message': message,
            'data': data
        }
    
    def error_response(
        self,
        error: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format error response.
        
        Args:
            error: Error message
            details: Additional error details
            
        Returns:
            Formatted error response dictionary
        """
        return {
            'success': False,
            'error': error,
            'details': details or {}
        }
    
    def handle_exception(
        self,
        e: Exception,
        operation: str
    ) -> Dict[str, Any]:
        """
        Handle exceptions with logging and rollback.
        
        Args:
            e: Exception raised
            operation: Operation being performed
            
        Returns:
            Error response
        """
        self.session.rollback()
        self.logger.error(f"Error in {operation}: {str(e)}", exc_info=True)
        
        return self.error_response(
            f"Failed to {operation}",
            {'exception': str(e)}
        )
    
    def commit_or_rollback(self) -> bool:
        """
        Commit transaction or rollback on error.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.session.commit()
            return True
        except SQLAlchemyError as e:
            self.session.rollback()
            self.logger.error(f"Commit failed: {str(e)}")
            return False