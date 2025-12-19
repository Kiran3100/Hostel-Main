"""
Leave Application Repository

Comprehensive leave application management with advanced querying,
status tracking, analytics, and workflow optimization.
"""

from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, case, extract
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql import text

from app.models.leave.leave_application import (
    LeaveApplication,
    LeaveCancellation,
    LeaveDocument,
    LeaveEmergencyContact,
    LeaveStatusHistory,
)
from app.models.common.enums import LeaveStatus, LeaveType
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.specifications import Specification
from app.repositories.base.pagination import PaginationParams, PaginatedResult


class LeaveApplicationRepository(BaseRepository[LeaveApplication]):
    """
    Leave application repository with comprehensive management capabilities.
    
    Features:
    - Advanced leave search and filtering
    - Status workflow management
    - Document management
    - Emergency contact tracking
    - Analytics and reporting
    - Performance optimization
    """

    def __init__(self, session: Session):
        """Initialize repository with database session."""
        super().__init__(session, LeaveApplication)

    # ============================================================================
    # CORE CRUD OPERATIONS
    # ============================================================================

    def create_leave_application(
        self,
        student_id: UUID,
        hostel_id: UUID,
        leave_data: Dict[str, Any],
        audit_context: Optional[Dict[str, Any]] = None
    ) -> LeaveApplication:
        """
        Create new leave application with validation and audit trail.
        
        Args:
            student_id: Student requesting leave
            hostel_id: Hostel where student resides
            leave_data: Leave application details
            audit_context: Audit information
            
        Returns:
            Created leave application
            
        Raises:
            ValueError: If validation fails
        """
        # Calculate total days if not provided
        if 'total_days' not in leave_data:
            from_date = leave_data['from_date']
            to_date = leave_data['to_date']
            leave_data['total_days'] = (to_date - from_date).days + 1

        # Set default values
        leave_data.setdefault('status', LeaveStatus.PENDING)
        leave_data.setdefault('applied_at', datetime.utcnow())
        leave_data.setdefault('requires_approval', True)
        
        # Create application
        application = LeaveApplication(
            student_id=student_id,
            hostel_id=hostel_id,
            **leave_data
        )
        
        # Create initial status history
        initial_status = LeaveStatusHistory(
            leave_id=application.id,
            old_status=None,
            new_status=LeaveStatus.PENDING,
            change_reason="Initial application submission",
            changed_at=datetime.utcnow(),
            changed_by=audit_context.get('user_id') if audit_context else None
        )
        
        self.session.add(application)
        self.session.add(initial_status)
        self.session.flush()
        
        return application

    def update_leave_application(
        self,
        leave_id: UUID,
        update_data: Dict[str, Any],
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Optional[LeaveApplication]:
        """
        Update leave application with validation.
        
        Args:
            leave_id: Leave application ID
            update_data: Fields to update
            audit_context: Audit information
            
        Returns:
            Updated leave application or None
        """
        application = self.find_by_id(leave_id)
        if not application:
            return None
        
        # Update modification tracking
        update_data['last_modified_at'] = datetime.utcnow()
        if audit_context and 'user_id' in audit_context:
            update_data['last_modified_by'] = audit_context['user_id']
        
        # Apply updates
        for key, value in update_data.items():
            if hasattr(application, key):
                setattr(application, key, value)
        
        self.session.flush()
        return application

    # ============================================================================
    # FINDER METHODS
    # ============================================================================

    def find_by_student(
        self,
        student_id: UUID,
        include_deleted: bool = False,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[LeaveApplication]:
        """
        Find all leave applications for a student.
        
        Args:
            student_id: Student ID
            include_deleted: Include soft-deleted records
            pagination: Pagination parameters
            
        Returns:
            Paginated leave applications
        """
        query = self.session.query(LeaveApplication).filter(
            LeaveApplication.student_id == student_id
        )
        
        if not include_deleted:
            query = query.filter(LeaveApplication.deleted_at.is_(None))
        
        query = query.order_by(LeaveApplication.applied_at.desc())
        
        return self._paginate_query(query, pagination)

    def find_by_hostel(
        self,
        hostel_id: UUID,
        status: Optional[LeaveStatus] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[LeaveApplication]:
        """
        Find leave applications for a hostel with optional filters.
        
        Args:
            hostel_id: Hostel ID
            status: Filter by status
            from_date: Filter by start date
            to_date: Filter by end date
            pagination: Pagination parameters
            
        Returns:
            Paginated leave applications
        """
        query = self.session.query(LeaveApplication).filter(
            LeaveApplication.hostel_id == hostel_id,
            LeaveApplication.deleted_at.is_(None)
        )
        
        if status:
            query = query.filter(LeaveApplication.status == status)
        
        if from_date:
            query = query.filter(LeaveApplication.from_date >= from_date)
        
        if to_date:
            query = query.filter(LeaveApplication.to_date <= to_date)
        
        query = query.order_by(LeaveApplication.applied_at.desc())
        
        return self._paginate_query(query, pagination)

    def find_by_status(
        self,
        status: LeaveStatus,
        hostel_id: Optional[UUID] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[LeaveApplication]:
        """
        Find leave applications by status.
        
        Args:
            status: Leave status
            hostel_id: Optional hostel filter
            pagination: Pagination parameters
            
        Returns:
            Paginated leave applications
        """
        query = self.session.query(LeaveApplication).filter(
            LeaveApplication.status == status,
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(LeaveApplication.hostel_id == hostel_id)
        
        query = query.order_by(LeaveApplication.applied_at.desc())
        
        return self._paginate_query(query, pagination)

    def find_pending_approvals(
        self,
        hostel_id: Optional[UUID] = None,
        older_than_hours: Optional[int] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[LeaveApplication]:
        """
        Find pending leave approvals with optional age filter.
        
        Args:
            hostel_id: Optional hostel filter
            older_than_hours: Filter applications older than hours
            pagination: Pagination parameters
            
        Returns:
            Paginated pending applications
        """
        query = self.session.query(LeaveApplication).filter(
            LeaveApplication.status == LeaveStatus.PENDING,
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(LeaveApplication.hostel_id == hostel_id)
        
        if older_than_hours:
            cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)
            query = query.filter(LeaveApplication.applied_at <= cutoff_time)
        
        query = query.order_by(
            LeaveApplication.priority.desc(),
            LeaveApplication.applied_at.asc()
        )
        
        return self._paginate_query(query, pagination)

    def find_active_leaves(
        self,
        hostel_id: Optional[UUID] = None,
        reference_date: Optional[date] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[LeaveApplication]:
        """
        Find currently active leaves.
        
        Args:
            hostel_id: Optional hostel filter
            reference_date: Date to check (default: today)
            pagination: Pagination parameters
            
        Returns:
            Paginated active leaves
        """
        if reference_date is None:
            reference_date = date.today()
        
        query = self.session.query(LeaveApplication).filter(
            LeaveApplication.status == LeaveStatus.APPROVED,
            LeaveApplication.from_date <= reference_date,
            LeaveApplication.to_date >= reference_date,
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(LeaveApplication.hostel_id == hostel_id)
        
        query = query.order_by(LeaveApplication.from_date)
        
        return self._paginate_query(query, pagination)

    def find_upcoming_leaves(
        self,
        hostel_id: Optional[UUID] = None,
        days_ahead: int = 7,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[LeaveApplication]:
        """
        Find upcoming approved leaves.
        
        Args:
            hostel_id: Optional hostel filter
            days_ahead: Number of days to look ahead
            pagination: Pagination parameters
            
        Returns:
            Paginated upcoming leaves
        """
        today = date.today()
        future_date = today + timedelta(days=days_ahead)
        
        query = self.session.query(LeaveApplication).filter(
            LeaveApplication.status == LeaveStatus.APPROVED,
            LeaveApplication.from_date > today,
            LeaveApplication.from_date <= future_date,
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(LeaveApplication.hostel_id == hostel_id)
        
        query = query.order_by(LeaveApplication.from_date)
        
        return self._paginate_query(query, pagination)

    def find_by_date_range(
        self,
        from_date: date,
        to_date: date,
        hostel_id: Optional[UUID] = None,
        status: Optional[LeaveStatus] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[LeaveApplication]:
        """
        Find leaves overlapping with date range.
        
        Args:
            from_date: Range start date
            to_date: Range end date
            hostel_id: Optional hostel filter
            status: Optional status filter
            pagination: Pagination parameters
            
        Returns:
            Paginated leaves in date range
        """
        query = self.session.query(LeaveApplication).filter(
            or_(
                and_(
                    LeaveApplication.from_date >= from_date,
                    LeaveApplication.from_date <= to_date
                ),
                and_(
                    LeaveApplication.to_date >= from_date,
                    LeaveApplication.to_date <= to_date
                ),
                and_(
                    LeaveApplication.from_date <= from_date,
                    LeaveApplication.to_date >= to_date
                )
            ),
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(LeaveApplication.hostel_id == hostel_id)
        
        if status:
            query = query.filter(LeaveApplication.status == status)
        
        query = query.order_by(LeaveApplication.from_date)
        
        return self._paginate_query(query, pagination)

    def find_overdue_returns(
        self,
        hostel_id: Optional[UUID] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[LeaveApplication]:
        """
        Find leaves where return is overdue.
        
        Args:
            hostel_id: Optional hostel filter
            pagination: Pagination parameters
            
        Returns:
            Paginated overdue returns
        """
        today = date.today()
        
        query = self.session.query(LeaveApplication).filter(
            LeaveApplication.status == LeaveStatus.APPROVED,
            LeaveApplication.to_date < today,
            LeaveApplication.return_confirmed == False,
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(LeaveApplication.hostel_id == hostel_id)
        
        query = query.order_by(LeaveApplication.to_date)
        
        return self._paginate_query(query, pagination)

    def find_by_leave_type(
        self,
        leave_type: LeaveType,
        hostel_id: Optional[UUID] = None,
        status: Optional[LeaveStatus] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[LeaveApplication]:
        """
        Find leaves by type.
        
        Args:
            leave_type: Leave type
            hostel_id: Optional hostel filter
            status: Optional status filter
            pagination: Pagination parameters
            
        Returns:
            Paginated leaves of specified type
        """
        query = self.session.query(LeaveApplication).filter(
            LeaveApplication.leave_type == leave_type,
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(LeaveApplication.hostel_id == hostel_id)
        
        if status:
            query = query.filter(LeaveApplication.status == status)
        
        query = query.order_by(LeaveApplication.applied_at.desc())
        
        return self._paginate_query(query, pagination)

    # ============================================================================
    # STATUS MANAGEMENT
    # ============================================================================

    def approve_leave(
        self,
        leave_id: UUID,
        approver_id: UUID,
        approval_notes: Optional[str] = None,
        conditions: Optional[str] = None,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Optional[LeaveApplication]:
        """
        Approve leave application.
        
        Args:
            leave_id: Leave application ID
            approver_id: User approving the leave
            approval_notes: Optional approval notes
            conditions: Optional conditions
            audit_context: Audit information
            
        Returns:
            Updated leave application or None
        """
        application = self.find_by_id(leave_id)
        if not application or application.status != LeaveStatus.PENDING:
            return None
        
        old_status = application.status
        
        # Update application
        application.status = LeaveStatus.APPROVED
        application.approved_by = approver_id
        application.approved_at = datetime.utcnow()
        application.approval_notes = approval_notes
        application.conditions = conditions
        
        # Record status change
        status_history = LeaveStatusHistory(
            leave_id=leave_id,
            old_status=old_status,
            new_status=LeaveStatus.APPROVED,
            change_reason="Leave approved",
            comments=approval_notes,
            changed_at=datetime.utcnow(),
            changed_by=approver_id,
            ip_address=audit_context.get('ip_address') if audit_context else None
        )
        
        self.session.add(status_history)
        self.session.flush()
        
        return application

    def reject_leave(
        self,
        leave_id: UUID,
        rejector_id: UUID,
        rejection_reason: str,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Optional[LeaveApplication]:
        """
        Reject leave application.
        
        Args:
            leave_id: Leave application ID
            rejector_id: User rejecting the leave
            rejection_reason: Reason for rejection
            audit_context: Audit information
            
        Returns:
            Updated leave application or None
        """
        application = self.find_by_id(leave_id)
        if not application or application.status != LeaveStatus.PENDING:
            return None
        
        old_status = application.status
        
        # Update application
        application.status = LeaveStatus.REJECTED
        application.rejected_by = rejector_id
        application.rejected_at = datetime.utcnow()
        application.rejection_reason = rejection_reason
        
        # Record status change
        status_history = LeaveStatusHistory(
            leave_id=leave_id,
            old_status=old_status,
            new_status=LeaveStatus.REJECTED,
            change_reason="Leave rejected",
            comments=rejection_reason,
            changed_at=datetime.utcnow(),
            changed_by=rejector_id,
            ip_address=audit_context.get('ip_address') if audit_context else None
        )
        
        self.session.add(status_history)
        self.session.flush()
        
        return application

    def cancel_leave(
        self,
        leave_id: UUID,
        canceller_id: UUID,
        cancellation_reason: str,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Optional[LeaveApplication]:
        """
        Cancel leave application.
        
        Args:
            leave_id: Leave application ID
            canceller_id: User cancelling the leave
            cancellation_reason: Reason for cancellation
            audit_context: Audit information
            
        Returns:
            Updated leave application or None
        """
        application = self.find_by_id(leave_id)
        if not application or not application.can_be_cancelled:
            return None
        
        old_status = application.status
        
        # Update application
        application.status = LeaveStatus.CANCELLED
        application.cancelled_by = canceller_id
        application.cancelled_at = datetime.utcnow()
        application.cancellation_reason = cancellation_reason
        
        # Record status change
        status_history = LeaveStatusHistory(
            leave_id=leave_id,
            old_status=old_status,
            new_status=LeaveStatus.CANCELLED,
            change_reason="Leave cancelled",
            comments=cancellation_reason,
            changed_at=datetime.utcnow(),
            changed_by=canceller_id,
            ip_address=audit_context.get('ip_address') if audit_context else None
        )
        
        self.session.add(status_history)
        self.session.flush()
        
        return application

    def confirm_return(
        self,
        leave_id: UUID,
        confirmer_id: UUID,
        actual_return_date: Optional[date] = None,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Optional[LeaveApplication]:
        """
        Confirm student return from leave.
        
        Args:
            leave_id: Leave application ID
            confirmer_id: User confirming return
            actual_return_date: Actual return date (default: today)
            audit_context: Audit information
            
        Returns:
            Updated leave application or None
        """
        application = self.find_by_id(leave_id)
        if not application or application.status != LeaveStatus.APPROVED:
            return None
        
        if actual_return_date is None:
            actual_return_date = date.today()
        
        application.actual_return_date = actual_return_date
        application.return_confirmed = True
        application.return_confirmed_at = datetime.utcnow()
        application.return_confirmed_by = confirmer_id
        
        self.session.flush()
        
        return application

    # ============================================================================
    # DOCUMENT MANAGEMENT
    # ============================================================================

    def add_document(
        self,
        leave_id: UUID,
        document_data: Dict[str, Any],
        uploaded_by: UUID
    ) -> Optional[LeaveDocument]:
        """
        Add supporting document to leave application.
        
        Args:
            leave_id: Leave application ID
            document_data: Document details
            uploaded_by: User uploading document
            
        Returns:
            Created document or None
        """
        application = self.find_by_id(leave_id)
        if not application:
            return None
        
        document = LeaveDocument(
            leave_id=leave_id,
            uploaded_by=uploaded_by,
            **document_data
        )
        
        self.session.add(document)
        self.session.flush()
        
        return document

    def verify_document(
        self,
        document_id: UUID,
        verifier_id: UUID,
        verification_notes: Optional[str] = None
    ) -> Optional[LeaveDocument]:
        """
        Verify leave document.
        
        Args:
            document_id: Document ID
            verifier_id: User verifying document
            verification_notes: Optional verification notes
            
        Returns:
            Updated document or None
        """
        document = self.session.query(LeaveDocument).filter(
            LeaveDocument.id == document_id
        ).first()
        
        if not document:
            return None
        
        document.is_verified = True
        document.verified_by = verifier_id
        document.verified_at = datetime.utcnow()
        document.verification_notes = verification_notes
        
        self.session.flush()
        
        return document

    def get_documents(
        self,
        leave_id: UUID,
        verified_only: bool = False
    ) -> List[LeaveDocument]:
        """
        Get all documents for leave application.
        
        Args:
            leave_id: Leave application ID
            verified_only: Return only verified documents
            
        Returns:
            List of documents
        """
        query = self.session.query(LeaveDocument).filter(
            LeaveDocument.leave_id == leave_id
        )
        
        if verified_only:
            query = query.filter(LeaveDocument.is_verified == True)
        
        return query.all()

    # ============================================================================
    # EMERGENCY CONTACT MANAGEMENT
    # ============================================================================

    def add_emergency_contact(
        self,
        leave_id: UUID,
        contact_data: Dict[str, Any]
    ) -> Optional[LeaveEmergencyContact]:
        """
        Add emergency contact for leave period.
        
        Args:
            leave_id: Leave application ID
            contact_data: Contact details
            
        Returns:
            Created contact or None
        """
        application = self.find_by_id(leave_id)
        if not application:
            return None
        
        contact = LeaveEmergencyContact(
            leave_id=leave_id,
            **contact_data
        )
        
        self.session.add(contact)
        self.session.flush()
        
        return contact

    def get_emergency_contacts(
        self,
        leave_id: UUID,
        verified_only: bool = False
    ) -> List[LeaveEmergencyContact]:
        """
        Get emergency contacts for leave application.
        
        Args:
            leave_id: Leave application ID
            verified_only: Return only verified contacts
            
        Returns:
            List of emergency contacts
        """
        query = self.session.query(LeaveEmergencyContact).filter(
            LeaveEmergencyContact.leave_id == leave_id
        )
        
        if verified_only:
            query = query.filter(LeaveEmergencyContact.is_verified == True)
        
        return query.order_by(LeaveEmergencyContact.priority).all()

    # ============================================================================
    # ANALYTICS AND REPORTING
    # ============================================================================

    def get_leave_statistics(
        self,
        hostel_id: Optional[UUID] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive leave statistics.
        
        Args:
            hostel_id: Optional hostel filter
            from_date: Optional start date
            to_date: Optional end date
            
        Returns:
            Dictionary with statistics
        """
        query = self.session.query(LeaveApplication).filter(
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(LeaveApplication.hostel_id == hostel_id)
        
        if from_date:
            query = query.filter(LeaveApplication.applied_at >= datetime.combine(from_date, datetime.min.time()))
        
        if to_date:
            query = query.filter(LeaveApplication.applied_at <= datetime.combine(to_date, datetime.max.time()))
        
        # Get counts by status
        status_counts = self.session.query(
            LeaveApplication.status,
            func.count(LeaveApplication.id)
        ).filter(
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            status_counts = status_counts.filter(LeaveApplication.hostel_id == hostel_id)
        
        status_counts = status_counts.group_by(LeaveApplication.status).all()
        
        # Get counts by type
        type_counts = self.session.query(
            LeaveApplication.leave_type,
            func.count(LeaveApplication.id)
        ).filter(
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            type_counts = type_counts.filter(LeaveApplication.hostel_id == hostel_id)
        
        type_counts = type_counts.group_by(LeaveApplication.leave_type).all()
        
        # Get average processing time for approved/rejected leaves
        avg_processing_time = self.session.query(
            func.avg(
                func.extract('epoch', LeaveApplication.approved_at - LeaveApplication.applied_at)
            ).label('avg_hours')
        ).filter(
            LeaveApplication.status.in_([LeaveStatus.APPROVED, LeaveStatus.REJECTED]),
            LeaveApplication.approved_at.isnot(None),
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            avg_processing_time = avg_processing_time.filter(LeaveApplication.hostel_id == hostel_id)
        
        avg_time = avg_processing_time.scalar()
        
        return {
            'total_applications': query.count(),
            'status_breakdown': {status.value: count for status, count in status_counts},
            'type_breakdown': {leave_type.value: count for leave_type, count in type_counts},
            'average_processing_hours': round(avg_time / 3600, 2) if avg_time else None,
            'active_leaves': self.find_active_leaves(hostel_id=hostel_id).total,
            'pending_approvals': self.find_pending_approvals(hostel_id=hostel_id).total,
            'overdue_returns': self.find_overdue_returns(hostel_id=hostel_id).total,
        }

    def get_student_leave_summary(
        self,
        student_id: UUID,
        academic_year_start: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get leave summary for a student.
        
        Args:
            student_id: Student ID
            academic_year_start: Optional academic year filter
            
        Returns:
            Dictionary with student leave summary
        """
        query = self.session.query(LeaveApplication).filter(
            LeaveApplication.student_id == student_id,
            LeaveApplication.deleted_at.is_(None)
        )
        
        if academic_year_start:
            academic_year_end = date(academic_year_start.year + 1, academic_year_start.month, academic_year_start.day)
            query = query.filter(
                LeaveApplication.from_date >= academic_year_start,
                LeaveApplication.from_date < academic_year_end
            )
        
        # Total days by type
        days_by_type = self.session.query(
            LeaveApplication.leave_type,
            func.sum(LeaveApplication.total_days)
        ).filter(
            LeaveApplication.student_id == student_id,
            LeaveApplication.status == LeaveStatus.APPROVED,
            LeaveApplication.deleted_at.is_(None)
        )
        
        if academic_year_start:
            days_by_type = days_by_type.filter(
                LeaveApplication.from_date >= academic_year_start,
                LeaveApplication.from_date < academic_year_end
            )
        
        days_by_type = days_by_type.group_by(LeaveApplication.leave_type).all()
        
        return {
            'total_applications': query.count(),
            'approved_applications': query.filter(LeaveApplication.status == LeaveStatus.APPROVED).count(),
            'rejected_applications': query.filter(LeaveApplication.status == LeaveStatus.REJECTED).count(),
            'pending_applications': query.filter(LeaveApplication.status == LeaveStatus.PENDING).count(),
            'total_days_used': sum(days for _, days in days_by_type if days),
            'days_by_type': {leave_type.value: days for leave_type, days in days_by_type},
            'active_leave': self.session.query(LeaveApplication).filter(
                LeaveApplication.student_id == student_id,
                LeaveApplication.status == LeaveStatus.APPROVED,
                LeaveApplication.from_date <= date.today(),
                LeaveApplication.to_date >= date.today(),
                LeaveApplication.deleted_at.is_(None)
            ).first()
        }

    def get_approval_trends(
        self,
        hostel_id: Optional[UUID] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get leave approval trends.
        
        Args:
            hostel_id: Optional hostel filter
            days: Number of days to analyze
            
        Returns:
            Dictionary with trend data
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = self.session.query(
            func.date(LeaveApplication.applied_at).label('date'),
            func.count(case([(LeaveApplication.status == LeaveStatus.APPROVED, 1)])).label('approved'),
            func.count(case([(LeaveApplication.status == LeaveStatus.REJECTED, 1)])).label('rejected'),
            func.count(case([(LeaveApplication.status == LeaveStatus.PENDING, 1)])).label('pending')
        ).filter(
            LeaveApplication.applied_at >= start_date,
            LeaveApplication.deleted_at.is_(None)
        )
        
        if hostel_id:
            query = query.filter(LeaveApplication.hostel_id == hostel_id)
        
        query = query.group_by(func.date(LeaveApplication.applied_at)).order_by('date')
        
        results = query.all()
        
        return {
            'period_days': days,
            'daily_trends': [
                {
                    'date': str(result.date),
                    'approved': result.approved,
                    'rejected': result.rejected,
                    'pending': result.pending
                }
                for result in results
            ]
        }

    # ============================================================================
    # SEARCH AND FILTER
    # ============================================================================

    def advanced_search(
        self,
        filters: Dict[str, Any],
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[LeaveApplication]:
        """
        Advanced search with multiple filters.
        
        Args:
            filters: Dictionary of filter criteria
            pagination: Pagination parameters
            
        Returns:
            Paginated search results
        """
        query = self.session.query(LeaveApplication).filter(
            LeaveApplication.deleted_at.is_(None)
        )
        
        # Apply filters
        if 'student_id' in filters:
            query = query.filter(LeaveApplication.student_id == filters['student_id'])
        
        if 'hostel_id' in filters:
            query = query.filter(LeaveApplication.hostel_id == filters['hostel_id'])
        
        if 'status' in filters:
            if isinstance(filters['status'], list):
                query = query.filter(LeaveApplication.status.in_(filters['status']))
            else:
                query = query.filter(LeaveApplication.status == filters['status'])
        
        if 'leave_type' in filters:
            if isinstance(filters['leave_type'], list):
                query = query.filter(LeaveApplication.leave_type.in_(filters['leave_type']))
            else:
                query = query.filter(LeaveApplication.leave_type == filters['leave_type'])
        
        if 'from_date' in filters:
            query = query.filter(LeaveApplication.from_date >= filters['from_date'])
        
        if 'to_date' in filters:
            query = query.filter(LeaveApplication.to_date <= filters['to_date'])
        
        if 'applied_after' in filters:
            query = query.filter(LeaveApplication.applied_at >= filters['applied_after'])
        
        if 'applied_before' in filters:
            query = query.filter(LeaveApplication.applied_at <= filters['applied_before'])
        
        if 'min_days' in filters:
            query = query.filter(LeaveApplication.total_days >= filters['min_days'])
        
        if 'max_days' in filters:
            query = query.filter(LeaveApplication.total_days <= filters['max_days'])
        
        if 'has_document' in filters:
            if filters['has_document']:
                query = query.filter(LeaveApplication.supporting_document_url.isnot(None))
            else:
                query = query.filter(LeaveApplication.supporting_document_url.is_(None))
        
        if 'return_confirmed' in filters:
            query = query.filter(LeaveApplication.return_confirmed == filters['return_confirmed'])
        
        # Apply sorting
        sort_by = filters.get('sort_by', 'applied_at')
        sort_order = filters.get('sort_order', 'desc')
        
        if hasattr(LeaveApplication, sort_by):
            order_col = getattr(LeaveApplication, sort_by)
            query = query.order_by(order_col.desc() if sort_order == 'desc' else order_col.asc())
        
        return self._paginate_query(query, pagination)

    # ============================================================================
    # VALIDATION AND BUSINESS RULES
    # ============================================================================

    def check_overlapping_leaves(
        self,
        student_id: UUID,
        from_date: date,
        to_date: date,
        exclude_leave_id: Optional[UUID] = None
    ) -> List[LeaveApplication]:
        """
        Check for overlapping leave applications.
        
        Args:
            student_id: Student ID
            from_date: Leave start date
            to_date: Leave end date
            exclude_leave_id: Optional leave ID to exclude from check
            
        Returns:
            List of overlapping leaves
        """
        query = self.session.query(LeaveApplication).filter(
            LeaveApplication.student_id == student_id,
            LeaveApplication.status.in_([LeaveStatus.PENDING, LeaveStatus.APPROVED]),
            or_(
                and_(
                    LeaveApplication.from_date >= from_date,
                    LeaveApplication.from_date <= to_date
                ),
                and_(
                    LeaveApplication.to_date >= from_date,
                    LeaveApplication.to_date <= to_date
                ),
                and_(
                    LeaveApplication.from_date <= from_date,
                    LeaveApplication.to_date >= to_date
                )
            ),
            LeaveApplication.deleted_at.is_(None)
        )
        
        if exclude_leave_id:
            query = query.filter(LeaveApplication.id != exclude_leave_id)
        
        return query.all()

    def validate_leave_quota(
        self,
        student_id: UUID,
        leave_type: LeaveType,
        days_requested: int,
        academic_year_start: date
    ) -> Dict[str, Any]:
        """
        Validate leave against quota.
        
        Args:
            student_id: Student ID
            leave_type: Leave type
            days_requested: Number of days requested
            academic_year_start: Academic year start date
            
        Returns:
            Validation result with quota information
        """
        # This would integrate with LeaveBalance repository
        # For now, return basic structure
        return {
            'is_valid': True,
            'days_available': None,
            'days_used': None,
            'days_remaining': None,
            'exceeds_quota': False
        }

    # ============================================================================
    # BULK OPERATIONS
    # ============================================================================

    def bulk_approve_leaves(
        self,
        leave_ids: List[UUID],
        approver_id: UUID,
        audit_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Bulk approve multiple leaves.
        
        Args:
            leave_ids: List of leave IDs to approve
            approver_id: User approving leaves
            audit_context: Audit information
            
        Returns:
            Results summary
        """
        approved = []
        failed = []
        
        for leave_id in leave_ids:
            result = self.approve_leave(leave_id, approver_id, audit_context=audit_context)
            if result:
                approved.append(leave_id)
            else:
                failed.append(leave_id)
        
        self.session.flush()
        
        return {
            'total': len(leave_ids),
            'approved': len(approved),
            'failed': len(failed),
            'approved_ids': approved,
            'failed_ids': failed
        }

    def bulk_update_status(
        self,
        leave_ids: List[UUID],
        new_status: LeaveStatus,
        user_id: UUID,
        reason: Optional[str] = None
    ) -> int:
        """
        Bulk update leave status.
        
        Args:
            leave_ids: List of leave IDs
            new_status: New status
            user_id: User making changes
            reason: Optional reason
            
        Returns:
            Number of updated leaves
        """
        updated = self.session.query(LeaveApplication).filter(
            LeaveApplication.id.in_(leave_ids),
            LeaveApplication.deleted_at.is_(None)
        ).update(
            {
                'status': new_status,
                'last_modified_at': datetime.utcnow(),
                'last_modified_by': user_id
            },
            synchronize_session=False
        )
        
        # Record status history for each
        for leave_id in leave_ids:
            history = LeaveStatusHistory(
                leave_id=leave_id,
                new_status=new_status,
                change_reason=reason or f"Bulk status update to {new_status.value}",
                changed_at=datetime.utcnow(),
                changed_by=user_id
            )
            self.session.add(history)
        
        self.session.flush()
        
        return updated

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _paginate_query(
        self,
        query,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[LeaveApplication]:
        """
        Apply pagination to query.
        
        Args:
            query: SQLAlchemy query
            pagination: Pagination parameters
            
        Returns:
            Paginated results
        """
        if pagination is None:
            pagination = PaginationParams(page=1, page_size=50)
        
        total = query.count()
        
        offset = (pagination.page - 1) * pagination.page_size
        items = query.offset(offset).limit(pagination.page_size).all()
        
        return PaginatedResult(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=(total + pagination.page_size - 1) // pagination.page_size
        )