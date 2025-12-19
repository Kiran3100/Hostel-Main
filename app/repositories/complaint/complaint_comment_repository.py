# --- File: complaint_comment_repository.py ---
"""
Complaint comment repository with threading, mentions, and edit tracking.

Handles complaint comments, internal notes, and discussion threads with
rich features and performance optimization.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from app.models.complaint.complaint_comment import ComplaintComment
from app.repositories.base.base_repository import BaseRepository


class ComplaintCommentRepository(BaseRepository[ComplaintComment]):
    """
    Complaint comment repository with advanced discussion features.
    
    Provides comment management, threading, mentions, and edit tracking
    with performance optimization.
    """

    def __init__(self, session: Session):
        """
        Initialize complaint comment repository.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(ComplaintComment, session)

    # ==================== CRUD Operations ====================

    def create_comment(
        self,
        complaint_id: str,
        commented_by: str,
        comment_text: str,
        is_internal: bool = False,
        attachments: Optional[List[str]] = None,
        mentioned_users: Optional[List[str]] = None,
        parent_comment_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ComplaintComment:
        """
        Create a new comment or reply.
        
        Args:
            complaint_id: Complaint identifier
            commented_by: User creating the comment
            comment_text: Comment content
            is_internal: Internal note flag
            attachments: List of attachment URLs
            mentioned_users: List of mentioned user IDs
            parent_comment_id: Parent comment for threading
            metadata: Additional metadata
            
        Returns:
            Created comment instance
        """
        # Calculate thread depth if reply
        thread_depth = 0
        if parent_comment_id:
            parent = self.find_by_id(parent_comment_id)
            if parent:
                thread_depth = parent.thread_depth + 1
        
        comment = ComplaintComment(
            complaint_id=complaint_id,
            commented_by=commented_by,
            comment_text=comment_text,
            is_internal=is_internal,
            attachments=attachments or [],
            mentioned_users=mentioned_users or [],
            parent_comment_id=parent_comment_id,
            thread_depth=thread_depth,
            metadata=metadata or {},
        )
        
        return self.create(comment)

    def update_comment(
        self,
        comment_id: str,
        comment_text: str,
        attachments: Optional[List[str]] = None,
    ) -> Optional[ComplaintComment]:
        """
        Update comment and track edit.
        
        Args:
            comment_id: Comment identifier
            comment_text: Updated comment text
            attachments: Updated attachments list
            
        Returns:
            Updated comment or None
        """
        comment = self.find_by_id(comment_id)
        if not comment:
            return None
        
        now = datetime.now(timezone.utc)
        
        update_data = {
            "comment_text": comment_text,
            "is_edited": True,
            "edited_at": now,
            "edit_count": comment.edit_count + 1,
        }
        
        if attachments is not None:
            update_data["attachments"] = attachments
        
        return self.update(comment_id, update_data)

    # ==================== Query Operations ====================

    def find_by_complaint(
        self,
        complaint_id: str,
        include_internal: bool = True,
        include_deleted: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintComment]:
        """
        Find all comments for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            include_internal: Include internal notes
            include_deleted: Include soft-deleted comments
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of comments
        """
        query = select(ComplaintComment).where(
            ComplaintComment.complaint_id == complaint_id
        )
        
        if not include_internal:
            query = query.where(ComplaintComment.is_internal == False)
        
        if not include_deleted:
            query = query.where(ComplaintComment.deleted_at.is_(None))
        
        query = query.order_by(ComplaintComment.created_at.asc())
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_root_comments(
        self,
        complaint_id: str,
        include_internal: bool = True,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintComment]:
        """
        Find root-level comments (not replies).
        
        Args:
            complaint_id: Complaint identifier
            include_internal: Include internal notes
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of root comments
        """
        query = select(ComplaintComment).where(
            and_(
                ComplaintComment.complaint_id == complaint_id,
                ComplaintComment.parent_comment_id.is_(None),
                ComplaintComment.deleted_at.is_(None),
            )
        )
        
        if not include_internal:
            query = query.where(ComplaintComment.is_internal == False)
        
        query = query.order_by(ComplaintComment.created_at.asc())
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_replies(
        self,
        parent_comment_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintComment]:
        """
        Find all replies to a comment.
        
        Args:
            parent_comment_id: Parent comment identifier
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of reply comments
        """
        query = select(ComplaintComment).where(
            and_(
                ComplaintComment.parent_comment_id == parent_comment_id,
                ComplaintComment.deleted_at.is_(None),
            )
        )
        
        query = query.order_by(ComplaintComment.created_at.asc())
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_by_user(
        self,
        user_id: str,
        complaint_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintComment]:
        """
        Find comments by a specific user.
        
        Args:
            user_id: User identifier
            complaint_id: Optional complaint filter
            date_from: Start date filter
            date_to: End date filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of user's comments
        """
        query = select(ComplaintComment).where(
            and_(
                ComplaintComment.commented_by == user_id,
                ComplaintComment.deleted_at.is_(None),
            )
        )
        
        if complaint_id:
            query = query.where(ComplaintComment.complaint_id == complaint_id)
        
        if date_from:
            query = query.where(ComplaintComment.created_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintComment.created_at <= date_to)
        
        query = query.order_by(desc(ComplaintComment.created_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_with_mentions(
        self,
        user_id: str,
        complaint_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintComment]:
        """
        Find comments mentioning a specific user.
        
        Args:
            user_id: User identifier
            complaint_id: Optional complaint filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of comments with user mentions
        """
        query = select(ComplaintComment).where(
            and_(
                ComplaintComment.mentioned_users.contains([user_id]),
                ComplaintComment.deleted_at.is_(None),
            )
        )
        
        if complaint_id:
            query = query.where(ComplaintComment.complaint_id == complaint_id)
        
        query = query.order_by(desc(ComplaintComment.created_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_internal_notes(
        self,
        complaint_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ComplaintComment]:
        """
        Find internal notes for a complaint.
        
        Args:
            complaint_id: Complaint identifier
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of internal notes
        """
        query = select(ComplaintComment).where(
            and_(
                ComplaintComment.complaint_id == complaint_id,
                ComplaintComment.is_internal == True,
                ComplaintComment.deleted_at.is_(None),
            )
        )
        
        query = query.order_by(ComplaintComment.created_at.asc())
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ==================== Threading Operations ====================

    def get_comment_thread(
        self,
        comment_id: str,
        max_depth: Optional[int] = None,
    ) -> List[ComplaintComment]:
        """
        Get entire comment thread (parent and all descendants).
        
        Args:
            comment_id: Root comment identifier
            max_depth: Maximum thread depth to fetch
            
        Returns:
            List of comments in thread
        """
        thread_comments = []
        
        # Get root comment
        root = self.find_by_id(comment_id)
        if not root:
            return []
        
        thread_comments.append(root)
        
        # Recursively get all replies
        def get_replies_recursive(parent_id: str, current_depth: int):
            if max_depth and current_depth >= max_depth:
                return
            
            replies = self.find_replies(parent_id)
            for reply in replies:
                thread_comments.append(reply)
                get_replies_recursive(reply.id, current_depth + 1)
        
        get_replies_recursive(comment_id, 0)
        
        return thread_comments

    def get_thread_summary(
        self,
        comment_id: str,
    ) -> Dict[str, Any]:
        """
        Get summary statistics for a comment thread.
        
        Args:
            comment_id: Root comment identifier
            
        Returns:
            Dictionary with thread statistics
        """
        thread = self.get_comment_thread(comment_id)
        
        if not thread:
            return {
                "comment_id": comment_id,
                "total_comments": 0,
                "max_depth": 0,
                "unique_commenters": 0,
            }
        
        max_depth = max(c.thread_depth for c in thread)
        unique_commenters = len(set(c.commented_by for c in thread))
        
        return {
            "comment_id": comment_id,
            "total_comments": len(thread),
            "max_depth": max_depth,
            "unique_commenters": unique_commenters,
            "latest_comment_at": max(c.created_at for c in thread),
        }

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
            Dictionary with comment statistics
        """
        # Total count
        total_query = select(func.count()).where(
            and_(
                ComplaintComment.complaint_id == complaint_id,
                ComplaintComment.deleted_at.is_(None),
            )
        )
        total = self.session.execute(total_query).scalar_one()
        
        # Internal notes count
        internal_query = select(func.count()).where(
            and_(
                ComplaintComment.complaint_id == complaint_id,
                ComplaintComment.is_internal == True,
                ComplaintComment.deleted_at.is_(None),
            )
        )
        internal = self.session.execute(internal_query).scalar_one()
        
        # Public comments count
        public = total - internal
        
        # Unique commenters
        unique_query = select(func.count(func.distinct(ComplaintComment.commented_by))).where(
            and_(
                ComplaintComment.complaint_id == complaint_id,
                ComplaintComment.deleted_at.is_(None),
            )
        )
        unique_commenters = self.session.execute(unique_query).scalar_one()
        
        # Latest comment
        latest_query = (
            select(ComplaintComment.created_at)
            .where(
                and_(
                    ComplaintComment.complaint_id == complaint_id,
                    ComplaintComment.deleted_at.is_(None),
                )
            )
            .order_by(desc(ComplaintComment.created_at))
            .limit(1)
        )
        latest_result = self.session.execute(latest_query)
        latest = latest_result.scalar_one_or_none()
        
        return {
            "complaint_id": complaint_id,
            "total_comments": total,
            "public_comments": public,
            "internal_notes": internal,
            "unique_commenters": unique_commenters,
            "latest_comment_at": latest,
        }

    def get_user_comment_activity(
        self,
        user_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get comment activity statistics for a user.
        
        Args:
            user_id: User identifier
            date_from: Start date filter
            date_to: End date filter
            
        Returns:
            Dictionary with activity statistics
        """
        query = select(ComplaintComment).where(
            and_(
                ComplaintComment.commented_by == user_id,
                ComplaintComment.deleted_at.is_(None),
            )
        )
        
        if date_from:
            query = query.where(ComplaintComment.created_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintComment.created_at <= date_to)
        
        result = self.session.execute(query)
        comments = list(result.scalars().all())
        
        if not comments:
            return {
                "user_id": user_id,
                "total_comments": 0,
                "internal_notes": 0,
                "public_comments": 0,
                "edited_comments": 0,
                "average_edits_per_comment": 0,
            }
        
        total = len(comments)
        internal = len([c for c in comments if c.is_internal])
        public = total - internal
        edited = len([c for c in comments if c.is_edited])
        total_edits = sum(c.edit_count for c in comments)
        
        return {
            "user_id": user_id,
            "total_comments": total,
            "internal_notes": internal,
            "public_comments": public,
            "edited_comments": edited,
            "total_edits": total_edits,
            "average_edits_per_comment": total_edits / total if total > 0 else 0,
        }

    # ==================== Search Operations ====================

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
        Advanced comment search with filters.
        
        Args:
            complaint_id: Filter by complaint
            search_term: Search in comment text
            user_id: Filter by commenter
            is_internal: Filter by internal/public
            date_from: Start date filter
            date_to: End date filter
            skip: Number of records to skip
            limit: Maximum records to return
            
        Returns:
            List of matching comments
        """
        query = select(ComplaintComment).where(
            ComplaintComment.deleted_at.is_(None)
        )
        
        if complaint_id:
            query = query.where(ComplaintComment.complaint_id == complaint_id)
        
        if search_term:
            search_pattern = f"%{search_term}%"
            query = query.where(ComplaintComment.comment_text.ilike(search_pattern))
        
        if user_id:
            query = query.where(ComplaintComment.commented_by == user_id)
        
        if is_internal is not None:
            query = query.where(ComplaintComment.is_internal == is_internal)
        
        if date_from:
            query = query.where(ComplaintComment.created_at >= date_from)
        
        if date_to:
            query = query.where(ComplaintComment.created_at <= date_to)
        
        query = query.order_by(desc(ComplaintComment.created_at))
        query = query.offset(skip).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())