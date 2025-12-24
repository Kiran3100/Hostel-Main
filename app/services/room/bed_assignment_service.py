"""
Bed Assignment Service

Manages assignment of beds to students and high-level operations like
releasing and swapping beds.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.room import BedAssignmentRepository, BedRepository
from app.repositories.student import StudentRepository
from app.schemas.room import (
    BedAssignmentRequest,
    BedReleaseRequest,
    BedSwapRequest,
    BedAssignment,
    BedDetailedStatus,
)
from app.core.exceptions import ValidationException, BusinessLogicException
from app.models.base.enums import BedStatus


class BedAssignmentService:
    """
    High-level service for bed assignments.

    Responsibilities:
    - Assign a bed to a student
    - Release (vacate) a bed
    - Swap beds between two students
    - List assignments for bed/student
    - Get detailed bed status
    """

    def __init__(
        self,
        bed_assignment_repo: BedAssignmentRepository,
        bed_repo: BedRepository,
        student_repo: StudentRepository,
    ) -> None:
        self.bed_assignment_repo = bed_assignment_repo
        self.bed_repo = bed_repo
        self.student_repo = student_repo

    # -------------------------------------------------------------------------
    # Core operations
    # -------------------------------------------------------------------------

    def assign_bed(
        self,
        db: Session,
        request: BedAssignmentRequest,
    ) -> BedAssignment:
        """
        Assign a bed to a student.

        Ensures:
        - Bed exists and is available
        - Student exists
        - No active conflicting assignment
        """
        bed = self.bed_repo.get_by_id(db, request.bed_id)
        if not bed:
            raise ValidationException("Bed not found")

        if bed.status not in {BedStatus.AVAILABLE, BedStatus.RESERVED}:
            raise BusinessLogicException("Bed is not available for assignment")

        student = self.student_repo.get_by_id(db, request.student_id)
        if not student:
            raise ValidationException("Student not found")

        # Ensure no active assignment on this bed
        active_assignment = self.bed_assignment_repo.get_active_by_bed(
            db, request.bed_id
        )
        if active_assignment:
            raise BusinessLogicException("Bed already assigned")

        payload = request.model_dump(exclude_none=True)
        obj = self.bed_assignment_repo.create_assignment(db, payload)

        # Optionally update bed status
        self.bed_repo.update_status(
            db,
            bed,
            status=BedStatus.OCCUPIED,
        )

        return BedAssignment.model_validate(obj)

    def release_bed(
        self,
        db: Session,
        request: BedReleaseRequest,
    ) -> BedAssignment:
        """
        Release (vacate) a bed.

        Ensures:
        - Active assignment exists for bed
        - Updates assignment and bed status
        """
        bed = self.bed_repo.get_by_id(db, request.bed_id)
        if not bed:
            raise ValidationException("Bed not found")

        assignment = self.bed_assignment_repo.get_active_by_bed(db, request.bed_id)
        if not assignment:
            raise BusinessLogicException("No active assignment for this bed")

        updated = self.bed_assignment_repo.release_assignment(
            db=db,
            assignment_id=assignment.id,
            release_date=request.release_date or datetime.utcnow(),
            release_reason=request.reason,
            check_out_condition=request.room_condition,
        )

        # Mark bed back to AVAILABLE or MAINTENANCE based on condition
        new_status = (
            BedStatus.MAINTENANCE
            if request.room_condition and request.room_condition.lower() == "needs_maintenance"
            else BedStatus.AVAILABLE
        )
        self.bed_repo.update_status(db, bed, status=new_status)

        return BedAssignment.model_validate(updated)

    def swap_beds(
        self,
        db: Session,
        request: BedSwapRequest,
    ) -> List[BedAssignment]:
        """
        Swap beds between two students.

        Ensures:
        - Both beds and students exist
        - Active assignments exist
        - Beds are distinct
        """
        if request.student_1_id == request.student_2_id:
            raise ValidationException("Cannot swap beds between the same student")
        if request.bed_1_id == request.bed_2_id:
            raise ValidationException("Cannot swap the same bed")

        bed1 = self.bed_repo.get_by_id(db, request.bed_1_id)
        bed2 = self.bed_repo.get_by_id(db, request.bed_2_id)
        if not bed1 or not bed2:
            raise ValidationException("One or both beds not found")

        s1 = self.student_repo.get_by_id(db, request.student_1_id)
        s2 = self.student_repo.get_by_id(db, request.student_2_id)
        if not s1 or not s2:
            raise ValidationException("One or both students not found")

        a1 = self.bed_assignment_repo.get_active_by_bed(db, bed1.id)
        a2 = self.bed_assignment_repo.get_active_by_bed(db, bed2.id)
        if not a1 or not a2:
            raise BusinessLogicException("Both beds must have active assignments")

        result = self.bed_assignment_repo.swap_assignments(
            db=db,
            assignment1=a1,
            assignment2=a2,
            swap_date=request.swap_date or datetime.utcnow(),
            reason=request.reason,
        )

        return [BedAssignment.model_validate(r) for r in result]

    # -------------------------------------------------------------------------
    # Listing & status
    # -------------------------------------------------------------------------

    def list_assignments_for_bed(
        self,
        db: Session,
        bed_id: UUID,
    ) -> List[BedAssignment]:
        objs = self.bed_assignment_repo.get_history_for_bed(db, bed_id)
        return [BedAssignment.model_validate(o) for o in objs]

    def list_assignments_for_student(
        self,
        db: Session,
        student_id: UUID,
    ) -> List[BedAssignment]:
        objs = self.bed_assignment_repo.get_history_for_student(db, student_id)
        return [BedAssignment.model_validate(o) for o in objs]

    def get_bed_status(
        self,
        db: Session,
        bed_id: UUID,
    ) -> BedDetailedStatus:
        """
        Return comprehensive status of a bed: current assignment, condition,
        maintenance info, and basic utilization metrics.
        """
        status_dict = self.bed_assignment_repo.get_detailed_status(db, bed_id)
        if not status_dict:
            raise ValidationException("Bed not found")

        return BedDetailedStatus.model_validate(status_dict)