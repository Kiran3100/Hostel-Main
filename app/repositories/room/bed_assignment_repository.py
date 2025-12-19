# app/repositories/room/bed_assignment_repository.py
"""
Bed assignment repository with intelligent assignment and optimization.
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, and_, or_, func, case, desc
from sqlalchemy.orm import Session, joinedload

from app.models.room import (
    BedAssignment,
    AssignmentRule,
    AssignmentConflict,
    AssignmentOptimization,
    AssignmentHistory,
    AssignmentPreference,
    Bed,
    Room,
)
from .base_repository import BaseRepository


class BedAssignmentRepository(BaseRepository[BedAssignment]):
    """
    Repository for BedAssignment entity and related models.
    
    Handles:
    - Bed assignment operations
    - Assignment rules and automation
    - Conflict detection and resolution
    - Assignment optimization
    - Assignment history tracking
    - Student preferences
    """

    def __init__(self, session: Session):
        super().__init__(BedAssignment, session)

    # ============================================================================
    # BED ASSIGNMENT OPERATIONS
    # ============================================================================

    def create_assignment_with_validation(
        self,
        assignment_data: Dict[str, Any],
        validate_conflicts: bool = True,
        commit: bool = True
    ) -> Tuple[Optional[BedAssignment], List[str]]:
        """
        Create bed assignment with validation and conflict checking.
        
        Args:
            assignment_data: Assignment data
            validate_conflicts: Whether to check for conflicts
            commit: Whether to commit transaction
            
        Returns:
            Tuple of (created assignment, list of warnings)
        """
        try:
            warnings = []
            
            # Validate bed availability
            bed_id = assignment_data.get('bed_id')
            occupied_from = assignment_data.get('occupied_from')
            expected_vacate_date = assignment_data.get('expected_vacate_date')
            
            if validate_conflicts:
                conflicts = self.check_assignment_conflicts(
                    bed_id,
                    occupied_from,
                    expected_vacate_date
                )
                
                if conflicts:
                    # Log conflicts
                    for conflict in conflicts:
                        self._create_conflict_record(
                            bed_id=bed_id,
                            conflict_type='DOUBLE_BOOKING',
                            description=conflict
                        )
                    return None, [f"Conflict detected: {c}" for c in conflicts]
            
            # Check bed availability
            bed = self.session.execute(
                select(Bed).where(Bed.id == bed_id)
            ).scalar_one_or_none()
            
            if not bed:
                return None, ["Bed not found"]
            
            if not bed.is_available or bed.is_occupied:
                warnings.append("Bed is currently not available")
            
            # Create assignment
            assignment = self.create(assignment_data, commit=False)
            
            # Update bed status
            bed.is_occupied = True
            bed.is_available = False
            bed.current_student_id = assignment_data.get('student_id')
            bed.occupied_from = occupied_from
            bed.expected_vacate_date = expected_vacate_date
            
            # Create assignment history record
            history = AssignmentHistory(
                assignment_id=assignment.id,
                bed_id=bed_id,
                student_id=assignment_data.get('student_id'),
                room_id=assignment_data.get('room_id'),
                change_type='CREATED',
                change_date=datetime.utcnow(),
                occupied_from=occupied_from,
                new_values=assignment_data
            )
            self.session.add(history)
            
            if commit:
                self.session.commit()
                self.session.refresh(assignment)
            
            return assignment, warnings
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to create assignment: {str(e)}")

    def check_assignment_conflicts(
        self,
        bed_id: str,
        start_date: date,
        end_date: Optional[date] = None
    ) -> List[str]:
        """
        Check for assignment conflicts.
        
        Args:
            bed_id: Bed ID
            start_date: Assignment start date
            end_date: Assignment end date
            
        Returns:
            List of conflict descriptions
        """
        conflicts = []
        
        # Check for overlapping assignments
        query = select(BedAssignment).where(
            and_(
                BedAssignment.bed_id == bed_id,
                BedAssignment.is_active == True,
                BedAssignment.occupied_from <= (end_date or date.max)
            )
        )
        
        if end_date:
            query = query.where(
                or_(
                    BedAssignment.expected_vacate_date.is_(None),
                    BedAssignment.expected_vacate_date >= start_date
                )
            )
        
        existing_assignments = self.session.execute(query).scalars().all()
        
        for assignment in existing_assignments:
            conflicts.append(
                f"Overlapping assignment for student {assignment.student_id} "
                f"from {assignment.occupied_from} to "
                f"{assignment.expected_vacate_date or 'indefinite'}"
            )
        
        return conflicts

    def find_active_assignments(
        self,
        hostel_id: Optional[str] = None,
        room_id: Optional[str] = None,
        student_id: Optional[str] = None
    ) -> List[BedAssignment]:
        """
        Find active bed assignments.
        
        Args:
            hostel_id: Hostel ID filter
            room_id: Room ID filter
            student_id: Student ID filter
            
        Returns:
            List of active assignments
        """
        filters = {'is_active': True, 'assignment_status': 'ACTIVE'}
        
        if hostel_id:
            filters['hostel_id'] = hostel_id
        if room_id:
            filters['room_id'] = room_id
        if student_id:
            filters['student_id'] = student_id
        
        return self.find_by_criteria(
            filters,
            order_by='occupied_from'
        )

    def find_student_current_assignment(
        self,
        student_id: str
    ) -> Optional[BedAssignment]:
        """
        Find student's current active assignment.
        
        Args:
            student_id: Student ID
            
        Returns:
            Current assignment or None
        """
        assignments = self.find_by_criteria({
            'student_id': student_id,
            'is_active': True,
            'assignment_status': 'ACTIVE'
        })
        
        return assignments[0] if assignments else None

    def complete_assignment(
        self,
        assignment_id: str,
        actual_vacate_date: date,
        completion_data: Optional[Dict[str, Any]] = None,
        commit: bool = True
    ) -> Optional[BedAssignment]:
        """
        Complete a bed assignment.
        
        Args:
            assignment_id: Assignment ID
            actual_vacate_date: Actual vacate date
            completion_data: Additional completion data
            commit: Whether to commit transaction
            
        Returns:
            Completed assignment
        """
        try:
            assignment = self.find_by_id(assignment_id)
            if not assignment:
                return None
            
            # Update assignment
            assignment.actual_vacate_date = actual_vacate_date
            assignment.is_active = False
            assignment.assignment_status = 'COMPLETED'
            assignment.last_status_change = datetime.utcnow()
            
            # Calculate duration
            if assignment.occupied_from:
                duration = (actual_vacate_date - assignment.occupied_from).days
                assignment.duration_days = duration
                assignment.duration_months = Decimal(duration / 30)
            
            # Update with additional data
            if completion_data:
                for key, value in completion_data.items():
                    if hasattr(assignment, key):
                        setattr(assignment, key, value)
            
            # Release bed
            bed = self.session.execute(
                select(Bed).where(Bed.id == assignment.bed_id)
            ).scalar_one_or_none()
            
            if bed:
                bed.is_occupied = False
                bed.is_available = True
                bed.current_student_id = None
                bed.occupied_from = None
                bed.expected_vacate_date = None
                bed.last_release_date = date.today()
            
            # Create history record
            history = AssignmentHistory(
                assignment_id=assignment_id,
                bed_id=assignment.bed_id,
                student_id=assignment.student_id,
                room_id=assignment.room_id,
                change_type='COMPLETED',
                change_date=datetime.utcnow(),
                occupied_from=assignment.occupied_from,
                occupied_to=actual_vacate_date,
                duration_days=assignment.duration_days,
                total_rent_paid=assignment.total_rent_paid
            )
            self.session.add(history)
            
            if commit:
                self.session.commit()
                self.session.refresh(assignment)
            
            return assignment
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to complete assignment: {str(e)}")

    def transfer_assignment(
        self,
        assignment_id: str,
        new_bed_id: str,
        transfer_date: date,
        reason: str,
        approved_by: Optional[str] = None,
        commit: bool = True
    ) -> Optional[BedAssignment]:
        """
        Transfer student to a different bed.
        
        Args:
            assignment_id: Current assignment ID
            new_bed_id: New bed ID
            transfer_date: Transfer date
            reason: Transfer reason
            approved_by: Approver user ID
            commit: Whether to commit transaction
            
        Returns:
            New assignment
        """
        try:
            # Get current assignment
            current_assignment = self.find_by_id(assignment_id)
            if not current_assignment:
                return None
            
            # Validate new bed
            new_bed = self.session.execute(
                select(Bed).where(Bed.id == new_bed_id)
            ).scalar_one_or_none()
            
            if not new_bed or not new_bed.is_available:
                raise ValueError("New bed is not available")
            
            # Complete current assignment
            self.complete_assignment(
                assignment_id,
                transfer_date,
                {'is_transfer': True, 'transfer_reason': reason},
                commit=False
            )
            
            # Create new assignment
            new_assignment_data = {
                'bed_id': new_bed_id,
                'student_id': current_assignment.student_id,
                'room_id': new_bed.room_id,
                'hostel_id': current_assignment.hostel_id,
                'occupied_from': transfer_date,
                'expected_vacate_date': current_assignment.expected_vacate_date,
                'monthly_rent': current_assignment.monthly_rent,
                'assignment_type': 'TRANSFER',
                'assignment_source': 'TRANSFER',
                'is_transfer': True,
                'previous_bed_id': current_assignment.bed_id,
                'transfer_reason': reason,
                'transfer_date': transfer_date,
                'transfer_approved_by': approved_by,
                'is_confirmed': True
            }
            
            new_assignment, _ = self.create_assignment_with_validation(
                new_assignment_data,
                validate_conflicts=True,
                commit=False
            )
            
            if commit:
                self.session.commit()
                if new_assignment:
                    self.session.refresh(new_assignment)
            
            return new_assignment
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to transfer assignment: {str(e)}")

    # ============================================================================
    # ASSIGNMENT RULES
    # ============================================================================

    def create_assignment_rule(
        self,
        rule_data: Dict[str, Any],
        commit: bool = True
    ) -> AssignmentRule:
        """
        Create assignment rule.
        
        Args:
            rule_data: Rule data
            commit: Whether to commit transaction
            
        Returns:
            Created assignment rule
        """
        try:
            rule = AssignmentRule(**rule_data)
            self.session.add(rule)
            
            if commit:
                self.session.commit()
                self.session.refresh(rule)
            
            return rule
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to create assignment rule: {str(e)}")

    def find_active_rules(
        self,
        hostel_id: str,
        rule_type: Optional[str] = None
    ) -> List[AssignmentRule]:
        """
        Find active assignment rules.
        
        Args:
            hostel_id: Hostel ID
            rule_type: Rule type filter
            
        Returns:
            List of active rules ordered by priority
        """
        query = select(AssignmentRule).where(
            and_(
                AssignmentRule.hostel_id == hostel_id,
                AssignmentRule.is_active == True
            )
        )
        
        if rule_type:
            query = query.where(AssignmentRule.rule_type == rule_type)
        
        query = query.order_by(
            AssignmentRule.priority,
            AssignmentRule.execution_order
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def execute_assignment_rules(
        self,
        hostel_id: str,
        assignment_request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute assignment rules for a request.
        
        Args:
            hostel_id: Hostel ID
            assignment_request: Assignment request data
            
        Returns:
            Dictionary with rule execution results
        """
        rules = self.find_active_rules(hostel_id)
        
        results = {
            'matched_rules': [],
            'score': Decimal('0.00'),
            'recommended_beds': [],
            'warnings': [],
            'requirements_met': []
        }
        
        for rule in rules:
            # Execute rule logic (simplified)
            if self._evaluate_rule(rule, assignment_request):
                results['matched_rules'].append(rule.rule_name)
                results['score'] += Decimal('10.00')
                
                # Update rule execution stats
                rule.execution_count += 1
                rule.success_count += 1
                rule.last_executed = datetime.utcnow()
        
        return results

    def _evaluate_rule(
        self,
        rule: AssignmentRule,
        request: Dict[str, Any]
    ) -> bool:
        """
        Evaluate if assignment request matches rule conditions.
        
        Args:
            rule: Assignment rule
            request: Assignment request data
            
        Returns:
            True if rule matches, False otherwise
        """
        # Simplified rule evaluation
        conditions = rule.conditions or {}
        
        for key, value in conditions.items():
            if key in request and request[key] != value:
                return False
        
        return True

    # ============================================================================
    # ASSIGNMENT CONFLICTS
    # ============================================================================

    def _create_conflict_record(
        self,
        bed_id: str,
        conflict_type: str,
        description: str,
        student_id: Optional[str] = None,
        severity: str = 'MEDIUM'
    ) -> AssignmentConflict:
        """
        Create conflict record.
        
        Args:
            bed_id: Bed ID
            conflict_type: Conflict type
            description: Conflict description
            student_id: Student ID
            severity: Conflict severity
            
        Returns:
            Created conflict record
        """
        conflict = AssignmentConflict(
            bed_id=bed_id,
            student_id=student_id,
            conflict_type=conflict_type,
            conflict_severity=severity,
            conflict_description=description,
            conflict_reason=description,
            detected_at=datetime.utcnow(),
            detected_by='SYSTEM',
            conflict_status='DETECTED'
        )
        self.session.add(conflict)
        return conflict

    def find_unresolved_conflicts(
        self,
        hostel_id: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[AssignmentConflict]:
        """
        Find unresolved assignment conflicts.
        
        Args:
            hostel_id: Hostel ID filter
            severity: Severity filter
            
        Returns:
            List of unresolved conflicts
        """
        query = select(AssignmentConflict).where(
            AssignmentConflict.is_resolved == False
        )
        
        if severity:
            query = query.where(AssignmentConflict.conflict_severity == severity)
        
        query = query.order_by(
            desc(AssignmentConflict.conflict_severity),
            AssignmentConflict.detected_at
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution_method: str,
        resolved_by: str,
        resolution_notes: Optional[str] = None,
        commit: bool = True
    ) -> Optional[AssignmentConflict]:
        """
        Resolve assignment conflict.
        
        Args:
            conflict_id: Conflict ID
            resolution_method: Resolution method
            resolved_by: Resolver user ID
            resolution_notes: Resolution notes
            commit: Whether to commit transaction
            
        Returns:
            Resolved conflict
        """
        try:
            conflict = self.session.execute(
                select(AssignmentConflict).where(
                    AssignmentConflict.id == conflict_id
                )
            ).scalar_one_or_none()
            
            if not conflict:
                return None
            
            conflict.is_resolved = True
            conflict.conflict_status = 'RESOLVED'
            conflict.resolution_method = resolution_method
            conflict.resolved_by = resolved_by
            conflict.resolved_at = datetime.utcnow()
            conflict.resolution_notes = resolution_notes
            
            if commit:
                self.session.commit()
                self.session.refresh(conflict)
            
            return conflict
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to resolve conflict: {str(e)}")

    # ============================================================================
    # ASSIGNMENT OPTIMIZATION
    # ============================================================================

    def run_assignment_optimization(
        self,
        hostel_id: str,
        optimization_type: str = 'INITIAL_PLACEMENT',
        optimization_params: Optional[Dict[str, Any]] = None,
        commit: bool = True
    ) -> AssignmentOptimization:
        """
        Run assignment optimization algorithm.
        
        Args:
            hostel_id: Hostel ID
            optimization_type: Type of optimization
            optimization_params: Optimization parameters
            commit: Whether to commit transaction
            
        Returns:
            Optimization results
        """
        try:
            # Get available beds and pending assignments
            available_beds = self._get_available_beds_for_optimization(hostel_id)
            pending_requests = self._get_pending_assignment_requests(hostel_id)
            
            # Run optimization algorithm
            optimization_results = self._execute_optimization_algorithm(
                available_beds,
                pending_requests,
                optimization_params or {}
            )
            
            # Create optimization record
            optimization = AssignmentOptimization(
                hostel_id=hostel_id,
                optimization_name=f"Optimization {datetime.utcnow()}",
                optimization_type=optimization_type,
                run_date=datetime.utcnow(),
                algorithm_used='GREEDY_MATCHING',
                algorithm_version='1.0',
                algorithm_parameters=optimization_params,
                total_beds_considered=len(available_beds),
                total_students_considered=len(pending_requests),
                available_beds=len(available_beds),
                pending_assignments=len(pending_requests),
                execution_status='COMPLETED',
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
                assignments_generated=optimization_results['assignments_count'],
                optimization_results=optimization_results,
                overall_optimization_score=optimization_results.get('score', Decimal('0.00'))
            )
            self.session.add(optimization)
            
            if commit:
                self.session.commit()
                self.session.refresh(optimization)
            
            return optimization
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to run optimization: {str(e)}")

    def _get_available_beds_for_optimization(
        self,
        hostel_id: str
    ) -> List[Bed]:
        """Get available beds for optimization."""
        query = select(Bed).join(Room).where(
            and_(
                Room.hostel_id == hostel_id,
                Bed.is_available == True,
                Bed.is_functional == True,
                Bed.is_deleted == False
            )
        )
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def _get_pending_assignment_requests(
        self,
        hostel_id: str
    ) -> List[Dict[str, Any]]:
        """Get pending assignment requests (simplified)."""
        # This would typically query a requests table
        return []

    def _execute_optimization_algorithm(
        self,
        available_beds: List[Bed],
        requests: List[Dict[str, Any]],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute optimization algorithm.
        
        Simplified greedy matching algorithm.
        """
        assignments = []
        score = Decimal('0.00')
        
        for request in requests:
            # Find best matching bed
            best_bed = None
            best_score = Decimal('0.00')
            
            for bed in available_beds:
                match_score = self._calculate_match_score(bed, request)
                if match_score > best_score:
                    best_score = match_score
                    best_bed = bed
            
            if best_bed:
                assignments.append({
                    'bed_id': best_bed.id,
                    'student_id': request.get('student_id'),
                    'match_score': float(best_score)
                })
                score += best_score
                available_beds.remove(best_bed)
        
        return {
            'assignments': assignments,
            'assignments_count': len(assignments),
            'score': score,
            'average_match_score': score / len(assignments) if assignments else Decimal('0.00')
        }

    def _calculate_match_score(
        self,
        bed: Bed,
        request: Dict[str, Any]
    ) -> Decimal:
        """Calculate matching score between bed and request."""
        score = Decimal('50.00')  # Base score
        
        # Add scoring logic based on preferences
        if request.get('bed_type') == bed.bed_type:
            score += Decimal('20.00')
        
        if request.get('prefers_upper_bunk') and bed.is_upper_bunk:
            score += Decimal('15.00')
        
        if request.get('prefers_lower_bunk') and bed.is_lower_bunk:
            score += Decimal('15.00')
        
        return score

    # ============================================================================
    # ASSIGNMENT HISTORY
    # ============================================================================

    def get_assignment_history(
        self,
        assignment_id: Optional[str] = None,
        bed_id: Optional[str] = None,
        student_id: Optional[str] = None,
        limit: int = 50
    ) -> List[AssignmentHistory]:
        """
        Get assignment history records.
        
        Args:
            assignment_id: Assignment ID filter
            bed_id: Bed ID filter
            student_id: Student ID filter
            limit: Maximum number of records
            
        Returns:
            List of history records
        """
        query = select(AssignmentHistory)
        
        conditions = []
        if assignment_id:
            conditions.append(AssignmentHistory.assignment_id == assignment_id)
        if bed_id:
            conditions.append(AssignmentHistory.bed_id == bed_id)
        if student_id:
            conditions.append(AssignmentHistory.student_id == student_id)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(desc(AssignmentHistory.change_date)).limit(limit)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ============================================================================
    # ASSIGNMENT PREFERENCES
    # ============================================================================

    def create_assignment_preference(
        self,
        preference_data: Dict[str, Any],
        commit: bool = True
    ) -> AssignmentPreference:
        """
        Create assignment preference.
        
        Args:
            preference_data: Preference data
            commit: Whether to commit transaction
            
        Returns:
            Created preference
        """
        try:
            preference = AssignmentPreference(**preference_data)
            self.session.add(preference)
            
            if commit:
                self.session.commit()
                self.session.refresh(preference)
            
            return preference
            
        except Exception as e:
            self.session.rollback()
            raise RuntimeError(f"Failed to create preference: {str(e)}")

    def find_student_preferences(
        self,
        student_id: str,
        is_active: bool = True
    ) -> List[AssignmentPreference]:
        """
        Find student assignment preferences.
        
        Args:
            student_id: Student ID
            is_active: Active status filter
            
        Returns:
            List of preferences
        """
        query = select(AssignmentPreference).where(
            AssignmentPreference.student_id == student_id
        )
        
        if is_active:
            query = query.where(AssignmentPreference.is_active == True)
        
        query = query.order_by(AssignmentPreference.preference_priority)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    # ============================================================================
    # ASSIGNMENT STATISTICS
    # ============================================================================

    def get_assignment_statistics(
        self,
        hostel_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive assignment statistics.
        
        Args:
            hostel_id: Hostel ID
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Dictionary with assignment statistics
        """
        query = select(
            func.count(BedAssignment.id).label('total_assignments'),
            func.sum(
                case((BedAssignment.is_active == True, 1), else_=0)
            ).label('active_assignments'),
            func.sum(
                case((BedAssignment.assignment_status == 'COMPLETED', 1), else_=0)
            ).label('completed_assignments'),
            func.sum(
                case((BedAssignment.is_transfer == True, 1), else_=0)
            ).label('transfers'),
            func.avg(BedAssignment.duration_days).label('avg_duration_days'),
            func.sum(BedAssignment.total_rent_paid).label('total_revenue'),
            func.sum(BedAssignment.outstanding_balance).label('total_outstanding')
        ).where(BedAssignment.hostel_id == hostel_id)
        
        if start_date:
            query = query.where(BedAssignment.occupied_from >= start_date)
        if end_date:
            query = query.where(BedAssignment.occupied_from <= end_date)
        
        result = self.session.execute(query).one()
        
        return {
            'total_assignments': result.total_assignments or 0,
            'active_assignments': result.active_assignments or 0,
            'completed_assignments': result.completed_assignments or 0,
            'transfers': result.transfers or 0,
            'avg_duration_days': round(float(result.avg_duration_days or 0), 2),
            'total_revenue': float(result.total_revenue or 0),
            'total_outstanding': float(result.total_outstanding or 0)
        }

    def find_expiring_assignments(
        self,
        hostel_id: str,
        days_ahead: int = 30
    ) -> List[BedAssignment]:
        """
        Find assignments expiring within specified days.
        
        Args:
            hostel_id: Hostel ID
            days_ahead: Number of days to look ahead
            
        Returns:
            List of expiring assignments
        """
        expiry_date = date.today() + timedelta(days=days_ahead)
        
        query = select(BedAssignment).where(
            and_(
                BedAssignment.hostel_id == hostel_id,
                BedAssignment.is_active == True,
                BedAssignment.expected_vacate_date.isnot(None),
                BedAssignment.expected_vacate_date <= expiry_date
            )
        ).order_by(BedAssignment.expected_vacate_date)
        
        result = self.session.execute(query)
        return list(result.scalars().all())

    def find_overdue_assignments(
        self,
        hostel_id: str
    ) -> List[BedAssignment]:
        """
        Find assignments that are overdue (past expected vacate date).
        
        Args:
            hostel_id: Hostel ID
            
        Returns:
            List of overdue assignments
        """
        query = select(BedAssignment).where(
            and_(
                BedAssignment.hostel_id == hostel_id,
                BedAssignment.is_active == True,
                BedAssignment.expected_vacate_date < date.today(),
                BedAssignment.actual_vacate_date.is_(None)
            )
        ).order_by(BedAssignment.expected_vacate_date)
        
        result = self.session.execute(query)
        return list(result.scalars().all())