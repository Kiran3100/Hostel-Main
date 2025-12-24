"""
Chatbot service with third-party provider integration and session management.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timedelta
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.integrations import ThirdPartyRepository
from app.models.integrations.api_integration import APIIntegration


logger = logging.getLogger(__name__)


class ChatbotService(BaseService[APIIntegration, ThirdPartyRepository]):
    """
    Chatbot session and message orchestration with third-party provider integration.
    
    Features:
    - Session lifecycle management
    - Multi-channel support (in_app, web, mobile)
    - Message context preservation
    - Conversation history retrieval
    - Provider-agnostic interface (Dialogflow, Lex, OpenAI, etc.)
    """

    # Constants
    DEFAULT_HISTORY_LIMIT = 50
    MAX_HISTORY_LIMIT = 500
    SESSION_TIMEOUT_HOURS = 24
    DEFAULT_CHANNEL = "in_app"
    SUPPORTED_CHANNELS = {"in_app", "web", "mobile", "voice"}

    def __init__(self, repository: ThirdPartyRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._logger = logger

    def start_session(
        self,
        user_id: UUID,
        channel: str = DEFAULT_CHANNEL,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Initiate a chatbot session and return session context from provider.
        
        Args:
            user_id: User initiating the chat session
            channel: Communication channel (in_app, web, mobile, voice)
            metadata: Additional session metadata
            
        Returns:
            ServiceResult containing session id and context
        """
        # Validate channel
        if channel not in self.SUPPORTED_CHANNELS:
            self._logger.warning(
                f"Unsupported channel '{channel}', using default '{self.DEFAULT_CHANNEL}'"
            )
            channel = self.DEFAULT_CHANNEL

        self._logger.info(
            f"Starting chatbot session for user {user_id} on channel '{channel}'"
        )

        try:
            # Prepare session metadata
            session_metadata = self._prepare_session_metadata(user_id, channel, metadata)
            
            # Delegate to repository to call provider
            session_data = self.repository.chatbot_start_session(
                user_id=user_id,
                channel=channel,
                metadata=session_metadata,
            )
            
            self.db.commit()
            
            # Enhance response with additional context
            enhanced_session = self._enhance_session_data(session_data, user_id, channel)
            
            self._logger.info(
                f"Chatbot session started successfully: {enhanced_session.get('session_id')}"
            )
            
            return ServiceResult.success(
                enhanced_session,
                message="Chatbot session started successfully"
            )
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error starting chatbot session for user {user_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "start chatbot session", user_id)
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Error starting chatbot session for user {user_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "start chatbot session", user_id)

    def send_user_message(
        self,
        session_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Send user message to provider and receive bot response.
        
        Args:
            session_id: Active session identifier
            message: User's message text
            context: Additional conversation context
            
        Returns:
            ServiceResult containing bot response and updated context
        """
        # Validate inputs
        if not session_id or not session_id.strip():
            return ServiceResult.failure(
                message="Session ID is required",
                error=ValueError("Invalid session_id"),
            )
        
        if not message or not message.strip():
            return ServiceResult.failure(
                message="Message cannot be empty",
                error=ValueError("Invalid message"),
            )

        self._logger.debug(
            f"Sending user message to session {session_id}: {message[:50]}..."
        )

        try:
            # Prepare message context
            message_context = self._prepare_message_context(context)
            
            # Delegate to provider
            reply = self.repository.chatbot_send_message(
                session_id=session_id,
                message=message.strip(),
                context=message_context,
            )
            
            # Validate and enhance response
            enhanced_reply = self._enhance_message_response(reply, session_id)
            
            self._logger.debug(
                f"Received bot response for session {session_id}"
            )
            
            return ServiceResult.success(
                enhanced_reply,
                message="Message processed successfully"
            )
            
        except Exception as e:
            self._logger.error(
                f"Error processing message for session {session_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "send chatbot message", session_id)

    def get_history(
        self,
        session_id: str,
        limit: int = DEFAULT_HISTORY_LIMIT,
        offset: int = 0,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        Retrieve chat history for a session.
        
        Args:
            session_id: Session identifier
            limit: Maximum number of messages to retrieve
            offset: Number of messages to skip (for pagination)
            
        Returns:
            ServiceResult containing list of messages
        """
        if not session_id or not session_id.strip():
            return ServiceResult.failure(
                message="Session ID is required",
                error=ValueError("Invalid session_id"),
            )

        # Validate and normalize limit
        limit = self._validate_history_limit(limit)

        self._logger.debug(
            f"Retrieving chat history for session {session_id} (limit={limit}, offset={offset})"
        )

        try:
            items = self.repository.chatbot_get_history(
                session_id=session_id,
                limit=limit,
                offset=offset,
            )
            
            messages = items or []
            
            self._logger.debug(
                f"Retrieved {len(messages)} messages for session {session_id}"
            )
            
            return ServiceResult.success(
                messages,
                metadata={
                    "count": len(messages),
                    "limit": limit,
                    "offset": offset,
                    "session_id": session_id,
                }
            )
            
        except Exception as e:
            self._logger.error(
                f"Error retrieving chat history for session {session_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get chatbot history", session_id)

    def end_session(
        self,
        session_id: str,
        reason: Optional[str] = None,
    ) -> ServiceResult[bool]:
        """
        Explicitly end a chatbot session.
        
        Args:
            session_id: Session to terminate
            reason: Optional reason for termination
            
        Returns:
            ServiceResult indicating success
        """
        self._logger.info(f"Ending chatbot session {session_id}, reason: {reason or 'User initiated'}")
        
        try:
            # Call provider to end session if supported
            if hasattr(self.repository, 'chatbot_end_session'):
                self.repository.chatbot_end_session(session_id, reason)
            
            self.db.commit()
            
            return ServiceResult.success(
                True,
                message="Session ended successfully"
            )
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Error ending session {session_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "end chatbot session", session_id)

    def _prepare_session_metadata(
        self,
        user_id: UUID,
        channel: str,
        metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Prepare enhanced session metadata."""
        return {
            "user_id": str(user_id),
            "channel": channel,
            "started_at": datetime.utcnow().isoformat(),
            "timeout_hours": self.SESSION_TIMEOUT_HOURS,
            **(metadata or {}),
        }

    def _prepare_message_context(
        self,
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Prepare message context with timestamp."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            **(context or {}),
        }

    def _enhance_session_data(
        self,
        session_data: Optional[Dict[str, Any]],
        user_id: UUID,
        channel: str,
    ) -> Dict[str, Any]:
        """Enhance session data with additional fields."""
        base_data = session_data or {}
        return {
            **base_data,
            "user_id": str(user_id),
            "channel": channel,
            "created_at": datetime.utcnow().isoformat(),
        }

    def _enhance_message_response(
        self,
        reply: Optional[Dict[str, Any]],
        session_id: str,
    ) -> Dict[str, Any]:
        """Enhance message response with metadata."""
        base_reply = reply or {}
        return {
            **base_reply,
            "session_id": session_id,
            "processed_at": datetime.utcnow().isoformat(),
        }

    def _validate_history_limit(self, limit: int) -> int:
        """Validate and normalize history limit."""
        if limit <= 0:
            self._logger.warning(
                f"Invalid history limit {limit}, using default {self.DEFAULT_HISTORY_LIMIT}"
            )
            return self.DEFAULT_HISTORY_LIMIT
        
        if limit > self.MAX_HISTORY_LIMIT:
            self._logger.warning(
                f"History limit {limit} exceeds maximum, using {self.MAX_HISTORY_LIMIT}"
            )
            return self.MAX_HISTORY_LIMIT
        
        return limit