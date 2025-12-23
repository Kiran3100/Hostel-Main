"""
In-app chat service using the notification subsystem.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from datetime import datetime
import logging
import hashlib

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.notification import NotificationRepository
from app.models.notification.notification import Notification as NotificationModel
from app.schemas.notification.notification_base import NotificationCreate
from app.schemas.notification.notification_response import NotificationResponse


logger = logging.getLogger(__name__)


class ChatService(BaseService[NotificationModel, NotificationRepository]):
    """
    In-app chat service leveraging the notification subsystem.
    
    Features:
    - One-on-one messaging
    - Thread-based conversations
    - Message history retrieval
    - Thread listing and management
    - Automatic thread ID generation
    """

    # Constants
    DEFAULT_MESSAGE_LIMIT = 50
    MAX_MESSAGE_LIMIT = 500
    MAX_MESSAGE_LENGTH = 5000
    DEFAULT_THREAD_LIMIT = 50
    MAX_THREAD_LIMIT = 200

    def __init__(self, repository: NotificationRepository, db_session: Session):
        super().__init__(repository, db_session)
        self._logger = logger

    def send_message(
        self,
        sender_user_id: UUID,
        recipient_user_id: UUID,
        message: str,
        thread_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ServiceResult[NotificationResponse]:
        """
        Send a chat message to a recipient.
        
        Args:
            sender_user_id: User sending the message
            recipient_user_id: User receiving the message
            message: Message content
            thread_id: Optional thread identifier (auto-generated if not provided)
            metadata: Additional message metadata
            
        Returns:
            ServiceResult containing the created notification
        """
        # Validate users are different
        if sender_user_id == recipient_user_id:
            return ServiceResult.failure(
                message="Cannot send message to yourself",
                error=ValueError("Sender and recipient cannot be the same"),
            )

        # Validate message content
        validation_result = self._validate_message(message)
        if not validation_result["valid"]:
            return ServiceResult.failure(
                message=validation_result["error"],
                error=ValueError(validation_result["error"]),
            )

        # Generate or validate thread ID
        if thread_id is None:
            thread_id = self._generate_thread_id(sender_user_id, recipient_user_id)
        
        self._logger.debug(
            f"Sending message from {sender_user_id} to {recipient_user_id} "
            f"in thread {thread_id}"
        )

        try:
            # Prepare notification request
            notification_request = self._create_message_notification(
                sender_user_id=sender_user_id,
                recipient_user_id=recipient_user_id,
                message=message,
                thread_id=thread_id,
                metadata=metadata,
            )

            # Create notification
            notification = self.repository.create_notification(notification_request)
            self.db.commit()

            response = self.repository.to_response(notification.id)
            
            self._logger.info(
                f"Message sent successfully: {notification.id} in thread {thread_id}"
            )

            return ServiceResult.success(
                response,
                message="Message sent successfully"
            )

        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(
                f"Database error sending message: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "send chat message", recipient_user_id)
        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Error sending message: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "send chat message", recipient_user_id)

    def get_conversation(
        self,
        user_id: UUID,
        other_user_id: UUID,
        thread_id: Optional[str] = None,
        limit: int = DEFAULT_MESSAGE_LIMIT,
        offset: int = 0,
    ) -> ServiceResult[List[NotificationResponse]]:
        """
        Retrieve messages for a conversation between two users.
        
        Args:
            user_id: Current user
            other_user_id: Other participant
            thread_id: Specific thread (auto-generated if not provided)
            limit: Maximum messages to retrieve
            offset: Number of messages to skip
            
        Returns:
            ServiceResult containing list of messages
        """
        # Validate limit
        limit = self._validate_limit(limit, self.MAX_MESSAGE_LIMIT, self.DEFAULT_MESSAGE_LIMIT)

        # Generate thread ID if not provided
        if thread_id is None:
            thread_id = self._generate_thread_id(user_id, other_user_id)

        self._logger.debug(
            f"Retrieving conversation for user {user_id} with {other_user_id} "
            f"(thread={thread_id}, limit={limit}, offset={offset})"
        )

        try:
            messages = self.repository.list_in_app_conversation(
                user_id=user_id,
                other_user_id=other_user_id,
                thread_id=thread_id,
                limit=limit,
                offset=offset,
            )

            self._logger.debug(
                f"Retrieved {len(messages)} messages for thread {thread_id}"
            )

            return ServiceResult.success(
                messages,
                metadata={
                    "count": len(messages),
                    "limit": limit,
                    "offset": offset,
                    "thread_id": thread_id,
                    "participants": [str(user_id), str(other_user_id)],
                }
            )

        except Exception as e:
            self._logger.error(
                f"Error retrieving conversation: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "get conversation", user_id)

    def list_threads(
        self,
        user_id: UUID,
        limit: int = DEFAULT_THREAD_LIMIT,
        offset: int = 0,
        include_unread_count: bool = True,
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """
        List active conversation threads for a user.
        
        Args:
            user_id: User to get threads for
            limit: Maximum threads to retrieve
            offset: Number of threads to skip
            include_unread_count: Include unread message counts
            
        Returns:
            ServiceResult containing list of threads with metadata
        """
        # Validate limit
        limit = self._validate_limit(limit, self.MAX_THREAD_LIMIT, self.DEFAULT_THREAD_LIMIT)

        self._logger.debug(
            f"Listing threads for user {user_id} (limit={limit}, offset={offset})"
        )

        try:
            threads = self.repository.list_in_app_threads(
                user_id=user_id,
                limit=limit,
                offset=offset,
            )

            # Enhance threads with additional metadata
            enhanced_threads = self._enhance_threads(
                threads,
                user_id,
                include_unread_count
            )

            self._logger.debug(
                f"Retrieved {len(enhanced_threads)} threads for user {user_id}"
            )

            return ServiceResult.success(
                enhanced_threads,
                metadata={
                    "count": len(enhanced_threads),
                    "limit": limit,
                    "offset": offset,
                    "user_id": str(user_id),
                }
            )

        except Exception as e:
            self._logger.error(
                f"Error listing threads for user {user_id}: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "list chat threads", user_id)

    def mark_as_read(
        self,
        user_id: UUID,
        thread_id: str,
        message_ids: Optional[List[UUID]] = None,
    ) -> ServiceResult[int]:
        """
        Mark messages in a thread as read.
        
        Args:
            user_id: User marking messages as read
            thread_id: Thread identifier
            message_ids: Specific message IDs (or all unread in thread if None)
            
        Returns:
            ServiceResult containing count of messages marked as read
        """
        self._logger.debug(
            f"Marking messages as read for user {user_id} in thread {thread_id}"
        )

        try:
            count = 0
            if hasattr(self.repository, 'mark_messages_read'):
                count = self.repository.mark_messages_read(
                    user_id=user_id,
                    thread_id=thread_id,
                    message_ids=message_ids,
                )
                self.db.commit()
            
            return ServiceResult.success(
                count,
                message=f"{count} message(s) marked as read"
            )

        except Exception as e:
            self.db.rollback()
            self._logger.error(
                f"Error marking messages as read: {str(e)}",
                exc_info=True
            )
            return self._handle_exception(e, "mark messages as read", user_id)

    def _validate_message(self, message: str) -> Dict[str, Any]:
        """
        Validate message content.
        
        Returns:
            Dictionary with 'valid' boolean and optional 'error' message
        """
        if not message or not message.strip():
            return {"valid": False, "error": "Message cannot be empty"}
        
        if len(message) > self.MAX_MESSAGE_LENGTH:
            return {
                "valid": False,
                "error": f"Message exceeds maximum length of {self.MAX_MESSAGE_LENGTH} characters"
            }
        
        return {"valid": True}

    def _generate_thread_id(self, user1_id: UUID, user2_id: UUID) -> str:
        """
        Generate a consistent thread ID for two users.
        
        Uses deterministic ordering to ensure the same thread ID
        regardless of which user initiates the conversation.
        """
        # Sort UUIDs to ensure consistency
        sorted_ids = sorted([str(user1_id), str(user2_id)])
        combined = f"{sorted_ids[0]}:{sorted_ids[1]}"
        
        # Create hash-based thread ID
        thread_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]
        return f"thread_{thread_hash}"

    def _create_message_notification(
        self,
        sender_user_id: UUID,
        recipient_user_id: UUID,
        message: str,
        thread_id: str,
        metadata: Optional[Dict[str, Any]],
    ) -> NotificationCreate:
        """Create notification request for chat message."""
        return NotificationCreate(
            user_id=str(recipient_user_id),
            notification_type="IN_APP",
            subject=None,
            message_body=message.strip(),
            metadata={
                "thread_id": thread_id,
                "sender_user_id": str(sender_user_id),
                "message_type": "chat",
                "timestamp": datetime.utcnow().isoformat(),
                **(metadata or {}),
            },
            scheduled_at=None,
            priority="normal",
        )

    def _enhance_threads(
        self,
        threads: List[Dict[str, Any]],
        user_id: UUID,
        include_unread_count: bool,
    ) -> List[Dict[str, Any]]:
        """Enhance thread data with additional metadata."""
        enhanced = []
        
        for thread in threads:
            enhanced_thread = {**thread}
            
            # Add unread count if requested
            if include_unread_count and hasattr(self.repository, 'get_unread_count'):
                try:
                    unread_count = self.repository.get_unread_count(
                        user_id=user_id,
                        thread_id=thread.get('thread_id'),
                    )
                    enhanced_thread['unread_count'] = unread_count
                except Exception as e:
                    self._logger.warning(
                        f"Could not get unread count for thread: {str(e)}"
                    )
                    enhanced_thread['unread_count'] = 0
            
            enhanced.append(enhanced_thread)
        
        return enhanced

    def _validate_limit(
        self,
        limit: int,
        max_limit: int,
        default_limit: int,
    ) -> int:
        """Validate and normalize limit parameter."""
        if limit <= 0:
            return default_limit
        
        if limit > max_limit:
            self._logger.warning(
                f"Limit {limit} exceeds maximum {max_limit}, using maximum"
            )
            return max_limit
        
        return limit