# app/repositories/supervisor/supervisor_assignment_repository.py
"""
Supervisor Assignment Repository - Assignment and transfer management.

Handles supervisor-hostel assignments, transfers, coverage analysis,
and workload optimization with approval workflows.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy import and_, or_, func, case
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import IntegrityError

from app.models.supervisor.supervisor_assignment import (
    SupervisorAssignment,
    AssignmentTransfer,
    AssignmentCoverage,
    WorkloadMetric,
)
from app.models.supervisor.supervisor import Supervisor
from app.models.hostel.hostel import Hostel
from app.repositories.base.base_repository import BaseRepository
from app.core.exceptions import (
    ResourceNotFoundError,
    BusinessLogicError,
    ValidationError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)



class SupervisorAssignmentRepository(BaseRepository[SupervisorAssignment]):
    """
    Supervisor assignment repository for hostel assignments.
    
    Manages assignment lifecycle, transfers, coverage analysis,
    and workload optimization for balanced supervision.
    """
    
    def __init__(self, db: Session):
        """Initialize assignment repository."""
        super().__init__(SupervisorAssignment, db)
        self.db = db
    
    # ==================== Assignment Operations ====================
    
    def create_assignment(
        self,
        supervisor_id: str,
        hostel_id: str,
        assigned_by: str,
        is_primary: bool = True,
        assignment_type: str = "permanent",
        effective_from: date = None,
        effective_to: Optional[date] = None,
        assigned_rooms: Optional[int] = None,
        assigned_floors: Optional[str] = None,
        assigned_areas: Optional[Dict] = None,
        responsibilities: Optional[Dict] = None,
        shift_timing: Optional[str] = None,
        assignment_reason: Optional[str] = None
    ) -> SupervisorAssignment:
        """
        Create new supervisor assignment.
        
        Args:
            supervisor_id: Supervisor ID
            hostel_id: Hostel ID
            assigned_by: Admin who assigned
            is_primary: Primary assignment flag
            assignment_type: Type (permanent, temporary, backup, relief)
            effective_from: Start date
            effective_to: End date (None for current)
            assigned_rooms: Number of rooms
            assigned_floors: Floor list
            assigned_areas: Specific areas/zones
            responsibilities: Specific duties
            shift_timing: Shift timing
            assignment_reason: Reason for assignment
            
        Returns:
            Created assignment instance
        """
        if effective_from is None:
            effective_from = date.today()
        
        try:
            # Check for conflicting assignments
            conflicts = self.get_conflicting_assignments(
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                start_date=effective_from,
                end_date=effective_to
            )
            
            if conflicts:
                raise BusinessLogicError(
                    f"Supervisor already has assignment for this period"
                )
            
            assignment = SupervisorAssignment(
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                assigned_by=assigned_by,
                assigned_date=date.today(),
                is_primary=is_primary,
                assignment_type=assignment_type,
                effective_from=effective_from,
                effective_to=effective_to,
                assigned_rooms=assigned_rooms,
                assigned_floors=assigned_floors,
                assigned_areas=assigned_areas,
                responsibilities=responsibilities,
                shift_timing=shift_timing,
                assignment_reason=assignment_reason,
                is_active=True
            )
            
            self.db.add(assignment)
            self.db.commit()
            self.db.refresh(assignment)
            
            logger.info(
                f"Created assignment for supervisor {supervisor_id} "
                f"to hostel {hostel_id}"
            )
            
            return assignment
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error creating assignment: {str(e)}")
            raise ValidationError(f"Invalid assignment data: {str(e)}")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating assignment: {str(e)}")
            raise
    
    def get_assignment_by_id(
        self,
        assignment_id: str,
        load_relationships: bool = True
    ) -> Optional[SupervisorAssignment]:
        """Get assignment by ID with optional relationships."""
        query = self.db.query(SupervisorAssignment).filter(
            SupervisorAssignment.id == assignment_id
        )
        
        if load_relationships:
            query = query.options(
                joinedload(SupervisorAssignment.supervisor),
                joinedload(SupervisorAssignment.hostel)
            )
        
        return query.first()
    
    def get_active_assignments(
        self,
        supervisor_id: Optional[str] = None,
        hostel_id: Optional[str] = None,
        is_primary: Optional[bool] = None
    ) -> List[SupervisorAssignment]:
        """
        Get active assignments with filters.
        
        Args:
            supervisor_id: Filter by supervisor
            hostel_id: Filter by hostel
            is_primary: Filter by primary status
            
        Returns:
            List of active assignments
        """
        query = self.db.query(SupervisorAssignment).filter(
            SupervisorAssignment.is_active == True
        )
        
        if supervisor_id:
            query = query.filter(
                SupervisorAssignment.supervisor_id == supervisor_id
            )
        
        if hostel_id:
            query = query.filter(
                SupervisorAssignment.hostel_id == hostel_id
            )
        
        if is_primary is not None:
            query = query.filter(
                SupervisorAssignment.is_primary == is_primary
            )
        
        return query.options(
            joinedload(SupervisorAssignment.supervisor),
            joinedload(SupervisorAssignment.hostel)
        ).all()
    
    def get_current_assignment(
        self,
        supervisor_id: str,
        hostel_id: Optional[str] = None
    ) -> Optional[SupervisorAssignment]:
        """Get current primary assignment for supervisor."""
        query = self.db.query(SupervisorAssignment).filter(
            and_(
                SupervisorAssignment.supervisor_id == supervisor_id,
                SupervisorAssignment.is_active == True,
                SupervisorAssignment.is_primary == True,
                SupervisorAssignment.effective_to.is_(None)
            )
        )
        
        if hostel_id:
            query = query.filter(SupervisorAssignment.hostel_id == hostel_id)
        
        return query.first()
    
    def get_conflicting_assignments(
        self,
        supervisor_id: str,
        hostel_id: str,
        start_date: date,
        end_date: Optional[date]
    ) -> List[SupervisorAssignment]:
        """Check for conflicting assignments in date range."""
        query = self.db.query(SupervisorAssignment).filter(
            and_(
                SupervisorAssignment.supervisor_id == supervisor_id,
                SupervisorAssignment.hostel_id == hostel_id,
                SupervisorAssignment.is_active == True
            )
        )
        
        # Check for overlapping dates
        if end_date:
            query = query.filter(
                or_(
                    and_(
                        SupervisorAssignment.effective_from <= end_date,
                        or_(
                            SupervisorAssignment.effective_to.is_(None),
                            SupervisorAssignment.effective_to >= start_date
                        )
                    )
                )
            )
        else:
            query = query.filter(
                or_(
                    SupervisorAssignment.effective_to.is_(None),
                    SupervisorAssignment.effective_to >= start_date
                )
            )
        
        return query.all()
    
    def revoke_assignment(
        self,
        assignment_id: str,
        revoked_by: str,
        revocation_reason: str,
        effective_date: date = None,
        handover_to: Optional[str] = None
    ) -> SupervisorAssignment:
        """
        Revoke assignment with handover support.
        
        Args:
            assignment_id: Assignment ID
            revoked_by: Admin revoking assignment
            revocation_reason: Reason for revocation
            effective_date: Revocation effective date
            handover_to: Supervisor for handover
            
        Returns:
            Revoked assignment
        """
        assignment = self.get_assignment_by_id(assignment_id)
        if not assignment:
            raise ResourceNotFoundError(f"Assignment {assignment_id} not found")
        
        if effective_date is None:
            effective_date = date.today()
        
        assignment.is_active = False
        assignment.effective_to = effective_date
        assignment.revoked_at = datetime.utcnow()
        assignment.revoked_by = revoked_by
        assignment.revocation_reason = revocation_reason
        assignment.handover_to_supervisor_id = handover_to
        
        self.db.commit()
        self.db.refresh(assignment)
        
        logger.info(f"Revoked assignment {assignment_id}")
        return assignment
    
    def complete_handover(
        self,
        assignment_id: str,
        handover_notes: Optional[str] = None
    ) -> SupervisorAssignment:
        """Mark assignment handover as completed."""
        assignment = self.get_assignment_by_id(assignment_id)
        if not assignment:
            raise ResourceNotFoundError(f"Assignment {assignment_id} not found")
        
        assignment.handover_completed = True
        if handover_notes:
            assignment.handover_notes = handover_notes
        
        self.db.commit()
        self.db.refresh(assignment)
        
        return assignment
    
    # ==================== Transfer Management ====================
    
    def create_transfer_request(
        self,
        supervisor_id: str,
        from_hostel_id: str,
        to_hostel_id: str,
        transfer_date: date,
        transfer_type: str,
        reason: str,
        requested_by: str,
        retain_permissions: bool = True,
        new_permissions_config: Optional[Dict] = None,
        handover_period_days: int = 7,
        handover_to: Optional[str] = None
    ) -> AssignmentTransfer:
        """
        Create transfer request for supervisor.
        
        Args:
            supervisor_id: Supervisor to transfer
            from_hostel_id: Current hostel
            to_hostel_id: Destination hostel
            transfer_date: Transfer effective date
            transfer_type: Type (permanent, temporary, emergency)
            reason: Transfer reason
            requested_by: Admin requesting transfer
            retain_permissions: Keep same permissions
            new_permissions_config: New permissions if not retaining
            handover_period_days: Handover duration
            handover_to: Supervisor for handover
            
        Returns:
            Created transfer request
        """
        try:
            transfer = AssignmentTransfer(
                supervisor_id=supervisor_id,
                from_hostel_id=from_hostel_id,
                to_hostel_id=to_hostel_id,
                transfer_date=transfer_date,
                transfer_type=transfer_type,
                reason=reason,
                requested_by=requested_by,
                approval_status="pending",
                retain_permissions=retain_permissions,
                new_permissions_config=new_permissions_config,
                handover_period_days=handover_period_days,
                handover_to_supervisor_id=handover_to
            )
            
            self.db.add(transfer)
            self.db.commit()
            self.db.refresh(transfer)
            
            logger.info(
                f"Created transfer request for supervisor {supervisor_id} "
                f"from hostel {from_hostel_id} to {to_hostel_id}"
            )
            
            return transfer
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating transfer request: {str(e)}")
            raise
    
    def approve_transfer(
        self,
        transfer_id: str,
        approved_by: str
    ) -> AssignmentTransfer:
        """Approve transfer request."""
        transfer = self.db.query(AssignmentTransfer).filter(
            AssignmentTransfer.id == transfer_id
        ).first()
        
        if not transfer:
            raise ResourceNotFoundError(f"Transfer {transfer_id} not found")
        
        if transfer.approval_status != "pending":
            raise BusinessLogicError(
                f"Transfer already {transfer.approval_status}"
            )
        
        transfer.approval_status = "approved"
        transfer.approved_by = approved_by
        transfer.approved_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(transfer)
        
        logger.info(f"Approved transfer {transfer_id}")
        return transfer
    
    def reject_transfer(
        self,
        transfer_id: str,
        rejected_by: str,
        rejection_reason: str
    ) -> AssignmentTransfer:
        """Reject transfer request."""
        transfer = self.db.query(AssignmentTransfer).filter(
            AssignmentTransfer.id == transfer_id
        ).first()
        
        if not transfer:
            raise ResourceNotFoundError(f"Transfer {transfer_id} not found")
        
        if transfer.approval_status != "pending":
            raise BusinessLogicError(
                f"Transfer already {transfer.approval_status}"
            )
        
        transfer.approval_status = "rejected"
        transfer.approved_by = rejected_by
        transfer.approved_at = datetime.utcnow()
        transfer.rejection_reason = rejection_reason
        
        self.db.commit()
        self.db.refresh(transfer)
        
        logger.info(f"Rejected transfer {transfer_id}")
        return transfer
    
    def execute_transfer(
        self,
        transfer_id: str,
        executed_by: str
    ) -> AssignmentTransfer:
        """
        Execute approved transfer.
        
        Creates new assignment and ends old one.
        """
        transfer = self.db.query(AssignmentTransfer).filter(
            AssignmentTransfer.id == transfer_id
        ).options(
            joinedload(AssignmentTransfer.supervisor)
        ).first()
        
        if not transfer:
            raise ResourceNotFoundError(f"Transfer {transfer_id} not found")
        
        if transfer.approval_status != "approved":
            raise BusinessLogicError("Transfer must be approved before execution")
        
        if transfer.transfer_completed:
            raise BusinessLogicError("Transfer already completed")
        
        try:
            # End current assignment
            current_assignment = self.get_current_assignment(
                supervisor_id=transfer.supervisor_id,
                hostel_id=transfer.from_hostel_id
            )
            
            if current_assignment:
                self.revoke_assignment(
                    assignment_id=current_assignment.id,
                    revoked_by=executed_by,
                    revocation_reason=f"Transfer to hostel {transfer.to_hostel_id}",
                    effective_date=transfer.transfer_date,
                    handover_to=transfer.handover_to_supervisor_id
                )
            
            # Create new assignment
            new_assignment = self.create_assignment(
                supervisor_id=transfer.supervisor_id,
                hostel_id=transfer.to_hostel_id,
                assigned_by=executed_by,
                is_primary=True,
                assignment_type="permanent" if transfer.transfer_type == "permanent" else "temporary",
                effective_from=transfer.transfer_date,
                assignment_reason=f"Transfer from hostel {transfer.from_hostel_id}"
            )
            
            # Mark transfer as completed
            transfer.transfer_completed = True
            transfer.completed_at = datetime.utcnow()
            transfer.completed_by = executed_by
            
            self.db.commit()
            self.db.refresh(transfer)
            
            logger.info(f"Executed transfer {transfer_id}")
            return transfer
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error executing transfer: {str(e)}")
            raise
    
    def get_pending_transfers(
        self,
        hostel_id: Optional[str] = None
    ) -> List[AssignmentTransfer]:
        """Get pending transfer requests."""
        query = self.db.query(AssignmentTransfer).filter(
            AssignmentTransfer.approval_status == "pending"
        )
        
        if hostel_id:
            query = query.filter(
                or_(
                    AssignmentTransfer.from_hostel_id == hostel_id,
                    AssignmentTransfer.to_hostel_id == hostel_id
                )
            )
        
        return query.options(
            joinedload(AssignmentTransfer.supervisor),
            joinedload(AssignmentTransfer.from_hostel),
            joinedload(AssignmentTransfer.to_hostel)
        ).all()
    
    # ==================== Coverage Analysis ====================
    
    def calculate_coverage(
        self,
        hostel_id: str,
        coverage_date: date,
        shift: str = "24x7"
    ) -> AssignmentCoverage:
        """
        Calculate supervisor coverage for hostel on specific date.
        
        Args:
            hostel_id: Hostel ID
            coverage_date: Date to analyze
            shift: Shift to analyze
            
        Returns:
            Coverage analysis
        """
        # Get active assignments for date
        assignments = self.db.query(SupervisorAssignment).filter(
            and_(
                SupervisorAssignment.hostel_id == hostel_id,
                SupervisorAssignment.is_active == True,
                SupervisorAssignment.effective_from <= coverage_date,
                or_(
                    SupervisorAssignment.effective_to.is_(None),
                    SupervisorAssignment.effective_to >= coverage_date
                )
            )
        ).all()
        
        total_assigned = len(assignments)
        
        # Check supervisor availability (not on leave/suspended)
        present_count = 0
        leave_count = 0
        
        for assignment in assignments:
            supervisor = assignment.supervisor
            if supervisor.status.value == "ACTIVE" and supervisor.is_active:
                present_count += 1
            elif supervisor.status.value == "ON_LEAVE":
                leave_count += 1
        
        # Calculate coverage percentage
        coverage_percentage = (
            (present_count / total_assigned * 100)
            if total_assigned > 0 else 0
        )
        
        # Determine if there's a gap
        has_gap = coverage_percentage < 100
        gap_severity = None
        
        if has_gap:
            if coverage_percentage < 50:
                gap_severity = "critical"
            elif coverage_percentage < 75:
                gap_severity = "high"
            elif coverage_percentage < 90:
                gap_severity = "medium"
            else:
                gap_severity = "low"
        
        # Create or update coverage record
        existing = self.db.query(AssignmentCoverage).filter(
            and_(
                AssignmentCoverage.hostel_id == hostel_id,
                AssignmentCoverage.coverage_date == coverage_date,
                AssignmentCoverage.shift == shift
            )
        ).first()
        
        if existing:
            coverage = existing
            coverage.total_supervisors_assigned = total_assigned
            coverage.supervisors_present = present_count
            coverage.supervisors_on_leave = leave_count
            coverage.coverage_percentage = int(coverage_percentage)
            coverage.has_coverage_gap = has_gap
            coverage.gap_severity = gap_severity
        else:
            coverage = AssignmentCoverage(
                hostel_id=hostel_id,
                coverage_date=coverage_date,
                shift=shift,
                total_supervisors_assigned=total_assigned,
                supervisors_present=present_count,
                supervisors_on_leave=leave_count,
                coverage_percentage=int(coverage_percentage),
                has_coverage_gap=has_gap,
                gap_severity=gap_severity
            )
            self.db.add(coverage)
        
        self.db.commit()
        self.db.refresh(coverage)
        
        return coverage
    
    def get_coverage_gaps(
        self,
        hostel_id: Optional[str] = None,
        start_date: date = None,
        end_date: date = None,
        min_severity: str = "low"
    ) -> List[AssignmentCoverage]:
        """Get coverage gaps with severity filter."""
        if start_date is None:
            start_date = date.today()
        if end_date is None:
            end_date = start_date + timedelta(days=7)
        
        severity_order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        min_level = severity_order.get(min_severity, 1)
        
        query = self.db.query(AssignmentCoverage).filter(
            and_(
                AssignmentCoverage.has_coverage_gap == True,
                AssignmentCoverage.coverage_date >= start_date,
                AssignmentCoverage.coverage_date <= end_date
            )
        )
        
        if hostel_id:
            query = query.filter(AssignmentCoverage.hostel_id == hostel_id)
        
        gaps = query.all()
        
        # Filter by severity
        filtered_gaps = [
            gap for gap in gaps
            if severity_order.get(gap.gap_severity, 0) >= min_level
        ]
        
        return sorted(
            filtered_gaps,
            key=lambda x: (
                severity_order.get(x.gap_severity, 0),
                x.coverage_date
            ),
            reverse=True
        )
    
    # ==================== Workload Management ====================
    
    def calculate_workload(
        self,
        supervisor_id: str,
        hostel_id: str,
        measurement_date: date,
        period_type: str = "daily"
    ) -> WorkloadMetric:
        """
        Calculate workload metrics for supervisor.
        
        Args:
            supervisor_id: Supervisor ID
            hostel_id: Hostel ID
            measurement_date: Measurement date
            period_type: Period (daily, weekly, monthly)
            
        Returns:
            Workload metric instance
        """
        # This would integrate with complaint, maintenance, and other modules
        # For now, creating a basic structure
        
        # Get assignment
        assignment = self.get_current_assignment(
            supervisor_id=supervisor_id,
            hostel_id=hostel_id
        )
        
        if not assignment:
            raise BusinessLogicError(
                f"No active assignment found for supervisor {supervisor_id}"
            )
        
        # Calculate metrics (placeholder - would query actual data)
        total_tasks = (
            assignment.complaints_handled +
            assignment.maintenance_requests +
            assignment.attendance_records
        )
        
        # Simple workload calculation
        workload_score = min(total_tasks * 2, 100)  # Cap at 100
        
        if workload_score < 30:
            workload_level = "light"
        elif workload_score < 60:
            workload_level = "normal"
        elif workload_score < 85:
            workload_level = "heavy"
        else:
            workload_level = "overloaded"
        
        # Create or update metric
        existing = self.db.query(WorkloadMetric).filter(
            and_(
                WorkloadMetric.supervisor_id == supervisor_id,
                WorkloadMetric.hostel_id == hostel_id,
                WorkloadMetric.measurement_date == measurement_date,
                WorkloadMetric.period_type == period_type
            )
        ).first()
        
        if existing:
            metric = existing
            metric.total_tasks = total_tasks
            metric.workload_score = workload_score
            metric.workload_level = workload_level
        else:
            metric = WorkloadMetric(
                supervisor_id=supervisor_id,
                hostel_id=hostel_id,
                measurement_date=measurement_date,
                period_type=period_type,
                total_tasks=total_tasks,
                workload_score=workload_score,
                workload_level=workload_level,
                estimated_capacity=100,
                utilization_percentage=workload_score,
                is_balanced=workload_level in ["light", "normal"],
                requires_rebalancing=workload_level == "overloaded"
            )
            self.db.add(metric)
        
        self.db.commit()
        self.db.refresh(metric)
        
        return metric
    
    def get_overloaded_supervisors(
        self,
        hostel_id: Optional[str] = None,
        threshold_score: int = 85
    ) -> List[WorkloadMetric]:
        """Get supervisors with high workload."""
        query = self.db.query(WorkloadMetric).filter(
            WorkloadMetric.workload_score >= threshold_score
        )
        
        if hostel_id:
            query = query.filter(WorkloadMetric.hostel_id == hostel_id)
        
        return query.options(
            joinedload(WorkloadMetric.supervisor)
        ).order_by(
            WorkloadMetric.workload_score.desc()
        ).all()
    
    def recommend_workload_rebalancing(
        self,
        hostel_id: str
    ) -> List[Dict[str, Any]]:
        """
        Recommend workload rebalancing for hostel.
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            List of rebalancing recommendations
        """
        # Get current workloads
        today = date.today()
        workloads = self.db.query(WorkloadMetric).filter(
            and_(
                WorkloadMetric.hostel_id == hostel_id,
                WorkloadMetric.measurement_date == today
            )
        ).all()
        
        if not workloads:
            return []
        
        recommendations = []
        
        # Find overloaded and underloaded supervisors
        overloaded = [w for w in workloads if w.workload_level == "overloaded"]
        light = [w for w in workloads if w.workload_level == "light"]
        
        for over in overloaded:
            for under in light:
                recommendations.append({
                    'from_supervisor_id': over.supervisor_id,
                    'to_supervisor_id': under.supervisor_id,
                    'current_workload_from': over.workload_score,
                    'current_workload_to': under.workload_score,
                    'recommendation': 'Transfer some tasks to balance workload',
                    'priority': 'high' if over.workload_score > 90 else 'medium'
                })
        
        return recommendations
    
    # ==================== Statistics ====================
    
    def get_assignment_statistics(
        self,
        hostel_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get assignment statistics."""
        query = self.db.query(SupervisorAssignment).filter(
            SupervisorAssignment.is_active == True
        )
        
        if hostel_id:
            query = query.filter(SupervisorAssignment.hostel_id == hostel_id)
        
        total = query.count()
        primary = query.filter(SupervisorAssignment.is_primary == True).count()
        
        # Assignment types
        permanent = query.filter(
            SupervisorAssignment.assignment_type == "permanent"
        ).count()
        temporary = query.filter(
            SupervisorAssignment.assignment_type == "temporary"
        ).count()
        backup = query.filter(
            SupervisorAssignment.assignment_type == "backup"
        ).count()
        
        return {
            'total_assignments': total,
            'primary_assignments': primary,
            'secondary_assignments': total - primary,
            'permanent_assignments': permanent,
            'temporary_assignments': temporary,
            'backup_assignments': backup
        }