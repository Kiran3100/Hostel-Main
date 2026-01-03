"""
Review Moderation Repository - Moderation workflow and content safety operations.

Implements moderation queue management, flagging, auto-moderation,
and compliance tracking.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, desc, asc, case
from sqlalchemy.orm import Session, joinedload

from app.models.review import Review
from app.models.review.review_moderation import (
    ReviewModerationLog,
    ReviewFlag,
    ReviewModerationQueue,
    ReviewAutoModeration,
)
from app.models.common.enums import ReviewStatus
from app.repositories.base import BaseRepository, PaginatedResult


class ReviewModerationRepository(BaseRepository[ReviewModerationLog]):
    """
    Repository for review moderation operations.
    
    Manages moderation workflows, flagging, queue management,
    and automated content safety checks.
    """
    
    def __init__(self, session: Session):
        """
        Initialize review moderation repository.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(ReviewModerationLog, session)
    
    # ==================== Moderation Log Operations ====================
    
    def log_moderation_action(
        self,
        review_id: UUID,
        action: str,
        moderator_id: Optional[UUID] = None,
        moderator_name: Optional[str] = None,
        action_reason: Optional[str] = None,
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
        is_automated: bool = False,
        automation_confidence: Optional[Decimal] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ReviewModerationLog:
        """
        Create moderation action log entry.
        
        Args:
            review_id: Review being moderated
            action: Moderation action taken
            moderator_id: Admin performing action
            moderator_name: Name of moderator
            action_reason: Reason for action
            previous_status: Status before action
            new_status: Status after action
            is_automated: Whether action was automated
            automation_confidence: Confidence score for automated actions
            metadata: Additional metadata
            
        Returns:
            Created moderation log entry
        """
        log_entry = ReviewModerationLog(
            review_id=review_id,
            action=action,
            moderator_id=moderator_id,
            moderator_name=moderator_name,
            action_reason=action_reason,
            previous_status=previous_status,
            new_status=new_status,
            is_automated=is_automated,
            automation_confidence=automation_confidence,
            metadata=metadata
        )
        
        self.session.add(log_entry)
        self.session.commit()
        self.session.refresh(log_entry)
        
        return log_entry
    
    def get_moderation_history(
        self,
        review_id: UUID,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginatedResult[ReviewModerationLog]:
        """
        Get moderation history for review.
        
        Args:
            review_id: Review ID
            pagination: Pagination parameters
            
        Returns:
            Paginated moderation log entries
        """
        query = self.session.query(ReviewModerationLog).filter(
            ReviewModerationLog.review_id == review_id
        ).order_by(desc(ReviewModerationLog.created_at))
        
        return self._paginate_query(query, pagination)
    
    def get_moderator_activity(
        self,
        moderator_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginatedResult[ReviewModerationLog]:
        """
        Get moderation activity for specific moderator.
        
        Args:
            moderator_id: Moderator admin ID
            start_date: Start of date range
            end_date: End of date range
            pagination: Pagination parameters
            
        Returns:
            Paginated moderation log entries
        """
        query = self.session.query(ReviewModerationLog).filter(
            ReviewModerationLog.moderator_id == moderator_id
        )
        
        if start_date:
            query = query.filter(ReviewModerationLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(ReviewModerationLog.created_at <= end_date)
        
        query = query.order_by(desc(ReviewModerationLog.created_at))
        
        return self._paginate_query(query, pagination)
    
    def get_moderation_statistics(
        self,
        moderator_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get moderation statistics.
        
        Args:
            moderator_id: Optional moderator filter
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Dictionary with moderation statistics
        """
        query = self.session.query(ReviewModerationLog)
        
        if moderator_id:
            query = query.filter(ReviewModerationLog.moderator_id == moderator_id)
        
        if start_date:
            query = query.filter(ReviewModerationLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(ReviewModerationLog.created_at <= end_date)
        
        # Get action counts
        action_counts = self.session.query(
            ReviewModerationLog.action,
            func.count(ReviewModerationLog.id).label('count')
        ).filter(
            ReviewModerationLog.moderator_id == moderator_id if moderator_id else True,
            ReviewModerationLog.created_at >= start_date if start_date else True,
            ReviewModerationLog.created_at <= end_date if end_date else True
        ).group_by(ReviewModerationLog.action).all()
        
        total_actions = query.count()
        automated_actions = query.filter(ReviewModerationLog.is_automated == True).count()
        
        return {
            'total_actions': total_actions,
            'automated_actions': automated_actions,
            'manual_actions': total_actions - automated_actions,
            'action_breakdown': {action: count for action, count in action_counts},
            'automation_rate': (automated_actions / total_actions * 100) if total_actions > 0 else 0
        }
    
    # ==================== Flag Operations ====================
    
    def create_flag(
        self,
        review_id: UUID,
        reporter_id: Optional[UUID] = None,
        reporter_email: Optional[str] = None,
        flag_reason: str,
        flag_description: Optional[str] = None,
        flag_category: Optional[str] = None,
        priority: str = 'medium',
        metadata: Optional[Dict[str, Any]] = None
    ) -> ReviewFlag:
        """
        Create review flag.
        
        Args:
            review_id: Review being flagged
            reporter_id: User reporting the review
            reporter_email: Reporter email if not logged in
            flag_reason: Reason for flagging
            flag_description: Detailed description
            flag_category: Flag category
            priority: Flag priority level
            metadata: Additional metadata
            
        Returns:
            Created flag entry
        """
        flag = ReviewFlag(
            review_id=review_id,
            reporter_id=reporter_id,
            reporter_email=reporter_email,
            flag_reason=flag_reason,
            flag_description=flag_description,
            flag_category=flag_category,
            priority=priority,
            metadata=metadata
        )
        
        self.session.add(flag)
        self.session.commit()
        self.session.refresh(flag)
        
        # Update review flag count
        review = self.session.query(Review).filter(Review.id == review_id).first()
        if review:
            review.is_flagged = True
            review.report_count += 1
            self.session.commit()
        
        return flag
    
    def resolve_flag(
        self,
        flag_id: UUID,
        admin_id: UUID,
        resolution_action: str,
        resolution_notes: Optional[str] = None
    ) -> ReviewFlag:
        """
        Resolve review flag.
        
        Args:
            flag_id: Flag to resolve
            admin_id: Admin resolving the flag
            resolution_action: Action taken
            resolution_notes: Resolution notes
            
        Returns:
            Resolved flag
        """
        flag = self.session.query(ReviewFlag).filter(
            ReviewFlag.id == flag_id
        ).first()
        
        if not flag:
            raise ValueError(f"Flag {flag_id} not found")
        
        flag.resolve(admin_id, resolution_action, resolution_notes)
        
        self.session.commit()
        self.session.refresh(flag)
        
        return flag
    
    def get_pending_flags(
        self,
        priority: Optional[str] = None,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginatedResult[ReviewFlag]:
        """
        Get pending flags requiring resolution.
        
        Args:
            priority: Optional priority filter
            pagination: Pagination parameters
            
        Returns:
            Paginated pending flags
        """
        query = self.session.query(ReviewFlag).filter(
            ReviewFlag.is_resolved == False
        )
        
        if priority:
            query = query.filter(ReviewFlag.priority == priority)
        
        query = query.order_by(
            case(
                (ReviewFlag.priority == 'urgent', 1),
                (ReviewFlag.priority == 'high', 2),
                (ReviewFlag.priority == 'medium', 3),
                else_=4
            ),
            asc(ReviewFlag.created_at)
        )
        
        return self._paginate_query(query, pagination)
    
    def get_review_flags(
        self,
        review_id: UUID,
        include_resolved: bool = False
    ) -> List[ReviewFlag]:
        """
        Get all flags for specific review.
        
        Args:
            review_id: Review ID
            include_resolved: Whether to include resolved flags
            
        Returns:
            List of flags
        """
        query = self.session.query(ReviewFlag).filter(
            ReviewFlag.review_id == review_id
        )
        
        if not include_resolved:
            query = query.filter(ReviewFlag.is_resolved == False)
        
        return query.order_by(desc(ReviewFlag.created_at)).all()
    
    def get_flag_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get flag statistics.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Dictionary with flag statistics
        """
        query = self.session.query(ReviewFlag)
        
        if start_date:
            query = query.filter(ReviewFlag.created_at >= start_date)
        
        if end_date:
            query = query.filter(ReviewFlag.created_at <= end_date)
        
        total_flags = query.count()
        pending_flags = query.filter(ReviewFlag.is_resolved == False).count()
        resolved_flags = query.filter(ReviewFlag.is_resolved == True).count()
        
        # Get reason breakdown
        reason_counts = self.session.query(
            ReviewFlag.flag_reason,
            func.count(ReviewFlag.id).label('count')
        ).filter(
            ReviewFlag.created_at >= start_date if start_date else True,
            ReviewFlag.created_at <= end_date if end_date else True
        ).group_by(ReviewFlag.flag_reason).all()
        
        # Get priority breakdown
        priority_counts = self.session.query(
            ReviewFlag.priority,
            func.count(ReviewFlag.id).label('count')
        ).filter(
            ReviewFlag.is_resolved == False
        ).group_by(ReviewFlag.priority).all()
        
        return {
            'total_flags': total_flags,
            'pending_flags': pending_flags,
            'resolved_flags': resolved_flags,
            'resolution_rate': (resolved_flags / total_flags * 100) if total_flags > 0 else 0,
            'reason_breakdown': {reason: count for reason, count in reason_counts},
            'priority_breakdown': {priority: count for priority, count in priority_counts}
        }
    
    # ==================== Moderation Queue Operations ====================
    
    def add_to_queue(
        self,
        review_id: UUID,
        hostel_id: UUID,
        priority_score: int = 50,
        requires_immediate_attention: bool = False,
        spam_score: Optional[Decimal] = None,
        sentiment_score: Optional[Decimal] = None,
        toxicity_score: Optional[Decimal] = None,
        auto_recommendation: Optional[str] = None,
        recommendation_confidence: Optional[Decimal] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ReviewModerationQueue:
        """
        Add review to moderation queue.
        
        Args:
            review_id: Review to add
            hostel_id: Associated hostel
            priority_score: Priority score (0-100)
            requires_immediate_attention: Urgent flag
            spam_score: Spam detection score
            sentiment_score: Sentiment analysis score
            toxicity_score: Toxicity detection score
            auto_recommendation: Automated recommendation
            recommendation_confidence: Confidence in recommendation
            metadata: Additional metadata
            
        Returns:
            Created queue entry
        """
        # Check if already in queue
        existing = self.session.query(ReviewModerationQueue).filter(
            ReviewModerationQueue.review_id == review_id
        ).first()
        
        if existing:
            return existing
        
        queue_entry = ReviewModerationQueue(
            review_id=review_id,
            hostel_id=hostel_id,
            priority_score=priority_score,
            requires_immediate_attention=requires_immediate_attention,
            spam_score=spam_score,
            sentiment_score=sentiment_score,
            toxicity_score=toxicity_score,
            auto_recommendation=auto_recommendation,
            recommendation_confidence=recommendation_confidence,
            metadata=metadata
        )
        
        self.session.add(queue_entry)
        self.session.commit()
        self.session.refresh(queue_entry)
        
        return queue_entry
    
    def assign_to_moderator(
        self,
        queue_id: UUID,
        moderator_id: UUID
    ) -> ReviewModerationQueue:
        """
        Assign queue item to moderator.
        
        Args:
            queue_id: Queue entry ID
            moderator_id: Moderator to assign
            
        Returns:
            Updated queue entry
        """
        queue_entry = self.session.query(ReviewModerationQueue).filter(
            ReviewModerationQueue.id == queue_id
        ).first()
        
        if not queue_entry:
            raise ValueError(f"Queue entry {queue_id} not found")
        
        queue_entry.assign_to_moderator(moderator_id)
        
        self.session.commit()
        self.session.refresh(queue_entry)
        
        return queue_entry
    
    def complete_moderation(
        self,
        queue_id: UUID
    ) -> ReviewModerationQueue:
        """
        Mark queue item as completed.
        
        Args:
            queue_id: Queue entry ID
            
        Returns:
            Completed queue entry
        """
        queue_entry = self.session.query(ReviewModerationQueue).filter(
            ReviewModerationQueue.id == queue_id
        ).first()
        
        if not queue_entry:
            raise ValueError(f"Queue entry {queue_id} not found")
        
        queue_entry.complete()
        
        self.session.commit()
        self.session.refresh(queue_entry)
        
        return queue_entry
    
    def escalate_review(
        self,
        queue_id: UUID,
        reason: Optional[str] = None
    ) -> ReviewModerationQueue:
        """
        Escalate review for higher-level moderation.
        
        Args:
            queue_id: Queue entry ID
            reason: Escalation reason
            
        Returns:
            Escalated queue entry
        """
        queue_entry = self.session.query(ReviewModerationQueue).filter(
            ReviewModerationQueue.id == queue_id
        ).first()
        
        if not queue_entry:
            raise ValueError(f"Queue entry {queue_id} not found")
        
        queue_entry.escalate()
        if reason:
            queue_entry.moderator_notes = reason
        
        self.session.commit()
        self.session.refresh(queue_entry)
        
        return queue_entry
    
    def get_moderation_queue(
        self,
        status: Optional[str] = None,
        assigned_to: Optional[UUID] = None,
        hostel_id: Optional[UUID] = None,
        min_priority: Optional[int] = None,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginatedResult[ReviewModerationQueue]:
        """
        Get moderation queue items.
        
        Args:
            status: Queue status filter
            assigned_to: Moderator filter
            hostel_id: Hostel filter
            min_priority: Minimum priority score
            pagination: Pagination parameters
            
        Returns:
            Paginated queue entries
        """
        query = self.session.query(ReviewModerationQueue)
        
        if status:
            query = query.filter(ReviewModerationQueue.queue_status == status)
        
        if assigned_to:
            query = query.filter(ReviewModerationQueue.assigned_to == assigned_to)
        
        if hostel_id:
            query = query.filter(ReviewModerationQueue.hostel_id == hostel_id)
        
        if min_priority:
            query = query.filter(ReviewModerationQueue.priority_score >= min_priority)
        
        # Order by priority and urgency
        query = query.order_by(
            desc(ReviewModerationQueue.requires_immediate_attention),
            desc(ReviewModerationQueue.priority_score),
            asc(ReviewModerationQueue.created_at)
        )
        
        return self._paginate_query(query, pagination)
    
    def get_queue_statistics(self) -> Dict[str, Any]:
        """
        Get moderation queue statistics.
        
        Returns:
            Dictionary with queue statistics
        """
        total_items = self.session.query(ReviewModerationQueue).count()
        
        pending_items = self.session.query(ReviewModerationQueue).filter(
            ReviewModerationQueue.queue_status == 'pending'
        ).count()
        
        in_review_items = self.session.query(ReviewModerationQueue).filter(
            ReviewModerationQueue.queue_status == 'in_review'
        ).count()
        
        escalated_items = self.session.query(ReviewModerationQueue).filter(
            ReviewModerationQueue.queue_status == 'escalated'
        ).count()
        
        urgent_items = self.session.query(ReviewModerationQueue).filter(
            ReviewModerationQueue.requires_immediate_attention == True,
            ReviewModerationQueue.queue_status.in_(['pending', 'in_review'])
        ).count()
        
        # Average priority score
        avg_priority = self.session.query(
            func.avg(ReviewModerationQueue.priority_score)
        ).filter(
            ReviewModerationQueue.queue_status.in_(['pending', 'in_review'])
        ).scalar()
        
        # Average time in queue for pending items
        avg_time_query = self.session.query(
            ReviewModerationQueue.time_in_queue_hours
        ).filter(
            ReviewModerationQueue.queue_status == 'pending'
        )
        
        avg_time_in_queue = avg_time_query.with_entities(
            func.avg(ReviewModerationQueue.time_in_queue_hours)
        ).scalar()
        
        return {
            'total_items': total_items,
            'pending_items': pending_items,
            'in_review_items': in_review_items,
            'escalated_items': escalated_items,
            'urgent_items': urgent_items,
            'average_priority_score': float(avg_priority or 0),
            'average_time_in_queue_hours': float(avg_time_in_queue or 0)
        }
    
    # ==================== Auto-Moderation Operations ====================
    
    def create_auto_moderation(
        self,
        review_id: UUID,
        spam_score: Decimal,
        sentiment_score: Decimal,
        toxicity_score: Decimal,
        profanity_score: Optional[Decimal] = None,
        is_spam: bool = False,
        is_toxic: bool = False,
        has_profanity: bool = False,
        is_authentic: bool = True,
        sentiment_label: Optional[str] = None,
        detected_language: Optional[str] = None,
        language_confidence: Optional[Decimal] = None,
        contains_personal_info: bool = False,
        contains_promotional_content: bool = False,
        contains_hate_speech: bool = False,
        auto_decision: str = 'manual_review',
        decision_confidence: Decimal = Decimal('0.5'),
        detected_issues: Optional[List[str]] = None,
        flagged_keywords: Optional[List[str]] = None,
        model_version: Optional[str] = None,
        processing_time_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ReviewAutoModeration:
        """
        Create auto-moderation analysis record.
        
        Args:
            review_id: Review being analyzed
            spam_score: Spam probability (0-1)
            sentiment_score: Sentiment score (-1 to 1)
            toxicity_score: Toxicity score (0-1)
            profanity_score: Profanity score (0-1)
            is_spam: Whether classified as spam
            is_toxic: Whether classified as toxic
            has_profanity: Whether contains profanity
            is_authentic: Whether appears authentic
            sentiment_label: Sentiment classification
            detected_language: Detected language code
            language_confidence: Language detection confidence
            contains_personal_info: Whether contains PII
            contains_promotional_content: Whether promotional
            contains_hate_speech: Whether contains hate speech
            auto_decision: Automated decision
            decision_confidence: Decision confidence score
            detected_issues: List of detected issues
            flagged_keywords: List of flagged keywords
            model_version: AI model version used
            processing_time_ms: Processing time in milliseconds
            metadata: Additional metadata
            
        Returns:
            Created auto-moderation record
        """
        auto_mod = ReviewAutoModeration(
            review_id=review_id,
            spam_score=spam_score,
            sentiment_score=sentiment_score,
            toxicity_score=toxicity_score,
            profanity_score=profanity_score,
            is_spam=is_spam,
            is_toxic=is_toxic,
            has_profanity=has_profanity,
            is_authentic=is_authentic,
            sentiment_label=sentiment_label,
            detected_language=detected_language,
            language_confidence=language_confidence,
            contains_personal_info=contains_personal_info,
            contains_promotional_content=contains_promotional_content,
            contains_hate_speech=contains_hate_speech,
            auto_decision=auto_decision,
            decision_confidence=decision_confidence,
            detected_issues=detected_issues or [],
            flagged_keywords=flagged_keywords or [],
            model_version=model_version,
            processing_time_ms=processing_time_ms,
            metadata=metadata
        )
        
        self.session.add(auto_mod)
        self.session.commit()
        self.session.refresh(auto_mod)
        
        return auto_mod
    
    def get_auto_moderation(
        self,
        review_id: UUID
    ) -> Optional[ReviewAutoModeration]:
        """
        Get auto-moderation results for review.
        
        Args:
            review_id: Review ID
            
        Returns:
            Auto-moderation record if exists
        """
        return self.session.query(ReviewAutoModeration).filter(
            ReviewAutoModeration.review_id == review_id
        ).first()
    
    def get_reviews_for_auto_approval(
        self,
        min_confidence: Decimal = Decimal('0.9'),
        limit: int = 100
    ) -> List[ReviewAutoModeration]:
        """
        Get reviews that can be auto-approved.
        
        Args:
            min_confidence: Minimum confidence threshold
            limit: Maximum number of results
            
        Returns:
            List of auto-moderation records for auto-approval
        """
        return self.session.query(ReviewAutoModeration).filter(
            ReviewAutoModeration.auto_decision == 'auto_approve',
            ReviewAutoModeration.decision_confidence >= min_confidence,
            ReviewAutoModeration.is_spam == False,
            ReviewAutoModeration.is_toxic == False,
            ReviewAutoModeration.is_authentic == True
        ).limit(limit).all()
    
    def get_reviews_for_auto_rejection(
        self,
        min_confidence: Decimal = Decimal('0.9'),
        limit: int = 100
    ) -> List[ReviewAutoModeration]:
        """
        Get reviews that should be auto-rejected.
        
        Args:
            min_confidence: Minimum confidence threshold
            limit: Maximum number of results
            
        Returns:
            List of auto-moderation records for auto-rejection
        """
        return self.session.query(ReviewAutoModeration).filter(
            ReviewAutoModeration.auto_decision == 'auto_reject',
            ReviewAutoModeration.decision_confidence >= min_confidence,
            or_(
                ReviewAutoModeration.is_spam == True,
                ReviewAutoModeration.is_toxic == True,
                ReviewAutoModeration.is_authentic == False
            )
        ).limit(limit).all()
    
    def get_auto_moderation_statistics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get auto-moderation statistics.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Dictionary with auto-moderation statistics
        """
        query = self.session.query(ReviewAutoModeration)
        
        if start_date:
            query = query.filter(ReviewAutoModeration.created_at >= start_date)
        
        if end_date:
            query = query.filter(ReviewAutoModeration.created_at <= end_date)
        
        total_analyzed = query.count()
        
        spam_count = query.filter(ReviewAutoModeration.is_spam == True).count()
        toxic_count = query.filter(ReviewAutoModeration.is_toxic == True).count()
        inauthentic_count = query.filter(ReviewAutoModeration.is_authentic == False).count()
        
        # Decision breakdown
        decision_counts = self.session.query(
            ReviewAutoModeration.auto_decision,
            func.count(ReviewAutoModeration.id).label('count')
        ).filter(
            ReviewAutoModeration.created_at >= start_date if start_date else True,
            ReviewAutoModeration.created_at <= end_date if end_date else True
        ).group_by(ReviewAutoModeration.auto_decision).all()
        
        # Average scores
        avg_scores = self.session.query(
            func.avg(ReviewAutoModeration.spam_score).label('avg_spam'),
            func.avg(ReviewAutoModeration.toxicity_score).label('avg_toxicity'),
            func.avg(ReviewAutoModeration.decision_confidence).label('avg_confidence')
        ).filter(
            ReviewAutoModeration.created_at >= start_date if start_date else True,
            ReviewAutoModeration.created_at <= end_date if end_date else True
        ).first()
        
        return {
            'total_analyzed': total_analyzed,
            'spam_detected': spam_count,
            'toxic_detected': toxic_count,
            'inauthentic_detected': inauthentic_count,
            'spam_rate': (spam_count / total_analyzed * 100) if total_analyzed > 0 else 0,
            'toxic_rate': (toxic_count / total_analyzed * 100) if total_analyzed > 0 else 0,
            'decision_breakdown': {decision: count for decision, count in decision_counts},
            'average_spam_score': float(avg_scores.avg_spam or 0),
            'average_toxicity_score': float(avg_scores.avg_toxicity or 0),
            'average_confidence': float(avg_scores.avg_confidence or 0)
        }
    
    # ==================== Helper Methods ====================
    
    def _paginate_query(
        self,
        query,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginatedResult:
        """Paginate query results."""
        if not pagination:
            pagination = {'page': 1, 'per_page': 20}
        
        page = pagination.get('page', 1)
        per_page = pagination.get('per_page', 20)
        
        total = query.count()
        items = query.limit(per_page).offset((page - 1) * per_page).all()
        
        return PaginatedResult(
            items=items,
            total_count=total,
            page=page,
            page_size=per_page
        )