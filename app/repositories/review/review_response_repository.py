"""
Review Response Repository - Hostel response management.

Implements response creation, template management, and response analytics.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import Session, joinedload

from app.models.review import Review
from app.models.review.review_response import (
    ReviewResponse,
    ResponseTemplate,
    ResponseStatistics,
)
from app.repositories.base import BaseRepository, PaginationResult


class ReviewResponseRepository(BaseRepository[ReviewResponse]):
    """
    Repository for review response operations.
    
    Manages hostel responses to reviews, response templates,
    and response performance analytics.
    """
    
    def __init__(self, session: Session):
        """
        Initialize review response repository.
        
        Args:
            session: SQLAlchemy database session
        """
        super().__init__(ReviewResponse, session)
    
    # ==================== Response CRUD Operations ====================
    
    def create_response(
        self,
        review_id: UUID,
        hostel_id: UUID,
        response_text: str,
        responded_by: UUID,
        responded_by_name: str,
        responded_by_role: Optional[str] = None,
        template_id: Optional[UUID] = None,
        requires_approval: bool = False,
        language: str = 'en',
        metadata: Optional[Dict[str, Any]] = None
    ) -> ReviewResponse:
        """
        Create response to review.
        
        Args:
            review_id: Review being responded to
            hostel_id: Hostel providing response
            response_text: Response content
            responded_by: Admin user creating response
            responded_by_name: Name of responder
            responded_by_role: Role of responder
            template_id: Template used (if any)
            requires_approval: Whether response needs approval
            language: Response language
            metadata: Additional metadata
            
        Returns:
            Created response
            
        Raises:
            ValueError: If review already has response
        """
        # Check for existing response
        existing = self.session.query(ReviewResponse).filter(
            ReviewResponse.review_id == review_id
        ).first()
        
        if existing:
            raise ValueError(f"Review {review_id} already has a response")
        
        # Get review to calculate response time
        review = self.session.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise ValueError(f"Review {review_id} not found")
        
        # Create response
        response = ReviewResponse(
            review_id=review_id,
            hostel_id=hostel_id,
            response_text=response_text,
            responded_by=responded_by,
            responded_by_name=responded_by_name,
            responded_by_role=responded_by_role,
            template_id=template_id,
            is_from_template=template_id is not None,
            requires_approval=requires_approval,
            is_approved=not requires_approval,
            is_published=not requires_approval,
            language=language,
            metadata=metadata
        )
        
        # Calculate response time
        response.calculate_response_time(review.created_at)
        
        # Set published_at if auto-approved
        if not requires_approval:
            response.published_at = datetime.utcnow()
        
        self.session.add(response)
        self.session.commit()
        self.session.refresh(response)
        
        # Update template usage if template was used
        if template_id:
            self._increment_template_usage(template_id)
        
        return response
    
    def update_response(
        self,
        response_id: UUID,
        response_text: str,
        edit_reason: Optional[str] = None
    ) -> ReviewResponse:
        """
        Update existing response.
        
        Args:
            response_id: Response to update
            response_text: New response text
            edit_reason: Reason for edit
            
        Returns:
            Updated response
        """
        response = self.find_by_id(response_id)
        if not response:
            raise ValueError(f"Response {response_id} not found")
        
        # Mark as edited
        response.mark_as_edited(edit_reason)
        response.response_text = response_text
        
        self.session.commit()
        self.session.refresh(response)
        
        return response
    
    def approve_response(
        self,
        response_id: UUID,
        approved_by: UUID
    ) -> ReviewResponse:
        """
        Approve response for publication.
        
        Args:
            response_id: Response to approve
            approved_by: Admin approving response
            
        Returns:
            Approved response
        """
        response = self.find_by_id(response_id)
        if not response:
            raise ValueError(f"Response {response_id} not found")
        
        response.is_approved = True
        response.approved_by = approved_by
        response.approved_at = datetime.utcnow()
        response.publish()
        
        self.session.commit()
        self.session.refresh(response)
        
        return response
    
    def publish_response(
        self,
        response_id: UUID
    ) -> ReviewResponse:
        """
        Publish approved response.
        
        Args:
            response_id: Response to publish
            
        Returns:
            Published response
        """
        response = self.find_by_id(response_id)
        if not response:
            raise ValueError(f"Response {response_id} not found")
        
        if not response.is_approved:
            raise ValueError("Response must be approved before publishing")
        
        response.publish()
        
        self.session.commit()
        self.session.refresh(response)
        
        return response
    
    def unpublish_response(
        self,
        response_id: UUID
    ) -> ReviewResponse:
        """
        Unpublish response.
        
        Args:
            response_id: Response to unpublish
            
        Returns:
            Unpublished response
        """
        response = self.find_by_id(response_id)
        if not response:
            raise ValueError(f"Response {response_id} not found")
        
        response.unpublish()
        
        self.session.commit()
        self.session.refresh(response)
        
        return response
    
    def delete_response(
        self,
        response_id: UUID
    ) -> bool:
        """
        Delete response.
        
        Args:
            response_id: Response to delete
            
        Returns:
            True if deleted
        """
        response = self.find_by_id(response_id)
        if not response:
            return False
        
        self.session.delete(response)
        self.session.commit()
        
        return True
    
    # ==================== Query Operations ====================
    
    def get_response_by_review(
        self,
        review_id: UUID
    ) -> Optional[ReviewResponse]:
        """
        Get response for specific review.
        
        Args:
            review_id: Review ID
            
        Returns:
            Response if exists
        """
        return self.session.query(ReviewResponse).filter(
            ReviewResponse.review_id == review_id
        ).first()
    
    def get_hostel_responses(
        self,
        hostel_id: UUID,
        filters: Optional[Dict[str, Any]] = None,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginationResult[ReviewResponse]:
        """
        Get all responses for hostel.
        
        Args:
            hostel_id: Hostel ID
            filters: Optional filters
            pagination: Pagination parameters
            
        Returns:
            Paginated responses
        """
        query = self.session.query(ReviewResponse).filter(
            ReviewResponse.hostel_id == hostel_id
        )
        
        if filters:
            query = self._apply_response_filters(query, filters)
        
        query = query.order_by(desc(ReviewResponse.responded_at))
        
        return self._paginate_query(query, pagination)
    
    def get_pending_approval(
        self,
        hostel_id: Optional[UUID] = None,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginationResult[ReviewResponse]:
        """
        Get responses pending approval.
        
        Args:
            hostel_id: Optional hostel filter
            pagination: Pagination parameters
            
        Returns:
            Paginated pending responses
        """
        query = self.session.query(ReviewResponse).filter(
            ReviewResponse.requires_approval == True,
            ReviewResponse.is_approved == False
        )
        
        if hostel_id:
            query = query.filter(ReviewResponse.hostel_id == hostel_id)
        
        query = query.order_by(asc(ReviewResponse.created_at))
        
        return self._paginate_query(query, pagination)
    
    def get_responder_responses(
        self,
        responder_id: UUID,
        hostel_id: Optional[UUID] = None,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginationResult[ReviewResponse]:
        """
        Get responses by specific responder.
        
        Args:
            responder_id: Responder admin ID
            hostel_id: Optional hostel filter
            pagination: Pagination parameters
            
        Returns:
            Paginated responses
        """
        query = self.session.query(ReviewResponse).filter(
            ReviewResponse.responded_by == responder_id
        )
        
        if hostel_id:
            query = query.filter(ReviewResponse.hostel_id == hostel_id)
        
        query = query.order_by(desc(ReviewResponse.responded_at))
        
        return self._paginate_query(query, pagination)
    
    # ==================== Response Analytics ====================
    
    def get_response_rate(
        self,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate response rate for hostel.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Response rate statistics
        """
        # Get total reviews
        review_query = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True
        )
        
        if start_date:
            review_query = review_query.filter(Review.created_at >= start_date)
        if end_date:
            review_query = review_query.filter(Review.created_at <= end_date)
        
        total_reviews = review_query.count()
        
        # Get reviews with responses
        responded_query = review_query.join(ReviewResponse)
        reviews_with_response = responded_query.count()
        
        # Calculate rate
        response_rate = (reviews_with_response / total_reviews * 100) if total_reviews > 0 else 0
        
        return {
            'total_reviews': total_reviews,
            'reviews_with_response': reviews_with_response,
            'reviews_without_response': total_reviews - reviews_with_response,
            'response_rate': round(response_rate, 2)
        }
    
    def get_average_response_time(
        self,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate average response time.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Response time statistics
        """
        query = self.session.query(ReviewResponse).filter(
            ReviewResponse.hostel_id == hostel_id,
            ReviewResponse.response_time_hours.isnot(None)
        )
        
        if start_date:
            query = query.filter(ReviewResponse.responded_at >= start_date)
        if end_date:
            query = query.filter(ReviewResponse.responded_at <= end_date)
        
        stats = query.with_entities(
            func.avg(ReviewResponse.response_time_hours).label('avg_time'),
            func.min(ReviewResponse.response_time_hours).label('min_time'),
            func.max(ReviewResponse.response_time_hours).label('max_time'),
            func.count(ReviewResponse.id).label('count')
        ).first()
        
        return {
            'average_hours': float(stats.avg_time or 0),
            'fastest_hours': float(stats.min_time or 0),
            'slowest_hours': float(stats.max_time or 0),
            'total_responses': stats.count
        }
    
    def get_template_usage_statistics(
        self,
        hostel_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get template usage statistics.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Template usage statistics
        """
        query = self.session.query(ReviewResponse).filter(
            ReviewResponse.hostel_id == hostel_id
        )
        
        if start_date:
            query = query.filter(ReviewResponse.responded_at >= start_date)
        if end_date:
            query = query.filter(ReviewResponse.responded_at <= end_date)
        
        total_responses = query.count()
        template_responses = query.filter(ReviewResponse.is_from_template == True).count()
        
        return {
            'total_responses': total_responses,
            'template_responses': template_responses,
            'manual_responses': total_responses - template_responses,
            'template_usage_rate': (template_responses / total_responses * 100) if total_responses > 0 else 0
        }
    
    # ==================== Template Operations ====================
    
    def create_template(
        self,
        name: str,
        category: str,
        template_text: str,
        hostel_id: Optional[UUID] = None,
        description: Optional[str] = None,
        available_placeholders: Optional[List[str]] = None,
        created_by: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        is_active: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ResponseTemplate:
        """
        Create response template.
        
        Args:
            name: Template name
            category: Template category
            template_text: Template content
            hostel_id: Hostel ID (None for global templates)
            description: Template description
            available_placeholders: List of available placeholders
            created_by: Creator admin ID
            tags: Template tags
            is_active: Whether template is active
            metadata: Additional metadata
            
        Returns:
            Created template
        """
        template = ResponseTemplate(
            hostel_id=hostel_id,
            name=name,
            category=category,
            template_text=template_text,
            description=description,
            available_placeholders=available_placeholders or [],
            created_by=created_by,
            tags=tags or [],
            is_active=is_active,
            metadata=metadata
        )
        
        self.session.add(template)
        self.session.commit()
        self.session.refresh(template)
        
        return template
    
    def update_template(
        self,
        template_id: UUID,
        updates: Dict[str, Any]
    ) -> ResponseTemplate:
        """
        Update response template.
        
        Args:
            template_id: Template to update
            updates: Fields to update
            
        Returns:
            Updated template
        """
        template = self.session.query(ResponseTemplate).filter(
            ResponseTemplate.id == template_id
        ).first()
        
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        for field, value in updates.items():
            if hasattr(template, field):
                setattr(template, field, value)
        
        self.session.commit()
        self.session.refresh(template)
        
        return template
    
    def get_templates(
        self,
        hostel_id: Optional[UUID] = None,
        category: Optional[str] = None,
        active_only: bool = True
    ) -> List[ResponseTemplate]:
        """
        Get response templates.
        
        Args:
            hostel_id: Optional hostel filter (None gets global templates)
            category: Optional category filter
            active_only: Whether to only return active templates
            
        Returns:
            List of templates
        """
        query = self.session.query(ResponseTemplate)
        
        if hostel_id is not None:
            # Get hostel-specific and global templates
            query = query.filter(
                or_(
                    ResponseTemplate.hostel_id == hostel_id,
                    ResponseTemplate.hostel_id.is_(None)
                )
            )
        else:
            # Get only global templates
            query = query.filter(ResponseTemplate.hostel_id.is_(None))
        
        if category:
            query = query.filter(ResponseTemplate.category == category)
        
        if active_only:
            query = query.filter(ResponseTemplate.is_active == True)
        
        return query.order_by(desc(ResponseTemplate.usage_count)).all()
    
    def get_template(
        self,
        template_id: UUID
    ) -> Optional[ResponseTemplate]:
        """
        Get specific template.
        
        Args:
            template_id: Template ID
            
        Returns:
            Template if exists
        """
        return self.session.query(ResponseTemplate).filter(
            ResponseTemplate.id == template_id
        ).first()
    
    def apply_template(
        self,
        template_id: UUID,
        placeholders: Dict[str, str]
    ) -> str:
        """
        Apply placeholders to template.
        
        Args:
            template_id: Template to use
            placeholders: Placeholder values
            
        Returns:
            Template text with placeholders replaced
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        return template.apply_placeholders(**placeholders)
    
    def approve_template(
        self,
        template_id: UUID,
        approved_by: UUID
    ) -> ResponseTemplate:
        """
        Approve template for use.
        
        Args:
            template_id: Template to approve
            approved_by: Admin approving template
            
        Returns:
            Approved template
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        template.is_approved = True
        template.approved_by = approved_by
        template.approved_at = datetime.utcnow()
        
        self.session.commit()
        self.session.refresh(template)
        
        return template
    
    def deactivate_template(
        self,
        template_id: UUID
    ) -> ResponseTemplate:
        """
        Deactivate template.
        
        Args:
            template_id: Template to deactivate
            
        Returns:
            Deactivated template
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")
        
        template.is_active = False
        
        self.session.commit()
        self.session.refresh(template)
        
        return template
    
    # ==================== Response Statistics ====================
    
    def create_statistics(
        self,
        hostel_id: UUID,
        period_start: datetime,
        period_end: datetime,
        period_type: str
    ) -> ResponseStatistics:
        """
        Create response statistics for period.
        
        Args:
            hostel_id: Hostel ID
            period_start: Period start date
            period_end: Period end date
            period_type: Type of period (daily, weekly, monthly, etc.)
            
        Returns:
            Created statistics
        """
        # Get reviews in period
        reviews_query = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            Review.created_at >= period_start,
            Review.created_at <= period_end
        )
        
        total_reviews = reviews_query.count()
        
        # Get responses in period
        responses_query = self.session.query(ReviewResponse).filter(
            ReviewResponse.hostel_id == hostel_id,
            ReviewResponse.responded_at >= period_start,
            ReviewResponse.responded_at <= period_end
        )
        
        total_responses = responses_query.count()
        
        # Calculate response rates by rating
        rating_response_rates = {}
        for rating in [5, 4, 3, 2, 1]:
            rating_reviews = reviews_query.filter(
                Review.overall_rating >= Decimal(rating),
                Review.overall_rating < Decimal(rating + 1)
            ).count()
            
            rating_responses = responses_query.join(Review).filter(
                Review.overall_rating >= Decimal(rating),
                Review.overall_rating < Decimal(rating + 1)
            ).count()
            
            rate = (rating_responses / rating_reviews * 100) if rating_reviews > 0 else 0
            rating_response_rates[f'{rating}_star'] = Decimal(str(round(rate, 2)))
        
        # Calculate timing metrics
        timing_stats = responses_query.with_entities(
            func.avg(ReviewResponse.response_time_hours).label('avg_time'),
            func.percentile_cont(0.5).within_group(
                ReviewResponse.response_time_hours
            ).label('median_time'),
            func.min(ReviewResponse.response_time_hours).label('fastest'),
            func.max(ReviewResponse.response_time_hours).label('slowest')
        ).first()
        
        # Calculate quality metrics
        quality_stats = responses_query.with_entities(
            func.avg(func.length(ReviewResponse.response_text)).label('avg_length'),
            func.avg(ReviewResponse.tone_score).label('avg_tone'),
            func.avg(ReviewResponse.professionalism_score).label('avg_prof')
        ).first()
        
        # Template usage
        template_responses = responses_query.filter(
            ReviewResponse.is_from_template == True
        ).count()
        
        # Pending responses
        pending = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            ~Review.id.in_(
                self.session.query(ReviewResponse.review_id)
            )
        ).count()
        
        # Oldest unanswered
        oldest_unanswered = self.session.query(Review).filter(
            Review.hostel_id == hostel_id,
            Review.is_published == True,
            ~Review.id.in_(
                self.session.query(ReviewResponse.review_id)
            )
        ).order_by(asc(Review.created_at)).first()
        
        oldest_days = None
        if oldest_unanswered:
            delta = datetime.utcnow() - oldest_unanswered.created_at
            oldest_days = delta.days
        
        # Create statistics record
        stats = ResponseStatistics(
            hostel_id=hostel_id,
            period_start=period_start,
            period_end=period_end,
            period_type=period_type,
            total_reviews=total_reviews,
            total_responses=total_responses,
            response_rate_5_star=rating_response_rates.get('5_star', Decimal('0')),
            response_rate_4_star=rating_response_rates.get('4_star', Decimal('0')),
            response_rate_3_star=rating_response_rates.get('3_star', Decimal('0')),
            response_rate_2_star=rating_response_rates.get('2_star', Decimal('0')),
            response_rate_1_star=rating_response_rates.get('1_star', Decimal('0')),
            average_response_time_hours=Decimal(str(timing_stats.avg_time or 0)),
            median_response_time_hours=Decimal(str(timing_stats.median_time or 0)),
            fastest_response_hours=Decimal(str(timing_stats.fastest or 0)),
            slowest_response_hours=Decimal(str(timing_stats.slowest or 0)),
            average_response_length=int(quality_stats.avg_length or 0),
            average_tone_score=Decimal(str(quality_stats.avg_tone or 0)),
            average_professionalism_score=Decimal(str(quality_stats.avg_prof or 0)),
            pending_responses=pending,
            oldest_unanswered_days=oldest_days,
            template_usage_count=template_responses
        )
        
        # Calculate response rate and health score
        stats.calculate_response_rate()
        stats.calculate_health_score()
        
        self.session.add(stats)
        self.session.commit()
        self.session.refresh(stats)
        
        return stats
    
    def get_statistics(
        self,
        hostel_id: UUID,
        period_type: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[ResponseStatistics]:
        """
        Get response statistics.
        
        Args:
            hostel_id: Hostel ID
            period_type: Period type filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List of statistics records
        """
        query = self.session.query(ResponseStatistics).filter(
            ResponseStatistics.hostel_id == hostel_id,
            ResponseStatistics.period_type == period_type
        )
        
        if start_date:
            query = query.filter(ResponseStatistics.period_start >= start_date)
        
        if end_date:
            query = query.filter(ResponseStatistics.period_end <= end_date)
        
        return query.order_by(desc(ResponseStatistics.period_start)).all()
    
    def get_latest_statistics(
        self,
        hostel_id: UUID,
        period_type: str = 'monthly'
    ) -> Optional[ResponseStatistics]:
        """
        Get latest statistics for hostel.
        
        Args:
            hostel_id: Hostel ID
            period_type: Period type
            
        Returns:
            Latest statistics if exists
        """
        return self.session.query(ResponseStatistics).filter(
            ResponseStatistics.hostel_id == hostel_id,
            ResponseStatistics.period_type == period_type
        ).order_by(desc(ResponseStatistics.period_start)).first()
    
    # ==================== Helper Methods ====================
    
    def _increment_template_usage(self, template_id: UUID):
        """Increment template usage count."""
        template = self.get_template(template_id)
        if template:
            template.increment_usage()
            self.session.commit()
    
    def _apply_response_filters(self, query, filters: Dict[str, Any]):
        """Apply filters to response query."""
        if 'is_published' in filters:
            query = query.filter(ReviewResponse.is_published == filters['is_published'])
        
        if 'is_approved' in filters:
            query = query.filter(ReviewResponse.is_approved == filters['is_approved'])
        
        if 'responded_by' in filters:
            query = query.filter(ReviewResponse.responded_by == filters['responded_by'])
        
        if 'from_template' in filters:
            query = query.filter(ReviewResponse.is_from_template == filters['from_template'])
        
        if 'min_response_time' in filters:
            query = query.filter(ReviewResponse.response_time_hours >= filters['min_response_time'])
        
        if 'max_response_time' in filters:
            query = query.filter(ReviewResponse.response_time_hours <= filters['max_response_time'])
        
        return query
    
    def _paginate_query(
        self,
        query,
        pagination: Optional[Dict[str, Any]] = None
    ) -> PaginationResult:
        """Paginate query results."""
        if not pagination:
            pagination = {'page': 1, 'per_page': 20}
        
        page = pagination.get('page', 1)
        per_page = pagination.get('per_page', 20)
        
        total = query.count()
        items = query.limit(per_page).offset((page - 1) * per_page).all()
        
        return PaginationResult(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            pages=(total + per_page - 1) // per_page
        )