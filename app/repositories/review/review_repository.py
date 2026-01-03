"""
Review Repository - Core review CRUD and query operations.

Implements comprehensive review management with advanced querying,
filtering, and analytics integration.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, desc, asc, case
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.review import (
    Review,
    ReviewAspect,
    ReviewVerification,
    ReviewStatusHistory,
)
from app.models.common.enums import ReviewStatus
from app.repositories.base import BaseRepository, PaginatedResult, AuditContext


class ReviewRepository(BaseRepository[Review]):
    """
    Repository for Review entity operations.
    
    Provides comprehensive review management with advanced querying,
    filtering, analytics, and lifecycle operations.
    """
    
    def __init__(self, session: Session):
        """
        Initialize review repository.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(Review, session)
    
    # ==================== CRUD Operations ====================
    
    def create_review(
        self,
        hostel_id: UUID,
        reviewer_id: UUID,
        data: Dict[str, Any],
        audit_context: Optional[AuditContext] = None
    ) -> Review:
        """
        Create new review with validation and initial status.
        
        Args:
            hostel_id: Hostel being reviewed
            reviewer_id: User creating the review
            data: Review data including ratings and content
            audit_context: Audit information
            
        Returns:
            Created review entity
            
        Raises:
            ValueError: If validation fails or duplicate review exists
        """
        # Check for existing review
        existing = self.find_by_criteria({
            'hostel_id': hostel_id,
            'reviewer_id': reviewer_id,
            'deleted_at': None
        })
        
        if existing:
            raise ValueError(
                f"Review already exists for user {reviewer_id} and hostel {hostel_id}"
            )
        
        # Prepare review data
        review_data = {
            'hostel_id': hostel_id,
            'reviewer_id': reviewer_id,
            'overall_rating': data['overall_rating'],
            'title': data['title'],
            'review_text': data['review_text'],
            'would_recommend': data.get('would_recommend', True),
            'status': ReviewStatus.DRAFT,
            'language': data.get('language', 'en'),
            'ip_address': data.get('ip_address'),
            'user_agent': data.get('user_agent'),
        }
        
        # Add optional fields
        optional_fields = [
            'student_id', 'booking_id', 'cleanliness_rating',
            'food_quality_rating', 'staff_behavior_rating',
            'security_rating', 'value_for_money_rating',
            'amenities_rating', 'location_rating',
            'wifi_quality_rating', 'maintenance_rating',
            'stay_duration_months', 'check_in_date', 'check_out_date',
            'photos', 'pros', 'cons'
        ]
        
        for field in optional_fields:
            if field in data:
                review_data[field] = data[field]
        
        # Create review
        review = self.create(review_data, audit_context)
        
        # Create initial status history
        self._create_status_history(
            review.id,
            None,
            ReviewStatus.DRAFT,
            reviewer_id,
            "Review created"
        )
        
        return review
    
    def update_review(
        self,
        review_id: UUID,
        data: Dict[str, Any],
        user_id: UUID,
        audit_context: Optional[AuditContext] = None
    ) -> Review:
        """
        Update existing review with edit tracking.
        
        Args:
            review_id: Review to update
            data: Updated review data
            user_id: User making the update
            audit_context: Audit information
            
        Returns:
            Updated review entity
            
        Raises:
            ValueError: If review not found or not editable
        """
        review = self.find_by_id(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        
        # Check if review is editable
        if review.status not in [ReviewStatus.DRAFT, ReviewStatus.PUBLISHED]:
            raise ValueError(f"Review in status {review.status} cannot be edited")
        
        # Update allowed fields
        updateable_fields = [
            'title', 'review_text', 'overall_rating',
            'cleanliness_rating', 'food_quality_rating',
            'staff_behavior_rating', 'security_rating',
            'value_for_money_rating', 'amenities_rating',
            'location_rating', 'wifi_quality_rating',
            'maintenance_rating', 'would_recommend',
            'pros', 'cons', 'photos'
        ]
        
        update_data = {
            field: data[field]
            for field in updateable_fields
            if field in data
        }
        
        # Mark as edited
        review.mark_as_edited()
        
        # Update review
        for field, value in update_data.items():
            setattr(review, field, value)
        
        self.session.commit()
        self.session.refresh(review)
        
        return review
    
    def delete_review(
        self,
        review_id: UUID,
        user_id: UUID,
        reason: Optional[str] = None,
        audit_context: Optional[AuditContext] = None
    ) -> bool:
        """
        Soft delete review with audit trail.
        
        Args:
            review_id: Review to delete
            user_id: User performing deletion
            reason: Deletion reason
            audit_context: Audit information
            
        Returns:
            True if deleted successfully
        """
        review = self.find_by_id(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        
        # Update status
        review.status = ReviewStatus.DELETED
        review.is_published = False
        
        # Soft delete
        return self.soft_delete(review_id, audit_context)
    
    # ==================== Query Operations ====================
    
    def find_by_hostel(
        self,
        hostel_id: UUID,
        filters: Optional[Dict[str, Any]] = None,
        pagination: Optional[Dict[str, Any]] = None,
        include_relationships: bool = False
    ) -> PaginatedResult[Review]:
        """
        Find reviews for specific hostel with filtering and pagination.
        
        Args:
            hostel_id: Hostel ID to filter by
            filters: Additional filter criteria
            pagination: Pagination parameters (page, per_page)
            include_relationships: Whether to load related entities
            
        Returns:
            Paginated review results
        """
        query = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.deleted_at.is_(None)
        )
        
        # Apply filters
        if filters:
            query = self._apply_filters(query, filters)
        
        # Load relationships if requested
        if include_relationships:
            query = query.options(
                joinedload(Review.reviewer),
                joinedload(Review.student),
                selectinload(Review.aspects),
                joinedload(Review.verification),
            )
        
        # Default ordering by most helpful and recent
        query = query.order_by(
            desc(Review.helpful_count),
            desc(Review.created_at)
        )
        
        return self._paginate_query(query, pagination)
    
    def find_by_reviewer(
        self,
        reviewer_id: UUID,
        filters: Optional[Dict[str, Any]] = None,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginatedResult[Review]:
        """
        Find reviews by specific reviewer.
        
        Args:
            reviewer_id: Reviewer user ID
            filters: Additional filter criteria
            pagination: Pagination parameters
            
        Returns:
            Paginated review results
        """
        query = self.session.query(Review).filter(
            Review.reviewer_id == reviewer_id,
            Review.deleted_at.is_(None)
        )
        
        if filters:
            query = self._apply_filters(query, filters)
        
        query = query.order_by(desc(Review.created_at))
        
        return self._paginate_query(query, pagination)
    
    def find_by_status(
        self,
        status: ReviewStatus,
        hostel_id: Optional[UUID] = None,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginatedResult[Review]:
        """
        Find reviews by status with optional hostel filter.
        
        Args:
            status: Review status to filter by
            hostel_id: Optional hostel ID filter
            pagination: Pagination parameters
            
        Returns:
            Paginated review results
        """
        query = self.session.query(Review).filter(
            Review.status == status,
            Review.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(Review.hostel_id == hostel_id)
        
        query = query.order_by(desc(Review.created_at))
        
        return self._paginate_query(query, pagination)
    
    def find_verified_reviews(
        self,
        hostel_id: Optional[UUID] = None,
        min_rating: Optional[Decimal] = None,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginatedResult[Review]:
        """
        Find verified stay reviews.
        
        Args:
            hostel_id: Optional hostel filter
            min_rating: Minimum rating filter
            pagination: Pagination parameters
            
        Returns:
            Paginated verified review results
        """
        query = self.session.query(Review).filter(
            Review.is_verified_stay == True,
            Review.is_published == True,
            Review.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(Review.hostel_id == hostel_id)
        
        if min_rating:
            query = query.filter(Review.overall_rating >= min_rating)
        
        query = query.order_by(desc(Review.verified_at))
        
        return self._paginate_query(query, pagination)
    
    def find_flagged_reviews(
        self,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginatedResult[Review]:
        """
        Find flagged reviews requiring moderation.
        
        Args:
            pagination: Pagination parameters
            
        Returns:
            Paginated flagged review results
        """
        query = self.session.query(Review).filter(
            Review.is_flagged == True,
            Review.deleted_at.is_(None)
        )
        
        query = query.order_by(desc(Review.flagged_at))
        
        return self._paginate_query(query, pagination)
    
    def find_pending_approval(
        self,
        hostel_id: Optional[UUID] = None,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginatedResult[Review]:
        """
        Find reviews pending approval.
        
        Args:
            hostel_id: Optional hostel filter
            pagination: Pagination parameters
            
        Returns:
            Paginated pending review results
        """
        query = self.session.query(Review).filter(
            Review.status == ReviewStatus.PENDING_APPROVAL,
            Review.is_approved == False,
            Review.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(Review.hostel_id == hostel_id)
        
        query = query.order_by(asc(Review.created_at))
        
        return self._paginate_query(query, pagination)
    
    def search_reviews(
        self,
        search_query: str,
        hostel_id: Optional[UUID] = None,
        filters: Optional[Dict[str, Any]] = None,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginatedResult[Review]:
        """
        Full-text search across review content.
        
        Args:
            search_query: Search text
            hostel_id: Optional hostel filter
            filters: Additional filters
            pagination: Pagination parameters
            
        Returns:
            Paginated search results
        """
        search_pattern = f"%{search_query}%"
        
        query = self.session.query(Review).filter(
            or_(
                Review.title.ilike(search_pattern),
                Review.review_text.ilike(search_pattern)
            ),
            Review.is_published == True,
            Review.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(Review.hostel_id == hostel_id)
        
        if filters:
            query = self._apply_filters(query, filters)
        
        # Order by relevance (simplified - would use full-text search in production)
        query = query.order_by(
            desc(Review.helpful_count),
            desc(Review.created_at)
        )
        
        return self._paginate_query(query, pagination)
    
    # ==================== Statistical Operations ====================
    
    def get_hostel_rating_summary(self, hostel_id: UUID) -> Dict[str, Any]:
        """
        Get rating summary for hostel.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Dictionary with rating statistics
        """
        result = self.session.query(
            func.count(Review.id).label('total_reviews'),
            func.avg(Review.overall_rating).label('average_rating'),
            func.min(Review.overall_rating).label('min_rating'),
            func.max(Review.overall_rating).label('max_rating'),
            func.sum(case((Review.would_recommend == True, 1), else_=0)).label('would_recommend_count')
        ).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            Review.deleted_at.is_(None)
        ).first()
        
        total_reviews = result.total_reviews or 0
        
        return {
            'total_reviews': total_reviews,
            'average_rating': float(result.average_rating) if result.average_rating else 0.0,
            'min_rating': float(result.min_rating) if result.min_rating else 0.0,
            'max_rating': float(result.max_rating) if result.max_rating else 0.0,
            'would_recommend_count': result.would_recommend_count or 0,
            'would_recommend_percentage': (
                (result.would_recommend_count / total_reviews * 100)
                if total_reviews > 0 else 0.0
            )
        }
    
    def get_rating_distribution(self, hostel_id: UUID) -> Dict[str, int]:
        """
        Get rating distribution for hostel.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Dictionary mapping rating values to counts
        """
        results = self.session.query(
            Review.overall_rating,
            func.count(Review.id).label('count')
        ).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            Review.deleted_at.is_(None)
        ).group_by(
            Review.overall_rating
        ).all()
        
        distribution = {
            '5.0': 0, '4.5': 0, '4.0': 0,
            '3.5': 0, '3.0': 0, '2.5': 0,
            '2.0': 0, '1.5': 0, '1.0': 0
        }
        
        for rating, count in results:
            distribution[str(float(rating))] = count
        
        return distribution
    
    def get_aspect_ratings(self, hostel_id: UUID) -> Dict[str, Decimal]:
        """
        Get average aspect ratings for hostel.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            Dictionary mapping aspect names to average ratings
        """
        result = self.session.query(
            func.avg(Review.cleanliness_rating).label('cleanliness'),
            func.avg(Review.food_quality_rating).label('food_quality'),
            func.avg(Review.staff_behavior_rating).label('staff_behavior'),
            func.avg(Review.security_rating).label('security'),
            func.avg(Review.value_for_money_rating).label('value_for_money'),
            func.avg(Review.amenities_rating).label('amenities'),
            func.avg(Review.location_rating).label('location'),
            func.avg(Review.wifi_quality_rating).label('wifi_quality'),
            func.avg(Review.maintenance_rating).label('maintenance')
        ).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            Review.deleted_at.is_(None)
        ).first()
        
        return {
            'cleanliness': Decimal(str(result.cleanliness or 0)).quantize(Decimal('0.01')),
            'food_quality': Decimal(str(result.food_quality or 0)).quantize(Decimal('0.01')),
            'staff_behavior': Decimal(str(result.staff_behavior or 0)).quantize(Decimal('0.01')),
            'security': Decimal(str(result.security or 0)).quantize(Decimal('0.01')),
            'value_for_money': Decimal(str(result.value_for_money or 0)).quantize(Decimal('0.01')),
            'amenities': Decimal(str(result.amenities or 0)).quantize(Decimal('0.01')),
            'location': Decimal(str(result.location or 0)).quantize(Decimal('0.01')),
            'wifi_quality': Decimal(str(result.wifi_quality or 0)).quantize(Decimal('0.01')),
            'maintenance': Decimal(str(result.maintenance or 0)).quantize(Decimal('0.01'))
        }
    
    def get_review_trends(
        self,
        hostel_id: UUID,
        period_days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get review rating trends over time.
        
        Args:
            hostel_id: Hostel ID
            period_days: Number of days to analyze
            
        Returns:
            List of daily rating averages
        """
        start_date = datetime.utcnow() - timedelta(days=period_days)
        
        results = self.session.query(
            func.date(Review.created_at).label('date'),
            func.avg(Review.overall_rating).label('avg_rating'),
            func.count(Review.id).label('count')
        ).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            Review.created_at >= start_date,
            Review.deleted_at.is_(None)
        ).group_by(
            func.date(Review.created_at)
        ).order_by(
            func.date(Review.created_at)
        ).all()
        
        return [
            {
                'date': result.date.isoformat(),
                'average_rating': float(result.avg_rating),
                'review_count': result.count
            }
            for result in results
        ]
    
    # ==================== Lifecycle Operations ====================
    
    def approve_review(
        self,
        review_id: UUID,
        admin_id: UUID,
        notes: Optional[str] = None
    ) -> Review:
        """
        Approve review for publication.
        
        Args:
            review_id: Review to approve
            admin_id: Admin approving the review
            notes: Optional approval notes
            
        Returns:
            Approved review
        """
        review = self.find_by_id(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        
        previous_status = review.status
        review.approve(admin_id)
        
        self._create_status_history(
            review_id,
            previous_status,
            ReviewStatus.PUBLISHED,
            admin_id,
            notes or "Review approved"
        )
        
        self.session.commit()
        self.session.refresh(review)
        
        return review
    
    def reject_review(
        self,
        review_id: UUID,
        admin_id: UUID,
        reason: str
    ) -> Review:
        """
        Reject review with reason.
        
        Args:
            review_id: Review to reject
            admin_id: Admin rejecting the review
            reason: Rejection reason
            
        Returns:
            Rejected review
        """
        review = self.find_by_id(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        
        previous_status = review.status
        review.reject(admin_id, reason)
        
        self._create_status_history(
            review_id,
            previous_status,
            ReviewStatus.REJECTED,
            admin_id,
            f"Review rejected: {reason}"
        )
        
        self.session.commit()
        self.session.refresh(review)
        
        return review
    
    def flag_review(
        self,
        review_id: UUID,
        user_id: UUID,
        reason: str
    ) -> Review:
        """
        Flag review for moderation.
        
        Args:
            review_id: Review to flag
            user_id: User flagging the review
            reason: Flag reason
            
        Returns:
            Flagged review
        """
        review = self.find_by_id(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        
        review.flag(user_id, reason)
        
        self.session.commit()
        self.session.refresh(review)
        
        return review
    
    def unflag_review(self, review_id: UUID) -> Review:
        """
        Remove flag from review.
        
        Args:
            review_id: Review to unflag
            
        Returns:
            Unflagged review
        """
        review = self.find_by_id(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        
        review.unflag()
        
        self.session.commit()
        self.session.refresh(review)
        
        return review
    
    def verify_stay(
        self,
        review_id: UUID,
        method: str,
        verified_by: Optional[UUID] = None
    ) -> Review:
        """
        Mark review as verified stay.
        
        Args:
            review_id: Review to verify
            method: Verification method used
            verified_by: Optional admin ID who verified
            
        Returns:
            Verified review
        """
        review = self.find_by_id(review_id)
        if not review:
            raise ValueError(f"Review {review_id} not found")
        
        review.verify_stay(method)
        
        self.session.commit()
        self.session.refresh(review)
        
        return review
    
    # ==================== Helper Methods ====================
    
    def _apply_filters(self, query, filters: Dict[str, Any]):
        """Apply filter criteria to query."""
        if 'min_rating' in filters:
            query = query.filter(Review.overall_rating >= filters['min_rating'])
        
        if 'max_rating' in filters:
            query = query.filter(Review.overall_rating <= filters['max_rating'])
        
        if 'verified_only' in filters and filters['verified_only']:
            query = query.filter(Review.is_verified_stay == True)
        
        if 'with_photos' in filters and filters['with_photos']:
            query = query.filter(Review.photos != [])
        
        if 'would_recommend' in filters:
            query = query.filter(Review.would_recommend == filters['would_recommend'])
        
        if 'status' in filters:
            query = query.filter(Review.status == filters['status'])
        
        if 'created_after' in filters:
            query = query.filter(Review.created_at >= filters['created_after'])
        
        if 'created_before' in filters:
            query = query.filter(Review.created_at <= filters['created_before'])
        
        return query
    
    def _paginate_query(
        self,
        query,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginatedResult[Review]:
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
    
    def _create_status_history(
        self,
        review_id: UUID,
        previous_status: Optional[ReviewStatus],
        new_status: ReviewStatus,
        changed_by: UUID,
        reason: str
    ):
        """Create status history entry."""
        history = ReviewStatusHistory(
            review_id=review_id,
            previous_status=previous_status,
            new_status=new_status,
            changed_by=changed_by,
            change_reason=reason
        )
        self.session.add(history)