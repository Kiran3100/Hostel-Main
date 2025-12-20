"""
Complaint comment and discussion service.

Handles comment creation, threading, mentions, edit tracking,
and discussion management for complaints.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.complaint.complaint_comment import ComplaintComment
from app.repositories.complaint.complaint_repository import ComplaintRepository
from app.repositories.complaint.complaint_comment_repository import (
    ComplaintCommentRepository,
)
from app.core.exceptions import (
    BusinessLogicError,
    NotFoundError,
    ValidationError,
)


class ComplaintCommentService:
    """
    Complaint comment and discussion service.
    
    Manages comments, internal notes, threading, mentions,
    and discussion workflow for complaints.
    """

    def __init__(self, session: Session):
        """
        Initialize comment service.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.complaint_repo = ComplaintRepository(session)
        self.comment_repo = ComplaintCommentRepository(session)

    # ==================== Comment Creation ====================

    def add_comment(
        self,
        complaint_id: str,
        commented_by: str,
        comment_text: str,
        is_internal: bool = False,
        attachments: Optional[List[str]] = None,
        mentioned_users: Optional[List[str]] = None,
        parent_comment_id: Optional[str] = None,
    ) -> ComplaintComment:
        """
        Add a comment to a complaint.
        
        Args:
            complaint_id: Complaint identifier
            commented_by: User creating comment
            comment_text: Comment content
            is_internal: Internal note flag
            attachments: Attachment URLs
            mentioned_users: Mentioned user IDs
            parent_comment_id: Parent comment for threading
            
        Returns:
            Created comment instance
            
        Raises:
            NotFoundError: If complaint not found
            ValidationError: If comment data invalid
        """
        # Verify complaint exists
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            raise NotFoundError(f"Complaint {complaint_id} not found")
        
        # Validate comment text
        if not comment_text or not comment_text.strip():
            raise ValidationError("Comment text is required")
        
        if len(comment_text) < 2:
            raise ValidationError("Comment must be at least 2 characters")
        
        # Verify parent comment if provided
        if parent_comment_id:
            parent = self.comment_repo.find_by_id(parent_comment_id)
            if not parent:
                raise NotFoundError(f"Parent comment {parent_comment_id} not found")
            
            if parent.complaint_id != complaint_id:
                raise ValidationError("Parent comment belongs to different complaint")
        
        # Extract mentions from text if not provided
        if mentioned_users is None:
            mentioned_users = self._extract_mentions(comment_text)
        
        # Create comment
        comment = self.comment_repo.create_comment(
            complaint_id=complaint_id,
            commented_by=commented_by,
            comment_text=comment_text,
            is_internal=is_internal,
            attachments=attachments,
            mentioned_users=mentioned_users,
            parent_comment_id=parent_comment_id,
        )
        
        # Update complaint comment count
        self._update_complaint_comment_count(complaint_id, is_internal)
        
        self.session.commit()
        self.session.refresh(comment)
        
        # Send notifications for mentions
        if mentioned_users:
            self._notify_mentioned_users(comment, mentioned_users)
        
        return comment

    def add_internal_note(
        self,
        complaint_id: str,
        commented_by: str,
        note_text: str,
        attachments: Optional[List[str]] = None,
    ) -> ComplaintComment:
        """
        Add an internal note (staff only).
        
        Args:
            complaint_id: Complaint identifier
            commented_by: User creating note
            note_text: Note content
            attachments: Attachment URLs
            
        Returns:
            Created internal note
        """
        return self.add_comment(
            complaint_id=complaint_id,
            commented_by=commented_by,
            comment_text=note_text,
            is_internal=True,
            attachments=attachments,
        )

    def reply_to_comment(
        self,
        parent_comment_id: str,
        commented_by: str,
        reply_text: str,
        is_internal: bool = False,
    ) -> ComplaintComment:
        """
        Reply to an existing comment.
        
        Args:
            parent_comment_id: Parent comment ID
            commented_by: User replying
            reply_text: Reply content
            is_internal: Internal reply flag
            
        Returns:
            Created reply comment
            
        Raises:
            NotFoundError: If parent comment not found
        """
        parent = self.comment_repo.find_by_id(parent_comment_id)
        if not parent:
            raise NotFoundError(f"Parent comment {parent_comment_id} not found")
        
        return self.add_comment(
            complaint_id=parent.complaint_id,
            commented_by=commented_by,
            comment_text=reply_text,
            is_internal=is_internal,
            parent_comment_id=parent_comment_id,
        )

    # ==================== Comment Updates ====================

    def update_comment(
        self,
        comment_id: str,
        user_id: str,
        comment_text: str,
        attachments: Optional[List[str]] = None,
    ) -> ComplaintComment:
        """
        Update a comment.
        
        Args:
            comment_id: Comment identifier
            user_id: User updating comment
            comment_text: Updated content
            attachments: Updated attachments
            
        Returns:
            Updated comment
            
        Raises:
            NotFoundError: If comment not found
            BusinessLogicError: If update not allowed
            ValidationError: If update data invalid
        """
        comment = self.comment_repo.find_by_id(comment_id)
        if not comment:
            raise NotFoundError(f"Comment {comment_id} not found")
        
        # Verify user owns the comment
        if comment.commented_by != user_id:
            raise BusinessLogicError("Only comment author can edit")
        
        # Validate new text
        if not comment_text or not comment_text.strip():
            raise ValidationError("Comment text cannot be empty")
        
        # Update comment
        updated = self.comment_repo.update_comment(
            comment_id=comment_id,
            comment_text=comment_text,
            attachments=attachments,
        )
        
        self.session.commit()
        self.session.refresh(updated)
        
        return updated

    def delete_comment(
        self,
        comment_id: str,
        user_id: str,
    ) -> bool:
        """
        Delete a comment (soft delete).
        
        Args:
            comment_id: Comment identifier
            user_id: User deleting comment
            
        Returns:
            True if deleted
            
        Raises:
            NotFoundError: If comment not found
            BusinessLogicError: If deletion not allowed
        """
        comment = self.comment_repo.find_by_id(comment_id)
        if not comment:
            raise NotFoundError(f"Comment {comment_id} not found")
        
        # Verify user owns the comment or is admin
        if comment.commented_by != user_id:
            # Would need admin role check here
            raise BusinessLogicError("Only comment author can delete")
        
        # Soft delete
        self.comment_repo.soft_delete(comment_id)
        
        # Update complaint comment count
        self._update_complaint_comment_count(
            comment.complaint_id,
            comment.is_internal,
            decrement=True,
        )
        
        self.session.commit()
        return True

    # ==================== Query Operations ====================

    def get_comment(
        self,
        comment_id: str,
    ) -> Optional[ComplaintComment]:
        """
        Get comment by ID.
        
        Args:
            comment_id: Comment identifier
            
        Returns:
            Comment instance or None
        """
        return self.comment_repo.find_by_id(comment_id)

    def get_complaint_comments(
        self,
        complaint_id: str,
        include_internal: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintComment]:
        """
        Get all comments for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            include_internal: Include internal notes
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of comments
        """
        return self.comment_repo.find_by_complaint(
            complaint_id=complaint_id,
            include_internal=include_internal,
            skip=skip,
            limit=limit,
        )

    def get_root_comments(
        self,
        complaint_id: str,
        include_internal: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintComment]:
        """
        Get root-level comments (not replies).
        
        Args:
            complaint_id: Complaint identifier
            include_internal: Include internal notes
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of root comments
        """
        return self.comment_repo.find_root_comments(
            complaint_id=complaint_id,
            include_internal=include_internal,
            skip=skip,
            limit=limit,
        )

    def get_comment_replies(
        self,
        parent_comment_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintComment]:
        """
        Get all replies to a comment.
        
        Args:
            parent_comment_id: Parent comment ID
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of replies
        """
        return self.comment_repo.find_replies(
            parent_comment_id=parent_comment_id,
            skip=skip,
            limit=limit,
        )

    def get_comment_thread(
        self,
        comment_id: str,
        max_depth: Optional[int] = None,
    ) -> List[ComplaintComment]:
        """
        Get entire comment thread.
        
        Args:
            comment_id: Root comment ID
            max_depth: Maximum depth to fetch
            
        Returns:
            List of comments in thread
        """
        return self.comment_repo.get_comment_thread(
            comment_id=comment_id,
            max_depth=max_depth,
        )

    def get_user_mentions(
        self,
        user_id: str,
        complaint_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintComment]:
        """
        Get comments mentioning a user.
        
        Args:
            user_id: User identifier
            complaint_id: Optional complaint filter
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of comments with mentions
        """
        return self.comment_repo.find_with_mentions(
            user_id=user_id,
            complaint_id=complaint_id,
            skip=skip,
            limit=limit,
        )

    def get_internal_notes(
        self,
        complaint_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintComment]:
        """
        Get internal notes for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of internal notes
        """
        return self.comment_repo.find_internal_notes(
            complaint_id=complaint_id,
            skip=skip,
            limit=limit,
        )

    # ==================== Analytics ====================

    def get_comment_statistics(
        self,
        complaint_id: str,
    ) -> Dict[str, Any]:
        """
        Get comment statistics for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            
        Returns:
            Comment statistics dictionary
        """
        return self.comment_repo.get_comment_statistics(complaint_id)

    def get_user_comment_activity(
        self,
        user_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get comment activity for a user.
        
        Args:
            user_id: User identifier
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Activity statistics
        """
        return self.comment_repo.get_user_comment_activity(
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
        )

    def get_thread_summary(
        self,
        comment_id: str,
    ) -> Dict[str, Any]:
        """
        Get thread summary statistics.
        
        Args:
            comment_id: Root comment ID
            
        Returns:
            Thread summary
        """
        return self.comment_repo.get_thread_summary(comment_id)

    # ==================== Search ====================

    def search_comments(
        self,
        complaint_id: Optional[str] = None,
        search_term: Optional[str] = None,
        user_id: Optional[str] = None,
        is_internal: Optional[bool] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintComment]:
        """
        Search comments with filters.
        
        Args:
            complaint_id: Filter by complaint
            search_term: Search in text
            user_id: Filter by commenter
            is_internal: Filter by internal/public
            date_from: Start date filter
            date_to: End date filter
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List of matching comments
        """
        return self.comment_repo.search_comments(
            complaint_id=complaint_id,
            search_term=search_term,
            user_id=user_id,
            is_internal=is_internal,
            date_from=date_from,
            date_to=date_to,
            skip=skip,
            limit=limit,
        )

    # ==================== Helper Methods ====================

    def _extract_mentions(self, text: str) -> List[str]:
        """
        Extract @mentions from comment text.
        
        Args:
            text: Comment text
            
        Returns:
            List of mentioned user IDs/usernames
        """
        import re
        
        # Pattern: @username or @user_id
        pattern = r'@(\w+)'
        matches = re.findall(pattern, text)
        
        # Would need to resolve usernames to user IDs
        # For now, return the matches as-is
        return matches

    def _update_complaint_comment_count(
        self,
        complaint_id: str,
        is_internal: bool,
        decrement: bool = False,
    ) -> None:
        """
        Update complaint comment counters.
        
        Args:
            complaint_id: Complaint identifier
            is_internal: Internal note flag
            decrement: Decrement instead of increment
        """
        complaint = self.complaint_repo.find_by_id(complaint_id)
        if not complaint:
            return
        
        delta = -1 if decrement else 1
        
        if is_internal:
            new_count = max(0, complaint.internal_notes_count + delta)
            self.complaint_repo.update(
                complaint_id,
                {"internal_notes_count": new_count}
            )
        else:
            new_count = max(0, complaint.total_comments + delta)
            self.complaint_repo.update(
                complaint_id,
                {"total_comments": new_count}
            )

    def _notify_mentioned_users(
        self,
        comment: ComplaintComment,
        mentioned_users: List[str],
    ) -> None:
        """
        Send notifications to mentioned users.
        
        Args:
            comment: Comment instance
            mentioned_users: List of mentioned user IDs
        """
        # Would integrate with notification service
        # For now, just log
        print(f"Notifying users {mentioned_users} about mention in comment {comment.id}")