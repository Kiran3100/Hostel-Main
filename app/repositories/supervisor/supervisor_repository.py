# app/repositories/supervisor/supervisor_repository.py
"""
Supervisor Repository - Core supervisor lifecycle management.

Handles comprehensive supervisor management with performance tracking,
employment lifecycle, workload optimization, and career development.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import and_, or_, func, case, distinct, select
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models.supervisor.supervisor import (
    Supervisor,
    SupervisorEmployment,
    SupervisorStatusHistory,
    SupervisorNote,
)
from app.models.supervisor.supervisor_permissions import SupervisorPermission
from app.models.supervisor.supervisor_assignment import SupervisorAssignment
from app.models.hostel.hostel import Hostel
from app.models.user.user import User
from app.schemas.common.enums import SupervisorStatus, EmploymentType
from app.repositories.base.base_repository import BaseRepository
from app.core.exceptions import (
    ResourceNotFoundError,
    BusinessLogicError,
    ValidationError,
)
from app.core.logging import logger


class SupervisorRepository(BaseRepository[Supervisor]):
    """
    Comprehensive supervisor management repository.
    
    Provides complete supervisor lifecycle management from hiring to termination
    with performance tracking, workload optimization, and career development.
    """
    
    def __init__(self, db: Session):
        """Initialize supervisor repository."""
        super().__init__(Supervisor, db)
        self.db = db
    
    # ==================== Core CRUD Operations ====================
    
    def create_supervisor(
        self,
        user_id: str,
        hostel_id: str,
        assigned_by: str,
        employee_id: Optional[str] = None,
        join_date: date = None,
        employment_type: EmploymentType = EmploymentType.FULL_TIME,
        designation: Optional[str] = None,
        salary: Optional[Decimal] = None,
        shift_timing: Optional[str] = None,
        contract_start_date: Optional[date] = None,
        contract_end_date: Optional[date] = None,
        emergency_contact_name: Optional[str] = None,
        emergency_contact_phone: Optional[str] = None,
        emergency_contact_relation: Optional[str] = None,
        notes: Optional[str] = None,
        **kwargs
    ) -> Supervisor:
        """
        Create new supervisor with complete employment details.
        
        Args:
            user_id: Associated user account ID
            hostel_id: Assigned hostel ID
            assigned_by: Admin who assigned supervisor
            employee_id: Unique employee/staff ID
            join_date: Joining/start date
            employment_type: Employment type (full-time, part-time, contract)
            designation: Job designation/title
            salary: Monthly salary
            shift_timing: Shift timing or working hours
            contract_start_date: Contract start date (for contract employees)
            contract_end_date: Contract end date (for contract employees)
            emergency_contact_name: Emergency contact name
            emergency_contact_phone: Emergency contact phone
            emergency_contact_relation: Emergency contact relationship
            notes: Administrative notes
            
        Returns:
            Created supervisor instance
            
        Raises:
            ValidationError: Invalid supervisor data
            BusinessLogicError: Business rule violation
        """
        try:
            # Validate user doesn't already have supervisor profile for this hostel
            existing = self.db.query(Supervisor).filter(
                and_(
                    Supervisor.user_id == user_id,
                    Supervisor.assigned_hostel_id == hostel_id,
                    Supervisor.is_deleted == False
                )
            ).first()
            
            if existing:
                raise BusinessLogicError(
                    f"Supervisor profile already exists for user {user_id} at hostel {hostel_id}"
                )
            
            # Set default join date
            if join_date is None:
                join_date = date.today()
            
            # Create supervisor
            supervisor = Supervisor(
                user_id=user_id,
                assigned_hostel_id=hostel_id,
                assigned_by=assigned_by,
                employee_id=employee_id,
                join_date=join_date,
                employment_type=employment_type,
                designation=designation,
                salary=salary,
                shift_timing=shift_timing,
                contract_start_date=contract_start_date,
                contract_end_date=contract_end_date,
                assigned_date=date.today(),
                status=SupervisorStatus.ACTIVE,
                is_active=True,
                emergency_contact_name=emergency_contact_name,
                emergency_contact_phone=emergency_contact_phone,
                emergency_contact_relation=emergency_contact_relation,
                notes=notes,
                **kwargs
            )
            
            self.db.add(supervisor)
            self.db.flush()
            
            # Create initial employment history record
            employment_history = SupervisorEmployment(
                supervisor_id=supervisor.id,
                hostel_id=hostel_id,
                start_date=join_date,
                employment_type=employment_type,
                designation=designation,
                shift_timing=shift_timing,
                changed_by=assigned_by
            )
            self.db.add(employment_history)
            
            # Create initial status history record
            status_history = SupervisorStatusHistory(
                supervisor_id=supervisor.id,
                previous_status=SupervisorStatus.ACTIVE,  # First status
                new_status=SupervisorStatus.ACTIVE,
                effective_date=join_date,
                reason="Initial supervisor assignment",
                changed_by=assigned_by
            )
            self.db.add(status_history)
            
            self.db.commit()
            self.db.refresh(supervisor)
            
            logger.info(
                f"Created supervisor {supervisor.id} for user {user_id} "
                f"at hostel {hostel_id}"
            )
            
            return supervisor
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error creating supervisor: {str(e)}")
            raise ValidationError(f"Invalid supervisor data: {str(e)}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating supervisor: {str(e)}")
            raise
    
    def get_supervisor_by_id(
        self,
        supervisor_id: str,
        include_deleted: bool = False,
        load_relationships: bool = True
    ) -> Optional[Supervisor]:
        """
        Get supervisor by ID with optional relationship loading.
        
        Args:
            supervisor_id: Supervisor ID
            include_deleted: Include soft-deleted supervisors
            load_relationships: Load related entities
            
        Returns:
            Supervisor instance or None
        """
        query = self.db.query(Supervisor).filter(Supervisor.id == supervisor_id)
        
        if not include_deleted:
            query = query.filter(Supervisor.is_deleted == False)
        
        if load_relationships:
            query = query.options(
                joinedload(Supervisor.user),
                joinedload(Supervisor.assigned_hostel),
                joinedload(Supervisor.permissions),
                selectinload(Supervisor.assignments)
            )
        
        return query.first()
    
    def get_supervisor_by_user_id(
        self,
        user_id: str,
        hostel_id: Optional[str] = None,
        include_deleted: bool = False
    ) -> Optional[Supervisor]:
        """
        Get supervisor by user ID and optional hostel ID.
        
        Args:
            user_id: User ID
            hostel_id: Optional hostel ID filter
            include_deleted: Include soft-deleted supervisors
            
        Returns:
            Supervisor instance or None
        """
        query = self.db.query(Supervisor).filter(Supervisor.user_id == user_id)
        
        if hostel_id:
            query = query.filter(Supervisor.assigned_hostel_id == hostel_id)
        
        if not include_deleted:
            query = query.filter(Supervisor.is_deleted == False)
        
        query = query.options(
            joinedload(Supervisor.user),
            joinedload(Supervisor.assigned_hostel),
            joinedload(Supervisor.permissions)
        )
        
        return query.first()
    
    def get_supervisor_by_employee_id(
        self,
        employee_id: str,
        include_deleted: bool = False
    ) -> Optional[Supervisor]:
        """
        Get supervisor by employee ID.
        
        Args:
            employee_id: Employee/staff ID
            include_deleted: Include soft-deleted supervisors
            
        Returns:
            Supervisor instance or None
        """
        query = self.db.query(Supervisor).filter(
            Supervisor.employee_id == employee_id
        )
        
        if not include_deleted:
            query = query.filter(Supervisor.is_deleted == False)
        
        return query.first()
    
    def update_supervisor(
        self,
        supervisor_id: str,
        update_data: Dict[str, Any],
        updated_by: str
    ) -> Supervisor:
        """
        Update supervisor information.
        
        Args:
            supervisor_id: Supervisor ID
            update_data: Fields to update
            updated_by: User making the update
            
        Returns:
            Updated supervisor instance
            
        Raises:
            ResourceNotFoundError: Supervisor not found
        """
        supervisor = self.get_supervisor_by_id(supervisor_id)
        if not supervisor:
            raise ResourceNotFoundError(f"Supervisor {supervisor_id} not found")
        
        try:
            # Track salary changes
            if 'salary' in update_data and update_data['salary'] != supervisor.salary:
                supervisor.last_salary_revision = date.today()
            
            # Update fields
            for field, value in update_data.items():
                if hasattr(supervisor, field):
                    setattr(supervisor, field, value)
            
            supervisor.updated_by = updated_by
            
            self.db.commit()
            self.db.refresh(supervisor)
            
            logger.info(f"Updated supervisor {supervisor_id}")
            return supervisor
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating supervisor {supervisor_id}: {str(e)}")
            raise
    
    # ==================== Status Management ====================
    
    def change_supervisor_status(
        self,
        supervisor_id: str,
        new_status: SupervisorStatus,
        reason: str,
        changed_by: str,
        effective_date: date = None,
        suspension_start: Optional[date] = None,
        suspension_end: Optional[date] = None,
        leave_start: Optional[date] = None,
        leave_end: Optional[date] = None,
        leave_type: Optional[str] = None,
        termination_type: Optional[str] = None,
        eligible_for_rehire: Optional[bool] = None,
        handover_to: Optional[str] = None
    ) -> Supervisor:
        """
        Change supervisor status with complete audit trail.
        
        Args:
            supervisor_id: Supervisor ID
            new_status: New status to set
            reason: Reason for status change
            changed_by: Admin making the change
            effective_date: Effective date of change
            suspension_start: Suspension start date
            suspension_end: Suspension end date
            leave_start: Leave start date
            leave_end: Leave end date
            leave_type: Type of leave
            termination_type: Type of termination
            eligible_for_rehire: Rehire eligibility
            handover_to: Supervisor ID for handover
            
        Returns:
            Updated supervisor instance
        """
        supervisor = self.get_supervisor_by_id(supervisor_id)
        if not supervisor:
            raise ResourceNotFoundError(f"Supervisor {supervisor_id} not found")
        
        if effective_date is None:
            effective_date = date.today()
        
        try:
            previous_status = supervisor.status
            
            # Create status history record
            status_history = SupervisorStatusHistory(
                supervisor_id=supervisor_id,
                previous_status=previous_status,
                new_status=new_status,
                effective_date=effective_date,
                reason=reason,
                changed_by=changed_by,
                handover_to=handover_to
            )
            self.db.add(status_history)
            
            # Update supervisor status
            supervisor.status = new_status
            
            # Handle status-specific fields
            if new_status == SupervisorStatus.SUSPENDED:
                supervisor.suspension_start_date = suspension_start or date.today()
                supervisor.suspension_end_date = suspension_end
                supervisor.suspension_reason = reason
                supervisor.is_active = False
                
            elif new_status == SupervisorStatus.ON_LEAVE:
                supervisor.leave_start_date = leave_start or date.today()
                supervisor.leave_end_date = leave_end
                supervisor.leave_type = leave_type
                supervisor.is_active = False
                
            elif new_status == SupervisorStatus.TERMINATED:
                supervisor.termination_date = effective_date
                supervisor.termination_reason = reason
                supervisor.termination_type = termination_type
                supervisor.eligible_for_rehire = eligible_for_rehire
                supervisor.is_active = False
                
                # End current employment history
                current_employment = self.db.query(SupervisorEmployment).filter(
                    and_(
                        SupervisorEmployment.supervisor_id == supervisor_id,
                        SupervisorEmployment.end_date.is_(None)
                    )
                ).first()
                
                if current_employment:
                    current_employment.end_date = effective_date
                    current_employment.reason_for_change = reason
                    current_employment.changed_by = changed_by
                
            elif new_status == SupervisorStatus.ACTIVE:
                # Clear suspension/leave details
                supervisor.suspension_start_date = None
                supervisor.suspension_end_date = None
                supervisor.suspension_reason = None
                supervisor.leave_start_date = None
                supervisor.leave_end_date = None
                supervisor.leave_type = None
                supervisor.is_active = True
            
            self.db.commit()
            self.db.refresh(supervisor)
            
            logger.info(
                f"Changed supervisor {supervisor_id} status from "
                f"{previous_status.value} to {new_status.value}"
            )
            
            return supervisor
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error changing supervisor status: {str(e)}")
            raise
    
    def suspend_supervisor(
        self,
        supervisor_id: str,
        reason: str,
        suspended_by: str,
        start_date: date = None,
        end_date: Optional[date] = None,
        handover_to: Optional[str] = None
    ) -> Supervisor:
        """Suspend supervisor with optional end date."""
        return self.change_supervisor_status(
            supervisor_id=supervisor_id,
            new_status=SupervisorStatus.SUSPENDED,
            reason=reason,
            changed_by=suspended_by,
            effective_date=start_date,
            suspension_start=start_date or date.today(),
            suspension_end=end_date,
            handover_to=handover_to
        )
    
    def terminate_supervisor(
        self,
        supervisor_id: str,
        reason: str,
        terminated_by: str,
        termination_type: str,
        effective_date: date = None,
        eligible_for_rehire: bool = False,
        handover_to: Optional[str] = None
    ) -> Supervisor:
        """Terminate supervisor employment."""
        return self.change_supervisor_status(
            supervisor_id=supervisor_id,
            new_status=SupervisorStatus.TERMINATED,
            reason=reason,
            changed_by=terminated_by,
            effective_date=effective_date,
            termination_type=termination_type,
            eligible_for_rehire=eligible_for_rehire,
            handover_to=handover_to
        )
    
    def reactivate_supervisor(
        self,
        supervisor_id: str,
        reason: str,
        reactivated_by: str,
        effective_date: date = None
    ) -> Supervisor:
        """Reactivate suspended or on-leave supervisor."""
        return self.change_supervisor_status(
            supervisor_id=supervisor_id,
            new_status=SupervisorStatus.ACTIVE,
            reason=reason,
            changed_by=reactivated_by,
            effective_date=effective_date
        )
    
    # ==================== Query Methods ====================
    
    def get_supervisors_by_hostel(
        self,
        hostel_id: str,
        status: Optional[SupervisorStatus] = None,
        is_active: Optional[bool] = None,
        employment_type: Optional[EmploymentType] = None,
        include_deleted: bool = False
    ) -> List[Supervisor]:
        """
        Get all supervisors for a hostel with optional filters.
        
        Args:
            hostel_id: Hostel ID
            status: Filter by status
            is_active: Filter by active status
            employment_type: Filter by employment type
            include_deleted: Include soft-deleted supervisors
            
        Returns:
            List of supervisors
        """
        query = self.db.query(Supervisor).filter(
            Supervisor.assigned_hostel_id == hostel_id
        )
        
        if status:
            query = query.filter(Supervisor.status == status)
        
        if is_active is not None:
            query = query.filter(Supervisor.is_active == is_active)
        
        if employment_type:
            query = query.filter(Supervisor.employment_type == employment_type)
        
        if not include_deleted:
            query = query.filter(Supervisor.is_deleted == False)
        
        query = query.options(
            joinedload(Supervisor.user),
            joinedload(Supervisor.permissions)
        )
        
        return query.all()
    
    def get_active_supervisors(
        self,
        hostel_id: Optional[str] = None
    ) -> List[Supervisor]:
        """Get all active supervisors, optionally filtered by hostel."""
        query = self.db.query(Supervisor).filter(
            and_(
                Supervisor.is_active == True,
                Supervisor.status == SupervisorStatus.ACTIVE,
                Supervisor.is_deleted == False
            )
        )
        
        if hostel_id:
            query = query.filter(Supervisor.assigned_hostel_id == hostel_id)
        
        return query.options(
            joinedload(Supervisor.user),
            joinedload(Supervisor.assigned_hostel)
        ).all()
    
    def get_supervisors_by_status(
        self,
        status: SupervisorStatus,
        hostel_id: Optional[str] = None
    ) -> List[Supervisor]:
        """Get supervisors by status."""
        query = self.db.query(Supervisor).filter(
            and_(
                Supervisor.status == status,
                Supervisor.is_deleted == False
            )
        )
        
        if hostel_id:
            query = query.filter(Supervisor.assigned_hostel_id == hostel_id)
        
        return query.all()
    
    def get_supervisors_on_probation(
        self,
        hostel_id: Optional[str] = None
    ) -> List[Supervisor]:
        """Get supervisors in probation period (first 3 months)."""
        probation_date = date.today() - timedelta(days=90)
        
        query = self.db.query(Supervisor).filter(
            and_(
                Supervisor.join_date >= probation_date,
                Supervisor.status == SupervisorStatus.ACTIVE,
                Supervisor.is_deleted == False
            )
        )
        
        if hostel_id:
            query = query.filter(Supervisor.assigned_hostel_id == hostel_id)
        
        return query.all()
    
    def get_contract_supervisors_expiring_soon(
        self,
        days: int = 30,
        hostel_id: Optional[str] = None
    ) -> List[Supervisor]:
        """Get contract supervisors with contracts expiring within specified days."""
        expiry_date = date.today() + timedelta(days=days)
        
        query = self.db.query(Supervisor).filter(
            and_(
                Supervisor.employment_type == EmploymentType.CONTRACT,
                Supervisor.contract_end_date.isnot(None),
                Supervisor.contract_end_date <= expiry_date,
                Supervisor.contract_end_date >= date.today(),
                Supervisor.status == SupervisorStatus.ACTIVE,
                Supervisor.is_deleted == False
            )
        )
        
        if hostel_id:
            query = query.filter(Supervisor.assigned_hostel_id == hostel_id)
        
        return query.order_by(Supervisor.contract_end_date).all()
    
    def search_supervisors(
        self,
        search_term: str,
        hostel_id: Optional[str] = None,
        status: Optional[SupervisorStatus] = None,
        limit: int = 50
    ) -> List[Supervisor]:
        """
        Search supervisors by name, employee ID, or email.
        
        Args:
            search_term: Search term
            hostel_id: Optional hostel filter
            status: Optional status filter
            limit: Maximum results
            
        Returns:
            List of matching supervisors
        """
        # Join with User table for name/email search
        query = self.db.query(Supervisor).join(User).filter(
            and_(
                Supervisor.is_deleted == False,
                or_(
                    User.full_name.ilike(f"%{search_term}%"),
                    User.email.ilike(f"%{search_term}%"),
                    Supervisor.employee_id.ilike(f"%{search_term}%")
                )
            )
        )
        
        if hostel_id:
            query = query.filter(Supervisor.assigned_hostel_id == hostel_id)
        
        if status:
            query = query.filter(Supervisor.status == status)
        
        return query.options(
            joinedload(Supervisor.user)
        ).limit(limit).all()
    
    # ==================== Statistics and Analytics ====================
    
    def get_supervisor_statistics(
        self,
        hostel_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive supervisor statistics.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary with statistics
        """
        query = self.db.query(Supervisor).filter(Supervisor.is_deleted == False)
        
        if hostel_id:
            query = query.filter(Supervisor.assigned_hostel_id == hostel_id)
        
        # Base counts
        total = query.count()
        active = query.filter(Supervisor.status == SupervisorStatus.ACTIVE).count()
        suspended = query.filter(Supervisor.status == SupervisorStatus.SUSPENDED).count()
        on_leave = query.filter(Supervisor.status == SupervisorStatus.ON_LEAVE).count()
        
        # Employment type breakdown
        full_time = query.filter(
            Supervisor.employment_type == EmploymentType.FULL_TIME
        ).count()
        part_time = query.filter(
            Supervisor.employment_type == EmploymentType.PART_TIME
        ).count()
        contract = query.filter(
            Supervisor.employment_type == EmploymentType.CONTRACT
        ).count()
        
        # Probation count
        probation_date = date.today() - timedelta(days=90)
        on_probation = query.filter(
            and_(
                Supervisor.join_date >= probation_date,
                Supervisor.status == SupervisorStatus.ACTIVE
            )
        ).count()
        
        # Contract expiring soon
        expiry_date = date.today() + timedelta(days=30)
        contracts_expiring = query.filter(
            and_(
                Supervisor.employment_type == EmploymentType.CONTRACT,
                Supervisor.contract_end_date.isnot(None),
                Supervisor.contract_end_date <= expiry_date,
                Supervisor.contract_end_date >= date.today()
            )
        ).count()
        
        # Average tenure
        avg_tenure_query = query.filter(
            Supervisor.status == SupervisorStatus.ACTIVE
        )
        supervisors = avg_tenure_query.all()
        
        if supervisors:
            total_tenure_days = sum(s.tenure_days for s in supervisors)
            avg_tenure_months = (total_tenure_days / len(supervisors)) / 30
        else:
            avg_tenure_months = 0
        
        return {
            'total_supervisors': total,
            'active_supervisors': active,
            'suspended_supervisors': suspended,
            'on_leave_supervisors': on_leave,
            'full_time_supervisors': full_time,
            'part_time_supervisors': part_time,
            'contract_supervisors': contract,
            'on_probation': on_probation,
            'contracts_expiring_soon': contracts_expiring,
            'average_tenure_months': round(avg_tenure_months, 2),
            'active_percentage': round((active / total * 100) if total > 0 else 0, 2)
        }
    
    def get_performance_summary(
        self,
        supervisor_id: str,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Get performance summary for a supervisor.
        
        Args:
            supervisor_id: Supervisor ID
            period_days: Period for metrics calculation
            
        Returns:
            Performance summary dictionary
        """
        supervisor = self.get_supervisor_by_id(supervisor_id)
        if not supervisor:
            raise ResourceNotFoundError(f"Supervisor {supervisor_id} not found")
        
        return {
            'supervisor_id': supervisor_id,
            'employee_id': supervisor.employee_id,
            'tenure_months': supervisor.tenure_months,
            'is_probation': supervisor.is_probation,
            'complaints_resolved': supervisor.total_complaints_resolved,
            'average_resolution_time_hours': float(supervisor.average_resolution_time_hours),
            'attendance_records': supervisor.total_attendance_records,
            'maintenance_requests': supervisor.total_maintenance_requests,
            'performance_rating': float(supervisor.performance_rating) if supervisor.performance_rating else None,
            'last_performance_review': supervisor.last_performance_review,
            'last_login': supervisor.last_login,
            'total_logins': supervisor.total_logins,
            'last_activity': supervisor.last_activity
        }
    
    # ==================== Notes Management ====================
    
    def add_supervisor_note(
        self,
        supervisor_id: str,
        note_type: str,
        subject: str,
        content: str,
        created_by: str,
        is_confidential: bool = False,
        is_visible_to_supervisor: bool = False,
        requires_follow_up: bool = False,
        follow_up_date: Optional[date] = None
    ) -> SupervisorNote:
        """
        Add administrative note for supervisor.
        
        Args:
            supervisor_id: Supervisor ID
            note_type: Note type (performance, disciplinary, commendation, general)
            subject: Note subject
            content: Note content
            created_by: Admin creating note
            is_confidential: Confidential flag
            is_visible_to_supervisor: Visibility to supervisor
            requires_follow_up: Follow-up required
            follow_up_date: Follow-up date
            
        Returns:
            Created note instance
        """
        supervisor = self.get_supervisor_by_id(supervisor_id)
        if not supervisor:
            raise ResourceNotFoundError(f"Supervisor {supervisor_id} not found")
        
        note = SupervisorNote(
            supervisor_id=supervisor_id,
            note_type=note_type,
            subject=subject,
            content=content,
            created_by=created_by,
            is_confidential=is_confidential,
            is_visible_to_supervisor=is_visible_to_supervisor,
            requires_follow_up=requires_follow_up,
            follow_up_date=follow_up_date
        )
        
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        
        logger.info(f"Added note for supervisor {supervisor_id}: {subject}")
        return note
    
    def get_supervisor_notes(
        self,
        supervisor_id: str,
        note_type: Optional[str] = None,
        include_confidential: bool = True,
        pending_follow_up_only: bool = False
    ) -> List[SupervisorNote]:
        """Get notes for supervisor with filters."""
        query = self.db.query(SupervisorNote).filter(
            SupervisorNote.supervisor_id == supervisor_id
        )
        
        if note_type:
            query = query.filter(SupervisorNote.note_type == note_type)
        
        if not include_confidential:
            query = query.filter(SupervisorNote.is_confidential == False)
        
        if pending_follow_up_only:
            query = query.filter(
                and_(
                    SupervisorNote.requires_follow_up == True,
                    SupervisorNote.follow_up_completed == False
                )
            )
        
        return query.order_by(SupervisorNote.created_at.desc()).all()
    
    def complete_note_follow_up(
        self,
        note_id: str
    ) -> SupervisorNote:
        """Mark note follow-up as completed."""
        note = self.db.query(SupervisorNote).filter(
            SupervisorNote.id == note_id
        ).first()
        
        if not note:
            raise ResourceNotFoundError(f"Note {note_id} not found")
        
        note.follow_up_completed = True
        self.db.commit()
        self.db.refresh(note)
        
        return note
    
    # ==================== Bulk Operations ====================
    
    def bulk_update_status(
        self,
        supervisor_ids: List[str],
        new_status: SupervisorStatus,
        reason: str,
        changed_by: str
    ) -> int:
        """
        Bulk update supervisor status.
        
        Args:
            supervisor_ids: List of supervisor IDs
            new_status: New status to set
            reason: Reason for change
            changed_by: Admin making change
            
        Returns:
            Number of supervisors updated
        """
        updated_count = 0
        
        for supervisor_id in supervisor_ids:
            try:
                self.change_supervisor_status(
                    supervisor_id=supervisor_id,
                    new_status=new_status,
                    reason=reason,
                    changed_by=changed_by
                )
                updated_count += 1
            except Exception as e:
                logger.error(
                    f"Error updating supervisor {supervisor_id} status: {str(e)}"
                )
                continue
        
        return updated_count
    
    def get_supervisors_for_review(
        self,
        hostel_id: Optional[str] = None,
        months_since_last_review: int = 6
    ) -> List[Supervisor]:
        """
        Get supervisors due for performance review.
        
        Args:
            hostel_id: Optional hostel filter
            months_since_last_review: Months since last review
            
        Returns:
            List of supervisors due for review
        """
        review_due_date = date.today() - timedelta(days=months_since_last_review * 30)
        
        query = self.db.query(Supervisor).filter(
            and_(
                Supervisor.status == SupervisorStatus.ACTIVE,
                Supervisor.is_deleted == False,
                or_(
                    Supervisor.last_performance_review.is_(None),
                    Supervisor.last_performance_review <= review_due_date
                )
            )
        )
        
        if hostel_id:
            query = query.filter(Supervisor.assigned_hostel_id == hostel_id)
        
        return query.all()
    
    # ==================== Soft Delete and Recovery ====================
    
    def soft_delete_supervisor(
        self,
        supervisor_id: str,
        deleted_by: str,
        reason: Optional[str] = None
    ) -> Supervisor:
        """
        Soft delete supervisor (maintains data integrity).
        
        Args:
            supervisor_id: Supervisor ID
            deleted_by: User performing deletion
            reason: Deletion reason
            
        Returns:
            Soft-deleted supervisor
        """
        supervisor = self.get_supervisor_by_id(supervisor_id)
        if not supervisor:
            raise ResourceNotFoundError(f"Supervisor {supervisor_id} not found")
        
        supervisor.is_deleted = True
        supervisor.deleted_at = datetime.utcnow()
        supervisor.deleted_by = deleted_by
        supervisor.is_active = False
        
        if reason:
            self.add_supervisor_note(
                supervisor_id=supervisor_id,
                note_type="general",
                subject="Supervisor Profile Deleted",
                content=reason,
                created_by=deleted_by,
                is_confidential=True
            )
        
        self.db.commit()
        self.db.refresh(supervisor)
        
        logger.info(f"Soft deleted supervisor {supervisor_id}")
        return supervisor
    
    def restore_supervisor(
        self,
        supervisor_id: str,
        restored_by: str
    ) -> Supervisor:
        """Restore soft-deleted supervisor."""
        supervisor = self.get_supervisor_by_id(supervisor_id, include_deleted=True)
        if not supervisor:
            raise ResourceNotFoundError(f"Supervisor {supervisor_id} not found")
        
        supervisor.is_deleted = False
        supervisor.deleted_at = None
        supervisor.deleted_by = None
        
        self.db.commit()
        self.db.refresh(supervisor)
        
        logger.info(f"Restored supervisor {supervisor_id}")
        return supervisor